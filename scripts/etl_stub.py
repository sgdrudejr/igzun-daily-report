#!/usr/bin/env python3
"""
ETL stub: normalize raw inputs into site/YYYY-MM-DD/result.json following data/schema.json.
- Reads raw files under data/raw/
  - data/raw/news/*.json or .csv
  - data/raw/market/*.csv or .json
  - data/raw/reports/*.json
- Produces site/<YYYY-MM-DD>/result.json

This is a starting point: adapt parsers to your raw formats.
"""
import os, sys, json, datetime, glob
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
RAW = DATA / 'raw'
SITE = ROOT / 'site'

def load_latest_news():
    news = []
    p = RAW / 'news'
    if not p.exists():
        return news
    for f in sorted(p.glob('*.json')):
        try:
            j = json.loads(f.read_text())
            # Expect j to be {title, summary, tags, impacts?}
            news.append(j)
        except Exception as e:
            print('skip', f, e)
    return news

def load_market_snapshot():
    # try market/json/latest.json
    p = RAW / 'market'
    if (p / 'latest.json').exists():
        return json.loads((p / 'latest.json').read_text())
    return {}


def build_result(date_str):
    # date_str YYYY-MM-DD
    news = load_latest_news()
    market = load_market_snapshot()
    # very simple mapping
    result = {
        'date': date_str,
        'title': '오픈 클로 AI 리포트',
        'generated_at': datetime.datetime.utcnow().isoformat() + 'Z',
        'briefing': {
            'insights': [ {'category':'요약','text':'자동생성 요약 없음 - ETL을 구성하세요.'} ],
            'indices': market.get('indices', [])
        },
        'newsList': news,
        'portfolio': {
            'accountAlert':'', 'accountDetail':'', 'weeklyReview':{}, 'planDesc':'', 'allocations':[]
        },
        'recommendations': [],
        'raw_sources': {
            'news_raw': 'data/raw/news/',
            'market_raw': 'data/raw/market/'
        }
    }
    return result

if __name__ == '__main__':
    date = datetime.date.today().isoformat()
    if len(sys.argv) > 1:
        date = sys.argv[1]
    outdir = SITE / date
    outdir.mkdir(parents=True, exist_ok=True)
    result = build_result(date)
    outpath = outdir / 'result.json'
    outpath.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print('Wrote', outpath)
