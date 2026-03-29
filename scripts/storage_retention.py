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


def main():
    parser = argparse.ArgumentParser(description="Compact older pipeline artifacts to save disk space")
    parser.add_argument("--base-dir", default=str(ROOT))
    parser.add_argument("--today", default=date.today().isoformat())
    parser.add_argument("--raw-days", type=int, default=45, help="Keep raw dirs newer than this many days")
    parser.add_argument("--normalized-days", type=int, default=75, help="Keep normalized dirs newer than this many days")
    parser.add_argument("--manifests-days", type=int, default=90, help="Keep manifest files newer than this many days")
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
        archive_path = archive_root / "raw" / f"{day_str}.tar.gz"
        if not archive_path.exists():
            archive_directory(raw_dir, archive_path)
        if args.delete_originals and raw_dir.exists():
            shutil.rmtree(raw_dir)
        status["archived"]["raw"].append({"date": day_str, "summary": str(summary_path), "archive": str(archive_path)})

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
        archive_path = archive_root / "normalized" / f"{day_str}.jsonl.gz"
        if not archive_path.exists():
            archive_file(docs_file, archive_path)
        if args.delete_originals and norm_dir.exists():
            shutil.rmtree(norm_dir)
        status["archived"]["normalized"].append({"date": day_str, "summary": str(summary_path), "archive": str(archive_path)})

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
