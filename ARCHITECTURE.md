# ARCHITECTURE

## 목표

이 파이프라인의 목표는 다음과 같다.

- 전 세계 주요 금융/시장 데이터를 안정적으로 수집한다.
- 수집 단계는 향후 cron 기반 자동 실행에 적합해야 한다.
- 사람 손으로 유지보수 가능한 구조를 유지한다.
- 수집 결과가 기존 분석 파이프라인과 호환되어야 한다.
- 최종적으로 3~6개월 투자 관점의 시장 판단과 ETF/테마 기반 포트폴리오 인사이트로 연결되어야 한다.

## 전체 실행 흐름

실제 기본 흐름은 [`scripts/daily_update.sh`](/Users/seo/igzun-daily-report/scripts/daily_update.sh) 에 연결되어 있다.

```text
sources.yaml
  -> collectors.runner
    -> fetcher 실행
    -> document_enricher
      -> 상세 HTML 본문 수집
      -> PDF 링크 발견 시 실제 다운로드
      -> PDF 텍스트 추출
    -> RawDocument 생성
    -> dedup 검사
    -> data/raw/{date}/{source_id}/*.json 저장
    -> data/raw/{date}/{source_id}/*_detail.html, *_detail.txt, *.pdf, *.txt 저장
    -> normalize
    -> data/normalized/{date}/documents.jsonl 저장
    -> manifest 저장
  -> collectors.bridge
    -> data/refined_insights_inventory.json 갱신
  -> legacy/analysis scripts
    -> process_pdfs.py
    -> refine_insights.py
    -> integrate_refined_insights.py
    -> load_market_data.py
    -> apply_market_quant.py
  -> macro_analysis.py
  -> etf_recommender.py
  -> build_site_report.py
    -> storage_retention.py
    -> build_horizon_views.py
  -> site/{date}/result.json, index.html
  -> site/horizon_index.json
  -> site/horizons/{daily,weekly,monthly,quarterly,halfyearly}/*.json
  -> site/template/index.html 기반 horizon 탭 UI
  -> git commit / git push
```

## 사이트 리포트 데이터 구조

[`scripts/build_site_report.py`](/Users/seo/igzun-daily-report/scripts/build_site_report.py) 는 각 날짜의 `site/{date}/result.json` 안에 `dataByPeriod` 를 생성한다.

핵심 블록:

- `briefing`
  - `sentiment`
  - `scoreChips`
  - `metricChips`
  - `forecast`
  - `strategy`
  - `insights`
  - `indices`
- `newsList`
  - 각 카드에 `summary`, `detailPoints`, `portfolioImplication`, `executionGuide`, `impacts`, `sources`
- `portfolio`
  - `portfolioScore`
  - `capitalPlan`
  - `targetAmounts`
  - `accountPlans`
  - `allocations`
  - `notes`
- `rebalancing`
  - `actions[*].todayAmount`
  - `actions[*].splitPlan`
  - `actions[*].addRule`
  - `actions[*].pauseRule`
  - `actions[*].reviewRule`
- `recommendations`
  - `ideas[*].macroContext`
  - `ideas[*].evidencePoints`
  - `ideas[*].positioning`
  - `ideas[*].watchPoint`

의도:

- 기사 요약이 끝이 아니라 포트폴리오와 매수 실행 가이드로 직접 이어져야 한다.
- 현재 포트폴리오가 전액 현금이어도 "어느 계좌에 얼마를 어떤 속도로 넣을지"를 보여줄 수 있어야 한다.
- 기간별로 같은 포트폴리오도 다른 질문으로 해석되어야 한다.

## 수집 파이프라인 구조

### 1. source registry

모든 수집 대상은 [`collectors/registry/sources.yaml`](/Users/seo/igzun-daily-report/collectors/registry/sources.yaml) 에 정의한다.

필수 개념:

- `id`: source 식별자
- `fetcher_type`: 어떤 fetcher class를 사용할지 결정
- `tier`: 우선순위/실행군
- `region`
- `language`
- `document_type`
- `sector`
- `enabled`
- `schedule`
- `config`

