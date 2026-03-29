# HANDOFF

## 프로젝트 목적

이 프로젝트의 목적은 단순 뉴스 스크랩이 아니다.

- 한국/미국/일본/유럽 중심의 주요 시장, 거시경제, 정책, 금리, 환율, 유가, 공시, 리서치 메타데이터를 지속적으로 수집한다.
- 수집 데이터를 기반으로 3~6개월 투자 관점의 시장 레짐 판단을 수행한다.
- 최종 산출물은 단순 기사 요약이 아니라 `시장 레짐 판단 -> 핵심 이슈 -> 섹터 영향 -> 포트폴리오 시사점 -> ETF/테마 아이디어`로 이어져야 한다.
- 개별 종목 추천보다 ETF/섹터/테마 단위의 인사이트를 우선한다.
- 매일 생성되는 데이터가 주간/월간/분기 분석으로 누적될 수 있어야 한다.
- 모든 단계는 한국어 리포트 작성에 연결되어야 하며, 메타데이터(출처/날짜/지역/자산군/섹터)를 반드시 남겨야 한다.

## 현재 진행 상태

### 이미 구현된 것

- `collectors/` 기반 1단계 수집 파이프라인이 구현되어 있다.
- 단일 진입점은 [`collectors/runner.py`](/Users/seo/igzun-daily-report/collectors/runner.py) 이다.
- 소스 정의는 [`collectors/registry/sources.yaml`](/Users/seo/igzun-daily-report/collectors/registry/sources.yaml) 기반이다.
- `raw -> normalized -> manifest -> bridge -> refined_insights_inventory.json` 흐름이 작동한다.
- `content_hash` 기반 중복 제거가 구현되어 있다.
- 수집 URL 로깅은 manifest의 `fetched_urls` 에 기록된다.
- `2026-03-27` 기준 1회 배치 결과가 생성되어 있고, 마지막 커밋은 `43b4c84` 이다.
- `scripts/daily_update.sh` 에 수집/분석/사이트 생성/배포 흐름이 연결되어 있다.
- `scripts/macro_analysis.py`, `scripts/etf_recommender.py`, `scripts/build_site_report.py` 작업이 시작되어 있다.
- [`scripts/build_site_report.py`](/Users/seo/igzun-daily-report/scripts/build_site_report.py) 가 `dataByPeriod` 호환 구조를 유지한 채 한국어 인사이트 중심 리포트로 재작성되었다.
- `site/{date}/result.json` 에 1일/1주/1개월/3개월/6개월 구간별 브리핑, 주요 이슈, 포트폴리오, ETF 아이디어가 들어가도록 정리되었다.
- `undefined`/`None`/`null` 문자열이 결과 JSON 에 남지 않도록 fallback 처리했다.
- [`site/template/index.html`](/Users/seo/igzun-daily-report/site/template/index.html) 를 기준 템플릿으로 추가했다.
- 날짜별 [`site/2026-03-27/index.html`](/Users/seo/igzun-daily-report/site/2026-03-27/index.html), [`site/2026-03-29/index.html`](/Users/seo/igzun-daily-report/site/2026-03-29/index.html) 도 템플릿 기준으로 다시 생성했다.
- 화면 문구를 `ETF 아이디어`, `레짐 온도`, `출처·메타데이터` 중심으로 정리했다.
- 포트폴리오 탭에 `포트폴리오 레짐 적합도` 점수 카드가 추가되었다.
- 현재 점수는 수익률 점수가 아니라 `레짐 적합도 + 분산도 + 현금 운용` 합성 점수다.

### 현재 작업 트리 상태

아래 파일은 아직 커밋되지 않은 작업 중 파일이다. 다음 에이전트는 이 상태를 전제로 이어받아야 한다.

- 수정됨: [`scripts/build_site_report.py`](/Users/seo/igzun-daily-report/scripts/build_site_report.py)
- 수정됨: [`scripts/etf_recommender.py`](/Users/seo/igzun-daily-report/scripts/etf_recommender.py)
- 수정됨: [`scripts/load_market_data.py`](/Users/seo/igzun-daily-report/scripts/load_market_data.py)
- 수정됨: [`scripts/macro_analysis.py`](/Users/seo/igzun-daily-report/scripts/macro_analysis.py)
- 신규 미추적: [`data/portfolio_state.json`](/Users/seo/igzun-daily-report/data/portfolio_state.json)

### 현재 확인된 산출물

- [`data/manifests/2026-03-27_run.json`](/Users/seo/igzun-daily-report/data/manifests/2026-03-27_run.json)
- [`data/macro_analysis/2026-03-27.json`](/Users/seo/igzun-daily-report/data/macro_analysis/2026-03-27.json)
- [`data/etf_recommendations/2026-03-27.json`](/Users/seo/igzun-daily-report/data/etf_recommendations/2026-03-27.json)
- [`site/2026-03-27/result.json`](/Users/seo/igzun-daily-report/site/2026-03-27/result.json)
- [`site/2026-03-27/index.html`](/Users/seo/igzun-daily-report/site/2026-03-27/index.html)

## 현재 디렉토리 구조

핵심 디렉토리만 적는다.

