"""Korean brokerage research center scraper — KB, Mirae Asset, etc."""

import re
import requests
from bs4 import BeautifulSoup

from ..base_fetcher import BaseFetcher, RawDocument
from ..fetcher_registry import register_fetcher


@register_fetcher("kr_brokerage")
class KRBrokerageFetcher(BaseFetcher):
    """Scrape public research summaries from Korean brokerage sites."""

    def fetch(self, date: str) -> list[RawDocument]:
        broker = self.config.get("config", {}).get("broker_name", "unknown")
        url = self.config.get("config", {}).get("research_url", "")

        if not url:
            self.logger.warning(f"No research_url configured for {broker}")
            return []

        try:
            return self._scrape_research_page(url, broker, date)
        except Exception as e:
            self.logger.error(f"Failed to scrape {broker}: {e}")
            return []

    def _scrape_research_page(self, url: str, broker: str, date: str) -> list[RawDocument]:
        """Generic scraper for Korean brokerage research pages."""
        resp = requests.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Accept-Language": "ko-KR,ko;q=0.9",
        }, timeout=15, verify=False)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")
        docs = []

        # Try to find research report links — common patterns
        links = soup.select("a[href]")
        for link in links:
            text = link.get_text(strip=True)
            href = link.get("href", "")

            # Filter: only items that look like report titles (minimum length, not navigation)
            if len(text) < 10 or len(text) > 200:
                continue
            if any(skip in text for skip in ["로그인", "회원가입", "메뉴", "검색", "홈"]):
                continue

            # Check if it looks like a research report title
            if not self._looks_like_report(text):
                continue

            full_url = href if href.startswith("http") else f"{url.rstrip('/')}/{href.lstrip('/')}"
            metadata = {
                "broker": broker,
            }
            if ".pdf" in full_url.lower():
                metadata["download_url"] = full_url

            docs.append(RawDocument(
                source_id=self.source_id,
                title=text,
                url=full_url,
                published_date=date,  # Can't always parse exact date from listing
                content=f"[{broker}] {text}",
                document_type="daily_report",
                region="KR",
                language="ko",
                sector="macro",
                tags=[broker, "research"],
                fetched_url=url,
                metadata=metadata,
            ))

        return docs[:20]  # Limit to 20 most relevant

    def _looks_like_report(self, text: str) -> bool:
        """Heuristic: does this text look like a research report title?"""
        keywords = [
            "시황", "데일리", "전략", "투자", "모닝", "이슈", "분석",
            "마켓", "리서치", "리포트", "시장", "경제", "글로벌",
            "섹터", "산업", "종목", "채권", "금리", "환율",
            "Daily", "Market", "Strategy", "Research", "Report",
        ]
        return any(kw in text for kw in keywords)

    def health_check(self) -> bool:
        url = self.config.get("config", {}).get("research_url", "")
        if not url:
            return False
        try:
            resp = requests.get(url, timeout=10, verify=False)
            return resp.status_code == 200
        except Exception:
            return False
