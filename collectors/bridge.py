#!/usr/bin/env python3
"""Bridge — converts normalized documents into the existing refined_insights_inventory.json format."""

import json
import argparse
from datetime import datetime
from pathlib import Path

from .base_fetcher import KST


def convert_to_insights(normalized_path: Path, output_path: Path):
    """Read normalized JSONL and append to refined_insights_inventory.json."""
    if not normalized_path.exists():
        print(f"No normalized data found at {normalized_path}")
        return

    # Load existing inventory
    existing = []
    if output_path.exists():
        with open(output_path, "r", encoding="utf-8") as f:
            existing = json.load(f)

    existing_ids = {item.get("source_file", "") for item in existing}

    new_items = []
    with open(normalized_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            doc = json.loads(line)

            source_file = doc.get("raw_file_path", doc.get("id", ""))
            if source_file in existing_ids:
                continue

            # Map to existing schema
            item = {
                "source_file": source_file,
                "date": doc.get("published_date", ""),
                "core_subject": doc.get("title", ""),
                "sentiment": 0.0,  # Will be filled by refine_insights.py
                "key_takeaways": [doc.get("summary", "")[:200]] if doc.get("summary") else [],
                "impact_assets": {
                    "USD": "neutral",
                    "Bonds": "neutral",
                    "Stocks": "neutral",
                },
                "source_meta": {
                    "source_id": doc.get("source_id", ""),
                    "region": doc.get("region", ""),
                    "document_type": doc.get("document_type", ""),
                    "url": doc.get("url", ""),
                    "fetched_url": doc.get("fetched_url", ""),
                    "content_length": doc.get("content_length", 0),
                    "tags": doc.get("tags", []),
                    "metadata": doc.get("metadata", {}),
                },
                "analysis_mode": "pending",
            }
            new_items.append(item)

    if new_items:
        existing.extend(new_items)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        print(f"Added {len(new_items)} new items to {output_path}")
    else:
        print("No new items to add")


def main():
    parser = argparse.ArgumentParser(description="Bridge: normalized docs → refined_insights format")
    parser.add_argument("--date", default=datetime.now(KST).strftime("%Y-%m-%d"))
    parser.add_argument("--base-dir", default=str(Path(__file__).resolve().parent.parent))
    args = parser.parse_args()

    base = Path(args.base_dir)
    normalized_path = base / "data" / "normalized" / args.date / "documents.jsonl"
    output_path = base / "data" / "refined_insights_inventory.json"

    convert_to_insights(normalized_path, output_path)


if __name__ == "__main__":
    main()
