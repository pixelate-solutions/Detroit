# Detroit Records — Municipal Document Intelligence

Detroit Records is a City of Detroit municipal document intelligence
application. It searches municipal records, answers questions with page-level
citations, compares document versions, extracts a connected knowledge graph,
and ingests new records. The included data is synthetic and
belongs to the fictional City of Rivergate.

The application makes no cloud AI calls and loads no runtime assets from a CDN.
The browser talks only to the local FastAPI process; FastAPI talks only to the
Ollama process on loopback. ChromaDB is embedded and persists to disk, while
SQLite provides document metadata and FTS5 keyword search.

## Prerequisites

- Apple Silicon Mac recommended for local model inference
- Python 3.11 or newer
- Node.js 20 or newer and npm
- [Ollama](https://ollama.com/) installed and running
- Tesseract and Poppler for scanned-PDF OCR

On macOS, install the native OCR tools with:

```bash
brew install tesseract poppler
```

On Debian/Ubuntu:

```bash
sudo apt-get install tesseract-ocr poppler-utils
```

## Model setup

Pull the recommended local LLM and the embedding model before disconnecting the
machine from the internet. `qwen3:14b` is the default because it has current
Ollama distribution and tool support while fitting comfortably on a 24 GB Mac:

```bash
ollama pull qwen3:14b
ollama pull nomic-embed-text
```

Confirm the exact demo machine can load and answer with the model:

```bash
ollama run qwen3:14b
```

The original discovery brief proposed `muse-glimmer:30b-mlx`. If that model is
available in your local Ollama installation, select it without changing code:

```bash
ollama pull muse-glimmer:30b-mlx
export OLLAMA_LLM_MODEL=muse-glimmer:30b-mlx
```

For a smaller fallback on a machine with less memory, use `qwen3:8b`.

The model name is configuration, not application code. `OLLAMA_LLM_MODEL`
selects the chat/extraction model and `OLLAMA_EMBED_MODEL` selects the embedding
model. They default to `qwen3:14b` and `nomic-embed-text`. `OLLAMA_BASE_URL` defaults to
`http://127.0.0.1:11434` and is deliberately rejected if it points at a
non-loopback host.

## Install

From this repository:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

cd frontend
npm install
npm run build
cd ..
```

Every frontend dependency—including React, PDF.js, Three.js, icons, and the 3D
graph renderer—is installed into the project and bundled by Vite. There are no
external fonts, scripts, images, or stylesheets.

## Run and seed

Start Ollama using its desktop app or normal system service. Then start the
combined backend and built frontend:

```bash
source .venv/bin/activate
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000), create your Detroit Records
account, and keep the server running. Every account receives a stable UUID and
its own private conversation history.

In a second terminal, authenticate the seed utility with that account and
ingest all 19 synthetic PDFs through the real upload API:

```bash
source .venv/bin/activate
export DETROIT_RECORDS_SEED_EMAIL='you@detroitmi.gov'
read -s DETROIT_RECORDS_SEED_PASSWORD
export DETROIT_RECORDS_SEED_PASSWORD
python backend/seed.py
```

The password is read without echoing it to the terminal. To remove it from the
shell environment after seeding, run `unset DETROIT_RECORDS_SEED_PASSWORD`.

Seeding is resumable: if a model interruption stops the run, launch the command
again and it uploads only missing seed filenames. Use `--force` only when a
second copy of the whole corpus is intentional.

FastAPI serves the built single-page application, so the demo needs only this
server and Ollama.

For frontend development with hot reload, run this instead in another terminal:

```bash
cd frontend
npm run dev
```

