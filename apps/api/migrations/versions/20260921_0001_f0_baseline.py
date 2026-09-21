"""Establish the empty F0 migration baseline.

Revision ID: 20260921_0001
Revises:
Create Date: 2026-09-21 00:00:00
"""

from collections.abc import Sequence

revision: str = "20260921_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """F0 intentionally creates no domain tables."""


def downgrade() -> None:
    """F0 intentionally creates no domain tables."""
