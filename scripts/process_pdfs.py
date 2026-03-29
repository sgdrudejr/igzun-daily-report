#!/usr/bin/env python3
import json
import os
import re
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parent.parent
RAW_BASE = Path(os.getenv("IGZUN_REPORTING_RAW_BASE", "/Users/seo/.openclaw/workspace/2_Project/Reporting/input/raw"))
OUT = ROOT / "data/processed_pdf_texts.json"

HEADER_PATTERNS = [
    r"^\s*page\s+\d+\s*$",
    r"^\s*\d+\s*/\s*\d+\s*$",
    r"^\s*\d+\s*$",
    r"^\s*KB\s*데일리\s*$",
    r"^\s*NH.*리서치.*$",
    r"^\s*미래에셋.*$",
]
NOISE_PATTERNS = [r"https?://\S+", r"www\.\S+", r"\bPage\s+\d+\b", r"\bBloomberg\b"]


def normalize_blocks(page):
    blocks = page.get_text("blocks")
    blocks = sorted(blocks, key=lambda block: (round(block[1], 1), round(block[0], 1)))
    lines = []
    for block in blocks:
        text = block[4].strip()
        if not text:
            continue
        text = text.replace("\u00a0", " ")
        lines.extend(part.strip() for part in text.splitlines() if part.strip())
    return lines


def clean_lines(lines):
    cleaned = []
    prev_blank = False
    seen = {}
    for line in lines:
        raw = line.strip()
        if any(re.match(pattern, raw, flags=re.I) for pattern in HEADER_PATTERNS):
            continue
        for pattern in NOISE_PATTERNS:
            raw = re.sub(pattern, "", raw, flags=re.I)
        raw = re.sub(r"\s+", " ", raw).strip()
        if not raw:
            if not prev_blank:
                cleaned.append("")
            prev_blank = True
            continue
        prev_blank = False
        seen[raw] = seen.get(raw, 0) + 1
        cleaned.append(raw)

    filtered = []
    for line in cleaned:
        if line and seen.get(line, 0) >= 4 and len(line) < 80:
            continue
        filtered.append(line)
    return filtered


def stitch_paragraphs(lines):
    paragraphs = []
    buffer = []
    for line in lines:
        if not line:
            if buffer:
                paragraphs.append(" ".join(buffer))
                buffer = []
            continue
        if re.match(r"^[•\-\d\)]", line) and buffer:
            paragraphs.append(" ".join(buffer))
            buffer = [line]
        else:
            buffer.append(line)
    if buffer:
        paragraphs.append(" ".join(buffer))
    text = "\n\n".join(paragraphs)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\n\s+", "\n", text)
    return text.strip()


def extract_pdf(path: Path):
    try:
        doc = fitz.open(str(path))
        lines = []
        for page in doc:
            lines.extend(normalize_blocks(page))
            lines.append("")
        raw = "\n".join(lines)
        clean = stitch_paragraphs(clean_lines(lines))
        return {
            "source_file": path.name,
            "source_path": str(path),
            "page_count": len(doc),
            "raw_text_len": len(raw),
            "clean_text_len": len(clean),
            "clean_text": clean,
        }
    except Exception as exc:
        return {
            "source_file": path.name,
            "source_path": str(path),
            "error": str(exc),
            "clean_text": "",
        }


def main():
    pdfs = sorted(RAW_BASE.rglob("*.pdf")) if RAW_BASE.exists() else []
    results = [extract_pdf(path) for path in pdfs]
    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print("wrote", OUT, "count=", len(results))


if __name__ == "__main__":
    main()
