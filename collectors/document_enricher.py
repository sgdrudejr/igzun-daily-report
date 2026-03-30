"""Enrich collected documents with downloaded source text or PDF attachments."""

from __future__ import annotations

import io
import re
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

from .base_fetcher import RawDocument

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}


def looks_like_pdf(url: str) -> bool:
    text = (url or "").lower()
    return ".pdf" in text or "download" in text and "pdf" in text


def clean_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"\r", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def extract_pdf_text(pdf_bytes: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
    except Exception:
        return ""

    chunks = []
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        text = clean_text(text)
        if text:
            chunks.append(text)
    return "\n\n".join(chunks).strip()


def extract_naver_detail(soup: BeautifulSoup) -> str:
    cell = soup.select_one("td.view_cnt")
    if not cell:
        return ""
    for tag in cell.select("script, style"):
        tag.decompose()
    return clean_text(cell.get_text("\n", strip=True))


def extract_shinhan_bbs_detail(soup: BeautifulSoup) -> str:
    title = clean_text((soup.select_one("td.title") or {}).get_text(" ", strip=True) if soup.select_one("td.title") else "")
    data_cell = soup.select_one("td.data")
    meta = clean_text(data_cell.get_text(" ", strip=True)) if data_cell else ""
    attachments = []
    for link in soup.select("div.attach02 a"):
        text = clean_text(link.get_text(" ", strip=True))
        if text:
            attachments.append(text)

    parts = [part for part in [title, meta] if part]
    if attachments:
        parts.append("첨부파일: " + ", ".join(attachments))
    return clean_text("\n".join(parts))


def extract_generic_html_text(soup: BeautifulSoup) -> str:
    candidates = []
    for selector in ["article", "main", "div#contentarea_left", "div.box_type_m", "div.content", "body"]:
        for node in soup.select(selector):
            for tag in node.select("script, style, nav, header, footer"):
                tag.decompose()
            text = clean_text(node.get_text("\n", strip=True))
            if len(text) >= 300:
                candidates.append(text)
    if not candidates:
        return ""
    candidates.sort(key=len, reverse=True)
    return candidates[0]


def find_pdf_link(soup: BeautifulSoup, base_url: str) -> str:
    for link in soup.select("a[href]"):
        href = (link.get("href") or "").strip()
        if not href:
            continue
        full_url = urljoin(base_url, href)
        if looks_like_pdf(full_url):
            return full_url
    return ""


def find_shinhan_pdf_popup(soup: BeautifulSoup, page_url: str) -> str:
    for link in soup.select("a[onclick]"):
        onclick = link.get("onclick", "")
        match = re.search(r"viewPdfFilePop\('([^']+)','([^']+)','([^']+)'\)", onclick)
        if not match:
            continue
        message_id, message_number, attachment_id = match.groups()
        page_url = (
            "https://bbs2.shinhansec.com/siw/board/message/view.pdf.file.pop.do"
            f"?messageId={message_id}"
            f"&messageNumber={message_number}"
            f"&attachmentId={attachment_id}"
        )
        board_name_match = re.search(r"boardName=([^&]+)", page_url)
        if board_name_match:
            page_url += f"&boardName={board_name_match.group(1)}"
        return page_url
    return ""


def fetch_html_detail(url: str, timeout: int = 20) -> dict:
    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout, verify=False)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")

    detail_text = extract_naver_detail(soup) if "finance.naver.com/research/" in url else ""
    if not detail_text and "bbs2.shinhansec.com/siw/board/message/view.file.pop.do" in url:
        detail_text = extract_shinhan_bbs_detail(soup)
    if not detail_text:
        detail_text = extract_generic_html_text(soup)

    download_url = find_pdf_link(soup, url)
    if not download_url and "bbs2.shinhansec.com/siw/board/message/view.file.pop.do" in url:
        download_url = find_shinhan_pdf_popup(soup, url)

    return {
        "html": response.text,
        "text": detail_text,
        "download_url": download_url,
    }


