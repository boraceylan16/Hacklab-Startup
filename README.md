# Pulse — AI News Intelligence

A full-stack, locally-running AI news app.
No paid APIs. No cloud. Just open source.

---

## Project Structure

```
pulse/
├── start.sh                  ← ONE-COMMAND LAUNCHER
├── requirements.txt
├── frontend/
│   └── index.html            ← The full app UI (open this in browser)
└── backend/
    ├── main.py               ← FastAPI server (port 8000)
    ├── pipeline.py           ← RSS → dedupe → extract → JSON
    ├── output/
    │   └── articles_latest.json   ← Pipeline output, read by API
    ├── config/
    │   └── feeds.py          ← RSS feed list (add/remove feeds here)
    └── core/
        ├── models.py
        ├── rss_collector.py
        ├── deduplicator.py
        ├── text_extractor.py
        └── ai_summarizer_draft1.py
```

---

## Quick Start (3 steps)

### Step 1 — Install Python deps
```bash
pip install fastapi "uvicorn[standard]" pydantic feedparser requests \
    newspaper3k readability-lxml beautifulsoup4 lxml python-multipart
```

### Step 2 — Collect articles (run once, then every 6h)
```bash
cd backend
python3 pipeline.py --feeds-limit 5 --no-extraction
# Takes ~1-2 min. Creates: backend/output/articles_latest.json
```

### Step 3 — Start the backend
```bash
cd backend
uvicorn main:app --reload --port 8000
```

Then open **`frontend/index.html`** in your browser. Done!

---

## One-command alternative (macOS/Linux)
```bash
chmod +x start.sh && ./start.sh
```
This does all 3 steps automatically and opens the browser.

---

## How it works

```
RSS Feeds (14 sources)
     ↓
pipeline.py            — Fetch → Deduplicate → Extract text
     ↓
output/articles_latest.json
     ↓
backend/main.py        — FastAPI: /api/v1/news, /api/v1/stats, etc.
     ↓
frontend/index.html    — Reads from API, renders Flashcards + Feed + Saved + Profile
```

---

## Key Features

- **Flashcard mode** — Top 10 articles as swipeable cards with AI summary
- **Feed view** — All articles ranked by importance score (recency × word count)
- **Category filters** — AI / Finance / Tech / Science / World
- **Save articles** — Synced with backend
- **Feedback** — Upvote/downvote affects future ranking (Phase 2)
- **Profile** — Set name, role, industry → personalises "Why this matters" text
- **Dark mode** — Toggle in sidebar
- **Keyboard nav** — ← → arrows, S to save
- **Mobile** — Bottom nav, swipe to navigate cards

---

## Config

### Add/remove RSS feeds
Edit `backend/config/feeds.py` — add dicts with `url`, `source`, `category`.

### Environment variables
```bash
DEV_API_KEY=dev-secret-123    # API key (match in frontend/index.html CONFIG section)
ENABLE_SUMMARIZER=false       # true = use BART AI (downloads ~1.6GB, slow)
ARTICLES_PATH=output/articles_latest.json
RATE_LIMIT_RPM=120
```

### Change backend URL / API key
Top of `frontend/index.html`:
```js
const BACKEND = 'http://localhost:8000';
const API_KEY = 'dev-secret-123';
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Backend status + article count |
| GET | `/api/v1/news` | Paginated ranked articles |
| GET | `/api/v1/articles/{id}` | Single article with full summary |
| POST | `/api/v1/articles/{id}/feedback` | save/unsave/upvote/downvote/skip |
| GET | `/api/v1/saved` | All saved articles |
| GET | `/api/v1/stats` | Category counts + total |
| GET | `/api/v1/flashcards/stream` | SSE stream of top articles |
| GET | `/docs` | Interactive API docs (FastAPI) |

---

## Roadmap

- **Phase 2** — TF-IDF topic classification, entity extraction, real ranking score
- **Phase 3** — User feedback → personalised ranking model
- **Phase 4** — BART summarisation, "Why it matters" AI generation
- **Phase 5** — Scheduler (auto-refresh every 6h), email digest
