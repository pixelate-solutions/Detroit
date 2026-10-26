from __future__ import annotations

import difflib
import json
import re
import time
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .auth import (
    authenticate_user,
    clear_session_cookie,
    create_user,
    current_user,
    issue_session,
    revoke_request_session,
    set_session_cookie,
    user_for_request,
)
from .comparisons import delete_comparison, get_comparison, list_comparisons, save_comparison
from .config import settings
from .conversations import (
    add_message,
    conversation_history,
    create_conversation,
    delete_conversation,
    get_conversation,
    list_conversations,
    require_conversation,
    revoke_share,
    share_conversation,
    update_assistant_message,
)
from .database import connect, initialize_database, row_to_document
from .file_browser import (
    browse_files,
    create_folder,
    delete_folder,
    list_all_folders,
    update_file,
    update_folder,
)
from .graph import entities_for_document, get_graph
from .ingestion import save_and_ingest_upload
from .ollama import OllamaUnavailable, ollama
from .search import (
    hybrid_search,
    keyword_search,
    merge_hybrid_results,
    recommend_documents,
    semantic_search,
)


app = FastAPI(title="Detroit Records", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=8, ge=1, le=50)


class ConversationTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=4000)
    history: list[ConversationTurn] = Field(default_factory=list, max_length=12)
    conversation_id: str | None = Field(default=None, max_length=64)


class SignupRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    display_name: str = Field(min_length=2, max_length=80)
    password: str = Field(min_length=10, max_length=256)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class ConversationCreateRequest(BaseModel):
    title: str = Field(default="New conversation", min_length=1, max_length=200)


class ShareRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class CompareRequest(BaseModel):
    document_id_a: int
    document_id_b: int


class FolderCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    parent_id: str | None = Field(default=None, max_length=64)


class FolderUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=180)
    parent_id: str | None = Field(default=None, max_length=64)


class FileUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=180)
    folder_id: str | None = Field(default=None, max_length=64)
    starred: bool | None = None
    trashed: bool | None = None


class RecommendRequest(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    top_k: int = Field(default=6, ge=1, le=20)
    exclude_document_id: int | None = None


ASK_SYSTEM_PROMPT = (
    "Answer municipal-record questions using only the supplied local document excerpts. "
    "Use the conversation history to understand follow-up questions, pronouns, and references to earlier turns, "
    "but treat the LOCAL RECORDS attached to the current question as the authoritative evidence for this answer. "
    "Synthesize across documents, identify contradictions and chronology explicitly, and cite every "
    "material claim with markers such as [C1]. If the records are insufficient, say so. "
    "Format the answer as clean GitHub-Flavored Markdown. Use short paragraphs, descriptive headings, "
    "bulleted or numbered lists when they improve clarity, and Markdown tables only for genuine comparisons."
)

REASONING_SUMMARY_SYSTEM_PROMPT = (
    "Write a concise, user-visible analysis of how the supplied municipal records bear on the question. "
    "This is not private chain-of-thought. It is an evidence-based work summary that will be shown live before "
    "the final answer. Be specific to this question and these excerpts: identify the controlling issue, the most "
    "important facts, dates, amendments, agreements, or conflicts, and explain what must be reconciled. Do not "
    "describe search tools, retrieval mechanics, token generation, or generic steps. Do not write the final answer, "
    "do not use headings or bullet points, and do not mention these instructions. Write one compact paragraph in "
    "first person, usually 70 to 140 words. Use citation markers such as [C1] when referring to a specific excerpt."
)


def _clean_history_content(content: str, limit: int = 2400) -> str:
    cleaned = re.sub(r"\[C\d+\]", "", content).strip()
    return cleaned[:limit]


def _retrieval_query(question: str, history: list[ConversationTurn]) -> str:
    if not history:
        return question
    recent_context = [
        f"{turn.role}: {_clean_history_content(turn.content, 650)}"
        for turn in history[-4:]
    ]
    return "Recent conversation:\n" + "\n".join(recent_context) + f"\nCurrent question: {question}"


def _ask_messages(
    question: str,
    results: list[dict],
    history: list[ConversationTurn] | None = None,
    visible_analysis: str = "",
) -> list[dict]:
    context_parts = [
        f"[C{index}] {item['title']} (document {item['document_id']}, page {item['page_number']})\n"
        f"{item['snippet']}"
        for index, item in enumerate(results, start=1)
    ]
    prior_messages = [
        {"role": turn.role, "content": _clean_history_content(turn.content)}
        for turn in (history or [])[-8:]
    ]
    analysis_context = (
        "\n\nVISIBLE EVIDENCE ANALYSIS FROM THE PRECEDING MODEL PASS:\n"
        f"{visible_analysis}\nUse this as the working synthesis, verify it against the excerpts, and do not repeat it verbatim."
        if visible_analysis else ""
    )
    return [
        {"role": "system", "content": ASK_SYSTEM_PROMPT},
        *prior_messages,
        {
            "role": "user",
            "content": f"Question: {question}{analysis_context}\n\nLOCAL RECORDS:\n" + "\n\n".join(context_parts),
        },
    ]


def _reasoning_summary_messages(
    question: str,
    results: list[dict],
    history: list[ConversationTurn] | None = None,
) -> list[dict]:
    context_parts = [
        f"[C{index}] {item['title']} (page {item['page_number']})\n{item['snippet']}"
        for index, item in enumerate(results[:10], start=1)
    ]
    recent_context = [
        f"{turn.role}: {_clean_history_content(turn.content, 700)}"
        for turn in (history or [])[-4:]
    ]
    conversation_context = (
        "\n\nRECENT CONVERSATION:\n" + "\n".join(recent_context)
        if recent_context else ""
    )
    return [
        {"role": "system", "content": REASONING_SUMMARY_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Question: {question}{conversation_context}\n\nLOCAL RECORD EXCERPTS:\n"
                + "\n\n".join(context_parts)
            ),
        },
    ]


