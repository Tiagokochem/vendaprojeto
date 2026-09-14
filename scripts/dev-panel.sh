#!/usr/bin/env bash
# Sobe o panel local (sem Docker) para smoke test.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Criou .env a partir de .env.example"
fi
cd apps/panel
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi
export PYTHONPATH="$ROOT/apps/panel:$ROOT/packages"
exec .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port "${PANEL_PORT:-8088}"
