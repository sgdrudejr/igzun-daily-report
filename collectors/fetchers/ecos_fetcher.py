"""Bank of Korea ECOS — KeyStatisticList API (key macro indicators)."""

import os
import json
from datetime import datetime

import requests
from dotenv import load_dotenv

from ..base_fetcher import BaseFetcher, RawDocument
from ..fetcher_registry import register_fetcher

load_dotenv()

# Indicators to capture from KeyStatisticList (KEYSTAT_NAME → internal tag)
WANTED = {
    "한국은행 기준금리":              "bok_base_rate",
    "원/달러 환율(종가)":              "usd_krw",
    "소비자물가지수":                  "cpi_kr",
    "코스피지수":                      "kospi",
    "실업률":                          "unemployment_kr",
    "경상수지":                        "current_account",
    "국고채수익률(3년)":               "kr_3y_yield",
    "소비자심리지수":                   "consumer_sentiment",
    "경제성장률(실질, 계절조정 전기대비)": "gdp_growth_qoq",
    "Dubai유(현물)":                   "dubai_crude",
    "금":                              "gold_kr",
}


@register_fetcher("ecos")
class ECOSFetcher(BaseFetcher):
    """Fetch Korean macro indicators from BOK ECOS KeyStatisticList API."""

    API_URL = "https://ecos.bok.or.kr/api/KeyStatisticList/{key}/json/kr/1/200/"

    def fetch(self, date: str) -> list[RawDocument]:
        api_key = os.getenv("BOK_API_KEY")
        if not api_key:
            self.logger.warning("BOK_API_KEY not set, skipping")
            return []

        try:
            rows = self._fetch_all(api_key)
        except Exception as e:
            self.logger.error(f"ECOS KeyStatisticList failed: {e}")
            return []

        docs = []
        for row in rows:
            name = row.get("KEYSTAT_NAME", "")
            tag = WANTED.get(name)
            if not tag:
                continue

            value_str = row.get("DATA_VALUE", "")
            cycle = row.get("CYCLE", date)
            unit = row.get("UNIT_NAME", "")

            try:
                value = float(value_str) if value_str else None
            except (ValueError, TypeError):
                value = None

            # Normalize cycle to YYYY-MM-DD best-effort
            pub_date = self._parse_cycle(cycle, date)

            content = json.dumps({
                "name": name,
                "value": value,
                "unit": unit,
                "cycle": cycle,
            }, ensure_ascii=False)

            docs.append(RawDocument(
                source_id=self.source_id,
                title=f"[BOK] {name}: {value_str} {unit}",
                url="https://ecos.bok.or.kr/",
                published_date=pub_date,
                content=content,
                document_type="time_series",
                region="KR",
                language="ko",
                sector="macro",
                tags=[tag, "bok", "ecos"],
                fetched_url=self.API_URL.format(key="***"),
                metadata={
                    "keystat_name": name,
                    "tag": tag,
                    "value": value,
                    "unit": unit,
                    "cycle": cycle,
                },
            ))

        self.logger.info(f"[{self.source_id}] collected {len(docs)} ECOS indicators")
        return docs

    def _fetch_all(self, api_key: str) -> list[dict]:
        url = self.API_URL.format(key=api_key)
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json().get("KeyStatisticList", {}).get("row", [])

    @staticmethod
    def _parse_cycle(cycle: str, fallback: str) -> str:
        """Convert BOK cycle strings like '20260327', '202603', '2025Q4' to YYYY-MM-DD."""
        if not cycle:
            return fallback
        c = cycle.strip()
        if len(c) == 8 and c.isdigit():          # YYYYMMDD
            return f"{c[:4]}-{c[4:6]}-{c[6:]}"
        if len(c) == 6 and c.isdigit():          # YYYYMM
            return f"{c[:4]}-{c[4:]}-01"
        if len(c) == 4 and c.isdigit():          # YYYY
            return f"{c}-01-01"
        if "Q" in c:                              # 2025Q4
            parts = c.split("Q")
            month = str(int(parts[1]) * 3 - 2).zfill(2)
            return f"{parts[0]}-{month}-01"
        return fallback

    def health_check(self) -> bool:
        return bool(os.getenv("BOK_API_KEY"))
