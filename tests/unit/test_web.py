import re

from factories import add_member

from ledenadmin.domain.enums import MemberStatus
from ledenadmin.domain.models import Member


def test_pages_render_with_security_headers(client) -> None:
    pages = ("/", "/leden", "/leden/nieuw", "/donaties", "/donaties/nieuw", "/rapportage")
    for path in (*pages, "/categorieen"):
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


def test_members_list_shows_total_count_when_filtered(client, session) -> None:
    add_member(session, name="Actief lid", email="actief@x.nl")
    inactive_member = add_member(session, name="Inactief lid", email="inactief@x.nl")
    inactive_member.status = MemberStatus.INACTIVE
    session.commit()

    html = client.get("/leden?status=actief", headers=BEHEERDER).text

    assert "Gevonden leden: <strong>1</strong>" in html
    assert "Totaal aantal leden: <strong>2</strong>" in client.get("/leden", headers=BEHEERDER).text
    partial = client.get("/leden?q=inactief", headers=BEHEERDER | {"HX-Request": "true"}).text
    assert 'hx-swap-oob="true">Gevonden leden: <strong>1</strong>' in partial


def test_navigation_follows_role(client) -> None:
    html = client.get("/", headers={"X-Dev-Roles": "bestuurder"}).text

    assert 'href="/rapportage"' in html
    assert 'href="/leden"' not in html
    assert client.get("/leden", headers={"X-Dev-Roles": "bestuurder"}).status_code == 403


def test_home_redirects_to_report(client) -> None:
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/rapportage"
    assert "<h1>Rapportage</h1>" in client.get("/").text


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


def test_report_accepts_and_shows_dutch_dates(client) -> None:
    default = client.get("/rapportage").text
    dutch = client.get("/rapportage?start_date=1-2-2026&end_date=28-02-2026").text
    invalid = client.get("/rapportage?start_date=31-02-2026")

    assert re.search(r'id="start_date"[^>]*value="01-01-\d{4}"', default)
    assert re.search(r'id="start_date"[^>]*type="text"', default)
    assert 'placeholder="dd-mm-jjjj"' in default
    assert "01-02-2026 t/m 28-02-2026" in dutch
    assert 'value="01-02-2026"' in dutch and 'value="28-02-2026"' in dutch
    assert "Vul een geldige begindatum in (dd-mm-jjjj)." in invalid.text


