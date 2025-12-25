from __future__ import annotations

from typing import Iterable, List

from .documents import Document


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> List[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    chunks: List[str] = []
    start = 0
    length = len(text)

    while start < length:
        end = min(start + chunk_size, length)
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk)
        if end >= length:
            break
        start = end - overlap
        if start < 0:
            start = 0

    return chunks


def chunk_documents(documents: Iterable[Document], chunk_size: int = 800, overlap: int = 100) -> List[Document]:
    chunked: List[Document] = []
    for doc in documents:
        for chunk in chunk_text(doc.text, chunk_size=chunk_size, overlap=overlap):
            chunked.append(Document(text=chunk, metadata=dict(doc.metadata)))
    return chunked
