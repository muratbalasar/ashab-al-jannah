"""Scheiding tussen organisaties: organisatie A mag nooit gegevens van B zien of wijzigen."""

from datetime import UTC, datetime

import pytest
from factories import add_donation, add_member
from sqlalchemy import select

from ledenadmin.domain.models import AuditLog, Category, Member, MemberField, Organization
from ledenadmin.services.category_service import CategoryService
from ledenadmin.services.member_field_service import MemberFieldService
from ledenadmin.services.organization_service import ensure_default_organization
from ledenadmin.tenancy import TenantContextError, as_platform

BEHEERDER = {"X-Dev-Roles": "beheerder"}


@pytest.fixture
def other_org(database) -> int:
    with database.session() as session:
        as_platform(session)
        org = Organization(slug="andere", name="Andere stichting")
        session.add(org)
        session.commit()
        org_id = org.id
    with database.session(org_id) as session:
        CategoryService(session).ensure_defaults()
        member = add_member(session, "Geheim Lid", "geheim@andere.nl")
        add_donation(session, member, "99.00", datetime(2026, 1, 1, tzinfo=UTC))
        MemberFieldService(session).create("Geheim veld", "tekst")
    return org_id


def test_queries_only_return_own_organization(session, other_org) -> None:
    add_member(session, "Eigen Lid", "eigen@x.nl")

    assert [m.name for m in session.scalars(select(Member))] == ["Eigen Lid"]
    assert all(c.organization_id != other_org for c in session.scalars(select(Category)))
    assert list(session.scalars(select(MemberField))) == []


def test_get_by_id_of_other_organization_returns_nothing(database, session, other_org) -> None:
    with database.session(other_org) as other:
        foreign_id = other.scalar(select(Member.id))
    assert session.get(Member, foreign_id) is None


def test_same_email_and_category_allowed_in_different_organizations(session, other_org) -> None:
    add_member(session, "Kopie", "geheim@andere.nl")
    assert session.scalar(select(Member.email)) == "geheim@andere.nl"


def test_new_rows_get_organization_and_cannot_be_moved(session, organization_id, other_org) -> None:
    member = add_member(session, "Nieuw Lid", "nieuw@x.nl")
    assert member.organization_id == organization_id

    member.organization_id = other_org
    with pytest.raises(TenantContextError):
        session.commit()


def test_query_without_organization_context_fails(database) -> None:
    with database.session() as session, pytest.raises(TenantContextError):
        session.scalars(select(Member)).all()


def test_web_and_api_never_show_other_organization(client, other_org, database) -> None:
    with database.session(other_org) as other:
        member_id = other.scalar(select(Member.id))

    assert "Geheim Lid" not in client.get("/leden", headers=BEHEERDER).text
    assert "Geheim veld" not in client.get("/ledenvelden", headers=BEHEERDER).text
    assert client.get(f"/leden/{member_id}", headers=BEHEERDER).status_code == 404
    assert client.get(f"/api/v1/members/{member_id}", headers=BEHEERDER).status_code == 404
    assert client.get("/api/v1/members", headers=BEHEERDER).json() == []
    assert "99,00" not in client.get("/donaties", headers=BEHEERDER).text


def test_audit_log_is_per_organization(client, database, other_org) -> None:
    with database.session() as session:
        session.add(
            AuditLog(
                organization_id=other_org,
                user="Spion",
                action="weergave",
                method="GET",
                path="/leden",
            )
        )
        session.commit()
    client.get("/leden", headers={"X-Dev-User": "Omar"})

    html = client.get("/logboek", headers=BEHEERDER).text
    assert "Omar" in html and "Spion" not in html


def test_default_organization_is_created_once(client, database, organization_id) -> None:
    with database.session() as session:
        assert ensure_default_organization(session) == organization_id
        assert session.scalars(select(Organization.slug)).all() == ["standaard"]
