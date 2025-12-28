from __future__ import annotations

import httpx
from openai import OpenAI

from .config import Config


class LLMNotConfigured(RuntimeError):
    pass

_client: OpenAI | None = None

def _get_client(config: Config) -> OpenAI:
    global _client

    if _client is not None:
        return _client

    _ensure_llm_config(config)

    # Force a vanilla httpx client (no proxy kwargs passed through OpenAI internals).
    http_client = httpx.Client(timeout=60.0)

    _client = OpenAI(
        api_key=config.llm_api_key or "local-key",
        base_url=config.llm_base_url,
        http_client=http_client,
    )

    return _client

def _ensure_llm_config(config: Config) -> None:
    if not config.llm_base_url:
        raise LLMNotConfigured(
            "No LLM endpoint configured. Set LANTERN_LLM_BASE_URL (and optionally "
            "LANTERN_LLM_API_KEY, LANTERN_LLM_MODEL) in your environment or .env file."
        )


def generate_answer(prompt: str, config: Config) -> str:
    client = _get_client(config)

    response = client.chat.completions.create(
        model=config.llm_model,
        messages=[
            {"role": "system", "content": config.llm_system_prompt},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )

    return response.choices[0].message.content.strip()
