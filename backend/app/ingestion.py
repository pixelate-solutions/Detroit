from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import UploadFile

from .ai import ai
from .config import settings
from .database import transaction
from .graph import persist_graph
from .parsing import chunk_document, extract_document, infer_title_and_type
from .rbac import CLASSIFICATIONS
from .vector_store import get_vector_store

ALLOWED_SUFFIXES = {".pdf", ".docx", ".txt", ".md"}


def ingest_path(
    path: Path,
    original_filename: str | None = None,
    classification: str = "internal",
    source_unit: str = "",
    upload_date: str | None = None,
    title: str | None = None,
    doc_type: str | None = None,
) -> dict:
    if classification not in CLASSIFICATIONS:
        raise ValueError("Unknown classification.")
    filename = Path(original_filename or path.name).name
    parsed = extract_document(path)
    if not parsed.full_text.strip():
        raise ValueError("No readable text was found in this document.")
    chunks = chunk_document(parsed)
    if not chunks:
        raise ValueError("The document did not contain enough readable text to index.")
    inferred_title, inferred_type = infer_title_and_type(filename, parsed.full_text)
    title = title or inferred_title
    doc_type = doc_type or inferred_type

    document_id: int | None = None
    vector_store = get_vector_store()
    try:
        # AI calls occur before commit so an unavailable local model cannot leave a half-indexed document.
        embeddings = ai.embed([chunk.text for chunk in chunks])
        extracted_graph = ai.extract_graph(title, parsed.full_text)
        ocr_status = "ocr" if parsed.ocr_used else "native"

        with transaction() as connection:
            cursor = connection.execute(
                """INSERT INTO documents(filename, title, doc_type, upload_date, full_text, page_count, file_path,
                                         classification, ocr_status, chunk_count, source_unit)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    filename,
                    title,
                    doc_type,
                    upload_date or datetime.now(timezone.utc).isoformat(),
                    parsed.full_text,
                    len(parsed.pages),
                    str(path.resolve()),
                    classification,
                    ocr_status,
                    len(chunks),
                    source_unit,
                ),
            )
            document_id = cursor.lastrowid
            chroma_ids: list[str] = []
            metadatas: list[dict] = []
            for index, chunk in enumerate(chunks):
                chroma_id = f"doc-{document_id}-chunk-{index}"
                chroma_ids.append(chroma_id)
                metadatas.append(
                    {
                        "document_id": document_id,
                        "page_number": chunk.page_number,
                        "chunk_index": index,
                        "classification": classification,
                    }
                )
                connection.execute(
                    """INSERT INTO chunks(document_id, chunk_text, page_number, char_start, char_end, chroma_id)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        document_id,
                        chunk.text,
                        chunk.page_number,
                        chunk.char_start,
                        chunk.char_end,
                        chroma_id,
                    ),
                )
            vector_store.add(chroma_ids, [chunk.text for chunk in chunks], embeddings, metadatas)
            entity_count, relation_count = persist_graph(connection, document_id, extracted_graph)
    except Exception:
        if document_id is not None:
            vector_store.delete_document(document_id)
        raise

    return {
        "document_id": document_id,
        "title": title,
        "doc_type": doc_type,
        "page_count": len(parsed.pages),
        "chunk_count": len(chunks),
        "entity_count": entity_count,
        "relation_count": relation_count,
        "ocr_used": parsed.ocr_used,
        "classification": classification,
        "stages": [
            {"name": "parsing", "status": "complete"},
            {"name": "ocr", "status": "complete", "used": parsed.ocr_used},
            {"name": "chunking", "status": "complete", "count": len(chunks)},
            {"name": "embedding", "status": "complete", "count": len(chunks)},
            {"name": "entity extraction", "status": "complete", "count": entity_count},
            {"name": "done", "status": "complete"},
        ],
    }


async def save_and_ingest_upload(upload: UploadFile, classification: str = "internal") -> dict:
    filename = Path(upload.filename or "document").name
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError("Supported file types are PDF, DOCX, TXT, and MD.")
    stored = settings.upload_dir / f"{uuid.uuid4().hex}{suffix}"
    try:
        with stored.open("wb") as output:
            while content := await upload.read(1024 * 1024):
                output.write(content)
        if stored.stat().st_size == 0:
            raise ValueError("The uploaded file is empty.")
        return ingest_path(stored, filename, classification)
    except Exception:
        stored.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()

