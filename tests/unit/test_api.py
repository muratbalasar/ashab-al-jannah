from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from ledenadmin.config import AuthMode, Settings
from ledenadmin.main import create_app

BESTUURDER = {"X-Dev-Roles": "bestuurder"}
BEHEERDER = {"X-Dev-Roles": "beheerder"}


def sub_id(client: TestClient, category: str, name: str) -> int:
    categories = client.get("/o/standaard/api/v1/categories").json()
    category_entry = next(c for c in categories if c["name"] == category)
    return next(s["id"] for s in category_entry["subcategories"] if s["name"] == name)


def create_member(client: TestClient, name="Jan Jansen", email="jan@example.nl") -> dict:
    response = client.post("/o/standaard/api/v1/members", json={"name": name, "email": email})
    assert response.status_code == 201, response.text
    return response.json()


def create_donation(client: TestClient, member_id: int, amount="50.00", headers=None, **extra):
    body = {
        "member_id": member_id,
        "subcategory_id": sub_id(client, "Sponsoring", "MKB"),
        "amount": amount,
        **extra,
    }
    return client.post("/o/standaard/api/v1/donations", json=body, headers=headers)


def test_health_is_public(settings, database) -> None:
    easyauth = settings.model_copy(update={"auth_mode": AuthMode.EASYAUTH})
    with TestClient(create_app(easyauth, database)) as client:
        assert client.get("/api/v1/health").json()["status"] == "healthy"
        assert client.get("/o/standaard/api/v1/members").status_code == 401


def test_me_returns_roles_and_permissions(client) -> None:
    me = client.get("/o/standaard/api/v1/me", headers=BESTUURDER).json()

    assert me["roles"] == ["bestuurder"]
    assert "reports:read" in me["permissions"]


def test_member_crud_and_validation(client) -> None:
    member = create_member(client)

    assert (
        client.get(f"/o/standaard/api/v1/members/{member['id']}").json()["email"]
        == "jan@example.nl"
    )
    assert (
        client.post(
            "/o/standaard/api/v1/members", json={"name": "X", "email": "JAN@example.nl"}
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/o/standaard/api/v1/members", json={"name": "X", "email": "geen-mail"}
        ).status_code
        == 422
    )
    patched = client.patch(
        f"/o/standaard/api/v1/members/{member['id']}", json={"status": "inactief"}
    )
    assert patched.json()["status"] == "inactief"
    assert (
        client.get("/o/standaard/api/v1/members", params={"status": "inactief"}).json()[0]["id"]
        == member["id"]
    )
    assert client.get("/o/standaard/api/v1/members/999").status_code == 404


def test_member_endpoints_require_permissions(client) -> None:
    assert client.get("/o/standaard/api/v1/members", headers=BESTUURDER).status_code == 403
    response = client.post(
        "/o/standaard/api/v1/members",
        json={"name": "X", "email": "x@y.nl"},
        headers={"X-Dev-Roles": "penningmeester"},
    )
    assert response.status_code == 403


def test_register_donation(client) -> None:
    member = create_member(client)

    response = create_donation(client, member["id"], description="Kassa")

    assert response.status_code == 201
    body = response.json()
    assert body["amount"] == "50.00"
    assert body["category"] == "Sponsoring" and body["subcategory"] == "MKB"
    assert (
        client.get(f"/o/standaard/api/v1/donations/{body['id']}").json()["description"] == "Kassa"
    )
    assert len(client.get(f"/o/standaard/api/v1/members/{member['id']}/donations").json()) == 1


@pytest.mark.parametrize(
    ("member_id", "amount", "expected"),
    [(999, "10", 422), (None, "0", 422), (None, "1.234", 422)],
)
def test_invalid_donation_is_not_stored(client, member_id, amount, expected) -> None:
    member = create_member(client)

    response = create_donation(client, member_id or member["id"], amount)

    assert response.status_code == expected
    assert client.get("/o/standaard/api/v1/donations").json() == []


def test_beheerder_can_do_everything(client) -> None:
    member = create_member(client)

    assert create_donation(client, member["id"], headers=BEHEERDER).status_code == 201
    assert (
        client.post("/o/standaard/api/v1/insights", json={}, headers=BEHEERDER).status_code == 200
    )
    assert (
        client.get("/o/standaard/api/v1/reports/export.csv", headers=BEHEERDER).status_code == 200
    )


def test_report_hides_member_details_for_bestuurder(client) -> None:
    member = create_member(client)
    create_donation(client, member["id"])

    full = client.get("/o/standaard/api/v1/reports/summary").json()
    limited = client.get("/o/standaard/api/v1/reports/summary", headers=BESTUURDER).json()

    assert full["by_member"][0]["label"] == "Jan Jansen"
    assert limited["total"] == full["total"] == "50.00"
    assert limited["by_member"] == [] and limited["donations"] == []
    filtered = client.get(
        "/o/standaard/api/v1/reports/summary",
        params={"member_id": member["id"]},
        headers=BESTUURDER,
    )
    assert filtered.status_code == 403


def test_report_rejects_end_before_start(client) -> None:
    params = {"start_date": "2026-02-02", "end_date": "2026-02-01"}

    response = client.get("/o/standaard/api/v1/reports/summary", params=params)

    assert response.status_code == 422
    assert "einddatum" in response.text


def test_member_report(client) -> None:
    member = create_member(client)
    other = create_member(client, "Piet", "piet@example.nl")
    create_donation(client, member["id"], "10")
    create_donation(client, other["id"], "20")

    report = client.get(f"/o/standaard/api/v1/reports/members/{member['id']}").json()

    assert report["total"] == "10.00"
    assert client.get("/o/standaard/api/v1/reports/members/999").status_code == 404


