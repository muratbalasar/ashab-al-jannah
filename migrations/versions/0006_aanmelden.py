"""aanmelden van organisaties en uitnodigingen (multi-tenant fase 3)

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-03 21:30:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import ledenadmin.db

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Gewone ADD COLUMN: een batch-hercreatie van 'organizations' faalt in SQLite zodra
    # andere tabellen er met een foreign key naar verwijzen.
    op.add_column("organizations", sa.Column("contact_email", sa.Unicode(length=320)))
    op.add_column("organizations", sa.Column("city", sa.Unicode(length=100)))
    op.add_column("organizations", sa.Column("kvk_verified_at", ledenadmin.db.UTCDateTime()))
    # Zonder foreign key: SQLite kan die niet toevoegen zonder de tabel te hercreëren.
    op.add_column("organizations", sa.Column("created_by_user_id", sa.Integer()))
    op.create_index(
        op.f("ix_organizations_created_by_user_id"), "organizations", ["created_by_user_id"]
    )

    op.create_table(
        "invitations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.Unicode(length=320), nullable=False),
        sa.Column("role", sa.Unicode(length=20), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=True),
        sa.Column("token_hash", sa.Unicode(length=64), nullable=False),
        sa.Column("expires_at", ledenadmin.db.UTCDateTime(), nullable=False),
        sa.Column("accepted_at", ledenadmin.db.UTCDateTime(), nullable=True),
        sa.Column("accepted_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Unicode(length=200), nullable=False),
        sa.Column("created_at", ledenadmin.db.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_invitations_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["members.id"],
            name=op.f("fk_invitations_member_id_members"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["accepted_by_user_id"],
            ["users.id"],
            name=op.f("fk_invitations_accepted_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invitations")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_invitations_token_hash")),
    )
    op.create_index(op.f("ix_invitations_organization_id"), "invitations", ["organization_id"])
    op.create_table(
        "mail_counters",
        sa.Column("day", sa.Unicode(length=10), nullable=False),
        sa.Column("sent", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("day", name=op.f("pk_mail_counters")),
    )


def downgrade() -> None:
    op.drop_table("mail_counters")
    op.drop_table("invitations")
    op.drop_index(op.f("ix_organizations_created_by_user_id"), table_name="organizations")
    with op.batch_alter_table("organizations") as batch_op:
        for column in ("created_by_user_id", "kvk_verified_at", "city", "contact_email"):
            batch_op.drop_column(column)
