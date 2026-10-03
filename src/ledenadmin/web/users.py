"""Gebruikersbeheer binnen een organisatie, aanmelden van organisaties en uitnodigingen."""

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ledenadmin.api.deps import CurrentIdentity, require
from ledenadmin.auth.principal import Principal
from ledenadmin.db import utcnow
from ledenadmin.domain.enums import Permission, Role
from ledenadmin.domain.errors import DomainError, NotFoundError
from ledenadmin.domain.models import Invitation, Member, Organization
from ledenadmin.services.category_service import CategoryService
from ledenadmin.services.invitation_service import (
    INVALID_LINK,
    InvitationService,
    accept_invitation,
    find_open_invitation,
)
from ledenadmin.services.mail_service import Mail, MailService
from ledenadmin.services.organization_data_service import OrganizationDataService
from ledenadmin.services.organization_service import NewOrganization, OrganizationService
from ledenadmin.services.user_service import UserService
from ledenadmin.tenancy import as_platform
from ledenadmin.web.routes import redirect, render
from ledenadmin.web.security import verify_csrf

org_router = APIRouter(dependencies=[Depends(verify_csrf)], include_in_schema=False)
public_router = APIRouter(dependencies=[Depends(verify_csrf)], include_in_schema=False)

CanManageUsers = Annotated[Principal, Depends(require(Permission.USERS_MANAGE))]
FormText = Annotated[str, Form()]
INVITABLE_ROLES = (Role.BEHEERDER, Role.PENNINGMEESTER, Role.BESTUURDER)
ROLE_LABELS = {
    Role.BEHEERDER.value: "Beheerder",
    Role.PENNINGMEESTER.value: "Penningmeester",
    Role.BESTUURDER.value: "Bestuurder",
    Role.LID.value: "Lid",
}


def mail_service(request: Request, session: Session) -> MailService:
    settings = request.app.state.settings
    return MailService(session, request.app.state.mail_transport, settings.mail_daily_limit)


def invitation_link(request: Request, token: str) -> str:
    return f"{request.app.state.settings.public_base_url.rstrip('/')}/uitnodiging/{token}"


# ── Gebruikers van de organisatie ────────────────────────────────────────────


def _users_page(
    request: Request,
    session: Session,
    link: str | None = None,
    mailed: bool = False,
    errors: dict[str, str] | None = None,
    values: dict[str, str] | None = None,
    status_code: int = 200,
) -> Response:
    organization = request.state.organization
    service = InvitationService(session, organization.id)
    mail = mail_service(request, session)
    context = {
        "users": service.users(),
        "invitations": service.open_invitations(),
        "roles": INVITABLE_ROLES,
        "role_labels": ROLE_LABELS,
        "link": link,
        "mailed": mailed,
        "mail_enabled": mail.enabled,
        "mail_quota": mail.quota(),
        "errors": errors or {},
        "values": values or {},
    }
    return render(request, "users/index.html", context, status_code)


def _platform_session(request: Request):
    return request.app.state.database.session()


@org_router.get("/gebruikers")
def users_index(request: Request, _: CanManageUsers) -> Response:
    with _platform_session(request) as session:
        return _users_page(request, as_platform(session))


def _send_invitation(
    request: Request, session: Session, email: str, token: str, role_label: str
) -> bool:
    organization = request.state.organization
    link = invitation_link(request, token)
    text = (
        f"U bent uitgenodigd als {role_label.lower()} van {organization.name}.\n\n"
        f"Open deze link en meld u aan met {email}:\n{link}\n\n"
        "De link is 7 dagen geldig en kan één keer worden gebruikt."
    )
    return mail_service(request, session).send(
        Mail(to=email, subject=f"Uitnodiging voor {organization.name}", text=text)
    )


@org_router.post("/gebruikers/uitnodigen")
def users_invite(
    request: Request,
    principal: CanManageUsers,
    email: FormText = "",
    role: FormText = "",
    member_id: FormText = "",
) -> Response:
    with _platform_session(request) as session:
        as_platform(session)
        values = {"email": email, "role": role}
        try:
            chosen = Role(role)
        except ValueError:
            return _users_page(
                request, session, errors={"role": "Kies een rol."}, values=values, status_code=422
            )
        service = InvitationService(session, request.state.organization.id)
        try:
            created = service.create(
                email, chosen, principal.name, int(member_id) if member_id.isdigit() else None
            )
        except DomainError as exc:
            if not member_id:
                return _users_page(
                    request,
                    session,
                    errors={exc.field or "__all__": exc.message},
                    values=values,
                    status_code=422,
                )
            raise
        mailed = _send_invitation(
            request, session, created.invitation.email, created.token, ROLE_LABELS[chosen.value]
        )
        return _users_page(
            request, session, link=invitation_link(request, created.token), mailed=mailed
        )


@org_router.post("/gebruikers/uitnodigingen/{invitation_id}/intrekken")
def users_revoke(request: Request, invitation_id: int, _: CanManageUsers) -> Response:
    with _platform_session(request) as session:
        InvitationService(as_platform(session), request.state.organization.id).revoke(invitation_id)
    return redirect(request, "/gebruikers")


@org_router.post("/gebruikers/rollen/{membership_id}/verwijderen")
def users_remove_role(request: Request, membership_id: int, _: CanManageUsers) -> Response:
    with _platform_session(request) as session:
        as_platform(session)
        try:
            InvitationService(session, request.state.organization.id).remove_role(membership_id)
        except DomainError as exc:
            if isinstance(exc, NotFoundError):
                raise
            return _users_page(request, session, errors={"__all__": exc.message}, status_code=422)
    return redirect(request, "/gebruikers")


