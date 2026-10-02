from collections.abc import Callable, Mapping
from datetime import date, datetime
from typing import Annotated, Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ledenadmin import audit
from ledenadmin.api.deps import CurrentPrincipal, Services, get_session, require
from ledenadmin.audit import Action
from ledenadmin.auth.principal import Principal
from ledenadmin.domain.enums import MemberStatus, Permission
from ledenadmin.domain.errors import ConflictError, DomainError
from ledenadmin.schemas.categories import CategoryCreate
from ledenadmin.schemas.donations import DonationCreate, DonationRead
from ledenadmin.schemas.members import MemberCreate, MemberUpdate
from ledenadmin.schemas.reports import Report, ReportFilter
from ledenadmin.services.member_field_service import (
    FIELD_TYPE_LABELS,
    FieldType,
    is_sensitive_label,
)
from ledenadmin.web.dates import nl_date_to_iso, nl_datetime_to_iso
from ledenadmin.web.security import verify_csrf

router = APIRouter(dependencies=[Depends(verify_csrf)], include_in_schema=False)

MESSAGES = {
    "lid-aangemaakt": "Het lid is aangemaakt.",
    "lid-bijgewerkt": "Het lid is bijgewerkt.",
    "lid-verwijderd": "Het lid is verwijderd, samen met {donaties} donatie(s).",
    "leden-verwijderd": "{aantal} leden zijn verwijderd, samen met {donaties} donatie(s).",
    "donatie-geregistreerd": "De donatie is geregistreerd.",
    "donatie-verwijderd": "De donatie is verwijderd.",
    "donaties-verwijderd": "{aantal} donaties zijn verwijderd.",
    "categorie-opgeslagen": "De categorie is opgeslagen.",
    "subcategorie-opgeslagen": "De subcategorie is opgeslagen.",
    "verwijderd": "Verwijderd.",
    "veld-opgeslagen": "Het veld is opgeslagen.",
}

CATEGORY_NAME_ERROR = "Vul een naam in (maximaal 100 tekens)."

FIELD_MESSAGES = {
    "name": "Vul een naam in (maximaal 200 tekens).",
    "email": "Vul een geldig e-mailadres in.",
    "status": "Kies een geldige status.",
    "member_id": "Kies een lid.",
    "subcategory_id": "Kies een categorie en subcategorie.",
    "amount": "Vul een bedrag groter dan 0 in, met maximaal 2 decimalen.",
    "donated_at": "Vul een geldige datum en tijd in (dd-mm-jjjj uu:mm).",
    "description": "De omschrijving mag maximaal 500 tekens bevatten.",
    "start_date": "Vul een geldige begindatum in (dd-mm-jjjj).",
    "end_date": "Vul een geldige einddatum in (dd-mm-jjjj).",
}

FILTER_FIELDS = ("start_date", "end_date", "member_id", "category_id", "subcategory_id")
# Ledenkeuzelijsten bevatten alle leden; filteren gebeurt in de browser (app.js).
MEMBER_PICKER_LIMIT = 10_000
FormText = Annotated[str, Form()]
FormBool = Annotated[bool, Form()]


def _perm(permission: Permission):
    return Annotated[Principal, Depends(require(permission))]


# ── Hulpfuncties ─────────────────────────────────────────────────────────────


def render(
    request: Request, template: str, context: dict[str, Any] | None = None, status_code: int = 200
) -> Response:
    melding = MESSAGES.get(request.query_params.get("melding", ""))
    if melding and "{" in melding:
        numbers = {k: request.query_params.get(k, "") for k in ("aantal", "donaties")}
        try:
            melding = melding.format(**{k: int(v) for k, v in numbers.items() if v.isdigit()})
        except KeyError:
            melding = None
    base = {
        "principal": getattr(request.state, "principal", None),
        "csrf_token": request.state.csrf_token,
        "melding": melding,
    }
    return request.app.state.templates.TemplateResponse(
        request, template, base | (context or {}), status_code=status_code
    )


