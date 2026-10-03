"""Logboek van gebruikersacties: aanmeldingen, weergaven, klikken, wijzigingen en verwijderingen.

De middleware legt elk verzoek vast met gebruiker, actie, pad en statuscode. Klikken komen
via `navigator.sendBeacon` van de browser binnen op `/logboek/klik`. Fouten bij het loggen
worden nooit aan de gebruiker getoond: het logboek mag de app niet blokkeren.
"""

import json
import logging
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl

from fastapi import Request
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, PlainTextResponse, Response

from ledenadmin.domain.models import AuditLog
from ledenadmin.tenancy import current_organization_id

logger = logging.getLogger("ledenadmin.audit")

SESSION_COOKIE = "logboek_sessie"
CLICK_SUFFIX = "/logboek/klik"
CLIENT_ERROR_SUFFIX = "/logboek/fout"
SKIP_PREFIXES = ("/static/", "/api/v1/health", "/favicon")
SKIP_FIELDS = {"csrf_token"}
MAX_DETAIL = 2000


class Action:
    LOGIN = "aanmelding"
    VIEW = "weergave"
    CLICK = "klik"
    UPDATE = "wijziging"
    DELETE = "verwijdering"
    ERROR = "fout"
    CLIENT_ERROR = "browserfout"


def classify(method: str, path: str) -> str:
    if path.endswith(CLICK_SUFFIX):
        return Action.CLICK
    if path.endswith(CLIENT_ERROR_SUFFIX):
        return Action.CLIENT_ERROR
    if method == "DELETE" or path.endswith("/verwijderen"):
        return Action.DELETE
    if method in {"POST", "PUT", "PATCH"}:
        return Action.UPDATE
    return Action.VIEW


def _detail_from_body(content_type: str, body: bytes) -> dict[str, object]:
    if not body:
        return {}
    text = body.decode("utf-8", errors="replace")
    if content_type.startswith("application/x-www-form-urlencoded"):
        fields: dict[str, object] = {}
        for key, value in parse_qsl(text, keep_blank_values=True):
            if key in SKIP_FIELDS:
                continue
            if key not in fields:
                fields[key] = value
            elif isinstance(fields[key], list):
                fields[key].append(value)
            else:
                fields[key] = [fields[key], value]
        return fields
    if content_type.startswith("application/json"):
        try:
            data = json.loads(text)
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {"body": data}
    return {}


ERROR_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def new_error_code() -> str:
    return "ERR-" + "".join(secrets.choice(ERROR_ALPHABET) for _ in range(6))


def error_response(request: Request, code: str) -> Response:
    from ledenadmin.api.errors import is_api_request, render_error

    message = "Er ging onverwacht iets mis. Vermeld code " + code + " als u contact opneemt."
    if is_api_request(request):
        return JSONResponse({"detail": message, "code": code}, status_code=500)
    try:
        return render_error(request, 500, message, code)
    except Exception:  # pragma: no cover - laatste vangnet
        return PlainTextResponse(message, status_code=500)


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if path.startswith(SKIP_PREFIXES):
            return await call_next(request)

        method = request.method
        detail: dict[str, object] = {}
        if request.url.query:
            detail["query"] = request.url.query
        if method in {"POST", "PUT", "PATCH", "DELETE"}:
            # Starlette bewaart de body, zodat de route hem daarna nog kan lezen.
            body = await request.body()
            detail |= _detail_from_body(request.headers.get("content-type", ""), body)

        error: dict[str, str] | None = None
        try:
            response = await call_next(request)
        except Exception as exc:
            # Onverwachte fout: traceback met foutcode naar het serverlog, korte regel in
            # het logboek en een nette foutpagina met dezelfde code voor de gebruiker.
            code = new_error_code()
            logger.exception("%s %s %s", code, method, path)
            error = {"foutcode": code, "type": type(exc).__name__}
            response = error_response(request, code)

        principal = getattr(request.state, "principal", None)
        identity = getattr(request.state, "identity", None) or principal
        if identity is None:
            try:
                identity = request.app.state.auth_provider.authenticate(request)
            except Exception:  # pragma: no cover - authenticatie mag het loggen niet breken
                identity = None
        user = identity.name if identity else "anoniem"
        entries: list[AuditLog] = []

        is_new_session = identity is not None and not request.cookies.get(SESSION_COOKIE)
        if is_new_session:
            roles = ",".join(sorted(principal.roles)) if principal else ""
            roles = roles or "geen rollen"
            entries.append(self._entry(request, user, Action.LOGIN, None, f"rollen: {roles}"))
            response.set_cookie(
                SESSION_COOKIE,
                secrets.token_urlsafe(16),
                httponly=True,
                samesite="lax",
                secure=request.app.state.settings.is_production,
            )

        action = Action.ERROR if error else classify(method, path)
        if error:
            text = json.dumps(error | detail, ensure_ascii=False)
        elif action in (Action.CLICK, Action.CLIENT_ERROR):
            text = json.dumps({k: v for k, v in detail.items() if k != "query"}, ensure_ascii=False)
        else:
            text = json.dumps(detail, ensure_ascii=False) if detail else None
        entries.append(self._entry(request, user, action, response.status_code, text))

        try:
            await run_in_threadpool(self._save, request, entries)
        except Exception:
            logger.exception("Logboekregel kon niet worden opgeslagen")
        return response

    @staticmethod
    def _entry(
        request: Request, user: str, action: str, status_code: int | None, detail: str | None
    ) -> AuditLog:
        client = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (
            request.client.host if request.client else None
        )
        return AuditLog(
            user=user[:200],
            action=action,
            method=request.method,
            path=request.url.path[:500],
            status_code=status_code,
            detail=detail[:MAX_DETAIL] if detail else None,
            ip=client[:64] if client else None,
            user_agent=(request.headers.get("user-agent") or "")[:300] or None,
        )

    @staticmethod
    def _save(request: Request, entries: list[AuditLog]) -> None:
        principal = getattr(request.state, "principal", None)
        organization_id = principal.organization_id if principal else None
        with request.app.state.database.session() as session:
            for entry in entries:
                entry.organization_id = organization_id
                logger.info(
                    "%s %s %s %s %s",
                    entry.user,
                    entry.action,
                    entry.method,
                    entry.path,
                    entry.status_code,
                )
                session.add(entry)
            session.commit()
            global _last_purge
            now = datetime.now(UTC)
            if _last_purge is None or now - _last_purge > timedelta(hours=1):
                _last_purge = now
                purge(session, now)


_last_purge: datetime | None = None


RETENTION = timedelta(days=41)


def purge(session: Session, now: datetime | None = None) -> int:
    """Verwijdert logregels ouder dan de bewaartermijn; geeft het aantal terug."""
    cutoff = (now or datetime.now(UTC)) - RETENTION
    result = session.execute(delete(AuditLog).where(AuditLog.at < cutoff))
    session.commit()
    return result.rowcount or 0


def recent(
    session: Session, user: str = "", action: str = "", limit: int | None = None
) -> list[AuditLog]:
    """Logregels van de organisatie waaraan de sessie gebonden is."""
    stmt = (
        select(AuditLog)
        .where(AuditLog.organization_id == current_organization_id(session))
        .order_by(AuditLog.at.desc(), AuditLog.id.desc())
        .limit(limit)
    )
    if user:
        stmt = stmt.where(AuditLog.user.contains(user))
    if action:
        stmt = stmt.where(AuditLog.action == action)
    return list(session.scalars(stmt))
