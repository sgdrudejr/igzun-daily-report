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
- `2026-03-30` 기준 일배치가 다시 실행되었고, 수집 -> 분석 -> 사이트 생성 -> horizon 집계까지 재생성되었다.
- `2026-01-01 ~ 2026-03-30` 구간에 대해 historical-safe source 기반 백필이 추가되었다.
- 백필 실행기는 [`scripts/backfill_history.py`](/Users/seo/igzun-daily-report/scripts/backfill_history.py) 이며, 현재 기준 Q1 백필 요약은 [`data/backfills/2026-01-01_to_2026-03-30.json`](/Users/seo/igzun-daily-report/data/backfills/2026-01-01_to_2026-03-30.json) 에 기록된다.
- 저장공간 정리기는 [`scripts/storage_retention.py`](/Users/seo/igzun-daily-report/scripts/storage_retention.py) 이며, 상태는 [`data/storage_retention/status.json`](/Users/seo/igzun-daily-report/data/storage_retention/status.json) 에 기록된다.
- `scripts/daily_update.sh` 에 수집/분석/사이트 생성/배포 흐름이 연결되어 있다.
- `scripts/daily_update.sh` 는 이제 `TZ=Asia/Seoul` 기준 날짜를 사용한다.
- `11:00 KST` 자동 실행용 launch agent 가 설치되어 있다.
- launch agent 템플릿은 [`cron/com.seo.igzun-daily-report.daily.plist`](/Users/seo/igzun-daily-report/cron/com.seo.igzun-daily-report.daily.plist), 설치 스크립트는 [`scripts/install_launch_agent.sh`](/Users/seo/igzun-daily-report/scripts/install_launch_agent.sh) 이다.
- `scripts/macro_analysis.py`, `scripts/etf_recommender.py`, `scripts/build_site_report.py` 작업이 시작되어 있다.
- [`scripts/build_site_report.py`](/Users/seo/igzun-daily-report/scripts/build_site_report.py) 가 `dataByPeriod` 호환 구조를 유지한 채 한국어 인사이트 중심 리포트로 재작성되었다.
- `site/{date}/result.json` 에 1일/1주/1개월/3개월/6개월 구간별 브리핑, 주요 이슈, 포트폴리오, ETF 아이디어가 들어가도록 정리되었다.
- `undefined`/`None`/`null` 문자열이 결과 JSON 에 남지 않도록 fallback 처리했다.
- [`site/template/index.html`](/Users/seo/igzun-daily-report/site/template/index.html) 를 기준 템플릿으로 추가했다.
- 날짜별 [`site/2026-03-27/index.html`](/Users/seo/igzun-daily-report/site/2026-03-27/index.html), [`site/2026-03-29/index.html`](/Users/seo/igzun-daily-report/site/2026-03-29/index.html), [`site/2026-03-30/index.html`](/Users/seo/igzun-daily-report/site/2026-03-30/index.html) 도 템플릿 기준으로 다시 생성했다.
- 화면 문구를 `ETF 아이디어`, `레짐 온도`, `출처·메타데이터` 중심으로 정리했다.
- 포트폴리오 탭에 `포트폴리오 레짐 적합도` 점수 카드가 추가되었다.
- 현재 점수는 수익률 점수가 아니라 `레짐 적합도 + 분산도 + 현금 운용` 합성 점수다.
- [`scripts/build_horizon_views.py`](/Users/seo/igzun-daily-report/scripts/build_horizon_views.py) 가 추가되었다.
- 이 스크립트는 누적된 일간 `site/*/result.json` 을 읽어 `site/horizon_index.json` 과 `site/horizons/` 아래 기간별 집계 파일을 생성한다.
- UI는 더 이상 좌하단 플로팅 달력이 아니라 `기간 유형 탭 -> 기간 선택 탭 -> 섹션 탭` 구조다.
- 상단 UI는 `기간 유형 칩 + 기간 선택 드롭다운` 1행 압축 구조로 다시 정리되었다.
- 새로고침 시 기본 진입값은 항상 `1일 / 최신 날짜` 이다.
- 각 섹션 탭은 개별 스크롤 pane 으로 동작하도록 바뀌었다.
- 섹션 순서는 `포트폴리오 -> 실행 가이드 -> 시장 브리핑 -> 핵심 이슈 -> ETF 아이디어` 다.
- 상단 헤더에 `누적 업데이트 수 / 누적 문서 수 / 평균 점수 / 주요 출처` 요약 pill 이 추가되었다.
- 현재 생성된 누적 버킷 수는 일간 25개, 주간 7개, 월간 2개, 분기 1개, 반기 1개다.
- Q1 백필 이후 현재 생성된 누적 버킷 수는 일간 66개, 주간 14개, 월간 3개, 분기 1개, 반기 1개다.
- `site/` 아래 HTML/JSON 검색 기준 `undefined`/`None` 문자열이 남지 않도록 다시 검증했다.
- `briefing.strategy`, `rebalancing`, `briefing.scoreChips`, `briefing.metricChips`, `portfolio.scoreChips` 블록이 추가되었다.
- 1일/1주/1개월/3개월/6개월은 각 기간의 질문과 지표가 다르게 보이도록 다시 정리되었다.
- `load_market_data.py`, `macro_analysis.py`, `etf_recommender.py` 는 특정 날짜 기준 as-of 계산이 가능하도록 보정되었다.
- 백필은 현재 `fred_api`, `opendart` 중심으로 수행된다. RSS/스크래퍼/ECOS 는 snapshot 성격이 강해 Q1 백필 기본 대상에서 제외된다.
- 저장공간 정리 1차 적용 결과: raw 32일치, normalized 10일치를 summary+archive 로 넘겼다.