def is_partial(request: Request) -> bool:
    return (
        request.headers.get("hx-request") == "true"
        and request.headers.get("hx-history-restore-request") != "true"
    )


def clean(values: Mapping[str, Any]) -> dict[str, str]:
    return {k: v.strip() for k, v in values.items() if isinstance(v, str) and v.strip()}


def form_errors(exc: ValidationError) -> dict[str, str]:
    errors: dict[str, str] = {}
    for error in exc.errors():
        field = str(error["loc"][0]) if error["loc"] else "__all__"
        message = FIELD_MESSAGES.get(field, error["msg"].removeprefix("Value error, "))
        errors.setdefault(field, message)
    return errors


def domain_errors(exc: DomainError) -> dict[str, str]:
    return {exc.field or "__all__": exc.message}


def parse_amount(text: str) -> str:
    """Accepteert Nederlandse notatie zoals '1.234,50' of '€ 25,-'."""
    value = text.replace("€", "").replace(" ", "").replace(",-", "")
    if "," in value:
        value = value.replace(".", "").replace(",", ".")
    return value


def today(request: Request) -> date:
    return datetime.now(request.app.state.settings.tz).date()


def parse_filter(values: Mapping[str, Any]) -> tuple[ReportFilter | None, dict[str, str]]:
    data = {k: v for k, v in clean(values).items() if k in FILTER_FIELDS}
    for field in ("start_date", "end_date"):
        if field in data:
            data[field] = nl_date_to_iso(data[field])
    try:
        return ReportFilter.model_validate(data), {}
    except ValidationError as exc:
        return None, form_errors(exc)


def chart_data(report: Report | None) -> dict[str, Any]:
    if report is None or report.is_empty:
        return {}
    return {
        "category": {
            "type": "bar",
            "label": "Bedrag per categorie",
            "labels": [b.label for b in report.by_category],
            "values": [float(b.total) for b in report.by_category],
        },
        "month": {
            "type": "line",
            "label": "Bedrag per maand",
            "labels": [b.label for b in report.by_month],
            "values": [float(b.total) for b in report.by_month],
        },
    }


# ── Dashboard ────────────────────────────────────────────────────────────────


@router.get("/")
def home() -> Response:
    # De rapportage is de startpagina; /rapportage regelt zelf de rechtencontrole.
    return RedirectResponse("/rapportage", status_code=303)


# ── Leden ────────────────────────────────────────────────────────────────────


@router.get("/leden")
def members_list(
    request: Request,
    services: Services,
    _: _perm(Permission.MEMBERS_READ),
    q: str = "",
    status: str = "",
) -> Response:
    status_value = MemberStatus(status) if status in set(MemberStatus) else None
    members = services.members.search(q.strip() or None, status_value, limit=None)
    context = {"members": members, "q": q, "status": status}
    template = "members/_table.html" if is_partial(request) else "members/list.html"
    return render(request, template, context)


@router.post("/leden/verwijderen")
def members_delete(
    services: Services,
    _: _perm(Permission.MEMBERS_DELETE),
    ids: Annotated[list[int] | None, Form()] = None,
) -> Response:
    members, donations = services.members.delete_many(ids or [])
    melding = "lid-verwijderd" if members == 1 else "leden-verwijderd"
    query = urlencode({"melding": melding, "aantal": members, "donaties": donations})
    return RedirectResponse(f"/leden?{query}", status_code=303)


@router.get("/leden/nieuw")
def member_new(
    request: Request, services: Services, _: _perm(Permission.MEMBERS_WRITE)
) -> Response:
    context = {"values": {"status": "actief"}, "errors": {}}
    return render(request, "members/new.html", context | _extra_fields(services))


def _extra_fields(services: Services) -> dict[str, Any]:
    return {"extra_fields": services.member_fields.list(), "field_types": FieldType}


async def _extra_form(request: Request) -> dict[str, str]:
    form = await request.form()
    return {k: v for k, v in form.items() if k.startswith("veld_") and isinstance(v, str)}


ExtraForm = Annotated[dict[str, str], Depends(_extra_form)]


