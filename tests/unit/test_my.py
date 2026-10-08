"""Fase 5: rol lid en 'Mijn omgeving'."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from test_users import add_org, grant

from ledenadmin.auth.principal import Identity
from ledenadmin.domain.enums import Role
from ledenadmin.domain.models import Donation, Member, Membership, Subcategory
from ledenadmin.services.user_service import UserService
from ledenadmin.tenancy import as_platform

LID = {"X-Dev-User": "lid", "X-Dev-Roles": ""}


def add_member(database, org: int, name: str, amount: str | None = None) -> int:
    with database.session(org) as session:
        member = Member(name=name, email=f"{name.lower().replace(' ', '')}@x.nl")
        session.add(member)
        session.flush()
        if amount:
            sub = session.scalars(select(Subcategory)).first()
            session.add(
                Donation(
                    member_id=member.id,
                    subcategory_id=sub.id,
                    amount_cents=int(Decimal(amount) * 100),
                    donated_at=datetime.now(UTC),
                    created_by="test",
                )
            )
        session.commit()
        return member.id


def link_lid(database, org: int, member_id: int | None) -> None:
    with database.session() as session:
        as_platform(session)
        user = UserService(session).upsert(Identity("dev", "lid", "lid"))
        session.add(
            Membership(
                user_id=user.id, organization_id=org, role=Role.LID.value, member_id=member_id
            )
        )
        session.commit()


@pytest.fixture
def org(database) -> int:
    org = add_org(database, "stichting-m")
    grant(database, "baas", org, Role.BEHEERDER)
    return org


def test_lid_sees_only_own_data(client, database, org) -> None:
    own = add_member(database, org, "Eigen Lid", "12.50")
    add_member(database, org, "Ander Lid", "99.00")
    link_lid(database, org, own)

    home = client.get("/o/stichting-m/", headers=LID, follow_redirects=False)
    assert home.headers["location"] == "/o/stichting-m/mijn"
    html = client.get("/o/stichting-m/mijn", headers=LID).text
    assert "Eigen Lid" in html and "12,50" in html
    assert "Ander Lid" not in html and "99,00" not in html
    assert 'href="/o/stichting-m/mijn"' in html
    assert 'href="/o/stichting-m/leden"' not in html


@pytest.mark.parametrize(
    "path",
    [
        "/o/stichting-m/leden",
        "/o/stichting-m/donaties",
        "/o/stichting-m/rapportage",
        "/o/stichting-m/api/v1/members",
        "/o/stichting-m/gebruikers",
    ],
)
def test_lid_has_no_access_to_management_pages(client, database, org, path) -> None:
    link_lid(database, org, add_member(database, org, "Eigen Lid"))
    assert client.get(path, headers=LID).status_code == 403


def test_lid_without_linked_member(client, database, org) -> None:
    link_lid(database, org, None)
    html = client.get("/o/stichting-m/mijn", headers=LID).text
    assert "nog niet gekoppeld" in html


def test_mijn_requires_self_read(client, database, org) -> None:
    grant(database, "penning", org, Role.PENNINGMEESTER)
    headers = {"X-Dev-User": "penning", "X-Dev-Roles": ""}
    assert client.get("/o/stichting-m/mijn", headers=headers).status_code == 403


def test_year_selection(client, database, org) -> None:
    link_lid(database, org, add_member(database, org, "Eigen Lid", "5.00"))
    last_year = datetime.now(UTC).year - 1
    html = client.get(f"/o/stichting-m/mijn?jaar={last_year}", headers=LID).text
    assert f"Jaaroverzicht {last_year}" in html
    assert "Geen donaties gevonden" in html
    assert "Jaaroverzicht 1900" not in client.get("/o/stichting-m/mijn?jaar=1900", headers=LID).text
