"""Helpassistent (US16): grenzen, privacy, limieten en zichtbaarheid."""

import json
import logging
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from test_my import add_member, link_lid
from test_users import add_org

from ledenadmin.auth.principal import Identity
from ledenadmin.config import AIProviderName, Settings
from ledenadmin.domain.models import AssistantUsage, AuditLog
from ledenadmin.services.assistant import service as assistant_service
from ledenadmin.services.assistant.knowledge import (
    KnowledgeChunk,
    fixed_knowledge,
    html_to_text,
)
from ledenadmin.services.assistant.providers import (
    AnthropicAssistantProvider,
    OpenAIAssistantProvider,
    build_assistant_provider,
)
from ledenadmin.services.assistant.service import (
    EMPTY,
    INVALID,
    LIMIT_TOTAL,
    LIMIT_USER,
    MAX_KNOWLEDGE_CHARS,
    REFUSAL,
    UNAVAILABLE,
    AssistantService,
    Block,
    UsageCounter,
    build_assistant,
    parse_answer,
    redact,
    to_blocks,
)
from ledenadmin.services.user_service import UserService
from ledenadmin.tenancy import as_platform

KNOWLEDGE = [
    KnowledgeChunk("leden", "Leden", "Nieuw lid: naam is verplicht.", "/o/x/help#leden"),
    KnowledgeChunk(
        "gebruikers", "Gebruikers", "Uitnodigen via Gebruikers.", "/o/x/help#gebruikers"
    ),
    KnowledgeChunk("techniek", "Techniek", "Werkt in elke browser."),
]
QUESTION = "Hoe nodig ik een penningmeester uit?"


def answer(on_topic=True, text="1. Ga naar Gebruikers.\n2. Kies Uitnodigen.", sources=None):
    return json.dumps(
        {"op_onderwerp": on_topic, "antwoord": text, "bronnen": sources or ["gebruikers"]}
    )


class FakeProvider:
    name = "nep"

    def __init__(self, response: str | None = None, error: Exception | None = None) -> None:
        self.response = answer() if response is None else response
        self.error = error
        self.calls: list[dict] = []

    def complete(self, instructions, question, schema, max_output_tokens) -> str:
        self.calls.append(
            {
                "instructions": instructions,
                "question": question,
                "schema": schema,
                "max_output_tokens": max_output_tokens,
            }
        )
        if self.error:
            raise self.error
        return self.response


def make_user(database, name: str = "vrager") -> int:
    with database.session() as session:
        as_platform(session)
        user = UserService(session).upsert(Identity("dev", name, name))
        session.commit()
        return user.id


def assistant_settings(settings: Settings, **limits) -> Settings:
    return settings.model_copy(update={"assistant_enabled": True, **limits})


@pytest.fixture
def user_id(database) -> int:
    return make_user(database)


def ask(database, service, user_id, question=QUESTION, knowledge=KNOWLEDGE):
    with database.session() as session:
        return service.ask(session, user_id, question, knowledge, "penningmeester")


# ── Configuratie ─────────────────────────────────────────────────────────────


def test_assistant_is_off_by_default_and_needs_external_provider(settings, caplog) -> None:
    assert settings.assistant_enabled is False and settings.assistant_active is False
    assert build_assistant(settings) is None

    enabled_local = assistant_settings(settings)
    with caplog.at_level(logging.WARNING):
        assert build_assistant(enabled_local) is None
    assert "AI_PROVIDER=local" in caplog.text

    external = Settings(
        _env_file=None,
        assistant_enabled=True,
        ai_provider=AIProviderName.OPENAI,
        ai_model="gpt-4.1-mini",
        openai_api_key="sleutel",
        openai_base_url="https://voorbeeld.openai.azure.com/openai/v1/",
    )
    assert external.assistant_active is True
    service = build_assistant(external)
    assert isinstance(service, AssistantService)
    assert isinstance(service._provider, OpenAIAssistantProvider)


def test_limits_have_hard_maximums() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, assistant_daily_limit_per_user=101)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, assistant_max_question_chars=5000)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, assistant_max_output_tokens=5000)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, assistant_daily_limit_total=0)


