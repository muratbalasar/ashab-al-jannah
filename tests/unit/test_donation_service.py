from datetime import UTC, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from factories import add_member, subcategory
from pydantic import ValidationError

from ledenadmin.domain.enums import MemberStatus
from ledenadmin.domain.errors import BusinessRuleError, NotFoundError
from ledenadmin.schemas.donations import DonationCreate
from ledenadmin.services.donation_service import DonationService

AMS = ZoneInfo("Europe/Amsterdam")
NOW = datetime(2026, 3, 10, 12, 0, tzinfo=UTC)


def service(session, allow_inactive: bool = False) -> DonationService:
    return DonationService(session, AMS, allow_inactive, clock=lambda: NOW)


def donation(session, member_id: int, amount: str = "50.00", **extra) -> DonationCreate:
    sub = subcategory(session, "Sponsoring", "MKB")
    return DonationCreate(member_id=member_id, subcategory_id=sub.id, amount=amount, **extra)


def test_register_defaults_to_now_and_stores_cents(session) -> None:
    member = add_member(session)

    result = service(session).register(donation(session, member.id), actor="penningmeester")

    assert result.amount_cents == 5000
    assert result.amount == Decimal("50.00")
    assert result.donated_at == NOW
    assert result.category.name == "Sponsoring"
    assert result.subcategory.name == "MKB"
    assert result.created_by == "penningmeester"


def test_naive_timestamp_is_interpreted_in_configured_timezone(session) -> None:
    member = add_member(session)
    data = donation(session, member.id, donated_at=datetime(2026, 2, 14, 10, 30))

    result = service(session).register(data, actor="t")

    assert result.donated_at == datetime(2026, 2, 14, 9, 30, tzinfo=UTC)


def test_future_timestamp_is_rejected(session) -> None:
    member = add_member(session)
    data = donation(session, member.id, donated_at=datetime(2026, 3, 11, 12, 0, tzinfo=UTC))

    with pytest.raises(BusinessRuleError) as error:
        service(session).register(data, actor="t")
    assert error.value.field == "donated_at"


def test_unknown_member_is_rejected(session) -> None:
    with pytest.raises(BusinessRuleError) as error:
        service(session).register(donation(session, 999), actor="t")
    assert error.value.field == "member_id"


def test_inactive_member_rule_is_configurable(session) -> None:
    member = add_member(session)
    member.status = MemberStatus.INACTIVE
    session.commit()

    with pytest.raises(BusinessRuleError):
        service(session).register(donation(session, member.id), actor="t")
    assert service(session, allow_inactive=True).register(donation(session, member.id), "t").id


def test_inactive_subcategory_is_rejected(session) -> None:
    member = add_member(session)
    data = donation(session, member.id)
    subcategory(session, "Sponsoring", "MKB").is_active = False
    session.commit()

    with pytest.raises(BusinessRuleError):
        service(session).register(data, actor="t")


@pytest.mark.parametrize("amount", ["0", "-5", "10.001", "abc"])
def test_invalid_amount_is_rejected_by_schema(amount: str) -> None:
    with pytest.raises(ValidationError):
        DonationCreate(member_id=1, subcategory_id=1, amount=amount)


def test_get_unknown_donation_raises_not_found(session) -> None:
    with pytest.raises(NotFoundError):
        service(session).get(123)


def test_recent_filters_on_member(session) -> None:
    jan = add_member(session, "Jan Jansen")
    piet = add_member(session, "Piet Pieters")
    svc = service(session)
    svc.register(donation(session, jan.id), "t")
    svc.register(donation(session, piet.id, "10"), "t")

    assert [d.member_id for d in svc.recent(member_id=piet.id)] == [piet.id]
    assert len(svc.recent()) == 2