새 소스를 추가할 때는:

1. `sources.yaml` 에 source 추가
2. 필요 시 `collectors/fetchers/` 에 fetcher 추가
3. fetcher를 registry에 등록

### 2. 단일 진입점

수집은 반드시 [`collectors/runner.py`](/Users/seo/igzun-daily-report/collectors/runner.py) 를 통해 실행한다.

지원 옵션:

- `--date YYYY-MM-DD`
- `--tier`
- `--source`
- `--dry-run`
- `--base-dir`

주의:

- `runner.py` 자체를 날짜 범위 루프로 확장하지 않는다.
- historical range 실행은 [`scripts/backfill_history.py`](/Users/seo/igzun-daily-report/scripts/backfill_history.py) 가 날짜 루프를 돌면서 내부적으로 `runner.py` 를 반복 호출하는 방식으로 유지한다.

### 3. fetcher 구조

모든 fetcher는 [`collectors/base_fetcher.py`](/Users/seo/igzun-daily-report/collectors/base_fetcher.py) 의 `BaseFetcher` 를 상속한다.

핵심 인터페이스:

- `fetch(date) -> list[RawDocument]`
- `health_check() -> bool`
- `fetch_with_retry()`

현재 구현 fetcher:

- [`collectors/fetchers/rss_fetcher.py`](/Users/seo/igzun-daily-report/collectors/fetchers/rss_fetcher.py)
- [`collectors/fetchers/fred_fetcher.py`](/Users/seo/igzun-daily-report/collectors/fetchers/fred_fetcher.py)
- [`collectors/fetchers/ecos_fetcher.py`](/Users/seo/igzun-daily-report/collectors/fetchers/ecos_fetcher.py)
- [`collectors/fetchers/opendart_fetcher.py`](/Users/seo/igzun-daily-report/collectors/fetchers/opendart_fetcher.py)
- [`collectors/fetchers/naver_research.py`](/Users/seo/igzun-daily-report/collectors/fetchers/naver_research.py)
- [`collectors/fetchers/kr_brokerage.py`](/Users/seo/igzun-daily-report/collectors/fetchers/kr_brokerage.py)
- [`collectors/fetchers/edgar_fetcher.py`](/Users/seo/igzun-daily-report/collectors/fetchers/edgar_fetcher.py)

원문 보강 레이어:

- [`collectors/document_enricher.py`](/Users/seo/igzun-daily-report/collectors/document_enricher.py)

역할:

- 네이버 리서치 상세 페이지처럼 HTML 본문이 있는 경우 실제 본문 텍스트 추출
- PDF 링크가 있으면 실제 파일 다운로드
- PDF 텍스트 추출 후 `RawDocument.content` 를 원문 기반으로 치환
- raw 디렉토리에 HTML/TXT/PDF artifact 저장

## 데이터 구조

### RawDocument

`RawDocument` 는 fetcher가 반환하는 공통 구조다.

주요 필드:

- `source_id`
- `title`
- `url`
- `published_date`
- `content`
- `document_type`
- `region`
- `language`
- `sector`
- `tags`
- `metadata`
- `fetched_url`

`doc_id` 는 `source_id|url|published_date` 기반 해시로 생성된다.

### Raw 저장

```text
data/raw/{date}/{source_id}/{doc_id}.json
data/raw/{date}/{source_id}/{doc_id}_detail.html
data/raw/{date}/{source_id}/{doc_id}_detail.txt
data/raw/{date}/{source_id}/{doc_id}.pdf
data/raw/{date}/{source_id}/{doc_id}.txt
```

설명:

- fetcher가 받아온 원본 payload 저장
- 가능한 경우 상세 HTML, PDF, 추출 텍스트도 같이 저장
- 재현 가능성 확보
- source별 디버깅 가능

### Normalized 저장

```text
data/normalized/{date}/documents.jsonl
```

`collectors/normalizer.py` 가 `RawDocument` 를 아래 필드로 변환한다.