### 현재 작업 트리 상태

다음 에이전트는 아래 상태를 전제로 이어받아야 한다.

- 커밋 전 변경 파일이 남아 있을 수 있으므로 반드시 `git status --short` 를 먼저 확인한다.
- [`scripts/build_horizon_views.py`](/Users/seo/igzun-daily-report/scripts/build_horizon_views.py) 는 새로 추가된 누적 집계 레이어다.
- [`site/template/index.html`](/Users/seo/igzun-daily-report/site/template/index.html) 와 날짜별 `site/*/index.html` 은 같은 탭형 UI를 공유한다.
- [`data/portfolio_state.json`](/Users/seo/igzun-daily-report/data/portfolio_state.json) 는 현재 전액 현금 상태를 반영한다.
- 브라우저 실기기 검증은 아직 남아 있다. 특히 Galaxy S25 Ultra 기준 줄바꿈, 칩 높이, 상단 드롭다운 폭을 확인해야 한다.
- `data/market_data_history/` 와 `data/etf_price_history/` 는 로컬 캐시이며 `.gitignore` 대상이다.
- `data/archives/` 는 로컬 압축본 저장소이며 Git 에 올리지 않는다.

### 현재 확인된 산출물

- [`data/manifests/2026-03-27_run.json`](/Users/seo/igzun-daily-report/data/manifests/2026-03-27_run.json)
- [`data/manifests/2026-03-30_run.json`](/Users/seo/igzun-daily-report/data/manifests/2026-03-30_run.json)
- [`data/macro_analysis/2026-03-27.json`](/Users/seo/igzun-daily-report/data/macro_analysis/2026-03-27.json)
- [`data/macro_analysis/2026-03-30.json`](/Users/seo/igzun-daily-report/data/macro_analysis/2026-03-30.json)
- [`data/etf_recommendations/2026-03-27.json`](/Users/seo/igzun-daily-report/data/etf_recommendations/2026-03-27.json)
- [`data/etf_recommendations/2026-03-30.json`](/Users/seo/igzun-daily-report/data/etf_recommendations/2026-03-30.json)
- [`site/2026-03-27/result.json`](/Users/seo/igzun-daily-report/site/2026-03-27/result.json)
- [`site/2026-03-27/index.html`](/Users/seo/igzun-daily-report/site/2026-03-27/index.html)
- [`site/2026-03-30/result.json`](/Users/seo/igzun-daily-report/site/2026-03-30/result.json)
- [`site/2026-03-30/index.html`](/Users/seo/igzun-daily-report/site/2026-03-30/index.html)
- [`site/2026-01-02/result.json`](/Users/seo/igzun-daily-report/site/2026-01-02/result.json)
- [`site/2026-02-12/result.json`](/Users/seo/igzun-daily-report/site/2026-02-12/result.json)
- [`site/horizon_index.json`](/Users/seo/igzun-daily-report/site/horizon_index.json)
- [`site/horizons/weekly/2026-03-w5.json`](/Users/seo/igzun-daily-report/site/horizons/weekly/2026-03-w5.json)
- [`data/backfills/2026-01-01_to_2026-03-30.json`](/Users/seo/igzun-daily-report/data/backfills/2026-01-01_to_2026-03-30.json)
- [`data/storage_retention/status.json`](/Users/seo/igzun-daily-report/data/storage_retention/status.json)

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
│   ├── backfills/
│   ├── archive_summaries/
│   ├── storage_retention/
│   ├── refined_insights_inventory.json
│   ├── market_data_latest.json
│   ├── market_quant_snapshot.json
│   └── portfolio_state.json
├── cron/
│   ├── jobs.cron
│   └── com.seo.igzun-daily-report.daily.plist
├── scripts/
│   ├── daily_update.sh
│   ├── install_cron.sh
│   ├── install_launch_agent.sh
│   ├── process_pdfs.py
│   ├── refine_insights.py
│   ├── integrate_refined_insights.py
│   ├── load_market_data.py
│   ├── apply_market_quant.py
│   ├── macro_analysis.py
│   ├── etf_recommender.py
│   ├── backfill_history.py
│   ├── storage_retention.py
│   ├── build_site_report.py
│   └── build_horizon_views.py
├── site/
│   ├── template/
│   └── horizons/
└── docs/
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
- `macro_analysis.py`, `etf_recommender.py`, `build_site_report.py`, `build_horizon_views.py` 가 연결되었다.
- `2026-03-30` 기준 batch 실행 및 사이트 산출물 생성
- 일간 결과를 다시 주간/월간/분기/반기 버킷으로 집계하는 레이어가 들어갔다.
- 1일/1주/1개월/3개월/6개월마다 누적 문서 수, 평균 점수, 주요 출처를 따로 보여준다.
- 2026년 1월~3월 weekday 기준 63개 날짜에 대해 Q1 백필을 수행했고, 사이트에는 총 66개 일간 버킷이 존재한다.
- `site/horizon_index.json` 에 storage retention 상태와 backfill run 메타가 추가되었다.
- `daily_update.sh` 에 retention 훅이 추가되어 오래된 raw/normalized/manifests 를 요약+압축 대상으로 보낼 수 있다.
- `daily_update.sh` 가 cron/launchd 환경에서도 깨지지 않도록 KST 날짜와 절대 python 경로를 사용하도록 보정했다.

