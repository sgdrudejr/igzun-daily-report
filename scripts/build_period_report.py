#!/usr/bin/env python3
import json, re
from pathlib import Path
from datetime import datetime

ROOT = Path('/Users/seo/.openclaw/workspace/igzun-daily-report')
SRC_DAILY = Path('/Users/seo/.openclaw/workspace/1_Project/DailyReport/output/2026-03-19_reportData.json')
SRC_MERGED = Path('/Users/seo/.openclaw/workspace/2_Project/Reporting/process/merged/2026-03-19_merged_news.json')
SRC_REPORTS = Path('/Users/seo/.openclaw/workspace/2_Project/Reporting/input/manifest/fetched_reports_2026-03-19.jsonl')
OUT_JSON = ROOT / 'site/2026-03-19/result.json'
OUT_REPORT = ROOT / 'data/coverage_report_2026-03-19.md'
TARGETS = [ROOT / 'site/2026-03-19/index.html', ROOT / 'templates/report.html']


def load_json(path):
    return json.loads(path.read_text())


def load_jsonl_titles(path):
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    return rows


def top_tags(title):
    toks = re.findall(r"[A-Za-z가-힣0-9]+", title)
    stop = {'the','and','for','with','from','this','that','are','was','will','into','after','amid','says','say','here'}
    out = []
    for t in toks:
        if len(t) < 2 or t.lower() in stop:
            continue
        out.append(t)
        if len(out) == 3:
            break
    return out or ['시장', '리포트']


