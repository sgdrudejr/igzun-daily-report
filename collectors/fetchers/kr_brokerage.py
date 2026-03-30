"""Korean brokerage research center scraper."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from ..base_fetcher import BaseFetcher, RawDocument
from ..fetcher_registry import register_fetcher

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}


@register_fetcher("kr_brokerage")
class KRBrokerageFetcher(BaseFetcher):
    """Scrape public research summaries from Korean brokerage sites."""

    def fetch(self, date: str) -> list[RawDocument]:
        cfg = self.config.get("config", {})
        broker = cfg.get("broker_name", "unknown")
        mode = cfg.get("broker_mode", "").lower()

        if mode == "shinhan":
            return self._fetch_shinhan(date)
        if mode == "mirae":
            return self._fetch_mirae(date)

        url = cfg.get("research_url", "")

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
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=15, verify=False)
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

            full_url = urljoin(f"{url.rstrip('/')}/", href)
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

    def _fetch_shinhan(self, date: str) -> list[RawDocument]:
        cfg = self.config.get("config", {})
        list_url = cfg.get("list_url", "")
        api_url = cfg.get("api_url", "")
        page_size = int(cfg.get("page_size", 50))
        max_pages = int(cfg.get("max_pages", 8))

        if not list_url or not api_url:
            self.logger.warning("Shinhan routes are not fully configured")
            return []

        session = requests.Session()
        session.get(list_url, headers=DEFAULT_HEADERS, timeout=20, verify=False)

        docs: list[RawDocument] = []
        seen_urls: set[str] = set()
        target = date

        for page in range(max_pages):
            payload = {
                "startCount": page * page_size,
                "listCount": page_size,
                "query": "",
                "searchType": "A",
                "boardCode": "",
            }
            response = session.post(
                api_url,
                data=payload,
                headers={**DEFAULT_HEADERS, "Referer": list_url},
                timeout=20,
                verify=False,
            )
            response.raise_for_status()
            body = response.json().get("body", {})
            collections = body.get("collectionList") or []
            items = collections[0].get("itemList", []) if collections else []
            if not items:
                break

            stop = False
            for item in items:
                item_date = (item.get("DATE") or "").replace(".", "-")
                if not item_date:
                    continue
                if item_date < target:
                    stop = True
                    break
                if item_date != target:
                    continue

                board_name = item.get("BOARD_NAME") or ""
                doc_id = item.get("DOCID") or item.get("MESSAGE_ID") or ""
                if not board_name or not doc_id:
                    continue

                detail_url = (
                    "https://bbs2.shinhansec.com/siw/board/message/view.file.pop.do"
                    f"?boardName={board_name}&messageId={doc_id}"
                )
                if detail_url in seen_urls:
                    continue
                seen_urls.add(detail_url)

                title = self._normalize_shinhan_title(item.get("TITLE", ""))
                category = self._normalize_shinhan_category(
                    item.get("VARIABLE_FIELD_NAME3") or "",
                    item.get("BOARD_TITLE") or "",
                    board_name,
                )
                author = item.get("REGISTER_NICKNAME") or ""
                metadata = {
                    "broker": "신한투자증권",
                    "author": author,
                    "board_name": board_name,
                    "board_title": item.get("BOARD_TITLE") or "",
                    "category": category,
                    "message_id": doc_id,
                    "attachment_id": item.get("ATTACHMENT_ID") or "",
                    "message_number": item.get("MESSAGE_NUMBER") or "",
                    "file_path": item.get("FILE_PATH") or "",
                    "display_name": item.get("DISPLAYNAME") or "",
                    "file_name": item.get("FILE_NAME") or "",
                    "detail_page_url": detail_url,
                    "pdf_popup_url": self._build_shinhan_pdf_popup_url(item),
                    "download_candidates": self._build_shinhan_candidates(item),
                }

                docs.append(RawDocument(
                    source_id=self.source_id,
                    title=title,
                    url=detail_url,
                    published_date=item_date,
                    content=f"[신한투자증권/{category}] {title}",
                    document_type="research_meta",
                    region="KR",
                    language="ko",
                    sector="macro",
                    tags=["신한투자증권", category, "research"],
                    fetched_url=api_url,
                    metadata=metadata,
                ))

            if stop:
                break

        return docs

    def _fetch_mirae(self, date: str) -> list[RawDocument]:
        cfg = self.config.get("config", {})
        category_id = str(cfg.get("category_id", "1527"))
        lookback_days = int(cfg.get("lookback_days", 7))

        end_dt = datetime.strptime(date, "%Y-%m-%d")
        start_dt = end_dt - timedelta(days=lookback_days)

        list_url = (
            "https://securities.miraeasset.com/bbs/board/message/list.do"
            f"?categoryId={category_id}"
            "&curPage=1"
            "&direction=1"
            "&listType=1"
            f"&searchEndDay={end_dt:%d}"
            f"&searchEndMonth={end_dt:%m}"
            f"&searchEndYear={end_dt:%Y}"
            f"&searchStartDay={start_dt:%d}"
            f"&searchStartMonth={start_dt:%m}"
            f"&searchStartYear={start_dt:%Y}"
            "&searchType=2"
            "&startPage=1"
        )

        response = requests.get(list_url, headers=DEFAULT_HEADERS, timeout=20, verify=False)
        response.raise_for_status()
        html = response.content.decode("euc-kr", errors="ignore")
        soup = BeautifulSoup(html, "lxml")

        docs: list[RawDocument] = []
        seen_urls: set[str] = set()

        for row in soup.select("tbody tr"):
            cells = row.select("td")
            if len(cells) < 4:
                continue

            item_date = cells[0].get_text(" ", strip=True)
            if item_date != date:
                continue

            title_link = cells[1].select_one("div.subject a")
            if not title_link:
                continue

            title = self._normalize_multiline_title(title_link.get_text("\n", strip=True))
            title_href = title_link.get("href", "")
            pdf_url = self._extract_first_match(
                cells[2].decode(),
                r"downConfirm\('([^']+pdf\?attachmentId=[^']+)'",
            )
            if not pdf_url:
                continue
            if pdf_url in seen_urls:
                continue
            seen_urls.add(pdf_url)

            message_match = re.search(r"javascript:view\('([^']+)'\s*,\s*'([^']+)'\)", title_href)
            author = cells[3].get_text(" ", strip=True)
            metadata = {
                "broker": "미래에셋증권",
                "author": author,
                "category_id": category_id,
                "download_url": pdf_url,
            }
            if message_match:
                metadata["message_id"] = message_match.group(1)
                metadata["message_seq"] = message_match.group(2)

            docs.append(RawDocument(
                source_id=self.source_id,
                title=title,
                url=pdf_url,
                published_date=item_date,
                content=f"[미래에셋증권] {title}",
                document_type="daily_report",
                region="KR",
                language="ko",
                sector="macro",
                tags=["미래에셋증권", "research"],
                fetched_url=list_url,
                metadata=metadata,
            ))

        return docs

    def _build_shinhan_candidates(self, item: dict) -> list[str]:
        file_path = item.get("FILE_PATH") or ""
        display_name = item.get("DISPLAYNAME") or ""
        file_name = item.get("FILE_NAME") or ""
        if not file_path:
            return []

        candidates = []
        if display_name:
            candidates.append(f"https://bbs2.shinhansec.com{file_path}/{display_name}")
            candidates.append(f"https://file.shinhansec.com{file_path}/{display_name}")
        if file_name:
            candidates.append(f"https://bbs2.shinhansec.com{file_path}/{file_name}.pdf")
            candidates.append(f"https://file.shinhansec.com{file_path}/{file_name}.pdf")
        return candidates

    def _build_shinhan_pdf_popup_url(self, item: dict) -> str:
        board_name = item.get("BOARD_NAME") or ""
        message_id = item.get("DOCID") or item.get("MESSAGE_ID") or ""
        message_number = item.get("MESSAGE_NUMBER") or ""
        attachment_id = item.get("ATTACHMENT_ID") or ""
        if not all([board_name, message_id, message_number, attachment_id]):
            return ""
        return (
            "https://bbs2.shinhansec.com/siw/board/message/view.pdf.file.pop.do"
            f"?boardName={board_name}"
            f"&messageId={message_id}"
            f"&messageNumber={message_number}"
            f"&attachmentId={attachment_id}"
        )

    def _normalize_shinhan_title(self, text: str) -> str:
        return re.sub(r"\s+", " ", text or "").strip()

    def _normalize_shinhan_category(self, raw_category: str, board_title: str, board_name: str) -> str:
        text = (raw_category or "").strip()
        if text and "=" not in text and len(text) < 40:
            return text
        if board_title:
            return board_title.strip()
        return board_name.strip()

    def _normalize_multiline_title(self, text: str) -> str:
        parts = [re.sub(r"\s+", " ", part).strip() for part in (text or "").splitlines() if part.strip()]
        if len(parts) >= 2:
            return f"[{parts[0]}] {parts[1]}"
        return parts[0] if parts else ""

    def _extract_first_match(self, text: str, pattern: str) -> str:
        match = re.search(pattern, text)
        return match.group(1) if match else ""

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
        cfg = self.config.get("config", {})
        url = (
            cfg.get("list_url")
            or cfg.get("research_url")
            or cfg.get("api_url")
            or ""
        )
        if not url:
            return False
        try:
            resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=10, verify=False)
            return resp.status_code == 200
        except Exception:
            return False
