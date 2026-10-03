from sqlalchemy import select

from ledenadmin.audit import Action, classify
from ledenadmin.domain.models import AuditLog

BEHEERDER = {"X-Dev-Roles": "beheerder"}


def entries(database) -> list[AuditLog]:
    with database.session() as session:
        return list(session.scalars(select(AuditLog).order_by(AuditLog.id)))


def test_classify() -> None:
    assert classify("GET", "/o/standaard/leden") == Action.VIEW
    assert classify("POST", "/o/standaard/leden") == Action.UPDATE
    assert classify("PATCH", "/o/standaard/api/v1/members/1") == Action.UPDATE
    assert classify("POST", "/o/standaard/donaties/verwijderen") == Action.DELETE
    assert classify("DELETE", "/o/standaard/api/v1/donations/1") == Action.DELETE
    assert classify("POST", "/o/standaard/logboek/klik") == Action.CLICK


def test_login_view_update_click_and_delete_are_logged(csrf_client, database) -> None:
    csrf_client.cookies.delete("logboek_sessie")
    csrf_client.get("/o/standaard/leden?q=jan", headers={"X-Dev-User": "Fatima"})
    csrf_client.post(
        "/o/standaard/leden",
        data={"name": "Jan", "email": "jan@x.nl", "csrf_token": csrf_client.csrf},
        headers={"X-Dev-User": "Fatima"},
    )
    csrf_client.post(
        "/o/standaard/logboek/klik",
        data={
            "label": "Opslaan",
            "pagina": "/o/standaard/leden/nieuw",
            "csrf_token": csrf_client.csrf,
        },
    )
    csrf_client.delete("/o/standaard/api/v1/donations/999")
    csrf_client.get("/static/app.css")

    log = entries(database)
    actions = [(e.action, e.method, e.path) for e in log]
    assert ("aanmelding", "GET", "/o/standaard/leden") in actions
    assert ("weergave", "GET", "/o/standaard/leden") in actions
    assert ("wijziging", "POST", "/o/standaard/leden") in actions
    assert ("klik", "POST", "/o/standaard/logboek/klik") in actions
    assert ("verwijdering", "DELETE", "/o/standaard/api/v1/donations/999") in actions
    assert not any(e.path.startswith("/static") for e in log)
    assert sum(e.action == "aanmelding" and e.path == "/o/standaard/leden" for e in log) == 1

    update = next(e for e in log if e.action == "wijziging")
    assert update.user == "Fatima" and update.status_code == 303
    assert '"email": "jan@x.nl"' in update.detail and "csrf_token" not in update.detail
    assert '"label": "Opslaan"' in next(e for e in log if e.action == "klik").detail
    assert next(
        e for e in log if e.action == "weergave" and e.path == "/o/standaard/leden"
    ).detail == ('{"query": "q=jan"}')


def test_click_requires_csrf(client, database) -> None:
    assert client.post("/o/standaard/logboek/klik", data={"label": "x"}).status_code == 403


def test_audit_page_only_for_beheerder(client) -> None:
    client.get("/o/standaard/leden", headers={"X-Dev-User": "Omar"})

    html = client.get("/o/standaard/logboek?gebruiker=omar&actie=weergave", headers=BEHEERDER).text

    assert 'href="/o/standaard/logboek"' in html
    assert "<td>Omar</td>" in html and "/o/standaard/leden" in html
    for role in ("penningmeester", "bestuurder"):
        headers = {"X-Dev-Roles": role}
        assert client.get("/o/standaard/logboek", headers=headers).status_code == 403
        assert (
            'href="/o/standaard/logboek"'
            not in client.get("/o/standaard/rapportage", headers=headers).text
        )


def test_purge_removes_entries_older_than_41_days(database) -> None:
    from datetime import UTC, datetime, timedelta

    from ledenadmin.audit import purge

    now = datetime(2026, 10, 1, tzinfo=UTC)
    with database.session() as session:
        for days in (0, 40, 42, 100):
            session.add(
                AuditLog(
                    at=now - timedelta(days=days),
                    user="x",
                    action="weergave",
                    method="GET",
                    path="/",
                )
            )
        session.commit()
        assert purge(session, now) == 2
        assert {e.at.replace(tzinfo=UTC) for e in session.scalars(select(AuditLog))} == {
            now,
            now - timedelta(days=40),
        }


def test_lists_render_all_rows_for_client_paging(client, session) -> None:
    from ledenadmin.dummy_data import seed

    seed(session)
    html = client.get("/o/standaard/leden", headers=BEHEERDER).text
    assert html.count('href="/o/standaard/leden/') >= 120 and "data-paginate" in html
    assert "data-paginate" in client.get("/o/standaard/donaties", headers=BEHEERDER).text
