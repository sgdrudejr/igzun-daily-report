"""Base fetcher with retry logic, logging, and health check interface."""

import time
import logging
import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

KST = timezone(offset=__import__("datetime").timedelta(hours=9))


@dataclass
class RawDocument:
    """A single fetched document before normalization."""
    source_id: str
    title: str
    url: str
    published_date: str          # YYYY-MM-DD
    content: str                 # full text or summary
    document_type: str           # daily_report, speech, time_series, news, research_meta, filing
    region: str                  # US, KR, JP, EU, Global
    language: str                # en, ko, ja
    sector: str = "macro"        # macro, equity, bond, fx, commodity, etc.
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    fetched_url: str = ""        # actual URL that was fetched (for source logging)

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()

    @property
    def doc_id(self) -> str:
        raw = f"{self.source_id}|{self.url}|{self.published_date}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["content_hash"] = self.content_hash
        d["id"] = self.doc_id
        return d


class BaseFetcher(ABC):
    """Abstract base for all source fetchers."""

    def __init__(self, source_config: dict):
        self.source_id: str = source_config["id"]
        self.config: dict = source_config
        self.logger = logging.getLogger(f"fetcher.{self.source_id}")

    @abstractmethod
    def fetch(self, date: str) -> list[RawDocument]:
        """Fetch documents for a given date (YYYY-MM-DD). Returns list of RawDocument."""
        ...

    def health_check(self) -> bool:
        """Quick check that the source is reachable. Override for custom logic."""
        return True

    def fetch_with_retry(self, date: str, max_retries: int = 3, backoff: float = 2.0) -> list[RawDocument]:
        """Fetch with exponential backoff retry."""
        last_error: Optional[Exception] = None
        for attempt in range(max_retries):
            try:
                docs = self.fetch(date)
                self.logger.info(f"[{self.source_id}] fetched {len(docs)} docs for {date}")
                return docs
            except Exception as e:
                last_error = e
                wait = backoff ** attempt
                self.logger.warning(f"[{self.source_id}] attempt {attempt+1}/{max_retries} failed: {e}. Retrying in {wait}s")
                time.sleep(wait)

        self.logger.error(f"[{self.source_id}] all {max_retries} attempts failed: {last_error}")
        return []
