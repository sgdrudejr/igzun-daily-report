#!/usr/bin/env python3
import json, re, sys
from pathlib import Path


def chunk_text(text, max_chars=1200, overlap=150):
    text = re.sub(r'\s+', ' ', text).strip()
    chunks = []
    i = 0
    n = len(text)
    while i < n:
        chunk = text[i:i+max_chars]
        chunks.append(chunk)
        if i + max_chars >= n:
            break
        i += max_chars - overlap
    return chunks


def main():
    if len(sys.argv) < 3:
        print('usage: chunk_raws.py <input-file> <output-json>')
        sys.exit(1)
    src = Path(sys.argv[1])
    out = Path(sys.argv[2])
    txt = src.read_text(errors='ignore')
    chunks = chunk_text(txt)
    payload = {'source': str(src), 'chunk_count': len(chunks), 'chunks': [{'id': i+1, 'text': c} for i,c in enumerate(chunks)]}
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print('wrote', out)

if __name__ == '__main__':
    main()
