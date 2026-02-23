"""
Phase 1-B: Full Text Extractor
Cascading extraction: newspaper3k → readability → BeautifulSoup → RSS fallback
"""

from __future__ import annotations
import logging
import time
import re
from typing import Optional
import requests

from core.models import RawArticle

logger = logging.getLogger(__name__)

try:
    from newspaper import Article as NewspaperArticle
    NEWSPAPER_AVAILABLE = True
except ImportError:
    NEWSPAPER_AVAILABLE = False

try:
    from readability import Document as ReadabilityDoc
    READABILITY_AVAILABLE = True
except ImportError:
    READABILITY_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

MIN_WORD_COUNT = 80
CONTENT_TAGS   = ["article", "main", "section"]
CONTENT_CLASSES = ["article", "post", "content", "story", "entry", "body"]
BOILERPLATE_PATTERNS = [
    r"subscribe to.*newsletter",
    r"sign up for.*alerts",
    r"advertisement",
    r"cookies policy",
    r"follow us on",
]
_BOILERPLATE_RE = re.compile("|".join(BOILERPLATE_PATTERNS), re.IGNORECASE)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


class TextExtractor:
    def __init__(
        self,
        timeout: int = 15,
        delay_between_requests: float = 0.3,
        min_word_count: int = MIN_WORD_COUNT,
    ):
        self.timeout = timeout
        self.delay = delay_between_requests
        self.min_words = min_word_count

    def extract_batch(self, articles: list[RawArticle], show_progress: bool = True) -> list[RawArticle]:
        total = len(articles)
        for i, article in enumerate(articles, 1):
            self._extract_one(article)
            if show_progress:
                status = "✓" if article.extraction_success else "✗"
                logger.info(
                    f"[EXTRACT {i:3}/{total}] {status} "
                    f"({article.extraction_method:12s}) "
                    f"{article.word_count:5d}w  {article.title[:55]}"
                )
            time.sleep(self.delay)
        return articles

    def extract_one(self, article: RawArticle) -> RawArticle:
        self._extract_one(article)
        return article

    def _extract_one(self, article: RawArticle) -> None:
        methods = [
            ("newspaper3k",  self._try_newspaper),
            ("readability",  self._try_readability),
            ("bs4",          self._try_beautifulsoup),
            ("rss_only",     self._try_rss_fallback),
        ]

        html: Optional[str] = None

        for method_name, method_fn in methods:
            try:
                if method_name in ("readability", "bs4"):
                    if html is None:
                        html = self._fetch_html(article.canonical_url)
                    if not html:
                        continue
                    text, image = method_fn(html, article.canonical_url)
                elif method_name == "newspaper3k":
                    text, image = method_fn(article.canonical_url)
                else:
                    text, image = method_fn(article)

                text = self._clean_text(text)
                wc = len(text.split())

                if wc >= self.min_words:
                    article.full_text = text
                    article.word_count = wc
                    article.extraction_method = method_name
                    article.extraction_success = True
                    if image and not article.top_image:
                        article.top_image = image
                    return

            except Exception as exc:
                logger.debug(f"[{method_name}] failed for {article.canonical_url}: {exc}")
                continue

        article.extraction_success = False
        article.extraction_method = "failed"
        article.extraction_error = "All extraction methods exhausted"

    def _try_newspaper(self, url: str) -> tuple[str, str]:
        if not NEWSPAPER_AVAILABLE:
            raise ImportError("newspaper3k not installed")
        art = NewspaperArticle(url, request_timeout=self.timeout)
        art.download()
        art.parse()
        return art.text, art.top_image or ""

    def _try_readability(self, html: str, url: str) -> tuple[str, str]:
        if not READABILITY_AVAILABLE:
            raise ImportError("readability-lxml not installed")
        doc = ReadabilityDoc(html, url=url)
        content_html = doc.summary(html_partial=True)
        if BS4_AVAILABLE:
            soup = BeautifulSoup(content_html, "html.parser")
            text = soup.get_text(separator="\n")
        else:
            text = re.sub(r"<[^>]+>", " ", content_html)
        return text, ""

    def _try_beautifulsoup(self, html: str, url: str) -> tuple[str, str]:
        if not BS4_AVAILABLE:
            raise ImportError("beautifulsoup4 not installed")
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup(["script", "style", "nav", "header", "footer",
                         "aside", "form", "noscript", "iframe"]):
            tag.decompose()

        container = None
        for tag_name in CONTENT_TAGS:
            container = soup.find(tag_name)
            if container:
                break

        if not container:
            for cls in CONTENT_CLASSES:
                container = soup.find(True, attrs={"class": re.compile(cls, re.I)})
                if container:
                    break

        target = container or soup.find("body") or soup
        paragraphs = target.find_all("p")
        text = "\n\n".join(p.get_text(separator=" ").strip() for p in paragraphs if p.get_text(strip=True))

        img = ""
        og_img = soup.find("meta", property="og:image")
        if og_img:
            img = og_img.get("content", "")

        return text, img

    def _try_rss_fallback(self, article: RawArticle) -> tuple[str, str]:
        if article.summary and len(article.summary.split()) >= self.min_words:
            return article.summary, article.top_image
        raise ValueError("RSS summary too short")

    def _fetch_html(self, url: str) -> Optional[str]:
        try:
            resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=self.timeout, allow_redirects=True)
            resp.raise_for_status()
            return resp.text
        except Exception as exc:
            logger.debug(f"[fetch_html] {url}: {exc}")
            return None

    def _clean_text(self, text: str) -> str:
        lines = text.splitlines()
        cleaned = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if _BOILERPLATE_RE.search(line):
                continue
            cleaned.append(line)
        return "\n".join(cleaned)