@router.post("/leden")
def member_create(
    request: Request,
    services: Services,
    principal: _perm(Permission.MEMBERS_WRITE),
    extra: ExtraForm,
    name: FormText = "",
    email: FormText = "",
    status: FormText = "actief",
) -> Response:
    values: dict[str, str] = {"name": name, "email": email, "status": status} | extra
    extra_values, errors = services.member_fields.validate(extra)
    context = _extra_fields(services)
    try:
        data = MemberCreate.model_validate(clean(values))
    except ValidationError as exc:
        errors = form_errors(exc) | errors
    if errors:
        return render(
            request, "members/new.html", context | {"values": values, "errors": errors}, 422
        )
    try:
        member = services.members.create(data, principal.name)
    except DomainError as exc:
        context |= {"values": values, "errors": domain_errors(exc)}
        return render(request, "members/new.html", context, 409)
    services.member_fields.save(member.id, extra_values)
    return RedirectResponse(f"/leden/{member.id}?melding=lid-aangemaakt", status_code=303)


def _member_detail(request, services, principal, member, values, errors, status_code=200):
    donations = (
        [DonationRead.from_entity(d) for d in services.donations.recent(20, member.id)]
        if principal.can(Permission.DONATIONS_READ)
        else []
    )
    context = {"member": member, "values": values, "errors": errors, "donations": donations}
    return render(request, "members/detail.html", context | _extra_fields(services), status_code)


@router.get("/leden/{member_id}")
def member_detail(
    request: Request, member_id: int, services: Services, principal: _perm(Permission.MEMBERS_READ)
) -> Response:
    member = services.members.get(member_id)
    values = {"name": member.name, "email": member.email, "status": member.status.value}
    values |= {f"veld_{k}": v for k, v in services.member_fields.values(member_id).items()}
    return _member_detail(request, services, principal, member, values, {})


@router.post("/leden/{member_id}")
def member_update(
    request: Request,
    member_id: int,
    services: Services,
    principal: _perm(Permission.MEMBERS_WRITE),
    extra: ExtraForm,
    name: FormText = "",
    email: FormText = "",
    status: FormText = "",
) -> Response:
    member = services.members.get(member_id)
    values: dict[str, str] = {"name": name, "email": email, "status": status} | extra
    extra_values, errors = services.member_fields.validate(extra)
    try:
        data = MemberUpdate.model_validate(
            {"name": name.strip(), "email": email.strip(), "status": status}
        )
    except ValidationError as exc:
        errors = form_errors(exc) | errors
    if errors:
        return _member_detail(request, services, principal, member, values, errors, 422)
    try:
        services.members.update(member_id, data)
    except DomainError as exc:
        return _member_detail(request, services, principal, member, values, domain_errors(exc), 409)
    services.member_fields.save(member_id, extra_values)
    return RedirectResponse(f"/leden/{member_id}?melding=lid-bijgewerkt", status_code=303)


# ── Ledenvelden (beheerder) ─────────────────────────────────────────────────

CanManageFields = _perm(Permission.MEMBER_FIELDS_WRITE)


def _fields_page(
    request: Request,
    services: Services,
    values: dict[str, str] | None = None,
    errors: dict[str, str] | None = None,
    status_code: int = 200,
) -> Response:
    context = {
        "fields": services.member_fields.list(include_inactive=True),
        "type_labels": FIELD_TYPE_LABELS,
        "is_sensitive": is_sensitive_label,
        "values": values or {"field_type": FieldType.TEXT},
        "errors": errors or {},
    }
    return render(request, "member_fields/index.html", context, status_code)


@router.get("/ledenvelden")
def member_fields_index(request: Request, services: Services, _: CanManageFields) -> Response:
    return _fields_page(request, services)


@router.post("/ledenvelden")
def member_field_create(
    request: Request,
    services: Services,
    _: CanManageFields,
    label: FormText = "",
    field_type: FormText = "",
) -> Response:
    values = {"label": label, "field_type": field_type}
    try:
        services.member_fields.create(label, field_type)
    except ConflictError as exc:
        return _fields_page(request, services, values, domain_errors(exc), 422)
    return RedirectResponse("/ledenvelden?melding=veld-opgeslagen", status_code=303)


