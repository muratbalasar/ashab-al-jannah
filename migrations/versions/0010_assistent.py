"""tellers voor de helpassistent (vragen per gebruiker per dag)

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-09 21:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assistant_usage",
        sa.Column("day", sa.Unicode(length=10), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("questions", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_assistant_usage_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("day", "user_id", name=op.f("pk_assistant_usage")),
    )


def downgrade() -> None:
    op.drop_table("assistant_usage")
