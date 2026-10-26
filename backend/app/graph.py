from __future__ import annotations

import json
from collections import defaultdict

from rapidfuzz import fuzz

from .database import connect, parse_observations


def _find_entity(connection, name: str, entity_type: str) -> int | None:
    candidates = connection.execute(
        "SELECT id, name FROM entities WHERE lower(entity_type) = lower(?)", (entity_type,)
    ).fetchall()
    normalized = " ".join(name.casefold().split())
    for candidate in candidates:
        existing = " ".join(candidate["name"].casefold().split())
        if normalized == existing or fuzz.ratio(normalized, existing) >= 94:
            return candidate["id"]
    return None


def persist_graph(connection, document_id: int, graph: dict) -> tuple[int, int]:
    entity_ids: dict[str, int] = {}
    entity_count = 0
    for item in graph.get("entities", []):
        name = " ".join(str(item.get("name", "")).split()).strip()
        entity_type = str(item.get("entityType", "other")).lower().strip()
        if not name:
            continue
        entity_id = _find_entity(connection, name, entity_type)
        observations = [str(value).strip() for value in item.get("observations", []) if str(value).strip()]
        if entity_id is None:
            cursor = connection.execute(
                "INSERT INTO entities(name, entity_type, observations) VALUES (?, ?, ?)",
                (name, entity_type, json.dumps(observations)),
            )
            entity_id = cursor.lastrowid
            entity_count += 1
        else:
            row = connection.execute("SELECT observations FROM entities WHERE id = ?", (entity_id,)).fetchone()
            merged = parse_observations(row["observations"])
            for observation in observations:
                if observation not in merged:
                    merged.append(observation)
            connection.execute("UPDATE entities SET observations = ? WHERE id = ?", (json.dumps(merged), entity_id))
        entity_ids[name.casefold()] = entity_id
        connection.execute(
            "INSERT OR IGNORE INTO entity_sources(entity_id, document_id) VALUES (?, ?)",
            (entity_id, document_id),
        )

    relation_count = 0
    for relation in graph.get("relations", []):
        source_id = entity_ids.get(str(relation.get("from", "")).casefold())
        target_id = entity_ids.get(str(relation.get("to", "")).casefold())
        if not source_id or not target_id or source_id == target_id:
            continue
        connection.execute(
            """INSERT INTO relations(source_entity_id, target_entity_id, relation_type, source_document_id)
               VALUES (?, ?, ?, ?)""",
            (source_id, target_id, str(relation.get("relationType", "related_to")), document_id),
        )
        relation_count += 1
    return entity_count, relation_count


def get_graph() -> dict:
    with connect() as connection:
        entities = connection.execute("SELECT * FROM entities ORDER BY name").fetchall()
        source_rows = connection.execute(
            """SELECT es.entity_id, d.id, d.title, d.doc_type
               FROM entity_sources es JOIN documents d ON d.id = es.document_id"""
        ).fetchall()
        sources: dict[int, list[dict]] = defaultdict(list)
        for row in source_rows:
            sources[row["entity_id"]].append(
                {"id": row["id"], "title": row["title"], "doc_type": row["doc_type"]}
            )
        id_to_name = {row["id"]: row["name"] for row in entities}
        relations = connection.execute("SELECT * FROM relations ORDER BY id").fetchall()
        return {
            "entities": [
                {
                    "name": row["name"],
                    "entityType": row["entity_type"],
                    "observations": parse_observations(row["observations"]),
                    "sourceDocuments": sources[row["id"]],
                }
                for row in entities
            ],
            "relations": [
                {
                    "from": id_to_name[row["source_entity_id"]],
                    "to": id_to_name[row["target_entity_id"]],
                    "relationType": row["relation_type"],
                    "sourceDocumentId": row["source_document_id"],
                }
                for row in relations
                if row["source_entity_id"] in id_to_name and row["target_entity_id"] in id_to_name
            ],
        }


def entities_for_document(document_id: int) -> list[dict]:
    with connect() as connection:
        rows = connection.execute(
            """SELECT e.* FROM entities e JOIN entity_sources es ON es.entity_id = e.id
               WHERE es.document_id = ? ORDER BY e.entity_type, e.name""",
            (document_id,),
        ).fetchall()
        return [
            {
                "name": row["name"],
                "entityType": row["entity_type"],
                "observations": parse_observations(row["observations"]),
            }
            for row in rows
        ]

