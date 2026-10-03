from collections.abc import Callable, Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from ledenadmin.auth.errors import NotAuthenticatedError, PermissionDeniedError
from ledenadmin.auth.principal import Principal
from ledenadmin.config import Settings
from ledenadmin.container import ServiceContainer
from ledenadmin.domain.enums import Permission


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_session(request: Request) -> Iterator[Session]:
    # Fase 1: één organisatie per installatie; vanaf fase 2 bepaald door URL en lidmaatschap.
    with request.app.state.database.session(request.app.state.organization_id) as session:
        yield session


def get_services(
    request: Request, session: Annotated[Session, Depends(get_session)]
) -> ServiceContainer:
    return ServiceContainer(session, request.app.state.settings, request.app.state.insights)


def get_principal(request: Request) -> Principal:
    principal = request.app.state.auth_provider.authenticate(request)
    if principal is None:
        raise NotAuthenticatedError()
    request.state.principal = principal
    return principal


def require(permission: Permission) -> Callable[..., Principal]:
    def dependency(principal: Annotated[Principal, Depends(get_principal)]) -> Principal:
        if not principal.can(permission):
            raise PermissionDeniedError()
        return principal

    return dependency


Services = Annotated[ServiceContainer, Depends(get_services)]
CurrentPrincipal = Annotated[Principal, Depends(get_principal)]
