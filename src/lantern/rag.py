from __future__ import annotations

from typing import Any, Dict, List

from .config import Config
from .embeddings import Embeddings
from .vectorstore import get_collection, query_collection
from .llm import generate_answer


def retrieve(
    query: str,
    embedder: Embeddings,
    config: Config,
    top_k: int = 6,
) -> List[Dict[str, Any]]:
    collection = get_collection(config.chroma_dir)
    query_embedding = embedder.embed_query(query)
    results = query_collection(collection, query_embedding, top_k=top_k)

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    hits: List[Dict[str, Any]] = []
    for text, metadata in zip(documents, metadatas):
        hits.append({"text": text, "metadata": metadata})
    return hits


def build_prompt(query: str, hits: List[Dict[str, Any]]) -> str:
    context_lines: List[str] = []
    for idx, hit in enumerate(hits, start=1):
        metadata = hit.get("metadata", {})
        source = metadata.get("source_path") or metadata.get("file_name") or "unknown"
        context_lines.append(f"[{idx}] Source: {source}\n{hit.get('text', '')}")

    context_block = "\n\n".join(context_lines)
    return (
        "You are a helpful assistant. Use ONLY the provided context to answer the question. "
        "If the answer is not in the context, say you don't know.\n\n"
        f"Context:\n{context_block}\n\n"
        f"Question: {query}\n\n"
        "Answer in a short response and include citations like [1]."
    )


def answer_question(query: str, config: Config, top_k: int = 6) -> str:
    embedder = Embeddings(config.embed_model)
    hits = retrieve(query, embedder, config, top_k=top_k)
    prompt = build_prompt(query, hits)
    response = generate_answer(prompt, config)

    if not hits:
        return "I don't know yet - I don't have any ingested context to answer from.\n\nSources:\n(none)"

    sources = []
    for idx, hit in enumerate(hits, start=1):
        metadata = hit.get("metadata", {})
        source = metadata.get("source_path") or metadata.get("file_name") or "unknown"
        sources.append(f"[{idx}] {source}")

    sources_block = "\n".join(sources)
    return f"{response}\n\nSources:\n{sources_block}"

