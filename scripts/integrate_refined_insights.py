#!/usr/bin/env python3
import json, re
from pathlib import Path

ROOT = Path('/Users/seo/.openclaw/workspace/igzun-daily-report')
INS = ROOT / 'data/refined_insights_inventory.json'
SITE = ROOT / 'site'


def load_insights():
    return json.loads(INS.read_text()) if INS.exists() else []


def group_by_date(items):
    out = {}
    for x in items:
        out.setdefault(x.get('date',''), []).append(x)
    return out


def integrate(date_str, path, items):
    obj = json.loads(path.read_text())
    if 'dataByPeriod' not in obj:
        return False
    period = obj['dataByPeriod'].setdefault('1일', {})
    brief = period.setdefault('briefing', {})
    if items:
        first = items[0]
        sent = first.get('sentiment', {})
        score01 = sent.get('score', 0)
        ui_score = int(round((score01 + 1.0) * 50))
        brief['sentiment'] = {
            'score': ui_score,
            'status': '매파/부정' if score01 < -0.2 else ('비둘기/긍정' if score01 > 0.2 else '중립'),
            'desc': sent.get('rationale', '감성 근거 없음')
        }
        takes = first.get('key_takeaways', [])[:3]
        brief['forecast'] = {
            'title': first.get('core_subject', '핵심 전망'),
            'text': '<br>'.join([f'{i+1}. {t}' for i,t in enumerate(takes)]),
            'sources': [{
                'label': x.get('source_file',''),
                'source': x.get('source_meta',{}).get('broker_or_source',''),
                'title': x.get('source_file',''),
                'published_at': x.get('date','')
            } for x in items[:5]]
        }
        period['newsList'] = []
        for x in items[:8]:
            period['newsList'].append({
                'title': x.get('core_subject','주요 이슈'),
                'tags': ['정제인사이트', '원문분석', '자동추출'],
                'summary': ' / '.join(x.get('key_takeaways', [])[:2]),
                'impacts': [
                    {'sector': 'USD', 'isPositive': x.get('impact_assets',{}).get('USD','') in ['강세','긍정'], 'desc': x.get('impact_assets',{}).get('USD','중립')},
                    {'sector': 'Bonds', 'isPositive': '상승' in x.get('impact_assets',{}).get('Bonds',''), 'desc': x.get('impact_assets',{}).get('Bonds','중립')},
                    {'sector': 'Stocks', 'isPositive': x.get('impact_assets',{}).get('Stocks','') in ['강세','긍정','완화적'], 'desc': x.get('impact_assets',{}).get('Stocks','중립')}
                ],
                'sources': [{
                    'label': x.get('source_file',''),
                    'source': x.get('source_meta',{}).get('broker_or_source',''),
                    'title': x.get('source_file',''),
                    'published_at': x.get('date','')
                }]
            })
        obj['dataStatus'] = 'full'
    else:
        obj['dataStatus'] = obj.get('dataStatus', 'sparse')
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2))
    return True


def main():
    items = load_insights()
    by_date = group_by_date(items)
    for p in SITE.glob('2026-*/result.json'):
        ds = p.parent.name
        integrate(ds, p, by_date.get(ds, []))
    print('integrated refined insights')

if __name__ == '__main__':
    main()
