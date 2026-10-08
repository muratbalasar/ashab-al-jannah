"""Onverwachte fouten: foutcode, regel in het logboek en traceback in het serverlog."""

import logging
import re

from sqlalchemy import select
from test_users import add_org, grant, superadmin_client  # noqa: F401

from ledenadmin.audit import Action
from ledenadmin.domain.enums import Role
from ledenadmin.domain.models import AuditLog
from ledenadmin.tenancy import as_platform
from ledenadmin.web import routes as web_routes
from ledenadmin.web.security import CSRF_COOKIE

BAAS = {"X-Dev-User": "baas", "X-Dev-Roles": ""}


def add_crash_route(monkeypatch) -> None:
    def boom(principal):
        raise RuntimeError("geheime details")

    monkeypatch.setattr(web_routes, "help_sections", boom)


def errors(database) -> list[AuditLog]:
    with database.session() as session:
        stmt = select(AuditLog).where(AuditLog.action.in_((Action.ERROR, Action.CLIENT_ERROR)))
        return list(as_platform(session).scalars(stmt))


def test_unexpected_error_gets_code_log_and_page(client, database, caplog, monkeypatch) -> None:
    org = add_org(database, "stichting-e")
    grant(database, "baas", org, Role.BEHEERDER)
    add_crash_route(monkeypatch)

    with caplog.at_level(logging.ERROR, logger="ledenadmin.audit"):
        response = client.get("/o/stichting-e/help", headers=BAAS)
    assert response.status_code == 500
    code = re.search(r"ERR-[A-Z2-9]{6}", response.text).group(0)
    assert "geheime details" not in response.text
    assert code in caplog.text and "geheime details" in caplog.text

    [entry] = errors(database)
    assert entry.status_code == 500 and entry.path == "/o/stichting-e/help"
    assert code in entry.detail and "RuntimeError" in entry.detail
    assert entry.user == "baas"


def test_browser_error_is_logged(client, database) -> None:
    org = add_org(database, "stichting-e")
    grant(database, "baas", org, Role.BEHEERDER)
    client.get("/aanmelden")
    response = client.post(
        "/o/stichting-e/logboek/fout",
        data={
            "csrf_token": client.cookies[CSRF_COOKIE],
            "melding": "TypeError: x is undefined",
            "pagina": "/o/stichting-e/leden",
        },
        headers=BAAS,
    )
    assert response.status_code == 204
    [entry] = errors(database)
    assert entry.action == Action.CLIENT_ERROR and "TypeError" in entry.detail


def test_platform_shows_error_count(superadmin_client, database, monkeypatch) -> None:  # noqa: F811
    add_crash_route(monkeypatch)
    superadmin_client.get("/o/standaard/help")
    admin = {"X-Dev-User": "baas", "X-Dev-Roles": ""}
    html = superadmin_client.get("/platform", headers=admin).text
    assert re.search(r"fouten \(24 uur\): <strong[^>]*>1</strong>", html)