Then open [http://127.0.0.1:5173](http://127.0.0.1:5173); Vite proxies `/api`
to FastAPI on port 8000.

## Demo walkthrough

1. Search for `714 Marquette rear stair`, open a result, and show the highlighted source page.
2. Ask: `What are the current height, setback, and closing-time rules in the Harbor Mixed-Use District?`
3. Ask: `Was the code violation at 714 Marquette Street actually resolved?`
4. Compare the ClearCurrent original agreement with Amendment 1.
5. In the graph, search for `440 Lantern Avenue`. The address connects permit applicant Rivermark Development LLC to unrelated city vendor Northline Civic Services Inc.; no single document states that connection.
6. Upload a new PDF or DOCX and watch each ingestion stage complete. Open it or search for its contents immediately, then revisit the graph.

## API overview

- `POST /api/auth/signup` — create a local user with a unique UUID and sign in
- `POST /api/auth/login` and `POST /api/auth/logout` — manage the local session
- `GET /api/auth/me` — return the current signed-in user
- `GET` / `POST /api/conversations` — list saved and shared chats or start one
- `GET` / `DELETE /api/conversations/{id}` — load or delete a conversation
- `POST /api/conversations/{id}/shares` — share a read-only chat with a registered user
- `GET /api/files` — browse per-user folders, favorites, search results, and Trash
- `POST` / `PATCH` / `DELETE /api/file-folders` — create, rename, move, and remove folders
- `PATCH /api/files/{document_id}` — rename, move, favorite, trash, or restore a record in a user's library
- `GET /api/comparisons` — list a user's saved record comparisons
- `POST /api/documents/upload` — parse, OCR when needed, chunk, embed, and extract graph data
- `POST /api/search` — merged SQLite FTS5 and Chroma semantic ranking
- `POST /api/ask` — local RAG answer with page-level citations
- `POST /api/ask/stream` — generate, persist, and stream a question-specific visible evidence analysis, followed by Markdown answer tokens, citations, and ranked conversation evidence
- `POST /api/compare` — exact text diff, substantive change summary, and saved comparison history
- `POST /api/recommend` — semantic document recommendations
- `GET /api/graph` — entities, relations, observations, and source documents
- `GET /api/health` — collection count and local-model availability

API documentation is available locally at
[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

### Authentication and sharing

Passwords are stored as salted scrypt hashes. Sign-in creates an opaque,
12-hour session whose token is stored only as a SHA-256 hash in SQLite; the
browser receives it in an HttpOnly, SameSite=Strict cookie. The cookie is
automatically marked Secure when Detroit Records is served over HTTPS. For a
production deployment, put the app behind HTTPS and add the organization's
normal identity provider, account recovery, email verification, MFA, audit
logging, and rate limiting.

Conversations and messages persist in SQLite. Owners can delete conversations,
share them with an exact registered email address, and revoke access. Shared
conversations are deliberately read-only. The evidence rail accumulates every
document cited throughout a conversation, counts each document at most once per
assistant turn, and ranks it by number of cited turns (then first appearance).
Each assistant turn also stores its separately generated visible evidence analysis;
the model streams that user-facing summary before it streams the cited answer.

File folders, display names, favorites, and Trash are user-specific organization
metadata. They never move, rename, or delete the underlying shared source file.
Comparison results are also stored per user and can be reopened from the
comparison-history panel.

## Runtime network verification

Build and seed while internet access is available, then disconnect Wi-Fi/Ethernet
and run the walkthrough. It should continue to work because all required assets
and model weights are local.

For a more explicit browser check:

1. Open browser developer tools and select the Network tab.
2. Clear the log and exercise every Detroit Records screen.
3. Verify every request targets `127.0.0.1:8000`, `localhost:5173` in development,
   or a local Vite asset URL. The browser never contacts Ollama directly.

For a backend check on macOS, watch outbound connections while running the demo:

```bash
lsof -i -n -P | grep -E 'uvicorn|ollama'
```

Only loopback listeners/connections should appear. Chroma telemetry is disabled
both in its environment configuration and client settings.

## Troubleshooting

**The header says “Ollama setup needed.”** Start Ollama, verify
`curl http://127.0.0.1:11434/api/tags`, and confirm both configured model names
appear. AI-dependent endpoints return an explicit 503 error and never try a
hosted fallback.

**`muse-glimmer:30b-mlx` cannot be pulled or loaded.** Use the configured
`qwen3:14b` default, or use `qwen3:8b` on a lower-memory machine. Restart
FastAPI after changing `OLLAMA_LLM_MODEL`; the resumable seed command skips
seed files that were already ingested successfully.

**OCR fails on an image-only PDF.** Confirm both `tesseract --version` and
`pdftoppm -v` work in the same shell that starts FastAPI. Native-text PDFs do
not require OCR binaries during parsing.

**Start over with an empty demo collection.** Stop FastAPI, move
`backend/data` somewhere safe, then restart and run `python backend/seed.py`.
The directory contains the SQLite database, Chroma index, and uploaded source
files. Moving it preserves a recoverable backup.

## Data and attribution

Rivergate, its people, organizations, addresses, cases, and events are entirely
fictional demonstration data. The knowledge-graph screen adapts rendering and
interaction patterns from Seth Rose's MIT-licensed Memory Knowledge Graph 3D.
See [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).
