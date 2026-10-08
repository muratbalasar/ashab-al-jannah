from fastapi import APIRouter
from pydantic import BaseModel

from ledenadmin import __version__
from ledenadmin.api.deps import CurrentPrincipal

router = APIRouter(tags=["systeem"])
public_router = APIRouter(tags=["systeem"])


class Health(BaseModel):
    status: str
    version: str


class Me(BaseModel):
    name: str
    organization_id: int | None
    roles: list[str]
    permissions: list[str]


@public_router.get("/health", response_model=Health)
def health() -> Health:
    return Health(status="healthy", version=__version__)


@router.get("/me", response_model=Me)
def me(principal: CurrentPrincipal) -> Me:
    return Me(
        name=principal.name,
        organization_id=principal.organization_id,
        roles=sorted(principal.roles),
        permissions=sorted(principal.permissions),
    )
