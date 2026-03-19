#!/usr/bin/env python3
import json, re, sys
from pathlib import Path
from pypdf import PdfReader

RAW_BASE = Path('/Users/seo/.openclaw/workspace/2_Project/Reporting/input/raw')
OUT = Path('/Users/seo/.openclaw/workspace/igzun-daily-report/data/processed_pdf_texts.json')

HEADER_PATTERNS = [
    r'^\s*page\s+\d+\s*$', r'^\s*\d+\s*/\s*\d+\s*$', r'^\s*\d+\s*$'
]
NOISE_PATTERNS = [
    r'https?://\S+', r'www\.\S+', r'\bBloomberg\b', r'\bPage\s+\d+\b'
]


def clean_text(text: str) -> str:
    lines = [l.strip() for l in text.splitlines()]
    out = []
    prev_blank = False
    for line in lines:
        if any(re.match(p, line, flags=re.I) for p in HEADER_PATTERNS):
            continue
        for pat in NOISE_PATTERNS:
            line = re.sub(pat, '', line, flags=re.I)
        line = re.sub(r'\s+', ' ', line).strip()
        if not line:
            if not prev_blank:
                out.append('')
            prev_blank = True
            continue
        prev_blank = False
        out.append(line)
    joined = '\n'.join(out)
    # merge broken line wraps inside paragraphs
    joined = re.sub(r'(?<!\n)\n(?!\n)', ' ', joined)
    joined = re.sub(r'\n{3,}', '\n\n', joined)
    joined = re.sub(r'\s+', ' ', joined)
    return joined.strip()


def extract_pdf(path: Path):
    try:
        reader = PdfReader(str(path))
        texts = []
        for page in reader.pages:
            txt = page.extract_text() or ''
            texts.append(txt)
        raw = '\n\n'.join(texts)
        clean = clean_text(raw)
        return {
            'source_file': path.name,
            'source_path': str(path),
            'page_count': len(reader.pages),
            'raw_text_len': len(raw),
            'clean_text_len': len(clean),
            'clean_text': clean
        }
    except Exception as e:
        return {
            'source_file': path.name,
            'source_path': str(path),
            'error': str(e),
            'clean_text': ''
        }


def main():
    pdfs = sorted(RAW_BASE.rglob('*.pdf'))
    results = [extract_pdf(p) for p in pdfs]
    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print('wrote', OUT, 'count=', len(results))

if __name__ == '__main__':
    main()