def test_donation_form_uses_dutch_datetime(csrf_client, session) -> None:
    member = add_member(session)
    form = csrf_client.get("/donaties/nieuw").text
    sub_id = re.search(r'<option value="(\d+)" >Sponsoring – MKB', form).group(1)

    assert re.search(r'id="donated_at"[^>]*value="\d{2}-\d{2}-\d{4} \d{2}:\d{2}"', form)
    response = csrf_client.post(
        "/donaties",
        data={
            "member_id": str(member.id),
            "subcategory_id": sub_id,
            "amount": "10",
            "donated_at": "14-02-2026 10:30",
            "csrf_token": csrf_client.csrf,
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "14-02-2026 10:30" in csrf_client.get("/donaties").text


def test_ai_analysis_partial(csrf_client) -> None:
    response = csrf_client.post(
        "/rapportage/ai",
        data={"start_date": "2020-01-01", "end_date": "2020-01-31"},
        headers={"X-CSRF-Token": csrf_client.csrf, "HX-Request": "true"},
    )

    assert response.status_code == 200
    assert "Onvoldoende gegevens" in response.text


BEHEERDER = {"X-Dev-Roles": "beheerder"}


def category_id(client, name: str) -> int:
    categories = client.get("/api/v1/categories", params={"include_inactive": True}).json()
    return next(c["id"] for c in categories if c["name"] == name)


def test_categories_page_only_for_beheerder(client) -> None:
    assert 'href="/categorieen"' in client.get("/", headers=BEHEERDER).text
    for role in ("penningmeester", "bestuurder"):
        headers = {"X-Dev-Roles": role}
        assert 'href="/categorieen"' not in client.get("/", headers=headers).text
        assert client.get("/categorieen", headers=headers).status_code == 403


def test_create_category_and_subcategory_via_form(csrf_client) -> None:
    response = csrf_client.post(
        "/categorieen",
        data={"name": " Evenementen ", "csrf_token": csrf_client.csrf},
        headers=BEHEERDER,
        follow_redirects=False,
    )
    assert response.status_code == 303
    new_id = category_id(csrf_client, "Evenementen")
    assert response.headers["location"].endswith(f"#categorie-{new_id}")

    response = csrf_client.post(
        f"/categorieen/{new_id}/subcategorieen",
        data={"name": "Iftar", "csrf_token": csrf_client.csrf},
        headers=BEHEERDER,
    )
    assert "De subcategorie is opgeslagen." in response.text
    assert '<span class="cat-name">Iftar</span>' in response.text


def test_category_form_errors_stay_with_their_form(csrf_client) -> None:
    sponsoring = category_id(csrf_client, "Sponsoring")

    duplicate = csrf_client.post(
        f"/categorieen/{sponsoring}",
        data={"name": "Donatie", "csrf_token": csrf_client.csrf},
        headers=BEHEERDER,
    )
    empty = csrf_client.post(
        "/categorieen", data={"name": "", "csrf_token": csrf_client.csrf}, headers=BEHEERDER
    )

    assert duplicate.status_code == 409
    assert "Categorie &#39;Donatie&#39; bestaat al" in duplicate.text
    assert duplicate.text.count('aria-invalid="true"') == 1
    assert f'id="cat-{sponsoring}-naam"' in duplicate.text
    assert 'value="Donatie"' in duplicate.text
    assert empty.status_code == 422
    assert "Vul een naam in (maximaal 100 tekens)." in empty.text


def test_rows_show_names_and_open_one_edit_form_on_request(client) -> None:
    sponsoring = category_id(client, "Sponsoring")

    overview = client.get("/categorieen", headers=BEHEERDER).text
    editing = client.get(
        f"/categorieen?bewerk=cat-{sponsoring}", headers={**BEHEERDER, "HX-Request": "true"}
    ).text

    assert '<h2 class="cat-name">Sponsoring</h2>' in overview
    assert f'id="cat-{sponsoring}-naam"' not in overview
    assert "<html" not in editing
    assert editing.count('name="name"') == 2  # nieuwe categorie + het geopende formulier
    assert f'id="cat-{sponsoring}-naam"' in editing and "autofocus" in editing


def test_htmx_actions_return_only_the_management_block(csrf_client) -> None:
    sponsoring = category_id(csrf_client, "Sponsoring")
    htmx = {**BEHEERDER, "HX-Request": "true", "X-CSRF-Token": csrf_client.csrf}

    toggled = csrf_client.post(
        f"/categorieen/{sponsoring}/status", data={"is_active": "false"}, headers=htmx
    )
    invalid = csrf_client.post(
        f"/categorieen/{sponsoring}/subcategorieen", data={"name": " "}, headers=htmx
    )

    assert toggled.status_code == 200
    assert toggled.text.lstrip().startswith('<div id="categorie-beheer"')
    assert 'Sponsoring <span class="inactive-tag">inactief</span>' in toggled.text
    assert invalid.status_code == 422 and "<html" not in invalid.text
    assert f'id="nieuw-{sponsoring}-naam"' in invalid.text
    assert "Vul een naam in (maximaal 100 tekens)." in invalid.text


def test_deactivate_category_hides_it_from_donation_form(csrf_client) -> None:
    sponsoring = category_id(csrf_client, "Sponsoring")

    response = csrf_client.post(
        f"/categorieen/{sponsoring}/status",
        data={"is_active": "false", "csrf_token": csrf_client.csrf},
        headers=BEHEERDER,
    )

    assert 'aria-label="Sponsoring activeren"' in response.text
    assert "Sponsoring – MKB" not in csrf_client.get("/donaties/nieuw").text


def test_rename_and_deactivate_subcategory_via_form(csrf_client) -> None:
    sponsoring = category_id(csrf_client, "Sponsoring")
    mkb = next(
        s["id"]
        for c in csrf_client.get("/api/v1/categories").json()
        for s in c["subcategories"]
        if c["id"] == sponsoring and s["name"] == "MKB"
    )
    action = f"/categorieen/{sponsoring}/subcategorieen/{mkb}"

    csrf_client.post(
        action, data={"name": "Bedrijven", "csrf_token": csrf_client.csrf}, headers=BEHEERDER
    )
    csrf_client.post(
        f"{action}/status",
        data={"is_active": "false", "csrf_token": csrf_client.csrf},
        headers=BEHEERDER,
    )

    form = csrf_client.get("/donaties/nieuw").text
    assert "Sponsoring – MKB" not in form and "Sponsoring – Bedrijven" not in form
    assert "Sponsoring – Particulier" in form


def test_member_pickers_have_search_and_list_all_members(client, session) -> None:
    session.add_all(
        Member(name=f"Lid {n:04d}", email=f"lid{n}@example.nl", status=MemberStatus.ACTIVE)
        for n in range(600)
    )
    session.commit()
    session.add(Member(name="Ayşe Öztürk", email="ayse@example.nl"))
    session.commit()

    for path in ("/rapportage", "/donaties/nieuw"):
        html = client.get(path).text
        assert 'data-member-search="member_id"' in html, path
        assert html.count('data-zoek="lid') == 600, path
        assert 'data-zoek="ayse@example.nl"' in html and "Ayşe Öztürk (" in html, path


def test_report_preselects_member_from_link(client, session) -> None:
    member = add_member(session)

    html = client.get(f"/rapportage?member_id={member.id}").text

    assert f'<option value="{member.id}" data-zoek="jan@example.nl" selected>' in html


def test_report_offers_pdf_export_with_print_header(client, session) -> None:
    from datetime import UTC, datetime

    from ledenadmin.dummy_data import seed

    seed(session, now=datetime(2026, 6, 30, tzinfo=UTC))

    html = client.get("/rapportage?start_date=01-01-2025&end_date=30-06-2026").text
    empty = client.get("/rapportage?start_date=01-01-2000&end_date=31-12-2000").text

    assert "data-print-report" in html and "Exporteer PDF" in html
    assert 'class="print-only print-head"' in html
    assert "<p data-print-filters>Periode 01-01-2025 t/m 30-06-2026</p>" in html
    assert "data-print-report" not in empty


def test_delete_button_only_for_unused_and_delete_works(csrf_client, session) -> None:
    from datetime import UTC, datetime

    from factories import add_donation, subcategory

    add_donation(session, add_member(session), "10", datetime(2026, 1, 1, tzinfo=UTC))
    mkb = subcategory(session, "Sponsoring", "MKB")
    particulier = subcategory(session, "Sponsoring", "Particulier")
    html = csrf_client.get("/categorieen", headers=BEHEERDER).text

    assert f'id="verwijder-sub-{mkb.id}"' not in html
    assert f'id="verwijder-cat-{mkb.category_id}"' not in html
    assert f'id="verwijder-sub-{particulier.id}"' in html
    assert "hx-confirm=" in html

    base = f"/categorieen/{mkb.category_id}/subcategorieen"
    data = {"csrf_token": csrf_client.csrf}
    hx = {**BEHEERDER, "HX-Request": "true"}
    refused = csrf_client.post(f"{base}/{mkb.id}/verwijderen", data=data, headers=hx)
    deleted = csrf_client.post(f"{base}/{particulier.id}/verwijderen", data=data, headers=hx)

    assert refused.status_code == 409 and "al gebruikt bij donaties" in refused.text
    assert deleted.status_code == 200 and "Verwijderd." in deleted.text
    assert "Particulier" not in deleted.text
    api = csrf_client.delete(f"/api/v1/categories/{category_id(csrf_client, 'Donatie')}")
    assert api.status_code == 204
    other = csrf_client.delete(
        f"/api/v1/categories/{mkb.category_id}", headers={"X-Dev-Roles": "penningmeester"}
    )
    assert other.status_code == 403


def test_beheerder_can_bulk_delete_donations(csrf_client, session) -> None:
    from datetime import UTC, datetime

    from factories import add_donation

    member = add_member(session)
    ids = [
        add_donation(session, member, str(n), datetime(2026, 1, n, tzinfo=UTC)).id
        for n in (1, 2, 3)
    ]
    html = csrf_client.get("/donaties", headers=BEHEERDER).text
    assert "data-select-all" in html and html.count("data-select-row") == 3
    for role in ("penningmeester", "bestuurder"):
        headers = {"X-Dev-Roles": role}
        if role == "penningmeester":
            assert "data-select-row" not in csrf_client.get("/donaties", headers=headers).text
        refused = csrf_client.post(
            "/donaties/verwijderen",
            data={"ids": ids, "csrf_token": csrf_client.csrf},
            headers=headers,
        )
        assert refused.status_code == 403

    response = csrf_client.post(
        "/donaties/verwijderen",
        data={"ids": ids[:2], "csrf_token": csrf_client.csrf},
        headers=BEHEERDER,
    )

    assert "2 donaties zijn verwijderd." in response.text
    assert response.text.count("data-select-row") == 1
    assert csrf_client.delete(f"/api/v1/donations/{ids[2]}").status_code == 204
    assert csrf_client.delete(f"/api/v1/donations/{ids[2]}").status_code == 404
    assert "Geen donaties gevonden." in csrf_client.get("/donaties").text
    bogus = csrf_client.get("/donaties?melding=donaties-verwijderd&aantal=<b>").text
    assert "donaties zijn verwijderd" not in bogus


def test_beheerder_can_bulk_delete_members_with_donations(csrf_client, session) -> None:
    from datetime import UTC, datetime

    from factories import add_donation
    from sqlalchemy import func, select

    from ledenadmin.domain.models import Donation, Member

    a = add_member(session, name="Lid A", email="a@x.nl")
    b = add_member(session, name="Lid B", email="b@x.nl")
    keep = add_member(session, name="Lid C", email="c@x.nl")
    for member in (a, a, b, keep):
        add_donation(session, member, "10", datetime(2026, 1, 1, tzinfo=UTC))

    html = csrf_client.get("/leden", headers=BEHEERDER).text
    assert "data-select-all" in html and html.count("data-select-row") == 3
    data = {"ids": [a.id, b.id], "csrf_token": csrf_client.csrf}
    for role in ("penningmeester", "bestuurder"):
        headers = {"X-Dev-Roles": role}
        assert "data-select-row" not in csrf_client.get("/leden", headers=headers).text
        refused = csrf_client.post("/leden/verwijderen", data=data, headers=headers)
        assert refused.status_code == 403

    response = csrf_client.post("/leden/verwijderen", data=data, headers=BEHEERDER)

    assert "2 leden zijn verwijderd, samen met 3 donatie(s)." in response.text
    session.expire_all()
    assert session.scalar(select(func.count(Member.id))) == 1
    assert session.scalar(select(func.count(Donation.id))) == 1
    assert csrf_client.delete(f"/api/v1/members/{keep.id}").status_code == 204
    assert csrf_client.delete(f"/api/v1/members/{keep.id}").status_code == 404
    assert session.scalar(select(func.count(Donation.id))) == 0


def test_donations_list_filters_on_member(client, session) -> None:
    from datetime import UTC, datetime

    from factories import add_donation

    a = add_member(session, name="Filter A", email="fa@x.nl")
    b = add_member(session, name="Filter B", email="fb@x.nl")
    add_donation(session, a, "10", datetime(2026, 1, 1, tzinfo=UTC))
    add_donation(session, b, "20", datetime(2026, 1, 2, tzinfo=UTC))

    html = client.get(f"/donaties?member_id={a.id}", headers=BEHEERDER).text
    assert 'data-member-search="member_id"' in html
    assert html.count('href="/leden/') == 1 and "€ 10,00" in html and "€ 20,00" not in html
    assert "Gevonden donaties: <strong>1</strong>" in html
    detail = client.get(f"/leden/{a.id}", headers=BEHEERDER).text
    assert "Totaal aantal donaties: <strong>1</strong>" in detail and "meest recente" not in detail
    assert "Totaal aantal donaties: <strong>2</strong>" in client.get("/donaties").text
    assert client.get("/donaties?member_id=x", headers=BEHEERDER).text.count("data-select-row") == 2
