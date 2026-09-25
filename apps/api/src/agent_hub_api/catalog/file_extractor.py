from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

import xlrd  # type: ignore[import-untyped]
from charset_normalizer import from_bytes
from openpyxl import load_workbook  # type: ignore[import-untyped]

from agent_hub_api.catalog.import_types import Cell, CellState, Workbook


class ExtractionError(ValueError):
    pass


NULL_MARKERS = {"null", "#null", "<null>"}


def _cell(value: Any) -> Cell:
    if value is None:
        return Cell(CellState.BLANK)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return Cell(CellState.BLANK)
        if stripped.casefold() in NULL_MARKERS:
            return Cell(CellState.EXPLICIT_NULL)
        return Cell(CellState.VALUE, stripped)
    return Cell(CellState.VALUE, value)


def _validate(
    sheets: dict[str, list[list[Cell]]], max_sheets: int, max_rows: int, max_columns: int
) -> None:
    if len(sheets) > max_sheets:
        raise ExtractionError(f"Workbook exceeds the {max_sheets} sheet limit")
    total_rows = sum(max(len(rows) - 1, 0) for rows in sheets.values())
    if total_rows > max_rows:
        raise ExtractionError(f"Workbook exceeds the {max_rows} row limit")
    if any(any(len(row) > max_columns for row in rows) for rows in sheets.values()):
        raise ExtractionError(f"Workbook exceeds the {max_columns} column limit")


def _detect_type(content: bytes, filename: str) -> str:
    suffix = Path(filename).suffix.casefold()
    if content.startswith(bytes.fromhex("D0CF11E0A1B11AE1")):
        return "xls"
    if content.startswith(b"PK\x03\x04"):
        return "xlsx"
    if suffix == ".csv" or b"\x00" not in content[:1024]:
        return "csv"
    raise ExtractionError("Unsupported or malformed catalog file")


def extract_workbook(
    content: bytes,
    filename: str,
    *,
    max_bytes: int,
    max_sheets: int,
    max_rows: int,
    max_columns: int,
) -> Workbook:
    if not content:
        raise ExtractionError("Catalog file is empty")
    if len(content) > max_bytes:
        raise ExtractionError(f"Catalog file exceeds the {max_bytes} byte limit")
    file_type = _detect_type(content, filename)
    sheets: dict[str, list[list[Cell]]] = {}
    try:
        if file_type == "csv":
            match = from_bytes(content).best()
            if match is None:
                raise ExtractionError("Unable to detect CSV encoding")
            decoded = str(match)
            dialect = csv.Sniffer().sniff(decoded[:8192], delimiters=",;\t|")
            sheets["Catalog"] = [
                [_cell(value) for value in row] for row in csv.reader(io.StringIO(decoded), dialect)
            ]
        elif file_type == "xlsx":
            book = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            try:
                for sheet in book.worksheets:
                    sheets[sheet.title] = [
                        [_cell(value) for value in row] for row in sheet.iter_rows(values_only=True)
                    ]
            finally:
                book.close()
        else:
            book = xlrd.open_workbook(file_contents=content, on_demand=True)
            try:
                for name in book.sheet_names():
                    sheet = book.sheet_by_name(name)
                    sheets[name] = [
                        [_cell(sheet.cell_value(r, c)) for c in range(sheet.ncols)]
                        for r in range(sheet.nrows)
                    ]
            finally:
                book.release_resources()
    except ExtractionError:
        raise
    except (csv.Error, UnicodeError, ValueError, OSError, xlrd.XLRDError) as exc:
        raise ExtractionError("Catalog file could not be parsed safely") from exc
    sheets = {name: rows for name, rows in sheets.items() if any(row for row in rows)}
    if not sheets:
        raise ExtractionError("Catalog file contains no readable sheets")
    _validate(sheets, max_sheets, max_rows, max_columns)
    return Workbook(file_type=file_type, sheets=sheets)
