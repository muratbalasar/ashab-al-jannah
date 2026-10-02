from datetime import UTC, datetime

from sqlalchemy import func, select

from ledenadmin.domain.models import Donation, Member
from ledenadmin.dummy_data import DUMMY_MEMBERS, seed

NOW = datetime(2026, 10, 1, 12, tzinfo=UTC)


def test_seed_adds_members_with_spread_donations(session):
    members, donations = seed(session, now=NOW)

    assert members == len(DUMMY_MEMBERS) == 120
    assert donations == session.scalar(select(func.count(Donation.id))) > 300
    rows = list(session.scalars(select(Donation)))
    assert len({d.subcategory_id for d in rows}) > 3
    assert len({(d.donated_at.year, d.donated_at.month) for d in rows}) > 6
    assert all(d.donated_at <= NOW for d in rows)


def test_seed_is_idempotent(session):
    seed(session, now=NOW)

    assert seed(session, now=NOW) == (0, 0)
    assert session.scalar(select(func.count(Member.id))) == 120
    assert len(set(session.scalars(select(Member.email)))) == 120