def _citation_payload(results: list[dict], indexes: list[int] | set[int]) -> list[dict]:
    citations = []
    for index in sorted(indexes):
        if 1 <= index <= len(results):
            item = results[index - 1]
            citations.append(
                {
                    "document_id": item["document_id"],
                    "document_title": item["title"],
                    "snippet": item["snippet"],
                    "page_number": item["page_number"],
                    "marker": f"C{index}",
                }
            )
    return citations


def _answer_citations(answer: str, results: list[dict]) -> list[dict]:
    cited_numbers = {int(value) for value in re.findall(r"\[C(\d+)\]", answer)}
    if not cited_numbers:
        cited_numbers = set(range(1, min(3, len(results)) + 1))
    return _citation_payload(results, cited_numbers)


def _stream_line(event_type: str, **payload) -> str:
    return json.dumps({"type": event_type, **payload}, ensure_ascii=False) + "\n"


@app.on_event("startup")
def startup() -> None:
    initialize_database()


@app.middleware("http")
async def authenticate_api_request(request: Request, call_next):
    public_paths = {"/api/health", "/api/auth/signup", "/api/auth/login"}
    if request.method != "OPTIONS" and request.url.path.startswith("/api/") and request.url.path not in public_paths:
        user = user_for_request(request)
        if user is None:
            return JSONResponse(
                status_code=401,
                content={"detail": "Sign in to continue."},
                headers={"Cache-Control": "no-store"},
            )
        request.state.user = user
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.exception_handler(OllamaUnavailable)
async def ollama_error_handler(_, exc: OllamaUnavailable):
    return JSONResponse(status_code=503, content={"detail": str(exc), "local_only": True})


