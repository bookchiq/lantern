from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import chromadb


COLLECTION_NAME = "lantern_docs"


def get_collection(chroma_dir: str):
    Path(chroma_dir).mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(
        path=chroma_dir,
        settings=chromadb.Settings(anonymized_telemetry=False)
    )
    return client.get_or_create_collection(name=COLLECTION_NAME)


def upsert_documents(
    collection,
    ids: List[str],
    embeddings: List[List[float]],
    documents: List[str],
    metadatas: List[Dict[str, Any]],
) -> None:
    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )


def query_collection(
    collection,
    query_embedding: List[float],
    top_k: int = 6,
) -> Dict[str, Any]:
    return collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )
