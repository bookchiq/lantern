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
    asana_pat: str | None
    asana_workspace_gid: str | None
    asana_project_gid: str | None
    asana_user_gid: str | None
    asana_limit: int


def _get_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value


def _get_env_int(name: str, default: int) -> int:
    value = _get_env(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"Invalid integer for {name}: {value}") from exc


def load_config() -> Config:
    load_dotenv()

    llm_base_url = _get_env("LANTERN_LLM_BASE_URL")
    llm_api_key = _get_env("LANTERN_LLM_API_KEY")
    llm_model = _get_env("LANTERN_LLM_MODEL", "gpt-4o-mini")
    embed_model = _get_env("LANTERN_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    chroma_dir = _get_env("LANTERN_CHROMA_DIR", "./data/chroma")
    llm_system_prompt = (
        "You are a concise assistant. Use the provided context to answer the question. "
        "If the answer is not in the context, say you are unsure."
    )

    asana_pat = _get_env("LANTERN_ASANA_PAT")
    asana_workspace_gid = _get_env("LANTERN_ASANA_WORKSPACE_GID")
    asana_project_gid = _get_env("LANTERN_ASANA_PROJECT_GID")
    asana_user_gid = _get_env("LANTERN_ASANA_USER_GID")
    asana_limit = _get_env_int("LANTERN_ASANA_LIMIT", 200)


    if chroma_dir is not None:
        chroma_dir = str(Path(chroma_dir))

    return Config(
        llm_base_url=llm_base_url,
        llm_api_key=llm_api_key,
        llm_model=llm_model or "gpt-4o-mini",
        embed_model=embed_model or "sentence-transformers/all-MiniLM-L6-v2",
        chroma_dir=chroma_dir or "./data/chroma",
        llm_system_prompt=llm_system_prompt,
        asana_pat=asana_pat,
        asana_workspace_gid=asana_workspace_gid,
        asana_project_gid=asana_project_gid,
        asana_user_gid=asana_user_gid,
        asana_limit=asana_limit,
    )
