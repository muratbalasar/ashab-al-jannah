import re

from factories import add_member


def test_pages_render_with_security_headers(client) -> None:
    for path in ("/", "/leden", "/leden/nieuw", "/donaties", "/donaties/nieuw", "/rapportage"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert "default-src 'self'" in response.headers["content-security-policy"]
        assert response.headers["x-frame-options"] == "DENY"


def test_app_name_is_shown_in_title_and_header(client) -> None:
    html = client.get("/leden").text

    assert "<title>Leden – Ashab al-Jannah</title>" in html
    assert "<strong>Ashab al-Jannah</strong>" in html
    assert 'lang="ar" dir="rtl">أَصْحَابُ الْجَنَّةِ<' in html
    assert client.get("/api/openapi.json").json()["info"]["title"].startswith("Ashab al-Jannah")


def test_navigation_follows_role(client) -> None:
    html = client.get("/", headers={"X-Dev-Roles": "bestuurder"}).text

    assert 'href="/rapportage"' in html
    assert 'href="/leden"' not in html
    assert client.get("/leden", headers={"X-Dev-Roles": "bestuurder"}).status_code == 403


def test_post_without_csrf_token_is_rejected(client) -> None:
    response = client.post("/leden", data={"name": "Jan", "email": "jan@example.nl"})

    assert response.status_code == 403
    assert "sessie" in response.text


def test_create_member_via_form(csrf_client) -> None:
    response = csrf_client.post(
        "/leden",
        data={"name": "Jan Jansen", "email": "jan@example.nl", "csrf_token": csrf_client.csrf},
        follow_redirects=False,
    )

    assert response.status_code == 303
    detail = csrf_client.get(response.headers["location"])
    assert "Het lid is aangemaakt." in detail.text
    assert "jan@example.nl" in detail.text


def test_invalid_member_form_shows_dutch_errors(csrf_client) -> None:
    response = csrf_client.post(
        "/leden", data={"name": "", "email": "fout", "csrf_token": csrf_client.csrf}
    )

    assert response.status_code == 422
    assert "Vul een naam in" in response.text
    assert "Vul een geldig e-mailadres in." in response.text
    assert 'aria-invalid="true"' in response.text


def test_update_member_to_inactive_via_form(csrf_client, session) -> None:
    member = add_member(session)

    response = csrf_client.post(
        f"/leden/{member.id}",
        data={
            "name": member.name,
            "email": member.email,
            "status": "inactief",
            "csrf_token": csrf_client.csrf,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "Inactief" in csrf_client.get("/leden?status=inactief").text


def test_register_donation_with_dutch_amount(csrf_client, session) -> None:
    member = add_member(session)
    form = csrf_client.get(f"/donaties/nieuw?member_id={member.id}").text
    sub_id = re.search(r'<option value="(\d+)" >Sponsoring – MKB', form).group(1)

    response = csrf_client.post(
        "/donaties",
        data={
            "member_id": str(member.id),
            "subcategory_id": sub_id,
            "amount": "€ 1.234,50",
            "donated_at": "2026-02-14T10:30",
            "csrf_token": csrf_client.csrf,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    listing = csrf_client.get("/donaties?melding=donatie-geregistreerd").text
    assert "€ 1.234,50" in listing and "14-02-2026 10:30" in listing


def test_invalid_donation_form_keeps_values(csrf_client, session) -> None:
    member = add_member(session)

    response = csrf_client.post(
        "/donaties",
        data={"member_id": str(member.id), "amount": "0", "csrf_token": csrf_client.csrf},
    )

    assert response.status_code == 422
    assert "Kies een categorie en subcategorie." in response.text


def test_report_partial_and_empty_state(client) -> None:
    response = client.get(
        "/rapportage?start_date=2020-01-01&end_date=2020-12-31", headers={"HX-Request": "true"}
    )

    assert "<html" not in response.text
    assert "Geen gegevens voor deze periode." in response.text
    assert "<canvas" not in response.text


def test_report_shows_validation_error(client) -> None:
    response = client.get("/rapportage?start_date=2026-02-02&end_date=2026-02-01")

    assert "De einddatum mag niet vóór de begindatum liggen" in response.text


def test_ai_analysis_partial(csrf_client) -> None:
    response = csrf_client.post(
        "/rapportage/ai",
        data={"start_date": "2020-01-01", "end_date": "2020-01-31"},
        headers={"X-CSRF-Token": csrf_client.csrf, "HX-Request": "true"},
    )

    assert response.status_code == 200
    assert "Onvoldoende gegevens" in response.text
