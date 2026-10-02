from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from factories import add_donation, add_member, subcategory
from pydantic import ValidationError

from ledenadmin.schemas.reports import ReportFilter
from ledenadmin.services.report_service import ReportService

AMS = ZoneInfo("Europe/Amsterdam")


def local(*args) -> datetime:
    return datetime(*args, tzinfo=AMS)


@pytest.fixture
def data(session):
    jan = add_member(session, "Jan Jansen")
    piet = add_member(session, "Piet Pieters")
    add_donation(session, jan, "10.00", local(2026, 1, 31, 23, 30))
    add_donation(session, jan, "50.00", local(2026, 2, 1, 0, 0), "Sponsoring", "MKB")
    add_donation(session, piet, "25.50", local(2026, 2, 15, 12, 0), "Contributie", "Jaarlijks")
    add_donation(session, jan, "30.00", local(2026, 2, 28, 23, 59), "Contributie", "Maandelijks")
    add_donation(session, piet, "99.00", local(2026, 3, 1, 0, 0))
    return {"jan": jan, "piet": piet}


def build(session, **filters):
    return ReportService(session, AMS).build(ReportFilter(**filters))


def test_period_is_inclusive_in_local_timezone(session, data) -> None:
    report = build(session, start_date=date(2026, 2, 1), end_date=date(2026, 2, 28))

    assert report.count == 3
    assert report.total == Decimal("105.50")
    assert [b.key for b in report.by_month] == ["2026-02"]


def test_breakdowns_add_up_to_total(session, data) -> None:
    report = build(session)

    for breakdown in (report.by_category, report.by_subcategory, report.by_month, report.by_member):
        assert sum(b.total for b in breakdown) == report.total
        assert sum(b.count for b in breakdown) == report.count
    assert report.by_category[0].label == "Sponsoring"
    assert report.average == Decimal("42.90")


def test_member_period_report_only_contains_that_member(session, data) -> None:
    report = build(
        session,
        member_id=data["jan"].id,
        start_date=date(2026, 2, 1),
        end_date=date(2026, 2, 28),
    )

    assert {d.member_name for d in report.donations} == {"Jan Jansen"}
    assert report.total == Decimal("80.00")


def test_category_and_subcategory_filters(session, data) -> None:
    contributie = subcategory(session, "Contributie", "Jaarlijks").category

    by_category = build(session, category_id=contributie.id)
    by_sub = build(session, subcategory_id=subcategory(session, "Contributie", "Jaarlijks").id)

    assert by_category.total == Decimal("55.50")
    assert by_sub.total == Decimal("25.50")


def test_empty_period_returns_empty_report(session, data) -> None:
    report = build(session, start_date=date(2025, 1, 1), end_date=date(2025, 12, 31))

    assert report.is_empty
    assert report.total == Decimal("0.00")
    assert report.average is None
    assert report.by_category == [] and report.by_month == []


def test_end_before_start_is_rejected() -> None:
    with pytest.raises(ValidationError, match="einddatum"):
        ReportFilter(start_date=date(2026, 2, 2), end_date=date(2026, 2, 1))


def test_without_member_details_removes_personal_data(session, data) -> None:
    report = build(session).without_member_details()

    assert report.by_member == [] and report.donations == []
    assert report.includes_member_details is False
    assert report.total == Decimal("214.50")
