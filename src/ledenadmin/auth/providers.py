import base64
import binascii
import json
import logging
from typing import Protocol

from starlette.requests import Request

from ledenadmin.auth.principal import Principal, parse_roles
from ledenadmin.config import AuthMode, Settings

logger = logging.getLogger(__name__)

EASYAUTH_PRINCIPAL_HEADER = "x-ms-client-principal"
EASYAUTH_NAME_HEADER = "x-ms-client-principal-name"
DEV_USER_HEADER = "x-dev-user"
DEV_ROLES_HEADER = "x-dev-roles"


class AuthProvider(Protocol):
    login_url: str | None

    def authenticate(self, request: Request) -> Principal | None: ...


class EasyAuthProvider:
    """Leest de identiteit die Azure Container Apps/App Service-authenticatie (Easy Auth) zet.

    Vertrouw deze headers alleen achter Easy Auth: het platform overschrijft ze bij elke
    request, zodat clients ze niet zelf kunnen meesturen.
    """

    login_url = "/.auth/login/aad"

    def __init__(self, role_claim_type: str = "roles") -> None:
        self._role_claim_type = role_claim_type

    def authenticate(self, request: Request) -> Principal | None:
        raw = request.headers.get(EASYAUTH_PRINCIPAL_HEADER)
        if not raw:
            return None
        try:
            payload = json.loads(base64.b64decode(raw, validate=False))
        except (binascii.Error, ValueError):
            logger.warning("Ongeldige Easy Auth principal-header ontvangen")
            return None

        claims = payload.get("claims") or []
        role_types = {self._role_claim_type, payload.get("role_typ")}
        name_type = payload.get("name_typ")
        roles = parse_roles(c.get("val", "") for c in claims if c.get("typ") in role_types)
        name = request.headers.get(EASYAUTH_NAME_HEADER) or next(
            (c.get("val") for c in claims if c.get("typ") in (name_type, "name")), "onbekend"
        )
        return Principal(name=name, roles=roles)


class DevAuthProvider:
    """Alleen voor lokale ontwikkeling en tests; geweigerd als APP_ENV=production."""

    login_url = None

    def __init__(self, user_name: str, roles: str) -> None:
        self._user_name = user_name
        self._roles = parse_roles(roles.split(","))

    def authenticate(self, request: Request) -> Principal | None:
        name = request.headers.get(DEV_USER_HEADER) or self._user_name
        roles_header = request.headers.get(DEV_ROLES_HEADER)
        roles = parse_roles(roles_header.split(",")) if roles_header is not None else self._roles
        return Principal(name=name, roles=roles)


def build_auth_provider(settings: Settings) -> AuthProvider:
    if settings.auth_mode == AuthMode.DEV:
        logger.warning("AUTH_MODE=dev actief: authenticatie is uitgeschakeld (alleen lokaal!)")
        return DevAuthProvider(settings.dev_user_name, settings.dev_user_roles)
    return EasyAuthProvider(settings.role_claim_type)
