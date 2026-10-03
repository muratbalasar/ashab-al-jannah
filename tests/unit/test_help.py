"""Help-pagina: alleen onderdelen die bij de rechten van de gebruiker passen."""

from test_my import add_member, link_lid
from test_users import add_org, grant

from ledenadmin.domain.enums import Role


def test_help_per_role(client, database) -> None:
    org = add_org(database, "stichting-h")
    grant(database, "baas", org, Role.BEHEERDER)
    grant(database, "penning", org, Role.PENNINGMEESTER)
    link_lid(database, org, add_member(database, org, "Eigen Lid"))

    def page(user):
        response = client.get(
            "/o/stichting-h/help", headers={"X-Dev-User": user, "X-Dev-Roles": ""}
        )
        assert response.status_code == 200
        return response.text

    lid = page("lid")
    assert 'id="lid"' in lid and 'id="start"' in lid
    assert 'id="instellingen"' not in lid and 'id="donaties"' not in lid

    penning = page("penning")
    assert 'id="donaties"' in penning and 'id="instellingen"' not in penning

    baas = page("baas")
    for anchor in ("leden", "donaties", "gebruikers", "instellingen"):
        assert f'id="{anchor}"' in baas
    assert 'id="platform"' not in baas
    assert 'href="/o/stichting-h/help"' in baas
