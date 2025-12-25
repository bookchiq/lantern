from __future__ import annotations

from openai import OpenAI

from .config import Config


class LLMNotConfigured(RuntimeError):
    pass


def _ensure_llm_config(config: Config) -> None:
    if not config.llm_base_url:
        raise LLMNotConfigured(
            "No LLM endpoint configured. Set LANTERN_LLM_BASE_URL (and optionally "
            "LANTERN_LLM_API_KEY, LANTERN_LLM_MODEL) in your environment or .env file."
        )


def generate_answer(prompt: str, config: Config) -> str:
    _ensure_llm_config(config)

    client = OpenAI(
        api_key=config.llm_api_key or "local-key",
        base_url=config.llm_base_url,
    )

    response = client.chat.completions.create(
        model=config.llm_model,
        messages=[
            {"role": "system", "content": "You are a concise assistant."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )

    return response.choices[0].message.content.strip()

