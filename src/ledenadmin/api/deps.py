from collections.abc import Callable, Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ledenadmin.auth.errors import NotAuthenticatedError, PermissionDeniedError
from ledenadmin.auth.principal import Identity, Principal
from ledenadmin.config import Settings
from ledenadmin.container import ServiceContainer
from ledenadmin.domain.enums import OrganizationStatus, Permission
from ledenadmin.domain.errors import NotFoundError
from ledenadmin.domain.models import Organization
from ledenadmin.services.user_service import UserService
from ledenadmin.tenancy import as_platform

ORG_PARAM = "org"
KVK_LENGTH = 8


class OrganizationRedirect(Exception):
    """Organisatie opgevraagd via KVK-nummer; stuur door naar de URL met de slug."""

    def __init__(self, location: str) -> None:
        self.location = location


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_identity(request: Request) -> Identity:
    identity = request.app.state.auth_provider.authenticate(request)
    if identity is None:
        raise NotAuthenticatedError()
    request.state.identity = identity
    return identity


def _not_found() -> NotFoundError:
    # Bewust dezelfde melding voor 'bestaat niet', 'geblokkeerd' en 'geen toegang'.
    return NotFoundError("Organisatie niet gevonden")


def _load_organization(request: Request) -> Organization | None:
    """De organisatie uit het pad `/o/{org}/...`, of None voor routes zonder organisatie."""
    key = request.path_params.get(ORG_PARAM)
    if key is None:
        return None
    if hasattr(request.state, "organization"):
        return request.state.organization
    with request.app.state.database.session() as session:
        as_platform(session)
        organization = session.scalar(select(Organization).where(Organization.slug == key))
        if organization is None and key.isdigit() and len(key) == KVK_LENGTH:
            by_kvk = session.scalar(select(Organization).where(Organization.kvk_number == key))
            if by_kvk is not None and by_kvk.status == OrganizationStatus.ACTIVE:
                prefix = request.url.path.split(f"/o/{key}", 1)
                rest = prefix[1] if len(prefix) == 2 else ""
                query = f"?{request.url.query}" if request.url.query else ""
                raise OrganizationRedirect(f"{prefix[0]}/o/{by_kvk.slug}{rest}{query}")
        if organization is None or organization.status != OrganizationStatus.ACTIVE:
            raise _not_found()
        session.expunge(organization)
    request.state.organization = organization
    return organization


def get_principal(request: Request) -> Principal:
    existing = getattr(request.state, "principal", None)
    if existing is not None:
        return existing
    identity = get_identity(request)
    organization = _load_organization(request)
    with request.app.state.database.session() as session:
        as_platform(session)
        principal = UserService(session, request.app.state.settings.superadmins).principal(
            identity, organization
        )
    if organization is not None and not principal.roles:
        raise _not_found()
    request.state.principal = principal
    return principal


def get_session(
    request: Request, principal: Annotated[Principal, Depends(get_principal)]
) -> Iterator[Session]:
    if principal.organization_id is None:  # pragma: no cover - programmeerfout
        raise RuntimeError("Sessie gevraagd buiten een organisatie")
    with request.app.state.database.session(principal.organization_id) as session:
        yield session


def get_services(
    request: Request, session: Annotated[Session, Depends(get_session)]
) -> ServiceContainer:
    return ServiceContainer(session, request.app.state.settings, request.app.state.insights)


def require(permission: Permission) -> Callable[..., Principal]:
    def dependency(principal: Annotated[Principal, Depends(get_principal)]) -> Principal:
        if not principal.can(permission):
            raise PermissionDeniedError()
        return principal

    return dependency


def require_superadmin(principal: Annotated[Principal, Depends(get_principal)]) -> Principal:
    if not principal.is_superadmin:
        raise PermissionDeniedError()
    return principal


Services = Annotated[ServiceContainer, Depends(get_services)]
CurrentPrincipal = Annotated[Principal, Depends(get_principal)]
CurrentIdentity = Annotated[Identity, Depends(get_identity)]
Superadmin = Annotated[Principal, Depends(require_superadmin)]