def test_provider_factory_chooses_anthropic() -> None:
    settings = Settings(
        _env_file=None,
        ai_provider=AIProviderName.ANTHROPIC,
        ai_model="claude-x",
        anthropic_api_key="sleutel",
    )
    assert isinstance(build_assistant_provider(settings), AnthropicAssistantProvider)


# ── Providers ────────────────────────────────────────────────────────────────


def test_openai_provider_uses_strict_schema_and_does_not_store() -> None:
    calls = {}

    def create(**kwargs):
        calls.update(kwargs)
        return SimpleNamespace(output_text=' {"x": 1} ')

    provider = OpenAIAssistantProvider(
        SimpleNamespace(responses=SimpleNamespace(create=create)), "m"
    )
    schema = {"type": "object"}

    assert provider.complete("instructies", "vraag", schema, 321) == '{"x": 1}'
    assert calls["store"] is False
    assert calls["max_output_tokens"] == 321
    assert calls["instructions"] == "instructies" and calls["input"] == "vraag"
    assert calls["text"]["format"] == {
        "type": "json_schema",
        "name": "assistent_antwoord",
        "schema": schema,
        "strict": True,
    }


def test_anthropic_provider_puts_schema_in_system_prompt() -> None:
    calls = {}

    def create(**kwargs):
        calls.update(kwargs)
        return SimpleNamespace(
            content=[
                SimpleNamespace(type="text", text='{"a"'),
                SimpleNamespace(type="text", text=": 1}"),
            ]
        )

    provider = AnthropicAssistantProvider(
        SimpleNamespace(messages=SimpleNamespace(create=create)), "c"
    )

    assert provider.complete("instructies", "vraag", {"type": "object"}, 222) == '{"a": 1}'
    assert calls["max_tokens"] == 222
    assert calls["system"].startswith("instructies") and '"type": "object"' in calls["system"]
    assert calls["messages"] == [{"role": "user", "content": "vraag"}]


# ── Hulpfuncties ─────────────────────────────────────────────────────────────


def test_redact_removes_contact_and_account_details_but_keeps_dates_and_amounts() -> None:
    text = redact(
        "Mail jan.jansen@example.nl of bel +31 6 1234 5678 / 0612345678, IBAN NL91 ABNA 0417 "
        "1643 00, BSN 123456782. Donatie van 09-10-2026 van € 1.234,50 en KVK 1234567."
    )

    for secret in ("jan.jansen", "1234 5678", "0612345678", "ABNA", "123456782", "1234567"):
        assert secret not in text
    for placeholder in ("[e-mailadres]", "[telefoonnummer]", "[IBAN]", "[nummer]"):
        assert placeholder in text
    assert "09-10-2026" in text and "€ 1.234,50" in text


def test_to_blocks_turns_text_into_paragraphs_and_lists() -> None:
    blocks = to_blocks("Zo werkt het:\nin twee stappen.\n\n1. Ga naar Gebruikers.\n2) Kies.\n- tip")

    assert blocks == (
        Block("p", ("Zo werkt het: in twee stappen.",)),
        Block("ol", ("Ga naar Gebruikers.", "Kies.")),
        Block("ul", ("tip",)),
    )


@pytest.mark.parametrize(
    "raw",
    [
        "geen json",
        "[1, 2]",
        "{kapot}",
        '{"op_onderwerp": "ja", "antwoord": "x", "bronnen": []}',
        '{"op_onderwerp": true, "antwoord": 1, "bronnen": []}',
        '{"op_onderwerp": true, "antwoord": "x", "bronnen": "leden"}',
        '{"op_onderwerp": true, "antwoord": "x", "bronnen": [1]}',
        '{"op_onderwerp": true, "antwoord": "x", ',
    ],
)
def test_parse_answer_rejects_anything_but_the_schema(raw) -> None:
    assert parse_answer(raw) is None


def test_parse_answer_accepts_json_with_surrounding_text() -> None:
    raw = 'Hier: {"op_onderwerp": true, "antwoord": " Ja. ", "bronnen": ["leden"]} klaar'
    assert parse_answer(raw) == (True, "Ja.", ["leden"])


