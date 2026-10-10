from ledenadmin.services.ai.base import SYSTEM_PROMPT, InsightInput


class GeminiInsightProvider:
    """Google Gemini via het OpenAI-compatibele endpoint (Chat Completions)."""

    name = "gemini"
    external = True

    def __init__(
        self,
        client,
        model: str,
        reasoning_effort: str | None = None,
        max_tokens: int = 1000,
    ) -> None:
        self._client = client
        self._model = model
        self._reasoning_effort = reasoning_effort
        self._max_tokens = max_tokens

    @classmethod
    def create(
        cls,
        api_key: str,
        model: str,
        base_url: str,
        timeout: float,
        reasoning_effort: str | None,
    ):
        from openai import OpenAI

        return cls(
            OpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=1),
            model,
            reasoning_effort,
        )

    def generate(self, data: InsightInput) -> str:
        extra = {"reasoning_effort": self._reasoning_effort} if self._reasoning_effort else {}
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": data.model_dump_json()},
            ],
            max_tokens=self._max_tokens,
            **extra,
        )
        text = (response.choices[0].message.content or "").strip()
        if not text:
            raise RuntimeError("Lege respons van AI-provider")
        return text
