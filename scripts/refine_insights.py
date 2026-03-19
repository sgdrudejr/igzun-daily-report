#!/usr/bin/env python3
import json, re
from pathlib import Path

PDF_JSON = Path('/Users/seo/.openclaw/workspace/igzun-daily-report/data/processed_pdf_texts.json')
RAW_BASE = Path('/Users/seo/.openclaw/workspace/2_Project/Reporting/input/raw')
OUT = Path('/Users/seo/.openclaw/workspace/igzun-daily-report/data/refined_insights_inventory.json')

TITLE_MAP = [
    ('fomc', '연준 금리 동결 및 향후 전망'),
    ('inflation', '인플레이션 및 금리 경로 점검'),
    ('oil', '유가 상승과 에너지 시장 영향'),
    ('iran', '이란 리스크와 글로벌 시장 파급'),
    ('housing', '미국 주택시장 전망'),
    ('market outlook', '시장 전망'),
    ('outlook', '거시 및 시장 전망'),
    ('daily', '일일 시장 브리핑')
]


def summarize_sentiment(text):
    low = text.lower()
    score = 0.0
    rationale = []
    if 'hold rates steady' in low or '동결' in text:
        score -= 0.2; rationale.append('금리 동결')
    if 'inflation' in low or '인플레' in text:
        score -= 0.3; rationale.append('인플레이션 부담')
    if 'rate cuts' in low or '금리 인하' in text:
        score += 0.2; rationale.append('금리 인하 기대')
    if 'oil' in low or '유가' in text:
        score -= 0.2; rationale.append('유가 부담')
    if 'growth' in low or '성장' in text:
        score += 0.2; rationale.append('성장 기대')
    score = max(-1.0, min(1.0, score))
    return score, ', '.join(rationale) if rationale else '원문 기반 중립 판정'


def takeaways(text):
    sents = re.split(r'(?<=[.!?])\s+', text)
    out = []
    for s in sents:
        s = s.strip()
        if len(s) < 40:
            continue
        out.append(s[:140] + ('...' if len(s) > 140 else ''))
        if len(out) == 3:
            break
    return out or ['요약 문장 추출 실패', '원문 정제는 완료됨', '후속 LLM 요약 고도화 필요']


def impact_assets(text):
    low = text.lower()
    usd = '중립'; bonds='중립'; stocks='중립'
    if 'inflation' in low or '유가' in text or 'oil' in low:
        usd='강세'; bonds='금리 상승/가격 하락'; stocks='약세'
    if 'rate cuts' in low or '금리 인하' in text:
        bonds='가격 상승 가능'; stocks='완화적'; usd='약세 가능'
    return {'USD': usd, 'Bonds': bonds, 'Stocks': stocks}


def core_subject(name, text):
    low = (name + ' ' + text[:500]).lower()
    for k, v in TITLE_MAP:
        if k in low:
            return v
    return '거시/시장 리포트 요약'


def extract_date(path_str):
    m = re.search(r'(2026-\d{2}-\d{2})', path_str)
    return m.group(1) if m else ''


def load_txt_files():
    items = []
    for p in sorted(RAW_BASE.rglob('*.txt')):
        try:
            txt = p.read_text(errors='ignore')
        except Exception:
            continue
        items.append({'source_file': p.name, 'source_path': str(p), 'date': extract_date(str(p)), 'clean_text': re.sub(r'\s+', ' ', txt).strip()})
    return items


def build_item(source_file, source_path, date, clean_text):
    text = clean_text or ''
    score, rationale = summarize_sentiment(text)
    return {
        'source_file': source_file,
        'date': date,
        'core_subject': core_subject(source_file, text),
        'sentiment': {'score': score, 'rationale': rationale},
        'key_takeaways': takeaways(text),
        'impact_assets': impact_assets(text),
        'source_meta': {'display_name': source_file, 'broker_or_source': source_path.split('/raw/')[-1].split('/')[0] if '/raw/' in source_path else '', 'path': source_path}
    }


def main():
    pdf_items = json.loads(PDF_JSON.read_text()) if PDF_JSON.exists() else []
    txt_items = load_txt_files()
    results = []
    for item in pdf_items:
        results.append(build_item(item.get('source_file',''), item.get('source_path',''), extract_date(item.get('source_path','')), item.get('clean_text','')))
    for item in txt_items:
        results.append(build_item(item['source_file'], item['source_path'], item['date'], item['clean_text']))
    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print('wrote', OUT, 'count=', len(results))

if __name__ == '__main__':
    main()
