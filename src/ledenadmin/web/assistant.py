"""Helpassistent in de web-UI (US16): alleen zichtbaar en bereikbaar als hij aan staat."""

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request, Response

from ledenadmin.api.deps import CurrentPrincipal
from ledenadmin.auth.principal import Principal
from ledenadmin.domain.errors import NotFoundError
from ledenadmin.services.assistant.knowledge import KnowledgeChunk, fixed_knowledge, html_to_text
from ledenadmin.services.assistant.service import AssistantService
from ledenadmin.web.routes import help_sections, is_partial, org_prefix, render
from ledenadmin.web.security import verify_csrf

router = APIRouter(dependencies=[Depends(verify_csrf)], include_in_schema=False)

QUESTION_FIELD = "assistent_vraag"


def _assistant(request: Request) -> AssistantService:
    assistant = getattr(request.app.state, "assistant", None)
    if assistant is None:
        raise NotFoundError("Pagina niet gevonden")
    return assistant


def build_knowledge(request: Request, principal: Principal) -> list[KnowledgeChunk]:
    """De help-secties van deze gebruiker (zoals op de Help-pagina) plus de vaste kennis."""
    org = org_prefix(request)
    env = request.app.state.templates.env

    def help_text(anchor: str) -> str:
        return html_to_text(
            env.get_template(f"help/{anchor}.html").render(org=org, principal=principal)
        )

    chunks = [
        KnowledgeChunk(anchor, title, help_text(anchor), f"{org}/help#{anchor}")
        for anchor, title in help_sections(principal)
    ]
    return chunks + fixed_knowledge(principal.is_superadmin)


def describe_roles(principal: Principal) -> str:
    roles = sorted(role.value for role in principal.roles)
    if principal.is_superadmin:
        roles.append("superadmin (platformbeheer)")
    return ", ".join(roles) or "geen"


@router.get("/assistent")
def assistant_page(request: Request, principal: CurrentPrincipal) -> Response:
    assistant = _assistant(request)
    with request.app.state.database.session() as session:
        remaining = assistant.remaining(session, principal.user_id)
    return render(
        request,
        "assistant/index.html",
        {"assistant": assistant, "reply": None, "remaining": remaining, "question": ""},
    )


@router.post("/assistent")
def assistant_ask(
    request: Request,
    principal: CurrentPrincipal,
    assistent_vraag: Annotated[str, Form()] = "",
) -> Response:
    assistant = _assistant(request)
    knowledge = build_knowledge(request, principal)
    with request.app.state.database.session() as session:
        reply = assistant.ask(
            session, principal.user_id, assistent_vraag, knowledge, describe_roles(principal)
        )
    context = {
        "assistant": assistant,
        "reply": reply,
        "remaining": reply.remaining,
        "question": assistent_vraag,
    }
    template = "assistant/_reply.html" if is_partial(request) else "assistant/index.html"
    return render(request, template, context)