- `id`
- `source_id`
- `title`
- `url`
- `published_date`
- `collected_date`
- `region`
- `sector`
- `document_type`
- `language`
- `summary`
- `content_length`
- `content_hash`
- `raw_file_path`
- `tags`
- `metadata`
- `fetched_url`

### Manifest 저장

```text
data/manifests/{date}_run.json
```

manifest는 각 수집 실행 단위를 기록한다.

필드:

- `date`
- `started_at`
- `finished_at`
- `total_documents`
- `total_duplicates`
- `total_errors`
- `sources`

각 source별 기록:

- `status`
- `documents`
- `duplicates`
- `errors`
- `error_msg`
- `fetched_urls`

이 `fetched_urls` 는 “어디서 무엇을 수집했는가”를 추적하기 위한 핵심 로그다.

### Dedup 저장

```text
data/index/content_hashes.json
```

설명:

- key: `content_hash`
- value: 최초 수집 날짜

중복 기준:

- `RawDocument.content` 의 SHA256 해시
- 같은 내용은 source가 달라도 중복으로 처리될 수 있음

주의:

- 현재는 `content` 기반 전역 dedup 이다.
- 향후 source별 dedup 전략을 넣고 싶더라도 현재 구조를 깨지 말고 확장해야 한다.
- historical backfill 시 dedup 때문에 특정 날짜 raw 폴더가 비어 있을 수 있다.
- 이 경우 [`scripts/macro_analysis.py`](/Users/seo/igzun-daily-report/scripts/macro_analysis.py) 는 해당 날짜 이전의 가장 최근 raw snapshot을 찾아 참고한다.

## bridge 호환 설계

기존 파이프라인과의 호환을 위해 [`collectors/bridge.py`](/Users/seo/igzun-daily-report/collectors/bridge.py) 가 존재한다.

역할:

- `data/normalized/{date}/documents.jsonl` 읽기
- 기존 [`data/refined_insights_inventory.json`](/Users/seo/igzun-daily-report/data/refined_insights_inventory.json) 포맷으로 append
- `source_meta.metadata`, `content_length` 를 함께 넘겨 downstream 이 원문 artifact 를 다시 찾을 수 있게 함

이 포맷은 현재 [`scripts/refine_insights.py`](/Users/seo/igzun-daily-report/scripts/refine_insights.py) 가 기대하는 형식을 유지하기 위해 절대 깨면 안 된다.

추가 연결:

- [`scripts/refine_insights.py`](/Users/seo/igzun-daily-report/scripts/refine_insights.py) 는 이제 기존 PDF 입력 외에도 `data/raw/**/*.txt` 를 읽는다.
- 즉 collector 가 내려받은 상세 본문/추출 텍스트도 실제 분석 입력이 된다.

## cron 실행 기준

현재 실제 자동화는 [`scripts/daily_update.sh`](/Users/seo/igzun-daily-report/scripts/daily_update.sh) 에 모여 있다.

권장 실행 분리:

- 06:00 KST: Tier 1 API source
- 07:00 KST: Tier 2 scraping source
- 08:00 KST: bridge 및 기본 정리
- 09:00 KST: insight refinement
- 11:00 KST: site report 생성 + 배포
- 14:00 KST: 미국 장중/장후 source 보강

현 시점에서는 하나의 `daily_update.sh` 로도 실행 가능하다.

현재 daily update 추가 단계:

- `storage_retention.py --delete-originals`
- `build_horizon_views.py`

즉, 매일 배치가 끝나면 오래된 raw/normalized/manifests 를 요약+압축 대상으로 넘기고, 그 뒤 1일/1주/1개월/3개월/6개월 뷰를 다시 집계한다.

### 기간별 실행 리듬

현재 보고서에서 사용하는 기본 분할매수 리듬:

- `1일`: 3거래일 분할매수
- `1주`: 주간 3회 분할매수
- `1개월`: 4주 분할 구축
- `3개월`: 6~8주 단계 구축
- `6개월`: 월별 리밸런싱 구축

이 값은 [`scripts/build_site_report.py`](/Users/seo/igzun-daily-report/scripts/build_site_report.py) 의 `EXECUTION_RHYTHM` 에 정의되어 있고, 포트폴리오/실행 가이드/ETF 아이디어에 동시에 반영된다.

