from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any


class CellState(StrEnum):
    MISSING = "missing"
    VALUE = "value"
    BLANK = "blank"
    EXPLICIT_NULL = "explicit_null"


@dataclass(frozen=True)
class Cell:
    state: CellState
    value: Any = None

    def json(self) -> dict[str, Any]:
        value = self.value
        if isinstance(value, Decimal):
            value = str(value)
        return {"state": self.state.value, "value": value}


@dataclass(frozen=True)
class SourceRow:
    sheet: str
    row: int
    cells: dict[str, Cell]


@dataclass
class Workbook:
    file_type: str
    sheets: dict[str, list[list[Cell]]]


@dataclass
class ImportIssueData:
    issue_type: str
    severity: str
    message: str
    source_location: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)
    options: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class CanonicalVariant:
    source: dict[str, Any]
    fields: dict[str, Cell]
    options: dict[str, Cell]
    attributes: dict[str, Cell]


@dataclass
class CanonicalProduct:
    source: dict[str, Any]
    fields: dict[str, Cell]
    options: list[str] = field(default_factory=list)
    attributes: dict[str, Cell] = field(default_factory=dict)
    variants: list[CanonicalVariant] = field(default_factory=list)
    images: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class AnalysisResult:
    file_type: str
    schema_fingerprint: str
    mapping: dict[str, str]
    products: list[CanonicalProduct]
    issues: list[ImportIssueData]
    metadata: dict[str, Any]
