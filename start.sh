#!/bin/bash
# ═══════════════════════════════════════════════════
# Pulse — One-command start
# Usage:  chmod +x start.sh && ./start.sh
# ═══════════════════════════════════════════════════
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
OUTPUT="$ROOT/backend/output/articles_latest.json"
FRONTEND="$ROOT/frontend/index.html"

echo ""
echo "╔══════════════════════════════════════╗"
echo "║     Pulse — AI News Intelligence     ║"
echo "╚══════════════════════════════════════╝"
echo ""

# 1. Install Python deps
echo "▶ Checking Python dependencies…"
pip install -q fastapi "uvicorn[standard]" pydantic feedparser requests \
    newspaper3k readability-lxml beautifulsoup4 lxml python-multipart 2>/dev/null || true
echo "  ✓ Dependencies ready"

# 2. Run pipeline if no articles yet (or older than 6h)
if [ ! -f "$OUTPUT" ] || [ "$(find "$OUTPUT" -mmin +360 2>/dev/null)" ]; then
  echo ""
  if [ ! -f "$OUTPUT" ]; then
    echo "▶ No articles found — running pipeline (first run ~2 min)…"
  else
    echo "▶ Articles older than 6h — refreshing…"
  fi
  cd "$BACKEND"
  python pipeline.py --feeds-limit 5 --no-extraction
  echo "  ✓ Articles collected"
else
  COUNT=$(python3 -c "import json; d=json.load(open('$OUTPUT')); print(len(d.get('articles',[])))" 2>/dev/null || echo "?")
  echo "  ✓ Articles ready ($COUNT articles in cache)"
fi

# 3. Start backend
echo ""
echo "▶ Starting backend on http://localhost:8000 …"
cd "$BACKEND"
export DEV_API_KEY="${DEV_API_KEY:-dev-secret-123}"
export ENABLE_SUMMARIZER="${ENABLE_SUMMARIZER:-false}"
export ARTICLES_PATH="$OUTPUT"

# Kill any existing instance on port 8000
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
sleep 0.5

uvicorn main:app --host 0.0.0.0 --port 8000 --reload --log-level warning &
BACKEND_PID=$!

# Wait until backend is ready (max 15s)
echo "  Waiting for backend to start…"
for i in $(seq 1 15); do
  if curl -s "http://localhost:8000/health" > /dev/null 2>&1; then
    echo "  ✓ Backend is ready!"
    break
  fi
  sleep 1
done

# 4. Open frontend
echo ""
echo "▶ Opening Pulse app…"
echo "  App:      $FRONTEND"
echo "  API:      http://localhost:8000"
echo "  API docs: http://localhost:8000/docs"
echo ""
echo "  Open frontend/index.html in your browser."
echo ""

if command -v open &>/dev/null;     then open "$FRONTEND";
elif command -v xdg-open &>/dev/null; then xdg-open "$FRONTEND";
fi

echo "══════════════════════════════════════════"
echo "  Pulse is running! Press Ctrl+C to stop."
echo "══════════════════════════════════════════"
echo ""

trap "echo ''; echo 'Stopping…'; kill $BACKEND_PID 2>/dev/null; exit 0" INT TERM
wait $BACKEND_PID
