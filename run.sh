#!/usr/bin/env bash
# clipbin launcher for macOS / Linux.
#   ./run.sh              start server + clipboard watcher
#   ./run.sh server       server only
#   ./run.sh watch        clipboard watcher only
# Any extra flags are passed straight to run.py (e.g. ./run.sh --port 9000).
set -euo pipefail
cd "$(dirname "$0")"

if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "Python 3 is required but was not found. Install it from https://python.org" >&2
  exit 1
fi

exec "$PY" run.py "$@"
