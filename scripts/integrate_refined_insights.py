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
    rationale = ' / '.join([x.get('sentiment', {}).get('rationale', '') for x in items[:5] if x.get('sentiment', {}).get('rationale')]) or '근거 부족'
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


def aggregate_short(label, items):
    takeaways = []
    for x in items[:6]:
        for t in x.get('key_takeaways', [])[:1]:
            if t and t not in takeaways:
                takeaways.append(t)
    while len(takeaways) < 3:
        takeaways.append('정제 인사이트 추가 수집 필요')
    title = '당일 핵심 인사이트' if label == '1일' else ('최근 3일 누적 인사이트' if label == '3일' else '최근 1주 누적 인사이트')
    return {
        'briefing': {
            'sentiment': score_to_ui(items),
            'forecast': {
                'title': title,
                'text': '<br>'.join([f'{i+1}. {t}' for i, t in enumerate(takeaways[:3])]),
                'sources': sources_from_items(items, 5)
            },
            'insights': [{'category': label, 'text': t, 'sources': sources_from_items(items, 3)} for t in takeaways[:3]],
            'indices': []
        },
        'newsList': [
            {
                'title': x.get('core_subject', '주요 이슈'),
                'tags': ['정제인사이트', label, '원문기반'],
                'summary': ' / '.join(x.get('key_takeaways', [])[:2]),
                'impacts': [
                    {'sector': 'USD', 'isPositive': x.get('impact_assets', {}).get('USD', '') in ['강세', '긍정'], 'desc': x.get('impact_assets', {}).get('USD', '중립')},
                    {'sector': 'Bonds', 'isPositive': '상승' in x.get('impact_assets', {}).get('Bonds', ''), 'desc': x.get('impact_assets', {}).get('Bonds', '중립')},
                    {'sector': 'Stocks', 'isPositive': x.get('impact_assets', {}).get('Stocks', '') in ['강세', '긍정', '완화적'], 'desc': x.get('impact_assets', {}).get('Stocks', '중립')}
                ],
                'sources': sources_from_items([x], 1)
            } for x in items[:8]
        ],
        'portfolio': {
            'accountAlert': f'{label} 기간은 정제 리포트 기반 해석 우선',
            'accountDetail': '실계좌 데이터 미연결 상태로 모델 코멘트만 유지합니다.',
            'weeklyReview': {'returnRate': '실계좌 미연결', 'desc': '계좌 스냅샷이 들어오면 실제 성과 계산으로 교체됩니다.'},
            'holdings': [], 'planDesc': f'{label} 기준 포트폴리오 전략 코멘트는 후속 계좌 연동 시 보강됩니다.', 'allocations': []
        },
        'recommendations': {'ideas': [], 'etfRanking': []}
    }


