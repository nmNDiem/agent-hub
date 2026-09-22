from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass, field

from pydantic import ValidationError

from agent_hub_api.catalog.schemas import (
    ImportErrorResponse,
    ProductCreateRequest,
    VariantCreateRequest,
)

CSV_COLUMNS = (
    "product_sku",
    "name",
    "description",
    "category",
    "currency",
    "price",
    "product_url",
    "variant_sku",
    "variant_name",
    "color",
    "size",
    "variant_price",
    "stock_quantity",
)
PRODUCT_COLUMNS = (
    "product_sku",
    "name",
    "description",
    "category",
    "currency",
    "price",
    "product_url",
)
VARIANT_COLUMNS = (
    "variant_sku",
    "variant_name",
    "color",
    "size",
    "variant_price",
    "stock_quantity",
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


def _validation_errors(row: int, exc: ValidationError) -> list[ImportErrorResponse]:
    errors: list[ImportErrorResponse] = []
    for detail in exc.errors():
        location = detail.get("loc", ())
        errors.append(
            ImportErrorResponse(
                row=row,
                column=str(location[-1]) if location else None,
                code="INVALID_VALUE",
                message=str(detail["msg"]),
            )
        )
    return errors


def parse_catalog_csv(content: bytes, *, max_bytes: int, max_rows: int) -> ParsedCatalogCsv:
    payload_sha256 = hashlib.sha256(content).hexdigest()
    errors: list[ImportErrorResponse] = []
    if len(content) > max_bytes:
        return ParsedCatalogCsv(
            payload_sha256,
            [],
            [
                ImportErrorResponse(
                    row=None, column=None, code="FILE_TOO_LARGE", message="CSV file is too large"
                )
            ],
        )
    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return ParsedCatalogCsv(
            payload_sha256,
            [],
            [
                ImportErrorResponse(
                    row=None,
                    column=None,
                    code="INVALID_ENCODING",
                    message="CSV must use UTF-8 encoding",
                )
            ],
        )
    reader = csv.DictReader(io.StringIO(decoded, newline=""))
    if reader.fieldnames is None:
        return ParsedCatalogCsv(
            payload_sha256,
            [],
            [
                ImportErrorResponse(
                    row=None, column=None, code="MISSING_HEADER", message="CSV header is missing"
                )
            ],
        )
    fieldnames = tuple(name.strip() for name in reader.fieldnames)
    missing = [column for column in CSV_COLUMNS if column not in fieldnames]
    if missing:
        return ParsedCatalogCsv(
            payload_sha256,
            [],
            [
                ImportErrorResponse(
                    row=1,
                    column=column,
                    code="MISSING_COLUMN",
                    message=f"Required column '{column}' is missing",
                )
                for column in missing
            ],
        )

    grouped: dict[str, ParsedProduct] = {}
    raw_products: dict[str, tuple[str, ...]] = {}
    variant_skus: set[str] = set()
    for index, source_row in enumerate(reader, start=2):
        if index - 1 > max_rows:
            errors.append(
                ImportErrorResponse(
                    row=index,
                    column=None,
                    code="TOO_MANY_ROWS",
                    message=f"CSV cannot contain more than {max_rows} data rows",
                )
            )
            break
        row = {key.strip(): (value or "").strip() for key, value in source_row.items() if key}
        product_sku = row.get("product_sku", "").upper()
        if not product_sku:
            errors.append(
                ImportErrorResponse(
                    row=index,
                    column="product_sku",
                    code="REQUIRED",
                    message="product_sku is required for CSV import",
                )
            )
            continue
        product_values = tuple(
            product_sku if column == "product_sku" else row.get(column, "")
            for column in PRODUCT_COLUMNS
        )
        first_values = raw_products.get(product_sku)
        if first_values is not None and first_values != product_values:
            errors.append(
                ImportErrorResponse(
                    row=index,
                    column="product_sku",
                    code="INCONSISTENT_PRODUCT",
                    message="Rows grouped by product_sku must use identical product fields",
                )
            )
            continue
        try:
            product_request = ProductCreateRequest.model_validate(
                {
                    "product_sku": product_sku,
                    "name": row.get("name", ""),
                    "description": row.get("description") or None,
                    "category": row.get("category") or None,
                    "currency": row.get("currency") or "VND",
                    "price": row.get("price") or None,
                    "product_url": row.get("product_url") or None,
                }
            )
        except ValidationError as exc:
            errors.extend(_validation_errors(index, exc))
            continue
        parsed_product = grouped.get(product_sku)
        if parsed_product is None:
            parsed_product = ParsedProduct(row=index, product=product_request)
            grouped[product_sku] = parsed_product
            raw_products[product_sku] = product_values

        has_variant_data = any(row.get(column) for column in VARIANT_COLUMNS)
        if not has_variant_data:
            continue
        variant_sku = row.get("variant_sku", "").upper()
        if not variant_sku:
            errors.append(
                ImportErrorResponse(
                    row=index,
                    column="variant_sku",
                    code="REQUIRED",
                    message="variant_sku is required when variant fields are present",
                )
            )
            continue
        if variant_sku in variant_skus:
            errors.append(
                ImportErrorResponse(
                    row=index,
                    column="variant_sku",
                    code="DUPLICATE_VARIANT_SKU",
                    message="variant_sku must be unique in the CSV",
                )
            )
            continue
        try:
            variant_request = VariantCreateRequest.model_validate(
                {
                    "variant_sku": variant_sku,
                    "name": row.get("variant_name") or None,
                    "color": row.get("color") or None,
                    "size": row.get("size") or None,
                    "price_override": row.get("variant_price") or None,
                    "stock_quantity": row.get("stock_quantity") or None,
                }
            )
        except ValidationError as exc:
            errors.extend(_validation_errors(index, exc))
            continue
        variant_skus.add(variant_sku)
        parsed_product.variants.append((index, variant_request))

    if not grouped and not errors:
        errors.append(
            ImportErrorResponse(
                row=None, column=None, code="EMPTY_FILE", message="CSV has no data rows"
            )
        )
    return ParsedCatalogCsv(payload_sha256, list(grouped.values()), errors)
