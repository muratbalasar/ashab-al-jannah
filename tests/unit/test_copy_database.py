"""Gegevens overzetten naar een andere database (bijv. van Azure SQL naar SQLite)."""

from datetime import UTC, datetime

import pytest
from alembic import command
from sqlalchemy import func, select
from test_migrations import alembic_config

from ledenadmin.copy_database import TargetNotEmptyError, copy_database, main
from ledenadmin.db import Database
from ledenadmin.domain.models import Donation, Member, Organization
from ledenadmin.services.category_service import CategoryService
from ledenadmin.tenancy import as_platform


def migrated(tmp_path, name: str) -> str:
    url = f"sqlite:///{tmp_path / name}"
    command.upgrade(alembic_config(url), "head")
    return url


def seed(url: str) -> None:
    database = Database(url)
    with database.session() as session:
        org_id = as_platform(session).scalar(select(Organization.id))
    with database.session(org_id) as session:
        CategoryService(session).ensure_defaults()
        member = Member(name="Jan", email="jan@x.nl")
        session.add(member)
        session.flush()
        sub = CategoryService(session).list()[0].subcategories[0]
        when = datetime(2026, 2, 14, 9, 30, tzinfo=UTC)
        session.add(
            Donation(member_id=member.id, subcategory_id=sub.id, amount_cents=500, donated_at=when)
        )
        session.commit()
    database.engine.dispose()


def test_copies_all_tables_and_keeps_values(tmp_path, capsys) -> None:
    source, target = migrated(tmp_path, "bron.db"), migrated(tmp_path, "doel.db")
    seed(source)

    assert main([source, target]) == 0

    assert "donations: 1" in capsys.readouterr().out
    database = Database(target)
    with database.session() as session:
        as_platform(session)
        donation = session.scalar(select(Donation))
        assert (donation.amount_cents, donation.donated_at.hour) == (500, 9)
        assert donation.member.name == "Jan"
        assert session.scalar(select(func.count(Organization.id))) == 1
    database.engine.dispose()


def test_refuses_target_with_data(tmp_path) -> None:
    source, target = migrated(tmp_path, "bron.db"), migrated(tmp_path, "doel.db")
    seed(source)
    seed(target)

    with pytest.raises(TargetNotEmptyError, match="members"):
        copy_database(source, target)
    assert main([source, target]) == 1
    assert main([]) == 2
