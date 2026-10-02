from datetime import UTC, datetime

import pytest
from factories import add_donation, add_member
from pydantic import ValidationError

from ledenadmin.domain.enums import MemberStatus
from ledenadmin.domain.errors import ConflictError, NotFoundError
from ledenadmin.schemas.members import MemberCreate, MemberUpdate
from ledenadmin.services.member_service import MemberService


def test_create_member_normalizes_email_and_defaults_to_active(session) -> None:
    member = MemberService(session).create(
        MemberCreate(name="  Jan Jansen ", email="Jan@Example.NL"), actor="beheerder"
    )

    assert member.id is not None
    assert member.name == "Jan Jansen"
    assert member.email == "jan@example.nl"
    assert member.status == MemberStatus.ACTIVE
    assert member.created_by == "beheerder"


def test_duplicate_email_is_rejected_case_insensitive(session) -> None:
    service = MemberService(session)
    service.create(MemberCreate(name="Jan", email="jan@example.nl"), actor="t")

    with pytest.raises(ConflictError) as error:
        service.create(MemberCreate(name="Ander", email="JAN@example.nl"), actor="t")

    assert error.value.field == "email"


@pytest.mark.parametrize("payload", [{"name": "", "email": "a@b.nl"}, {"name": "A", "email": "x"}])
def test_invalid_member_input_is_rejected(payload) -> None:
    with pytest.raises(ValidationError):
        MemberCreate(**payload)


def test_deactivating_member_keeps_donation_history(session) -> None:
    member = add_member(session)
    add_donation(session, member, "50.00", datetime(2026, 2, 1, tzinfo=UTC))

    updated = MemberService(session).update(member.id, MemberUpdate(status=MemberStatus.INACTIVE))

    assert updated.status == MemberStatus.INACTIVE
    assert len(updated.donations) == 1


def test_update_to_email_of_other_member_conflicts(session) -> None:
    add_member(session, "Jan Jansen", "jan@example.nl")
    piet = add_member(session, "Piet Pieters", "piet@example.nl")

    with pytest.raises(ConflictError):
        MemberService(session).update(piet.id, MemberUpdate(email="jan@example.nl"))


def test_update_keeping_own_email_is_allowed(session) -> None:
    jan = add_member(session, "Jan Jansen", "jan@example.nl")

    updated = MemberService(session).update(
        jan.id, MemberUpdate(name="Jan J.", email="jan@example.nl")
    )

    assert updated.name == "Jan J."


def test_search_by_text_and_status(session) -> None:
    add_member(session, "Jan Jansen", "jan@example.nl")
    piet = add_member(session, "Piet Pieters", "piet@club.nl")
    piet.status = MemberStatus.INACTIVE
    session.commit()
    service = MemberService(session)

    assert [m.name for m in service.search("JANS")] == ["Jan Jansen"]
    assert [m.name for m in service.search("club")] == ["Piet Pieters"]
    assert [m.name for m in service.search(status=MemberStatus.INACTIVE)] == ["Piet Pieters"]


def test_get_unknown_member_raises_not_found(session) -> None:
    with pytest.raises(NotFoundError):
        MemberService(session).get(999)
