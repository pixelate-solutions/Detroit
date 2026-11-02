from __future__ import annotations

import difflib
import json
import re
import time
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import audit, demo_ai
from .ai import ai, clean_history_content
from .auth import (
    authenticate_user,
    clear_session_cookie,
    create_user,
    current_user,
    issue_session,
    revoke_request_session,
    set_session_cookie,
    user_by_email,
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
from .ollama import OllamaUnavailable
from .rbac import CLASSIFICATIONS, access_policy, allowed_classifications, can, can_view, role_info
from .search import (
    hybrid_search,
    keyword_search,
    merge_hybrid_results,
    recommend_documents,
    semantic_search,
)

app = FastAPI(title="Civic Records AI", version="0.2.0")
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


def _retrieval_query(question: str, history: list[ConversationTurn]) -> str:
    if not history:
        return question
    recent_context = [f"{turn.role}: {clean_history_content(turn.content, 650)}" for turn in history[-4:]]
    return "Recent conversation:\n" + "\n".join(recent_context) + f"\nCurrent question: {question}"


def _allowed(request: Request) -> list[str]:
    return allowed_classifications(current_user(request).get("role", ""))


def _require_document_access(request: Request, row, action: str = "document.view") -> None:
    user = current_user(request)
    if not can_view(user.get("role", ""), row["classification"]):
        audit.log_event(
            user, action, resource_type="document", resource_id=row["id"],
            detail=f"Denied: {row['title']} is {row['classification']}", outcome="denied",
        )
        raise HTTPException(status_code=403, detail="Your role is not cleared for this record's classification.")


def _focused_snippet(item: dict, question: str, limit: int = 340) -> str:
    """Return the passage window that best matches the question, for citation cards and highlighting."""
    text = item.get("text") or item["snippet"]
    if not question:
        return item["snippet"]
    evidence = demo_ai.select_evidence(question, [{**item, "text": text}], limit=2)
    if not evidence:
        return item["snippet"]
    joined = " ".join(sentence for _, sentence, _ in evidence)
    return joined if len(joined) <= limit else joined[: limit - 1].rsplit(" ", 1)[0] + "…"


def _citation_payload(results: list[dict], indexes: list[int] | set[int], question: str = "") -> list[dict]:
    citations = []
    for index in sorted(indexes):
        if 1 <= index <= len(results):
            item = results[index - 1]
            citations.append(
                {
                    "document_id": item["document_id"],
                    "document_title": item["title"],
                    "classification": item.get("classification", ""),
                    "snippet": _focused_snippet(item, question),
                    "page_number": item["page_number"],
                    "marker": f"C{index}",
                }
            )
    return citations


def _answer_citations(answer: str, results: list[dict], question: str = "") -> list[dict]:
    cited_numbers = {int(value) for value in re.findall(r"\[C(\d+)\]", answer)}
    if not cited_numbers:
        cited_numbers = set(range(1, min(3, len(results)) + 1))
    return _citation_payload(results, cited_numbers, question)


def _stream_line(event_type: str, **payload) -> str:
    return json.dumps({"type": event_type, **payload}, ensure_ascii=False) + "\n"


@app.on_event("startup")
def startup() -> None:
    initialize_database()


@app.middleware("http")
async def authenticate_api_request(request: Request, call_next):
    public_paths = {"/api/health", "/api/auth/signup", "/api/auth/login", "/api/demo/accounts", "/api/demo/login"}
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
    audit.log_event(user, "auth.signup")
    return {"user": _user_payload(user)}


@app.post("/api/auth/login")
def login(payload: LoginRequest, request: Request, response: Response) -> dict:
    user = authenticate_user(payload.email, payload.password)
    if user is None:
        audit.log_event({"email": payload.email}, "auth.login", detail="Failed sign-in", outcome="denied")
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    token = issue_session(user["id"])
    set_session_cookie(response, request, token)
    audit.log_event(user, "auth.login")
    return {"user": _user_payload(user)}


def _user_payload(user: dict) -> dict:
    info = role_info(user.get("role", ""))
    return {
        **user,
        "role_label": info["label"],
        "classifications": list(info["classifications"]),
        "permissions": list(info["permissions"]),
    }


DEMO_ACCOUNTS = [
    {"email": "r.alvarez@rivergate-fd.example", "display_name": "Capt. Rosa Alvarez", "role": "fire_officer"},
    {"email": "d.okafor@rivergate-fd.example", "display_name": "Dana Okafor", "role": "records_admin"},
    {"email": "m.chen@rivergate-fd.example", "display_name": "FF Marcus Chen", "role": "firefighter"},
    {"email": "pio@rivergate-fd.example", "display_name": "Jamie Ruiz", "role": "public_info"},
]


@app.get("/api/demo/accounts")
def demo_accounts() -> dict:
    if not settings.demo_mode:
        return {"enabled": False, "accounts": []}
    accounts = []
    for account in DEMO_ACCOUNTS:
        if user_by_email(account["email"]):
            accounts.append({**account, "role_label": role_info(account["role"])["label"]})
    return {"enabled": True, "deployment": settings.deployment_name, "accounts": accounts}


class DemoLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)


