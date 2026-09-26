from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlparse

import nh3

from agent_hub_api.catalog.file_extractor import extract_workbook
from agent_hub_api.catalog.import_types import (
    AnalysisResult,
    CanonicalProduct,
    CanonicalVariant,
    Cell,
    CellState,
    ImportIssueData,
)


def normalize_label(value: str) -> str:
    value = value.replace("Đ", "D").replace("đ", "d")
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().casefold()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


ALIASES: dict[str, set[str]] = {
    "product_slug": {"handle", "slug", "duong dan alias", "duong dan", "product handle"},
    "product_name": {"name", "product name", "title", "ten san pham", "ten"},
    "product_sku": {"product sku", "ma san pham"},
    "description": {"description", "body html", "noi dung", "mo ta"},
    "brand": {"brand", "vendor", "nha cung cap", "thuong hieu"},
    "category": {"category", "type", "product type", "loai", "danh muc"},
    "tags": {"tags", "tag"},
    "variant_sku": {"sku", "variant sku", "ma sku", "ma"},
    "variant_name": {"variant name"},
    "legacy_color": {"color", "colour"},
    "legacy_size": {"size"},
    "product_url": {"product url", "url"},
    "barcode": {"barcode", "ma vach barcode", "ma vach"},
    "price": {"price", "gia"},
    "variant_price": {"variant price"},
    "compare_at_price": {"compare at price", "gia so sanh"},
    "stock_quantity": {"inventory qty", "quantity", "stock", "so luong", "ton kho"},
    "location_code": {"location code", "branch code", "warehouse code", "ma chi nhanh", "ma kho"},
    "location_price": {"location price", "branch price", "store price", "gia chi nhanh"},
    "location_compare_at_price": {"location compare at price", "gia so sanh chi nhanh"},
    "inventory_policy": {"inventory policy", "quan ly kho"},
    "image_url": {"image src", "image", "anh dai dien", "url anh"},
    "image_alt": {"image alt text", "alt text", "chu thich anh"},
    "variant_image_url": {"variant image", "anh phien ban"},
    "external_product_id": {"product id", "id san pham"},
    "external_variant_id": {"variant id", "id tuy chon"},
}


def canonical_header(header: str) -> tuple[str | None, float]:
    normalized = normalize_label(header)
    compact_option = re.search(r"option\s*([123])\s*(name|value)", normalized)
    if compact_option:
        index, kind = compact_option.groups()
        return f"option_{index}_{kind}", 1.0
    localized_option = re.search(r"(?:gia tri\s+)?thuoc tinh\s*([123])", normalized)
    if localized_option:
        option_kind = "value" if normalized.startswith("gia tri") else "name"
        return (
            f"option_{localized_option.group(1)}_{option_kind}",
            1.0,
        )
    option_match = re.search(
        r"(?:option|thuoc tinh)\s*([123])(?:\s*(name|value|gia tri))?", normalized
    )
    if option_match:
        index, kind = option_match.groups()
        return f"option_{index}_{'value' if kind in {'value', 'gia tri'} else 'name'}", 1.0
    matches = [name for name, aliases in ALIASES.items() if normalized in aliases]
    if len(matches) == 1:
        return matches[0], 1.0
    # Conservative token overlap helps unusual human-authored headers, never identity.
    scored = sorted(
        (
            (
                len(set(normalized.split()) & set(alias.split())) / max(len(set(alias.split())), 1),
                name,
            )
            for name, aliases in ALIASES.items()
            for alias in aliases
        ),
        reverse=True,
    )
    return (scored[0][1], scored[0][0]) if scored and scored[0][0] >= 0.8 else (None, 0.0)


def _value(cell: Cell) -> Any:
    return cell.value if cell.state is CellState.VALUE else None


def _field(row: dict[str, Cell], name: str) -> Cell:
    return row.get(name, Cell(CellState.MISSING))