@router.post("/ledenvelden/{field_id}/status")
def member_field_status(
    field_id: int, services: Services, _: CanManageFields, is_active: FormBool
) -> Response:
    services.member_fields.set_active(field_id, is_active)
    return RedirectResponse("/ledenvelden?melding=veld-opgeslagen", status_code=303)


@router.post("/ledenvelden/{field_id}/verwijderen")
def member_field_delete(field_id: int, services: Services, _: CanManageFields) -> Response:
    services.member_fields.delete(field_id)
    return RedirectResponse("/ledenvelden?melding=verwijderd", status_code=303)


# ── Logboek ──────────────────────────────────────────────────────────────────


@router.post("/logboek/klik", status_code=204)
def audit_click(_: CurrentPrincipal) -> Response:
    # De AuditMiddleware schrijft de regel; hier alleen authenticatie en CSRF.
    return Response(status_code=204)


@router.get("/logboek")
def audit_index(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    _: _perm(Permission.AUDIT_READ),
    gebruiker: str = "",
    actie: str = "",
) -> Response:
    actions = [Action.LOGIN, Action.VIEW, Action.CLICK, Action.UPDATE, Action.DELETE]
    context = {
        "entries": audit.recent(session, gebruiker.strip(), actie if actie in actions else ""),
        "actions": actions,
        "gebruiker": gebruiker,
        "actie": actie,
    }
    return render(request, "audit/index.html", context)


# ── Donaties ─────────────────────────────────────────────────────────────────


@router.get("/donaties")
def donations_list(
    request: Request,
    services: Services,
    _: _perm(Permission.DONATIONS_READ),
    member_id: str = "",
) -> Response:
    selected = int(member_id) if member_id.isdigit() else None
    donations = [DonationRead.from_entity(d) for d in services.donations.recent(None, selected)]
    context = {
        "donations": donations,
        "member_id": str(selected or ""),
        "members": services.members.search(limit=MEMBER_PICKER_LIMIT),
    }
    return render(request, "donations/list.html", context)


def _donation_form(request, services, values, errors, status_code=200) -> Response:
    context = {
        "values": values,
        "errors": errors,
        "members": services.members.search(status=MemberStatus.ACTIVE, limit=MEMBER_PICKER_LIMIT),
        "categories": services.categories.list(),
    }
    return render(request, "donations/new.html", context, status_code)


@router.get("/donaties/nieuw")
def donation_new(
    request: Request,
    services: Services,
    _: _perm(Permission.DONATIONS_WRITE),
    member_id: str = "",
) -> Response:
    now = datetime.now(request.app.state.settings.tz)
    values = {"member_id": member_id, "donated_at": now.strftime("%Y-%m-%dT%H:%M")}
    return _donation_form(request, services, values, {})


@router.post("/donaties")
def donation_create(
    request: Request,
    services: Services,
    principal: _perm(Permission.DONATIONS_WRITE),
    member_id: FormText = "",
    subcategory_id: FormText = "",
    amount: FormText = "",
    donated_at: FormText = "",
    description: FormText = "",
) -> Response:
    values = {
        "member_id": member_id,
        "subcategory_id": subcategory_id,
        "amount": amount,
        "donated_at": donated_at,
        "description": description,
    }
    data = clean(values)
    if "amount" in data:
        data["amount"] = parse_amount(data["amount"])
    if "donated_at" in data:
        data["donated_at"] = nl_datetime_to_iso(data["donated_at"])
    try:
        services.donations.register(DonationCreate.model_validate(data), principal.name)
    except ValidationError as exc:
        return _donation_form(request, services, values, form_errors(exc), 422)
    except DomainError as exc:
        return _donation_form(request, services, values, domain_errors(exc), 422)
    return RedirectResponse("/donaties?melding=donatie-geregistreerd", status_code=303)


