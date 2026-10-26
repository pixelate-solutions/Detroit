from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from typing import Iterator

from .config import settings


SCHEMA = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS documents (
  id INTEGER PRIMARY KEY,
  filename TEXT NOT NULL,
  title TEXT NOT NULL,
  doc_type TEXT NOT NULL,
  upload_date TEXT NOT NULL,
  full_text TEXT NOT NULL,
  page_count INTEGER NOT NULL,
  file_path TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
  id INTEGER PRIMARY KEY,
  document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  chunk_text TEXT NOT NULL,
  page_number INTEGER NOT NULL,
  char_start INTEGER NOT NULL,
  char_end INTEGER NOT NULL,
  chroma_id TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
  chunk_text,
  content='chunks',
  content_rowid='id',
  tokenize='porter unicode61'
);

CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
  INSERT INTO chunks_fts(rowid, chunk_text) VALUES (new.id, new.chunk_text);
END;
CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
  INSERT INTO chunks_fts(chunks_fts, rowid, chunk_text) VALUES ('delete', old.id, old.chunk_text);
END;
CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
  INSERT INTO chunks_fts(chunks_fts, rowid, chunk_text) VALUES ('delete', old.id, old.chunk_text);
  INSERT INTO chunks_fts(rowid, chunk_text) VALUES (new.id, new.chunk_text);
END;

CREATE TABLE IF NOT EXISTS entities (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  observations TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS relations (
  id INTEGER PRIMARY KEY,
  source_entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  target_entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  relation_type TEXT NOT NULL,
  source_document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS entity_sources (
  entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  PRIMARY KEY(entity_id, document_id)
);

CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL COLLATE NOCASE UNIQUE,
  display_name TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
  id TEXT PRIMARY KEY,
  owner_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversation_messages (
  id TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
  content TEXT NOT NULL,
  reasoning_summary TEXT NOT NULL DEFAULT '',
  trace_json TEXT NOT NULL DEFAULT '[]',
  citations_json TEXT NOT NULL DEFAULT '[]',
  elapsed_ms INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'complete',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversation_shares (
  conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  shared_by_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL,
  PRIMARY KEY(conversation_id, user_id)
);

CREATE TABLE IF NOT EXISTS comparisons (
  id TEXT PRIMARY KEY,
  owner_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  document_a_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  document_b_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  summary TEXT NOT NULL,
  diff_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS file_folders (
  id TEXT PRIMARY KEY,
  owner_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  parent_id TEXT REFERENCES file_folders(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS file_entries (
  owner_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  folder_id TEXT REFERENCES file_folders(id) ON DELETE SET NULL,
  display_name TEXT,
  starred INTEGER NOT NULL DEFAULT 0 CHECK(starred IN (0, 1)),
  trashed INTEGER NOT NULL DEFAULT 0 CHECK(trashed IN (0, 1)),
  updated_at TEXT NOT NULL,
  PRIMARY KEY(owner_user_id, document_id)
);

CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(source_entity_id);
CREATE INDEX IF NOT EXISTS idx_relations_target ON relations(target_entity_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_conversations_owner ON conversations(owner_user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON conversation_messages(conversation_id, created_at);
CREATE INDEX IF NOT EXISTS idx_shares_user ON conversation_shares(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_comparisons_owner ON comparisons(owner_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_file_folders_owner ON file_folders(owner_user_id, parent_id, name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_file_entries_folder ON file_entries(owner_user_id, folder_id, trashed);
CREATE INDEX IF NOT EXISTS idx_file_entries_starred ON file_entries(owner_user_id, starred, trashed);
"""


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(settings.database_path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")
    return connection


def initialize_database() -> None:
    with connect() as connection:
        connection.executescript(SCHEMA)
        message_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(conversation_messages)").fetchall()
        }
        if "reasoning_summary" not in message_columns:
            connection.execute(
                "ALTER TABLE conversation_messages ADD COLUMN reasoning_summary TEXT NOT NULL DEFAULT ''"
            )


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    connection = connect()
    try:
        # Acquire the single SQLite writer slot before any reads in the
        # transaction. Deferred transactions can otherwise deadlock when
        # several file updates read first and then try to become writers.
        connection.execute("BEGIN IMMEDIATE")
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def row_to_document(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "filename": row["filename"],
        "title": row["title"],
        "doc_type": row["doc_type"],
        "upload_date": row["upload_date"],
        "page_count": row["page_count"],
    }


def parse_observations(raw: str) -> list[str]:
    try:
        value = json.loads(raw)
        return value if isinstance(value, list) else []
    except (json.JSONDecodeError, TypeError):
        return []