@app.post("/api/demo/login")
def demo_login(payload: DemoLoginRequest, request: Request, response: Response) -> dict:
    allowed_emails = {account["email"] for account in DEMO_ACCOUNTS}
    if not settings.demo_mode or payload.email not in allowed_emails:
        raise HTTPException(status_code=404, detail="Demo sign-in is disabled.")
    user = user_by_email(payload.email)
    if user is None:
        raise HTTPException(status_code=404, detail="Run the demo seed first: python -m app.seed_demo")
    token = issue_session(user["id"])
    set_session_cookie(response, request, token)
    audit.log_event(user, "auth.login", detail="Demo sign-in")
    return {"user": _user_payload(user)}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response) -> dict:
    revoke_request_session(request)
    clear_session_cookie(response, request)
    return {"ok": True}


@app.get("/api/auth/me")
def me(request: Request) -> dict:
    return {"user": _user_payload(current_user(request))}


@app.get("/api/access-policy")
def get_access_policy(request: Request) -> dict:
    user = current_user(request)
    with connect() as connection:
        rows = connection.execute(
            "SELECT classification, count(*) AS n FROM documents GROUP BY classification"
        ).fetchall()
    counts = {row["classification"]: row["n"] for row in rows}
    policy = access_policy()
    for item in policy["classifications"]:
        item["document_count"] = counts.get(item["id"], 0)
        item["visible"] = can_view(user.get("role", ""), item["id"])
    return {**policy, "user": _user_payload(user)}


