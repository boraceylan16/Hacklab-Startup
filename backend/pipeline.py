"""
Phase 1 Pipeline Orchestrator
Run: python pipeline.py
     python pipeline.py --feeds-limit 5 --no-extraction
"""

from __future__ import annotations
import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config.feeds import RSS_FEEDS, REQUEST_TIMEOUT, MAX_ARTICLES_FEED, USER_AGENT, OUTPUT_DIR
from core.models import CollectionResult
from core.rss_collector import RSSCollector
from core.text_extractor import TextExtractor
from core.deduplicator import Deduplicator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def run_pipeline(
    feeds=None,
    max_per_feed: int = MAX_ARTICLES_FEED,
    timeout: int = REQUEST_TIMEOUT,
    do_extraction: bool = True,
    output_dir: str = OUTPUT_DIR,
) -> CollectionResult:
    feeds = feeds or RSS_FEEDS
    result = CollectionResult(run_started_at=datetime.utcnow())

    logger.info("=" * 60)
    logger.info("PHASE 1-A  RSS Collection")
    logger.info(f"  Feeds: {len(feeds)}  |  Max per feed: {max_per_feed}")
    logger.info("=" * 60)

    collector = RSSCollector(timeout=timeout, max_per_feed=max_per_feed, user_agent=USER_AGENT)
    articles, rss_stats = collector.collect(feeds)

    result.feeds_attempted = rss_stats["attempted"]
    result.feeds_succeeded = rss_stats["succeeded"]
    result.feeds_failed    = rss_stats["failed"]

    logger.info(f"\n[RSS DONE] {rss_stats['succeeded']}/{rss_stats['attempted']} feeds → {len(articles)} raw articles\n")

    logger.info("=" * 60)
    logger.info("PHASE 1-B  Deduplication")
    logger.info("=" * 60)

    deduplicator = Deduplicator(title_similarity_threshold=0.75)
    articles, dupes_removed = deduplicator.deduplicate(articles)
    result.duplicates_removed = dupes_removed

    logger.info(f"[DEDUP DONE] Removed {dupes_removed} duplicates → {len(articles)} unique articles\n")

    if do_extraction:
        logger.info("=" * 60)
        logger.info("PHASE 1-C  Full Text Extraction")
        logger.info("=" * 60)
        extractor = TextExtractor(timeout=timeout)
        articles = extractor.extract_batch(articles)
        failures = sum(1 for a in articles if not a.extraction_success)
        result.extraction_failures = failures
        logger.info(f"\n[EXTRACT DONE] {len(articles) - failures}/{len(articles)} successful\n")
    else:
        logger.info("[EXTRACT SKIPPED] --no-extraction flag set")

    result.articles = articles
    result.run_ended_at = datetime.utcnow()

    _save_output(result, output_dir)
    _print_summary(result)

    return result


def _save_output(result: CollectionResult, output_dir: str) -> None:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    payload = {
        "meta": result.summary_dict(),
        "articles": [a.to_dict() for a in result.articles],
    }

    ts_path = Path(output_dir) / f"articles_{ts}.json"
    latest_path = Path(output_dir) / "articles_latest.json"

    for p in [ts_path, latest_path]:
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info(f"[SAVED] {latest_path}")


def _print_summary(result: CollectionResult) -> None:
    s = result.summary_dict()
    duration = (result.run_ended_at - result.run_started_at).seconds if result.run_ended_at else 0
    logger.info("\n" + "=" * 60)
    logger.info("PHASE 1 COMPLETE")
    logger.info("=" * 60)
    logger.info(f"  Duration           : {duration}s")
    logger.info(f"  Feeds              : {s['feeds_succeeded']}/{s['feeds_attempted']} OK")
    logger.info(f"  Articles collected : {s['total_articles']}")
    logger.info(f"  Duplicates removed : {s['duplicates_removed']}")
    logger.info(f"  Extraction success : {s['extraction_success_rate']}%")
    logger.info("=" * 60 + "\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Pulse — Phase 1 Pipeline")
    p.add_argument("--feeds-limit",  type=int, default=None)
    p.add_argument("--max-per-feed", type=int, default=MAX_ARTICLES_FEED)
    p.add_argument("--timeout",      type=int, default=REQUEST_TIMEOUT)
    p.add_argument("--no-extraction", action="store_true")
    p.add_argument("--output-dir",   type=str, default=OUTPUT_DIR)
    args = p.parse_args()

    feeds = RSS_FEEDS[:args.feeds_limit] if args.feeds_limit else RSS_FEEDS

    run_pipeline(
        feeds=feeds,
        max_per_feed=args.max_per_feed,
        timeout=args.timeout,
        do_extraction=not args.no_extraction,
        output_dir=args.output_dir,
    )
