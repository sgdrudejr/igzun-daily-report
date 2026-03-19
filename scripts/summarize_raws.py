#!/usr/bin/env python3
import re
from pathlib import Path


def clean_text(txt: str) -> str:
    txt = re.sub(r'\s+', ' ', txt).strip()
    return txt


def summarize_text(txt: str, max_chars: int = 240) -> str:
    txt = clean_text(txt)
    if not txt:
        return ''
    # heuristic summary: first 2 sentences or truncated first chunk
    parts = re.split(r'(?<=[.!?])\s+', txt)
    cand = ' '.join(parts[:2]).strip()
    if len(cand) < 60:
        cand = txt[:max_chars]
    return cand[:max_chars] + ('...' if len(cand) > max_chars else '')


def summarize_file(path: str) -> str:
    p = Path(path)
    if not p.exists() or p.suffix.lower() not in {'.txt', '.html', '.md'}:
        return ''
    try:
        txt = p.read_text(errors='ignore')
    except Exception:
        return ''
    return summarize_text(txt)
