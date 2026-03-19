#!/usr/bin/env python3
import json, re
from pathlib import Path
import fitz

RAW_BASE = Path('/Users/seo/.openclaw/workspace/2_Project/Reporting/input/raw')
OUT = Path('/Users/seo/.openclaw/workspace/igzun-daily-report/data/processed_pdf_texts.json')

HEADER_PATTERNS = [
    r'^\s*page\s+\d+\s*$', r'^\s*\d+\s*/\s*\d+\s*$', r'^\s*\d+\s*$',
    r'^\s*KB\s*데일리\s*$', r'^\s*NH.*리서치.*$', r'^\s*미래에셋.*$',
]
NOISE_PATTERNS = [
    r'https?://\S+', r'www\.\S+', r'\bPage\s+\d+\b', r'\bBloomberg\b'
]


def normalize_blocks(page):
    blocks = page.get_text('blocks')
    blocks = sorted(blocks, key=lambda b: (round(b[1], 1), round(b[0], 1)))
    lines = []
    for b in blocks:
        txt = b[4].strip()
        if not txt:
            continue
        txt = txt.replace('\u00a0', ' ')
        parts = [x.strip() for x in txt.splitlines() if x.strip()]
        lines.extend(parts)
    return lines


def clean_lines(lines):
    out = []
    prev_blank = False
    seen = {}
    for line in lines:
        raw = line.strip()
        if any(re.match(p, raw, flags=re.I) for p in HEADER_PATTERNS):
            continue
        for pat in NOISE_PATTERNS:
            raw = re.sub(pat, '', raw, flags=re.I)
        raw = re.sub(r'\s+', ' ', raw).strip()
        if not raw:
            if not prev_blank:
                out.append('')
            prev_blank = True
            continue
        prev_blank = False
        seen[raw] = seen.get(raw, 0) + 1
        out.append(raw)
    # remove repeated header/footer-ish lines that appear too often
    out2 = []
    for line in out:
        if line and seen.get(line, 0) >= 4 and len(line) < 80:
            continue
        out2.append(line)
    return out2


def stitch_paragraphs(lines):
    paras = []
    buf = []
    for line in lines:
        if not line:
            if buf:
                paras.append(' '.join(buf))
                buf = []
            continue
        # keep bullet-ish starts as new paragraph
        if re.match(r'^[•\-\d\)]', line) and buf:
            paras.append(' '.join(buf))
            buf = [line]
        else:
            buf.append(line)
    if buf:
        paras.append(' '.join(buf))
    text = '\n\n'.join(paras)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n\s+', '\n', text)
    return text.strip()


def extract_pdf(path: Path):
    try:
        doc = fitz.open(str(path))
        lines = []
        for page in doc:
            lines.extend(normalize_blocks(page))
            lines.append('')
        raw = '\n'.join(lines)
        clean = stitch_paragraphs(clean_lines(lines))
        return {
            'source_file': path.name,
            'source_path': str(path),
            'page_count': len(doc),
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
