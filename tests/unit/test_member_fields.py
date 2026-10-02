import pytest

from ledenadmin.services.member_field_service import (
    FieldType,
    MemberFieldService,
    is_sensitive_label,
    looks_like_bsn,
    normalize,
)

BEHEERDER = {"X-Dev-Roles": "beheerder"}


@pytest.mark.parametrize(
    "label",
    ["BSN", "bsn-nummer", "Burgerservicenummer", "Sofi nummer", "Paspoortnummer", "Religie",
     "Medische info", "ID-kaart nr", "Wachtwoord"],
)  # fmt: skip
def test_sensitive_labels_are_blocked(label: str) -> None:
    assert is_sensitive_label(label)


@pytest.mark.parametrize("label", ["Telefoon", "IBAN", "Nieuwsbrief", "Adres", "Huisnummer"])
def test_normal_labels_are_allowed(label: str) -> None:
    assert not is_sensitive_label(label)


def test_normalize_per_type() -> None:
    assert normalize(FieldType.IBAN, "nl91abna0417164300") == "NL91 ABNA 0417 1643 00"
    assert normalize(FieldType.MOBILE, "+31 6 1234 5678") == "0612345678"
    assert normalize(FieldType.MOBILE, "06-12345678") == "0612345678"
    assert normalize(FieldType.NUMBER, "12,5") == "12,5"
    assert normalize(FieldType.BOOLEAN, "ja") == "ja"
    assert normalize(FieldType.BOOLEAN, "") == ""
    assert normalize(FieldType.TEXT, "  ") == ""
    for field_type, value in [
        (FieldType.IBAN, "NL91ABNA0417164301"),
        (FieldType.MOBILE, "0201234567"),
        (FieldType.NUMBER, "abc"),
    ]:
        with pytest.raises(ValueError):
            normalize(field_type, value)


def test_bsn_value_is_blocked() -> None:
    assert looks_like_bsn("111222333") and looks_like_bsn("1112.22.333")
    assert not looks_like_bsn("123456789")
    with pytest.raises(ValueError, match="BSN"):
        normalize(FieldType.NUMBER, "111222333")
    with pytest.raises(ValueError, match="BSN"):
        normalize(FieldType.TEXT, "111 222 333")


def test_admin_manages_fields_and_member_values(csrf_client, session) -> None:
    c = csrf_client
    base = {"csrf_token": c.csrf}
    blocked = c.post("/ledenvelden", data=base | {"label": "BSN", "field_type": "nummer"},
                     headers=BEHEERDER)  # fmt: skip
    assert blocked.status_code == 422 and "AVG" in blocked.text
    for label, kind in [("Telefoon", "mobiel"), ("IBAN", "iban"), ("Nieuwsbrief", "ja_nee")]:
        r = c.post("/ledenvelden", data=base | {"label": label, "field_type": kind},
                   headers=BEHEERDER, follow_redirects=False)  # fmt: skip
        assert r.status_code == 303
    dup = c.post("/ledenvelden", data=base | {"label": "Telefoon", "field_type": "tekst"},
                 headers=BEHEERDER)  # fmt: skip
    assert dup.status_code == 422
    fields = {f.label: f.id for f in MemberFieldService(session).list()}
    tel, iban, news = (f"veld_{fields[k]}" for k in ("Telefoon", "IBAN", "Nieuwsbrief"))

    form = base | {"name": "Ali", "email": "ali@x.nl", "status": "actief"}
    bad = c.post("/leden", data=form | {tel: "123", iban: "NL00XXXX"}, headers=BEHEERDER)
    assert bad.status_code == 422 and "mobiel" in bad.text and "IBAN" in bad.text
    ok = c.post("/leden", data=form | {tel: "06 12345678", iban: "NL91ABNA0417164300", news: "ja"},
                headers=BEHEERDER, follow_redirects=False)  # fmt: skip
    assert ok.status_code == 303
    detail = c.get(ok.headers["location"], headers=BEHEERDER).text
    assert 'value="0612345678"' in detail and "NL91 ABNA 0417 1643 00" in detail
    assert "checked" in detail.split(f'name="{news}"')[1].split(">")[0]

    member_url = ok.headers["location"].split("?")[0]
    c.post(member_url, data=form | {tel: ""}, headers=BEHEERDER)
    assert 'value="0612345678"' not in c.get(member_url, headers=BEHEERDER).text

    r = c.post(f"/ledenvelden/{fields['Telefoon']}/verwijderen", data=base, headers=BEHEERDER,
               follow_redirects=False)  # fmt: skip
    assert r.status_code == 303
    assert "<td>Telefoon</td>" not in c.get("/ledenvelden", headers=BEHEERDER).text


def test_fields_page_only_for_beheerder(client) -> None:
    for role in ("penningmeester", "bestuurder"):
        assert client.get("/ledenvelden", headers={"X-Dev-Roles": role}).status_code == 403