def fetch_pdf(url: str, timeout: int = 25) -> dict:
    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout, verify=False)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").lower()
    pdf_bytes = response.content
    if "pdf" not in content_type and not pdf_bytes.startswith(b"%PDF"):
        return {"bytes": b"", "text": "", "url": response.url}
    return {
        "bytes": pdf_bytes,
        "text": extract_pdf_text(pdf_bytes),
        "url": response.url,
    }


def enrich_document(doc: RawDocument) -> dict:
    """Fetch richer source text before dedup/save. Mutates doc.content/metadata when useful."""
    metadata = doc.metadata or {}
    artifacts: dict[str, str | bytes] = {}

    detail_url = metadata.get("detail_page_url") or ""
    if not detail_url and doc.url and not looks_like_pdf(doc.url):
        detail_url = doc.url

    if detail_url and any(token in detail_url for token in [
        "finance.naver.com/research/",
        "bbs2.shinhansec.com/siw/board/message/view.file.pop.do",
        "read",
        "report",
        "research",
    ]):
        try:
            detail = fetch_html_detail(detail_url)
            detail_text = detail.get("text", "") or ""
            if detail_text:
                doc.content = f"{doc.title}\n\n{detail_text}"
                doc.document_type = "research_report" if doc.document_type == "research_meta" else doc.document_type
                metadata["detail_page_url"] = detail_url
                metadata["detail_text_length"] = len(detail_text)
                artifacts["detail_html"] = detail.get("html", "") or ""
                artifacts["detail_text"] = detail_text
            if detail.get("download_url") and not metadata.get("download_url"):
                metadata["download_url"] = detail["download_url"]
        except Exception:
            pass

    download_url = metadata.get("download_url") or (doc.url if looks_like_pdf(doc.url) else "")
    if download_url:
        try:
            pdf_payload = fetch_pdf(download_url)
            if pdf_payload.get("bytes"):
                pdf_text = pdf_payload.get("text", "") or ""
                if pdf_text and len(pdf_text) > max(len(doc.content), 300):
                    doc.content = f"{doc.title}\n\n{pdf_text}"
                    doc.document_type = "research_report"
                metadata["download_url"] = pdf_payload.get("url", download_url)
                metadata["pdf_text_length"] = len(pdf_text)
                artifacts["pdf_bytes"] = pdf_payload["bytes"]
                if pdf_text:
                    artifacts["pdf_text"] = pdf_text
            elif "bbs2.shinhansec.com/siw/board/message/view.pdf.file.pop.do" in download_url:
                metadata["download_login_required"] = True
        except Exception:
            if "bbs2.shinhansec.com/siw/board/message/view.pdf.file.pop.do" in download_url:
                metadata["download_login_required"] = True

    doc.metadata = metadata
    return artifacts


def save_artifacts(doc: RawDocument, artifacts: dict, raw_dir: Path, base_dir: Path) -> dict:
    """Persist fetched HTML/PDF/text artifacts next to the raw json file."""
    refs = {}
    if artifacts.get("detail_html"):
        path = raw_dir / f"{doc.doc_id}_detail.html"
        path.write_text(artifacts["detail_html"], encoding="utf-8")
        refs["detail_html_path"] = str(path.relative_to(base_dir))
    if artifacts.get("detail_text"):
        path = raw_dir / f"{doc.doc_id}_detail.txt"
        path.write_text(artifacts["detail_text"], encoding="utf-8")
        refs["detail_text_path"] = str(path.relative_to(base_dir))
    if artifacts.get("pdf_bytes"):
        path = raw_dir / f"{doc.doc_id}.pdf"
        path.write_bytes(artifacts["pdf_bytes"])
        refs["pdf_path"] = str(path.relative_to(base_dir))
    if artifacts.get("pdf_text"):
        path = raw_dir / f"{doc.doc_id}.txt"
        path.write_text(artifacts["pdf_text"], encoding="utf-8")
        refs["pdf_text_path"] = str(path.relative_to(base_dir))
    return refs
