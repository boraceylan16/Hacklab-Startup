"""
Summarizer — uses BART locally (free, no API key).
Falls back to extractive if model unavailable.
"""

import re
import logging

log = logging.getLogger(__name__)

MODEL        = "facebook/bart-large-cnn"
MAX_INPUT    = 600
MIN_TOKENS   = 40
MAX_TOKENS   = 120
FB_SENTENCES = 3

_pipeline = None


def _load():
    global _pipeline
    if _pipeline is not None:
        return _pipeline
    try:
        from transformers import pipeline
        log.info(f"Loading AI model '{MODEL}'...")
        _pipeline = pipeline("summarization", model=MODEL, device=-1, framework="pt")
        log.info("✅ AI model ready.")
    except Exception as e:
        log.warning(f"⚠️  Could not load AI model: {e}")
        _pipeline = None
    return _pipeline


def _ai_summarize(text: str):
    pipe = _load()
    if pipe is None:
        return None
    words = text.split()
    if len(words) < 50:
        return None
    truncated = " ".join(words[:MAX_INPUT])
    try:
        result = pipe(truncated, min_length=MIN_TOKENS, max_length=MAX_TOKENS, do_sample=False, truncation=True)
        return result[0]["summary_text"].strip() or None
    except Exception as e:
        log.warning(f"AI inference failed: {e}")
        return None


def _extractive(text: str, n: int = FB_SENTENCES) -> str:
    if not text:
        return ""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    kept = []
    for s in sentences:
        s = s.strip()
        if len(s) < 40:
            continue
        if any(skip in s.lower() for skip in ["cookie", "subscribe", "sign up", "newsletter", "advertisement"]):
            continue
        kept.append(s)
        if len(kept) >= n:
            break
    return " ".join(kept)


def summarize(text: str) -> dict:
    ai_result = _ai_summarize(text)
    if ai_result:
        return {"summary": ai_result, "method": "ai"}
    fallback = _extractive(text)
    return {"summary": fallback if fallback else "No summary available.", "method": "fallback"}