@app.post("/api/auth/signup")
def signup(payload: SignupRequest, request: Request, response: Response) -> dict:
    try:
        user = create_user(payload.email, payload.display_name, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    token = issue_session(user["id"])
    set_session_cookie(response, request, token)
    return {"user": user}


@app.post("/api/auth/login")
def login(payload: LoginRequest, request: Request, response: Response) -> dict:
    user = authenticate_user(payload.email, payload.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    token = issue_session(user["id"])
    set_session_cookie(response, request, token)
    return {"user": user}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response) -> dict:
    revoke_request_session(request)
    clear_session_cookie(response, request)
    return {"ok": True}


@app.get("/api/auth/me")
def me(request: Request) -> dict:
    return {"user": current_user(request)}


@app.get("/api/conversations")
def conversations_index(request: Request) -> dict:
    return {"conversations": list_conversations(current_user(request)["id"])}


@app.post("/api/conversations")
def new_conversation(payload: ConversationCreateRequest, request: Request) -> dict:
    return {"conversation": create_conversation(current_user(request)["id"], payload.title)}


@app.get("/api/conversations/{conversation_id}")
def conversation_show(conversation_id: str, request: Request) -> dict:
    return get_conversation(conversation_id, current_user(request)["id"])


@app.delete("/api/conversations/{conversation_id}")
def conversation_delete(conversation_id: str, request: Request) -> dict:
    delete_conversation(conversation_id, current_user(request)["id"])
    return {"ok": True}


@app.post("/api/conversations/{conversation_id}/shares")
def conversation_share(conversation_id: str, payload: ShareRequest, request: Request) -> dict:
    recipient = share_conversation(conversation_id, current_user(request)["id"], payload.email)
    return {"shared_with": recipient}


@app.delete("/api/conversations/{conversation_id}/shares/{shared_user_id}")
def conversation_unshare(conversation_id: str, shared_user_id: str, request: Request) -> dict:
    revoke_share(conversation_id, current_user(request)["id"], shared_user_id)
    return {"ok": True}


@app.get("/api/comparisons")
def comparisons_index(request: Request) -> dict:
    return {"comparisons": list_comparisons(current_user(request)["id"])}


@app.get("/api/comparisons/{comparison_id}")
def comparison_show(comparison_id: str, request: Request) -> dict:
    return {"comparison": get_comparison(comparison_id, current_user(request)["id"])}


@app.delete("/api/comparisons/{comparison_id}")
def comparison_delete(comparison_id: str, request: Request) -> dict:
    delete_comparison(comparison_id, current_user(request)["id"])
    return {"ok": True}


@app.get("/api/files")
def files_index(
    request: Request,
    folder_id: str | None = None,
    view: str = "root",
    query: str = "",
) -> dict:
    return browse_files(current_user(request)["id"], folder_id, view, query)


@app.get("/api/file-folders")
def folders_index(request: Request) -> dict:
    return {"folders": list_all_folders(current_user(request)["id"])}


@app.post("/api/file-folders")
def folder_create(payload: FolderCreateRequest, request: Request) -> dict:
    return {"folder": create_folder(current_user(request)["id"], payload.name, payload.parent_id)}


@app.patch("/api/file-folders/{folder_id}")
def folder_update(folder_id: str, payload: FolderUpdateRequest, request: Request) -> dict:
    fields = payload.model_fields_set
    if not fields:
        raise HTTPException(status_code=422, detail="Choose a folder property to update.")
    return {
        "folder": update_folder(
            current_user(request)["id"],
            folder_id,
            fields,
            payload.name,
            payload.parent_id,
        )
    }


@app.delete("/api/file-folders/{folder_id}")
def folder_delete(folder_id: str, request: Request) -> dict:
    delete_folder(current_user(request)["id"], folder_id)
    return {"ok": True}


@app.patch("/api/files/{document_id}")
def file_update(document_id: int, payload: FileUpdateRequest, request: Request) -> dict:
    fields = payload.model_fields_set
    if not fields:
        raise HTTPException(status_code=422, detail="Choose a file property to update.")
    return {
        "file": update_file(
            current_user(request)["id"],
            document_id,
            fields,
            payload.name,
            payload.folder_id,
            payload.starred,
            payload.trashed,
        )
    }


@app.get("/api/health")
def health() -> dict:
    with connect() as connection:
        document_count = connection.execute("SELECT count(*) FROM documents").fetchone()[0]
    try:
        local_ai = ollama.health()
    except OllamaUnavailable as exc:
        local_ai = {
            "available": False,
            "error": str(exc),
            "llm_model": settings.llm_model,
            "embedding_model": settings.embedding_model,
        }
    return {"status": "ok", "offline_runtime": True, "document_count": document_count, "local_ai": local_ai}


@app.get("/api/documents")
def list_documents() -> dict:
    with connect() as connection:
        rows = connection.execute("SELECT * FROM documents ORDER BY upload_date DESC, id DESC").fetchall()
    return {"documents": [row_to_document(row) for row in rows]}


@app.get("/api/documents/{document_id}")
def get_document(document_id: int) -> dict:
    with connect() as connection:
        row = connection.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")
    result = row_to_document(row)
    result.update({"full_text": row["full_text"], "entities": entities_for_document(document_id)})
    return result


@app.get("/api/documents/{document_id}/file")
def get_document_file(document_id: int):
    with connect() as connection:
        row = connection.execute("SELECT filename, file_path FROM documents WHERE id = ?", (document_id,)).fetchone()
    if row is None or not Path(row["file_path"]).is_file():
        raise HTTPException(status_code=404, detail="Document file not found")
    return FileResponse(row["file_path"], filename=row["filename"])


@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)) -> dict:
    try:
        return await save_and_ingest_upload(file)
    except OllamaUnavailable:
        raise
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/search")
def search(request: SearchRequest) -> dict:
    return {"query": request.query, "results": hybrid_search(request.query, request.top_k)}


