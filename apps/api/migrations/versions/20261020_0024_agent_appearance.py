"""Add user-configurable Agent appearance.

Revision ID: 20261020_0024
Revises: 20261019_0023
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261020_0024"
down_revision: str | None = "20261019_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column("icon", sa.String(length=32), nullable=False, server_default="message-circle"),
    )
    op.add_column(
        "agents",
        sa.Column("color", sa.String(length=7), nullable=False, server_default="#0E8A8C"),
    )
    op.create_check_constraint(
        "ck_agents_icon",
        "agents",
        "icon IN ('message-circle','bot','headphones','sparkles','shopping-bag',"
        "'calendar-days','briefcase-business','heart-handshake')",
    )
    op.create_check_constraint(
        "ck_agents_color_hex",
        "agents",
        "color ~ '^#[0-9A-F]{6}$'",
    )


def downgrade() -> None:
    op.drop_constraint("ck_agents_color_hex", "agents", type_="check")
    op.drop_constraint("ck_agents_icon", "agents", type_="check")
    op.drop_column("agents", "color")
    op.drop_column("agents", "icon")