## historical backfill 레이어

[`scripts/backfill_history.py`](/Users/seo/igzun-daily-report/scripts/backfill_history.py) 는 과거 날짜를 현재 구조에 맞춰 재생성하는 래퍼다.

역할:

- `load_market_data.py` 로 긴 구간 시장데이터 캐시 생성
- `etf_recommender.py` 로 ETF 가격 history cache 생성
- 날짜별로 `collectors.runner -> macro_analysis.py -> etf_recommender.py -> build_site_report.py` 순서 실행
- 마지막에 `build_horizon_views.py` 를 다시 돌려 1일/1주/1개월/3개월/6개월 누적 버킷 재생성

현재 기본 historical-safe source:

- `fred_api`
- `opendart`

현재 snapshot-only source로 간주하는 항목:

- RSS 계열
- `ecos_api`
- `naver_research`
- `kr_brokerage_*`

이 snapshot-only source들은 과거 시점 그대로 재현하기 어려우므로, 현재는 `data/backfills/*.json` 에 skipped 목록으로만 남긴다.

## 기간별 집계 레이어

[`scripts/build_horizon_views.py`](/Users/seo/igzun-daily-report/scripts/build_horizon_views.py) 는 누적된 일간 결과를 다시 읽어 기간별 뷰 파일을 만든다.

역할:

- 1일: 날짜별 버킷
- 1주: `YYYY-MM-wN` 형태의 월별 주차 버킷
- 1개월: 월 버킷
- 3개월: 분기 버킷
- 6개월: 반기 버킷

생성 파일:

- [`site/horizon_index.json`](/Users/seo/igzun-daily-report/site/horizon_index.json)
- [`site/horizons/daily/`](/Users/seo/igzun-daily-report/site/horizons/daily/)
- [`site/horizons/weekly/`](/Users/seo/igzun-daily-report/site/horizons/weekly/)
- [`site/horizons/monthly/`](/Users/seo/igzun-daily-report/site/horizons/monthly/)
- [`site/horizons/quarterly/`](/Users/seo/igzun-daily-report/site/horizons/quarterly/)
- [`site/horizons/halfyearly/`](/Users/seo/igzun-daily-report/site/horizons/halfyearly/)

추가 메타:

- `site/horizon_index.json` 에 `storageRetention`, `backfillRuns` 메타를 함께 저장한다.
- 현재 프론트가 이 메타를 직접 렌더링하지는 않지만, 웹 레이어에서 읽을 수 있게 보존한다.

집계 원칙:

- 가장 최근 일간 결과를 해당 버킷의 기본 본문으로 사용한다.
- `updateCount`, `docsTotal`, `avgScore`, `sourceLabels` 를 누적 계산해 버킷 헤더와 본문에 다시 주입한다.
- 주간/월간/분기/반기 버킷은 단순 date alias 가 아니라 누적 요약 레이어다.
- `site/template/index.html` 은 `기간 유형 탭 -> 기간 선택 탭 -> 섹션 탭` 구조로 이 집계 파일들을 읽는다.

## 보고서/프론트 구조

### result.json 주요 블록

현재 일간 `site/{date}/result.json` 의 각 period 섹션은 아래 블록을 가진다.

- `briefing`
- `newsList`
- `portfolio`
- `rebalancing`
- `recommendations`

`briefing` 내부에는 아래 세부 블록이 포함된다.

- `sentiment`
- `scoreChips`
- `metricChips`
- `forecast`
- `strategy`
- `insights`
- `indices`

### UI 구조

[`site/template/index.html`](/Users/seo/igzun-daily-report/site/template/index.html) 는 다음 규칙으로 동작한다.

- 상단은 `기간 유형 칩 + 기간 선택 드롭다운` 1행 구조
- 새로고침 시 항상 `1일 / 최신 날짜` 로 진입
- 본문은 `포트폴리오 -> 실행 가이드 -> 시장 브리핑 -> 핵심 이슈 -> ETF 아이디어` 탭 구조
- 각 탭은 독립적인 scroll pane 으로 동작
- 출처 메타데이터는 본문 중간 삽입이 아니라 카드/아이템 하단의 고정 slot 에 렌더

