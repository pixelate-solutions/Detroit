from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import HTTPException

from .auth import utc_now
from .database import connect, transaction


def _clean_name(name: str, kind: str) -> str:
    value = " ".join(name.strip().split())
    if not value or len(value) > 180 or value in {".", ".."} or "/" in value or "\\" in value:
        raise HTTPException(status_code=422, detail=f"Enter a valid {kind} name up to 180 characters.")
    return value


def _require_folder(connection, folder_id: str, user_id: str):
    row = connection.execute(
        "SELECT * FROM file_folders WHERE id = ? AND owner_user_id = ?",
        (folder_id, user_id),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Folder not found.")
    return row


def _ensure_unique_folder(connection, user_id: str, parent_id: str | None, name: str, exclude_id: str | None = None) -> None:
    row = connection.execute(
        """SELECT id FROM file_folders
           WHERE owner_user_id = ? AND parent_id IS ? AND name = ? COLLATE NOCASE AND id IS NOT ?""",
        (user_id, parent_id, name, exclude_id),
    ).fetchone()
    if row is not None:
        raise HTTPException(status_code=409, detail="A folder with that name already exists here.")


def create_folder(user_id: str, name: str, parent_id: str | None) -> dict:
    name = _clean_name(name, "folder")
    folder_id = str(uuid.uuid4())
    now = utc_now()
    with transaction() as connection:
        if parent_id is not None:
            _require_folder(connection, parent_id, user_id)
        _ensure_unique_folder(connection, user_id, parent_id, name)
        connection.execute(
            "INSERT INTO file_folders(id, owner_user_id, parent_id, name, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (folder_id, user_id, parent_id, name, now, now),
        )
    return {"id": folder_id, "name": name, "parent_id": parent_id, "created_at": now, "updated_at": now}


def list_all_folders(user_id: str) -> list[dict]:
    with connect() as connection:
        rows = connection.execute(
            """SELECT f.*,
                      (SELECT count(*) FROM file_folders c WHERE c.parent_id = f.id AND c.owner_user_id = f.owner_user_id) +
                      (SELECT count(*) FROM file_entries e WHERE e.folder_id = f.id AND e.owner_user_id = f.owner_user_id AND e.trashed = 0) AS item_count
               FROM file_folders f WHERE f.owner_user_id = ? ORDER BY f.name COLLATE NOCASE""",
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def update_folder(user_id: str, folder_id: str, fields: set[str], name: str | None, parent_id: str | None) -> dict:
    with transaction() as connection:
        folder = _require_folder(connection, folder_id, user_id)
        next_name = _clean_name(name, "folder") if "name" in fields and name is not None else folder["name"]
        next_parent = parent_id if "parent_id" in fields else folder["parent_id"]
        if next_parent == folder_id:
            raise HTTPException(status_code=422, detail="A folder cannot contain itself.")
        if next_parent is not None:
            _require_folder(connection, next_parent, user_id)
            ancestor = next_parent
            while ancestor is not None:
                if ancestor == folder_id:
                    raise HTTPException(status_code=422, detail="A folder cannot be moved inside one of its descendants.")
                parent = connection.execute(
                    "SELECT parent_id FROM file_folders WHERE id = ? AND owner_user_id = ?",
                    (ancestor, user_id),
                ).fetchone()
                ancestor = parent["parent_id"] if parent else None
        _ensure_unique_folder(connection, user_id, next_parent, next_name, folder_id)
        now = utc_now()
        connection.execute(
            "UPDATE file_folders SET name = ?, parent_id = ?, updated_at = ? WHERE id = ?",
            (next_name, next_parent, now, folder_id),
        )
    return {"id": folder_id, "name": next_name, "parent_id": next_parent, "updated_at": now}


def delete_folder(user_id: str, folder_id: str) -> None:
    with transaction() as connection:
        _require_folder(connection, folder_id, user_id)
        child = connection.execute(
            "SELECT 1 FROM file_folders WHERE parent_id = ? AND owner_user_id = ? LIMIT 1",
            (folder_id, user_id),
        ).fetchone()
        file_row = connection.execute(
            "SELECT 1 FROM file_entries WHERE folder_id = ? AND owner_user_id = ? AND trashed = 0 LIMIT 1",
            (folder_id, user_id),
        ).fetchone()
        if child is not None or file_row is not None:
            raise HTTPException(status_code=409, detail="Move or trash the folder's contents before deleting it.")
        connection.execute("DELETE FROM file_folders WHERE id = ?", (folder_id,))


def _breadcrumbs(connection, folder_id: str | None, user_id: str) -> list[dict]:
    crumbs: list[dict] = []
    current = folder_id
    seen: set[str] = set()
    while current is not None and current not in seen:
        seen.add(current)
        row = _require_folder(connection, current, user_id)
        crumbs.append({"id": row["id"], "name": row["name"]})
        current = row["parent_id"]
    return list(reversed(crumbs))


def _file_payload(row) -> dict:
    path = Path(row["file_path"])
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    extension = path.suffix.lower().lstrip(".") or Path(row["filename"]).suffix.lower().lstrip(".") or "file"
    return {
        "id": row["id"],
        "name": row["display_name"] or row["title"],
        "original_title": row["title"],
        "filename": row["filename"],
        "doc_type": row["doc_type"],
        "extension": extension,
        "size_bytes": size,
        "page_count": row["page_count"],
        "upload_date": row["upload_date"],
        "folder_id": row["folder_id"],
        "starred": bool(row["starred"]),
        "trashed": bool(row["trashed"]),
        "classification": row["classification"],
        "ocr_status": row["ocr_status"],
        "chunk_count": row["chunk_count"],
        "source_unit": row["source_unit"],
        "modified_at": row["entry_updated_at"] or row["upload_date"],
    }


def browse_files(user_id: str, folder_id: str | None, view: str, query: str, allowed: list[str] | None = None) -> dict:
    allowed = allowed or ["public"]
    class_marks = ",".join("?" for _ in allowed)
    query = " ".join(query.strip().split())[:200]
    if view not in {"root", "folder", "starred", "trash", "search"}:
        raise HTTPException(status_code=422, detail="Unknown file view.")
    with connect() as connection:
        if folder_id is not None:
            _require_folder(connection, folder_id, user_id)
        breadcrumbs = _breadcrumbs(connection, folder_id, user_id) if view == "folder" else []
        folder_params: list = [user_id]
        folder_where = "f.owner_user_id = ?"
        if view == "folder":
            folder_where += " AND f.parent_id IS ?"
            folder_params.append(folder_id)
        elif view == "root":
            folder_where += " AND f.parent_id IS NULL"
        elif view == "search" and query:
            folder_where += " AND f.name LIKE ? ESCAPE '\\' COLLATE NOCASE"
            escaped_folder_query = query.replace("%", "\\%").replace("_", "\\_")
            folder_params.append(f"%{escaped_folder_query}%")
        else:
            folder_where += " AND 0"
        folder_rows = connection.execute(
            f"""SELECT f.*,
                       (SELECT count(*) FROM file_folders c WHERE c.parent_id = f.id AND c.owner_user_id = f.owner_user_id) +
                       (SELECT count(*) FROM file_entries e WHERE e.folder_id = f.id AND e.owner_user_id = f.owner_user_id AND e.trashed = 0) AS item_count
                FROM file_folders f WHERE {folder_where} ORDER BY f.name COLLATE NOCASE""",
            folder_params,
        ).fetchall()

        file_params: list = [user_id]
        file_where = "1 = 1"
        if view == "folder":
            file_where = "COALESCE(e.trashed, 0) = 0 AND e.folder_id IS ?"
            file_params.append(folder_id)
        elif view == "root":
            file_where = "COALESCE(e.trashed, 0) = 0 AND e.folder_id IS NULL"
        elif view == "starred":
            file_where = "e.starred = 1 AND e.trashed = 0"
        elif view == "trash":
            file_where = "e.trashed = 1"
        elif view == "search":
            escaped = query.replace("%", "\\%").replace("_", "\\_")
            file_where = "COALESCE(e.trashed, 0) = 0 AND (COALESCE(e.display_name, d.title) LIKE ? ESCAPE '\\' COLLATE NOCASE OR d.filename LIKE ? ESCAPE '\\' COLLATE NOCASE)"
            file_params.extend([f"%{escaped}%", f"%{escaped}%"])
        file_rows = connection.execute(
            f"""SELECT d.*, e.folder_id, e.display_name, COALESCE(e.starred, 0) AS starred,
                       COALESCE(e.trashed, 0) AS trashed, e.updated_at AS entry_updated_at
                FROM documents d
                LEFT JOIN file_entries e ON e.document_id = d.id AND e.owner_user_id = ?
                WHERE ({file_where}) AND d.classification IN ({class_marks})
                ORDER BY d.title COLLATE NOCASE""",
            [*file_params, *allowed],
        ).fetchall()
        total_documents = connection.execute(
            f"SELECT count(*) FROM documents WHERE classification IN ({class_marks})", allowed
        ).fetchone()[0]
        hidden_documents = connection.execute(
            f"SELECT count(*) FROM documents WHERE classification NOT IN ({class_marks})", allowed
        ).fetchone()[0]
        starred_count = connection.execute(
            "SELECT count(*) FROM file_entries WHERE owner_user_id = ? AND starred = 1 AND trashed = 0",
            (user_id,),
        ).fetchone()[0]
        trash_count = connection.execute(
            "SELECT count(*) FROM file_entries WHERE owner_user_id = ? AND trashed = 1",
            (user_id,),
        ).fetchone()[0]
    return {
        "view": view,
        "folder_id": folder_id,
        "breadcrumbs": breadcrumbs,
        "folders": [dict(row) for row in folder_rows],
        "files": [_file_payload(row) for row in file_rows],
        "counts": {
            "documents": total_documents,
            "starred": starred_count,
            "trash": trash_count,
            "hidden_by_policy": hidden_documents,
        },
    }


def update_file(
    user_id: str,
    document_id: int,
    fields: set[str],
    name: str | None,
    folder_id: str | None,
    starred: bool | None,
    trashed: bool | None,
) -> dict:
    with transaction() as connection:
        document = connection.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
        if document is None:
            raise HTTPException(status_code=404, detail="File not found.")
        current = connection.execute(
            "SELECT * FROM file_entries WHERE owner_user_id = ? AND document_id = ?",
            (user_id, document_id),
        ).fetchone()
        values = {
            "display_name": current["display_name"] if current else None,
            "folder_id": current["folder_id"] if current else None,
            "starred": current["starred"] if current else 0,
            "trashed": current["trashed"] if current else 0,
        }
        if "name" in fields:
            values["display_name"] = _clean_name(name or "", "file")
        if "folder_id" in fields:
            if folder_id is not None:
                _require_folder(connection, folder_id, user_id)
            values["folder_id"] = folder_id
        if "starred" in fields:
            values["starred"] = int(bool(starred))
        if "trashed" in fields:
            values["trashed"] = int(bool(trashed))
        now = utc_now()
        connection.execute(
            """INSERT INTO file_entries(owner_user_id, document_id, folder_id, display_name, starred, trashed, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(owner_user_id, document_id) DO UPDATE SET
                 folder_id = excluded.folder_id,
                 display_name = excluded.display_name,
                 starred = excluded.starred,
                 trashed = excluded.trashed,
                 updated_at = excluded.updated_at""",
            (user_id, document_id, values["folder_id"], values["display_name"], values["starred"], values["trashed"], now),
        )
        row = connection.execute(
            """SELECT d.*, e.folder_id, e.display_name, e.starred, e.trashed, e.updated_at AS entry_updated_at
               FROM documents d JOIN file_entries e ON e.document_id = d.id
               WHERE d.id = ? AND e.owner_user_id = ?""",
            (document_id, user_id),
        ).fetchone()
    return _file_payload(row)
