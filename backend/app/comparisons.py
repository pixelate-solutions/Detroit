from __future__ import annotations

import json
import uuid

from fastapi import HTTPException

from .auth import utc_now
from .database import connect, transaction


def save_comparison(
    user_id: str,
    document_a_id: int,
    document_b_id: int,
    summary: str,
    diff: list[dict],
) -> str:
    comparison_id = str(uuid.uuid4())
    with transaction() as connection:
        connection.execute(
            """INSERT INTO comparisons(
                 id, owner_user_id, document_a_id, document_b_id, summary, diff_json, created_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                comparison_id,
                user_id,
                document_a_id,
                document_b_id,
                summary,
                json.dumps(diff, ensure_ascii=False),
                utc_now(),
            ),
        )
    return comparison_id


def _comparison_payload(row, include_diff: bool = True) -> dict:
    payload = {
        "id": row["id"],
        "document_a": {"id": row["document_a_id"], "title": row["document_a_title"]},
        "document_b": {"id": row["document_b_id"], "title": row["document_b_title"]},
        "summary": row["summary"],
        "created_at": row["created_at"],
    }
    if include_diff:
        try:
            payload["diff"] = json.loads(row["diff_json"])
        except (json.JSONDecodeError, TypeError):
            payload["diff"] = []
    return payload


def list_comparisons(user_id: str) -> list[dict]:
    with connect() as connection:
        rows = connection.execute(
            """SELECT c.*, a.title AS document_a_title, b.title AS document_b_title
               FROM comparisons c
               JOIN documents a ON a.id = c.document_a_id
               JOIN documents b ON b.id = c.document_b_id
               WHERE c.owner_user_id = ? ORDER BY c.created_at DESC""",
            (user_id,),
        ).fetchall()
    return [_comparison_payload(row, include_diff=False) for row in rows]


def get_comparison(comparison_id: str, user_id: str) -> dict:
    with connect() as connection:
        row = connection.execute(
            """SELECT c.*, a.title AS document_a_title, b.title AS document_b_title
               FROM comparisons c
               JOIN documents a ON a.id = c.document_a_id
               JOIN documents b ON b.id = c.document_b_id
               WHERE c.id = ? AND c.owner_user_id = ?""",
            (comparison_id, user_id),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Comparison not found.")
    return _comparison_payload(row)


def delete_comparison(comparison_id: str, user_id: str) -> None:
    with transaction() as connection:
        cursor = connection.execute(
            "DELETE FROM comparisons WHERE id = ? AND owner_user_id = ?",
            (comparison_id, user_id),
        )
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Comparison not found.")
