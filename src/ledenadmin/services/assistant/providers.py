"""Koppelingen met de AI-dienst voor de helpassistent.

Beide providers krijgen de instructies (met de kennis) apart van de vraag, een harde grens
op het aantal antwoordtokens en moeten één JSON-object teruggeven volgens `schema`.
"""

import json
from typing import Protocol

from ledenadmin.config import AIProviderName, Settings


class AssistantProvider(Protocol):
    name: str

    def complete(
        self, instructions: str, question: str, schema: dict, max_output_tokens: int
    ) -> str: ...


class OpenAIAssistantProvider:
    """OpenAI of Azure OpenAI (v1-endpoint) via de Responses API met structured output."""

    name = "openai"

    def __init__(self, client, model: str) -> None:
        self._client = client
        self._model = model

    @classmethod
    def create(cls, api_key: str, model: str, base_url: str | None, timeout: float):
        from openai import OpenAI

        return cls(
            OpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=1), model
        )

    def complete(
        self, instructions: str, question: str, schema: dict, max_output_tokens: int
    ) -> str:
        response = self._client.responses.create(
            model=self._model,
            instructions=instructions,
            input=question,
            max_output_tokens=max_output_tokens,
            # Vragen en antwoorden niet bij de AI-dienst laten bewaren.
            store=False,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "assistent_antwoord",
                    "schema": schema,
                    "strict": True,
                }
            },
        )
        return (response.output_text or "").strip()


class AnthropicAssistantProvider:
    """Anthropic Claude via de Messages API; het schema staat in de instructies."""

    name = "anthropic"

    def __init__(self, client, model: str) -> None:
        self._client = client
        self._model = model

    @classmethod
    def create(cls, api_key: str, model: str, timeout: float):
        from anthropic import Anthropic

        return cls(Anthropic(api_key=api_key, timeout=timeout, max_retries=1), model)

    def complete(
        self, instructions: str, question: str, schema: dict, max_output_tokens: int
    ) -> str:
        message = self._client.messages.create(
            model=self._model,
            max_tokens=max_output_tokens,
            system=(
                f"{instructions}\n\nAntwoord uitsluitend met één JSON-object volgens dit schema, "
                f"zonder andere tekst:\n{json.dumps(schema, ensure_ascii=False)}"
            ),
            messages=[{"role": "user", "content": question}],
        )
        return "".join(
            getattr(block, "text", "") for block in message.content if block.type == "text"
        ).strip()


def build_assistant_provider(settings: Settings) -> AssistantProvider:
    if settings.ai_provider == AIProviderName.ANTHROPIC:
        return AnthropicAssistantProvider.create(
            api_key=settings.anthropic_api_key,
            model=settings.ai_model,
            timeout=settings.ai_timeout_seconds,
        )
    return OpenAIAssistantProvider.create(
        api_key=settings.openai_api_key,
        model=settings.ai_model,
        base_url=settings.openai_base_url,
        timeout=settings.ai_timeout_seconds,
    )
