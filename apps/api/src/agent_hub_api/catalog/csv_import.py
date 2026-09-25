from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from agent_hub_api.catalog.file_extractor import ExtractionError
from agent_hub_api.catalog.import_pipeline import analyze_catalog
from agent_hub_api.catalog.import_types import Cell, CellState
from agent_hub_api.catalog.schemas import (
    ImportErrorResponse,
    ProductCreateRequest,
    VariantCreateRequest,
)


@dataclass
class ParsedProduct:
    row: int
    product: ProductCreateRequest
    variants: list[tuple[int, VariantCreateRequest]] = field(default_factory=list)


@dataclass
class ParsedCatalogCsv:
    payload_sha256: str
    products: list[ParsedProduct]
    errors: list[ImportErrorResponse]

    @property
    def variant_count(self) -> int:
        return sum(len(product.variants) for product in self.products)


def _value(fields: dict[str, Cell], name: str) -> Any:
    cell = fields.get(name, Cell(CellState.MISSING))
    return cell.value if cell.state is CellState.VALUE else None


def _validation_errors(row: int, exc: ValidationError) -> list[ImportErrorResponse]:
    return [
        ImportErrorResponse(
            row=row,
            column=str(detail.get("loc", (None,))[-1]),
            code="INVALID_VALUE",
            message=str(detail["msg"]),
        )
        for detail in exc.errors()
    ]


def parse_catalog_csv(content: bytes, *, max_bytes: int, max_rows: int) -> ParsedCatalogCsv:
    """Compatibility adapter over the universal structure-driven pipeline."""

    digest = hashlib.sha256(content).hexdigest()
    try:
        analysis = analyze_catalog(
            content,
            "catalog.csv",
            max_bytes=max_bytes,
            max_sheets=1,
            max_rows=max_rows,
            max_columns=200,
        )
    except ExtractionError as exc:
        return ParsedCatalogCsv(
            digest,
            [],
            [ImportErrorResponse(row=None, column=None, code="FILE_ERROR", message=str(exc))],
        )

    errors = [
        ImportErrorResponse(
            row=int(issue.source_location.get("row", 0)) or None,
            column=None,
            code=issue.issue_type,
            message=issue.message,
        )
        for issue in analysis.issues
        if issue.severity in {"error", "needs_confirmation"}
    ]
    parsed: list[ParsedProduct] = []
    seen_variants: set[str] = set()
    for product in analysis.products:
        row = int(product.source["row"])
        product_sku = _value(product.fields, "product_sku")
        if not product_sku:
            errors.append(
                ImportErrorResponse(
                    row=row,
                    column="product_sku",
                    code="REQUIRED",
                    message="product_sku is required for the legacy CSV API",
                )
            )
            continue
        try:
            request = ProductCreateRequest.model_validate(
                {
                    "product_sku": product_sku,
                    "name": _value(product.fields, "name"),
                    "description": _value(product.fields, "description"),
                    "category": _value(product.fields, "category"),
                    "currency": _value(product.fields, "currency") or "VND",
                    "price": _value(product.fields, "base_price"),
                    "product_url": _value(product.fields, "product_url"),
                }
            )
        except ValidationError as exc:
            errors.extend(_validation_errors(row, exc))
            continue
        item = ParsedProduct(row=row, product=request)
        for variant in product.variants:
            variant_row = int(variant.source["row"])
            variant_sku = _value(variant.fields, "variant_sku")
            if not variant_sku:
                errors.append(
                    ImportErrorResponse(
                        row=variant_row,
                        column="variant_sku",
                        code="REQUIRED",
                        message="variant_sku is required when variant fields are present",
                    )
                )
                continue
            normalized_sku = str(variant_sku).strip().upper()
            if normalized_sku in seen_variants:
                errors.append(
                    ImportErrorResponse(
                        row=variant_row,
                        column="variant_sku",
                        code="DUPLICATE_VARIANT_SKU",
                        message="variant_sku must be unique in the CSV",
                    )
                )
                continue
            seen_variants.add(normalized_sku)
            try:
                item.variants.append(
                    (
                        variant_row,
                        VariantCreateRequest.model_validate(
                            {
                                "variant_sku": normalized_sku,
                                "name": _value(variant.fields, "name"),
                                "color": _value(variant.options, "Color"),
                                "size": _value(variant.options, "Size"),
                                "price_override": _value(variant.fields, "price"),
                                "stock_quantity": _value(variant.fields, "stock_quantity"),
                            }
                        ),
                    )
                )
            except ValidationError as exc:
                errors.extend(_validation_errors(variant_row, exc))
        parsed.append(item)
    if not parsed and not errors:
        errors.append(
            ImportErrorResponse(row=None, column=None, code="EMPTY_FILE", message="CSV has no data")
        )
    return ParsedCatalogCsv(digest, parsed, errors)