### 아직 미구현 또는 미완료

- 브라우저에서 실제 `site/{date}/index.html` 렌더링 검증
- 탭 간 개별 스크롤 동작 검증
- Galaxy S25 Ultra 기준 줄바꿈 / 상단 드롭다운 UI 검증
- 포트폴리오 시사점 로직 정교화
- 포트폴리오 점수 산식 고도화
- ETF/섹터 아이디어를 지역/레짐/리스크와 더 강하게 연결하는 설명 강화
- `kr_brokerage_kb`, `kr_brokerage_mirae` 스크래퍼 안정화
- 주요 유럽/일본 소스 추가 확장
- source health check와 stale source 알림
- cron 시각 분리 운영 검증

## 다음 작업 우선순위

1. 브라우저 렌더링 검증
- `site/{date}/index.html` 에서 기간 유형 탭 -> 기간 선택 탭 -> 섹션 탭 흐름 확인
- 모바일/데스크톱에서 chip overflow 및 탭 전환 UX 확인
- `undefined`/`None` 가 실제 화면에도 보이지 않는지 확인
- 각 섹션 pane 스크롤이 독립적으로 유지되는지 확인
- 새로고침 시 항상 `1일 / 최신 날짜` 로 초기화되는지 확인

2. 인사이트 품질 강화
- 1일은 뉴스/변동성 중심
- 1주는 흐름과 수급 중심
- 1개월은 월간 레짐·섹터 축 중심
- 3개월/6개월은 자산배분·ETF 아이디어 중심으로 차별화 강화

3. 포트폴리오 연결 강화
- [`data/portfolio_state.json`](/Users/seo/igzun-daily-report/data/portfolio_state.json) 활용
- 현재 현금 배분(ISA / 토스증권 / 연금저축)을 반영해 계좌별 제안 연결

4. 수집 소스 품질 개선
- KB/Mirae scraper 수정
- JP/EU 리서치/매크로 소스 추가
- 저작권 이슈가 있는 PDF는 직접 다운로드보다 메타데이터/링크 우선

5. horizon 데이터 고도화
- `site/horizons/*` 버킷별로 더 다른 메트릭과 서술을 넣기
- 주간/월간/분기별 비교형 지표 추가
- 실제 보유 종목이 들어오면 신규 매수뿐 아니라 비중 축소/교체 액션까지 계산 확장
- snapshot-only source의 역사적 백필 전략 별도 설계
- archive 복원 스크립트 또는 raw 재수집 절차 문서화

## 삭제된 이전 우선순위 메모

기존 `build_site_report.py 완성`, `주간/월간 확장 설계` 는 이미 1차 완료되었고, 이제는 품질 고도화와 렌더링 검증 단계다.

## 참고용 렌더링 검증 포인트
- `site/{date}/result.json` 과 `site/{date}/index.html` 구조 일치 확인
- `site/horizon_index.json` 과 `site/horizons/*` 가 템플릿과 맞는지 확인
- `site/template/index.html` 을 기준 템플릿으로 유지

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

8. historical backfill은 current snapshot source와 분리해서 다룰 것
- `fred_api`, `opendart` 같은 historical-safe source와 RSS/스크래퍼를 혼용해 과거를 재현했다고 가정하면 안 됨
- snapshot-only source는 `data/backfills/*.json` 에 skipped 로 남기는 현재 정책 유지

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