@app.post("/api/ask")
def ask(request: AskRequest) -> dict:
    keyword = keyword_search(request.question, 20)
    semantic = semantic_search(_retrieval_query(request.question, request.history), 20)
    results = merge_hybrid_results(keyword, semantic, 10)
    if not results:
        return {"answer": "I could not find relevant information in the local document collection.", "citations": []}
    answer = ollama.chat(
        _ask_messages(request.question, results, request.history),
        temperature=0.1,
        max_tokens=1800,
    )
    return {"answer": answer, "citations": _answer_citations(answer, results)}


@app.post("/api/ask/stream")
def ask_stream(payload: AskRequest, http_request: Request):
    user_id = current_user(http_request)["id"]
    if payload.conversation_id:
        conversation = require_conversation(payload.conversation_id, user_id, owner_only=True)
        history_rows = conversation_history(payload.conversation_id, user_id)
    else:
        conversation = create_conversation(user_id, payload.question)
        history_rows = []
    history = [ConversationTurn(**item) for item in history_rows]
    conversation_id = conversation["id"]
    add_message(conversation_id, "user", payload.question)
    assistant_message_id = add_message(conversation_id, "assistant", "", status="streaming")

    def generate():
        started = time.monotonic()
        trace_state: list[dict] = []
        reasoning_parts: list[str] = []
        answer_parts: list[str] = []
        final_citations: list[dict] = []
        persisted = False

        def trace_line(**step) -> str:
            index = next((index for index, item in enumerate(trace_state) if item["id"] == step["id"]), None)
            if index is None:
                trace_state.append(step)
            else:
                trace_state[index] = {**trace_state[index], **step}
            return _stream_line("trace", **step)

        def persist(status: str) -> list[dict]:
            nonlocal persisted
            elapsed_ms = round((time.monotonic() - started) * 1000)
            update_assistant_message(
                assistant_message_id,
                "".join(answer_parts),
                "".join(reasoning_parts),
                trace_state,
                final_citations,
                elapsed_ms,
                status,
            )
            persisted = True
            return get_conversation(conversation_id, user_id)["sources"]

        try:
            yield _stream_line(
                "conversation",
                conversation={
                    "id": conversation_id,
                    "title": conversation["title"],
                    "access": "owner",
                },
                assistant_message_id=assistant_message_id,
            )
            retrieval_limit = 20
            yield trace_line(
                id="keyword",
                status="running",
                kind="tool",
                title="Searching Detroit records",
                detail="Looking for exact names, dates, and phrases",
            )
            keyword = keyword_search(payload.question, retrieval_limit)
            yield trace_line(
                id="keyword",
                status="complete",
                kind="tool",
                title="Searched exact language",
                detail=f"Found {len(keyword)} potentially relevant passages",
            )

            yield trace_line(
                id="semantic",
                status="running",
                kind="tool",
                title="Checking the conversation" if history else "Checking related passages",
                detail=(
                    "Using your recent messages to understand this follow-up"
                    if history
                    else "Looking for records that discuss the same topic"
                ),
            )
            semantic = semantic_search(_retrieval_query(payload.question, history), retrieval_limit)
            yield trace_line(
                id="semantic",
                status="complete",
                kind="tool",
                title="Checked the conversation" if history else "Checked related passages",
                detail=(
                    f"Found {len(semantic)} passages related to this conversation"
                    if history
                    else f"Found {len(semantic)} related passages"
                ),
            )

            results = merge_hybrid_results(keyword, semantic, 10)
            document_count = len({item["document_id"] for item in results})
            yield trace_line(
                id="evidence",
                status="complete",
                kind="reading",
                title="Reading the strongest sources",
                detail=f"Reviewing {len(results)} passages across {document_count} municipal records",
                document_count=document_count,
            )
            yield _stream_line(
                "sources",
                citations=_citation_payload(results, list(range(1, min(6, len(results)) + 1))),
            )

            if not results:
                answer = "I could not find relevant information in the local document collection."
                answer_parts.append(answer)
                yield _stream_line("delta", text=answer)
                yield _stream_line("citations", citations=[])
                sources = persist("complete")
                yield _stream_line("conversation_sources", sources=sources)
                yield _stream_line("done", elapsed_ms=round((time.monotonic() - started) * 1000), conversation_id=conversation_id)
                return

            yield trace_line(
                id="reasoning",
                status="running",
                kind="thinking",
                title="Analyzing the evidence",
                detail="Generating a visible evidence analysis for this question",
                document_count=document_count,
            )
            for text in ollama.visible_analysis_stream(
                _reasoning_summary_messages(payload.question, results, history),
                temperature=0.25,
                max_tokens=360,
            ):
                if not text:
                    continue
                reasoning_parts.append(text)
                yield _stream_line("reasoning_delta", text=text)
            yield _stream_line("reasoning_done")
            yield trace_line(
                id="reasoning",
                status="complete",
                kind="thinking",
                title="Analyzed the evidence",
                detail="Completed the visible evidence analysis",
                document_count=document_count,
            )

            writing_started = False
            for event in ollama.chat_stream(
                _ask_messages(payload.question, results, history, "".join(reasoning_parts)),
                temperature=0.1,
                max_tokens=1800,
            ):
                if event["type"] == "reasoning_started":
                    continue
                text = event.get("text", "")
                if not text:
                    continue
                if not writing_started:
                    writing_started = True
                    yield trace_line(
                        id="writing",
                        status="running",
                        kind="writing",
                        title="Writing the answer",
                        detail="Streaming the cited response as it is generated",
                        document_count=document_count,
                    )
                answer_parts.append(text)
                yield _stream_line("delta", text=text)

            answer = "".join(answer_parts)
            yield trace_line(
                id="writing",
                status="complete",
                kind="writing",
                title="Finished the answer",
                detail=f"Completed in {time.monotonic() - started:.1f} seconds",
                document_count=document_count,
            )
            final_citations.extend(_answer_citations("".join(reasoning_parts) + "\n" + answer, results))
            yield _stream_line("citations", citations=final_citations)
            sources = persist("complete")
            yield _stream_line("conversation_sources", sources=sources)
            yield _stream_line("done", elapsed_ms=round((time.monotonic() - started) * 1000), conversation_id=conversation_id)
        except OllamaUnavailable as exc:
            persist("error")
            yield _stream_line("error", message=str(exc))
        except Exception as exc:
            persist("error")
            yield _stream_line("error", message=f"The local answer stream stopped: {exc}")
        finally:
            if not persisted:
                update_assistant_message(
                    assistant_message_id,
                    "".join(answer_parts),
                    "".join(reasoning_parts),
                    trace_state,
                    final_citations,
                    round((time.monotonic() - started) * 1000),
                    "stopped",
                )

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-store, no-transform",
            "X-Accel-Buffering": "no",
            "X-Content-Type-Options": "nosniff",
        },
    )


