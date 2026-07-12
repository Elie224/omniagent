"""Client LLM multi-provider."""
from omniagent.core.config import settings


class LLMClient:
    """Facade simple sur OpenAI et Anthropic."""

    def __init__(self, provider: str = "openai", model: str | None = None):
        self.provider = provider
        if provider == "openai":
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(api_key=settings.openai_api_key)
            self.model = model or "gpt-4o"
        elif provider == "anthropic":
            from anthropic import AsyncAnthropic
            self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
            self.model = model or "claude-sonnet-4-5"
        else:
            raise ValueError(f"Provider inconnu: {provider}")

    async def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        if self.provider == "openai":
            r = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system},
                         {"role": "user", "content": user}],
                max_tokens=max_tokens,
            )
            return r.choices[0].message.content or ""
        r = await self.client.messages.create(
            model=self.model,
            system=system,
            messages=[{"role": "user", "content": user}],
            max_tokens=max_tokens,
        )
        return r.content[0].text


def get_llm(provider: str = "openai", model: str | None = None) -> LLMClient:
    return LLMClient(provider=provider, model=model)