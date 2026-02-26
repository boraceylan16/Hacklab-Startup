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


def canonical_url(url: str) -> str: #getting the url of the article
    try:
        parsed = urlparse(url.lower().strip())
        qs = {k: v for k, v in parse_qs(parsed.query).items() if k not in STRIP_PARAMS} #canonicalization, selecting the most representative url
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


def url_fingerprint(url: str) -> str: # encoding in hash
    return hashlib.sha256(canonical_url(url).encode()).hexdigest()


def normalize_title(title: str) -> str: #normalizing the format of the title
    title = title.lower()
    title = re.sub(r"[^\w\s]", "", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title


def title_similarity(a: str, b: str) -> float: # comparing the titles
    wa = set(normalize_title(a).split())
    wb = set(normalize_title(b).split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb) # common words / total words


class Deduplicator:
    def __init__(self, title_similarity_threshold: float = 0.75):
        self.threshold = title_similarity_threshold #title similarity minimum. If this is exceeded
        self._url_seen: set[str] = set() #set of urls (unique)
        self._title_store: list[str] = []

    def deduplicate(self, articles: list[RawArticle]) -> tuple[list[RawArticle], int]: #removing the duplicates
        unique: list[RawArticle] = [] 
        removed = 0

        for article in articles: 
            fp = url_fingerprint(article.canonical_url) #generate url fingerprint

            if fp in self._url_seen: #if the url fingerprint is seen before reove it
                removed += 1
                continue

            if self._is_title_duplicate(article.title): #if title is too similar
                removed += 1
                continue

            self._url_seen.add(fp) #adding to the seen urls
            if article.title:
                self._title_store.append(article.title) #for storing titles
            unique.append(article) #appending to the unique articles

        return unique, removed

    def _is_title_duplicate(self, title: str) -> bool: #checking if the title is very similar
        if not title:
            return False
        for seen_title in self._title_store[-200:]: #comparing with last 200 articles
            if title_similarity(title, seen_title) >= self.threshold: 
                return True
        return False

    def reset(self): #clearing deduplication memory
        self._url_seen.clear()
        self._title_store.clear()
