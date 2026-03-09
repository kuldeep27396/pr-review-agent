from __future__ import annotations

from typing import Any

import httpx

from pr_review_agent.config import Settings


class LLMClient:
    def __init__(self, settings: Settings, logger: Any) -> None:
        self.settings = settings
        self.logger = logger
        self.client = httpx.AsyncClient(timeout=max(10.0, settings.review_timeout_ms / 1000))

    async def aclose(self) -> None:
        await self.client.aclose()

    @property
    def base_url(self) -> str:
        if self.settings.llm_provider == "groq":
            return "https://api.groq.com/openai/v1"
        return "https://api.openai.com/v1"

    def _base_url_for_provider(self, provider: str) -> str:
        if provider == "groq":
            return "https://api.groq.com/openai/v1"
        return "https://api.openai.com/v1"

    async def chat(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int,
        temperature: float = 0.1,
        fallback_model: str | None = None,
    ) -> str:
        providers = [
            (
                self.settings.llm_provider,
                self.settings.api_key,
                model,
            )
        ]
        if self.settings.fallback_llm_provider and self.settings.fallback_api_key:
            providers.append(
                (
                    self.settings.fallback_llm_provider,
                    self.settings.fallback_api_key,
                    fallback_model or model,
                )
            )

        last_error: Exception | None = None
        for index, (provider, api_key, selected_model) in enumerate(providers):
            try:
                return await self._chat_once(
                    provider=provider,
                    api_key=api_key,
                    messages=messages,
                    model=selected_model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
            except Exception as exc:
                last_error = exc
                self.logger.warning(
                    "LLM provider failed provider=%s model=%s fallback=%s",
                    provider,
                    selected_model,
                    index < len(providers) - 1,
                )
        if last_error is not None:
            raise last_error
        raise RuntimeError("No LLM provider configured")

    async def _chat_once(
        self,
        *,
        provider: str,
        api_key: str | None,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> str:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if not model.startswith("o"):
            payload["temperature"] = temperature

        response = await self.client.post(
            f"{self._base_url_for_provider(provider)}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            self.logger.error("LLM request failed: %s", exc.response.text)
            raise

        data = response.json()
        return data["choices"][0]["message"]["content"]