def build_period_data():
    daily = load_json(SRC_DAILY)
    merged = load_json(SRC_MERGED) if SRC_MERGED.exists() else {'stories': []}
    reports = load_jsonl_titles(SRC_REPORTS)

    one_day_news = []
    for item in daily.get('newsList', [])[:6]:
        one_day_news.append({
            'title': item.get('title', ''),
            'tags': item.get('tags', [])[:4],
            'summary': item.get('summary') or '원문 소스에서 요약 추출이 아직 비어 있습니다.',
            'impacts': item.get('impacts', [])[:3],
        })

    macro_news = []
    for story in merged.get('stories', [])[:4]:
        macro_news.append({
            'title': story.get('headline', ''),
            'tags': story.get('keywords', [])[:4] or top_tags(story.get('headline', '')),
            'summary': story.get('summary') or '병합 소스는 확보됐지만 요약 본문 추출은 아직 미완성입니다.',
            'impacts': [
                {
                    'sector': '거시 / 금리 / 정책',
                    'isPositive': False if 'fomc' in story.get('headline', '').lower() or 'infl' in story.get('headline', '').lower() else True,
                    'desc': f"원문 {story.get('source_count', 0)}건이 병합된 이슈입니다."
                }
            ]
        })

    report_titles = [r.get('title', '') for r in reports[:6]]

    result = {
        'date': '2026년 3월 19일 기준 업데이트',
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'dataByPeriod': {
            '1일': {
                'briefing': {
                    'sentiment': {
                        'score': 43,
                        'status': '중립',
                        'desc': '3월 19일 수집 데이터 기준으로 금리·유가 변수는 부담이지만 현금 대기 전략은 여전히 유효합니다.'
                    },
                    'forecast': {
                        'title': '당일 뉴스 + 지수 기반 단기 전망',
                        'text': 'FOMC 관련 불확실성과 유가 상승 이슈가 단기 변동성을 키우고 있습니다. 다만 현금 비중이 높다면 하락 구간은 분할 진입 관점으로 해석할 수 있습니다.'
                    },
                    'insights': daily.get('briefing', {}).get('insights', [])[:5],
                    'indices': daily.get('briefing', {}).get('indices', [])[:6]
                },
                'newsList': one_day_news,
                'portfolio': {
                    'accountAlert': daily.get('portfolio', {}).get('accountAlert', '당일 계좌 요약 데이터가 부족합니다.'),
                    'accountDetail': daily.get('portfolio', {}).get('accountDetail', ''),
                    'weeklyReview': daily.get('portfolio', {}).get('weeklyReview', {'returnRate': '데이터 없음', 'desc': '성과 데이터 없음'}),
                    'holdings': [
                        {
                            'name': 'SOXX (반도체 ETF)',
                            'ticker': 'SOXX',
                            'returnRate': '데이터 미연결',
                            'score': -10,
                            'indicators': ['나스닥 약세', '반도체 변동성 확대', 'FOMC 영향'],
                            'reason': '기존 일간 리포트의 반도체 비중 경고를 반영한 임시 시그널입니다. 실제 계좌 보유종목 파일이 연결되면 교체됩니다.'
                        },
                        {
                            'name': 'TLT (장기국채 ETF)',
                            'ticker': 'TLT',
                            'returnRate': '데이터 미연결',
                            'score': 20,
                            'indicators': ['금리 고점 논리', '방어 자산', '듀레이션 민감'],
                            'reason': '일간 리포트 제안 자산배분에 포함된 방어 자산으로 반영했습니다.'
                        }
                    ],
                    'planDesc': daily.get('portfolio', {}).get('planDesc', ''),
                    'allocations': daily.get('portfolio', {}).get('allocations', [])[:4]
                },
                'recommendations': {
                    'ideas': [
                        {
                            'logo': x.get('logo', '📌'),
                            'name': x.get('name', ''),
                            'ticker': x.get('ticker', ''),
                            'action': x.get('action', ''),
                            'linkedIssue': x.get('linkedIssue', ''),
                            'reason': x.get('reason', '')
                        } for x in daily.get('recommendations', [])[:3]
                    ],
                    'etfRanking': [
                        {'rank': 1, 'name': 'Energy Select Sector SPDR', 'ticker': 'XLE', 'score': 85},
                        {'rank': 2, 'name': 'SPDR Gold Trust', 'ticker': 'GLD', 'score': 72},
                        {'rank': 3, 'name': 'iShares 20+ Year Treasury Bond', 'ticker': 'TLT', 'score': 68}
                    ]
                },
                'raw_sources': {
                    'news': ['1_Project/DailyReport/output/2026-03-19_reportData.json', '2_Project/Reporting/process/merged/2026-03-19_merged_news.json'],
                    'market': ['1_Project/DailyReport/output/2026-03-19_reportData.json'],
                    'reports': ['2_Project/Reporting/input/manifest/fetched_reports_2026-03-19.jsonl'],
                    'portfolio': []
                }
            },
            '1개월': {
                'briefing': {
                    'sentiment': {
                        'score': 61,
                        'status': '완만한 위험선호',
                        'desc': '3월 19일 확보된 증권사/매크로 원문은 인플레·유가 부담 속에서도 구조적 테마를 유지하는 쪽에 가깝습니다.'
                    },
                    'forecast': {
                        'title': '월간 리포트/매크로 원문 누적 기반 전망',
                        'text': 'KB 데일리, 미래에셋 FOMC 코멘트, JPM/노무라 계열 매크로 원문을 보면 금리 민감 구간은 부담이지만 전력망·인프라·에너지·방어 자산의 상대 매력이 유지됩니다.'
                    },
                    'insights': [
                        {'category': '매크로', 'text': '3월 FOMC와 인플레 리스크가 정책의 초점을 다시 물가 안정으로 이동시키고 있습니다.'},
                        {'category': '테마', 'text': '전력망·인프라·에너지 관련 장기 테마는 원문 리포트들에서 반복적으로 확인됩니다.'},
                        {'category': '원문수집', 'text': f'3월 19일 기준 리포트 fetch {len(reports)}건, 병합 뉴스 {merged.get("merged_stories", 0)}건을 확보했습니다.'}
                    ],
                    'indices': [
                        {'name': 'S&P 500 (일간 기준 대체)', 'price': '6,646.13', 'change': '▼ 0.75%', 'isUp': False},
                        {'name': 'WTI 원유', 'price': '96.16', 'change': '▲ 0.99%', 'isUp': True},
                        {'name': '금(Gold)', 'price': '4,864.04', 'change': '▼ 2.78%', 'isUp': False}
                    ]
                },
                'newsList': macro_news,
                'portfolio': {
                    'accountAlert': '월간 관점에서는 성장주 편중보다 인프라·방어자산 병행이 더 적절해 보입니다.',
                    'accountDetail': '실제 계좌 원본이 연결되지 않아 월간 포트폴리오 평가는 모델 포트폴리오 기준으로 작성했습니다.',
                    'weeklyReview': {
                        'returnRate': '실계좌 월간 수익률 미연결',
                        'desc': '현재는 시장/리포트 기반 전략 코멘트만 가능하며 실제 월간 성과 계산에는 계좌 원본이 더 필요합니다.'
                    },
                    'holdings': [
                        {
                            'name': 'PAVE',
                            'ticker': 'PAVE',
                            'returnRate': '모델 추적',
                            'score': 55,
                            'indicators': ['인프라 슈퍼사이클', '전력망 투자', '구조적 CAPEX'],
                            'reason': '여러 원문 리포트에서 장기 투자 테마로 반복 확인되어 월간 아이디어로 적합합니다.'
                        },
                        {
                            'name': 'TSLA',
                            'ticker': 'TSLA',
                            'returnRate': '원본 계좌 미연결',
                            'score': -35,
                            'indicators': ['금리 부담', '성장주 밸류에이션', '수요 둔화 우려'],
                            'reason': '원문 기반으로는 성장주 중에서도 금리 부담과 실적 민감도가 높은 편으로 평가됩니다.'
                        }
                    ],
                    'planDesc': '월간 기준으로는 코어지수 + 인프라/에너지 + 현금 완충 구조가 적절합니다.',
                    'allocations': [
                        {'name': 'S&P 500', 'percent': 45, 'color': '#191F28', 'desc': '코어 베타'},
                        {'name': '인프라/에너지', 'percent': 35, 'color': '#F04452', 'desc': '구조적 테마 + 지정학 수혜'},
                        {'name': '현금/채권', 'percent': 20, 'color': '#E5E8EB', 'desc': '변동성 대응'}
                    ]
                },
                'recommendations': {
                    'ideas': [
                        {
                            'logo': '🔌',
                            'name': 'Global X U.S. Infrastructure',
                            'ticker': 'PAVE',
                            'action': '장기 관찰 및 분할매수',
                            'linkedIssue': '전력망/인프라 투자 확대',
                            'reason': '3월 19일 수집된 국내외 원문에서 구조적 투자 테마로 가장 일관되게 확인됐습니다.'
                        }
                    ],
                    'etfRanking': [
                        {'rank': 1, 'name': 'Global X U.S. Infrastructure', 'ticker': 'PAVE', 'score': 91},
                        {'rank': 2, 'name': 'Energy Select Sector SPDR', 'ticker': 'XLE', 'score': 83},
                        {'rank': 3, 'name': 'iShares 20+ Year Treasury Bond', 'ticker': 'TLT', 'score': 69}
                    ]
                },
                'raw_sources': {
                    'news': ['2_Project/Reporting/process/merged/2026-03-19_merged_news.json'],
                    'market': ['1_Project/DailyReport/output/2026-03-19_reportData.json'],
                    'reports': report_titles,
                    'portfolio': []
                }
            }
        }
    }
    return result


