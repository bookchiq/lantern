from __future__ import annotations

import json

from datetime import datetime
from hashlib import sha1
from pathlib import Path
from typing import Iterable, List

from .chunking import chunk_text
from .config import Config
from .documents import Document
from .embeddings import Embeddings
from .vectorstore import get_collection, upsert_documents


SUPPORTED_EXTENSIONS = {".txt", ".md"}


def sanitize_metadata(metadata: dict) -> dict:
    """Sanitize metadata for Chroma.

    Chroma metadata values must be str, int, float, or bool. This function:
    - drops keys with None values
    - coerces lists/tuples/sets into comma-joined strings
    - coerces dicts/other objects into JSON or string representations
    """
    clean: dict = {}

    for key, value in (metadata or {}).items():
        if value is None:
            continue

        if isinstance(value, (str, int, float, bool)):
            clean[key] = value
            continue

        if isinstance(value, (list, tuple, set)):
            parts = [str(v) for v in value if v is not None]
            clean[key] = ", ".join(parts)
            continue

        if isinstance(value, dict):
            try:
                clean[key] = json.dumps(value, ensure_ascii=False, sort_keys=True)
            except Exception:
                clean[key] = str(value)
            continue

        clean[key] = str(value)

    return clean


def load_documents_from_folder(path: Path) -> List[Document]:
    documents: List[Document] = []
    for file_path in path.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        text = file_path.read_text(encoding="utf-8", errors="ignore")
        stat = file_path.stat()
        metadata = {
            "source_path": str(file_path),
            "file_name": file_path.name,
            "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        }
        documents.append(Document(text=text, metadata=metadata))
    return documents


def _chunk_id(source_path: str, chunk_index: int) -> str:
    raw = f"{source_path}:{chunk_index}".encode("utf-8")
    return sha1(raw).hexdigest()


def ingest_documents(
    documents: Iterable[Document],
    embedder: Embeddings,
    config: Config,
    chunk_size: int = 800,
    overlap: int = 100,
    batch_size: int = 64,
) -> int:
    collection = get_collection(config.chroma_dir)

    ids: List[str] = []
    texts: List[str] = []
    metadatas: List[dict] = []
    total_chunks = 0

    def flush() -> None:
        nonlocal ids, texts, metadatas
        if not ids:
            return
        embeddings = embedder.embed_texts(texts)
        upsert_documents(collection, ids, embeddings, texts, metadatas)
        ids, texts, metadatas = [], [], []

    for doc in documents:
        chunks = chunk_text(doc.text, chunk_size=chunk_size, overlap=overlap)
        for index, chunk in enumerate(chunks):
            chunk_id = _chunk_id(doc.metadata.get("source_path", ""), index)
            metadata = dict(doc.metadata)
            metadata.update({"chunk_index": index, "chunk_id": chunk_id})

            ids.append(chunk_id)
            texts.append(chunk)
            metadatas.append(sanitize_metadata(metadata))
            total_chunks += 1

            if len(ids) >= batch_size:
                flush()

    flush()
    return total_chunks


def ingest_folder(path: Path, config: Config) -> int:
    documents = load_documents_from_folder(path)
    embedder = Embeddings(config.embed_model)
    return ingest_documents(documents, embedder, config)
