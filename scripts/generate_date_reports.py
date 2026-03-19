#!/usr/bin/env python3
import json, re
from pathlib import Path
from datetime import date, timedelta

WS = Path('/Users/seo/.openclaw/workspace')
ROOT = Path('/Users/seo/.openclaw/workspace/igzun-daily-report')
RAW = WS / '2_Project/Reporting/input/raw'
TEMPLATE = ROOT / 'templates/report.html'
INVENTORY = ROOT / 'data/raw_inventory_2026-02-19_to_2026-03-19.json'


def list_dates(start, end):
    cur = start
    out = []
    while cur <= end:
        out.append(cur)
        cur += timedelta(days=1)
    return out


def files_for_day(ds):
    return sorted([p for p in RAW.rglob(f'*{ds}*') if p.is_file()])


def first_text_summary(paths):
    for p in paths:
        if p.suffix.lower() == '.txt':
            try:
                txt = p.read_text(errors='ignore')
            except Exception:
                continue
            txt = re.sub(r'\s+', ' ', txt).strip()
            if txt:
                return txt[:280] + ('...' if len(txt) > 280 else '')
    return '해당 날짜의 원문은 존재하지만 자동 요약 본문 추출은 아직 제한적입니다.'


def build_result(ds, files):
    by_source = {}
    for p in files:
        parts = p.parts
        try:
            idx = parts.index('raw')
            source = '/'.join(parts[idx+1:idx+3])
        except Exception:
            source = 'unknown'
        by_source[source] = by_source.get(source, 0) + 1
    top_sources = sorted(by_source.items(), key=lambda x: (-x[1], x[0]))[:5]
    summary = first_text_summary(files)
    period = {
        'briefing': {
            'sentiment': {'score': 50, 'status': '중립', 'desc': f'{ds} 수집 원문 {len(files)}건 기준 자동 생성된 기본 브리핑입니다.'},
            'forecast': {'title': '해당 날짜 자동 브리핑', 'text': summary, 'sources': [{'label': s, 'source': s.split('/')[-1], 'title': s, 'published_at': ds} for s,_ in top_sources]},
            'insights': [{'category': '원문수집', 'text': f'해당 날짜 raw 파일 {len(files)}건 확보. 상위 출처: ' + ', '.join([f'{s}({c})' for s,c in top_sources]), 'sources': [{'label': s, 'source': s.split('/')[-1], 'title': s, 'published_at': ds} for s,_ in top_sources]}],
            'indices': []
        },
        'newsList': [{
            'title': '해당 날짜 수집 이슈 요약',
            'tags': ['자동생성', '원문기반', '수집완료'],
            'summary': summary,
            'impacts': [{'sector': '시장 전반', 'isPositive': True, 'desc': '상세 영향은 후속 정교화 예정'}],
            'sources': [{'label': s, 'source': s.split('/')[-1], 'title': s, 'published_at': ds} for s,_ in top_sources]
        }],
        'portfolio': {
            'accountAlert': '과거 날짜 포트폴리오 원본 미연결',
            'accountDetail': '해당 날짜는 우선 원문 수집 결과와 시장 해석만 제공합니다.',
            'weeklyReview': {'returnRate': '데이터 미연결', 'desc': '계좌 스냅샷 필요'},
            'holdings': [],
            'planDesc': '과거 날짜는 전략 설명만 임시 제공',
            'allocations': []
        },
        'recommendations': {'ideas': [], 'etfRanking': []},
        'raw_sources': {'news': [str(p) for p in files[:20]], 'market': [], 'reports': [str(p) for p in files[:20]], 'portfolio': []}
    }
    return {'date': f'{ds} 기준 업데이트', 'dataByPeriod': {'1일': period}}


def main():
    start = date(2026,2,19); end = date(2026,3,19)
    inventory = []
    template = TEMPLATE.read_text()
    for d in list_dates(start, end):
        ds = d.isoformat()
        files = files_for_day(ds)
        inventory.append({'date': ds, 'count': len(files)})
        if not files:
            continue
        outdir = ROOT / 'site' / ds
        outdir.mkdir(parents=True, exist_ok=True)
        result = build_result(ds, files)
        (outdir / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
        (outdir / 'index.html').write_text(template)
    INVENTORY.write_text(json.dumps(inventory, ensure_ascii=False, indent=2))
    print('wrote', INVENTORY)

if __name__ == '__main__':
    main()
