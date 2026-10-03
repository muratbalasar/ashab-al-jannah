"""Fase 2: gebruikers, lidmaatschappen per organisatie, URL /o/{org}, superadmin."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from ledenadmin.auth.principal import Identity
from ledenadmin.domain.enums import OrganizationStatus, Role
from ledenadmin.domain.models import Membership, Organization, User
from ledenadmin.main import create_app
from ledenadmin.services.category_service import CategoryService
from ledenadmin.services.user_service import UserService
from ledenadmin.tenancy import as_platform
from ledenadmin.web.security import CSRF_COOKIE

BEHEERDER = {"X-Dev-Roles": "beheerder"}


def add_org(database, slug: str, kvk: str | None = None) -> int:
    with database.session() as session:
        as_platform(session)
        org = Organization(slug=slug, name=f"Stichting {slug}", kvk_number=kvk)
        session.add(org)
        session.commit()
        org_id = org.id
    with database.session(org_id) as session:
        CategoryService(session).ensure_defaults()
    return org_id


def grant(database, user_name: str, org_id: int, role: Role) -> None:
    with database.session() as session:
        as_platform(session)
        users = UserService(session)
        user = users.upsert(Identity("dev", user_name, user_name))
        users.grant(user, org_id, frozenset({role}))
        session.commit()


@pytest.fixture
def org_b(database) -> int:
    return add_org(database, "stichting-b", kvk="12345678")


def test_login_creates_user_and_default_membership(client, database) -> None:
    client.get("/o/standaard/leden", headers={"X-Dev-User": "aisha", **BEHEERDER})

    with database.session() as session:
        as_platform(session)
        user = session.scalar(select(User).where(User.subject == "aisha"))
        roles = session.scalars(select(Membership.role).where(Membership.user_id == user.id))
        assert user.email == "aisha@dev.local"
        assert user.last_login_at is not None
        assert list(roles) == ["beheerder"]


def test_claimed_roles_do_not_grant_access_to_other_organizations(client, org_b) -> None:
    headers = {"X-Dev-User": "indringer", **BEHEERDER}

    assert client.get("/o/stichting-b/leden", headers=headers).status_code == 404
    assert client.get("/o/stichting-b/api/v1/members", headers=headers).status_code == 404
    assert client.get("/o/bestaat-niet/leden", headers=headers).status_code == 404


def test_membership_gives_roles_only_in_that_organization(client, database, org_b) -> None:
    grant(database, "penning", org_b, Role.PENNINGMEESTER)
    headers = {"X-Dev-User": "penning", "X-Dev-Roles": ""}

    me = client.get("/o/stichting-b/api/v1/me", headers=headers).json()
    assert me["roles"] == ["penningmeester"]
    assert me["organization_id"] == org_b
    assert client.get("/o/stichting-b/donaties", headers=headers).status_code == 200
    assert client.get("/o/stichting-b/categorieen", headers=headers).status_code == 403
    assert client.get("/o/standaard/leden", headers=headers).status_code == 404


def test_links_and_redirects_stay_inside_organization(client, database, org_b) -> None:
    grant(database, "beheer-b", org_b, Role.BEHEERDER)
    headers = {"X-Dev-User": "beheer-b", "X-Dev-Roles": ""}

    html = client.get("/o/stichting-b/leden", headers=headers).text
    assert 'href="/o/stichting-b/leden/nieuw"' in html
    assert 'data-org="/o/stichting-b"' in html
    client.get("/o/stichting-b/leden", headers=headers)
    token = client.cookies[CSRF_COOKIE]
    response = client.post(
        "/o/stichting-b/leden",
        data={"name": "B Lid", "email": "b@b.nl", "csrf_token": token},
        headers=headers,
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith("/o/stichting-b/leden/")
    assert "B Lid" not in client.get("/o/standaard/leden").text


def test_kvk_number_redirects_to_slug(client, database, org_b) -> None:
    grant(database, "beheer-b", org_b, Role.BEHEERDER)

    response = client.get(
        "/o/12345678/leden?q=x", headers={"X-Dev-User": "beheer-b"}, follow_redirects=False
    )

    assert response.status_code == 307
    assert response.headers["location"] == "/o/stichting-b/leden?q=x"


def test_blocked_organization_is_not_reachable(client, database, org_b) -> None:
    grant(database, "beheer-b", org_b, Role.BEHEERDER)
    with database.session() as session:
        as_platform(session)
        session.get(Organization, org_b).status = OrganizationStatus.BLOCKED
        session.commit()

    assert client.get("/o/stichting-b/leden", headers={"X-Dev-User": "beheer-b"}).status_code == 404


def test_home_lists_organizations_when_user_has_several(client, database, org_b) -> None:
    grant(database, "tweevoud", org_b, Role.BESTUURDER)
    headers = {"X-Dev-User": "tweevoud", "X-Dev-Roles": "bestuurder"}

    html = client.get("/", headers=headers).text

    assert 'href="/o/stichting-b/"' in html
    assert 'href="/o/standaard/"' in html


def test_legacy_urls_redirect_to_default_organization(client) -> None:
    response = client.get("/leden/5?x=1", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/o/standaard/leden/5?x=1"
    assert client.get("/onbekend", follow_redirects=False).status_code == 404


@pytest.fixture
def superadmin_client(settings, database) -> Iterator[TestClient]:
    with_admin = settings.model_copy(update={"superadmin_subjects": "dev|baas, x|y"})
    with TestClient(create_app(with_admin, database)) as test_client:
        yield test_client


def test_platform_is_only_for_superadmin(superadmin_client, org_b) -> None:
    client = superadmin_client
    assert client.get("/platform", headers={"X-Dev-User": "gewoon"}).status_code == 403

    admin = {"X-Dev-User": "baas", "X-Dev-Roles": ""}
    html = client.get("/platform", headers=admin).text
    assert "Stichting stichting-b" in html
    assert "12345678" in html

    token = client.cookies[CSRF_COOKIE]
    response = client.post(
        f"/platform/{org_b}/status",
        data={"status": "geblokkeerd", "csrf_token": token},
        headers=admin,
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "geblokkeerd" in client.get("/platform", headers=admin).text


def test_superadmin_without_membership_sees_no_member_data(superadmin_client, org_b) -> None:
    admin = {"X-Dev-User": "baas", "X-Dev-Roles": ""}

    assert superadmin_client.get("/o/stichting-b/leden", headers=admin).status_code == 404
