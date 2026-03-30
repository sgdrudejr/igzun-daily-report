#!/usr/bin/env python3
"""
경량 H-RAG용 계층형 인덱스 생성기.

목적:
- 최근 누적 문서를 문서/섹션/청크 3단계로 재구성한다.
- 완전한 벡터 DB 없이도 로컬에서 깊이 있는 수동/반자동 리서치의 기반을 만든다.

Output:
- data/research_index/hierarchical/{date}.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from build_research_context import SOURCE_NAMES, available_dates, docs_for_date, extract_topics, safe_text

PRIORITY_SOURCES = {
    "fed_speeches_rss",
    "fed_press_rss",
    "bis_speeches",
    "naver_research",
    "kr_brokerage_kb",
    "kr_brokerage_mirae",
    "kr_brokerage_shinhan",
    "fred_api",
    "ecos_api",
}


def _score_doc(doc: dict) -> float:
    score = 0.0
    source_id = doc.get("source_id") or ""
    if source_id in PRIORITY_SOURCES:
        score += 10
    dtype = (doc.get("document_type") or "").lower()
    if "report" in dtype or "speech" in dtype:
        score += 5
    if "news" in dtype:
        score += 2
    summary = safe_text(doc.get("summary"))
    content = safe_text(doc.get("content"))
    score += min(len(summary), 400) / 100
    score += min(len(content), 1200) / 300
    return score


def _split_sections(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    blocks = [block.strip() for block in re.split(r"\n{2,}", text) if block.strip()]
    if blocks:
        return blocks[:6]
    sentences = re.split(r"(?<=[.!?。])\s+", text)
    sections = []
    current = []
    current_len = 0
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if current_len + len(sentence) > 420 and current:
            sections.append(" ".join(current))
            current = [sentence]
            current_len = len(sentence)
        else:
            current.append(sentence)
            current_len += len(sentence)
    if current:
        sections.append(" ".join(current))
    return sections[:6]


def _chunk_text(text: str, max_chars: int = 380, overlap: int = 60) -> list[str]:
    text = text.strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return [chunk for chunk in chunks if chunk][:8]


def build_hierarchical_index(root: Path, date_str: str, max_docs: int = 260) -> dict:
    target_date = date.fromisoformat(date_str)
    dates = available_dates(root, target_date)[-30:]

    all_docs = []
    for ds in dates:
        for doc in docs_for_date(root, ds):
            item = dict(doc)
            item["_bucket_date"] = ds
            all_docs.append(item)

    ranked_docs = sorted(all_docs, key=_score_doc, reverse=True)[:max_docs]

    documents = []
    sections = []
    chunks = []
    topic_counter_docs = []

    for idx, doc in enumerate(ranked_docs, 1):
        doc_id = doc.get("id") or f"doc-{idx}"
        title = safe_text(doc.get("title")) or f"문서 {idx}"
        summary = safe_text(doc.get("summary"))
        content = safe_text(doc.get("content"))
        merged_text = "\n\n".join(part for part in [summary, content] if part).strip() or title
        topics = extract_topics([doc])
        topic_names = [item["topic"] for item in topics[:4]]
        topic_counter_docs.extend(topic_names)

        documents.append(
            {
                "doc_id": doc_id,
                "date": doc.get("_bucket_date"),
                "source_id": doc.get("source_id"),
                "source_label": SOURCE_NAMES.get(doc.get("source_id"), doc.get("source_id")),
                "title": title,
                "region": doc.get("region"),
                "document_type": doc.get("document_type"),
                "topics": topic_names,
                "coarse_summary": (summary or content or title)[:260],
            }
        )

        for section_idx, section_text in enumerate(_split_sections(merged_text), 1):
            section_id = f"{doc_id}::sec{section_idx}"
            sections.append(
                {
                    "section_id": section_id,
                    "doc_id": doc_id,
                    "heading": section_text[:40],
                    "summary": section_text[:220],
                    "topics": topic_names,
                }
            )
            for chunk_idx, chunk_text in enumerate(_chunk_text(section_text), 1):
                chunks.append(
                    {
                        "chunk_id": f"{section_id}::chunk{chunk_idx}",
                        "section_id": section_id,
                        "doc_id": doc_id,
                        "text": chunk_text,
                        "topics": topic_names,
                    }
                )

    top_topics = []
    counts = {}
    for topic in topic_counter_docs:
        counts[topic] = counts.get(topic, 0) + 1
    for topic, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:8]:
        top_topics.append({"topic": topic, "count": count})

    return {
        "date": date_str,
        "window": {
            "from_date": dates[0] if dates else date_str,
            "to_date": date_str,
            "window_days": len(dates),
        },
        "summary": {
            "raw_document_count": len(all_docs),
            "indexed_document_count": len(documents),
            "section_count": len(sections),
            "chunk_count": len(chunks),
            "top_topics": top_topics,
        },
        "documents": documents,
        "sections": sections,
        "chunks": chunks,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--base-dir", default=str(ROOT))
    parser.add_argument("--max-docs", type=int, default=260)
    args = parser.parse_args()

    root = Path(args.base_dir)
    index = build_hierarchical_index(root, args.date, max_docs=args.max_docs)

    out_dir = root / "data" / "research_index" / "hierarchical"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{args.date}.json"
    out_file.write_text(json.dumps(index, ensure_ascii=False, indent=2))
    print(f"wrote {out_file}")
    print(json.dumps(index["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
