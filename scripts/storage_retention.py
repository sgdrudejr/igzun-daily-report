#!/usr/bin/env python3
"""
Storage retention/compaction for regeneratable pipeline artifacts.

Policy:
  - keep site/, macro_analysis/, etf_recommendations/ intact
  - summarize and archive older raw/normalized/manifests
  - optionally delete originals after archive creation
"""
import argparse
import gzip
import json
import re
import shutil
import tarfile
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def parse_iso_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def dated_dirs(base: Path) -> list[tuple[date, Path]]:
    items = []
    if not base.exists():
        return items
    for path in base.iterdir():
        if not path.is_dir():
            continue
        try:
            items.append((parse_iso_date(path.name), path))
        except ValueError:
            continue
    return sorted(items)


def site_exists(root: Path, day: str) -> bool:
    return (root / "site" / day / "result.json").exists()


def summarize_raw_date(path: Path) -> dict:
    summary = {"date": path.name, "sources": [], "doc_count": 0}
    for source_dir in sorted(path.iterdir()):
        if not source_dir.is_dir():
            continue
        count = 0
        examples = []
        for json_file in sorted(source_dir.glob("*.json")):
            count += 1
            if len(examples) >= 3:
                continue
            try:
                obj = json.loads(json_file.read_text())
                examples.append(
                    {
                        "title": obj.get("title", ""),
                        "published_date": obj.get("published_date", ""),
                        "url": obj.get("url", ""),
                        "document_type": obj.get("document_type", ""),
                    }
                )
            except Exception:
                continue
        summary["doc_count"] += count
        summary["sources"].append({"source_id": source_dir.name, "count": count, "examples": examples})
    return summary


def summarize_normalized_date(path: Path) -> dict:
    docs_file = path / "documents.jsonl"
    summary = {"date": path.name, "doc_count": 0, "sources": {}, "regions": {}, "types": {}}
    if not docs_file.exists():
        return summary
    for line in docs_file.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        summary["doc_count"] += 1
        for key, field in [("sources", "source_id"), ("regions", "region"), ("types", "document_type")]:
            value = obj.get(field) or "unknown"
            summary[key][value] = summary[key].get(value, 0) + 1
    return summary


def ensure_parent(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)


def archive_directory(source: Path, archive_path: Path):
    ensure_parent(archive_path)
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(source, arcname=source.name)


def archive_file(source: Path, archive_path: Path):
    ensure_parent(archive_path)
    with source.open("rb") as src, gzip.open(archive_path, "wb") as dst:
        shutil.copyfileobj(src, dst)


