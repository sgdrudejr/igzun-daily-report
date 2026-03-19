#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import date, timedelta

ROOT = Path('/Users/seo/.openclaw/workspace/igzun-daily-report')
INS = ROOT / 'data/refined_insights_inventory.json'
SITE = ROOT / 'site'


def load_insights():
    return json.loads(INS.read_text()) if INS.exists() else []


def parse_date(ds):
    y, m, d = map(int, ds.split('-'))
    return date(y, m, d)


def group_by_date(items):
    out = {}
    for x in items:
        out.setdefault(x.get('date', ''), []).append(x)
    return out


def date_range_items(by_date, end_ds, days):
    end = parse_date(end_ds)
    acc = []
    for i in range(days):
        ds = (end - timedelta(days=i)).isoformat()
        acc.extend(by_date.get(ds, []))
    return acc


def status_from_count(count):
    if count >= 8:
        return 'full'
    if count >= 3:
        return 'partial'
    if count >= 1:
        return 'sparse'
    return 'empty'


def score_to_ui(items):
    if not items:
        return {'score': 50, 'status': '중립', 'desc': '정제 인사이트 없음'}
    vals = [x.get('sentiment', {}).get('score', 0.0) for x in items]
    avg = sum(vals) / len(vals)
    ui_score = int(round((avg + 1.0) * 50))
    status = '매파/부정' if avg < -0.2 else ('비둘기/긍정' if avg > 0.2 else '중립')
    rationale = ' / '.join([x.get('sentiment', {}).get('rationale', '') for x in items[:3] if x.get('sentiment', {}).get('rationale')]) or '근거 부족'
    return {'score': ui_score, 'status': status, 'desc': rationale}


def sources_from_items(items, max_n=5):
    out = []
    for x in items[:max_n]:
        out.append({
            'label': x.get('source_file', ''),
            'source': x.get('source_meta', {}).get('broker_or_source', ''),
            'title': x.get('source_file', ''),
            'published_at': x.get('date', '')
        })
    return out


def aggregate_period(label, items):
    if not items:
        return None
    title = {
        '1일': '당일 핵심 인사이트',
        '3일': '최근 3일 누적 인사이트',
        '1주': '최근 1주 누적 인사이트',
        '1개월': '최근 1개월 누적 인사이트'
    }.get(label, f'{label} 인사이트')
    takeaways = []
    for x in items[:3]:
        for t in x.get('key_takeaways', [])[:1]:
            if t and t not in takeaways:
                takeaways.append(t)
    while len(takeaways) < 3:
        takeaways.append('정제 인사이트 추가 수집 필요')
    news_list = []
    for x in items[:8]:
        news_list.append({
            'title': x.get('core_subject', '주요 이슈'),
            'tags': ['정제인사이트', label, '원문기반'],
            'summary': ' / '.join(x.get('key_takeaways', [])[:2]),
            'impacts': [
                {'sector': 'USD', 'isPositive': x.get('impact_assets', {}).get('USD', '') in ['강세', '긍정'], 'desc': x.get('impact_assets', {}).get('USD', '중립')},
                {'sector': 'Bonds', 'isPositive': '상승' in x.get('impact_assets', {}).get('Bonds', ''), 'desc': x.get('impact_assets', {}).get('Bonds', '중립')},
                {'sector': 'Stocks', 'isPositive': x.get('impact_assets', {}).get('Stocks', '') in ['강세', '긍정', '완화적'], 'desc': x.get('impact_assets', {}).get('Stocks', '중립')}
            ],
            'sources': sources_from_items([x], 1)
        })
    period = {
        'briefing': {
            'sentiment': score_to_ui(items),
            'forecast': {
                'title': title,
                'text': '<br>'.join([f'{i+1}. {t}' for i, t in enumerate(takeaways[:3])]),
                'sources': sources_from_items(items, 5)
            },
            'insights': [
                {'category': label, 'text': t, 'sources': sources_from_items(items, 3)} for t in takeaways[:3]
            ],
            'indices': []
        },
        'newsList': news_list,
        'portfolio': {
            'accountAlert': f'{label} 기간은 정제 리포트 기반 해석 우선',
            'accountDetail': '실계좌 데이터 미연결 상태로 모델 코멘트만 유지합니다.',
            'weeklyReview': {'returnRate': '실계좌 미연결', 'desc': '계좌 스냅샷이 들어오면 실제 성과 계산으로 교체됩니다.'},
            'holdings': [],
            'planDesc': f'{label} 기준 포트폴리오 전략 코멘트는 후속 계좌 연동 시 보강됩니다.',
            'allocations': []
        },
        'recommendations': {'ideas': [], 'etfRanking': []}
    }
    return period


def integrate(date_str, path, by_date):
    obj = json.loads(path.read_text())
    periods = {
        '1일': date_range_items(by_date, date_str, 1),
        '3일': date_range_items(by_date, date_str, 3),
        '1주': date_range_items(by_date, date_str, 7),
        '1개월': date_range_items(by_date, date_str, 30),
    }
    obj['dataByPeriod'] = obj.get('dataByPeriod', {})
    for label, items in periods.items():
        agg = aggregate_period(label, items)
        if agg:
            obj['dataByPeriod'][label] = agg
    day_count = len(periods['1일'])
    obj['dataStatus'] = status_from_count(day_count)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2))
    return True


def main():
    items = load_insights()
    by_date = group_by_date(items)
    for p in SITE.glob('2026-*/result.json'):
        ds = p.parent.name
        integrate(ds, p, by_date)
    print('integrated refined insights with period aggregation')

if __name__ == '__main__':
    main()
