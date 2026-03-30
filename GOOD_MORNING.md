# GOOD_MORNING

## 밤새 완료한 작업
- LLM 요약 파이프라인을 초보 투자자 친화형 스토리텔링 구조로 개편했습니다.
  - 수정 파일: [/Users/seo/igzun-daily-report/scripts/llm_insights.py](/Users/seo/igzun-daily-report/scripts/llm_insights.py)
  - 핵심 변화:
    - 단순 사실 나열 대신 `현상 -> 이유 -> 포트폴리오 영향 -> 행동` 구조 강제
    - 어려운 용어는 괄호 안에 쉬운 뜻을 덧붙이도록 프롬프트 보강
    - `오늘의 핵심 인사이트(So What?)` 3줄 출력 추가
    - SPY / QQQ / GLD / TLT 중심 설명 강화
- 시장 데이터 수집을 보강했습니다.
  - 수정 파일: [/Users/seo/igzun-daily-report/scripts/load_market_data.py](/Users/seo/igzun-daily-report/scripts/load_market_data.py), [/Users/seo/igzun-daily-report/scripts/macro_analysis.py](/Users/seo/igzun-daily-report/scripts/macro_analysis.py)
  - 핵심 변화:
    - SPY / QQQ / GLD / TLT 시세 및 변동폭 수집 추가
    - 매크로 분석 결과에 ETF 가격/기간별 수익률 반영
- HTML 리포트를 대시보드형으로 개선했습니다.
  - 수정 파일: [/Users/seo/igzun-daily-report/site/template/index.html](/Users/seo/igzun-daily-report/site/template/index.html), [/Users/seo/igzun-daily-report/scripts/build_site_report.py](/Users/seo/igzun-daily-report/scripts/build_site_report.py)
  - 핵심 변화:
    - 최상단 `Executive Summary (오늘의 3줄 요약)` 카드 추가
    - SPY / QQQ / GLD / TLT용 `Market Dashboard` 카드 추가
    - `현상 -> 이유 -> 내 포트폴리오 영향` 블록 추가
    - 모바일 반응형 스타일 보강
- 수동 심화분석 브리프를 안정화했습니다.
  - 수정 파일: [/Users/seo/igzun-daily-report/scripts/build_manual_summary_brief.py](/Users/seo/igzun-daily-report/scripts/build_manual_summary_brief.py), [/Users/seo/igzun-daily-report/scripts/daily_update.sh](/Users/seo/igzun-daily-report/scripts/daily_update.sh)
  - 핵심 변화:
    - `build_site_report.py` 이후에 브리프를 생성하도록 순서 수정
    - `result.json`이 아직 없더라도 `macro_analysis`, `signals`, `portfolio_state`에서 스냅샷을 채우도록 fallback 보강
- 2026-03-31 데이터 생성과 검증을 완료했습니다.
  - 생성 파일 예시:
    - [/Users/seo/igzun-daily-report/site/2026-03-31/result.json](/Users/seo/igzun-daily-report/site/2026-03-31/result.json)
    - [/Users/seo/igzun-daily-report/site/2026-03-31/index.html](/Users/seo/igzun-daily-report/site/2026-03-31/index.html)
    - [/Users/seo/igzun-daily-report/data/llm_insights/2026-03-31.json](/Users/seo/igzun-daily-report/data/llm_insights/2026-03-31.json)
    - [/Users/seo/igzun-daily-report/data/manual_summary/2026-03-31.md](/Users/seo/igzun-daily-report/data/manual_summary/2026-03-31.md)
    - [/Users/seo/igzun-daily-report/data/etf_recommendations/2026-03-31.json](/Users/seo/igzun-daily-report/data/etf_recommendations/2026-03-31.json)

## 성공 / 실패 / 보류 정리
### 성공
- 2026-03-31 수집 -> 분석 -> 리포트 생성 전체 흐름 실행 성공
- SPY / QQQ / GLD / TLT 데이터가 리포트와 대시보드에 반영됨
- 수동 브리프의 `데이터 없음` 문제 해결
- 추천 ETF 엔진 재실행 후 `ETF 데이터 없음` 문구 제거

### 보류 또는 비차단 이슈
- LLM API 키가 없어 현재 `llm_insights.py`는 규칙 기반 fallback으로 동작합니다.
- 네이버/KB/신한 수집 시 `InsecureRequestWarning` 경고가 발생하지만, 수집 자체는 계속 진행됩니다.
- 일부 증권사 원문 PDF는 로그인 또는 권한 제약이 있어 자동 다운로드가 제한됩니다.

## 아침에 가장 먼저 확인할 것
1. 오늘 생성된 리포트 화면 확인
```bash
open /Users/seo/igzun-daily-report/site/2026-03-31/index.html
```

2. 수동 심화분석 브리프 확인
```bash
open /Users/seo/igzun-daily-report/data/manual_summary/2026-03-31.md
```

3. 워크트리 상태 확인
```bash
cd /Users/seo/igzun-daily-report && git status --short
```

4. 필요하면 오늘 브리프만 다시 생성
```bash
cd /Users/seo/igzun-daily-report && .venv/bin/python scripts/build_manual_summary_brief.py --date 2026-03-31 --base-dir /Users/seo/igzun-daily-report
```

## 참고
- 10:00 KST 자동 배치 구조는 유지되어 있습니다.
- 이번 커밋에서는 사용자가 이미 가지고 있던 로컬 변경인 `data/refined_insights_inventory.json` 과 `docs/` 는 의도적으로 제외했습니다.