def replace_report_data(html_text, report_obj):
    payload = 'const reportData = ' + json.dumps(report_obj, ensure_ascii=False, indent=2) + ';'
    new_text, count = re.subn(r'const reportData = \{.*?\n\};', payload, html_text, count=1, flags=re.S)
    return new_text, count


def main():
    result = build_period_data()
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2))

    missing = [
        '- 실제 계좌 원본(보유종목별 실현/평가손익, 비중)이 없어 portfolio.holdings/weeklyReview 일부를 모델 기반으로 채움',
        '- 뉴스/리포트 요약 본문 추출이 비어 있는 원문이 많아 newsList.summary 일부는 placeholder로 채움',
        '- 1주, 3개월, 1년 기간 데이터는 아직 미생성',
        '- 개별 종목 지표(RSI, MACD 등)의 실제 계산 원본이 없어 indicators 일부는 규칙 기반 문구로 대체',
        '- ETF ranking 점수는 정식 팩터 모델이 아니라 현재 원문 테마 강도 기반 임시 점수임'
    ]
    OUT_REPORT.write_text('# 2026-03-19 데이터 커버리지 보고\n\n' + '\n'.join(missing) + '\n')

    for t in TARGETS:
        text = t.read_text()
        new_text, count = replace_report_data(text, result)
        if count:
            t.write_text(new_text)
    print('wrote', OUT_JSON)
    print('wrote', OUT_REPORT)

if __name__ == '__main__':
    main()
