"""Fase 6: export, zacht verwijderen, herstellen, definitief wissen en platformoverzicht."""

import io
import json
import zipfile
from datetime import timedelta

import pytest
from sqlalchemy import func, select
from test_my import add_member, link_lid
from test_users import add_org, grant

from ledenadmin.db import utcnow
from ledenadmin.domain.enums import OrganizationStatus, Role
from ledenadmin.domain.models import (
    AuditLog,
    Category,
    Donation,
    Member,
    Membership,
    Organization,
)
from ledenadmin.services.organization_data_service import OrganizationDataService
from ledenadmin.tenancy import as_platform
from ledenadmin.web.security import CSRF_COOKIE

BAAS = {"X-Dev-User": "baas", "X-Dev-Roles": ""}


@pytest.fixture
def org(database) -> int:
    org = add_org(database, "stichting-e")
    grant(database, "baas", org, Role.BEHEERDER)
    add_member(database, org, "Export Lid", "25.00")
    return org


def token(client, headers) -> str:
    client.get("/aanmelden", headers=headers)
    return client.cookies[CSRF_COOKIE]


def count(database, model, org: int) -> int:
    with database.session() as session:
        return as_platform(session).scalar(
            select(func.count()).select_from(model).where(model.organization_id == org)
        )


def test_export_contains_only_own_data(client, database, org) -> None:
    other = add_org(database, "stichting-f")
    add_member(database, other, "Vreemd Lid", "1.00")

    response = client.get("/o/stichting-e/instellingen/export", headers=BAAS)

    assert response.headers["content-type"] == "application/zip"
    assert "export-stichting-e-" in response.headers["content-disposition"]
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    assert set(archive.namelist()) == {
        "export.json",
        "leden.csv",
        "donaties.csv",
        "categorieen.csv",
        "ledenvelden.csv",
        "gebruikers.csv",
    }
    data = json.loads(archive.read("export.json"))
    assert [m["naam"] for m in data["leden"]] == ["Export Lid"]
    assert data["donaties"][0]["bedrag"] == "25.00"
    assert data["gebruikers"] == [{"naam": "baas", "email": "baas@dev.local", "rol": "beheerder"}]
    leden = archive.read("leden.csv").decode("utf-8")
    assert leden.startswith("\ufeff") and "Export Lid" in leden and "Vreemd" not in leden


@pytest.mark.parametrize("role", [Role.PENNINGMEESTER, Role.BESTUURDER])
def test_settings_are_beheerder_only(client, database, org, role) -> None:
    grant(database, "ander", org, role)
    headers = {"X-Dev-User": "ander", "X-Dev-Roles": ""}
    assert client.get("/o/stichting-e/instellingen", headers=headers).status_code == 403
    assert client.get("/o/stichting-e/instellingen/export", headers=headers).status_code == 403


def test_delete_requires_confirmation(client, org) -> None:
    response = client.post(
        "/o/stichting-e/instellingen/verwijderen",
        data={"confirm": "verkeerd", "csrf_token": token(client, BAAS)},
        headers=BAAS,
    )
    assert response.status_code == 422
    assert "stichting-e" in response.text
    assert client.get("/o/stichting-e/leden", headers=BAAS).status_code == 200


def test_soft_delete_hides_organization_and_can_be_restored(client, database, org) -> None:
    response = client.post(
        "/o/stichting-e/instellingen/verwijderen",
        data={"confirm": "stichting-e", "csrf_token": token(client, BAAS)},
        headers=BAAS,
        follow_redirects=False,
    )
    assert response.headers["location"] == "/?melding=verwijderd"
    assert client.get("/o/stichting-e/leden", headers=BAAS).status_code == 404
    assert "definitief gewist" in client.get("/?melding=verwijderd", headers=BAAS).text
    assert count(database, Member, org) == 1

    with database.session() as session:
        OrganizationDataService(session).restore(org)
    assert client.get("/o/stichting-e/leden", headers=BAAS).status_code == 200


def test_purge_removes_everything_after_grace_period(database, org) -> None:
    keep = add_org(database, "stichting-blijft")
    add_member(database, keep, "Blijft", "3.00")
    link_lid(database, org, None)
    with database.session() as session:
        as_platform(session).add(
            AuditLog(organization_id=org, user="baas", action="weergave", method="GET", path="/")
        )
        session.commit()
        service = OrganizationDataService(session)
        service.soft_delete(org)
        assert service.purge_expired() == 0
        assert service.purge_expired(utcnow() + timedelta(days=31)) == 1
        assert session.get(Organization, org) is None

    for model in (Member, Donation, Category, Membership, AuditLog):
        assert count(database, model, org) == 0
    assert count(database, Member, keep) == 1


def test_purge_only_for_deleted(database, org) -> None:
    with database.session() as session:
        with pytest.raises(Exception, match="verwijderde"):
            OrganizationDataService(session).purge(org)


def test_platform_overview_and_actions(client, database, org, settings) -> None:
    superadmin = {"X-Dev-User": "super", "X-Dev-Roles": ""}
    client.app.state.settings = settings.model_copy(update={"superadmin_subjects": "dev|super"})
    html = client.get("/platform", headers=superadmin).text
    assert "Stichting stichting-e" in html
    assert "Export Lid" not in html

    with database.session() as session:
        OrganizationDataService(session).soft_delete(org)
    csrf = token(client, superadmin)
    assert "Herstellen" in client.get("/platform", headers=superadmin).text
    client.post(f"/platform/{org}/wissen", data={"csrf_token": csrf}, headers=superadmin)
    with database.session() as session:
        assert as_platform(session).get(Organization, org) is None


def test_overview_counts(database, org) -> None:
    with database.session() as session:
        row = next(o for o in OrganizationDataService(session).overview() if o["id"] == org)
    assert (row["users"], row["members"], row["status"]) == (1, 1, OrganizationStatus.ACTIVE.value)
