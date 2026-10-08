import secrets

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from ledenadmin.auth.errors import PermissionDeniedError

CSRF_COOKIE = "csrftoken"
CSRF_FIELD = "csrf_token"
CSRF_HEADER = "x-csrf-token"
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
DOCS_PATH = "/api/docs"

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)


class SecurityMiddleware(BaseHTTPMiddleware):
    """Zet beveiligingsheaders en zorgt voor een CSRF-token-cookie per browser."""

    def __init__(self, app, secure_cookies: bool) -> None:
        super().__init__(app)
        self._secure_cookies = secure_cookies

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        token = request.cookies.get(CSRF_COOKIE)
        is_new = not token or len(token) < 32
        if is_new:
            token = secrets.token_urlsafe(32)
        request.state.csrf_token = token

        response = await call_next(request)

        if is_new:
            response.set_cookie(
                CSRF_COOKIE,
                token,
                httponly=True,
                samesite="lax",
                secure=self._secure_cookies,
                path="/",
            )
        if not request.url.path.startswith(DOCS_PATH):
            response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response


def safe_return_path(value: str, default: str = "/") -> str:
    """Alleen paden binnen deze site, zodat een terug-link geen open redirect wordt."""
    if value.startswith("/") and not value.startswith("//") and "\\" not in value:
        return value
    return default


async def verify_csrf(request: Request) -> None:
    """Double-submit-controle voor formulieren en HTMX-verzoeken van de web-UI."""
    if request.method not in UNSAFE_METHODS:
        return
    cookie_token = request.cookies.get(CSRF_COOKIE, "")
    sent = request.headers.get(CSRF_HEADER)
    if not sent:
        form = await request.form()
        sent = form.get(CSRF_FIELD)
    valid = cookie_token and isinstance(sent, str) and secrets.compare_digest(sent, cookie_token)
    if not valid:
        raise PermissionDeniedError(
            "Je sessie is verlopen of ongeldig. Ververs de pagina en probeer het opnieuw."
        )