@app.post("/api/compare")
def compare(payload: CompareRequest, request: Request) -> dict:
    with connect() as connection:
        rows = connection.execute(
            "SELECT id, title, full_text FROM documents WHERE id IN (?, ?)",
            (payload.document_id_a, payload.document_id_b),
        ).fetchall()
    by_id = {row["id"]: row for row in rows}
    if payload.document_id_a == payload.document_id_b:
        raise HTTPException(status_code=422, detail="Choose two different records.")
    if payload.document_id_a not in by_id or payload.document_id_b not in by_id:
        raise HTTPException(status_code=404, detail="One or both documents were not found")
    before = by_id[payload.document_id_a]
    after = by_id[payload.document_id_b]
    diff_lines = []
    for line in difflib.ndiff(before["full_text"].splitlines(), after["full_text"].splitlines()):
        prefix = line[:2]
        if prefix == "? ":
            continue
        kind = "added" if prefix == "+ " else "removed" if prefix == "- " else "unchanged"
        diff_lines.append({"type": kind, "text": line[2:]})
    summary = ollama.chat(
        [
            {
                "role": "system",
                "content": (
                    "Compare two versions of a municipal document. Explain only substantive changes, including "
                    "money, dates, obligations, scope, and public impact. Be concise and use bullets."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"ORIGINAL — {before['title']}:\n{before['full_text'][:50000]}\n\n"
                    f"REVISED — {after['title']}:\n{after['full_text'][:50000]}"
                ),
            },
        ],
        temperature=0.1,
        max_tokens=1200,
    )
    comparison_id = save_comparison(
        current_user(request)["id"],
        before["id"],
        after["id"],
        summary,
        diff_lines,
    )
    return {
        "id": comparison_id,
        "document_a": {"id": before["id"], "title": before["title"]},
        "document_b": {"id": after["id"], "title": after["title"]},
        "summary": summary,
        "diff": diff_lines,
    }


@app.post("/api/recommend")
def recommend(request: RecommendRequest) -> dict:
    return {
        "documents": recommend_documents(request.text, request.top_k, request.exclude_document_id)
    }


@app.get("/api/graph")
def graph() -> dict:
    return get_graph()


if settings.frontend_dist.is_dir():
    assets = settings.frontend_dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}")
    def frontend(full_path: str):
        candidate = settings.frontend_dist / full_path
        if candidate.is_file() and settings.frontend_dist in candidate.resolve().parents:
            return FileResponse(candidate)
        return FileResponse(settings.frontend_dist / "index.html")