def _money(cell: Cell) -> Cell:
    if cell.state is not CellState.VALUE:
        return cell
    raw = str(cell.value).strip().replace(" ", "")
    # Common exports use dots as thousands separators. Decimal fractions retain <=2 digits.
    if re.fullmatch(r"-?\d{1,3}(?:\.\d{3})+", raw):
        raw = raw.replace(".", "")
    raw = raw.replace(",", ".")
    try:
        return Cell(CellState.VALUE, Decimal(raw).quantize(Decimal("0.01")))
    except InvalidOperation:
        return Cell(CellState.VALUE, cell.value)


def _integer(cell: Cell) -> Cell:
    if cell.state is not CellState.VALUE:
        return cell
    try:
        return Cell(CellState.VALUE, int(Decimal(str(cell.value))))
    except (InvalidOperation, ValueError):
        return cell


def _valid_url(value: Any) -> bool:
    parsed = urlparse(str(value))
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _serialize_fields(fields: dict[str, Cell]) -> dict[str, dict[str, Any]]:
    return {name: cell.json() for name, cell in fields.items()}


def serialize_product(product: CanonicalProduct) -> dict[str, Any]:
    return {
        "source": product.source,
        "fields": _serialize_fields(product.fields),
        "attributes": _serialize_fields(product.attributes),
        "variants": [
            {
                "source": variant.source,
                "fields": _serialize_fields(variant.fields),
                "options": _serialize_fields(variant.options),
                "attributes": _serialize_fields(variant.attributes),
            }
            for variant in product.variants
        ],
        "images": product.images,
    }