```text
/Users/seo/igzun-daily-report
├── collectors/
│   ├── base_fetcher.py
│   ├── bridge.py
│   ├── dedup.py
│   ├── fetcher_registry.py
│   ├── manifest.py
│   ├── normalizer.py
│   ├── registry_loader.py
│   ├── runner.py
│   ├── fetchers/
│   │   ├── ecos_fetcher.py
│   │   ├── edgar_fetcher.py
│   │   ├── fred_fetcher.py
│   │   ├── kr_brokerage.py
│   │   ├── naver_research.py
│   │   ├── opendart_fetcher.py
│   │   └── rss_fetcher.py
│   └── registry/
│       └── sources.yaml
├── data/
│   ├── raw/
│   ├── normalized/
│   ├── manifests/
│   ├── index/
│   ├── macro_analysis/
│   ├── etf_recommendations/
│   ├── refined_insights_inventory.json
│   ├── market_data_latest.json
│   ├── market_quant_snapshot.json
│   └── portfolio_state.json
├── scripts/
│   ├── daily_update.sh
│   ├── process_pdfs.py
│   ├── refine_insights.py
│   ├── integrate_refined_insights.py
│   ├── load_market_data.py
│   ├── apply_market_quant.py
│   ├── macro_analysis.py
│   ├── etf_recommender.py
│   └── build_site_report.py
├── site/
└── templates/
```

## 구현된 것 / 미구현된 것

### 구현된 것

- source registry 구조
- fetcher registration 구조
- `RawDocument` 표준 구조
- dedup index 저장 구조
- manifest 저장 구조
- normalized JSONL 저장 구조
- bridge를 통한 기존 `refined_insights_inventory.json` 호환
- RSS/FRED/ECOS/OpenDART/Naver Research/SEC EDGAR/BIS/Investing.com fetcher
- `daily_update.sh` 에 collectors 단계 추가
- `macro_analysis.py` 와 `etf_recommender.py` 의 초안
- 2026-03-27 기준 batch 실행 및 사이트 산출물 생성

### 아직 미구현 또는 미완료

- 한국어 중심의 인사이트 리포트 HTML 구조 최종 확정
- 브라우저에서 실제 `site/{date}/index.html` 렌더링 검증
- 포트폴리오 시사점 로직 정교화
- 포트폴리오 점수 산식 고도화
- ETF/섹터 아이디어를 지역/레짐/리스크와 더 강하게 연결하는 설명 강화
- 주간/월간/분기 누적 리포트 구조
- `kr_brokerage_kb`, `kr_brokerage_mirae` 스크래퍼 안정화
- 주요 유럽/일본 소스 추가 확장
- source health check와 stale source 알림
- cron 시각 분리 운영 검증

## 다음 작업 우선순위

1. [`scripts/build_site_report.py`](/Users/seo/igzun-daily-report/scripts/build_site_report.py) 완성
- 한국어 중심
- 단순 기사 나열 금지
- 1일/1주/1개월/3개월/6개월 구분
- 레짐/핵심 이슈/섹터 영향/포트폴리오 시사점/ETF 아이디어 포함
- `undefined` 출력 금지

2. 사이트 렌더링 검증
- `site/{date}/result.json` 과 `site/{date}/index.html` 구조 일치 확인
- 기존 HTML과 호환되는지 확인
- `site/template/index.html` 을 기준 템플릿으로 유지
- 필요 시 기존 HTML을 업데이트하되 데이터 흐름은 유지

3. 포트폴리오 연결 강화
- [`data/portfolio_state.json`](/Users/seo/igzun-daily-report/data/portfolio_state.json) 활용
- 현재 현금 배분(ISA / 토스증권 / 연금저축)을 반영해 계좌별 제안 연결

4. 수집 소스 품질 개선
- KB/Mirae scraper 수정
- JP/EU 리서치/매크로 소스 추가
- 저작권 이슈가 있는 PDF는 직접 다운로드보다 메타데이터/링크 우선

5. 주간/월간 확장 설계
- 일간 산출물 누적으로 주간/월간/분기 분석이 가능하도록 집계 레이어 추가

## 절대 바꾸면 안 되는 규칙

아래 규칙은 반드시 지켜야 한다.

1. 기존 구조를 임의로 바꾸지 말 것
- `collectors/`, `data/`, `scripts/` 구조 유지

2. `sources.yaml` 기반 구조를 깨지 말 것
- 모든 수집 대상은 [`collectors/registry/sources.yaml`](/Users/seo/igzun-daily-report/collectors/registry/sources.yaml) 에 등록

3. `runner.py` 를 단일 진입점으로 유지할 것
- 별도 수집 진입 스크립트 추가 금지

4. `manifest / dedup / normalized` 저장 구조를 변경하지 말 것
- 하위 호환 깨지면 안 됨

5. `bridge.py` 출력 포맷을 깨지 말 것
- [`scripts/refine_insights.py`](/Users/seo/igzun-daily-report/scripts/refine_insights.py) 와 호환 유지 필요

6. 기존 파일 수정은 최소화할 것
- 새 파일 추가는 가능
- 기존 인터페이스는 유지

7. 불확실한 경우 구조를 새로 만들지 말 것
- `TODO` 로 명시하고 남길 것

8. 문서 갱신 필수
- 작업 후 반드시 이 파일과 [`TASKS.md`](/Users/seo/igzun-daily-report/TASKS.md) 를 업데이트

## 빠른 실행 흐름

수집만 실행:

```bash
cd /Users/seo/igzun-daily-report
source .venv/bin/activate
python -m collectors.runner --date 2026-03-27 --base-dir /Users/seo/igzun-daily-report
python -m collectors.bridge --date 2026-03-27 --base-dir /Users/seo/igzun-daily-report
```

전체 일배치 실행:

```bash
cd /Users/seo/igzun-daily-report
bash scripts/daily_update.sh
```
