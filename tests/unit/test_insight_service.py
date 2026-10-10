from datetime import UTC, date, datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from factories import add_donation, add_member
from pydantic import ValidationError

from ledenadmin.config import AIProviderName, Settings
from ledenadmin.schemas.reports import ReportFilter
from ledenadmin.services.ai.anthropic_provider import AnthropicInsightProvider
from ledenadmin.services.ai.base import InsightInput
from ledenadmin.services.ai.gemini_provider import GeminiInsightProvider
from ledenadmin.services.ai.insight_service import (
    NO_DATA,
    InsightService,
    build_insight_provider,
)
from ledenadmin.services.ai.local_provider import RuleBasedInsightProvider
from ledenadmin.services.ai.openai_provider import OpenAIInsightProvider
from ledenadmin.services.report_service import ReportService

AMS = ZoneInfo("Europe/Amsterdam")


class RecordingProvider:
    name = "test"
    external = True

    def __init__(self, fail: bool = False) -> None:
        self.received: list[InsightInput] = []
        self.fail = fail

    def generate(self, data: InsightInput) -> str:
        self.received.append(data)
        if self.fail:
            raise TimeoutError("provider offline")
        return "- trend"


@pytest.fixture
def report(session):
    jan = add_member(session, "Jan Jansen", "jan@example.nl")
    add_donation(session, jan, "40", datetime(2026, 1, 10, tzinfo=UTC), description="Jan contant")
    add_donation(session, jan, "60", datetime(2026, 2, 10, tzinfo=UTC), "Contributie", "Jaarlijks")
    return ReportService(session, AMS).build(
        ReportFilter(start_date=date(2026, 1, 1), end_date=date(2026, 2, 28))
    )


def test_external_provider_only_receives_aggregates(report) -> None:
    provider = RecordingProvider()

    insight = InsightService(provider).generate(report)

    payload = provider.received[0].model_dump_json()
    for personal in ("Jan Jansen", "jan@example.nl", "Jan contant"):
        assert personal not in payload
    assert insight.external is True
    assert insight.period == "01-01-2026 t/m 28-02-2026"


def test_empty_report_does_not_call_provider(session) -> None:
    provider = RecordingProvider()
    empty = ReportService(session, AMS).build(ReportFilter(start_date=date(2020, 1, 1)))

    insight = InsightService(provider).generate(empty)

    assert insight.text == NO_DATA
    assert provider.received == []


def test_failing_provider_falls_back_to_local_analysis(report) -> None:
    insight = InsightService(RecordingProvider(fail=True)).generate(report)

    assert insight.provider == "lokaal"
    assert insight.external is False
    assert insight.warning
    assert "€ 100,00" in insight.text


def test_local_provider_describes_top_category_and_trend(report) -> None:
    text = RuleBasedInsightProvider().generate(InsightInput.from_report(report))

    assert "2 donaties" in text
    assert "'Contributie'" in text and "60%" in text
    assert "2026-02 ten opzichte van 2026-01: stijging van 50%" in text


def test_openai_provider_uses_responses_api(report) -> None:
    calls = {}

    def create(**kwargs):
        calls.update(kwargs)
        return SimpleNamespace(output_text=" - inzicht ")

    client = SimpleNamespace(responses=SimpleNamespace(create=create))
    text = OpenAIInsightProvider(client, "model-x").generate(InsightInput.from_report(report))

    assert text == "- inzicht"
    assert calls["model"] == "model-x"
    assert "Jan Jansen" not in calls["input"]


def test_anthropic_provider_joins_text_blocks(report) -> None:
    blocks = [SimpleNamespace(type="text", text="- a"), SimpleNamespace(type="other")]
    client = SimpleNamespace(
        messages=SimpleNamespace(create=lambda **kwargs: SimpleNamespace(content=blocks))
    )

    text = AnthropicInsightProvider(client, "claude-x").generate(InsightInput.from_report(report))

    assert text == "- a"


def test_gemini_provider_sends_only_aggregates_via_chat_completions(report) -> None:
    calls = {}

    def create(**kwargs):
        calls.update(kwargs)
        message = SimpleNamespace(content=" - trend ")
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    text = GeminiInsightProvider(client, "gemini-x", "minimal").generate(
        InsightInput.from_report(report)
    )

    assert text == "- trend"
    assert calls["model"] == "gemini-x" and calls["reasoning_effort"] == "minimal"
    assert "Jan Jansen" not in calls["messages"][1]["content"]


def test_factory_builds_gemini_provider() -> None:
    settings = Settings(
        _env_file=None, ai_provider=AIProviderName.GEMINI, ai_model="g", gemini_api_key="k"
    )

    assert isinstance(build_insight_provider(settings), GeminiInsightProvider)


def test_empty_external_response_triggers_fallback(report) -> None:
    client = SimpleNamespace(
        responses=SimpleNamespace(create=lambda **kwargs: SimpleNamespace(output_text=""))
    )

    insight = InsightService(OpenAIInsightProvider(client, "m")).generate(report)

    assert insight.provider == "lokaal" and insight.warning


def test_factory_defaults_to_local_provider(settings) -> None:
    assert isinstance(build_insight_provider(settings), RuleBasedInsightProvider)


def test_external_provider_requires_model_and_key() -> None:
    with pytest.raises(ValidationError, match="AI_MODEL"):
        Settings(_env_file=None, ai_provider=AIProviderName.OPENAI, openai_api_key="k")
    with pytest.raises(ValidationError, match="ANTHROPIC_API_KEY"):
        Settings(_env_file=None, ai_provider=AIProviderName.ANTHROPIC, ai_model="m")
