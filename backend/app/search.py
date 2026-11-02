from __future__ import annotations

import re
from collections import defaultdict

from .ai import ai
from .database import connect
from .vector_store import get_vector_store


def _safe_fts_query(query: str) -> str:
    terms = re.findall(r"[\w-]+", query, flags=re.UNICODE)
    return " OR ".join(f'"{term}"' for term in terms[:20])


def _format_result(row, score: float, channel: str) -> dict:
    snippet = row["chunk_text"].strip()
    if len(snippet) > 520:
        snippet = snippet[:517].rsplit(" ", 1)[0] + "…"
    return {
        "chunk_id": row["chunk_id"],
        "document_id": row["document_id"],
        "title": row["title"],
        "doc_type": row["doc_type"],
        "classification": row["classification"],
        "snippet": snippet,
        "text": row["chunk_text"].strip(),
        "page_number": row["page_number"],
        "score": round(max(0.0, min(1.0, score)), 4),
        "matched_by": channel,
    }


def _marks(values: list[str]) -> str:
    return ",".join("?" for _ in values)


def keyword_search(query: str, top_k: int, allowed: list[str]) -> list[dict]:
    fts_query = _safe_fts_query(query)
    if not fts_query or not allowed:
        return []
    with connect() as connection:
        rows = connection.execute(
            f"""SELECT c.id AS chunk_id, c.document_id, c.chunk_text, c.page_number,
                      d.title, d.doc_type, d.classification, bm25(chunks_fts) AS rank
               FROM chunks_fts
               JOIN chunks c ON c.id = chunks_fts.rowid
               JOIN documents d ON d.id = c.document_id
               WHERE chunks_fts MATCH ? AND d.classification IN ({_marks(allowed)})
               ORDER BY rank LIMIT ?""",
            (fts_query, *allowed, top_k),
        ).fetchall()
    if not rows:
        return []
    strengths = [1.0 / (1.0 + max(0.0, abs(float(row["rank"])))) for row in rows]
    best = max(strengths) or 1.0
    return [_format_result(row, strength / best, "keyword") for row, strength in zip(rows, strengths)]


def semantic_search(query: str, top_k: int, allowed: list[str]) -> list[dict]:
    if not allowed:
        return []
    embedding = ai.embed([query])[0]
    vectors = get_vector_store().query(embedding, top_k, allowed)
    if not vectors:
        return []
    chroma_ids = [item["chroma_id"] for item in vectors]
    placeholders = ",".join("?" for _ in chroma_ids)
    with connect() as connection:
        rows = connection.execute(
            f"""SELECT c.id AS chunk_id, c.document_id, c.chunk_text, c.page_number, c.chroma_id,
                       d.title, d.doc_type, d.classification FROM chunks c JOIN documents d ON d.id = c.document_id
                WHERE c.chroma_id IN ({placeholders}) AND d.classification IN ({_marks(allowed)})""",
            [*chroma_ids, *allowed],
        ).fetchall()
    by_id = {row["chroma_id"]: row for row in rows}
    results = []
    for item in vectors:
        if item["chroma_id"] in by_id:
            similarity = 1.0 - float(item["distance"])
            results.append(_format_result(by_id[item["chroma_id"]], similarity, "semantic"))
    return results


def merge_hybrid_results(keyword: list[dict], semantic: list[dict], top_k: int = 8) -> list[dict]:
    merged: dict[int, dict] = {}
    reciprocal: defaultdict[int, float] = defaultdict(float)
    channels: defaultdict[int, set[str]] = defaultdict(set)
    for channel_results in (keyword, semantic):
        for rank, item in enumerate(channel_results, start=1):
            chunk_id = item["chunk_id"]
            reciprocal[chunk_id] += 1.0 / (30 + rank)
            channels[chunk_id].add(item["matched_by"])
            merged.setdefault(chunk_id, item)
    if not merged:
        return []
    highest = max(reciprocal.values())
    ranked = []
    for chunk_id, item in merged.items():
        value = dict(item)
        value["score"] = round(reciprocal[chunk_id] / highest, 4)
        value["matched_by"] = "+".join(sorted(channels[chunk_id]))
        ranked.append(value)
    return sorted(ranked, key=lambda item: item["score"], reverse=True)[:top_k]


def hybrid_search(query: str, allowed: list[str], top_k: int = 8) -> list[dict]:
    keyword = keyword_search(query, max(top_k * 2, 10), allowed)
    semantic = semantic_search(query, max(top_k * 2, 10), allowed)
    return merge_hybrid_results(keyword, semantic, top_k)


def recommend_documents(
    text: str, allowed: list[str], top_k: int = 6, exclude_document_id: int | None = None
) -> list[dict]:
    chunks = semantic_search(text, max(top_k * 4, 16), allowed)
    best: dict[int, dict] = {}
    for item in chunks:
        document_id = item["document_id"]
        if document_id == exclude_document_id:
            continue
        if document_id not in best or item["score"] > best[document_id]["score"]:
            best[document_id] = {
                "document_id": document_id,
                "title": item["title"],
                "doc_type": item["doc_type"],
                "classification": item["classification"],
                "score": item["score"],
                "snippet": item["snippet"],
            }
    return sorted(best.values(), key=lambda item: item["score"], reverse=True)[:top_k]
