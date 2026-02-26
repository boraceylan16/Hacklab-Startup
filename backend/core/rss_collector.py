"""
Phase 1-A: RSS Feed Collector
"""

from __future__ import annotations
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Optional
import requests

try:
    import feedparser #try to download feedparser
    FEEDPARSER_AVAILABLE = True
except ImportError:
    FEEDPARSER_AVAILABLE = False
    logging.warning("feedparser not installed. Run: pip install feedparser") 

from core.models import RawArticle

logger = logging.getLogger(__name__)


class RSSCollector: #declaring the RSSCollector Class
    def __init__(
        self,
        timeout: int = 15,
        max_per_feed: int = 20,
        user_agent: str = "NewsIntelBot/1.0",
        retry_attempts: int = 2,
        retry_delay: float = 1.5,
    ):
        self.timeout = timeout 
        self.max_per_feed = max_per_feed #maximum number of articles per feed
        self.user_agent = user_agent #user agent
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay # 1.5 seconds ig
        self._seen_urls: set[str] = set() # urls seen

    def collect(self, feeds: list[dict]) -> tuple[list[RawArticle], dict]: #collecting the feeds and returning the stats
        if not FEEDPARSER_AVAILABLE: 
            raise RuntimeError("feedparser is required. pip install feedparser")

        all_articles: list[RawArticle] = [] #initializing list of Raw articles
        stats = {"attempted": 0, "succeeded": 0, "failed": 0, "duplicates_skipped": 0} #initializing the stats dict

        for feed_cfg in feeds: #for feed in feeds
            stats["attempted"] += 1 #increase attempt by 1
            try:
                articles, dupes = self._collect_feed(feed_cfg) #collect the articles in the feed
                all_articles.extend(articles)
                stats["succeeded"] += 1 #increase success by 1 
                stats["duplicates_skipped"] += dupes 
                logger.info(
                    f"[RSS] ✓ {feed_cfg['source']:20s} → {len(articles)} articles  "
                    f"({dupes} dupes skipped)" 
                )
            except Exception as exc: #if collecting the efeed fails
                stats["failed"] += 1 #increase the fail by 1
                logger.error(f"[RSS] ✗ {feed_cfg['source']} failed: {exc}")

        return all_articles, stats

    def _collect_feed(self, feed_cfg: dict) -> tuple[list[RawArticle], int]: #this is feed specific (executing on one feed)
        raw_content = self._fetch_with_retry(feed_cfg["url"]) #fetching the raw content
        parsed = feedparser.parse(raw_content) #parsing the content, the result is a dict containing metadata
        articles: list[RawArticle] = [] #articles
        dupes = 0 #duplicate numbers
        cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=36) #only articles published within 36 hours

        entries = parsed.entries[: self.max_per_feed] #truncating to the max number of articles
        for entry in entries: #iterating over entries
            url = self._extract_url(entry) #extracting the url
            if not url: #in case url is not extracted
                continue

            published_at = self._extract_published(entry) 
            if not self._is_within_window(published_at, cutoff): #if the article isn't published within 36 hours
                continue

            if url in self._seen_urls: #if url is already fetched, increase the duplicates by 1
                dupes += 1
                continue
            self._seen_urls.add(url) #add one url

            article = self._entry_to_article(entry, url, feed_cfg) #
            articles.append(article) #

        return articles, dupes

    def _fetch_with_retry(self, url: str) -> bytes: #fetching the url
        headers = {"User-Agent": self.user_agent}
        last_exc = None

        for attempt in range(self.retry_attempts + 1):
            try:
                resp = requests.get(url, headers=headers, timeout=self.timeout)
                resp.raise_for_status()
                return resp.content
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < self.retry_attempts:
                    time.sleep(self.retry_delay) #1.5 seconds delay

        raise last_exc

    def _extract_url(self, entry) -> Optional[str]: #extracting the url from the feed
        for attr in ("link", "id", "guid"):
            url = getattr(entry, attr, None)
            if url and url.startswith("http"):
                return url.strip()
        return None

    def _extract_published(self, entry) -> Optional[datetime]: #extracting the published date
        t = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
        if t:
            try:
                return datetime(*t[:6])
            except Exception:
                pass
        return None

    def _is_within_window(self, published_at: Optional[datetime], cutoff: datetime) -> bool: #checking if the article is within 36 hours
        if published_at is None:
            return False
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)
        return published_at >= cutoff

    def _entry_to_article(self, entry, url: str, feed_cfg: dict) -> RawArticle: #conversion from entry to article
        tags = []
        for tag in getattr(entry, "tags", []): 
            label = getattr(tag, "term", None) or getattr(tag, "label", None) #gettng the label (category)
            if label:
                tags.append(label.strip())

        summary = ""
        for attr in ("summary", "description", "content"): 
            val = getattr(entry, attr, None)
            if val:
                if isinstance(val, list):
                    val = val[0].get("value", "")
                summary = _strip_html(val)
                break

        return RawArticle(
            canonical_url=url,
            source=feed_cfg.get("source", ""),
            category=feed_cfg.get("category", "general"),
            feed_url=feed_cfg.get("url", ""),
            title=getattr(entry, "title", "").strip(),
            summary=summary[:1000],
            author=getattr(entry, "author", ""),
            tags=tags[:10],
            published_at=self._extract_published(entry),
        )


def _strip_html(text: str) -> str: #stripping html
    import re
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = re.sub(r"\s+", " ", clean)
    return clean.strip()
