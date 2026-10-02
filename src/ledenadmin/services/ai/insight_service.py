import logging

from ledenadmin.config import AIProviderName, Settings
from ledenadmin.schemas.reports import Insight, Report
from ledenadmin.services.ai.base import InsightInput, InsightProvider
from ledenadmin.services.ai.local_provider import RuleBasedInsightProvider

logger = logging.getLogger(__name__)

NO_DATA = "Onvoldoende gegevens: er zijn geen donaties in de geselecteerde periode."


class InsightService:
    """Maakt trendinzichten; valt terug op de lokale provider als een externe dienst faalt."""

    def __init__(self, provider: InsightProvider, fallback: InsightProvider | None = None) -> None:
        self._provider = provider
        self._fallback = fallback or RuleBasedInsightProvider()

    def generate(self, report: Report) -> Insight:
        period = report.filter.describe_period()
        if report.is_empty:
            return Insight(
                provider=self._provider.name, external=False, period=period, text=NO_DATA
            )

        data = InsightInput.from_report(report)
        try:
            text = self._provider.generate(data)
            return Insight(
                provider=self._provider.name,
                external=self._provider.external,
                period=period,
                text=text,
            )
        except Exception:
            logger.exception(
                "AI-provider '%s' faalde; lokale analyse gebruikt", self._provider.name
            )
            return Insight(
                provider=self._fallback.name,
                external=False,
                period=period,
                text=self._fallback.generate(data),
                warning="Externe AI-dienst niet beschikbaar; lokale analyse getoond.",
            )


def build_insight_provider(settings: Settings) -> InsightProvider:
    match settings.ai_provider:
        case AIProviderName.OPENAI:
            from ledenadmin.services.ai.openai_provider import OpenAIInsightProvider

            return OpenAIInsightProvider.create(
                api_key=settings.openai_api_key,
                model=settings.ai_model,
                base_url=settings.openai_base_url,
                timeout=settings.ai_timeout_seconds,
            )
        case AIProviderName.ANTHROPIC:
            from ledenadmin.services.ai.anthropic_provider import AnthropicInsightProvider

            return AnthropicInsightProvider.create(
                api_key=settings.anthropic_api_key,
                model=settings.ai_model,
                timeout=settings.ai_timeout_seconds,
            )
        case _:
            return RuleBasedInsightProvider()
