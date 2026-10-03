import base64
import binascii
import json
import logging
from typing import Protocol

from starlette.requests import Request

from ledenadmin.auth.principal import Identity, parse_roles
from ledenadmin.config import AuthMode, Settings

logger = logging.getLogger(__name__)

EASYAUTH_PRINCIPAL_HEADER = "x-ms-client-principal"
EASYAUTH_NAME_HEADER = "x-ms-client-principal-name"
DEV_USER_HEADER = "x-dev-user"
DEV_ROLES_HEADER = "x-dev-roles"
EASYAUTH_IDP_HEADER = "x-ms-client-principal-idp"
DEV_ISSUER = "dev"
# Entra zet het object-id in 'oid' of de lange claimnaam; andere providers gebruiken 'sub'.
SUBJECT_CLAIMS = (
    "http://schemas.microsoft.com/identity/claims/objectidentifier",
    "oid",
    "sub",
    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier",
)
EMAIL_CLAIMS = (
    "email",
    "emails",
    "preferred_username",
    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
)
EMAIL_VERIFIED_CLAIM = "email_verified"


class AuthProvider(Protocol):
    login_url: str | None

    def authenticate(self, request: Request) -> Identity | None: ...


class EasyAuthProvider:
    """Leest de identiteit die Azure Container Apps/App Service-authenticatie (Easy Auth) zet.

    Vertrouw deze headers alleen achter Easy Auth: het platform overschrijft ze bij elke
    request, zodat clients ze niet zelf kunnen meesturen.
    """

    def __init__(self, role_claim_type: str = "roles", login_url: str = "/.auth/login/aad") -> None:
        self._role_claim_type = role_claim_type
        self.login_url = login_url

    def authenticate(self, request: Request) -> Identity | None:
        raw = request.headers.get(EASYAUTH_PRINCIPAL_HEADER)
        if not raw:
            return None
        try:
            payload = json.loads(base64.b64decode(raw, validate=False))
        except (binascii.Error, ValueError):
            logger.warning("Ongeldige Easy Auth principal-header ontvangen")
            return None

        claims = payload.get("claims") or []

        def claim(*types: str) -> str | None:
            return next(
                (c.get("val") for c in claims if c.get("typ") in types and c.get("val")), None
            )

        role_types = {self._role_claim_type, payload.get("role_typ")}
        roles = parse_roles(c.get("val", "") for c in claims if c.get("typ") in role_types)
        subject = claim(*SUBJECT_CLAIMS)
        if not subject:
            logger.warning("Easy Auth principal zonder subject-claim ontvangen")
            return None
        issuer = claim("iss") or request.headers.get(EASYAUTH_IDP_HEADER) or "onbekend"
        email = claim(*EMAIL_CLAIMS)
        # Een expliciet niet-geverifieerd e-mailadres telt niet: het koppelt uitnodigingen.
        if (claim(EMAIL_VERIFIED_CLAIM) or "").lower() == "false" or "@" not in (email or ""):
            email = None
        name = (
            request.headers.get(EASYAUTH_NAME_HEADER)
            or claim(payload.get("name_typ") or "name", "name")
            or email
            or "onbekend"
        )
        return Identity(issuer, subject, name, email, roles)


class DevAuthProvider:
    """Alleen voor lokale ontwikkeling en tests; geweigerd als APP_ENV=production."""

    login_url = None

    def __init__(self, user_name: str, roles: str) -> None:
        self._user_name = user_name
        self._roles = parse_roles(roles.split(","))

    def authenticate(self, request: Request) -> Identity | None:
        name = request.headers.get(DEV_USER_HEADER) or self._user_name
        roles_header = request.headers.get(DEV_ROLES_HEADER)
        roles = parse_roles(roles_header.split(",")) if roles_header is not None else self._roles
        return Identity(DEV_ISSUER, name, name, f"{name}@dev.local", roles)


def build_auth_provider(settings: Settings) -> AuthProvider:
    if settings.auth_mode == AuthMode.DEV:
        logger.warning("AUTH_MODE=dev actief: authenticatie is uitgeschakeld (alleen lokaal!)")
        return DevAuthProvider(settings.dev_user_name, settings.dev_user_roles)
    return EasyAuthProvider(settings.role_claim_type, settings.easyauth_login_url)
