"""Generic RSS/Atom feed fetcher — reusable for Fed speeches, BIS, Investing.com, etc."""

import feedparser
from datetime import datetime
from email.utils import parsedate_to_datetime

from ..base_fetcher import BaseFetcher, RawDocument
from ..fetcher_registry import register_fetcher


@register_fetcher("rss")
class RSSFetcher(BaseFetcher):
    """Fetch articles from any RSS/Atom feed."""

    def fetch(self, date: str) -> list[RawDocument]:
        feed_url = self.config["config"]["feed_url"]
        self.logger.info(f"Fetching RSS: {feed_url}")

        feed = feedparser.parse(feed_url)
        if feed.bozo and not feed.entries:
            raise RuntimeError(f"RSS parse error: {feed.bozo_exception}")

        docs = []
        for entry in feed.entries:
            pub_date = self._parse_date(entry)
            if not pub_date:
                continue

            # Optionally filter to only today's entries
            # For initial collection, we take all recent entries
            title = entry.get("title", "")
            link = entry.get("link", "")
            summary = entry.get("summary", entry.get("description", ""))
            content = summary
            if hasattr(entry, "content") and entry.content:
                content = entry.content[0].get("value", summary)

            tags = [t.get("term", "") for t in entry.get("tags", [])] if hasattr(entry, "tags") else []

            docs.append(RawDocument(
                source_id=self.source_id,
                title=title,
                url=link,
                published_date=pub_date,
                content=content,
                document_type=self.config.get("document_type", "news"),
                region=self.config.get("region", "Global"),
                language=self.config.get("language", "en"),
                sector=self.config.get("sector", "macro"),
                tags=tags,
                fetched_url=feed_url,
                metadata={"feed_url": feed_url},
            ))

        return docs

    def _parse_date(self, entry) -> str | None:
        """Extract published date from feed entry."""
        for field in ("published", "updated", "created"):
            raw = entry.get(field)
            if raw:
                try:
                    dt = parsedate_to_datetime(raw)
                    return dt.strftime("%Y-%m-%d")
                except Exception:
                    pass
            parsed = entry.get(f"{field}_parsed")
            if parsed:
                try:
                    dt = datetime(*parsed[:6])
                    return dt.strftime("%Y-%m-%d")
                except Exception:
                    pass
        return None

    def health_check(self) -> bool:
        feed_url = self.config["config"]["feed_url"]
        feed = feedparser.parse(feed_url)
        return bool(feed.entries)
