from ledenadmin.services.ai.base import SYSTEM_PROMPT, InsightInput


class AnthropicInsightProvider:
    """Anthropic Claude via de Messages API."""

    name = "anthropic"
    external = True

    def __init__(self, client, model: str, max_tokens: int = 600) -> None:
        self._client = client
        self._model = model
        self._max_tokens = max_tokens

    @classmethod
    def create(cls, api_key: str, model: str, timeout: float):
        from anthropic import Anthropic

        return cls(Anthropic(api_key=api_key, timeout=timeout, max_retries=1), model)

    def generate(self, data: InsightInput) -> str:
        message = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": data.model_dump_json()}],
        )
        text = "".join(
            getattr(block, "text", "") for block in message.content if block.type == "text"
        ).strip()
        if not text:
            raise RuntimeError("Lege respons van AI-provider")
        return text
