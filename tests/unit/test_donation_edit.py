"""Donaties corrigeren: wijzigingsgeschiedenis, online betalingen, rechten en voorbije jaren."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from factories import add_donation, add_member, subcategory
from sqlalchemy import select
from test_users import add_org, grant

from ledenadmin.domain.enums import MemberStatus, Role
from ledenadmin.domain.errors import BusinessRuleError
from ledenadmin.domain.models import Donation, DonationChange, Payment
from ledenadmin.schemas.donations import DonationUpdate
from ledenadmin.services.donation_service import DonationService
from ledenadmin.web.security import CSRF_COOKIE

AMS = ZoneInfo("Europe/Amsterdam")
NOW = datetime(2026, 3, 10, 12, 0, tzinfo=UTC)
WHEN = datetime(2026, 2, 14, 9, 30, 27, tzinfo=UTC)


def service(session) -> DonationService:
    return DonationService(session, AMS, clock=lambda: NOW)


def update(donation, **changes) -> DonationUpdate:
    data = {
        "member_id": donation.member_id,
        "subcategory_id": donation.subcategory_id,
        "amount": str(donation.amount),
        # Het formulier stuurt lokale tijd zonder seconden.
        "donated_at": donation.donated_at.astimezone(AMS).replace(second=0, tzinfo=None),
        "description": donation.description,
    }
    return DonationUpdate(**(data | changes))


def test_update_records_old_and_new_values(session) -> None:
    jan = add_member(session)
    piet = add_member(session, "Piet Pieters")
    donation = add_donation(session, jan, "50.00", WHEN, description="Oud")
    project = subcategory(session, "Donatie", "Project")

    result = service(session).update(
        donation.id,
        update(
            donation,
            member_id=piet.id,
            subcategory_id=project.id,
            amount="5.00",
            donated_at=datetime(2026, 2, 13, 10, 0),
            description="",
        ),
        actor="baas",
    )

    fields = {c.field: (c.old_value, c.new_value) for c in result.changes}
    assert fields == {
        "Lid": (f"Jan Jansen ({jan.id})", f"Piet Pieters ({piet.id})"),
        "Categorie": ("Sponsoring – MKB", "Donatie – Project"),
        "Bedrag": ("€ 50,00", "€ 5,00"),
        "Datum": ("14-02-2026 10:30", "13-02-2026 10:00"),
        "Omschrijving": ("Oud", "–"),
    }
    assert result.years == {2026}
    stored = session.get(Donation, donation.id)
    assert (stored.member_id, stored.amount_cents, stored.description) == (piet.id, 500, None)
    history = service(session).changes(donation.id)
    assert len(history) == 5 and {c.changed_by for c in history} == {"baas"}


def test_unchanged_form_records_nothing_and_keeps_seconds(session) -> None:
    donation = add_donation(session, add_member(session), "50.00", WHEN)

    result = service(session).update(donation.id, update(donation), actor="baas")

    assert result.changes == [] and result.years == frozenset()
    assert session.get(Donation, donation.id).donated_at == WHEN
    assert session.scalars(select(DonationChange)).all() == []


def test_online_payment_locks_member_amount_and_date(session) -> None:
    jan = add_member(session)
    donation = add_donation(session, jan, "25.00", WHEN)
    session.add(
        Payment(
            member_id=jan.id,
            subcategory_id=donation.subcategory_id,
            amount_cents=2500,
            status="paid",
            donation_id=donation.id,
        )
    )
    session.commit()
    svc = service(session)
    assert svc.is_online_payment(donation.id)

    with pytest.raises(BusinessRuleError, match="online betaald"):
        svc.update(donation.id, update(donation, amount="20.00"), actor="baas")
    with pytest.raises(BusinessRuleError, match="online betaald"):
        svc.update(donation.id, update(donation, member_id=add_member(session, "Piet").id), "b")

    result = svc.update(donation.id, update(donation, description="Iftar"), actor="baas")
    assert [c.field for c in result.changes] == ["Omschrijving"]


def test_inactive_member_or_subcategory_stays_until_changed(session) -> None:
    jan = add_member(session)
    donation = add_donation(session, jan, "50.00", WHEN)
    jan.status = MemberStatus.INACTIVE
    subcategory(session, "Sponsoring", "MKB").is_active = False
    session.commit()

    result = service(session).update(donation.id, update(donation, amount="60.00"), "baas")
    assert [c.field for c in result.changes] == ["Bedrag"]

    other = add_member(session, "Kees Klaassen")
    other.status = MemberStatus.INACTIVE
    session.commit()
    with pytest.raises(BusinessRuleError) as error:
        service(session).update(donation.id, update(donation, member_id=other.id), "baas")
    assert error.value.field == "member_id"


def test_years_cover_old_and_new_date(session) -> None:
    donation = add_donation(session, add_member(session), "50.00", WHEN)

    result = service(session).update(
        donation.id, update(donation, donated_at=datetime(2025, 12, 31, 23, 0)), "baas"
    )

    assert result.years == {2025, 2026}


def test_future_date_is_rejected(session) -> None:
    donation = add_donation(session, add_member(session), "50.00", WHEN)

    with pytest.raises(BusinessRuleError) as error:
        service(session).update(
            donation.id, update(donation, donated_at=datetime(2026, 4, 1, 10, 0)), "baas"
        )
    assert error.value.field == "donated_at"


# ── Web ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def org(database) -> int:
    org_id = add_org(database, "stichting-e")
    grant(database, "baas", org_id, Role.BEHEERDER)
    grant(database, "penning", org_id, Role.PENNINGMEESTER)
    return org_id


def headers(user: str) -> dict[str, str]:
    return {"X-Dev-User": user, "X-Dev-Roles": ""}


def seed(database, org: int, when: datetime) -> tuple[int, int]:
    with database.session(org) as session:
        member = add_member(session, "Lid Een", "lid@x.nl")
        donation = add_donation(session, member, "50.00", when)
        return member.id, donation.id


def form_values(database, org: int, donation_id: int, **changes: str) -> dict[str, str]:
    """Wat het bewerkformulier verstuurt als niets wordt aangepast."""
    with database.session(org) as session:
        d = session.get(Donation, donation_id)
        values = {
            "member_id": str(d.member_id),
            "subcategory_id": str(d.subcategory_id),
            "amount": f"{d.amount:.2f}".replace(".", ","),
            "donated_at": d.donated_at.astimezone(AMS).strftime("%d-%m-%Y %H:%M"),
            "description": d.description or "",
        }
    return values | changes


def test_edit_link_and_page_only_for_beheerder(client, database, org) -> None:
    member_id, donation_id = seed(database, org, datetime.now(UTC))
    page = f"/o/stichting-e/leden/{member_id}"
    edit = f"/o/stichting-e/donaties/{donation_id}/bewerken"

    assert f"{edit}?terug=" in client.get(page, headers=headers("baas")).text
    assert "/bewerken" not in client.get(page, headers=headers("penning")).text
    assert client.get(edit, headers=headers("penning")).status_code == 403
    assert client.post(edit, headers=headers("penning")).status_code == 403
    response = client.get(edit, headers=headers("baas"))
    assert "Donatie bewerken" in response.text and "nog niet gewijzigd" in response.text


def test_edit_via_web_redirects_back_and_shows_history(client, database, org) -> None:
    _, donation_id = seed(database, org, datetime.now(UTC))
    edit = f"/o/stichting-e/donaties/{donation_id}/bewerken"
    form = client.get(
        f"{edit}?terug=/o/stichting-e/rapportage?jaar=1%26melding=x", headers=headers("baas")
    )
    assert 'name="terug" value="/o/stichting-e/rapportage?jaar=1"' in form.text
    token = client.cookies[CSRF_COOKIE]

    response = client.post(
        edit,
        data=form_values(database, org, donation_id, amount="7,50")
        | {"csrf_token": token, "terug": "/o/stichting-e/rapportage?jaar=1"},
        headers=headers("baas"),
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (
        "/o/stichting-e/rapportage?jaar=1&melding=donatie-bijgewerkt"
    )
    history = client.get(edit, headers=headers("baas")).text
    assert "€ 50,00" in history and "€ 7,50" in history and "baas" in history

    unchanged = client.post(
        edit,
        data=form_values(database, org, donation_id)
        | {"csrf_token": token, "terug": "https://evil.example"},
        headers=headers("baas"),
        follow_redirects=False,
    )
    assert unchanged.headers["location"] == "/o/stichting-e/donaties?melding=donatie-ongewijzigd"


def test_past_year_warns_and_names_year(client, database, org) -> None:
    last_year = datetime.now(UTC).year - 1
    _, donation_id = seed(database, org, datetime(last_year, 6, 1, 10, 0, tzinfo=UTC))
    edit = f"/o/stichting-e/donaties/{donation_id}/bewerken"

    form = client.get(edit, headers=headers("baas"))
    assert f"valt in {last_year}" in form.text and "data-confirm" in form.text
    response = client.post(
        edit,
        data=form_values(database, org, donation_id, amount="1,00")
        | {"csrf_token": client.cookies[CSRF_COOKIE]},
        headers=headers("baas"),
    )
    assert f"de cijfers over {last_year}" in response.text


def test_invalid_input_rerenders_form(client, database, org) -> None:
    _, donation_id = seed(database, org, datetime.now(UTC))
    edit = f"/o/stichting-e/donaties/{donation_id}/bewerken"
    client.get(edit, headers=headers("baas"))

    response = client.post(
        edit,
        data={"amount": "-5", "csrf_token": client.cookies[CSRF_COOKIE]},
        headers=headers("baas"),
    )

    assert response.status_code == 422
    assert "Vul een bedrag groter dan 0 in" in response.text
    assert (
        client.get("/o/stichting-e/donaties/999/bewerken", headers=headers("baas")).status_code
        == 404
    )


def test_other_organization_donation_is_not_found(client, database, org) -> None:
    other = add_org(database, "stichting-f")
    _, donation_id = seed(database, other, datetime.now(UTC))

    url = f"/o/stichting-e/donaties/{donation_id}/bewerken"
    assert client.get(url, headers=headers("baas")).status_code == 404


def test_history_is_removed_with_donation(database, org) -> None:
    _, donation_id = seed(database, org, datetime.now(UTC))
    with database.session(org) as session:
        donation = session.get(Donation, donation_id)
        svc = DonationService(session, AMS)
        svc.update(donation_id, update(donation, amount="9.00"), "baas")
        svc.delete_many([donation_id])
        assert session.scalars(select(DonationChange)).all() == []
