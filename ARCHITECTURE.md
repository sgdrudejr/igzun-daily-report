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
    -> RawDocument 생성
    -> dedup 검사
    -> data/raw/{date}/{source_id}/*.json 저장
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
  -> site/{date}/result.json, index.html
  -> git commit / git push
```

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
```

설명:

- fetcher가 받아온 원본 payload 저장
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

## bridge 호환 설계

기존 파이프라인과의 호환을 위해 [`collectors/bridge.py`](/Users/seo/igzun-daily-report/collectors/bridge.py) 가 존재한다.

역할:

- `data/normalized/{date}/documents.jsonl` 읽기
- 기존 [`data/refined_insights_inventory.json`](/Users/seo/igzun-daily-report/data/refined_insights_inventory.json) 포맷으로 append

이 포맷은 현재 [`scripts/refine_insights.py`](/Users/seo/igzun-daily-report/scripts/refine_insights.py) 가 기대하는 형식을 유지하기 위해 절대 깨면 안 된다.

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

