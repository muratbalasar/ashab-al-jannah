"""organisaties (multi-tenant fase 1)

Maakt de tabel `organizations` aan en hangt alle bestaande gegevens onder één
standaardorganisatie. Unieke sleutels gelden voortaan per organisatie.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-03 15:30:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import ledenadmin.db

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "members",
    "categories",
    "subcategories",
    "donations",
    "member_fields",
    "member_field_values",
)
# Tabel -> kolom die voortaan per organisatie uniek is (de oude globale sleutel vervalt).
UNIQUE_PER_ORG = {"members": "email", "categories": "name", "member_fields": "label"}


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.Unicode(length=80), nullable=False),
        sa.Column("name", sa.Unicode(length=200), nullable=False),
        sa.Column("kvk_number", sa.Unicode(length=8), nullable=True),
        sa.Column("status", sa.Unicode(length=20), nullable=False),
        sa.Column("created_at", ledenadmin.db.UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organizations")),
        sa.UniqueConstraint("kvk_number", name=op.f("uq_organizations_kvk_number")),
        sa.UniqueConstraint("slug", name=op.f("uq_organizations_slug")),
    )
    op.execute(
        "INSERT INTO organizations (id, slug, name, status, created_at) "
        "VALUES (1, 'standaard', 'Standaard', 'actief', CURRENT_TIMESTAMP)"
    )

    for table in (*TENANT_TABLES, "audit_log"):
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column("organization_id", sa.Integer(), nullable=True))
        op.execute(f"UPDATE {table} SET organization_id = 1")  # noqa: S608 - vaste tabelnamen

    for table in TENANT_TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column("organization_id", existing_type=sa.Integer(), nullable=False)
            batch_op.create_index(op.f(f"ix_{table}_organization_id"), ["organization_id"])
            batch_op.create_foreign_key(
                op.f(f"fk_{table}_organization_id_organizations"),
                "organizations",
                ["organization_id"],
                ["id"],
                ondelete="RESTRICT",
            )
            if table in UNIQUE_PER_ORG:
                column = UNIQUE_PER_ORG[table]
                batch_op.drop_constraint(op.f(f"uq_{table}_{column}"), type_="unique")
                batch_op.create_unique_constraint(
                    op.f(f"uq_{table}_organization_id"), ["organization_id", column]
                )

    with op.batch_alter_table("audit_log") as batch_op:
        batch_op.create_index(op.f("ix_audit_log_organization_id"), ["organization_id"])
        batch_op.create_foreign_key(
            op.f("fk_audit_log_organization_id_organizations"),
            "organizations",
            ["organization_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    # Alleen veilig met één organisatie: unieke sleutels worden weer globaal.
    with op.batch_alter_table("audit_log") as batch_op:
        batch_op.drop_constraint(
            op.f("fk_audit_log_organization_id_organizations"), type_="foreignkey"
        )
        batch_op.drop_index(op.f("ix_audit_log_organization_id"))
        batch_op.drop_column("organization_id")

    for table in reversed(TENANT_TABLES):
        with op.batch_alter_table(table) as batch_op:
            if table in UNIQUE_PER_ORG:
                column = UNIQUE_PER_ORG[table]
                batch_op.drop_constraint(op.f(f"uq_{table}_organization_id"), type_="unique")
                batch_op.create_unique_constraint(op.f(f"uq_{table}_{column}"), [column])
            batch_op.drop_constraint(
                op.f(f"fk_{table}_organization_id_organizations"), type_="foreignkey"
            )
            batch_op.drop_index(op.f(f"ix_{table}_organization_id"))
            batch_op.drop_column("organization_id")

    op.drop_table("organizations")
