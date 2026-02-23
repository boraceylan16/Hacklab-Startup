"""
Data models for the News Intelligence pipeline.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
import hashlib, json


@dataclass
class RawArticle:
    id: str = ""
    canonical_url: str = ""
    source: str = ""
    category: str = ""
    feed_url: str = ""
    title: str = ""
    summary: str = ""
    full_text: str = ""
    author: str = ""
    tags: list[str] = field(default_factory=list)
    top_image: str = ""
    published_at: Optional[datetime] = None
    collected_at: datetime = field(default_factory=datetime.utcnow)
    word_count: int = 0
    extraction_method: str = ""
    extraction_success: bool = False
    extraction_error: str = ""

    def __post_init__(self):
        if self.canonical_url and not self.id:
            self.id = hashlib.sha256(self.canonical_url.encode()).hexdigest()[:16]
        if self.full_text:
            self.word_count = len(self.full_text.split())

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in ("published_at", "collected_at"):
            if d[k] is not None:
                d[k] = d[k].isoformat()
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @property
    def has_full_text(self) -> bool:
        return bool(self.full_text) and self.word_count > 50

    @property
    def content_preview(self) -> str:
        text = self.full_text or self.summary
        return text[:300].strip() + ("…" if len(text) > 300 else "")


@dataclass
class CollectionResult:
    articles: list[RawArticle] = field(default_factory=list)
    feeds_attempted: int = 0
    feeds_succeeded: int = 0
    feeds_failed: int = 0
    duplicates_removed: int = 0
    extraction_failures: int = 0
    run_started_at: datetime = field(default_factory=datetime.utcnow)
    run_ended_at: Optional[datetime] = None

    @property
    def total_articles(self) -> int:
        return len(self.articles)

    @property
    def extraction_success_rate(self) -> float:
        if not self.articles:
            return 0.0
        return sum(1 for a in self.articles if a.extraction_success) / len(self.articles)

    def summary_dict(self) -> dict:
        return {
            "total_articles": self.total_articles,
            "feeds_attempted": self.feeds_attempted,
            "feeds_succeeded": self.feeds_succeeded,
            "feeds_failed": self.feeds_failed,
            "duplicates_removed": self.duplicates_removed,
            "extraction_failures": self.extraction_failures,
            "extraction_success_rate": round(self.extraction_success_rate * 100, 1),
            "run_started_at": self.run_started_at.isoformat(),
            "run_ended_at": self.run_ended_at.isoformat() if self.run_ended_at else None,
        }
