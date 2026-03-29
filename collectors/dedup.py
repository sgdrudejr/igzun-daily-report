"""Content-hash based deduplication index."""

import json
from pathlib import Path
from datetime import date as date_type


class DedupIndex:
    """Tracks content hashes to avoid storing duplicate documents."""

    def __init__(self, base_dir: Path):
        self.index_path = base_dir / "data" / "index" / "content_hashes.json"
        self._hashes: dict[str, str] = {}
        self._load()

    def _load(self):
        if self.index_path.exists():
            with open(self.index_path, "r") as f:
                self._hashes = json.load(f)

    def save(self):
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.index_path, "w") as f:
            json.dump(self._hashes, f, indent=2)

    def is_duplicate(self, content_hash: str) -> bool:
        return content_hash in self._hashes

    def add(self, content_hash: str, date: str):
        if content_hash not in self._hashes:
            self._hashes[content_hash] = date

    def cleanup(self, days_to_keep: int = 90):
        """Remove hashes older than days_to_keep."""
        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(days=days_to_keep)).strftime("%Y-%m-%d")
        self._hashes = {h: d for h, d in self._hashes.items() if d >= cutoff}

    @property
    def size(self) -> int:
        return len(self._hashes)
