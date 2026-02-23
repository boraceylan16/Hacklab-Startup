"""
backend/main.py — Pulse News API
Run: uvicorn main:app --reload --port 8000
"""

import os, sys, json, time, asyncio, logging, re
from collections import defaultdict
from datetime import datetime
from typing import Optional
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, Depends, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("pulse")

# ── Config ────────────────────────────────────────────────────────────────────
DEV_API_KEY       = os.getenv("DEV_API_KEY", "dev-secret-123")
ENABLE_SUMMARIZER = os.getenv("ENABLE_SUMMARIZER", "false").lower() == "true"
ARTICLES_PATH     = os.getenv("ARTICLES_PATH", str(Path(__file__).parent / "output" / "articles_latest.json"))
RATE_LIMIT_RPM    = int(os.getenv("RATE_LIMIT_RPM", "120"))

app = FastAPI(title="Pulse API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rate limiter ──────────────────────────────────────────────────────────────
_buckets: dict[str, list[float]] = defaultdict(list)

def _rate_check(ip: str):
    now = time.time()
    hits = [t for t in _buckets[ip] if now - t < 60]
    if len(hits) >= RATE_LIMIT_RPM:
        raise HTTPException(429, "Rate limit exceeded")
    hits.append(now)
    _buckets[ip] = hits

def auth(request: Request):
    _rate_check(request.client.host)
    key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
    if key != DEV_API_KEY:
        raise HTTPException(401, "Invalid API key")

# ── Article loading ───────────────────────────────────────────────────────────
def load_articles() -> list[dict]:
    try:
        with open(ARTICLES_PATH, encoding="utf-8") as f:
            data = json.load(f)
        articles = data.get("articles", [])

        # Score: blend word_count + recency
        now = datetime.utcnow()
        for a in articles:
            wc = a.get("word_count", 0)
            try:
                pub = datetime.fromisoformat(a["published_at"].replace("Z","")) if a.get("published_at") else None
                age_hours = max((now - pub).total_seconds() / 3600, 0.1) if pub else 24
            except:
                age_hours = 24
            # Higher score = more words + more recent
            a["_score"] = (min(wc, 2000) / 200) + (10 / age_hours)

        articles.sort(key=lambda a: a.get("_score", 0), reverse=True)

        # Normalize to 0–10 scale
        max_s = max((a["_score"] for a in articles), default=1)
        for i, a in enumerate(articles):
            a["score"] = round(10 * a["_score"] / max_s, 1)

        return articles
    except FileNotFoundError:
        log.warning(f"No articles at {ARTICLES_PATH} — run: cd backend && python pipeline.py --no-extraction")
        return []
    except Exception as e:
        log.error(f"Error loading articles: {e}")
        return []

# ── Extractive summarizer (no AI needed) ─────────────────────────────────────
def get_summary(text: str) -> dict:
    if ENABLE_SUMMARIZER and text:
        try:
            from core.ai_summarizer_draft1 import summarize
            return summarize(text)
        except Exception as e:
            log.warning(f"AI summarizer failed: {e}")

    # Extractive fallback
    if not text:
        return {"summary": "", "method": "none"}
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    kept = [s for s in sentences if len(s) > 40][:5]
    return {"summary": " ".join(kept) or text[:400], "method": "extractive"}

# ── Schemas ───────────────────────────────────────────────────────────────────
class FeedbackBody(BaseModel):
    action: str  # save | unsave | upvote | downvote | skip

# ── In-memory state ───────────────────────────────────────────────────────────
_feedback: dict[str, list[str]] = defaultdict(list)
_saved:    set[str]             = set()

# ═════════════════════════════════════════════════════════════════════════════
# ROUTES
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/health")
def health():
    articles = load_articles()
    return {
        "status": "ok",
        "articles_loaded": len(articles),
        "articles_path": ARTICLES_PATH,
        "summarizer": ENABLE_SUMMARIZER,
        "ts": datetime.utcnow().isoformat(),
    }


@app.get("/api/v1/news")
def get_news(
    limit:     int  = Query(20, le=100),
    page:      int  = Query(1, ge=1),
    category:  str  = Query(""),
    flashcard: bool = Query(False),
    _: None = Depends(auth),
):
    articles = load_articles()
    if category:
        articles = [a for a in articles if a.get("category","").lower() == category.lower()]
    if flashcard:
        articles = articles[:10]

    total = len(articles)
    start = (page - 1) * limit
    page_arts = articles[start: start + limit]

    return {
        "articles": [{
            "id":            a.get("id", ""),
            "title":         a.get("title", ""),
            "summary":       a.get("summary", "") or a.get("full_text", "")[:300],
            "score":         a.get("score", 0),
            "published_at":  a.get("published_at"),
            "category":      a.get("category", "general"),
            "canonical_url": a.get("canonical_url", ""),
            "source":        a.get("source", ""),
            "top_image":     a.get("top_image", ""),
            "author":        a.get("author", ""),
            "saved":         a.get("id","") in _saved,
        } for a in page_arts],
        "total": total,
        "page": page,
        "limit": limit,
        "has_more": (start + limit) < total,
    }


@app.get("/api/v1/articles/{article_id}")
def get_article(article_id: str, _: None = Depends(auth)):
    article = next((a for a in load_articles() if a.get("id") == article_id), None)
    if not article:
        raise HTTPException(404, "Article not found")

    full_text = article.get("full_text") or article.get("summary", "")
    summary_data = get_summary(full_text)

    return {
        **{k: article.get(k, "") for k in ["id","title","category","canonical_url","source","author","top_image"]},
        "published_at":   article.get("published_at"),
        "score":          article.get("score", 0),
        "summary":        summary_data["summary"],
        "summary_method": summary_data["method"],
        "full_text":      full_text,
        "saved":          article_id in _saved,
    }


@app.post("/api/v1/articles/{article_id}/feedback")
def post_feedback(article_id: str, body: FeedbackBody, _: None = Depends(auth)):
    valid = {"save", "unsave", "upvote", "downvote", "skip"}
    if body.action not in valid:
        raise HTTPException(422, f"action must be one of {valid}")
    if body.action == "save":
        _saved.add(article_id)
    elif body.action == "unsave":
        _saved.discard(article_id)
    _feedback[article_id].append(body.action)
    return {"ok": True, "saved": article_id in _saved}


@app.get("/api/v1/saved")
def get_saved(_: None = Depends(auth)):
    articles = load_articles()
    saved_arts = [a for a in articles if a.get("id") in _saved]
    return {"articles": saved_arts, "total": len(saved_arts)}


@app.get("/api/v1/stats")
def get_stats(_: None = Depends(auth)):
    articles = load_articles()
    from collections import Counter
    cats = Counter(a.get("category", "general") for a in articles)
    return {
        "total_articles": len(articles),
        "by_category":    dict(cats),
        "saved_count":    len(_saved),
        "top_score":      articles[0]["score"] if articles else 0,
    }


@app.get("/api/v1/flashcards/stream")
async def flashcard_stream(
    request: Request,
    last_event_id: Optional[str] = Query(None, alias="lastEventId"),
    _: None = Depends(auth),
):
    articles = load_articles()[:10]
    start_idx = 0
    if last_event_id:
        ids = [a.get("id") for a in articles]
        if last_event_id in ids:
            start_idx = ids.index(last_event_id) + 1

    async def gen():
        for article in articles[start_idx:]:
            if await request.is_disconnected():
                break
            full_text = article.get("full_text") or article.get("summary", "")
            summary_data = get_summary(full_text)
            payload = {
                "id":            article.get("id",""),
                "title":         article.get("title",""),
                "summary":       summary_data["summary"],
                "score":         article.get("score", 0),
                "category":      article.get("category","general"),
                "source":        article.get("source",""),
                "published_at":  article.get("published_at"),
                "canonical_url": article.get("canonical_url",""),
                "saved":         article.get("id","") in _saved,
            }
            yield f"id: {article['id']}\nevent: article\ndata: {json.dumps(payload)}\n\n"
            await asyncio.sleep(0.05)
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
        headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})
