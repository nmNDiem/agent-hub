from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

from fastapi import status
from sqlalchemy import and_, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.catalog.file_extractor import ExtractionError
from agent_hub_api.catalog.import_pipeline import (
    analyze_catalog,
    serialize_product,
)
from agent_hub_api.catalog.import_types import ImportIssueData
from agent_hub_api.catalog.models import (
    CatalogImport,
    CatalogImportIssue,
    CatalogImportMappingProfile,
    CatalogImportStagedRecord,
    InventoryLevel,
    Location,
    LocationVariant,
    Product,
    ProductImage,
    ProductVariant,
)
from agent_hub_api.catalog.options import set_variant_options
from agent_hub_api.catalog.read_models import AuthorizedCatalogScope, CatalogQuery
from agent_hub_api.catalog.read_service import CatalogReadService
from agent_hub_api.catalog.schemas import (
    CatalogImportResponse,
    CatalogSearchItem,
    CatalogSearchResponse,
    ImportDiffSummary,
    ImportIssueDetail,
    ResolveImportIssueRequest,
    UniversalImportCommitResponse,
)
from agent_hub_api.catalog.scope_service import resolve_location, upsert_variant_location
from agent_hub_api.core.config import Settings
from agent_hub_api.core.errors import ApiError
from agent_hub_api.identity.models import User
from agent_hub_api.workspaces.service import WorkspaceService


def _cell_value(fields: dict[str, Any], name: str) -> Any:
    cell = fields.get(name, {"state": "missing", "value": None})
    return cell.get("value") if cell.get("state") == "value" else None


def _apply_cell(target: object, attribute: str, cell: dict[str, Any]) -> bool:
    state = cell.get("state")
    if state in {"missing", "blank"}:
        return False
    value = None if state == "explicit_null" else cell.get("value")
    if attribute in {"price", "compare_at_price", "price_override"} and value is not None:
        value = Decimal(str(value))
    if getattr(target, attribute) == value:
        return False
    setattr(target, attribute, value)
    return True


