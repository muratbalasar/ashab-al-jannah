from collections.abc import Mapping
from datetime import date, datetime
from typing import Annotated, Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import ValidationError

from ledenadmin.api.deps import CurrentPrincipal, Services, require
from ledenadmin.auth.principal import Principal
from ledenadmin.domain.enums import MemberStatus, Permission
from ledenadmin.domain.errors import DomainError
from ledenadmin.schemas.donations import DonationCreate, DonationRead
from ledenadmin.schemas.members import MemberCreate, MemberUpdate
from ledenadmin.schemas.reports import Report, ReportFilter
from ledenadmin.web.security import verify_csrf

router = APIRouter(dependencies=[Depends(verify_csrf)], include_in_schema=False)

MESSAGES = {
    "lid-aangemaakt": "Het lid is aangemaakt.",
    "lid-bijgewerkt": "Het lid is bijgewerkt.",
    "donatie-geregistreerd": "De donatie is geregistreerd.",
}

FIELD_MESSAGES = {
    "name": "Vul een naam in (maximaal 200 tekens).",
    "email": "Vul een geldig e-mailadres in.",
    "status": "Kies een geldige status.",
    "member_id": "Kies een lid.",
    "subcategory_id": "Kies een categorie en subcategorie.",
    "amount": "Vul een bedrag groter dan 0 in, met maximaal 2 decimalen.",
    "donated_at": "Vul een geldige datum en tijd in.",
    "description": "De omschrijving mag maximaal 500 tekens bevatten.",
    "start_date": "Vul een geldige begindatum in.",
    "end_date": "Vul een geldige einddatum in.",
}

FILTER_FIELDS = ("start_date", "end_date", "member_id", "category_id", "subcategory_id")
FormText = Annotated[str, Form()]


def _perm(permission: Permission):
    return Annotated[Principal, Depends(require(permission))]


# ── Hulpfuncties ─────────────────────────────────────────────────────────────


def render(
    request: Request, template: str, context: dict[str, Any] | None = None, status_code: int = 200
) -> Response:
    base = {
        "principal": getattr(request.state, "principal", None),
        "csrf_token": request.state.csrf_token,
        "melding": MESSAGES.get(request.query_params.get("melding", "")),
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
def dashboard(request: Request, services: Services, principal: CurrentPrincipal) -> Response:
    report = None
    if principal.can(Permission.REPORTS_READ):
        end = today(request)
        report_filter = ReportFilter(start_date=end.replace(day=1), end_date=end)
        report = services.visible_report(principal, report_filter)
    return render(request, "dashboard.html", {"report": report})


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
    members = services.members.search(q.strip() or None, status_value, limit=200)
    context = {"members": members, "q": q, "status": status}
    template = "members/_table.html" if is_partial(request) else "members/list.html"
    return render(request, template, context)


@router.get("/leden/nieuw")
def member_new(request: Request, _: _perm(Permission.MEMBERS_WRITE)) -> Response:
    return render(request, "members/new.html", {"values": {"status": "actief"}, "errors": {}})


@router.post("/leden")
def member_create(
    request: Request,
    services: Services,
    principal: _perm(Permission.MEMBERS_WRITE),
    name: FormText = "",
    email: FormText = "",
    status: FormText = "actief",
) -> Response:
    values = {"name": name, "email": email, "status": status}
    try:
        member = services.members.create(MemberCreate.model_validate(clean(values)), principal.name)
    except ValidationError as exc:
        return render(
            request, "members/new.html", {"values": values, "errors": form_errors(exc)}, 422
        )
    except DomainError as exc:
        context = {"values": values, "errors": domain_errors(exc)}
        return render(request, "members/new.html", context, 409)
    return RedirectResponse(f"/leden/{member.id}?melding=lid-aangemaakt", status_code=303)


def _member_detail(request, services, principal, member, values, errors, status_code=200):
    donations = (
        [DonationRead.from_entity(d) for d in services.donations.recent(20, member.id)]
        if principal.can(Permission.DONATIONS_READ)
        else []
    )
    context = {"member": member, "values": values, "errors": errors, "donations": donations}
    return render(request, "members/detail.html", context, status_code)


@router.get("/leden/{member_id}")
def member_detail(
    request: Request, member_id: int, services: Services, principal: _perm(Permission.MEMBERS_READ)
) -> Response:
    member = services.members.get(member_id)
    values = {"name": member.name, "email": member.email, "status": member.status.value}
    return _member_detail(request, services, principal, member, values, {})


@router.post("/leden/{member_id}")
def member_update(
    request: Request,
    member_id: int,
    services: Services,
    principal: _perm(Permission.MEMBERS_WRITE),
    name: FormText = "",
    email: FormText = "",
    status: FormText = "",
) -> Response:
    member = services.members.get(member_id)
    values = {"name": name, "email": email, "status": status}
    try:
        data = MemberUpdate.model_validate(
            {"name": name.strip(), "email": email.strip(), "status": status}
        )
        services.members.update(member_id, data)
    except ValidationError as exc:
        return _member_detail(request, services, principal, member, values, form_errors(exc), 422)
    except DomainError as exc:
        return _member_detail(request, services, principal, member, values, domain_errors(exc), 409)
    return RedirectResponse(f"/leden/{member_id}?melding=lid-bijgewerkt", status_code=303)


# ── Donaties ─────────────────────────────────────────────────────────────────


@router.get("/donaties")
def donations_list(
    request: Request, services: Services, _: _perm(Permission.DONATIONS_READ)
) -> Response:
    donations = [DonationRead.from_entity(d) for d in services.donations.recent(100)]
    return render(request, "donations/list.html", {"donations": donations})


def _donation_form(request, services, values, errors, status_code=200) -> Response:
    context = {
        "values": values,
        "errors": errors,
        "members": services.members.search(status=MemberStatus.ACTIVE, limit=500),
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
    try:
        services.donations.register(DonationCreate.model_validate(data), principal.name)
    except ValidationError as exc:
        return _donation_form(request, services, values, form_errors(exc), 422)
    except DomainError as exc:
        return _donation_form(request, services, values, domain_errors(exc), 422)
    return RedirectResponse("/donaties?melding=donatie-geregistreerd", status_code=303)


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
        services.members.search(limit=500) if principal.can(Permission.REPORTS_MEMBER_READ) else []
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
