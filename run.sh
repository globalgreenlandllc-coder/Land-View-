#!/usr/bin/env bash
# Start Land-View locally: Flask API (:8000) + Vite UI (:5174) together.
# Usage:  ./run.sh        (Ctrl+C stops both)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; cd "$ROOT"
API_PORT="${PORT:-8000}"; UI_PORT=5174

echo "▸ Land-View launcher"
for p in "$API_PORT" "$UI_PORT"; do
  pids="$(lsof -ti:"$p" 2>/dev/null || true)"
  [ -n "$pids" ] && { echo "  freeing port $p"; kill $pids 2>/dev/null || true; }
done

python3 -c "import flask" >/dev/null 2>&1 || { echo "▸ installing Python deps…"; python3 -m pip install -q -r requirements.txt; }
[ -d web/node_modules ] || { echo "▸ installing UI deps…"; (cd web && npm install --no-audit --no-fund); }

echo "▸ starting API on http://localhost:$API_PORT"
PORT="$API_PORT" python3 server.py >/tmp/landview-api.log 2>&1 &
API_PID=$!
cleanup() { echo; echo "▸ stopping…"; kill "$API_PID" 2>/dev/null || true; [ -n "${UI_PID:-}" ] && kill "$UI_PID" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

healthy=0
for _ in $(seq 1 30); do
  curl -fsS "http://localhost:$API_PORT/api/health" >/dev/null 2>&1 && { healthy=1; break; }
  sleep 0.5
done
if [ "$healthy" != 1 ]; then
  echo "✗ API failed to start — see /tmp/landview-api.log:"; tail -n 20 /tmp/landview-api.log || true
  exit 1
fi

echo "▸ starting UI  on http://localhost:$UI_PORT"
echo; echo "  ➜  Open  http://localhost:$UI_PORT   (Ctrl+C to stop both)"; echo
(cd web && npm run dev) & UI_PID=$!
wait "$UI_PID"
