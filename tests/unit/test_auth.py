import base64
import json

import pytest
from pydantic import ValidationError
from starlette.requests import Request

from ledenadmin.auth.principal import Identity, Principal, parse_roles
from ledenadmin.auth.providers import DevAuthProvider, EasyAuthProvider, build_auth_provider
from ledenadmin.config import AuthMode, Settings
from ledenadmin.domain.enums import Permission, Role


def request_with(headers: dict[str, str]) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    return Request({"type": "http", "headers": raw})


def easyauth_header(claims: list[dict], **extra) -> str:
    payload = {"auth_typ": "aad", "claims": claims, **extra}
    return base64.b64encode(json.dumps(payload).encode()).decode()


def test_easyauth_reads_name_and_app_roles() -> None:
    header = easyauth_header(
        [
            {"typ": "roles", "val": "Penningmeester"},
            {"typ": "roles", "val": "onbekend"},
            {"typ": "name", "val": "Fatma"},
            {"typ": "iss", "val": "https://login.example/t"},
            {"typ": "oid", "val": "abc-123"},
            {"typ": "email", "val": "fatma@example.nl"},
        ]
    )

    identity = EasyAuthProvider().authenticate(request_with({"X-MS-CLIENT-PRINCIPAL": header}))

    assert identity == Identity(
        "https://login.example/t",
        "abc-123",
        "Fatma",
        "fatma@example.nl",
        frozenset({Role.PENNINGMEESTER}),
    )
    assert identity.key == "https://login.example/t|abc-123"


def test_easyauth_supports_role_typ_and_name_header() -> None:
    role_typ = "http://schemas.microsoft.com/ws/2008/06/identity/claims/role"
    header = easyauth_header(
        [{"typ": role_typ, "val": "bestuurder"}, {"typ": "sub", "val": "s1"}], role_typ=role_typ
    )

    identity = EasyAuthProvider().authenticate(
        request_with({"X-MS-CLIENT-PRINCIPAL": header, "X-MS-CLIENT-PRINCIPAL-NAME": "a@b.nl"})
    )

    assert identity.name == "a@b.nl"
    assert identity.claimed_roles == {Role.BESTUURDER}


@pytest.mark.parametrize(
    ("claims", "expected"),
    [
        ([{"typ": "email", "val": "a@b.nl"}, {"typ": "email_verified", "val": "true"}], "a@b.nl"),
        ([{"typ": "email", "val": "a@b.nl"}, {"typ": "email_verified", "val": "False"}], None),
        ([{"typ": "emails", "val": "a@b.nl"}], "a@b.nl"),
        ([{"typ": "preferred_username", "val": "gebruikersnaam"}], None),
    ],
)
def test_easyauth_only_uses_verified_email(claims, expected) -> None:
    header = easyauth_header([{"typ": "sub", "val": "s1"}, *claims])

    identity = EasyAuthProvider().authenticate(request_with({"X-MS-CLIENT-PRINCIPAL": header}))

    assert identity.email == expected


def test_easyauth_login_url_is_configurable() -> None:
    settings = Settings(auth_mode=AuthMode.EASYAUTH, easyauth_login_url="/.auth/login/extern")
    assert build_auth_provider(settings).login_url == "/.auth/login/extern"


def test_easyauth_without_subject_is_anonymous() -> None:
    header = easyauth_header([{"typ": "name", "val": "x"}])

    assert EasyAuthProvider().authenticate(request_with({"X-MS-CLIENT-PRINCIPAL": header})) is None


@pytest.mark.parametrize("headers", [{}, {"X-MS-CLIENT-PRINCIPAL": "%%%geen-base64"}])
def test_easyauth_without_valid_header_is_anonymous(headers) -> None:
    assert EasyAuthProvider().authenticate(request_with(headers)) is None


def test_dev_provider_defaults_and_header_override() -> None:
    provider = DevAuthProvider("dev", "beheerder")

    assert provider.authenticate(request_with({})).claimed_roles == {Role.BEHEERDER}
    override = provider.authenticate(request_with({"X-Dev-User": "b", "X-Dev-Roles": "bestuurder"}))
    assert override == Identity("dev", "b", "b", "b@dev.local", frozenset({Role.BESTUURDER}))
    assert provider.authenticate(request_with({"X-Dev-Roles": ""})).claimed_roles == frozenset()


def test_role_permissions() -> None:
    bestuurder = Principal("b", parse_roles(["bestuurder"]))
    penningmeester = Principal("p", parse_roles(["penningmeester"]))
    beheerder = Principal("h", parse_roles(["beheerder"]))

    assert bestuurder.can(Permission.REPORTS_READ)
    assert not bestuurder.can(Permission.MEMBERS_READ)
    assert not bestuurder.can(Permission.REPORTS_MEMBER_READ)
    assert penningmeester.can(Permission.DONATIONS_WRITE)
    assert not penningmeester.can(Permission.MEMBERS_WRITE)
    assert beheerder.permissions == frozenset(Permission)
    assert not penningmeester.can(Permission.CATEGORIES_WRITE)
    assert not bestuurder.can(Permission.CATEGORIES_WRITE)
    lid = Principal("l", parse_roles(["lid"]))
    assert lid.permissions == {Permission.SELF_READ, Permission.SELF_DONATE}


def test_dev_auth_is_refused_in_production() -> None:
    with pytest.raises(ValidationError, match="AUTH_MODE=dev"):
        Settings(_env_file=None, app_env="production", auth_mode=AuthMode.DEV)


def test_sqlite_is_refused_in_production_unless_explicitly_allowed() -> None:
    with pytest.raises(ValidationError, match="SQLite"):
        Settings(_env_file=None, app_env="production")
    assert Settings(_env_file=None, app_env="production", allow_sqlite_in_production=True)


def test_build_auth_provider_defaults_to_easyauth() -> None:
    assert isinstance(build_auth_provider(Settings(_env_file=None)), EasyAuthProvider)
