"""Alleen bij AUTH_MODE=dev: lokaal van gebruiker wisselen, bijv. om uitnodigingen te testen."""

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import RedirectResponse

from ledenadmin.auth.providers import DEV_USER_COOKIE, clean_dev_user
from ledenadmin.config import AuthMode
from ledenadmin.domain.errors import NotFoundError
from ledenadmin.web.security import safe_return_path, verify_csrf


def require_dev_mode(request: Request) -> None:
    if request.app.state.settings.auth_mode != AuthMode.DEV:
        raise NotFoundError("Pagina niet gevonden")


router = APIRouter(
    prefix="/dev",
    dependencies=[Depends(require_dev_mode), Depends(verify_csrf)],
    include_in_schema=False,
)


def _page(request: Request, terug: str, error: str | None = None, status_code: int = 200):
    identity = request.app.state.auth_provider.authenticate(request)
    context = {
        "principal": None,
        "csrf_token": request.state.csrf_token,
        "org": "",
        "current": identity.name if identity else "",
        "current_email": identity.email if identity else "",
        "switched": bool(clean_dev_user(request.cookies.get(DEV_USER_COOKIE, ""))),
        "default_user": request.app.state.settings.dev_user_name,
        "terug": safe_return_path(terug),
        "error": error,
    }
    return request.app.state.templates.TemplateResponse(
        request, "dev/user.html", context, status_code=status_code
    )


@router.get("/gebruiker")
def dev_user_form(request: Request, terug: str = "/") -> Response:
    return _page(request, terug)


@router.post("/gebruiker")
def dev_user_switch(
    request: Request,
    gebruiker: Annotated[str, Form()] = "",
    terug: Annotated[str, Form()] = "/",
    actie: Annotated[str, Form()] = "wissel",
) -> Response:
    response = RedirectResponse(safe_return_path(terug), status_code=303)
    if actie == "standaard":
        response.delete_cookie(DEV_USER_COOKIE, path="/")
        return response
    user = clean_dev_user(gebruiker)
    if user is None:
        error = "Vul een gebruikersnaam of e-mailadres in (letters, cijfers en . _ + - @)."
        return _page(request, terug, error, 422)
    response.set_cookie(DEV_USER_COOKIE, user, httponly=True, samesite="lax", path="/")
    return response
