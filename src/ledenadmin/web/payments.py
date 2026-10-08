"""Online doneren: Mollie-instellingen (beheerder), doneren (lid) en de webhook van Mollie."""

from decimal import Decimal, InvalidOperation
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from ledenadmin.api.deps import Services, require
from ledenadmin.auth.principal import Principal
from ledenadmin.domain.enums import OrganizationStatus, Permission
from ledenadmin.domain.errors import DomainError, NotFoundError
from ledenadmin.domain.models import Organization
from ledenadmin.services.payment_service import MollieError, PaymentService
from ledenadmin.tenancy import as_platform
from ledenadmin.web.routes import redirect, render
from ledenadmin.web.security import verify_csrf

org_router = APIRouter(dependencies=[Depends(verify_csrf)], include_in_schema=False)
# Zonder CSRF en zonder login: Mollie roept dit aan. De status wordt altijd bij Mollie opgehaald.
webhook_router = APIRouter(include_in_schema=False)

CanManageOrganization = Annotated[Principal, Depends(require(Permission.ORGANIZATION_MANAGE))]
CanDonate = Annotated[Principal, Depends(require(Permission.SELF_DONATE))]
FormText = Annotated[str, Form()]
STATUS_TEXT = {
    "paid": "Hartelijk dank! Uw donatie is ontvangen.",
    "open": "De betaling is nog niet afgerond.",
    "pending": "De betaling wordt verwerkt. U ziet de donatie zo spoedig mogelijk.",
    "authorized": "De betaling wordt verwerkt.",
    "canceled": "De betaling is geannuleerd.",
    "expired": "De betaling is verlopen.",
    "failed": "De betaling is mislukt.",
}


def payment_service(request: Request, session, organization: Organization) -> PaymentService:
    state = request.app.state
    return PaymentService(session, organization, state.mollie_api, state.secret_box)


def online_enabled(request: Request) -> bool:
    organization = getattr(request.state, "organization", None)
    return bool(
        organization is not None
        and organization.mollie_api_key_encrypted
        and request.app.state.secret_box.enabled
    )


# ── Instellingen (beheerder) ─────────────────────────────────────────────────


def _settings(request: Request, errors=None, status_code=200) -> Response:
    organization = request.state.organization
    with request.app.state.database.session(organization.id) as session:
        mode = payment_service(request, session, organization).mode
    context = {
        "errors": errors or {},
        "grace_days": 30,
        "mollie_mode": mode,
        "mollie_available": request.app.state.secret_box.enabled,
    }
    return render(request, "organizations/settings.html", context, status_code)


@org_router.post("/instellingen/mollie")
def mollie_save(request: Request, _: CanManageOrganization, api_key: FormText = "") -> Response:
    organization = request.state.organization
    with request.app.state.database.session() as session:
        stored = as_platform(session).get(Organization, organization.id)
        try:
            payment_service(request, session, stored).set_api_key(stored, api_key)
        except DomainError as exc:
            return _settings(request, {exc.field or "__all__": exc.message}, 422)
        session.commit()
        organization.mollie_api_key_encrypted = stored.mollie_api_key_encrypted
    return redirect(request, "/instellingen?melding=mollie-gekoppeld")


@org_router.post("/instellingen/mollie/ontkoppelen")
def mollie_remove(request: Request, _: CanManageOrganization) -> Response:
    organization = request.state.organization
    with request.app.state.database.session() as session:
        as_platform(session).get(Organization, organization.id).mollie_api_key_encrypted = None
        session.commit()
    organization.mollie_api_key_encrypted = None
    return redirect(request, "/instellingen?melding=mollie-ontkoppeld")


# ── Doneren (lid) ────────────────────────────────────────────────────────────


@org_router.post("/mijn/doneren")
def donate(
    request: Request,
    services: Services,
    principal: CanDonate,
    amount: FormText = "",
    subcategory_id: FormText = "",
) -> Response:
    if principal.member_id is None:
        raise NotFoundError("Uw account is niet gekoppeld aan een lid")
    organization = request.state.organization
    try:
        value = Decimal(amount.replace(",", ".").strip())
    except InvalidOperation:
        value = Decimal(0)
    service = payment_service(request, services.session, organization)
    try:
        checkout = service.start(
            principal.member_id,
            int(subcategory_id) if subcategory_id.isdigit() else 0,
            value,
            request.app.state.settings.public_base_url,
            principal.name,
        )
    except DomainError as exc:
        return redirect(request, f"/mijn?fout={exc.field or 'algemeen'}")
    return RedirectResponse(checkout, status_code=303)


@org_router.get("/mijn/betaling/{payment_id}")
def payment_return(
    request: Request, payment_id: int, services: Services, principal: CanDonate
) -> Response:
    if principal.member_id is None:
        raise NotFoundError("Betaling niet gevonden")
    service = payment_service(request, services.session, request.state.organization)
    payment = service.get_for_member(payment_id, principal.member_id)
    try:
        # Ook zonder (bereikbare) webhook de status bijwerken.
        service.refresh(payment)
    except MollieError:
        pass
    context = {"payment": payment, "message": STATUS_TEXT.get(payment.status, payment.status)}
    return render(request, "my/payment.html", context)


# ── Webhook ──────────────────────────────────────────────────────────────────


@webhook_router.post("/betalingen/webhook/{slug}")
async def webhook(request: Request, slug: str) -> Response:
    form = await request.form()
    mollie_id = form.get("id")
    # Altijd 200 voor onbekende verzoeken: niets prijsgeven over wat wel bestaat.
    if not isinstance(mollie_id, str) or not mollie_id.startswith("tr_"):
        return Response(status_code=200)
    database = request.app.state.database
    with database.session() as session:
        organization = as_platform(session).scalar(
            select(Organization).where(Organization.slug == slug)
        )
        if organization is None or organization.status == OrganizationStatus.DELETED:
            return Response(status_code=200)
        session.expunge(organization)
    with database.session(organization.id) as session:
        service = payment_service(request, session, organization)
        payment = service.by_mollie_id(mollie_id)
        if payment is not None:
            try:
                service.refresh(payment)
            except MollieError:
                # Mollie probeert het later opnieuw bij een andere status dan 200.
                return Response(status_code=503)
    return Response(status_code=200)
