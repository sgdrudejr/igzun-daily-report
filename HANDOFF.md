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
- 원문 다운로드/상세 본문 확보 경로는 [`collectors/registry/download_routes.yaml`](/Users/seo/igzun-daily-report/collectors/registry/download_routes.yaml) 에 운영 문서로 정리한다.
- `download_routes.yaml` 에는 네이버 리서치 외에 신한/KB/미래에셋/하나/삼성 국내 증권사와 ECB/BIS/BOJ/IMF 공개 소스의 실제 다운로드 루트 검증 결과가 반영되어 있다.
- `naver_research` 는 시장정보/투자정보/종목분석/산업분석/경제분석/채권분석 6개 카테고리를 모두 수집 대상으로 확장했다.
- `naver_research` 는 2026-03-30 검증 기준 카테고리별 30건씩 총 180건의 리스트 메타를 수집할 수 있다.
- `kr_brokerage_shinhan` 는 공개 list API 기반으로 실제 문서 메타를 수집한다.
- `kr_brokerage_shinhan` 는 이제 `bbs2.shinhansec.com` 상세 popup HTML까지 저장하고, PDF popup 경로도 metadata에 남긴다. 다만 현재 확인된 PDF popup은 로그인 게이트가 있다.
- `kr_brokerage_mirae` 는 공개 리스트에서 PDF direct link를 잡아 실제 PDF/TXT 아티팩트를 저장한다.
- `raw -> normalized -> manifest -> bridge -> refined_insights_inventory.json` 흐름이 작동한다.
- 공개 리포트 링크는 이제 메타데이터만 저장하지 않고, 가능한 경우 상세 본문 HTML/TXT와 PDF/TXT 아티팩트까지 같이 저장한다.
- `content_hash` 기반 중복 제거가 구현되어 있다.
- 수집 URL 로깅은 manifest의 `fetched_urls` 에 기록된다.
- `2026-03-30` 기준 일배치가 다시 실행되었고, 수집 -> 분석 -> 사이트 생성 -> horizon 집계까지 재생성되었다.
- `2026-01-01 ~ 2026-03-30` 구간에 대해 historical-safe source 기반 백필이 추가되었다.
- 백필 실행기는 [`scripts/backfill_history.py`](/Users/seo/igzun-daily-report/scripts/backfill_history.py) 이며, 현재 기준 Q1 백필 요약은 [`data/backfills/2026-01-01_to_2026-03-30.json`](/Users/seo/igzun-daily-report/data/backfills/2026-01-01_to_2026-03-30.json) 에 기록된다.
- 저장공간 정리기는 [`scripts/storage_retention.py`](/Users/seo/igzun-daily-report/scripts/storage_retention.py) 이며, 상태는 [`data/storage_retention/status.json`](/Users/seo/igzun-daily-report/data/storage_retention/status.json) 에 기록된다.
- `storage_retention.py` 는 이제 오래된 원문을 단순 압축만 하지 않고 `compact_raw`, `compact_normalized`, `chunks` 아카이브를 함께 생성한다.
- 즉, 오래된 PDF/HTML/TXT 원문을 지우더라도 `핵심 메타 + 발췌문 + 청크 텍스트`는 유지되어 후속 분석과 RAG형 활용이 가능하다.
- `scripts/daily_update.sh` 에 수집/분석/사이트 생성/배포 흐름이 연결되어 있다.
- `scripts/daily_update.sh` 는 이제 `TZ=Asia/Seoul` 기준 날짜를 사용한다.
- `scripts/valuation_engine.py` 가 추가되어 S&P500 ERP, 52주 레인지, 200일선 이격도, KOSPI PBR 추정치를 생성한다.
- `scripts/signal_engine.py` 가 추가되어 RSI, MACD, 볼린저밴드, 이평선, 캔들, 엘리엇 파동을 종합한 ETF별 `강력매수/분할매수/소규모탐색/관망/비중축소/회피` 신호를 생성한다.
- `scripts/llm_insights.py` 가 추가되어 매크로/밸류에이션/신호/수집문서를 합친 한국어 투자 인사이트를 생성한다.
- `scripts/build_research_context.py` 가 추가되어 최근 7거래일/30거래일 누적 문서, 과거 레짐·점수 변화, horizon 집계 요약, 계좌 실행 제약을 묶은 상위 `딥리서치 컨텍스트` 를 생성한다.
- 현재 LLM 단계는 파이프라인에 연결되어 있으나 `.env` 의 `ANTHROPIC_API_KEY` 가 비어 있어 실제 API 호출 대신 fallback 규칙 기반 인사이트로 동작한다.
- `llm_insights.py` 는 이제 당일 문서만 보지 않고 `data/research_context/{date}.json` 을 함께 읽어 누적 맥락 기반 분석을 수행한다.
- `llm_insights.py` 는 이제 OpenAI Responses API도 지원한다. `.env` 에 `OPENAI_API_KEY` 를 넣으면 기본값으로 `gpt-5.4` 를 사용하며, `OPENAI_LLM_MODEL` 과 `LLM_PROVIDER` 로 provider/model 우선순위를 조절할 수 있다.
- `11:00 KST` 자동 실행용 launch agent 가 설치되어 있다.
- launch agent 템플릿은 [`cron/com.seo.igzun-daily-report.daily.plist`](/Users/seo/igzun-daily-report/cron/com.seo.igzun-daily-report.daily.plist), 설치 스크립트는 [`scripts/install_launch_agent.sh`](/Users/seo/igzun-daily-report/scripts/install_launch_agent.sh) 이다.
- `scripts/macro_analysis.py`, `scripts/etf_recommender.py`, `scripts/build_site_report.py` 작업이 시작되어 있다.
- `build_site_report.py` 는 이제 top buy에 `microPlan`, `microStepAmount`, `timingDetails` 를 포함해 1%~2% 단위 분할매수 가이드를 노출한다.
- [`scripts/build_site_report.py`](/Users/seo/igzun-daily-report/scripts/build_site_report.py) 가 `dataByPeriod` 호환 구조를 유지한 채 한국어 인사이트 중심 리포트로 재작성되었다.
- `site/{date}/result.json` 에 1일/1주/1개월/3개월/6개월 구간별 브리핑, 주요 이슈, 포트폴리오, ETF 아이디어가 들어가도록 정리되었다.
- 포트폴리오 블록에 `capitalPlan`, `targetAmounts`, `todayTargetAmounts`, `accountPlans`, `keyStats`, `scoreCoachmark` 가 추가되어 총 현금, 이번 기간 집행 예산, 자산군 목표 금액, 오늘 집행 목표, 계좌별 코멘트, 점수 설명까지 함께 보여준다.
- 실행 가이드 블록에 `todayAmount`, `splitPlan`, `addRule`, `pauseRule`, `reviewRule` 가 추가되어 분할매수 단계와 보류 조건을 구체적으로 제시한다.
- ETF 아이디어 블록에 `macroContext`, `evidencePoints`, `positioning`, `watchPoint` 가 추가되어 왜 사는지와 어떤 비중으로 접근할지까지 설명한다.
- 핵심 이슈 카드에 `portfolioImplication`, `executionGuide` 가 추가되어 기사 요약이 포트폴리오 판단과 집행 방식으로 직접 연결된다.
- [`collectors/document_enricher.py`](/Users/seo/igzun-daily-report/collectors/document_enricher.py) 가 추가되어 다음을 수행한다.
  - 네이버 리서치 상세 페이지 본문 추출
  - PDF 링크 발견 시 실제 파일 다운로드
  - PDF 텍스트 추출
  - `data/raw/{date}/{source_id}/` 아래 `*_detail.html`, `*_detail.txt`, `*.pdf`, `*.txt` 저장
