"""Fase 3: organisatie aanmelden, uitnodigingen, rolbeheer en e-maillimiet."""

import re
from datetime import timedelta

import pytest
from sqlalchemy import select
from test_users import add_org, grant

from ledenadmin.auth.principal import Identity
from ledenadmin.db import utcnow
from ledenadmin.domain.enums import Role
from ledenadmin.domain.errors import BusinessRuleError, ConflictError
from ledenadmin.domain.models import Category, Invitation, Member, Membership, Organization
from ledenadmin.services.invitation_service import InvitationService, accept_invitation
from ledenadmin.services.kvk_service import FormatOnlyLookup, KvkResult, normalize_kvk
from ledenadmin.services.mail_service import Mail, MailService, RecordingTransport
from ledenadmin.services.organization_service import (
    NewOrganization,
    OrganizationService,
    slugify,
)
from ledenadmin.services.user_service import UserService
from ledenadmin.tenancy import as_platform
from ledenadmin.web.security import CSRF_COOKIE


def nobody(user: str) -> dict[str, str]:
    """Headers voor een dev-gebruiker zonder rollen uit het token."""
    return {"X-Dev-User": user, "X-Dev-Roles": ""}


def csrf(client, headers) -> str:
    client.get("/aanmelden", headers=headers)
    return client.cookies[CSRF_COOKIE]


def user_for(session, name: str):
    return UserService(as_platform(session)).upsert(
        Identity("dev", name, name, f"{name}@dev.local")
    )


class NotFoundLookup:
    def lookup(self, kvk_number: str) -> KvkResult:
        return KvkResult(found=False, verified=True)


class VerifiedLookup:
    def lookup(self, kvk_number: str) -> KvkResult:
        return KvkResult(found=True, name="Officieel", city="Utrecht", verified=True)


# ── Organisatie aanmelden ────────────────────────────────────────────────────


def test_slugify() -> None:
    assert slugify("Stichting Ashab al-Jannah!") == "stichting-ashab-al-jannah"
    assert slugify("Café Één") == "cafe-een"
    assert slugify("!!!") == "stichting"
    assert normalize_kvk("1234 56.78") == "12345678"


def test_create_organization_makes_creator_beheerder(database) -> None:
    with database.session() as session:
        user = user_for(session, "oprichter")
        org = OrganizationService(session, VerifiedLookup()).create(
            user, NewOrganization("Stichting Noord", "11112222", "info@noord.nl")
        )
        roles = session.scalars(
            select(Membership.role).where(Membership.organization_id == org.id)
        ).all()
        assert org.slug == "stichting-noord"
        assert org.city == "Utrecht"
        assert org.kvk_verified_at is not None
        assert roles == ["beheerder"]


def test_slug_collision_gets_suffix(database) -> None:
    add_org(database, "stichting-noord")
    with database.session() as session:
        user = user_for(session, "oprichter")
        org = OrganizationService(session, FormatOnlyLookup()).create(
            user, NewOrganization("Stichting Noord", "11112222", "info@noord.nl")
        )
        assert org.slug == "stichting-noord-2"
        assert org.kvk_verified_at is None


@pytest.mark.parametrize("kvk", ["1234567", "abcdefgh", "123456789"])
def test_invalid_kvk_is_rejected(database, kvk) -> None:
    with database.session() as session:
        user = user_for(session, "oprichter")
        with pytest.raises(BusinessRuleError, match="8 cijfers"):
            OrganizationService(session, FormatOnlyLookup()).create(
                user, NewOrganization("X", kvk, "a@b.nl")
            )


def test_unknown_kvk_is_rejected(database) -> None:
    with database.session() as session:
        user = user_for(session, "oprichter")
        with pytest.raises(BusinessRuleError, match="niet gevonden"):
            OrganizationService(session, NotFoundLookup()).create(
                user, NewOrganization("X", "11112222", "a@b.nl")
            )


def test_duplicate_kvk_points_to_existing_beheerder(database) -> None:
    add_org(database, "bestaand", kvk="11112222")
    with database.session() as session:
        user = user_for(session, "oprichter")
        with pytest.raises(ConflictError, match="beheerder"):
            OrganizationService(session, FormatOnlyLookup()).create(
                user, NewOrganization("X", "11112222", "a@b.nl")
            )


