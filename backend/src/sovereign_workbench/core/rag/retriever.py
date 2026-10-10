"""Retriever facade used by the ``search_documents`` tool."""

from __future__ import annotations

from sovereign_workbench.core.rag.embeddings import get_embedder
from sovereign_workbench.core.rag.store import search
from sovereign_workbench.db.session import session_scope
from sovereign_workbench.schemas.documents import Chunk


class Retriever:
    def search(self, query: str, *, top_k: int = 5) -> list[Chunk]:
        vector = get_embedder().embed_one(query)
        with session_scope() as session:
            return search(session, vector, top_k=top_k)


_retriever: Retriever | None = None


def get_retriever() -> Retriever:
    global _retriever
    if _retriever is None:
        _retriever = Retriever()
    return _retriever