- [`scripts/refine_insights.py`](/Users/seo/igzun-daily-report/scripts/refine_insights.py) 는 이제 기존 PDF/텍스트 입력 외에 `data/raw/**/*.txt` 도 읽어서 collector가 수집한 원문 텍스트를 실제 분석 입력으로 사용한다.
- [`requirements.txt`](/Users/seo/igzun-daily-report/requirements.txt) 에 최소 Python 의존성을 기록했다. 새 환경에서는 `pypdf` 가 반드시 필요하다.
- `undefined`/`None`/`null` 문자열이 결과 JSON 에 남지 않도록 fallback 처리했다.
- [`site/template/index.html`](/Users/seo/igzun-daily-report/site/template/index.html) 를 기준 템플릿으로 추가했고, 최신 버전은 Toss 증권/토스뱅크 UI 위계를 참고해 핵심 카드 3개 + 하단 시트형 설명/출처 구조로 재배치되었다.
- 날짜별 [`site/2026-03-27/index.html`](/Users/seo/igzun-daily-report/site/2026-03-27/index.html), [`site/2026-03-29/index.html`](/Users/seo/igzun-daily-report/site/2026-03-29/index.html), [`site/2026-03-30/index.html`](/Users/seo/igzun-daily-report/site/2026-03-30/index.html) 도 템플릿 기준으로 다시 생성했다.
- 화면 문구를 `ETF 아이디어`, `레짐 온도`, `출처·메타데이터` 중심으로 정리했다.
- 포트폴리오 탭에 `포트폴리오 레짐 적합도` 점수 카드가 추가되었다.
- 현재 점수는 수익률 점수가 아니라 `레짐 적합도 + 분산도 + 현금 운용` 합성 점수다.
- [`scripts/build_horizon_views.py`](/Users/seo/igzun-daily-report/scripts/build_horizon_views.py) 가 추가되었다.
- 이 스크립트는 누적된 일간 `site/*/result.json` 을 읽어 `site/horizon_index.json` 과 `site/horizons/` 아래 기간별 집계 파일을 생성한다.
- UI는 더 이상 좌하단 플로팅 달력이 아니라 최신 일간 리포트를 기본으로 보는 탭 구조다.
- 상단의 `1일/1주/1개월/3개월/6개월` 선택 칩은 제거되었고, 별도 `기간별 투자 방향성` 탭에서 일간/주간/월간/분기/반기 흐름을 비교한다.
- 새로고침 시 기본 진입값은 항상 `1일 / 최신 날짜` 이다.
- 각 섹션 탭은 개별 스크롤 pane 으로 동작하도록 바뀌었다.
- 섹션 순서는 `포트폴리오 -> 실행 가이드 -> 기간별 투자 방향성 -> 시장 브리핑 -> 핵심 이슈 -> ETF 아이디어` 다.
- 상단 헤더는 최소 정보만 남기도록 축소되었고, 기존 `누적 업데이트 / 주요 출처` pill 행은 제거되었다.
- 포트폴리오 점수 설명과 출처 메타데이터는 본문 inline 확장 대신 하단 시트(sheet) 오버레이로 열리도록 바뀌었다.
- 실행 가이드는 여러 종목 카드를 세로로 쌓지 않고 상단 셀렉터로 종목을 선택한 뒤 한 카드씩 읽는 구조로 바뀌었다.
- 시장 브리핑은 점수를 `선별 매수 가능 / 중립 대응 / 현금 우위` 같은 해석 문구로 연결하고, LLM 내러티브를 먼저 보여주도록 바뀌었다.
- `site/horizons/*/*.json` 은 이제 top-level 에 `regime`, `regimeKr`, `totalScore`, `valuation`, `signals`, `llmInsights` 를 함께 담는다.
- 현재 생성된 누적 버킷 수는 일간 25개, 주간 7개, 월간 2개, 분기 1개, 반기 1개다.
- Q1 백필 이후 현재 생성된 누적 버킷 수는 일간 66개, 주간 14개, 월간 3개, 분기 1개, 반기 1개다.
- `site/` 아래 HTML/JSON 검색 기준 `undefined`/`None` 문자열이 남지 않도록 다시 검증했다.
- `briefing.strategy`, `rebalancing`, `briefing.scoreChips`, `briefing.metricChips`, `portfolio.scoreChips` 블록이 추가되었다.
- 1일/1주/1개월/3개월/6개월은 각 기간의 질문과 지표가 다르게 보이도록 다시 정리되었다.
- 1일/1주/1개월/3개월/6개월은 집행 리듬도 다르게 설계되어 있다.
  - 1일: 3거래일 분할매수
  - 1주: 주간 3회 분할매수
  - 1개월: 4주 분할 구축
  - 3개월: 6~8주 단계 구축
  - 6개월: 월별 리밸런싱 구축