def test_html_to_text_keeps_lists_and_drops_tags() -> None:
    html = (
        '<p>Ga naar <a href="/x">Leden</a> &amp; kies.</p><ul><li>Eén</li><li><b>Twee</b></li></ul>'
    )
    assert html_to_text(html) == "Ga naar Leden & kies.\n- Eén\n- Twee"


def test_fixed_knowledge_platform_part_only_for_superadmin() -> None:
    assert [c.id for c in fixed_knowledge(False)] == ["functies", "techniek"]
    assert [c.id for c in fixed_knowledge(True)][-1] == "platform-techniek"
    assert all(c.text for c in fixed_knowledge(True))


# ── Vragen stellen ───────────────────────────────────────────────────────────


def test_answer_with_sources_from_the_given_knowledge_only(settings, database, user_id) -> None:
    provider = FakeProvider(answer(sources=["gebruikers", "onbekend", "gebruikers", "leden"]))
    service = AssistantService(provider, assistant_settings(settings))

    reply = ask(database, service, user_id)

    assert reply.answered and not reply.notice
    assert reply.blocks == (Block("ol", ("Ga naar Gebruikers.", "Kies Uitnodigen.")),)
    assert [s.id for s in reply.sources] == ["gebruikers", "leden"]
    assert reply.remaining == 19
    call = provider.calls[0]
    assert call["max_output_tokens"] == 600
    assert call["schema"]["properties"]["bronnen"]["items"]["enum"] == [
        "leden",
        "gebruikers",
        "techniek",
    ]
    assert call["schema"]["additionalProperties"] is False
    assert QUESTION in call["question"] and call["question"].startswith("Vraag van de gebruiker")
    for expected in ("[id: leden] Leden", "Uitnodigen via Gebruikers.", "penningmeester"):
        assert expected in call["instructions"]
    assert service.canary in call["instructions"]


def test_only_redacted_question_is_sent(settings, database, user_id) -> None:
    provider = FakeProvider()
    service = AssistantService(provider, assistant_settings(settings))

    ask(database, service, user_id, "Waarom krijgt piet@example.nl geen mail?")

    assert "piet@example.nl" not in provider.calls[0]["question"]
    assert "[e-mailadres]" in provider.calls[0]["question"]


@pytest.mark.parametrize(
    "response",
    [
        answer(on_topic=False, text="", sources=["techniek"]),
        answer(text="De code is CTRL-PLACEHOLDER."),
    ],
)
def test_off_topic_or_leaking_answers_are_refused(settings, database, user_id, response) -> None:
    service = AssistantService(FakeProvider(), assistant_settings(settings))
    service._provider.response = response.replace("CTRL-PLACEHOLDER", service.canary)

    reply = ask(database, service, user_id, "Wat is de hoofdstad van Frankrijk?")

    assert reply.refused and reply.notice == REFUSAL and not reply.blocks
    assert reply.remaining == 19


@pytest.mark.parametrize("response", ["kapot", answer(text="   ")])
def test_unusable_answer_gives_fixed_message(settings, database, user_id, response) -> None:
    service = AssistantService(FakeProvider(response), assistant_settings(settings))

    reply = ask(database, service, user_id)

    assert reply.notice == INVALID and not reply.answered and not reply.refused
    assert reply.remaining == 19


def test_provider_failure_is_not_counted_and_not_logged_with_question(
    settings, database, user_id, caplog
) -> None:
    error = RuntimeError(f"timeout bij vraag: {QUESTION}")
    service = AssistantService(FakeProvider(error=error), assistant_settings(settings))

    with caplog.at_level(logging.INFO):
        reply = ask(database, service, user_id)

    assert reply.notice == UNAVAILABLE and reply.remaining == 20
    assert "RuntimeError" in caplog.text and QUESTION not in caplog.text
    with database.session() as session:
        assert UsageCounter(session, settings.tz).used(user_id) == 0


