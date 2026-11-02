from __future__ import annotations

import os

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

import chromadb
from chromadb.config import Settings as ChromaSettings

from .config import settings


class VectorStore:
    def __init__(self) -> None:
        self.client = chromadb.PersistentClient(
            path=str(settings.chroma_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        from .ai import ai

        self.collection = self.client.get_or_create_collection(
            ai.collection_name, metadata={"hnsw:space": "cosine"}
        )

    def add(self, ids: list[str], texts: list[str], embeddings: list[list[float]], metadatas: list[dict]) -> None:
        self.collection.upsert(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)

    def query(self, embedding: list[float], top_k: int, classifications: list[str] | None = None) -> list[dict]:
        if self.collection.count() == 0:
            return []
        where = {"classification": {"$in": classifications}} if classifications else None
        result = self.collection.query(
            query_embeddings=[embedding], n_results=min(top_k, self.collection.count()), where=where
        )
        rows = []
        for index, chroma_id in enumerate(result["ids"][0]):
            rows.append(
                {
                    "chroma_id": chroma_id,
                    "distance": result["distances"][0][index],
                    "document": result["documents"][0][index],
                    "metadata": result["metadatas"][0][index],
                }
            )
        return rows

    def delete_document(self, document_id: int) -> None:
        self.collection.delete(where={"document_id": document_id})


_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store