class UniversalCatalogService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    async def _authorize(self, user: User, workspace_id: UUID, *, write: bool = False) -> None:
        _, role = await WorkspaceService(self.session).get_for_user(user.id, workspace_id)
        if write and role not in {"owner", "admin"}:
            raise ApiError(
                status.HTTP_403_FORBIDDEN, "FORBIDDEN", "Bạn không có quyền thay đổi catalog."
            )

    async def create_and_analyze(
        self, user: User, workspace_id: UUID, filename: str, content: bytes
    ) -> CatalogImportResponse:
        await self._authorize(user, workspace_id, write=True)
        await self.session.commit()
        now = datetime.now(UTC)
        job = CatalogImport(
            workspace_id=workspace_id,
            payload_sha256=hashlib.sha256(content).hexdigest(),
            original_filename=filename[:255],
            source_content=content,
            status="analyzing",
            lease_expires_at=None,
            summary_json={},
            metadata_json={},
            created_at=now,
            updated_at=now,
        )
        async with self.session.begin():
            self.session.add(job)
            await self.session.flush()
            job_id = job.id
        try:
            await self._analyze(job, workspace_id)
        except ExtractionError as exc:
            async with self.session.begin():
                job.status = "failed"
                job.result = {"code": "FILE_ERROR", "message": str(exc)}
                job.updated_at = datetime.now(UTC)
        return await self._get_response(workspace_id, job_id)

    async def _analyze(
        self, job: CatalogImport, workspace_id: UUID, mapping_override: dict[str, str] | None = None
    ) -> None:
        assert job.source_content is not None and job.original_filename is not None
        analysis = analyze_catalog(
            job.source_content,
            job.original_filename,
            max_bytes=self.settings.catalog_import_max_bytes,
            max_sheets=self.settings.catalog_import_max_sheets,
            max_rows=self.settings.catalog_import_max_rows,
            max_columns=self.settings.catalog_import_max_columns,
            mapping_override=mapping_override,
        )
        serialized = [serialize_product(product) for product in analysis.products]
        product_skus = {
            str(_cell_value(item["fields"], "product_sku")).upper()
            for item in serialized
            if _cell_value(item["fields"], "product_sku")
        }
        variant_skus = {
            str(_cell_value(v["fields"], "variant_sku")).upper()
            for item in serialized
            for v in item["variants"]
            if _cell_value(v["fields"], "variant_sku")
        }
        products_by_sku = (
            {
                p.product_sku: p
                for p in (
                    await self.session.scalars(
                        select(Product).where(
                            Product.workspace_id == workspace_id,
                            Product.product_sku.in_(product_skus),
                        )
                    )
                ).all()
            }
            if product_skus
            else {}
        )
        variants_by_sku = (
            {
                v.variant_sku: v
                for v in (
                    await self.session.scalars(
                        select(ProductVariant).where(
                            ProductVariant.workspace_id == workspace_id,
                            ProductVariant.variant_sku.in_(variant_skus),
                        )
                    )
                ).all()
            }
            if variant_skus
            else {}
        )
        locations = list(
            (
                await self.session.scalars(
                    select(Location).where(Location.workspace_id == workspace_id)
                )
            ).all()
        )
        locations_by_code = {
            location.code: location
            for location in locations
            if location.code is not None and location.is_active
        }
        known_location_codes = set(locations_by_code)
        existing_location_data: dict[
            tuple[int, int], tuple[LocationVariant, InventoryLevel | None]
        ] = {}
        if variants_by_sku:
            location_rows = (
                await self.session.execute(
                    select(LocationVariant, InventoryLevel)
                    .outerjoin(
                        InventoryLevel,
                        and_(
                            InventoryLevel.workspace_id == LocationVariant.workspace_id,
                            InventoryLevel.location_id == LocationVariant.location_id,
                            InventoryLevel.variant_id == LocationVariant.variant_id,
                        ),
                    )
                    .where(
                        LocationVariant.workspace_id == workspace_id,
                        LocationVariant.variant_id.in_(
                            [variant.id for variant in variants_by_sku.values()]
                        ),
                    )
                )
            ).all()
            existing_location_data = {
                (assignment.location_id, assignment.variant_id): (assignment, inventory)
                for assignment, inventory in location_rows
            }
        for item in serialized:
            for variant in item["variants"]:
                location_code = _cell_value(variant["fields"], "location_code")
                normalized_code = str(location_code).strip().upper() if location_code else None
                if normalized_code and normalized_code not in known_location_codes:
                    analysis.issues.append(
                        ImportIssueData(
                            "UNKNOWN_LOCATION",
                            "error",
                            f'Location code "{normalized_code}" không tồn tại trong workspace.',
                            variant["source"],
                            {"location_code": normalized_code},
                        )
                    )
        product_ids = {v.product_id for v in variants_by_sku.values()}
        existing_by_id = (
            {
                p.id: p
                for p in (
                    await self.session.scalars(
                        select(Product).where(
                            Product.workspace_id == workspace_id, Product.id.in_(product_ids)
                        )
                    )
                ).all()
            }
            if product_ids
            else {}
        )
        existing_product_ids = {product.id for product in products_by_sku.values()} | set(
            existing_by_id
        )
        implicit_variants_by_product = (
            {
                variant.product_id: variant
                for variant in (
                    await self.session.scalars(
                        select(ProductVariant).where(
                            ProductVariant.workspace_id == workspace_id,
                            ProductVariant.product_id.in_(existing_product_ids),
                            ProductVariant.variant_sku.is_(None),
                        )
                    )
                ).all()
            }
            if existing_product_ids
            else {}
        )
        records: list[CatalogImportStagedRecord] = []
        counts = {
            "products": {"create": 0, "update": 0, "unchanged": 0, "conflict": 0},
            "variants": {"create": 0, "update": 0, "unchanged": 0, "conflict": 0},
            "images": {"create": 0, "update": 0, "unchanged": 0, "conflict": 0},
        }
        variant_mutations: dict[str, str] = {}
        mutation_priority = {"unchanged": 0, "update": 1, "create": 2, "conflict": 3}
        for item in serialized:
            sku = _cell_value(item["fields"], "product_sku")
            candidates = {
                variants_by_sku[str(vsku).upper()].product_id
                for v in item["variants"]
                if (vsku := _cell_value(v["fields"], "variant_sku"))
                and str(vsku).upper() in variants_by_sku
            }
            product = products_by_sku.get(str(sku).upper()) if sku else None
            if product:
                candidates.add(product.id)
            mutation = "conflict" if len(candidates) > 1 else "update" if candidates else "create"
            target = next(iter(candidates), None)
            if mutation == "update" and target is not None:
                product = existing_by_id.get(target) or product
                if product and self._product_unchanged(product, item["fields"]):
                    mutation = "unchanged"
            counts["products"][mutation] += 1
            records.append(
                CatalogImportStagedRecord(
                    workspace_id=workspace_id,
                    import_id=job.id,
                    entity_type="product",
                    source_location=item["source"],
                    normalized_json=item,
                    identity_json={
                        "product_sku": sku,
                        "variant_skus": sorted(
                            str(_cell_value(v["fields"], "variant_sku"))
                            for v in item["variants"]
                            if _cell_value(v["fields"], "variant_sku")
                        ),
                    },
                    mutation=mutation,
                    target_entity_id=target,
                )
            )
            variants_for_diff = item["variants"] or [
                {"fields": {}, "options": {}, "source": item["source"]}
            ]
            for variant in variants_for_diff:
                vsku = _cell_value(variant["fields"], "variant_sku")
                existing = (
                    variants_by_sku.get(str(vsku).upper())
                    if vsku
                    else implicit_variants_by_product.get(target)
                    if target
                    else None
                )
                vmutation = "update" if existing else "create"
                location_code = _cell_value(variant["fields"], "location_code")
                resolved_location = locations_by_code.get(
                    str(location_code).strip().upper() if location_code else "DEFAULT"
                )
                location_data = (
                    existing_location_data.get((resolved_location.id, existing.id))
                    if existing is not None and resolved_location is not None
                    else None
                )
                if existing and self._variant_unchanged(existing, variant["fields"], location_data):
                    vmutation = "unchanged"
                variant_key = (
                    str(vsku).strip().upper()
                    if vsku
                    else f"product:{target or sku or item['source']}:default"
                )
                previous = variant_mutations.get(variant_key)
                if previous is None or mutation_priority[vmutation] > mutation_priority[previous]:
                    variant_mutations[variant_key] = vmutation
            counts["images"]["create"] += len(item["images"])
        for mutation in variant_mutations.values():
            counts["variants"][mutation] += 1
        for record in records:
            if record.mutation == "conflict":
                analysis.issues.append(
                    ImportIssueData(
                        "IDENTITY_CONFLICT",
                        "needs_confirmation",
                        "Các định danh trong cùng nhóm trỏ tới nhiều sản phẩm.",
                        record.source_location,
                        record.identity_json,
                    )
                )
        await self.session.execute(
            delete(CatalogImportStagedRecord).where(
                CatalogImportStagedRecord.workspace_id == workspace_id,
                CatalogImportStagedRecord.import_id == job.id,
            )
        )
        await self.session.execute(
            delete(CatalogImportIssue).where(
                CatalogImportIssue.workspace_id == workspace_id,
                CatalogImportIssue.import_id == job.id,
            )
        )
        self.session.add_all(records)
        self.session.add_all(
            [
                CatalogImportIssue(
                    workspace_id=workspace_id,
                    import_id=job.id,
                    issue_type=i.issue_type,
                    severity=i.severity,
                    entity_scope=None,
                    source_location=i.source_location,
                    message=i.message,
                    evidence_json=i.evidence,
                    options_json=i.options,
                    status="open",
                )
                for i in analysis.issues
            ]
        )
        job.file_type = analysis.file_type
        job.schema_fingerprint = analysis.schema_fingerprint
        job.summary_json = cast(dict[str, object], counts)
        job.metadata_json = {**analysis.metadata, "mapping": analysis.mapping}
        profile = await self.session.scalar(
            select(CatalogImportMappingProfile)
            .where(
                CatalogImportMappingProfile.workspace_id == workspace_id,
                CatalogImportMappingProfile.schema_fingerprint == analysis.schema_fingerprint,
            )
            .order_by(CatalogImportMappingProfile.confirmed_by_user.desc())
        )
        if profile is not None:
            profile.last_used_at = datetime.now(UTC)
            job.mapping_profile_id = profile.id
            job.metadata_json = {**job.metadata_json, "mapping_profile_reused": True}
        elif not any(i.severity in {"error", "needs_confirmation"} for i in analysis.issues):
            profile = CatalogImportMappingProfile(
                workspace_id=workspace_id,
                schema_fingerprint=analysis.schema_fingerprint,
                mapping_json=cast(dict[str, object], analysis.mapping),
                confidence=Decimal("1.0"),
                confirmed_by_user=False,
            )
            self.session.add(profile)
            await self.session.flush()
            job.mapping_profile_id = profile.id
        job.catalog_revision_at_analysis = datetime.now(UTC)
        job.updated_at = datetime.now(UTC)
        job.status = (
            "needs_confirmation"
            if any(i.severity in {"error", "needs_confirmation"} for i in analysis.issues)
            else "ready"
        )
        await self.session.commit()

    @staticmethod
    def _product_unchanged(product: Product, fields: dict[str, Any]) -> bool:
        pairs = (
            ("name", "name"),
            ("brand", "brand"),
            ("category", "category"),
            ("price", "base_price"),
            ("compare_at_price", "compare_at_price"),
        )
        return all(
            _cell_value(fields, source) is None
            or str(getattr(product, target)) == str(_cell_value(fields, source))
            for target, source in pairs
        )

    @staticmethod
    def _variant_unchanged(
        variant: ProductVariant,
        fields: dict[str, Any],
        location_data: tuple[LocationVariant, InventoryLevel | None] | None,
    ) -> bool:
        pairs = (
            ("price_override", "price"),
            ("compare_at_price", "compare_at_price"),
        )
        base_unchanged = all(
            _cell_value(fields, source) is None
            or str(getattr(variant, target)) == str(_cell_value(fields, source))
            for target, source in pairs
        )
        if not base_unchanged:
            return False
        location_fields = {
            "stock_quantity": location_data[1].quantity
            if location_data is not None and location_data[1] is not None
            else None,
            "location_price": location_data[0].price_override if location_data else None,
            "location_compare_at_price": (
                location_data[0].compare_at_price_override if location_data else None
            ),
        }
        for source, current in location_fields.items():
            cell = fields.get(source, {"state": "missing", "value": None})
            if cell.get("state") in {"missing", "blank"}:
                continue
            desired = cell.get("value") if cell.get("state") == "value" else None
            if str(current) != str(desired):
                return False
        has_location_reference = _cell_value(fields, "location_code") is not None
        return location_data is not None or not has_location_reference

    async def get(self, user: User, workspace_id: UUID, import_id: int) -> CatalogImportResponse:
        await self._authorize(user, workspace_id)
        return await self._get_response(workspace_id, import_id)

    async def _get_response(self, workspace_id: UUID, import_id: int) -> CatalogImportResponse:
        job = await self.session.scalar(
            select(CatalogImport).where(
                CatalogImport.workspace_id == workspace_id, CatalogImport.id == import_id
            )
        )
        if job is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Không tìm thấy import.")
        issues = list(
            (
                await self.session.scalars(
                    select(CatalogImportIssue)
                    .where(
                        CatalogImportIssue.workspace_id == workspace_id,
                        CatalogImportIssue.import_id == import_id,
                    )
                    .order_by(CatalogImportIssue.id)
                )
            ).all()
        )
        summary = job.summary_json or {"products": {}, "variants": {}, "images": {}}
        return CatalogImportResponse(
            id=job.id,
            status=cast(Any, job.status),
            original_filename=job.original_filename or "catalog",
            file_type=job.file_type,
            schema_fingerprint=job.schema_fingerprint,
            summary=ImportDiffSummary.model_validate(summary),
            issues=[
                ImportIssueDetail(
                    id=i.id,
                    issue_type=i.issue_type,
                    severity=i.severity,
                    message=i.message,
                    source_location=cast(Any, i.source_location),
                    evidence=cast(Any, i.evidence_json),
                    options=cast(Any, i.options_json),
                    status=i.status,
                )
                for i in issues
            ],
            metadata=cast(Any, job.metadata_json or {}),
            result=cast(Any, job.result),
            created_at=job.created_at,
            updated_at=job.updated_at,
        )

    async def resolve(
        self,
        user: User,
        workspace_id: UUID,
        import_id: int,
        issue_id: int,
        request: ResolveImportIssueRequest,
    ) -> CatalogImportResponse:
        await self._authorize(user, workspace_id, write=True)
        issue = await self.session.scalar(
            select(CatalogImportIssue).where(
                CatalogImportIssue.workspace_id == workspace_id,
                CatalogImportIssue.import_id == import_id,
                CatalogImportIssue.id == issue_id,
            )
        )
        if issue is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Không tìm thấy câu hỏi import.")
        if issue.severity == "error" and request.action == "ignore":
            raise ApiError(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "ISSUE_NOT_IGNORABLE",
                "Lỗi dữ liệu này phải được sửa trong tệp rồi phân tích lại.",
            )
        if request.action == "map" and request.field:
            job = await self.session.get(CatalogImport, import_id)
            header = issue.evidence_json.get("header")
            if job is None or not isinstance(header, str):
                raise ApiError(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    "INVALID_RESOLUTION",
                    "Câu trả lời không phù hợp với vấn đề này.",
                )
            current_mapping = cast(dict[str, str], job.metadata_json.get("mapping", {}))
            await self.session.rollback()
            await self._analyze(job, workspace_id, {**current_mapping, header: request.field})
            if job.mapping_profile_id is not None:
                profile = await self.session.get(
                    CatalogImportMappingProfile, job.mapping_profile_id
                )
                if profile is not None:
                    profile.confirmed_by_user = True
                    await self.session.commit()
            return await self._get_response(workspace_id, import_id)
        issue.status = "resolved"
        issue.resolution_json = request.model_dump(mode="json")
        issue.resolved_at = datetime.now(UTC)
        remaining = await self.session.scalar(
            select(func.count())
            .select_from(CatalogImportIssue)
            .where(
                CatalogImportIssue.workspace_id == workspace_id,
                CatalogImportIssue.import_id == import_id,
                CatalogImportIssue.id != issue_id,
                CatalogImportIssue.status == "open",
                CatalogImportIssue.severity.in_(["error", "needs_confirmation"]),
            )
        )
        job = await self.session.get(CatalogImport, import_id)
        if job is not None and not remaining:
            job.status = "ready"
            job.updated_at = datetime.now(UTC)
        await self.session.commit()
        return await self.get(user, workspace_id, import_id)

    async def commit(
        self, user: User, workspace_id: UUID, import_id: int, idempotency_key: str
    ) -> UniversalImportCommitResponse:
        await self._authorize(user, workspace_id, write=True)
        job = await self.session.scalar(
            select(CatalogImport).where(
                CatalogImport.workspace_id == workspace_id, CatalogImport.id == import_id
            )
        )
        if job is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Không tìm thấy import.")
        if job.status == "committed" and job.result:
            return UniversalImportCommitResponse.model_validate({**job.result, "replayed": True})
        if job.status != "ready":
            raise ApiError(
                status.HTTP_409_CONFLICT,
                "IMPORT_NOT_READY",
                "Import còn lỗi hoặc câu hỏi chưa xử lý.",
            )
        if job.idempotency_key and job.idempotency_key != idempotency_key:
            raise ApiError(
                status.HTTP_409_CONFLICT,
                "IDEMPOTENCY_PAYLOAD_MISMATCH",
                "Import đã dùng khóa idempotency khác.",
            )
        result = {
            "import_id": import_id,
            "status": "committed",
            "products_created": 0,
            "products_updated": 0,
            "products_unchanged": 0,
            "variants_created": 0,
            "variants_updated": 0,
            "variants_unchanged": 0,
            "images_created": 0,
            "replayed": False,
        }
        await self.session.rollback()
        try:
            async with self.session.begin():
                job = await self.session.scalar(
                    select(CatalogImport)
                    .where(
                        CatalogImport.workspace_id == workspace_id, CatalogImport.id == import_id
                    )
                    .with_for_update()
                )
                if job is None or job.status != "ready":
                    raise ApiError(
                        status.HTTP_409_CONFLICT,
                        "IMPORT_NOT_READY",
                        "Import đã thay đổi trạng thái.",
                    )
                records = list(
                    (
                        await self.session.scalars(
                            select(CatalogImportStagedRecord)
                            .where(
                                CatalogImportStagedRecord.workspace_id == workspace_id,
                                CatalogImportStagedRecord.import_id == import_id,
                                CatalogImportStagedRecord.entity_type == "product",
                            )
                            .order_by(CatalogImportStagedRecord.id)
                        )
                    ).all()
                )
                job.status = "committing"
                job.idempotency_key = idempotency_key
                variant_outcomes: dict[int, str] = {}
                for record in records:
                    await self._commit_record(workspace_id, record, result, variant_outcomes)
                job.status = "committed"
                job.committed_at = datetime.now(UTC)
                job.completed_at = job.committed_at
                job.updated_at = job.committed_at
                job.result = result
        except IntegrityError as exc:
            raise ApiError(
                status.HTTP_409_CONFLICT,
                "CONCURRENCY_CONFLICT",
                "Catalog đã thay đổi; hãy phân tích lại import.",
            ) from exc
        return UniversalImportCommitResponse.model_validate(result)

    async def _commit_record(
        self,
        workspace_id: UUID,
        record: CatalogImportStagedRecord,
        result: dict[str, Any],
        variant_outcomes: dict[int, str],
    ) -> None:
        data = cast(dict[str, Any], record.normalized_json)
        fields = cast(dict[str, Any], data["fields"])
        product = (
            await self.session.scalar(
                select(Product).where(
                    Product.workspace_id == workspace_id, Product.id == record.target_entity_id
                )
            )
            if record.target_entity_id
            else None
        )
        if product is None:
            product = Product(
                workspace_id=workspace_id,
                name=str(_cell_value(fields, "name")),
                product_sku=(
                    str(_cell_value(fields, "product_sku")).upper()
                    if _cell_value(fields, "product_sku")
                    else None
                ),
                currency=str(_cell_value(fields, "currency") or "VND"),
                attributes_json={},
            )
            self.session.add(product)
            await self.session.flush()
            result["products_created"] += 1
        else:
            result[
                "products_unchanged" if record.mutation == "unchanged" else "products_updated"
            ] += 1
        for attr, source in (
            ("name", "name"),
            ("slug", "slug"),
            ("brand", "brand"),
            ("category", "category"),
            ("price", "base_price"),
            ("compare_at_price", "compare_at_price"),
            ("description", "description_text"),
            ("description_html_source", "description_html_source"),
            ("description_html_sanitized", "description_html_sanitized"),
            ("description_text", "description_text"),
        ):
            if source in fields:
                _apply_cell(product, attr, fields[source])
        variants = cast(list[dict[str, Any]], data["variants"])
        creates_implicit_variant = not variants
        if not variants:
            variants = [
                {
                    "fields": {},
                    "options": {},
                    "source": data["source"],
                }
            ]
        for variant_data in variants:
            vf = cast(dict[str, Any], variant_data["fields"])
            sku = _cell_value(vf, "variant_sku")
            variant = (
                await self.session.scalar(
                    select(ProductVariant).where(
                        ProductVariant.workspace_id == workspace_id,
                        ProductVariant.variant_sku == str(sku).upper(),
                    )
                )
                if sku
                else await self.session.scalar(
                    select(ProductVariant).where(
                        ProductVariant.workspace_id == workspace_id,
                        ProductVariant.product_id == product.id,
                        ProductVariant.variant_sku.is_(None),
                    )
                )
            )
            created = variant is None
            if variant is None:
                variant = ProductVariant(
                    workspace_id=workspace_id,
                    product_id=product.id,
                    variant_sku=str(sku).upper() if sku else None,
                    attributes_json={"system_default": True} if creates_implicit_variant else {},
                )
                self.session.add(variant)
                await self.session.flush()
            elif variant.product_id != product.id:
                raise ApiError(
                    status.HTTP_409_CONFLICT,
                    "IDENTITY_CONFLICT",
                    "SKU biến thể thuộc sản phẩm khác.",
                )
            changed = False
            for attr, source in (
                ("barcode", "barcode"),
                ("price_override", "price"),
                ("compare_at_price", "compare_at_price"),
            ):
                if source in vf:
                    changed = _apply_cell(variant, attr, vf[source]) or changed
            await self._set_options(
                workspace_id,
                product,
                variant,
                cast(dict[str, Any], variant_data["options"]),
            )
            location_code = _cell_value(vf, "location_code")
            location = await resolve_location(
                self.session,
                workspace_id,
                str(location_code) if location_code is not None else None,
            )
            stock_cell = vf.get("stock_quantity", {"state": "missing", "value": None})
            price_cell = vf.get("location_price", {"state": "missing", "value": None})
            compare_cell = vf.get("location_compare_at_price", {"state": "missing", "value": None})
            quantity_supplied = stock_cell.get("state") in {"value", "explicit_null"}
            price_supplied = price_cell.get("state") in {"value", "explicit_null"}
            compare_supplied = compare_cell.get("state") in {"value", "explicit_null"}
            await upsert_variant_location(
                self.session,
                workspace_id=workspace_id,
                location=location,
                variant=variant,
                quantity=(int(stock_cell["value"]) if stock_cell.get("state") == "value" else None),
                quantity_supplied=quantity_supplied,
                price_override=(
                    Decimal(str(price_cell["value"]))
                    if price_cell.get("state") == "value"
                    else None
                ),
                price_supplied=price_supplied,
                compare_at_price_override=(
                    Decimal(str(compare_cell["value"]))
                    if compare_cell.get("state") == "value"
                    else None
                ),
                compare_price_supplied=compare_supplied,
            )
            outcome = "created" if created else "updated" if changed else "unchanged"
            previous = variant_outcomes.get(variant.id)
            priority = {"unchanged": 0, "updated": 1, "created": 2}
            if previous is None:
                result[f"variants_{outcome}"] += 1
                variant_outcomes[variant.id] = outcome
            elif priority[outcome] > priority[previous]:
                result[f"variants_{previous}"] -= 1
                result[f"variants_{outcome}"] += 1
                variant_outcomes[variant.id] = outcome
        images = cast(list[dict[str, Any]], data["images"])
        for index, image in enumerate(images):
            url = image.get("source_url")
            exists_image = await self.session.scalar(
                select(ProductImage.id).where(
                    ProductImage.workspace_id == workspace_id,
                    ProductImage.product_id == product.id,
                    ProductImage.source_url == url,
                )
            )
            if not exists_image:
                self.session.add(
                    ProductImage(
                        workspace_id=workspace_id,
                        product_id=product.id,
                        source_url=url,
                        object_key=None,
                        original_filename=None,
                        content_type=None,
                        byte_size=None,
                        width=None,
                        height=None,
                        sha256=None,
                        alt_text=image.get("alt_text"),
                        sort_order=index,
                        status="active",
                    )
                )
                result["images_created"] += 1

    async def _set_options(
        self, workspace_id: UUID, product: Product, variant: ProductVariant, options: dict[str, Any]
    ) -> None:
        values = {
            name: str(cell["value"])
            for name, cell in options.items()
            if cell.get("state") == "value"
        }
        await set_variant_options(
            self.session,
            workspace_id,
            product,
            variant,
            values,
            replace_all=True,
        )

    async def search(
        self,
        user: User,
        workspace_id: UUID,
        *,
        text: str | None,
        brand: str | None,
        price_min: Decimal | None,
        price_max: Decimal | None,
        in_stock: bool | None,
        options: list[str],
        attributes: list[str],
        limit: int,
        location_id: int | None = None,
        collection_id: int | None = None,
    ) -> CatalogSearchResponse:
        await self._authorize(user, workspace_id)
        products = await CatalogReadService(self.session).search_products(
            AuthorizedCatalogScope(workspace_id=workspace_id),
            CatalogQuery(
                text=text,
                brand=brand,
                price_min=price_min,
                price_max=price_max,
                in_stock=in_stock,
                options=tuple(options),
                attributes=tuple(attributes),
                requested_location_ids=(
                    frozenset({location_id}) if location_id is not None else None
                ),
                requested_collection_ids=(
                    frozenset({collection_id}) if collection_id is not None else None
                ),
                limit=limit,
            ),
        )
        items: list[CatalogSearchItem] = []
        for product in products:
            for variant in product.variants:
                for availability in variant.availability:
                    items.append(
                        CatalogSearchItem(
                            id=product.id,
                            name=product.name,
                            brand=product.brand,
                            category=product.category,
                            currency=product.currency,
                            price=product.base_price,
                            variant_id=variant.id,
                            variant_sku=variant.sku,
                            effective_price=availability.effective_price,
                            stock_quantity=availability.quantity,
                            location_id=availability.location_id,
                            location_name=availability.location_name,
                            options=dict(variant.options),
                            attributes=cast(Any, product.attributes),
                        )
                    )
        return CatalogSearchResponse(items=items[:limit])