@pytest.mark.parametrize("question", ["", "   ", "?!", "x" * 501])
def test_empty_or_too_long_question_is_not_sent(settings, database, user_id, question) -> None:
    provider = FakeProvider()
    service = AssistantService(provider, assistant_settings(settings))

    reply = ask(database, service, user_id, question)

    assert reply.notice and provider.calls == [] and reply.remaining == 20
    assert reply.notice == EMPTY or "maximaal 500 tekens" in reply.notice


def test_daily_limit_per_user(settings, database, user_id) -> None:
    provider = FakeProvider()
    service = AssistantService(
        provider, assistant_settings(settings, assistant_daily_limit_per_user=2)
    )

    assert ask(database, service, user_id).remaining == 1
    assert ask(database, service, user_id).remaining == 0
    blocked = ask(database, service, user_id)

    assert blocked.notice == LIMIT_USER.format(limit=2) and blocked.remaining == 0
    assert len(provider.calls) == 2
    with database.session() as session:
        assert service.remaining(session, user_id) == 0
        assert service.remaining(session, make_user(database, "ander")) == 2


def test_daily_limit_for_the_whole_platform(settings, database, user_id) -> None:
    provider = FakeProvider()
    service = AssistantService(
        provider, assistant_settings(settings, assistant_daily_limit_total=1)
    )

    ask(database, service, user_id)
    other = ask(database, service, make_user(database, "ander"))

    assert other.notice == LIMIT_TOTAL and len(provider.calls) == 1


def test_old_usage_rows_are_cleaned_up(settings, database, user_id) -> None:
    with database.session() as session:
        session.add(AssistantUsage(day="2000-01-01", user_id=user_id, questions=5))
        session.commit()
        counter = UsageCounter(session, settings.tz)
        counter.add(user_id, 1)

        assert [row.day for row in session.scalars(select(AssistantUsage))] == [counter.today()]
        assert counter.total() == 1


def test_knowledge_is_capped(settings, caplog) -> None:
    service = AssistantService(FakeProvider(), assistant_settings(settings))
    huge = [KnowledgeChunk("groot", "Groot", "x" * (MAX_KNOWLEDGE_CHARS + 500))]

    with caplog.at_level(logging.WARNING):
        instructions = service.instructions(huge, "lid")

    assert "x" * (MAX_KNOWLEDGE_CHARS + 1) not in instructions and "ingekort" in caplog.text


# ── Web ──────────────────────────────────────────────────────────────────────


def enable(client, settings, provider: FakeProvider) -> AssistantService:
    service = AssistantService(provider, assistant_settings(settings))
    client.app.state.assistant = service
    return service


def test_assistant_is_invisible_and_unreachable_when_off(csrf_client) -> None:
    assert csrf_client.app.state.assistant is None
    assert csrf_client.get("/o/standaard/assistent").status_code == 404
    response = csrf_client.post(
        "/o/standaard/assistent",
        data={"assistent_vraag": QUESTION, "csrf_token": csrf_client.csrf},
    )
    assert response.status_code == 404
    assert "/assistent" not in csrf_client.get("/o/standaard/help").text
    assert "/assistent" not in csrf_client.get("/o/standaard/leden").text


def test_menu_help_and_page_when_on(client, settings) -> None:
    enable(client, settings, FakeProvider())

    assert 'href="/o/standaard/assistent"' in client.get("/o/standaard/leden").text
    assert "Vraag het de assistent" in client.get("/o/standaard/help").text
    page = client.get("/o/standaard/assistent")
    assert page.status_code == 200
    assert 'maxlength="500"' in page.text and "Nog 20 van 20 vragen vandaag." in page.text


def test_ask_via_htmx_returns_escaped_answer_fragment(csrf_client, settings) -> None:
    provider = FakeProvider(answer(text="<script>alert(1)</script>\n- Kies <b>Uitnodigen</b>"))
    enable(csrf_client, settings, provider)

    response = csrf_client.post(
        "/o/standaard/assistent",
        data={"assistent_vraag": QUESTION},
        headers={"HX-Request": "true", "X-CSRF-Token": csrf_client.csrf},
    )

    assert response.status_code == 200
    assert "<html" not in response.text
    assert "<script>" not in response.text and "&lt;script&gt;" in response.text
    assert "<li>Kies &lt;b&gt;Uitnodigen&lt;/b&gt;</li>" in response.text
    assert 'href="/o/standaard/help#gebruikers"' in response.text
    assert "Nog 19 van 20 vragen vandaag." in response.text