def test_csv_export_neutralizes_formulas(client) -> None:
    member = create_member(client, '=HYPERLINK("x")', "evil@example.nl")
    create_donation(client, member["id"], "12.5")

    response = client.get("/o/standaard/api/v1/reports/export.csv")

    assert response.headers["content-type"].startswith("text/csv")
    text = response.content.decode("utf-8-sig")
    assert text.splitlines()[0].startswith("donatie_id;datum;lid_id;lid_naam")
    assert "\"'=HYPERLINK" in text and ";12,50;" in text
    assert (
        client.get("/o/standaard/api/v1/reports/export.csv", headers=BESTUURDER).status_code == 403
    )


def test_insight_endpoint(client) -> None:
    member = create_member(client)
    create_donation(client, member["id"])

    insight = client.post("/o/standaard/api/v1/insights", json={}, headers=BESTUURDER).json()

    assert insight["provider"] == "lokaal" and "€ 50,00" in insight["text"]


def test_categories_management(client) -> None:
    created = client.post(
        "/o/standaard/api/v1/categories", json={"name": "Evenementen"}, headers=BEHEERDER
    )
    assert created.status_code == 201
    category_id = created.json()["id"]
    sub = client.post(
        f"/o/standaard/api/v1/categories/{category_id}/subcategories",
        json={"name": "Iftar"},
        headers=BEHEERDER,
    )
    assert sub.status_code == 201
    assert (
        client.post("/o/standaard/api/v1/categories", json={"name": "Evenementen"}).status_code
        == 409
    )
    for role in ("bestuurder", "penningmeester"):
        response = client.post(
            "/o/standaard/api/v1/categories", json={"name": "X"}, headers={"X-Dev-Roles": role}
        )
        assert response.status_code == 403, role


def test_update_category_and_subcategory(client) -> None:
    category_id = client.post(
        "/o/standaard/api/v1/categories", json={"name": "Evenementen"}
    ).json()["id"]
    sub_url = f"/o/standaard/api/v1/categories/{category_id}/subcategories"
    sub_id_ = client.post(sub_url, json={"name": "Iftar"}).json()["id"]

    renamed = client.patch(
        f"/o/standaard/api/v1/categories/{category_id}",
        json={"name": "Activiteiten"},
        headers=BEHEERDER,
    )
    assert renamed.json()["name"] == "Activiteiten"
    assert renamed.json()["is_active"] is True
    sub = client.patch(f"{sub_url}/{sub_id_}", json={"name": "Iftar 2026", "is_active": False})
    assert sub.json() == {"id": sub_id_, "name": "Iftar 2026", "is_active": False}

    deactivated = client.patch(
        f"/o/standaard/api/v1/categories/{category_id}", json={"is_active": False}
    )
    assert deactivated.json()["name"] == "Activiteiten"
    names = [c["name"] for c in client.get("/o/standaard/api/v1/categories").json()]
    assert "Activiteiten" not in names
    all_names = [
        c["name"] for c in client.get("/o/standaard/api/v1/categories?include_inactive=true").json()
    ]
    assert "Activiteiten" in all_names


def test_update_category_errors(client) -> None:
    contributie_sub = sub_id(client, "Contributie", "Jaarlijks")
    sponsoring = next(
        c for c in client.get("/o/standaard/api/v1/categories").json() if c["name"] == "Sponsoring"
    )

    assert (
        client.patch(
            f"/o/standaard/api/v1/categories/{sponsoring['id']}", json={"name": "Donatie"}
        ).status_code
        == 409
    )
    assert (
        client.patch(
            f"/o/standaard/api/v1/categories/{sponsoring['id']}", json={"name": ""}
        ).status_code
        == 422
    )
    assert (
        client.patch("/o/standaard/api/v1/categories/999", json={"is_active": False}).status_code
        == 404
    )
    wrong_parent = (
        f"/o/standaard/api/v1/categories/{sponsoring['id']}/subcategories/{contributie_sub}"
    )
    assert client.patch(wrong_parent, json={"is_active": False}).status_code == 404
    assert (
        client.patch(
            f"/o/standaard/api/v1/categories/{sponsoring['id']}",
            json={"is_active": False},
            headers={"X-Dev-Roles": "penningmeester"},
        ).status_code
        == 403
    )


def test_inactive_subcategory_rejects_new_donations(client) -> None:
    member = create_member(client)
    sponsoring = next(
        c for c in client.get("/o/standaard/api/v1/categories").json() if c["name"] == "Sponsoring"
    )
    mkb = sub_id(client, "Sponsoring", "MKB")
    client.patch(
        f"/o/standaard/api/v1/categories/{sponsoring['id']}/subcategories/{mkb}",
        json={"is_active": False},
    )

    assert create_donation(client, member["id"]).status_code == 422


@pytest.fixture
def production_client(database) -> Iterator[TestClient]:
    settings = Settings(
        _env_file=None,
        database_url="sqlite://",
        app_env="production",
        allow_sqlite_in_production=True,
    )
    with TestClient(create_app(settings, database), base_url="https://testserver") as client:
        yield client


def test_production_sets_secure_cookie_and_requires_login(production_client) -> None:
    response = production_client.get("/o/standaard/leden", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"].startswith("/.auth/login/aad?post_login_redirect_uri=")
    assert "secure" in response.headers["set-cookie"].lower()