### 기간별 해석 원칙

동일한 현재 포트폴리오라도 기간에 따라 질문이 달라진다.

- 1일: 오늘 바로 진입할 근거가 있는가
- 1주: 이번 주의 반응이 추세로 이어질 수 있는가
- 1개월: 월간 레짐을 기준으로 어떤 자산군을 중심에 둘 것인가
- 3개월: 3개월 후를 보며 어떤 포트폴리오를 만들어 둘 것인가
- 6개월: 6개월 보유를 전제로 어떤 비중을 유지해야 하는가

이 차이를 반영하기 위해:

- `briefing.metricChips` 는 period별로 서로 다른 지표를 노출
- `briefing.strategy` 는 period별 질문 중심 서술을 사용
- `rebalancing` 은 period별 실행 예산 비율과 액션 강도를 다르게 계산

생성 파일:

- [`site/horizon_index.json`](/Users/seo/igzun-daily-report/site/horizon_index.json)
- `site/horizons/daily/*.json`
- `site/horizons/weekly/*.json`
- `site/horizons/monthly/*.json`
- `site/horizons/quarterly/*.json`
- `site/horizons/halfyearly/*.json`

설계 원칙:

- 일간 결과를 원본으로 유지
- 주간/월간/분기/반기 뷰는 누적 요약 레이어로 생성
- 최신 일간 리포트의 해당 기간 섹션을 기반으로 사용
- 그 위에 `업데이트 횟수`, `평균 점수`, `누적 문서 수`, `주요 출처`를 덧붙여 집계 인사이트를 만든다

## 실패 처리 기준

### fetch 단계

- `fetch_with_retry()` 로 재시도
- 기본 재시도: 3회
- backoff: 지수 증가
- 실패해도 전체 파이프라인은 가능한 한 계속 진행

### source 상태 분류

- `success`
- `empty`
- `all_duplicates`
- `skipped`
- `error`
- `dry_run_ok`
- `dry_run_fail`

### 운영 기준

- 일부 source 실패는 전체 배치를 막지 않는다.
- manifest 기준으로 실패/빈 결과/중복률을 확인한다.
- 동일 source가 3일 이상 `empty` 또는 `error` 인 경우 stale 경고를 주는 로직을 추가할 예정

## 스토리지 정리 레이어

[`scripts/storage_retention.py`](/Users/seo/igzun-daily-report/scripts/storage_retention.py) 는 오래된 재생산 가능 산출물을 요약/압축/삭제하는 레이어다.

대상:

- `data/raw/{date}/`
- `data/normalized/{date}/`
- `data/manifests/{date}_run.json`

정리 원칙:

- `site/{date}/result.json` 이 존재하는 날짜만 정리 대상으로 삼는다.
- raw는 `data/archive_summaries/raw/{date}.json` summary + `data/archives/raw/{date}.tar.gz`
- normalized는 `data/archive_summaries/normalized/{date}.json` summary + `data/archives/normalized/{date}.jsonl.gz`
- manifests는 `data/archives/manifests/{date}_run.json.gz`
- archive 파일은 로컬 보관용이며 `.gitignore` 대상이다.
- 요약 상태는 `data/storage_retention/status.json` 에 기록하고 Git 에 포함할 수 있다.

## 현재 아키텍처의 핵심 제약

아래는 반드시 유지해야 한다.

- `sources.yaml` 기반 source 정의
- `runner.py` 단일 진입점
- `raw/normalized/manifests/index` 저장 구조
- `bridge.py` 를 통한 기존 파이프라인 호환
- `data/refined_insights_inventory.json` 하위 호환

## TODO

- `build_site_report.py` 결과 스키마 고정
- 한국어 인사이트 HTML 구조 확정
- 주간/월간/분기 집계 레이어 추가
- source stale 경고 체계 추가
- KB/Mirae scraper 안정화
