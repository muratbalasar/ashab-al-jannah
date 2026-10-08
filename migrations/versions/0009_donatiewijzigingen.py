"""wijzigingen van donaties vastleggen (oude en nieuwe waarde)

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-08 21:16:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import ledenadmin.db

revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "donation_changes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("donation_id", sa.Integer(), nullable=False),
        sa.Column("changed_at", ledenadmin.db.UTCDateTime(), nullable=False),
        sa.Column("changed_by", sa.Unicode(length=200), nullable=False),
        sa.Column("field", sa.Unicode(length=40), nullable=False),
        sa.Column("old_value", sa.Unicode(length=600), nullable=False),
        sa.Column("new_value", sa.Unicode(length=600), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["donation_id"],
            ["donations.id"],
            name=op.f("fk_donation_changes_donation_id_donations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_donation_changes_organization_id_organizations"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_donation_changes")),
    )
    op.create_index(op.f("ix_donation_changes_donation_id"), "donation_changes", ["donation_id"])
    op.create_index(
        op.f("ix_donation_changes_organization_id"), "donation_changes", ["organization_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_donation_changes_organization_id"), table_name="donation_changes")
    op.drop_index(op.f("ix_donation_changes_donation_id"), table_name="donation_changes")
    op.drop_table("donation_changes")
