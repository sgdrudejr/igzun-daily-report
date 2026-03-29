"""OpenDART fetcher — Korean corporate disclosure filings."""

import os
import json
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv

from ..base_fetcher import BaseFetcher, RawDocument
from ..fetcher_registry import register_fetcher

load_dotenv()


@register_fetcher("opendart")
class OpenDARTFetcher(BaseFetcher):
    """Fetch recent disclosures from OpenDART API."""

    DART_BASE = "https://opendart.fss.or.kr/api"

    def fetch(self, date: str) -> list[RawDocument]:
        api_key = os.getenv("OPENDART_API_KEY")
        if not api_key:
            self.logger.warning("OPENDART_API_KEY not set, skipping")
            return []

        docs = []
        begin_date = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y%m%d")
        end_date = date.replace("-", "")

        try:
            filings = self._fetch_list(api_key, begin_date, end_date)
            for filing in filings[:50]:  # Limit to 50 most recent
                docs.append(RawDocument(
                    source_id=self.source_id,
                    title=filing.get("report_nm", ""),
                    url=f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={filing.get('rcept_no', '')}",
                    published_date=self._format_date(filing.get("rcept_dt", date.replace("-", ""))),
                    content=json.dumps(filing, ensure_ascii=False),
                    document_type="filing",
                    region="KR",
                    language="ko",
                    sector="equity",
                    tags=[filing.get("corp_cls", ""), filing.get("pblntf_ty", "")],
                    fetched_url=f"{self.DART_BASE}/list.json",
                    metadata={
                        "corp_name": filing.get("corp_name", ""),
                        "corp_code": filing.get("corp_code", ""),
                        "rcept_no": filing.get("rcept_no", ""),
                        "pblntf_ty": filing.get("pblntf_ty", ""),
                    },
                ))
        except Exception as e:
            self.logger.error(f"Failed to fetch OpenDART: {e}")

        return docs

    def _fetch_list(self, api_key: str, begin_date: str, end_date: str) -> list[dict]:
        """Fetch disclosure list from DART."""
        resp = requests.get(f"{self.DART_BASE}/list.json", params={
            "crtfc_key": api_key,
            "bgn_de": begin_date,
            "end_de": end_date,
            "page_count": 50,
            "sort": "date",
            "sort_mth": "desc",
        }, timeout=30)
        resp.raise_for_status()

        result = resp.json()
        if result.get("status") != "000":
            self.logger.warning(f"DART API returned status {result.get('status')}: {result.get('message')}")
            return []

        return result.get("list", [])

    def _format_date(self, date_str: str) -> str:
        """Convert YYYYMMDD to YYYY-MM-DD."""
        if len(date_str) == 8:
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        return date_str

    def health_check(self) -> bool:
        return bool(os.getenv("OPENDART_API_KEY"))
