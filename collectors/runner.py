#!/usr/bin/env python3
"""Main collection runner — iterates over active sources, fetches, deduplicates, normalizes, and logs manifest."""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from .base_fetcher import KST
from .registry_loader import get_active_sources, get_sources_by_tier
from .dedup import DedupIndex
from .normalizer import normalize_document, save_normalized
from .manifest import Manifest
from .fetcher_registry import FETCHER_CLASSES


def _import_fetchers():
    """Import all fetcher modules so they register themselves."""
    from .fetchers import rss_fetcher, fred_fetcher, ecos_fetcher, opendart_fetcher  # noqa: F401
    from .fetchers import naver_research, kr_brokerage, edgar_fetcher  # noqa: F401


def run_collection(date: str, base_dir: Path, tier: int | None = None,
                   source_id: str | None = None, dry_run: bool = False) -> Manifest:
    """Run the full collection pipeline for a given date."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logger = logging.getLogger("runner")

    _import_fetchers()

    # Load sources
    if source_id:
        sources = [s for s in get_active_sources() if s["id"] == source_id]
    elif tier is not None:
        sources = get_sources_by_tier(tier)
    else:
        sources = get_active_sources()

    if not sources:
        logger.warning("No sources matched the filter criteria")

    dedup = DedupIndex(base_dir)
    manifest = Manifest(date, base_dir)

    logger.info(f"Starting collection for {date} — {len(sources)} sources")

    for src in sources:
        sid = src["id"]
        fetcher_type = src.get("fetcher_type", sid)

        if fetcher_type not in FETCHER_CLASSES:
            logger.warning(f"[{sid}] No fetcher class registered for type '{fetcher_type}', skipping")
            manifest.record_source(sid, "skipped", error_msg=f"No fetcher for type '{fetcher_type}'")
            continue

        fetcher_cls = FETCHER_CLASSES[fetcher_type]
        fetcher = fetcher_cls(src)

        if dry_run:
            ok = fetcher.health_check()
            manifest.record_source(sid, "dry_run_ok" if ok else "dry_run_fail")
            continue

        raw_docs = fetcher.fetch_with_retry(date)

        new_docs = []
        dupes = 0
        fetched_urls = set()

        for doc in raw_docs:
            if doc.fetched_url:
                fetched_urls.add(doc.fetched_url)
            if dedup.is_duplicate(doc.content_hash):
                dupes += 1
                continue
            dedup.add(doc.content_hash, date)

            # Save raw content
            raw_dir = base_dir / "data" / "raw" / date / sid
            raw_dir.mkdir(parents=True, exist_ok=True)
            raw_path = raw_dir / f"{doc.doc_id}.json"
            with open(raw_path, "w", encoding="utf-8") as f:
                json.dump(doc.to_dict(), f, ensure_ascii=False, indent=2)

            normalized = normalize_document(doc, str(raw_path.relative_to(base_dir)))
            new_docs.append(normalized)

        if new_docs:
            save_normalized(new_docs, date, base_dir)

        status = "success" if not raw_docs or new_docs else "all_duplicates"
        if not raw_docs and not dupes:
            status = "empty"

        manifest.record_source(
            sid,
            status=status,
            documents=len(new_docs),
            duplicates=dupes,
            fetched_urls=sorted(fetched_urls),
        )

    dedup.save()
    manifest_path = manifest.save()
    logger.info(f"Manifest saved to {manifest_path}")
    logger.info(manifest.summary())

    return manifest


def main():
    parser = argparse.ArgumentParser(description="Run financial data collection pipeline")
    parser.add_argument("--date", default=datetime.now(KST).strftime("%Y-%m-%d"),
                        help="Collection date (YYYY-MM-DD)")
    parser.add_argument("--tier", type=int, help="Only run sources of this tier (1, 2, or 3)")
    parser.add_argument("--source", help="Only run a specific source by ID")
    parser.add_argument("--dry-run", action="store_true", help="Only check source health, don't fetch")
    parser.add_argument("--base-dir", default=str(Path(__file__).resolve().parent.parent),
                        help="Project root directory")
    args = parser.parse_args()

    manifest = run_collection(
        date=args.date,
        base_dir=Path(args.base_dir),
        tier=args.tier,
        source_id=args.source,
        dry_run=args.dry_run,
    )

    # Exit with error code if all sources failed
    failed = sum(1 for s in manifest.sources.values() if s["status"] in ("error", "dry_run_fail"))
    if failed == len(manifest.sources) and manifest.sources:
        sys.exit(1)


if __name__ == "__main__":
    main()