def test_creation_limits(database) -> None:
    with database.session() as session:
        user = user_for(session, "oprichter")
        service = OrganizationService(session, FormatOnlyLookup(), max_per_user=2)
        first = service.create(user, NewOrganization("Een", "10000001", "a@b.nl"))
        with pytest.raises(BusinessRuleError, match="24 uur"):
            service.create(user, NewOrganization("Twee", "10000002", "a@b.nl"))
        first.created_at = utcnow() - timedelta(days=2)
        session.commit()
        service.create(user, NewOrganization("Twee", "10000002", "a@b.nl"))
        with pytest.raises(BusinessRuleError, match="maximaal 2"):
            service.create(user, NewOrganization("Drie", "10000003", "a@b.nl"))


def test_signup_web_flow(client, database) -> None:
    headers = nobody("nieuw")
    html = client.get("/", headers=headers).text
    assert 'href="/aanmelden"' in html
    response = client.post(
        "/aanmelden",
        data={
            "name": "Stichting Zuid",
            "kvk_number": "22223333",
            "city": "Breda",
            "contact_email": "info@zuid.nl",
            "csrf_token": csrf(client, headers),
        },
        headers=headers,
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/o/stichting-zuid/"
    page = client.get("/o/stichting-zuid/gebruikers", headers=headers)
    assert page.status_code == 200
    assert "nieuw@dev.local" in page.text
    with database.session() as session:
        org_id = as_platform(session).scalar(
            select(Organization.id).where(Organization.slug == "stichting-zuid")
        )
    with database.session(org_id) as session:
        assert session.scalars(select(Category)).first() is not None


def test_signup_shows_errors(client) -> None:
    headers = nobody("nieuw")
    response = client.post(
        "/aanmelden",
        data={
            "name": "X",
            "kvk_number": "12",
            "contact_email": "a@b.nl",
            "csrf_token": csrf(client, headers),
        },
        headers=headers,
    )
    assert response.status_code == 422
    assert "8 cijfers" in response.text


# ── Uitnodigingen ────────────────────────────────────────────────────────────


@pytest.fixture
def org_id(database) -> int:
    org = add_org(database, "stichting-c")
    grant(database, "baas", org, Role.BEHEERDER)
    return org


def invite(database, org: int, email: str, role: Role = Role.PENNINGMEESTER, member_id=None):
    with database.session() as session:
        return (
            InvitationService(as_platform(session), org)
            .create(email, role, "baas", member_id)
            .token
        )


def test_accept_invitation_grants_role(database, org_id) -> None:
    token = invite(database, org_id, "Penning@Dev.Local")
    with database.session() as session:
        user = user_for(session, "penning")
        assert accept_invitation(session, token, user).id == org_id
        assert UserService(session).roles_in(user, org_id) == {Role.PENNINGMEESTER}
        with pytest.raises(BusinessRuleError, match="ongeldig"):
            accept_invitation(session, token, user)


def test_invitation_requires_matching_email(database, org_id) -> None:
    token = invite(database, org_id, "iemand@anders.nl")
    with database.session() as session:
        with pytest.raises(BusinessRuleError, match="iemand@anders.nl"):
            accept_invitation(session, token, user_for(session, "penning"))


def test_expired_and_revoked_invitations(database, org_id) -> None:
    token = invite(database, org_id, "penning@dev.local")
    with database.session() as session:
        as_platform(session)
        invitation = session.scalar(select(Invitation))
        invitation.expires_at = utcnow() - timedelta(minutes=1)
        session.commit()
        with pytest.raises(BusinessRuleError, match="verlopen"):
            accept_invitation(session, token, user_for(session, "penning"))
    token = invite(database, org_id, "penning@dev.local")
    with database.session() as session:
        service = InvitationService(as_platform(session), org_id)
        service.revoke(service.open_invitations()[0].id)
        with pytest.raises(BusinessRuleError):
            accept_invitation(session, token, user_for(session, "penning"))


def test_token_is_stored_hashed(database, org_id) -> None:
    token = invite(database, org_id, "x@y.nl")
    with database.session() as session:
        stored = as_platform(session).scalar(select(Invitation.token_hash))
        assert token not in stored and len(stored) == 64


def test_member_invitation_links_member(database, org_id) -> None:
    with database.session(org_id) as session:
        member = Member(name="Lid Een", email="lid@dev.local")
        session.add(member)
        session.commit()
        member_id = member.id
    with database.session() as session:
        with pytest.raises(BusinessRuleError):
            InvitationService(as_platform(session), org_id).create("lid@dev.local", Role.LID, "b")
    token = invite(database, org_id, "lid@dev.local", Role.LID, member_id)
    with database.session() as session:
        user = user_for(session, "lid")
        accept_invitation(session, token, user)
        membership = session.scalar(select(Membership).where(Membership.user_id == user.id))
        assert (membership.role, membership.member_id) == ("lid", member_id)


def test_last_beheerder_cannot_be_removed(database, org_id) -> None:
    with database.session() as session:
        service = InvitationService(as_platform(session), org_id)
        only = session.scalar(select(Membership).where(Membership.organization_id == org_id))
        with pytest.raises(BusinessRuleError, match="minstens één beheerder"):
            service.remove_role(only.id)
    grant(database, "tweede", org_id, Role.BEHEERDER)
    with database.session() as session:
        InvitationService(as_platform(session), org_id).remove_role(only.id)


def test_invite_and_accept_via_web(client, database, org_id) -> None:
    baas = nobody("baas")
    response = client.post(
        "/o/stichting-c/gebruikers/uitnodigen",
        data={
            "email": "penning@dev.local",
            "role": "penningmeester",
            "csrf_token": csrf(client, baas),
        },
        headers=baas,
    )
    assert response.status_code == 200
    link = re.search(r"http://[^\"]+/uitnodiging/[\w-]+", response.text).group(0)
    path = link.split("8000", 1)[1]

    penning = nobody("penning")
    assert client.get("/o/stichting-c/leden", headers=penning).status_code == 404
    assert "penningmeester" in client.get(path, headers=penning).text
    accepted = client.post(
        path, data={"csrf_token": csrf(client, penning)}, headers=penning, follow_redirects=False
    )
    assert accepted.headers["location"] == "/o/stichting-c/"
    assert client.get("/o/stichting-c/donaties", headers=penning).status_code == 200
    assert client.get("/o/stichting-c/gebruikers", headers=penning).status_code == 403


def test_users_page_is_beheerder_only_and_scoped(client, database, org_id) -> None:
    other = add_org(database, "stichting-d")
    grant(database, "baas", other, Role.PENNINGMEESTER)
    assert client.get("/o/stichting-d/gebruikers", headers=nobody("baas")).status_code == 403
    assert "Gebruikers" in client.get("/o/stichting-c/leden", headers=nobody("baas")).text


# ── E-mail ───────────────────────────────────────────────────────────────────


def test_mail_daily_limit(database) -> None:
    transport = RecordingTransport()
    with database.session() as session:
        mail = MailService(as_platform(session), transport, daily_limit=5)
        for _ in range(4):
            assert mail.send(Mail("a@b.nl", "s", "t"))
        assert mail.quota().warning and not mail.quota().exhausted
        assert mail.send(Mail("a@b.nl", "s", "t"))
        assert mail.quota().exhausted
        assert not mail.send(Mail("a@b.nl", "s", "t"))
    assert len(transport.sent) == 5


def test_invitation_mail_is_sent_when_configured(client, database, org_id) -> None:
    transport = RecordingTransport()
    client.app.state.mail_transport = transport
    baas = nobody("baas")
    response = client.post(
        "/o/stichting-c/gebruikers/uitnodigen",
        data={"email": "p@x.nl", "role": "bestuurder", "csrf_token": csrf(client, baas)},
        headers=baas,
    )
    assert "per e-mail verstuurd" in response.text
    assert transport.sent[0].to == "p@x.nl"
    assert "/uitnodiging/" in transport.sent[0].text
