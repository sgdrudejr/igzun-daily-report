"""Manifest writer — logs each collection run's results."""

import json
from datetime import datetime
from pathlib import Path

from .base_fetcher import KST


class Manifest:
    """Tracks a single collection run."""

    def __init__(self, date: str, base_dir: Path):
        self.date = date
        self.base_dir = base_dir
        self.started_at = datetime.now(KST).isoformat()
        self.sources: dict[str, dict] = {}

    def record_source(self, source_id: str, status: str, documents: int = 0,
                      duplicates: int = 0, errors: int = 0, error_msg: str = "",
                      fetched_urls: list[str] | None = None):
        self.sources[source_id] = {
            "status": status,
            "documents": documents,
            "duplicates": duplicates,
            "errors": errors,
            "error_msg": error_msg,
            "fetched_urls": fetched_urls or [],
        }

    def save(self) -> Path:
        out_dir = self.base_dir / "data" / "manifests"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{self.date}_run.json"

        total_docs = sum(s["documents"] for s in self.sources.values())
        total_errors = sum(s["errors"] for s in self.sources.values())
        total_dupes = sum(s["duplicates"] for s in self.sources.values())

        data = {
            "date": self.date,
            "started_at": self.started_at,
            "finished_at": datetime.now(KST).isoformat(),
            "total_documents": total_docs,
            "total_duplicates": total_dupes,
            "total_errors": total_errors,
            "sources": self.sources,
        }

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return out_path

    def summary(self) -> str:
        lines = [f"=== Collection Manifest: {self.date} ==="]
        for sid, info in self.sources.items():
            lines.append(f"  {sid}: {info['status']} | docs={info['documents']} dupes={info['duplicates']} errors={info['errors']}")
        total = sum(s["documents"] for s in self.sources.values())
        lines.append(f"  TOTAL: {total} documents")
        return "\n".join(lines)
