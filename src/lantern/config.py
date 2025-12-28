from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    llm_base_url: str | None
    llm_api_key: str | None
    llm_model: str
    embed_model: str
    chroma_dir: str
    llm_system_prompt: str


def _get_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value


def load_config() -> Config:
    load_dotenv()

    llm_base_url = _get_env("LANTERN_LLM_BASE_URL")
    llm_api_key = _get_env("LANTERN_LLM_API_KEY")
    llm_model = _get_env("LANTERN_LLM_MODEL", "gpt-4o-mini")
    embed_model = _get_env("LANTERN_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    chroma_dir = _get_env("LANTERN_CHROMA_DIR", "./data/chroma")
    llm_system_prompt: str = (
        "You are a concise assistant. Use the provided context to answer the question. "
        "If the answer is not in the context, say you are unsure."
)


    if chroma_dir is not None:
        chroma_dir = str(Path(chroma_dir))

    return Config(
        llm_base_url=llm_base_url,
        llm_api_key=llm_api_key,
        llm_model=llm_model or "gpt-4o-mini",
        embed_model=embed_model or "sentence-transformers/all-MiniLM-L6-v2",
        chroma_dir=chroma_dir or "./data/chroma",
        llm_system_prompt=llm_system_prompt,
    )

