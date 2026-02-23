"""
Phase 1-C: Deduplication
"""

from __future__ import annotations
import hashlib
import re
import logging
from urllib.parse import urlparse, urlunparse, urlencode, parse_qs

from core.models import RawArticle

logger = logging.getLogger(__name__)

STRIP_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "referer", "source", "cmpid", "cmp", "src", "mc_cid", "mc_eid",
    "fbclid", "gclid", "dclid", "_ga",
}


def canonical_url(url: str) -> str:
    try:
        parsed = urlparse(url.lower().strip())
        qs = {k: v for k, v in parse_qs(parsed.query).items() if k not in STRIP_PARAMS}
        clean = parsed._replace(
            scheme=parsed.scheme,
            netloc=parsed.netloc,
            path=parsed.path.rstrip("/"),
            query=urlencode(qs, doseq=True),
            fragment="",
        )
        return urlunparse(clean)
    except Exception:
        return url


def url_fingerprint(url: str) -> str:
    return hashlib.sha256(canonical_url(url).encode()).hexdigest()


def normalize_title(title: str) -> str:
    title = title.lower()
    title = re.sub(r"[^\w\s]", "", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title


def title_similarity(a: str, b: str) -> float:
    wa = set(normalize_title(a).split())
    wb = set(normalize_title(b).split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


class Deduplicator:
    def __init__(self, title_similarity_threshold: float = 0.75):
        self.threshold = title_similarity_threshold
        self._url_seen: set[str] = set()
        self._title_store: list[str] = []

    def deduplicate(self, articles: list[RawArticle]) -> tuple[list[RawArticle], int]:
        unique: list[RawArticle] = []
        removed = 0

        for article in articles:
            fp = url_fingerprint(article.canonical_url)

            if fp in self._url_seen:
                removed += 1
                continue

            if self._is_title_duplicate(article.title):
                removed += 1
                continue

            self._url_seen.add(fp)
            if article.title:
                self._title_store.append(article.title)
            unique.append(article)

        return unique, removed

    def _is_title_duplicate(self, title: str) -> bool:
        if not title:
            return False
        for seen_title in self._title_store[-200:]:
            if title_similarity(title, seen_title) >= self.threshold:
                return True
        return False

    def reset(self):
        self._url_seen.clear()
        self._title_store.clear()
