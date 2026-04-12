#!/bin/bash
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "=== Marafone Digital ==="

# Backend
echo "[1/2] Avvio backend..."
cd "$ROOT/game/backend"
uv sync
uv run uvicorn aimaraffa.api:app --reload --port 8000 &
BACKEND_PID=$!
echo "Backend avviato (PID $BACKEND_PID)"

# Frontend
echo "[2/2] Avvio frontend..."
cd "$ROOT/game/frontend"

if [ ! -d "node_modules" ]; then
    echo "Installo dipendenze npm..."
    npm install
fi

npm run dev &
FRONTEND_PID=$!
echo "Frontend avviato (PID $FRONTEND_PID)"

echo ""
echo "=== Apri http://localhost:5173 ==="
echo "Premi CTRL+C per fermare tutto"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
