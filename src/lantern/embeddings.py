from __future__ import annotations

from typing import List

from sentence_transformers import SentenceTransformer


class Embeddings:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model: SentenceTransformer | None = None

    def _load(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(self.model_name, device="cpu")
        return self._model

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        model = self._load()
        vectors = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
        return vectors.tolist()

    def embed_query(self, text: str) -> List[float]:
        return self.embed_texts([text])[0]