- `load_market_data.py`, `macro_analysis.py`, `etf_recommender.py` 는 특정 날짜 기준 as-of 계산이 가능하도록 보정되었다.
- 백필은 현재 `fred_api`, `opendart` 중심으로 수행된다. RSS/스크래퍼/ECOS 는 snapshot 성격이 강해 Q1 백필 기본 대상에서 제외된다.
- 저장공간 정리 1차 적용 결과: raw 32일치, normalized 10일치를 summary+archive 로 넘겼다.
- 저장공간 정리 정책은 현재 `archive_summaries/raw|normalized/*.json` + `archives/compact_raw/*.jsonl.gz` + `archives/compact_normalized/*.jsonl.gz` + `archives/chunks/*.jsonl.gz` 구조다.

### 현재 작업 트리 상태

다음 에이전트는 아래 상태를 전제로 이어받아야 한다.

- 커밋 전 변경 파일이 남아 있을 수 있으므로 반드시 `git status --short` 를 먼저 확인한다.
- [`scripts/build_horizon_views.py`](/Users/seo/igzun-daily-report/scripts/build_horizon_views.py) 는 새로 추가된 누적 집계 레이어다.
- [`site/template/index.html`](/Users/seo/igzun-daily-report/site/template/index.html) 와 날짜별 `site/*/index.html` 은 같은 탭형 UI를 공유한다.
- [`data/portfolio_state.json`](/Users/seo/igzun-daily-report/data/portfolio_state.json) 는 현재 전액 현금 상태를 반영한다.
- 브라우저 실기기 검증은 아직 남아 있다. 특히 Galaxy S25 Ultra 기준 줄바꿈, 칩 높이, 상단 드롭다운 폭을 확인해야 한다.
- `data/market_data_history/` 와 `data/etf_price_history/` 는 로컬 캐시이며 `.gitignore` 대상이다.
- `data/archives/` 는 로컬 압축본 저장소이며 Git 에 올리지 않는다.
- `data/research_context/{date}.json` 은 LLM/딥리서치 입력용 누적 컨텍스트 스냅샷이며, `daily_update.sh` 에서 valuation/signal 이후 자동 생성된다.

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
│       ├── sources.yaml
│       └── download_routes.yaml
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
│   ├── valuation_engine.py
│   ├── signal_engine.py
│   ├── llm_insights.py
│   ├── build_research_context.py
│   ├── technical_timing.py
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
- source별 원문 다운로드 경로 문서화 구조
- 국내 증권사(신한/KB/미래에셋/하나/삼성) 및 해외 공개기관(ECB/BIS/BOJ/IMF) 루트 1차 구체화
- 네이버 리서치 6개 카테고리 전체 확장
- 신한 list API fetcher 1차 구현
- 미래에셋 direct PDF fetcher 1차 구현
- fetcher registration 구조
- `RawDocument` 표준 구조
- dedup index 저장 구조
- manifest 저장 구조
- normalized JSONL 저장 구조
- bridge를 통한 기존 `refined_insights_inventory.json` 호환
- RSS/FRED/ECOS/OpenDART/Naver Research/SEC EDGAR/BIS/Investing.com fetcher
- `daily_update.sh` 에 collectors 단계 추가
- `macro_analysis.py`, `etf_recommender.py`, `build_site_report.py`, `build_horizon_views.py` 가 연결되었다.
- 밸류에이션 레이어 추가
- 명시적 매수/매도/보류 신호 엔진 추가
- LLM 인사이트 생성 레이어 추가
- `2026-03-30` 기준 batch 실행 및 사이트 산출물 생성
- 일간 결과를 다시 주간/월간/분기/반기 버킷으로 집계하는 레이어가 들어갔다.
- 1일/1주/1개월/3개월/6개월마다 누적 문서 수, 평균 점수, 주요 출처를 따로 보여준다.
- 2026년 1월~3월 weekday 기준 63개 날짜에 대해 Q1 백필을 수행했고, 사이트에는 총 66개 일간 버킷이 존재한다.
- `site/horizon_index.json` 에 storage retention 상태와 backfill run 메타가 추가되었다.
- `daily_update.sh` 에 retention 훅이 추가되어 오래된 raw/normalized/manifests 를 요약+압축 대상으로 보낼 수 있다.
- `daily_update.sh` 가 cron/launchd 환경에서도 깨지지 않도록 KST 날짜와 절대 python 경로를 사용하도록 보정했다.
- `naver_research` 는 더 이상 짧은 제목 메타만 수집하지 않고, 상세 페이지 본문을 우선 수집한다.
- `naver_research` 의 `industry` 카테고리는 타 카테고리와 테이블 구조가 달라 title cell index를 별도 처리한다.