@router.post("/donaties/verwijderen")
def donations_delete(
    services: Services,
    _: _perm(Permission.DONATIONS_DELETE),
    ids: Annotated[list[int] | None, Form()] = None,
) -> Response:
    count = services.donations.delete_many(ids or [])
    melding = "donatie-verwijderd" if count == 1 else "donaties-verwijderd"
    return RedirectResponse(f"/donaties?melding={melding}&aantal={count}", status_code=303)


# ── Categorieën ──────────────────────────────────────────────────────────────
# Met HTMX wordt alleen het beheerblok vervangen (scrollpositie blijft behouden);
# zonder JavaScript werken dezelfde formulieren via redirects.

CanManageCategories = _perm(Permission.CATEGORIES_WRITE)


def _categories_page(
    request: Request,
    services: Services,
    editing: str = "",
    values: dict[str, str] | None = None,
    errors: dict[str, str] | None = None,
    status_code: int = 200,
    melding: str = "",
) -> Response:
    """`editing` is de sleutel van het geopende formulier; `values`/`errors` horen daarbij."""
    context = {
        "categories": services.categories.list(include_inactive=True),
        "used_subcategory_ids": services.categories.used_subcategory_ids(),
        "editing": editing,
        "values": values or {},
        "errors": errors or {},
        "beheer_melding": melding,
    }
    template = "categories/_beheer.html" if is_partial(request) else "categories/index.html"
    return render(request, template, context, status_code)


def _saved(request: Request, services: Services, category_id: int, message: str) -> Response:
    if is_partial(request):
        return _categories_page(request, services)
    url = f"/categorieen?melding={message}#categorie-{category_id}"
    return RedirectResponse(url, status_code=303)


def _save_name(
    request: Request,
    services: Services,
    editing: str,
    name: str,
    save: Callable[[str], int],
    message: str,
) -> Response:
    """Valideert en bewaart een (sub)categorienaam; `save` geeft de categorie-ID terug."""
    values = {"name": name}
    try:
        category_id = save(CategoryCreate.model_validate(values).name)
    except ValidationError:
        errors = {"name": CATEGORY_NAME_ERROR}
        return _categories_page(request, services, editing, values, errors, 422)
    except ConflictError as exc:
        return _categories_page(request, services, editing, values, domain_errors(exc), 409)
    return _saved(request, services, category_id, message)


@router.get("/categorieen")
def categories_index(
    request: Request, services: Services, _: CanManageCategories, bewerk: str = ""
) -> Response:
    return _categories_page(request, services, editing=bewerk)


@router.post("/categorieen")
def category_create(
    request: Request, services: Services, _: CanManageCategories, name: FormText = ""
) -> Response:
    return _save_name(
        request,
        services,
        "nieuwe-categorie",
        name,
        lambda value: services.categories.create_category(value).id,
        "categorie-opgeslagen",
    )


@router.post("/categorieen/{category_id}")
def category_rename(
    request: Request,
    category_id: int,
    services: Services,
    _: CanManageCategories,
    name: FormText = "",
) -> Response:
    return _save_name(
        request,
        services,
        f"cat-{category_id}",
        name,
        lambda value: services.categories.update_category(category_id, name=value).id,
        "categorie-opgeslagen",
    )


@router.post("/categorieen/{category_id}/status")
def category_set_status(
    request: Request,
    category_id: int,
    services: Services,
    _: CanManageCategories,
    is_active: FormBool,
) -> Response:
    services.categories.update_category(category_id, is_active=is_active)
    return _saved(request, services, category_id, "categorie-opgeslagen")


@router.post("/categorieen/{category_id}/subcategorieen")
def subcategory_create(
    request: Request,
    category_id: int,
    services: Services,
    _: CanManageCategories,
    name: FormText = "",
) -> Response:
    return _save_name(
        request,
        services,
        f"nieuw-{category_id}",
        name,
        lambda value: services.categories.create_subcategory(category_id, value).category_id,
        "subcategorie-opgeslagen",
    )


