"""Embedding models.

The default is a dependency-free hashing embedder so a fresh clone works on the
8 GB machine with no downloads. The real retrieval model (bge-small) is opt-in and
loaded lazily. Both satisfy the same interface, so nothing downstream changes.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

from sovereign_workbench.config import get_settings
from sovereign_workbench.observability.logging import get_logger

log = get_logger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class Embedder(Protocol):
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...

    def embed_one(self, text: str) -> list[float]: ...


class HashingEmbedder:
    """Deterministic bag-of-tokens hashing, L2-normalised. No model, no network."""

    def __init__(self, dim: int = 384) -> None:
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_one(t) for t in texts]

    def embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        for token in _TOKEN_RE.findall(text.lower()):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self.dim
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0:
            return vector
        return [v / norm for v in vector]


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer  # lazy, heavy

        self._model = SentenceTransformer(model_name, device="cpu")
        self.dim = int(self._model.get_sentence_embedding_dimension())

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return [list(map(float, v)) for v in vectors]

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]


_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is not None:
        return _embedder
    settings = get_settings()
    if settings.embedding_provider == "sentence-transformers":
        try:
            _embedder = SentenceTransformerEmbedder(settings.embed_model)
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "falling back to hashing embedder",
                extra={"extra_fields": {"error": str(exc)}},
            )
            _embedder = HashingEmbedder()
    else:
        _embedder = HashingEmbedder()
    return _embedder


def reset_embedder() -> None:
    global _embedder
    _embedder = None
