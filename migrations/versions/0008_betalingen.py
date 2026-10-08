"""online betalingen via Mollie (multi-tenant fase 7)

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-03 22:10:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import ledenadmin.db

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("mollie_api_key_encrypted", sa.Unicode(length=500)))
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("mollie_id", sa.Unicode(length=40), nullable=True),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("subcategory_id", sa.Integer(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("status", sa.Unicode(length=20), nullable=False),
        sa.Column("donation_id", sa.Integer(), nullable=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("created_at", ledenadmin.db.UTCDateTime(), nullable=False),
        sa.Column("updated_at", ledenadmin.db.UTCDateTime(), nullable=False),
        sa.Column("created_by", sa.Unicode(length=200), nullable=False),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["members.id"],
            name=op.f("fk_payments_member_id_members"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["subcategory_id"],
            ["subcategories.id"],
            name=op.f("fk_payments_subcategory_id_subcategories"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["donation_id"],
            ["donations.id"],
            name=op.f("fk_payments_donation_id_donations"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_payments_organization_id_organizations"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payments")),
        sa.UniqueConstraint("mollie_id", name=op.f("uq_payments_mollie_id")),
    )
    op.create_index(op.f("ix_payments_member_id"), "payments", ["member_id"])
    op.create_index(op.f("ix_payments_organization_id"), "payments", ["organization_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_payments_organization_id"), table_name="payments")
    op.drop_index(op.f("ix_payments_member_id"), table_name="payments")
    op.drop_table("payments")
    with op.batch_alter_table("organizations") as batch_op:
        batch_op.drop_column("mollie_api_key_encrypted")
