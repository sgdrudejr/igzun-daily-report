"""Naver Finance Research — scrapes brokerage report metadata (title, broker, date, link)."""

import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from ..base_fetcher import BaseFetcher, RawDocument
from ..fetcher_registry import register_fetcher


@register_fetcher("naver_research")
class NaverResearchFetcher(BaseFetcher):
    """Scrape research report metadata from Naver Finance."""

    BASE_URL = "https://finance.naver.com/research/"
    CATEGORIES = {
        "market_info": "market_info_list.naver",   # 시장정보
        "invest": "invest_list.naver",              # 투자정보
        "industry": "industry_list.naver",          # 산업분석
    }

    def fetch(self, date: str) -> list[RawDocument]:
        categories = self.config.get("config", {}).get("categories", ["market_info"])
        docs = []

        for cat in categories:
            endpoint = self.CATEGORIES.get(cat)
            if not endpoint:
                continue
            try:
                cat_docs = self._scrape_category(cat, endpoint, date)
                docs.extend(cat_docs)
            except Exception as e:
                self.logger.error(f"Failed to scrape category {cat}: {e}")

        return docs

    def _scrape_category(self, category: str, endpoint: str, date: str) -> list[RawDocument]:
        url = f"{self.BASE_URL}{endpoint}"
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")
        docs = []

        # Parse the research table
        table = soup.select_one("table.type_1")
        if not table:
            return docs

        rows = table.select("tr")
        for row in rows:
            cells = row.select("td")
            if len(cells) < 3:
                continue

            title_tag = cells[0].select_one("a")
            if not title_tag:
                continue

            title = title_tag.get_text(strip=True)
            link = title_tag.get("href", "")
            if link and not link.startswith("http"):
                link = f"https://finance.naver.com/research/{link}"

            broker = cells[1].get_text(strip=True) if len(cells) > 1 else ""
            # Date is in one of the later cells — find the one matching date pattern
            pub_date_text = ""
            for cell in cells:
                txt = cell.get_text(strip=True)
                if re.search(r"\d{2}\.\d{2}\.\d{2}", txt):
                    pub_date_text = txt
                    break

            # Parse date (format: YY.MM.DD)
            pub_date = self._parse_naver_date(pub_date_text)
            if not pub_date:
                continue

            content = f"[{broker}] {title}"

            docs.append(RawDocument(
                source_id=self.source_id,
                title=title,
                url=link,
                published_date=pub_date,
                content=content,
                document_type="research_meta",
                region="KR",
                language="ko",
                sector="equity" if category != "market_info" else "macro",
                tags=[category, broker],
                fetched_url=url,
                metadata={
                    "broker": broker,
                    "category": category,
                    "naver_link": link,
                },
            ))

        return docs

    def _parse_naver_date(self, text: str) -> str | None:
        """Parse 'YY.MM.DD' or 'YYYY.MM.DD' format."""
        match = re.search(r"(\d{2,4})\.(\d{2})\.(\d{2})", text)
        if not match:
            return None
        year = match.group(1)
        if len(year) == 2:
            year = f"20{year}"
        return f"{year}-{match.group(2)}-{match.group(3)}"

    def health_check(self) -> bool:
        try:
            resp = requests.get(self.BASE_URL, timeout=10)
            return resp.status_code == 200
        except Exception:
            return False
