"""Normalize RawDocuments into a standard JSONL format with metadata."""

import json
from datetime import datetime, timezone
from pathlib import Path

from .base_fetcher import RawDocument, KST


def normalize_document(doc: RawDocument, raw_file_path: str = "") -> dict:
    """Convert a RawDocument into the normalized schema."""
    return {
        "id": doc.doc_id,
        "source_id": doc.source_id,
        "title": doc.title,
        "url": doc.url,
        "published_date": doc.published_date,
        "collected_date": datetime.now(KST).isoformat(),
        "region": doc.region,
        "sector": doc.sector,
        "document_type": doc.document_type,
        "language": doc.language,
        "summary": doc.content[:500] if doc.content else "",
        "content_hash": doc.content_hash,
        "raw_file_path": raw_file_path,
        "tags": doc.tags,
        "metadata": doc.metadata,
        "fetched_url": doc.fetched_url,
    }


def save_normalized(docs: list[dict], date: str, base_dir: Path) -> Path:
    """Save normalized documents as JSONL for a given date."""
    out_dir = base_dir / "data" / "normalized" / date
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "documents.jsonl"

    with open(out_path, "a", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")

    return out_path
