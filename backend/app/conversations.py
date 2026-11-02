from __future__ import annotations

import json
import uuid

from fastapi import HTTPException

from .auth import normalize_email, utc_now
from .database import connect, transaction


def _json_list(raw: str) -> list:
    try:
        value = json.loads(raw)
        return value if isinstance(value, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _title_from_question(question: str) -> str:
    title = " ".join(question.strip().split())
    return title if len(title) <= 72 else title[:69].rstrip() + "…"


def _conversation_row(connection, conversation_id: str, user_id: str):
    return connection.execute(
        """SELECT c.*, owner.display_name AS owner_name, owner.email AS owner_email,
                  CASE WHEN c.owner_user_id = ? THEN 'owner' ELSE 'shared' END AS access
           FROM conversations c
           JOIN users owner ON owner.id = c.owner_user_id
           WHERE c.id = ? AND (
             c.owner_user_id = ? OR EXISTS (
               SELECT 1 FROM conversation_shares cs
               WHERE cs.conversation_id = c.id AND cs.user_id = ?
             )
           )""",
        (user_id, conversation_id, user_id, user_id),
    ).fetchone()


def require_conversation(conversation_id: str, user_id: str, owner_only: bool = False) -> dict:
    with connect() as connection:
        row = _conversation_row(connection, conversation_id, user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    result = dict(row)
    if owner_only and result["access"] != "owner":
        raise HTTPException(status_code=403, detail="Shared conversations are read-only.")
    return result


def create_conversation(user_id: str, question: str = "New conversation") -> dict:
    conversation_id = str(uuid.uuid4())
    now = utc_now()
    title = _title_from_question(question)
    with transaction() as connection:
        connection.execute(
            "INSERT INTO conversations(id, owner_user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (conversation_id, user_id, title, now, now),
        )
    return {
        "id": conversation_id,
        "owner_user_id": user_id,
        "title": title,
        "created_at": now,
        "updated_at": now,
        "access": "owner",
    }


def list_conversations(user_id: str) -> list[dict]:
    with connect() as connection:
        rows = connection.execute(
            """SELECT c.id, c.owner_user_id, c.title, c.created_at, c.updated_at,
                      owner.display_name AS owner_name,
                      CASE WHEN c.owner_user_id = ? THEN 'owner' ELSE 'shared' END AS access,
                      (SELECT count(*) FROM conversation_messages cm WHERE cm.conversation_id = c.id) AS message_count,
                      (SELECT count(*) FROM conversation_shares cs2 WHERE cs2.conversation_id = c.id) AS share_count,
                      (SELECT substr(cm2.content, 1, 130) FROM conversation_messages cm2
                       WHERE cm2.conversation_id = c.id ORDER BY cm2.created_at DESC LIMIT 1) AS preview
               FROM conversations c
               JOIN users owner ON owner.id = c.owner_user_id
               WHERE c.owner_user_id = ? OR EXISTS (
                 SELECT 1 FROM conversation_shares cs
                 WHERE cs.conversation_id = c.id AND cs.user_id = ?
               )
               ORDER BY c.updated_at DESC""",
            (user_id, user_id, user_id),
        ).fetchall()
    return [dict(row) for row in rows]


def _ranked_sources(messages: list[dict]) -> list[dict]:
    sources: dict[int, dict] = {}
    first_seen = 0
    for message in messages:
        if message["role"] != "assistant":
            continue
        cited_in_message: set[int] = set()
        for citation in message["citations"]:
            document_id = citation.get("document_id")
            if not isinstance(document_id, int) or document_id in cited_in_message:
                continue
            cited_in_message.add(document_id)
            if document_id not in sources:
                first_seen += 1
                sources[document_id] = {
                    **citation,
                    "usage_count": 0,
                    "first_seen": first_seen,
                }
            sources[document_id]["usage_count"] += 1
            sources[document_id].update({key: value for key, value in citation.items() if value})
    ranked = sorted(sources.values(), key=lambda item: (-item["usage_count"], item["first_seen"]))
    for rank, source in enumerate(ranked, start=1):
        source["rank"] = rank
        source.pop("first_seen", None)
    return ranked


def get_conversation(conversation_id: str, user_id: str) -> dict:
    conversation = require_conversation(conversation_id, user_id)
    with connect() as connection:
        rows = connection.execute(
            "SELECT * FROM conversation_messages WHERE conversation_id = ? ORDER BY created_at, id",
            (conversation_id,),
        ).fetchall()
        share_rows = []
        if conversation["access"] == "owner":
            share_rows = connection.execute(
                """SELECT u.id, u.display_name, u.email, cs.created_at
                   FROM conversation_shares cs JOIN users u ON u.id = cs.user_id
                   WHERE cs.conversation_id = ? ORDER BY u.display_name COLLATE NOCASE""",
                (conversation_id,),
            ).fetchall()
    messages = [
        {
            "id": row["id"],
            "role": row["role"],
            "content": row["content"],
            "reasoning_summary": row["reasoning_summary"],
            "trace": _json_list(row["trace_json"]),
            "citations": _json_list(row["citations_json"]),
            "elapsed": row["elapsed_ms"],
            "status": row["status"],
            "created_at": row["created_at"],
            "error": "",
        }
        for row in rows
    ]
    return {
        "conversation": {
            "id": conversation["id"],
            "title": conversation["title"],
            "owner_user_id": conversation["owner_user_id"],
            "owner_name": conversation["owner_name"],
            "access": conversation["access"],
            "created_at": conversation["created_at"],
            "updated_at": conversation["updated_at"],
        },
        "messages": messages,
        "sources": _ranked_sources(messages),
        "shares": [dict(row) for row in share_rows],
    }


def conversation_history(conversation_id: str, user_id: str) -> list[dict]:
    require_conversation(conversation_id, user_id, owner_only=True)
    with connect() as connection:
        rows = connection.execute(
            """SELECT role, content FROM conversation_messages
               WHERE conversation_id = ? AND content <> '' ORDER BY created_at DESC LIMIT 10""",
            (conversation_id,),
        ).fetchall()
    return [dict(row) for row in reversed(rows)]


def add_message(conversation_id: str, role: str, content: str, status: str = "complete") -> str:
    message_id = str(uuid.uuid4())
    now = utc_now()
    with transaction() as connection:
        connection.execute(
            """INSERT INTO conversation_messages(
                 id, conversation_id, role, content, reasoning_summary, trace_json, citations_json, elapsed_ms, status, created_at
               ) VALUES (?, ?, ?, ?, '', '[]', '[]', 0, ?, ?)""",
            (message_id, conversation_id, role, content, status, now),
        )
        connection.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conversation_id))
    return message_id


