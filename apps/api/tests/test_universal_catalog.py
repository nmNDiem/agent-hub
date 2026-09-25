import csv
import io
from pathlib import Path

from openpyxl import Workbook as XlsxWorkbook  # type: ignore[import-untyped]

from agent_hub_api.catalog.file_extractor import extract_workbook
from agent_hub_api.catalog.import_pipeline import analyze_catalog
from agent_hub_api.catalog.import_types import CellState


def limits() -> dict[str, int]:
    return {"max_bytes": 10 * 1024 * 1024, "max_sheets": 20, "max_rows": 20_000, "max_columns": 200}


def analyze(content: bytes, filename: str):  # type: ignore[no-untyped-def]
    return analyze_catalog(
        content,
        filename,
        max_bytes=10 * 1024 * 1024,
        max_sheets=20,
        max_rows=20_000,
        max_columns=200,
    )


def test_csv_extraction_detects_encoding_delimiter_and_cell_states() -> None:
    content = "Name;Stock;Visible;Note\nCafé;0;false;NULL\n".encode("cp1252")
    workbook = extract_workbook(content, "catalog.csv", **limits())
    row = workbook.sheets["Catalog"][1]
    assert workbook.file_type == "csv"
    assert row[1].state is CellState.VALUE and row[1].value == "0"
    assert row[2].state is CellState.VALUE and row[2].value == "false"
    assert row[3].state is CellState.EXPLICIT_NULL


def test_xlsx_multi_sheet_uses_the_same_logical_pipeline() -> None:
    output = io.BytesIO()
    book = XlsxWorkbook()
    first = book.active
    first.title = "Products"
    first.append(["Handle", "Name", "SKU"])
    first.append(["shirt", "Shirt", "SHIRT-M"])
    second = book.create_sheet("Extra")
    second.append(["Handle", "Name", "SKU"])
    second.append(["hat", "Hat", "HAT-1"])
    book.save(output)
    analysis = analyze(output.getvalue(), "catalog.xlsx")
    assert analysis.file_type == "xlsx"
    assert len(analysis.products) == 2
    assert sum(len(product.variants) for product in analysis.products) == 2


def test_original_xls_regression_fixture_is_normalized_without_vendor_branch() -> None:
    fixture = Path(__file__).parents[3] / "assets" / "test-files" / "products_export_16.7.xls"
    analysis = analyze(fixture.read_bytes(), fixture.name)
    assert analysis.file_type == "xls"
    assert len(analysis.products) == 14
    assert sum(len(product.variants) for product in analysis.products) == 30
    assert sum(len(product.images) for product in analysis.products) == 29
    assert all(issue.severity == "warning" for issue in analysis.issues)
    assert "source" not in analysis.metadata


def test_schema_fingerprint_ignores_order_case_and_optional_columns() -> None:
    first = b"Handle,Name,SKU,Brand\nshirt,Shirt,S-1,AgentHub\n"
    second = b" sku , NAME , handle \nS-1,Shirt,shirt\n"
    assert (
        analyze(first, "first.csv").schema_fingerprint
        == analyze(second, "renamed.csv").schema_fingerprint
    )


def universal_csv() -> bytes:
    output = io.StringIO(newline="")
    columns = [
        "Handle",
        "Name",
        "SKU",
        "Option1 Name",
        "Option1 Value",
        "Option2 Name",
        "Option2 Value",
        "Price",
        "Quantity",
    ]
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    writer.writerow(
        {
            "Handle": "shirt",
            "Name": "Shirt",
            "SKU": "RED-M",
            "Option1 Name": "Color",
            "Option1 Value": "Red",
            "Option2 Name": "Size",
            "Option2 Value": "M",
            "Price": "100",
            "Quantity": "0",
        }
    )
    writer.writerow(
        {
            "Handle": "shirt",
            "SKU": "BLUE-L",
            "Option1 Name": "Color",
            "Option1 Value": "Blue",
            "Option2 Name": "Size",
            "Option2 Value": "L",
            "Price": "120",
            "Quantity": "3",
        }
    )
    return output.getvalue().encode()
