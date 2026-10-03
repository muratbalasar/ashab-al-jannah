"""gebruikers en lidmaatschappen (multi-tenant fase 2)

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-04 10:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import ledenadmin.db

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("issuer", sa.Unicode(length=300), nullable=False),
        sa.Column("subject", sa.Unicode(length=200), nullable=False),
        sa.Column("email", sa.Unicode(length=320), nullable=True),
        sa.Column("display_name", sa.Unicode(length=200), nullable=False),
        sa.Column("created_at", ledenadmin.db.UTCDateTime(), nullable=False),
        sa.Column("last_login_at", ledenadmin.db.UTCDateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("issuer", "subject", name=op.f("uq_users_issuer")),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"])
    op.create_table(
        "memberships",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.Unicode(length=20), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=True),
        sa.Column("created_at", ledenadmin.db.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_memberships_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_memberships_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["members.id"],
            name=op.f("fk_memberships_member_id_members"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memberships")),
        sa.UniqueConstraint(
            "user_id", "organization_id", "role", name=op.f("uq_memberships_user_id")
        ),
    )
    op.create_index(op.f("ix_memberships_user_id"), "memberships", ["user_id"])
    op.create_index(op.f("ix_memberships_organization_id"), "memberships", ["organization_id"])


def downgrade() -> None:
    op.drop_table("memberships")
    op.drop_table("users")