@router.post("/categorieen/{category_id}/subcategorieen/{subcategory_id}")
def subcategory_rename(
    request: Request,
    category_id: int,
    subcategory_id: int,
    services: Services,
    _: CanManageCategories,
    name: FormText = "",
) -> Response:
    return _save_name(
        request,
        services,
        f"sub-{subcategory_id}",
        name,
        lambda value: services.categories.update_subcategory(
            category_id, subcategory_id, name=value
        ).category_id,
        "subcategorie-opgeslagen",
    )


@router.post("/categorieen/{category_id}/subcategorieen/{subcategory_id}/status")
def subcategory_set_status(
    request: Request,
    category_id: int,
    subcategory_id: int,
    services: Services,
    _: CanManageCategories,
    is_active: FormBool,
) -> Response:
    services.categories.update_subcategory(category_id, subcategory_id, is_active=is_active)
    return _saved(request, services, category_id, "subcategorie-opgeslagen")


def _delete(request: Request, services: Services, delete: Callable[[], None]) -> Response:
    try:
        delete()
    except ConflictError as exc:
        return _categories_page(request, services, melding=exc.message, status_code=409)
    if is_partial(request):
        return _categories_page(request, services, melding="Verwijderd.")
    return RedirectResponse("/categorieen?melding=verwijderd", status_code=303)


@router.post("/categorieen/{category_id}/verwijderen")
def category_delete(
    request: Request, category_id: int, services: Services, _: CanManageCategories
) -> Response:
    return _delete(request, services, lambda: services.categories.delete_category(category_id))


@router.post("/categorieen/{category_id}/subcategorieen/{subcategory_id}/verwijderen")
def subcategory_delete(
    request: Request,
    category_id: int,
    subcategory_id: int,
    services: Services,
    _: CanManageCategories,
) -> Response:
    return _delete(
        request,
        services,
        lambda: services.categories.delete_subcategory(category_id, subcategory_id),
    )


# ── Rapportage ───────────────────────────────────────────────────────────────


@router.get("/rapportage")
def reports(
    request: Request, services: Services, principal: _perm(Permission.REPORTS_READ)
) -> Response:
    raw = dict(request.query_params)
    if not any(field in raw for field in FILTER_FIELDS):
        end = today(request)
        raw = {"start_date": end.replace(month=1, day=1).isoformat(), "end_date": end.isoformat()}
    if not principal.can(Permission.REPORTS_MEMBER_READ):
        raw.pop("member_id", None)

    report_filter, errors = parse_filter(raw)
    report = services.visible_report(principal, report_filter) if report_filter else None
    export_query = urlencode(report_filter.model_dump(exclude_none=True)) if report_filter else ""
    context = {
        "values": raw,
        "errors": errors,
        "report": report,
        "charts": chart_data(report),
        "export_query": export_query,
    }
    if is_partial(request):
        return render(request, "reports/_report.html", context)

    context["categories"] = services.categories.list(include_inactive=True)
    context["members"] = (
        services.members.search(limit=MEMBER_PICKER_LIMIT)
        if principal.can(Permission.REPORTS_MEMBER_READ)
        else []
    )
    return render(request, "reports/index.html", context)


@router.post("/rapportage/ai")
def report_insight(
    request: Request,
    services: Services,
    principal: _perm(Permission.INSIGHTS_READ),
    start_date: FormText = "",
    end_date: FormText = "",
    member_id: FormText = "",
    category_id: FormText = "",
    subcategory_id: FormText = "",
) -> Response:
    raw = {
        "start_date": start_date,
        "end_date": end_date,
        "member_id": member_id if principal.can(Permission.REPORTS_MEMBER_READ) else "",
        "category_id": category_id,
        "subcategory_id": subcategory_id,
    }
    report_filter, errors = parse_filter(raw)
    insight = None
    if report_filter:
        insight = services.insights.generate(services.visible_report(principal, report_filter))
    return render(request, "reports/_insight.html", {"insight": insight, "errors": errors})
