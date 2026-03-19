#!/usr/bin/env python3
import json, re, subprocess, tempfile, os, time
from pathlib import Path

PDF_JSON = Path('/Users/seo/.openclaw/workspace/igzun-daily-report/data/processed_pdf_texts.json')
RAW_BASE = Path('/Users/seo/.openclaw/workspace/2_Project/Reporting/input/raw')
OUT = Path('/Users/seo/.openclaw/workspace/igzun-daily-report/data/refined_insights_inventory.json')

PROMPT_TEMPLATE = '''다음 금융/매크로 리포트 본문을 읽고 반드시 JSON만 출력하라.
조건:
- 한국어로 쓸 것
- core_subject는 핵심 주제를 짧게
- sentiment.score는 -1.0 ~ 1.0
- key_takeaways는 정확히 3개
- impact_assets는 USD, Bonds, Stocks 3개 키를 반드시 포함
- 과도한 추측 금지. 본문에 없는 것은 보수적으로 작성

출력 JSON 스키마:
{
  "core_subject": "string",
  "sentiment": {"score": 0.0, "rationale": "string"},
  "key_takeaways": ["string", "string", "string"],
  "impact_assets": {"USD": "string", "Bonds": "string", "Stocks": "string"}
}

문서 제목: {title}
문서 본문:
{text}
'''

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


def clean_text(text):
    return re.sub(r'\s+', ' ', text).strip()


def heuristic_item(source_file, source_path, date, text):
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
    score = max(-1.0, min(1.0, score))
    subject = '거시/시장 리포트 요약'
    low_title = (source_file + ' ' + text[:500]).lower()
    for k, v in TITLE_MAP:
        if k in low_title:
            subject = v; break
    sents = re.split(r'(?<=[.!?])\s+', text)
    takes = []
    for s in sents:
        s = s.strip()
        if len(s) < 40:
            continue
        takes.append(s[:140] + ('...' if len(s) > 140 else ''))
        if len(takes) == 3:
            break
    while len(takes) < 3:
        takes.append('추가 핵심 문장 추출 필요')
    impact = {'USD':'중립','Bonds':'중립','Stocks':'중립'}
    if 'inflation' in low or '유가' in text or 'oil' in low:
        impact={'USD':'강세','Bonds':'금리 상승/가격 하락','Stocks':'약세'}
    elif 'rate cuts' in low or '금리 인하' in text:
        impact={'USD':'약세 가능','Bonds':'가격 상승 가능','Stocks':'완화적'}
    return {
        'source_file': source_file,
        'date': date,
        'core_subject': subject,
        'sentiment': {'score': score, 'rationale': ', '.join(rationale) if rationale else '원문 기반 중립 판정'},
        'key_takeaways': takes,
        'impact_assets': impact,
        'source_meta': {'display_name': source_file, 'broker_or_source': source_path.split('/raw/')[-1].split('/')[0] if '/raw/' in source_path else '', 'path': source_path}
    }


def try_llm(title, text, retries=2):
    prompt = PROMPT_TEMPLATE.format(title=title, text=text[:12000])
    with tempfile.NamedTemporaryFile('w', delete=False, suffix='.txt') as f:
        f.write(prompt)
        prompt_path = f.name
    try:
        for attempt in range(retries + 1):
            try:
                cmd = ['summarize', prompt_path, '--length', 'short']
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
                if proc.returncode != 0:
                    raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
                out = proc.stdout.strip()
                m = re.search(r'\{.*\}', out, flags=re.S)
                if not m:
                    raise ValueError('JSON not found in LLM output')
                obj = json.loads(m.group(0))
                return obj
            except Exception:
                if attempt >= retries:
                    raise
                time.sleep(1.5 * (attempt + 1))
    finally:
        try: os.unlink(prompt_path)
        except Exception: pass


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
        items.append({'source_file': p.name, 'source_path': str(p), 'date': extract_date(str(p)), 'clean_text': clean_text(txt)})
    return items


def build_item(source_file, source_path, date, clean_text_value):
    text = clean_text(clean_text_value or '')
    if not text:
        return heuristic_item(source_file, source_path, date, text)
    try:
        llm = try_llm(source_file, text)
        return {
            'source_file': source_file,
            'date': date,
            'core_subject': llm.get('core_subject', '거시/시장 리포트 요약'),
            'sentiment': llm.get('sentiment', {'score': 0.0, 'rationale': 'LLM 응답 누락'}),
            'key_takeaways': llm.get('key_takeaways', ['요약 누락', '요약 누락', '요약 누락'])[:3],
            'impact_assets': llm.get('impact_assets', {'USD':'중립','Bonds':'중립','Stocks':'중립'}),
            'source_meta': {'display_name': source_file, 'broker_or_source': source_path.split('/raw/')[-1].split('/')[0] if '/raw/' in source_path else '', 'path': source_path},
            'analysis_mode': 'llm'
        }
    except Exception:
        item = heuristic_item(source_file, source_path, date, text)
        item['analysis_mode'] = 'heuristic_fallback'
        return item


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