### 아직 미구현 또는 미완료

- 브라우저에서 실제 `site/{date}/index.html` 렌더링 검증
- 탭 간 개별 스크롤 동작 검증
- Galaxy S25 Ultra 기준 줄바꿈 / 상단 드롭다운 UI 검증
- 직접 PDF 링크를 제공하는 국내 증권사 소스(KB/신한/미래에셋 등) 셀렉터 안정화
- `download_routes.yaml` 에 적힌 신한 list API, KB Today, 미래에셋 attachment download, 하나 file server, 삼성 querystring download 루트를 실제 fetcher 로 옮기는 작업
- KB Today/리포트 상세 흐름을 실제 fetcher로 옮기기
- 하나/삼성의 파일명 확보 로직을 붙여 direct PDF 수집까지 연결하기
- 삼성증권은 direct PDF endpoint는 확인됐지만 리스트/리서치 허브 추출은 로그인 또는 추가 제약 가능성이 있어 재검증이 필요
- 포트폴리오 시사점 로직 정교화
- 포트폴리오 점수 산식 고도화
- ETF/섹터 아이디어를 지역/레짐/리스크와 더 강하게 연결하는 설명 강화 2차
- 보유 종목이 생겼을 때 매도/축소 가이드까지 자동 산출하도록 확장
- 실제 Claude API 키를 연결해 fallback이 아닌 실 LLM 내러티브로 전환
- `kr_brokerage_kb`, `kr_brokerage_mirae` 스크래퍼 안정화
- 주요 유럽/일본 소스 추가 확장
- source health check와 stale source 알림
- cron 시각 분리 운영 검증

## 다음 작업 우선순위

1. 브라우저 렌더링 검증
- `site/{date}/index.html` 에서 `기간별 투자 방향성` 탭이 최신 horizon 데이터를 정상 로드하는지 확인
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
- `site/horizon_index.json` 과 `site/horizons/*` 가 `기간별 투자 방향성` 탭과 맞는지 확인
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
