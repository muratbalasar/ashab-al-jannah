from urllib.parse import quote

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, RedirectResponse, Response

from ledenadmin.api.deps import OrganizationRedirect
from ledenadmin.auth.errors import NotAuthenticatedError, PermissionDeniedError
from ledenadmin.domain.errors import BusinessRuleError, ConflictError, DomainError, NotFoundError

STATUS_BY_ERROR: list[tuple[type[DomainError], int]] = [
    (NotFoundError, status.HTTP_404_NOT_FOUND),
    (ConflictError, status.HTTP_409_CONFLICT),
    (BusinessRuleError, status.HTTP_422_UNPROCESSABLE_CONTENT),
]


def is_api_request(request: Request) -> bool:
    path = request.url.path
    return path.startswith("/api/") or (path.startswith("/o/") and "/api/" in path)


def status_for(error: DomainError) -> int:
    for error_type, code in STATUS_BY_ERROR:
        if isinstance(error, error_type):
            return code
    return status.HTTP_400_BAD_REQUEST


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain_error(request: Request, exc: DomainError) -> Response:
        body = {"detail": exc.message, "field": exc.field}
        if is_api_request(request):
            return JSONResponse(body, status_code=status_for(exc))
        return _html_error(request, status_for(exc), exc.message)

    @app.exception_handler(OrganizationRedirect)
    async def _org_redirect(request: Request, exc: OrganizationRedirect) -> Response:
        return RedirectResponse(exc.location, status.HTTP_307_TEMPORARY_REDIRECT)

    @app.exception_handler(NotAuthenticatedError)
    async def _not_authenticated(request: Request, exc: NotAuthenticatedError) -> Response:
        if is_api_request(request):
            return JSONResponse(
                {"detail": "Aanmelden vereist"}, status_code=status.HTTP_401_UNAUTHORIZED
            )
        login_url = request.app.state.auth_provider.login_url
        if login_url:
            target = request.url.path + (f"?{request.url.query}" if request.url.query else "")
            return RedirectResponse(f"{login_url}?post_login_redirect_uri={quote(target)}", 302)
        return _html_error(request, status.HTTP_401_UNAUTHORIZED, "Aanmelden vereist")

    @app.exception_handler(PermissionDeniedError)
    async def _forbidden(request: Request, exc: PermissionDeniedError) -> Response:
        if is_api_request(request):
            return JSONResponse({"detail": exc.message}, status_code=status.HTTP_403_FORBIDDEN)
        return _html_error(request, status.HTTP_403_FORBIDDEN, exc.message)


def _html_error(request: Request, status_code: int, message: str) -> Response:
    return render_error(request, status_code, message)


def render_error(
    request: Request, status_code: int, message: str, code: str | None = None
) -> Response:
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "status_code": status_code,
            "message": message,
            "error_code": code,
            "principal": None,
            "org": "",
            "csrf_token": getattr(request.state, "csrf_token", ""),
        },
        status_code=status_code,
    )
