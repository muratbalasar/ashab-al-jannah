"""Routes buiten een organisatie: startpagina (organisatiekeuze) en platformbeheer."""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select

from ledenadmin.api.deps import CurrentIdentity, Superadmin
from ledenadmin.audit import Action
from ledenadmin.domain.enums import OrganizationStatus
from ledenadmin.domain.errors import NotFoundError
from ledenadmin.domain.models import AuditLog, Organization
from ledenadmin.services.organization_data_service import OrganizationDataService
from ledenadmin.services.organization_service import DEFAULT_SLUG
from ledenadmin.services.user_service import UserService
from ledenadmin.tenancy import as_platform
from ledenadmin.web.security import verify_csrf

router = APIRouter(dependencies=[Depends(verify_csrf)], include_in_schema=False)

# Oude URL's van vóór multi-tenant blijven werken via de standaardorganisatie.
LEGACY_PREFIXES = ("leden", "ledenvelden", "donaties", "categorieen", "rapportage", "logboek")


def _render(request: Request, template: str, context: dict, status_code: int = 200) -> Response:
    base = {
        "principal": getattr(request.state, "principal", None),
        "csrf_token": request.state.csrf_token,
        "org": "",
    }
    return request.app.state.templates.TemplateResponse(
        request, template, base | context, status_code=status_code
    )


@router.get("/")
def home(request: Request, identity: CurrentIdentity) -> Response:
    settings = request.app.state.settings
    with request.app.state.database.session() as session:
        as_platform(session)
        users = UserService(session, settings.superadmins)
        default = session.scalar(select(Organization).where(Organization.slug == DEFAULT_SLUG))
        principal = users.principal(identity, default)
        request.state.principal = principal
        organizations = users.organizations(users.upsert(identity))
        session.commit()
        choices = [(o.slug, o.name) for o in organizations]
    if len(choices) == 1 and "melding" not in request.query_params:
        return RedirectResponse(f"/o/{choices[0][0]}/", status_code=303)
    if not choices and principal.is_superadmin:
        return RedirectResponse("/platform", status_code=303)
    deleted = request.query_params.get("melding") == "verwijderd"
    return _render(request, "organizations/choose.html", {"choices": choices, "deleted": deleted})


@router.get("/platform")
def platform(request: Request, principal: Superadmin) -> Response:
    with request.app.state.database.session() as session:
        service = OrganizationDataService(session)
        service.purge_expired()
        organizations = service.overview()
        since = datetime.now(UTC) - timedelta(hours=24)
        errors = as_platform(session).scalar(
            select(func.count(AuditLog.id)).where(
                AuditLog.action.in_((Action.ERROR, Action.CLIENT_ERROR)),
                AuditLog.at >= since,
            )
        )
    context = {
        "organizations": organizations,
        "Status": OrganizationStatus,
        "errors_24h": errors or 0,
    }
    return _render(request, "platform/index.html", context)


@router.post("/platform/{organization_id}/herstellen")
def platform_restore(organization_id: int, _: Superadmin, request: Request) -> Response:
    with request.app.state.database.session() as session:
        OrganizationDataService(session).restore(organization_id)
    return RedirectResponse("/platform", status_code=303)


@router.post("/platform/{organization_id}/wissen")
def platform_purge(organization_id: int, _: Superadmin, request: Request) -> Response:
    with request.app.state.database.session() as session:
        OrganizationDataService(session).purge(organization_id)
    return RedirectResponse("/platform", status_code=303)


@router.post("/platform/{organization_id}/status")
def platform_status(
    organization_id: int,
    _: Superadmin,
    request: Request,
    status: Annotated[str, Form()] = "",
) -> Response:
    if status not in {OrganizationStatus.ACTIVE.value, OrganizationStatus.BLOCKED.value}:
        raise NotFoundError("Onbekende status")
    with request.app.state.database.session() as session:
        as_platform(session)
        organization = session.get(Organization, organization_id)
        if organization is None or organization.status == OrganizationStatus.DELETED:
            raise NotFoundError("Organisatie niet gevonden")
        organization.status = status
        session.commit()
    return RedirectResponse("/platform", status_code=303)


@router.get("/{section}")
@router.get("/{section}/{rest:path}")
def legacy(request: Request, section: str, rest: str = "") -> Response:
    if section not in LEGACY_PREFIXES:
        raise NotFoundError("Pagina niet gevonden")
    query = f"?{request.url.query}" if request.url.query else ""
    path = f"/{section}/{rest}" if rest else f"/{section}"
    return RedirectResponse(f"/o/{DEFAULT_SLUG}{path}{query}", status_code=307)
