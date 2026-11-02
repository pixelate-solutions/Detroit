"""Append-only audit log of record access, questions, ingestion, and denials."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from .database import connect, transaction


def log_event(
    user: dict | None,
    action: str,
    *,
    resource_type: str = "",
    resource_id: str | int | None = None,
    detail: str = "",
    outcome: str = "allowed",
    metadata: dict | None = None,
) -> None:
    with transaction() as connection:
        connection.execute(
            """INSERT INTO audit_log(id, created_at, user_id, user_email, user_role, action,
                                     resource_type, resource_id, detail, outcome, metadata_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()),
                datetime.now(timezone.utc).isoformat(),
                (user or {}).get("id"),
                (user or {}).get("email", ""),
                (user or {}).get("role", ""),
                action,
                resource_type,
                None if resource_id is None else str(resource_id),
                detail[:500],
                outcome,
                json.dumps(metadata or {}, ensure_ascii=False),
            ),
        )


def list_events(
    *,
    user_id: str | None = None,
    action: str | None = None,
    outcome: str | None = None,
    include_sign_ins: bool = True,
    limit: int = 200,
) -> list[dict]:
    clauses: list[str] = []
    params: list = []
    if not include_sign_ins:
        clauses.append("NOT (action = 'auth.login' AND outcome = 'allowed')")
    if user_id:
        clauses.append("user_id = ?")
        params.append(user_id)
    if action:
        clauses.append("action = ?")
        params.append(action)
    if outcome:
        clauses.append("outcome = ?")
        params.append(outcome)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect() as connection:
        rows = connection.execute(
            f"""SELECT a.*, u.display_name FROM audit_log a LEFT JOIN users u ON u.id = a.user_id
                {where} ORDER BY a.created_at DESC LIMIT ?""",
            (*params, limit),
        ).fetchall()
    events = []
    for row in rows:
        item = dict(row)
        try:
            item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
        except json.JSONDecodeError:
            item["metadata"] = {}
        events.append(item)
    return events


def summary() -> dict:
    with connect() as connection:
        total = connection.execute("SELECT count(*) FROM audit_log").fetchone()[0]
        denied = connection.execute("SELECT count(*) FROM audit_log WHERE outcome = 'denied'").fetchone()[0]
        questions = connection.execute("SELECT count(*) FROM audit_log WHERE action = 'ask'").fetchone()[0]
        views = connection.execute("SELECT count(*) FROM audit_log WHERE action = 'document.view'").fetchone()[0]
    return {"total": total, "denied": denied, "questions": questions, "document_views": views}