def update_assistant_message(
    message_id: str,
    content: str,
    reasoning_summary: str,
    trace: list[dict],
    citations: list[dict],
    elapsed_ms: int,
    status: str,
) -> None:
    now = utc_now()
    with transaction() as connection:
        row = connection.execute(
            "SELECT conversation_id FROM conversation_messages WHERE id = ? AND role = 'assistant'",
            (message_id,),
        ).fetchone()
        if row is None:
            return
        connection.execute(
            """UPDATE conversation_messages
               SET content = ?, reasoning_summary = ?, trace_json = ?, citations_json = ?, elapsed_ms = ?, status = ?
               WHERE id = ?""",
            (
                content,
                reasoning_summary,
                json.dumps(trace, ensure_ascii=False),
                json.dumps(citations, ensure_ascii=False),
                elapsed_ms,
                status,
                message_id,
            ),
        )
        connection.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, row["conversation_id"]))


def share_conversation(conversation_id: str, owner_user_id: str, email: str) -> dict:
    require_conversation(conversation_id, owner_user_id, owner_only=True)
    try:
        email = normalize_email(email)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    with transaction() as connection:
        recipient = connection.execute(
            "SELECT id, display_name, email FROM users WHERE email = ? COLLATE NOCASE",
            (email,),
        ).fetchone()
        if recipient is None:
            raise HTTPException(status_code=404, detail="No user has that email address.")
        if recipient["id"] == owner_user_id:
            raise HTTPException(status_code=422, detail="You already own this conversation.")
        connection.execute(
            """INSERT OR IGNORE INTO conversation_shares(conversation_id, user_id, shared_by_user_id, created_at)
               VALUES (?, ?, ?, ?)""",
            (conversation_id, recipient["id"], owner_user_id, utc_now()),
        )
    return dict(recipient)


def revoke_share(conversation_id: str, owner_user_id: str, shared_user_id: str) -> None:
    require_conversation(conversation_id, owner_user_id, owner_only=True)
    with transaction() as connection:
        connection.execute(
            "DELETE FROM conversation_shares WHERE conversation_id = ? AND user_id = ?",
            (conversation_id, shared_user_id),
        )


def delete_conversation(conversation_id: str, owner_user_id: str) -> None:
    require_conversation(conversation_id, owner_user_id, owner_only=True)
    with transaction() as connection:
        connection.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