def aggregate_mid(label, items):
    title = '최근 1개월 누적 인사이트'
    subjects = {}
    impacts = {'USD': [], 'Bonds': [], 'Stocks': []}
    for x in items:
        subjects[x.get('core_subject', '기타')] = subjects.get(x.get('core_subject', '기타'), 0) + 1
        ia = x.get('impact_assets', {})
        for k in impacts:
            if ia.get(k): impacts[k].append(ia[k])
    top_subjects = sorted(subjects.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    takes = [f'{s} 관련 인사이트 {c}건 축적' for s, c in top_subjects]
    while len(takes) < 3:
        takes.append('추가 누적 인사이트 필요')
    return {
        'briefing': {
            'sentiment': score_to_ui(items),
            'forecast': {'title': title, 'text': '<br>'.join([f'{i+1}. {t}' for i, t in enumerate(takes)]), 'sources': sources_from_items(items, 6)},
            'insights': [{'category': '내러티브', 'text': t, 'sources': sources_from_items(items, 4)} for t in takes],
            'indices': []
        },
        'newsList': [{
            'title': '1개월 핵심 내러티브 변화',
            'tags': ['내러티브', '자산군 방향성', '누적분석'],
            'summary': ' / '.join(takes[:2]),
            'impacts': [
                {'sector': 'USD', 'isPositive': impacts['USD'].count('강세') >= impacts['USD'].count('약세 가능'), 'desc': impacts['USD'][0] if impacts['USD'] else '중립'},
                {'sector': 'Bonds', 'isPositive': sum('상승' in x for x in impacts['Bonds']) >= sum('하락' in x for x in impacts['Bonds']), 'desc': impacts['Bonds'][0] if impacts['Bonds'] else '중립'},
                {'sector': 'Stocks', 'isPositive': sum(x in ['강세','긍정','완화적'] for x in impacts['Stocks']) >= sum(x in ['약세','부정'] for x in impacts['Stocks']), 'desc': impacts['Stocks'][0] if impacts['Stocks'] else '중립'}
            ],
            'sources': sources_from_items(items, 5)
        }],
        'portfolio': {'accountAlert': '1개월 누적 원문을 기준으로 자산군 방향성을 우선 반영합니다.', 'accountDetail': '실계좌 미연결 상태입니다.', 'weeklyReview': {'returnRate': '실계좌 미연결', 'desc': '계좌 스냅샷 필요'}, 'holdings': [], 'planDesc': '1개월 내러티브 변화 기준 자산배분 해석', 'allocations': []},
        'recommendations': {'ideas': [], 'etfRanking': []}
    }


def aggregate_long_3m(items):
    title = '최근 3개월 거시 구조 변화 분석'
    # regime shift / macro trend / fundamentals 방향성 중심
    texts = ' '.join([x.get('core_subject','') + ' ' + ' '.join(x.get('key_takeaways', [])) + ' ' + x.get('sentiment',{}).get('rationale','') for x in items])
    regime = '중립'
    if any(k in texts for k in ['인플레이션', '유가', '전쟁', '긴축', '금리 동결']):
        regime = '인플레/긴축 레짐'
    if any(k in texts for k in ['성장', '인프라', 'AI', '전력망']):
        regime += ' + 구조적 투자 확대'
    takeaways = [
        f'3개월 누적 기준 거시 레짐은 "{regime}" 성격이 강했음',
        '단기 뉴스가 아니라 누적된 리포트/정책/뉴스를 종합하면 금리·유가·정책 불확실성이 구조적 변수로 반복 확인됨',
        '펀더멘털 방향성은 성장주 내 차별화, 인프라/에너지/방어자산 선호 강화 쪽으로 해석됨'
    ]
    return {
        'briefing': {
            'sentiment': score_to_ui(items),
            'forecast': {'title': title, 'text': '<br>'.join([f'{i+1}. {t}' for i, t in enumerate(takeaways)]), 'sources': sources_from_items(items, 8)},
            'insights': [
                {'category': 'Regime Shift', 'text': takeaways[0], 'sources': sources_from_items(items, 5)},
                {'category': 'Macro Trend', 'text': takeaways[1], 'sources': sources_from_items(items, 5)},
                {'category': 'Fundamental', 'text': takeaways[2], 'sources': sources_from_items(items, 5)}
            ],
            'indices': []
        },
        'newsList': [{
            'title': '3개월 구조 변화 요약',
            'tags': ['Regime Shift', '매크로', '펀더멘털'],
            'summary': ' / '.join(takeaways[:2]),
            'impacts': [
                {'sector': '주식', 'isPositive': False, 'desc': '성장주 전반보다는 차별화 장세'},
                {'sector': '채권', 'isPositive': False, 'desc': '금리/물가 변수에 민감한 구간 지속'},
                {'sector': '실물/인프라', 'isPositive': True, 'desc': '구조적 투자 테마 지속'}
            ],
            'sources': sources_from_items(items, 8)
        }],
        'portfolio': {'accountAlert': '3개월 구간은 구조적 레짐 변화 중심 해석이 우선입니다.', 'accountDetail': '실계좌 미연결 상태입니다.', 'weeklyReview': {'returnRate': '실계좌 미연결', 'desc': '계좌 스냅샷 필요'}, 'holdings': [], 'planDesc': '3개월 누적 거시 트렌드 기준 자산배분', 'allocations': []},
        'recommendations': {'ideas': [], 'etfRanking': []}
    }


def integrate(date_str, path, by_date):
    obj = json.loads(path.read_text())
    p1 = date_range_items(by_date, date_str, 1)
    p3 = date_range_items(by_date, date_str, 3)
    p7 = date_range_items(by_date, date_str, 7)
    p30 = date_range_items(by_date, date_str, 30)
    p90 = date_range_items(by_date, date_str, 90)
    obj['dataByPeriod'] = obj.get('dataByPeriod', {})
    if p1: obj['dataByPeriod']['1일'] = aggregate_short('1일', p1)
    if p3: obj['dataByPeriod']['3일'] = aggregate_short('3일', p3)
    if p7: obj['dataByPeriod']['1주'] = aggregate_short('1주', p7)
    if p30: obj['dataByPeriod']['1개월'] = aggregate_mid('1개월', p30)
    if p90: obj['dataByPeriod']['3개월'] = aggregate_long_3m(p90)
    obj['dataStatus'] = status_from_count(len(p1))
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2))
    return True


def main():
    items = load_insights()
    by_date = group_by_date(items)
    for p in SITE.glob('2026-*/result.json'):
        ds = p.parent.name
        integrate(ds, p, by_date)
    print('integrated refined insights with differentiated period aggregation')

if __name__ == '__main__':
    main()
