#!/usr/bin/env bash
# One-command local demo: no GPU, no Ollama, no network after install.
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3}"
if [ ! -d .venv ]; then "$PYTHON" -m venv .venv; fi
.venv/bin/pip install -q -r backend/requirements.txt
(cd frontend && npm install --silent && npm run build --silent)

export CIVIC_RECORDS_DEMO=1
export CIVIC_RECORDS_AI="${CIVIC_RECORDS_AI:-auto}"
(cd backend && ../.venv/bin/python -m app.seed_demo "$@")
echo "Open http://127.0.0.1:4106 and pick a demo account."
exec .venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 4106