@app.get("/api/audit")
def audit_index(
    request: Request,
    action: str | None = None,
    outcome: str | None = None,
    include_sign_ins: bool = False,
    limit: int = 200,
) -> dict:
    user = current_user(request)
    if not can(user.get("role", ""), "audit:read"):
        return {
            "events": audit.list_events(user_id=user["id"], limit=min(limit, 500)),
            "summary": None,
            "scope": "self",
        }
    return {
        "events": audit.list_events(
            action=action, outcome=outcome, include_sign_ins=include_sign_ins, limit=min(limit, 500)
        ),
        "summary": audit.summary(),
        "scope": "all",
    }


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
    return browse_files(current_user(request)["id"], folder_id, view, query, _allowed(request))


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
    with connect() as connection:
        row = connection.execute("SELECT id, title, classification FROM documents WHERE id = ?", (document_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="File not found.")
    _require_document_access(request, row, "document.update")
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
    return {
        "status": "ok",
        "offline_runtime": True,
        "demo_mode": settings.demo_mode,
        "deployment": settings.deployment_name,
        "document_count": document_count,
        "local_ai": ai.health(),
    }


@app.get("/api/documents")
def list_documents(request: Request) -> dict:
    allowed = _allowed(request)
    marks = ",".join("?" for _ in allowed)
    with connect() as connection:
        rows = connection.execute(
            f"SELECT * FROM documents WHERE classification IN ({marks}) ORDER BY upload_date DESC, id DESC", allowed
        ).fetchall()
        hidden = connection.execute(
            f"SELECT count(*) FROM documents WHERE classification NOT IN ({marks})", allowed
        ).fetchone()[0]
    return {"documents": [row_to_document(row) for row in rows], "hidden_by_policy": hidden}


@app.get("/api/documents/{document_id}")
def get_document(document_id: int, request: Request) -> dict:
    with connect() as connection:
        row = connection.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")
    _require_document_access(request, row)
    audit.log_event(current_user(request), "document.view", resource_type="document", resource_id=document_id, detail=row["title"])
    result = row_to_document(row)
    result.update({"full_text": row["full_text"], "entities": entities_for_document(document_id)})
    return result


@app.get("/api/documents/{document_id}/file")
def get_document_file(document_id: int, request: Request):
    with connect() as connection:
        row = connection.execute(
            "SELECT id, title, classification, filename, file_path FROM documents WHERE id = ?", (document_id,)
        ).fetchone()
    if row is None or not Path(row["file_path"]).is_file():
        raise HTTPException(status_code=404, detail="Document file not found")
    _require_document_access(request, row, "document.download")
    return FileResponse(row["file_path"], filename=row["filename"])


@app.post("/api/documents/upload")
async def upload_document(
    request: Request, file: UploadFile = File(...), classification: str = Form("internal")
) -> dict:
    user = current_user(request)
    if not can(user.get("role", ""), "ingest"):
        audit.log_event(user, "document.ingest", detail=file.filename or "", outcome="denied")
        raise HTTPException(status_code=403, detail="Your role does not permit adding records.")
    if classification not in CLASSIFICATIONS or not can_view(user.get("role", ""), classification):
        raise HTTPException(status_code=422, detail="Choose a classification you are cleared for.")
    try:
        result = await save_and_ingest_upload(file, classification)
        audit.log_event(
            user, "document.ingest", resource_type="document", resource_id=result["document_id"],
            detail=result["title"], metadata={"classification": classification, "ocr": result["ocr_used"]},
        )
        return result
    except OllamaUnavailable:
        raise
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/search")
def search(payload: SearchRequest, request: Request) -> dict:
    results = hybrid_search(payload.query, _allowed(request), payload.top_k)
    audit.log_event(current_user(request), "search", detail=payload.query, metadata={"results": len(results)})
    return {"query": payload.query, "results": results}


@app.post("/api/ask")
def ask(payload: AskRequest, request: Request) -> dict:
    allowed = _allowed(request)
    keyword = keyword_search(payload.question, 20, allowed)
    semantic = semantic_search(_retrieval_query(payload.question, payload.history), 20, allowed)
    results = merge_hybrid_results(keyword, semantic, 10)
    if not results:
        answer, citations = "I could not find relevant information in the records available to your role.", []
    else:
        answer = ai.answer(payload.question, results, [turn.model_dump() for turn in payload.history])
        citations = _answer_citations(answer, results, payload.question)
    audit.log_event(
        current_user(request), "ask", detail=payload.question,
        metadata={"cited_documents": sorted({c["document_id"] for c in citations}), "provider": ai.mode},
    )
    return {"answer": answer, "citations": citations}


@app.post("/api/ask/stream")
def ask_stream(payload: AskRequest, http_request: Request):
    user = current_user(http_request)
    user_id = user["id"]
    allowed = allowed_classifications(user.get("role", ""))
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
                title="Searching department records",
                detail="Looking for exact names, dates, and phrases",
            )
            keyword = keyword_search(payload.question, retrieval_limit, allowed)
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
            semantic = semantic_search(_retrieval_query(payload.question, history), retrieval_limit, allowed)
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
                detail=f"Reviewing {len(results)} passages across {document_count} records",
                document_count=document_count,
            )
            yield _stream_line(
                "sources",
                citations=_citation_payload(results, list(range(1, min(6, len(results)) + 1)), payload.question),
            )

            if not results:
                answer = "I could not find relevant information in the records available to your role."
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
            history_dicts = [turn.model_dump() for turn in history]
            for text in ai.analysis_stream(payload.question, results, history_dicts):
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
            for text in ai.answer_stream(payload.question, results, history_dicts, "".join(reasoning_parts)):
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
            final_citations.extend(_answer_citations(answer, results, payload.question))
            audit.log_event(
                user, "ask", resource_type="conversation", resource_id=conversation_id, detail=payload.question,
                metadata={
                    "cited_documents": sorted({c["document_id"] for c in final_citations}),
                    "provider": ai.mode,
                },
            )
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
            "SELECT id, title, full_text, classification FROM documents WHERE id IN (?, ?)",
            (payload.document_id_a, payload.document_id_b),
        ).fetchall()
    by_id = {row["id"]: row for row in rows}
    if payload.document_id_a == payload.document_id_b:
        raise HTTPException(status_code=422, detail="Choose two different records.")
    if payload.document_id_a not in by_id or payload.document_id_b not in by_id:
        raise HTTPException(status_code=404, detail="One or both documents were not found")
    before = by_id[payload.document_id_a]
    after = by_id[payload.document_id_b]
    _require_document_access(request, before, "compare")
    _require_document_access(request, after, "compare")
    diff_lines = []
    for line in difflib.ndiff(before["full_text"].splitlines(), after["full_text"].splitlines()):
        prefix = line[:2]
        if prefix == "? ":
            continue
        kind = "added" if prefix == "+ " else "removed" if prefix == "- " else "unchanged"
        diff_lines.append({"type": kind, "text": line[2:]})
    summary = ai.compare_summary(dict(before), dict(after), diff_lines)
    audit.log_event(
        current_user(request), "compare", detail=f"{before['title']} vs {after['title']}",
        metadata={"documents": [before["id"], after["id"]]},
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
def recommend(payload: RecommendRequest, request: Request) -> dict:
    return {
        "documents": recommend_documents(payload.text, _allowed(request), payload.top_k, payload.exclude_document_id)
    }


@app.get("/api/graph")
def graph(request: Request) -> dict:
    return get_graph(_allowed(request))


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