def write_jsonl_gz(records: list[dict], archive_path: Path):
    ensure_parent(archive_path)
    with gzip.open(archive_path, "wt", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def excerpt(text: str, limit: int = 700) -> str:
    compact = clean_text(text)
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def chunk_text(text: str, chunk_chars: int, overlap_chars: int) -> list[str]:
    compact = clean_text(text)
    if not compact:
        return []
    if len(compact) <= chunk_chars:
        return [compact]
    chunks = []
    start = 0
    while start < len(compact):
        end = min(len(compact), start + chunk_chars)
        chunk = compact[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(compact):
            break
        start = max(0, end - overlap_chars)
    return chunks


def compact_raw_date(
    path: Path,
    compact_path: Path,
    chunks_path: Path,
    chunk_chars: int,
    overlap_chars: int,
    max_chunks_per_doc: int,
) -> dict:
    docs: dict[str, dict] = {}

    for source_dir in sorted(path.iterdir()):
        if not source_dir.is_dir():
            continue
        for json_file in sorted(source_dir.glob("*.json")):
            doc_id = json_file.stem
            entry = docs.setdefault(doc_id, {
                "doc_id": doc_id,
                "source_id": source_dir.name,
                "artifacts": [],
                "texts": {},
                "metadata": {},
            })
            entry["artifacts"].append(json_file.name)
            try:
                obj = json.loads(json_file.read_text())
            except Exception:
                continue
            entry["title"] = obj.get("title", entry.get("title", ""))
            entry["url"] = obj.get("url", entry.get("url", ""))
            entry["published_date"] = obj.get("published_date", entry.get("published_date", ""))
            entry["document_type"] = obj.get("document_type", entry.get("document_type", ""))
            entry["region"] = obj.get("region", entry.get("region", ""))
            entry["sector"] = obj.get("sector", entry.get("sector", ""))
            entry["language"] = obj.get("language", entry.get("language", ""))
            entry["tags"] = obj.get("tags", entry.get("tags", []))
            entry["metadata"] = obj.get("metadata", entry.get("metadata", {}))
            for field in ("content", "summary"):
                value = clean_text(obj.get(field, ""))
                if value:
                    entry["texts"][field] = value

        for text_file in sorted(source_dir.glob("*.txt")):
            stem = text_file.stem
            doc_id = stem[:-7] if stem.endswith("_detail") else stem
            text_kind = "detail_text" if stem.endswith("_detail") else "pdf_text"
            entry = docs.setdefault(doc_id, {
                "doc_id": doc_id,
                "source_id": source_dir.name,
                "artifacts": [],
                "texts": {},
                "metadata": {},
            })
            entry["artifacts"].append(text_file.name)
            try:
                value = clean_text(text_file.read_text())
            except Exception:
                value = ""
            if value:
                entry["texts"][text_kind] = value

        for html_file in sorted(source_dir.glob("*_detail.html")):
            stem = html_file.stem
            doc_id = stem[:-7] if stem.endswith("_detail") else stem
            entry = docs.setdefault(doc_id, {
                "doc_id": doc_id,
                "source_id": source_dir.name,
                "artifacts": [],
                "texts": {},
                "metadata": {},
            })
            entry["artifacts"].append(html_file.name)

    compact_records = []
    chunk_records = []
    for doc_id, doc in docs.items():
        texts = doc.get("texts", {})
        primary_text = max(texts.values(), key=len, default="")
        compact_records.append({
            "date": path.name,
            "doc_id": doc_id,
            "source_id": doc.get("source_id", ""),
            "title": doc.get("title", ""),
            "url": doc.get("url", ""),
            "published_date": doc.get("published_date", ""),
            "document_type": doc.get("document_type", ""),
            "region": doc.get("region", ""),
            "sector": doc.get("sector", ""),
            "language": doc.get("language", ""),
            "tags": doc.get("tags", []),
            "text_length": len(primary_text),
            "excerpt": excerpt(primary_text or texts.get("summary") or texts.get("content") or "", 900),
            "artifacts": sorted(set(doc.get("artifacts", []))),
            "metadata": {
                "broker": (doc.get("metadata") or {}).get("broker"),
                "category": (doc.get("metadata") or {}).get("category"),
                "download_url": (doc.get("metadata") or {}).get("download_url"),
            },
        })
        if primary_text:
            for idx, chunk in enumerate(chunk_text(primary_text, chunk_chars, overlap_chars)[:max_chunks_per_doc], start=1):
                chunk_records.append({
                    "date": path.name,
                    "doc_id": doc_id,
                    "source_id": doc.get("source_id", ""),
                    "title": doc.get("title", ""),
                    "published_date": doc.get("published_date", ""),
                    "chunk_index": idx,
                    "text": chunk,
                    "char_count": len(chunk),
                    "document_type": doc.get("document_type", ""),
                    "region": doc.get("region", ""),
                    "sector": doc.get("sector", ""),
                    "tags": doc.get("tags", []),
                })

    write_jsonl_gz(compact_records, compact_path)
    write_jsonl_gz(chunk_records, chunks_path)
    return {
        "compact_docs": len(compact_records),
        "chunk_docs": len(chunk_records),
        "compact_path": str(compact_path),
        "chunks_path": str(chunks_path),
    }


def compact_normalized_date(path: Path, compact_path: Path) -> dict:
    docs_file = path / "documents.jsonl"
    if not docs_file.exists():
        return {"compact_docs": 0, "compact_path": str(compact_path)}
    compact_records = []
    for line in docs_file.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        text = obj.get("summary") or obj.get("content") or ""
        compact_records.append({
            "date": path.name,
            "id": obj.get("id"),
            "source_id": obj.get("source_id"),
            "title": obj.get("title"),
            "url": obj.get("url"),
            "published_date": obj.get("published_date"),
            "region": obj.get("region"),
            "sector": obj.get("sector"),
            "document_type": obj.get("document_type"),
            "language": obj.get("language"),
            "tags": obj.get("tags", []),
            "excerpt": excerpt(text, 900),
            "content_hash": obj.get("content_hash"),
            "raw_file_path": obj.get("raw_file_path"),
        })
    write_jsonl_gz(compact_records, compact_path)
    return {"compact_docs": len(compact_records), "compact_path": str(compact_path)}


def main():
    parser = argparse.ArgumentParser(description="Compact older pipeline artifacts to save disk space")
    parser.add_argument("--base-dir", default=str(ROOT))
    parser.add_argument("--today", default=date.today().isoformat())
    parser.add_argument("--raw-days", type=int, default=45, help="Keep raw dirs newer than this many days")
    parser.add_argument("--normalized-days", type=int, default=75, help="Keep normalized dirs newer than this many days")
    parser.add_argument("--manifests-days", type=int, default=90, help="Keep manifest files newer than this many days")
    parser.add_argument("--chunk-chars", type=int, default=1400, help="Chunk size for archived text corpus")
    parser.add_argument("--chunk-overlap", type=int, default=180, help="Chunk overlap chars for archived text corpus")
    parser.add_argument("--max-chunks-per-doc", type=int, default=12, help="Cap stored chunks per archived document")
    parser.add_argument("--delete-originals", action="store_true", help="Delete originals after archive creation")
    args = parser.parse_args()

    root = Path(args.base_dir)
    today = parse_iso_date(args.today)
    raw_cutoff = today - timedelta(days=args.raw_days)
    normalized_cutoff = today - timedelta(days=args.normalized_days)
    manifests_cutoff = today - timedelta(days=args.manifests_days)

    status = {
        "generated_at": datetime.now().isoformat(),
        "policy": {
            "raw_days": args.raw_days,
            "normalized_days": args.normalized_days,
            "manifests_days": args.manifests_days,
            "chunk_chars": args.chunk_chars,
            "chunk_overlap": args.chunk_overlap,
            "max_chunks_per_doc": args.max_chunks_per_doc,
            "delete_originals": args.delete_originals,
        },
        "archived": {"raw": [], "normalized": [], "manifests": []},
        "skipped": [],
    }

    archive_root = root / "data" / "archives"
    summary_root = root / "data" / "archive_summaries"

    for day, raw_dir in dated_dirs(root / "data" / "raw"):
        if day > raw_cutoff:
            continue
        day_str = day.isoformat()
        if not site_exists(root, day_str):
            status["skipped"].append({"date": day_str, "type": "raw", "reason": "site_result_missing"})
            continue
        raw_summary = summarize_raw_date(raw_dir)
        summary_path = summary_root / "raw" / f"{day_str}.json"
        ensure_parent(summary_path)
        summary_path.write_text(json.dumps(raw_summary, ensure_ascii=False, indent=2))
        compact_info = compact_raw_date(
            raw_dir,
            archive_root / "compact_raw" / f"{day_str}.jsonl.gz",
            archive_root / "chunks" / f"{day_str}.jsonl.gz",
            args.chunk_chars,
            args.chunk_overlap,
            args.max_chunks_per_doc,
        )
        archive_path = archive_root / "raw" / f"{day_str}.tar.gz"
        if not archive_path.exists():
            archive_directory(raw_dir, archive_path)
        if args.delete_originals and raw_dir.exists():
            shutil.rmtree(raw_dir)
        status["archived"]["raw"].append({
            "date": day_str,
            "summary": str(summary_path),
            "archive": str(archive_path),
            **compact_info,
        })

    for day, norm_dir in dated_dirs(root / "data" / "normalized"):
        if day > normalized_cutoff:
            continue
        day_str = day.isoformat()
        if not site_exists(root, day_str):
            status["skipped"].append({"date": day_str, "type": "normalized", "reason": "site_result_missing"})
            continue
        docs_file = norm_dir / "documents.jsonl"
        if not docs_file.exists():
            continue
        normalized_summary = summarize_normalized_date(norm_dir)
        summary_path = summary_root / "normalized" / f"{day_str}.json"
        ensure_parent(summary_path)
        summary_path.write_text(json.dumps(normalized_summary, ensure_ascii=False, indent=2))
        compact_info = compact_normalized_date(
            norm_dir,
            archive_root / "compact_normalized" / f"{day_str}.jsonl.gz",
        )
        archive_path = archive_root / "normalized" / f"{day_str}.jsonl.gz"
        if not archive_path.exists():
            archive_file(docs_file, archive_path)
        if args.delete_originals and norm_dir.exists():
            shutil.rmtree(norm_dir)
        status["archived"]["normalized"].append({
            "date": day_str,
            "summary": str(summary_path),
            "archive": str(archive_path),
            **compact_info,
        })

    manifest_root = root / "data" / "manifests"
    if manifest_root.exists():
        for manifest_file in sorted(manifest_root.glob("*_run.json")):
            day_str = manifest_file.stem.replace("_run", "")
            try:
                manifest_day = parse_iso_date(day_str)
            except ValueError:
                continue
            if manifest_day > manifests_cutoff:
                continue
            if not site_exists(root, day_str):
                status["skipped"].append({"date": day_str, "type": "manifest", "reason": "site_result_missing"})
                continue
            archive_path = archive_root / "manifests" / f"{day_str}_run.json.gz"
            if not archive_path.exists():
                archive_file(manifest_file, archive_path)
            if args.delete_originals and manifest_file.exists():
                manifest_file.unlink()
            status["archived"]["manifests"].append({"date": day_str, "archive": str(archive_path)})

    status_dir = root / "data" / "storage_retention"
    status_dir.mkdir(parents=True, exist_ok=True)
    status_file = status_dir / "status.json"
    status_file.write_text(json.dumps(status, ensure_ascii=False, indent=2))
    print(f"wrote {status_file}")
    print(
        "archived raw={raw} normalized={normalized} manifests={manifests}".format(
            raw=len(status["archived"]["raw"]),
            normalized=len(status["archived"]["normalized"]),
            manifests=len(status["archived"]["manifests"]),
        )
    )


if __name__ == "__main__":
    main()