def test_ask_without_htmx_returns_full_page_and_requires_csrf(csrf_client, settings) -> None:
    enable(csrf_client, settings, FakeProvider())

    page = csrf_client.post(
        "/o/standaard/assistent",
        data={"assistent_vraag": QUESTION, "csrf_token": csrf_client.csrf},
    )
    assert page.status_code == 200 and "<html" in page.text and "Ga naar Gebruikers." in page.text
    assert QUESTION in page.text

    no_token = csrf_client.post("/o/standaard/assistent", data={"assistent_vraag": QUESTION})
    assert no_token.status_code == 403


def test_question_is_not_stored_in_the_audit_log(csrf_client, settings, database) -> None:
    enable(csrf_client, settings, FakeProvider())
    csrf_client.post(
        "/o/standaard/assistent",
        data={"assistent_vraag": "Geheime vraag over Fatima", "csrf_token": csrf_client.csrf},
    )

    with database.session() as session:
        rows = [r for r in session.scalars(select(AuditLog)) if r.path.endswith("/assistent")]
    assert rows and all("Fatima" not in (r.detail or "") for r in rows)


def test_knowledge_follows_role_and_never_contains_member_data(client, settings, database) -> None:
    provider = FakeProvider()
    enable(client, settings, provider)
    org = add_org(database, "stichting-a")
    link_lid(database, org, add_member(database, org, "Jan Geheim", "25"))
    client.cookies.clear()
    client.get("/o/stichting-a/assistent", headers={"X-Dev-User": "lid", "X-Dev-Roles": ""})
    token = client.cookies.get("csrftoken")

    response = client.post(
        "/o/stichting-a/assistent",
        data={"assistent_vraag": "Hoe doneer ik online?", "csrf_token": token},
        headers={"X-Dev-User": "lid", "X-Dev-Roles": ""},
    )

    assert response.status_code == 200
    instructions = provider.calls[0]["instructions"]
    assert "[id: lid]" in instructions and "[id: start]" in instructions
    for hidden in ("[id: instellingen]", "[id: gebruikers]", "[id: platform-techniek]"):
        assert hidden not in instructions
    assert "Jan Geheim" not in instructions and "jangeheim@x.nl" not in instructions
    assert "rol(len): lid." in instructions


def test_superadmin_gets_platform_knowledge_within_the_cap(database, settings) -> None:
    from fastapi.testclient import TestClient

    from ledenadmin.main import create_app

    with_admin = settings.model_copy(update={"superadmin_subjects": "dev|tester"})
    with TestClient(create_app(with_admin, database)) as client:
        provider = FakeProvider()
        enable(client, with_admin, provider)
        client.get("/o/standaard/assistent")
        client.post(
            "/o/standaard/assistent",
            data={"assistent_vraag": QUESTION, "csrf_token": client.cookies.get("csrftoken")},
        )

    instructions = provider.calls[0]["instructions"]
    assert "[id: platform-techniek]" in instructions and "[id: platform]" in instructions
    assert "superadmin (platformbeheer)" in instructions
    knowledge = instructions.split("KENNIS", 1)[1]
    assert len(knowledge) < MAX_KNOWLEDGE_CHARS


def test_service_module_never_logs_question_text(settings, database, user_id, caplog) -> None:
    service = AssistantService(FakeProvider(), assistant_settings(settings))

    with caplog.at_level(logging.DEBUG, logger=assistant_service.logger.name):
        ask(database, service, user_id, "Vraag met Fatima erin")
        service._provider.response = answer(on_topic=False, text="")
        ask(database, service, user_id, "Nog een vraag met Fatima")

    assert "Fatima" not in caplog.text and "beantwoord" in caplog.text
