"""zacht verwijderen van organisaties (multi-tenant fase 6)

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-03 22:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import ledenadmin.db

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("deleted_at", ledenadmin.db.UTCDateTime()))


def downgrade() -> None:
    with op.batch_alter_table("organizations") as batch_op:
        batch_op.drop_column("deleted_at")