@org_router.post("/leden/{member_id}/uitnodigen")
def member_invite(request: Request, member_id: int, principal: CanManageUsers) -> Response:
    """Nodigt een lid uit voor 'Mijn omgeving', op het e-mailadres van het ledenrecord."""
    with _platform_session(request) as session:
        as_platform(session)
        member = session.get(Member, member_id)
        if member is None or member.organization_id != request.state.organization.id:
            raise NotFoundError(f"Lid {member_id} bestaat niet")
        created = InvitationService(session, member.organization_id).create(
            member.email, Role.LID, principal.name, member.id
        )
        mailed = _send_invitation(request, session, member.email, created.token, "lid")
        return _users_page(
            request, session, link=invitation_link(request, created.token), mailed=mailed
        )


# ── Instellingen: export en verwijderen (AVG) ────────────────────────────────

CanManageOrganization = Annotated[Principal, Depends(require(Permission.ORGANIZATION_MANAGE))]
GRACE_DAYS = 30


def _settings_page(request: Request, errors=None, status_code=200) -> Response:
    context = {"errors": errors or {}, "grace_days": GRACE_DAYS}
    return render(request, "organizations/settings.html", context, status_code)


@org_router.get("/instellingen")
def settings_index(request: Request, _: CanManageOrganization) -> Response:
    return _settings_page(request)


@org_router.get("/instellingen/export")
def settings_export(request: Request, _: CanManageOrganization) -> Response:
    organization = request.state.organization
    with _platform_session(request) as session:
        content = OrganizationDataService(session).export(organization.id)
    filename = f"export-{organization.slug}-{utcnow():%Y%m%d}.zip"
    return Response(
        content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@org_router.post("/instellingen/verwijderen")
def settings_delete(request: Request, _: CanManageOrganization, confirm: FormText = "") -> Response:
    organization = request.state.organization
    if confirm.strip() != organization.slug:
        errors = {"confirm": f"Typ precies '{organization.slug}' om te bevestigen."}
        return _settings_page(request, errors, 422)
    with _platform_session(request) as session:
        OrganizationDataService(session).soft_delete(organization.id)
    return RedirectResponse("/?melding=verwijderd", status_code=303)


# ── Organisatie aanmelden ────────────────────────────────────────────────────


def _signup_page(request: Request, values=None, errors=None, status_code=200) -> Response:
    return render(
        request,
        "organizations/new.html",
        {"values": values or {}, "errors": errors or {}},
        status_code,
    )


@public_router.get("/aanmelden")
def signup_form(request: Request, identity: CurrentIdentity) -> Response:
    return _signup_page(request, {"contact_email": identity.email or ""})


@public_router.post("/aanmelden")
def signup(
    request: Request,
    identity: CurrentIdentity,
    name: FormText = "",
    kvk_number: FormText = "",
    city: FormText = "",
    contact_email: FormText = "",
) -> Response:
    settings = request.app.state.settings
    values = {"name": name, "kvk_number": kvk_number, "city": city, "contact_email": contact_email}
    with _platform_session(request) as session:
        as_platform(session)
        user = UserService(session, settings.superadmins).upsert(identity)
        service = OrganizationService(
            session, request.app.state.kvk_lookup, settings.max_organizations_per_user
        )
        try:
            organization = service.create(
                user, NewOrganization(name, kvk_number, contact_email, city or None)
            )
        except DomainError as exc:
            session.rollback()
            return _signup_page(
                request, values, {exc.field or "__all__": exc.message}, status_code=422
            )
        _notify_superadmin(request, session, organization)
        slug, organization_id = organization.slug, organization.id
    if settings.seed_default_categories:
        with request.app.state.database.session(organization_id) as tenant:
            CategoryService(tenant).ensure_defaults()
    return RedirectResponse(f"/o/{slug}/", status_code=303)


def _notify_superadmin(request: Request, session: Session, organization: Organization) -> None:
    recipient = request.app.state.settings.superadmin_email
    if not recipient:
        return
    text = (
        f"Nieuwe organisatie: {organization.name} (KVK {organization.kvk_number}, "
        f"{organization.city or 'plaats onbekend'}).\n"
        f"Contact: {organization.contact_email}\n"
        f"{request.app.state.settings.public_base_url.rstrip('/')}/platform"
    )
    mail_service(request, session).send(
        Mail(to=recipient, subject=f"Nieuwe organisatie: {organization.name}", text=text)
    )


# ── Uitnodiging accepteren ───────────────────────────────────────────────────


def _invitation_page(request: Request, context: dict, status_code: int = 200) -> Response:
    return render(request, "invitations/accept.html", context, status_code)


@public_router.get("/uitnodiging/{token}")
def invitation_show(request: Request, token: str, identity: CurrentIdentity) -> Response:
    with _platform_session(request) as session:
        as_platform(session)
        invitation: Invitation | None = find_open_invitation(session, token)
        if invitation is None:
            return _invitation_page(request, {"error": INVALID_LINK}, 404)
        organization = session.get(Organization, invitation.organization_id)
        context = {
            "token": token,
            "organization_name": organization.name if organization else "",
            "role_label": ROLE_LABELS.get(invitation.role, invitation.role),
            "email": invitation.email,
            "identity_email": identity.email,
        }
    return _invitation_page(request, context)


@public_router.post("/uitnodiging/{token}")
def invitation_accept(request: Request, token: str, identity: CurrentIdentity) -> Response:
    settings = request.app.state.settings
    with _platform_session(request) as session:
        as_platform(session)
        user = UserService(session, settings.superadmins).upsert(identity)
        try:
            organization = accept_invitation(session, token, user)
        except DomainError as exc:
            session.rollback()
            return _invitation_page(request, {"error": exc.message}, 422)
        slug = organization.slug
    return RedirectResponse(f"/o/{slug}/", status_code=303)
