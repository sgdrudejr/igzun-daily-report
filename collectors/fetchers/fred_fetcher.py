"""FRED API fetcher — US macro economic time series."""

import os
import json
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv

from ..base_fetcher import BaseFetcher, RawDocument
from ..fetcher_registry import register_fetcher

load_dotenv()


@register_fetcher("fred")
class FREDFetcher(BaseFetcher):
    """Fetch economic time series from FRED API."""

    FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"

    def fetch(self, date: str) -> list[RawDocument]:
        api_key = os.getenv("FRED_API_KEY")
        if not api_key:
            self.logger.warning("FRED_API_KEY not set, skipping")
            return []

        series_list = self.config["config"]["series"]
        docs = []

        for series in series_list:
            series_id = series["id"]
            try:
                data = self._fetch_series(api_key, series_id, date)
                if not data:
                    continue

                content = json.dumps(data, indent=2)
                latest = data[-1] if data else {}

                docs.append(RawDocument(
                    source_id=self.source_id,
                    title=f"{series['name']} ({series_id})",
                    url=f"https://fred.stlouisfed.org/series/{series_id}",
                    published_date=latest.get("date", date),
                    content=content,
                    document_type="time_series",
                    region="US",
                    language="en",
                    sector="macro",
                    tags=series.get("tags", []),
                    fetched_url=self.FRED_BASE,
                    metadata={
                        "series_id": series_id,
                        "latest_value": latest.get("value"),
                        "latest_date": latest.get("date"),
                        "observation_count": len(data),
                    },
                ))
            except Exception as e:
                self.logger.error(f"Failed to fetch {series_id}: {e}")

        return docs

    def _fetch_series(self, api_key: str, series_id: str, date: str,
                      lookback_days: int = 30) -> list[dict]:
        """Fetch recent observations for a FRED series."""
        start = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

        resp = requests.get(self.FRED_BASE, params={
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "observation_start": start,
            "observation_end": date,
        }, timeout=30)
        resp.raise_for_status()

        observations = resp.json().get("observations", [])
        return [{"date": o["date"], "value": o["value"]}
                for o in observations if o["value"] != "."]

    def health_check(self) -> bool:
        api_key = os.getenv("FRED_API_KEY")
        return bool(api_key)