def analyze_catalog(
    content: bytes,
    filename: str,
    *,
    max_bytes: int,
    max_sheets: int,
    max_rows: int,
    max_columns: int,
    mapping_override: dict[str, str] | None = None,
) -> AnalysisResult:
    workbook = extract_workbook(
        content,
        filename,
        max_bytes=max_bytes,
        max_sheets=max_sheets,
        max_rows=max_rows,
        max_columns=max_columns,
    )
    issues: list[ImportIssueData] = []
    products: list[CanonicalProduct] = []
    all_mapping: dict[str, str] = {}
    header_shapes: list[list[str]] = []
    for sheet_name, table in workbook.sheets.items():
        if not table:
            continue
        header_row = next(
            (
                index
                for index, row in enumerate(table[:25])
                if sum(cell.state is CellState.VALUE for cell in row) >= 2
            ),
            None,
        )
        if header_row is None:
            issues.append(
                ImportIssueData(
                    "SCHEMA_ERROR", "error", "Không tìm thấy hàng tiêu đề.", {"sheet": sheet_name}
                )
            )
            continue
        headers = [str(_value(cell) or "") for cell in table[header_row]]
        mapping: dict[int, str] = {}
        seen: set[str] = set()
        for index, header in enumerate(headers):
            override = (mapping_override or {}).get(header)
            canonical, confidence = (override, 1.0) if override else canonical_header(header)
            if canonical and canonical not in seen:
                mapping[index] = canonical
                all_mapping[header] = canonical
                seen.add(canonical)
            elif canonical in seen:
                # A second descriptive/SEO column is optional evidence, not an ambiguity.
                continue
            elif header and confidence >= 0.5:
                issues.append(
                    ImportIssueData(
                        "AMBIGUOUS_COLUMN",
                        "needs_confirmation",
                        f'Cột "{header}" chưa thể được ánh xạ an toàn.',
                        {"sheet": sheet_name, "row": header_row + 1, "column": index + 1},
                        {"header": header, "suggestion": canonical, "confidence": confidence},
                        [{"action": "map", "field": canonical}, {"action": "ignore"}],
                    )
                )
        header_shapes.append(sorted(mapping.values()))
        if "product_name" not in seen and "product_slug" not in seen:
            issues.append(
                ImportIssueData(
                    "MISSING_PRODUCT_IDENTITY",
                    "error",
                    "Cần cột tên hoặc đường dẫn sản phẩm.",
                    {"sheet": sheet_name},
                )
            )
            continue
        current: CanonicalProduct | None = None
        grouped: dict[str, CanonicalProduct] = {}
        for row_index, raw in enumerate(table[header_row + 1 :], start=header_row + 2):
            row = {
                canonical: raw[index] if index < len(raw) else Cell(CellState.MISSING)
                for index, canonical in mapping.items()
            }
            if not any(cell.state is CellState.VALUE for cell in row.values()):
                continue
            name = _value(_field(row, "product_name"))
            slug = _value(_field(row, "product_slug"))
            image = _value(_field(row, "image_url"))
            variant_sku = _value(_field(row, "variant_sku"))
            product_sku = _value(_field(row, "product_sku"))
            location_code = _value(_field(row, "location_code"))
            group_key = str(slug or product_sku or "").strip().casefold()
            if name:
                fields = {
                    "name": Cell(CellState.VALUE, str(name).strip()),
                    "slug": _field(row, "product_slug"),
                    "product_sku": _field(row, "product_sku"),
                    "brand": _field(row, "brand"),
                    "category": _field(row, "category"),
                    "description": _field(row, "description"),
                    "product_url": _field(row, "product_url"),
                    "currency": Cell(CellState.VALUE, "VND"),
                    "base_price": (
                        _money(_field(row, "price"))
                        if location_code is None
                        else Cell(CellState.MISSING)
                    ),
                    "compare_at_price": _money(_field(row, "compare_at_price")),
                }
                description = _value(fields["description"])
                if isinstance(description, str) and "<" in description:
                    fields["description_html_source"] = Cell(CellState.VALUE, description)
                    fields["description_html_sanitized"] = Cell(
                        CellState.VALUE, nh3.clean(description)
                    )
                    fields["description_text"] = Cell(
                        CellState.VALUE,
                        re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", description)).strip(),
                    )
                current = CanonicalProduct({"sheet": sheet_name, "row": row_index}, fields)
                if group_key and group_key in grouped:
                    current = grouped[group_key]
                else:
                    products.append(current)
                    if group_key:
                        grouped[group_key] = current
            elif group_key:
                current = grouped.get(group_key)
            if current is None:
                issues.append(
                    ImportIssueData(
                        "AMBIGUOUS_GROUPING",
                        "needs_confirmation",
                        "Không xác định được sản phẩm cha của hàng này.",
                        {"sheet": sheet_name, "row": row_index},
                        {
                            "populated_fields": sorted(
                                k for k, v in row.items() if v.state is CellState.VALUE
                            )
                        },
                    )
                )
                continue
            if image:
                if _valid_url(image):
                    if not any(item["source_url"] == str(image) for item in current.images):
                        current.images.append(
                            {
                                "source_url": str(image),
                                "alt_text": _value(_field(row, "image_alt")),
                                "source": {"sheet": sheet_name, "row": row_index},
                            }
                        )
                else:
                    issues.append(
                        ImportIssueData(
                            "INVALID_IMAGE_URL",
                            "warning",
                            "URL ảnh không hợp lệ và sẽ bị bỏ qua.",
                            {"sheet": sheet_name, "row": row_index},
                        )
                    )
            has_location_data = any(
                _field(row, field).state in {CellState.VALUE, CellState.EXPLICIT_NULL}
                for field in ("location_code", "stock_quantity", "location_price")
            )
            if (
                variant_sku
                or has_location_data
                or any(_value(_field(row, f"option_{i}_value")) for i in range(1, 4))
            ):
                options: dict[str, Cell] = {}
                if _field(row, "legacy_color").state is CellState.VALUE:
                    options["Color"] = _field(row, "legacy_color")
                if _field(row, "legacy_size").state is CellState.VALUE:
                    options["Size"] = _field(row, "legacy_size")
                for index in range(1, 4):
                    option_name = _value(_field(row, f"option_{index}_name"))
                    option_value = _field(row, f"option_{index}_value")
                    if (
                        option_name
                        and option_value.state is CellState.VALUE
                        and str(option_name).casefold() != "title"
                    ):
                        options[str(option_name).strip()] = option_value
                variant = CanonicalVariant(
                    {"sheet": sheet_name, "row": row_index},
                    {
                        "variant_sku": _field(row, "variant_sku"),
                        "name": _field(row, "variant_name"),
                        "barcode": _field(row, "barcode"),
                        "price": _money(
                            _field(row, "variant_price")
                            if _field(row, "variant_price").state is not CellState.MISSING
                            else _field(row, "price")
                            if location_code is None
                            else Cell(CellState.MISSING)
                        ),
                        "compare_at_price": _money(_field(row, "compare_at_price")),
                        "stock_quantity": _integer(_field(row, "stock_quantity")),
                        "inventory_policy": _field(row, "inventory_policy"),
                        "location_code": _field(row, "location_code"),
                        "location_price": _money(
                            _field(row, "location_price")
                            if _field(row, "location_price").state is not CellState.MISSING
                            else _field(row, "price")
                            if location_code is not None
                            else Cell(CellState.MISSING)
                        ),
                        "location_compare_at_price": _money(
                            _field(row, "location_compare_at_price")
                        ),
                    },
                    options,
                    {},
                )
                stock_cell = variant.fields["stock_quantity"]
                if (
                    stock_cell.state is CellState.VALUE
                    and isinstance(stock_cell.value, int)
                    and stock_cell.value < 0
                ):
                    variant.fields["stock_quantity"] = Cell(CellState.BLANK)
                    issues.append(
                        ImportIssueData(
                            "NEGATIVE_STOCK_NORMALIZED",
                            "warning",
                            "Tồn kho âm được giữ là chưa xác định thay vì ghi số âm.",
                            {"sheet": sheet_name, "row": row_index},
                            {"source_value": stock_cell.value},
                        )
                    )
                current.variants.append(variant)
                variant_image = _value(_field(row, "variant_image_url"))
                if (
                    variant_image
                    and _valid_url(variant_image)
                    and not any(item["source_url"] == str(variant_image) for item in current.images)
                ):
                    current.images.append(
                        {
                            "source_url": str(variant_image),
                            "variant_sku": str(variant_sku or ""),
                            "source": {"sheet": sheet_name, "row": row_index},
                        }
                    )
    canonical_shape = sorted(
        {
            value
            for shape in header_shapes
            for value in shape
            if value in {"product_slug", "product_name", "product_sku", "variant_sku"}
            or value.startswith("option_")
        }
    )
    fingerprint = hashlib.sha256(
        json.dumps(canonical_shape, separators=(",", ":")).encode()
    ).hexdigest()
    duplicate_skus = [
        sku
        for (sku, _location), count in Counter(
            (
                str(_value(v.fields["variant_sku"])).strip().upper(),
                str(_value(v.fields.get("location_code", Cell(CellState.MISSING))) or "DEFAULT")
                .strip()
                .upper(),
            )
            for p in products
            for v in p.variants
            if _value(v.fields["variant_sku"])
        ).items()
        if count > 1
    ]
    for sku in duplicate_skus:
        issues.append(
            ImportIssueData(
                "DUPLICATE_VARIANT_SKU",
                "error",
                f"SKU biến thể {sku} xuất hiện nhiều lần.",
                evidence={"sku": sku},
            )
        )
    return AnalysisResult(
        workbook.file_type,
        fingerprint,
        all_mapping,
        products,
        issues,
        {
            "sheets": len(workbook.sheets),
            "rows": sum(max(len(rows) - 1, 0) for rows in workbook.sheets.values()),
        },
    )
