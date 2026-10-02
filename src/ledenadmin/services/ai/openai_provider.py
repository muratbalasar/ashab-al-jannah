from ledenadmin.services.ai.base import SYSTEM_PROMPT, InsightInput


class OpenAIInsightProvider:
    """OpenAI of een OpenAI-compatibel endpoint (zoals Azure OpenAI v1) via de Responses API."""

    name = "openai"
    external = True

    def __init__(self, client, model: str) -> None:
        self._client = client
        self._model = model

    @classmethod
    def create(cls, api_key: str, model: str, base_url: str | None, timeout: float):
        from openai import OpenAI

        return cls(
            OpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=1), model
        )

    def generate(self, data: InsightInput) -> str:
        response = self._client.responses.create(
            model=self._model,
            instructions=SYSTEM_PROMPT,
            input=data.model_dump_json(),
        )
        text = (response.output_text or "").strip()
        if not text:
            raise RuntimeError("Lege respons van AI-provider")
        return text
