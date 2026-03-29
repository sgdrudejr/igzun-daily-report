"""SEC EDGAR fetcher — US corporate filings (13-F, N-PORT for ETF holdings)."""

import json
import requests

from ..base_fetcher import BaseFetcher, RawDocument
from ..fetcher_registry import register_fetcher


@register_fetcher("edgar")
class EDGARFetcher(BaseFetcher):
    """Fetch recent filings from SEC EDGAR full-text search."""

    EFTS_BASE = "https://efts.sec.gov/LATEST/search-index"
    SEARCH_URL = "https://efts.sec.gov/LATEST/search-index?q=%22ETF%22&dateRange=custom&startdt={start}&enddt={end}&forms={forms}"

    def fetch(self, date: str) -> list[RawDocument]:
        user_agent = self.config.get("config", {}).get("user_agent", "igzun-daily-report")
        filing_types = self.config.get("config", {}).get("filing_types", ["13-F"])

        docs = []
        headers = {"User-Agent": user_agent, "Accept": "application/json"}

        for form_type in filing_types:
            try:
                filings = self._search_filings(date, form_type, headers)
                for filing in filings[:10]:
                    docs.append(RawDocument(
                        source_id=self.source_id,
                        title=f"{filing.get('entity_name', '')} - {form_type}",
                        url=filing.get("file_url", ""),
                        published_date=filing.get("file_date", date),
                        content=json.dumps(filing, indent=2),
                        document_type="filing",
                        region="US",
                        language="en",
                        sector="equity",
                        tags=[form_type, "sec", "etf"],
                        fetched_url="https://efts.sec.gov/LATEST/search-index",
                        metadata={
                            "form_type": form_type,
                            "entity_name": filing.get("entity_name", ""),
                            "cik": filing.get("cik", ""),
                        },
                    ))
            except Exception as e:
                self.logger.error(f"EDGAR search failed for {form_type}: {e}")

        return docs

    def _search_filings(self, date: str, form_type: str, headers: dict) -> list[dict]:
        """Search EDGAR EFTS for recent filings."""
        url = "https://efts.sec.gov/LATEST/search-index"
        params = {
            "q": "*",
            "dateRange": "custom",
            "startdt": date,
            "enddt": date,
            "forms": form_type,
        }

        resp = requests.get(url, params=params, headers=headers, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("hits", {}).get("hits", [])
        return []

    def health_check(self) -> bool:
        try:
            resp = requests.get("https://www.sec.gov", timeout=10,
                                headers={"User-Agent": "igzun-daily-report"})
            return resp.status_code == 200
        except Exception:
            return False
