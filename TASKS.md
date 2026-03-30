# TASKS

## 완료된 작업

- [x] `igzun-daily-report` 리포지토리 로컬 클론
- [x] `.venv` 생성 및 기본 의존성 설치
- [x] `collectors/` 디렉토리 구조 생성
- [x] [`collectors/base_fetcher.py`](/Users/seo/igzun-daily-report/collectors/base_fetcher.py) 구현
- [x] [`collectors/fetcher_registry.py`](/Users/seo/igzun-daily-report/collectors/fetcher_registry.py) 구현
- [x] [`collectors/normalizer.py`](/Users/seo/igzun-daily-report/collectors/normalizer.py) 구현
- [x] [`collectors/dedup.py`](/Users/seo/igzun-daily-report/collectors/dedup.py) 구현
- [x] [`collectors/manifest.py`](/Users/seo/igzun-daily-report/collectors/manifest.py) 구현
- [x] [`collectors/registry_loader.py`](/Users/seo/igzun-daily-report/collectors/registry_loader.py) 구현
- [x] [`collectors/runner.py`](/Users/seo/igzun-daily-report/collectors/runner.py) 구현
- [x] [`collectors/bridge.py`](/Users/seo/igzun-daily-report/collectors/bridge.py) 구현
- [x] [`collectors/registry/sources.yaml`](/Users/seo/igzun-daily-report/collectors/registry/sources.yaml) 작성
- [x] RSS fetcher 구현
- [x] FRED fetcher 구현
- [x] ECOS fetcher 구현
- [x] OpenDART fetcher 구현
- [x] Naver Research fetcher 구현
- [x] KR brokerage fetcher 초안 구현
- [x] SEC EDGAR fetcher 구현
- [x] 공개 리포트 원문 보강 레이어(`collectors/document_enricher.py`) 추가
- [x] source별 원문 다운로드 경로 문서 [`collectors/registry/download_routes.yaml`](/Users/seo/igzun-daily-report/collectors/registry/download_routes.yaml) 추가
- [x] 네이버 리서치 상세 본문 수집 추가
- [x] PDF 링크 발견 시 실제 파일 다운로드 + 텍스트 추출 추가
- [x] `scripts/refine_insights.py` 에 collector raw text 입력 추가
- [x] `content_hash` 기반 dedup 저장 구조 적용
- [x] manifest에 `fetched_urls` 기록
- [x] `normalized -> refined_insights_inventory.json` bridge 연결
- [x] [`scripts/daily_update.sh`](/Users/seo/igzun-daily-report/scripts/daily_update.sh) 에 collectors 단계 연결
- [x] `2026-03-27` 배치 1회 실행
- [x] `2026-03-27` 산출물 생성 확인
- [x] ECOS KeyStatisticList API 방식으로 단순화
- [x] [`scripts/load_market_data.py`](/Users/seo/igzun-daily-report/scripts/load_market_data.py) 지역 확장 초안 반영
- [x] [`scripts/macro_analysis.py`](/Users/seo/igzun-daily-report/scripts/macro_analysis.py) 초안 작성
- [x] [`scripts/etf_recommender.py`](/Users/seo/igzun-daily-report/scripts/etf_recommender.py) 초안 작성
- [x] [`scripts/build_site_report.py`](/Users/seo/igzun-daily-report/scripts/build_site_report.py) 재작성 시작
- [x] [`scripts/build_site_report.py`](/Users/seo/igzun-daily-report/scripts/build_site_report.py) 를 `dataByPeriod` 호환 한국어 리포트 구조로 재작성
- [x] `1일/1주/1개월/3개월/6개월` 구간별 브리핑/이슈/포트폴리오/ETF 아이디어 생성
- [x] `result.json` 에 `undefined`/`None`/`null` 문자열 미포함 검증
- [x] `2026-03-27`, `2026-03-29` 날짜로 리포트 재생성 검증
- [x] [`site/template/index.html`](/Users/seo/igzun-daily-report/site/template/index.html) 생성
- [x] 날짜별 HTML 문구를 투자 리포트 톤으로 정리
- [x] 포트폴리오 레짐 적합도 점수 로직 추가
- [x] 포트폴리오 탭에 현재 배분 vs 목표 배분 비교 카드 추가
- [x] [`scripts/build_horizon_views.py`](/Users/seo/igzun-daily-report/scripts/build_horizon_views.py) 추가
- [x] `site/horizon_index.json` 생성
- [x] `site/horizons/` 아래 일간/주간/월간/분기/반기 집계 파일 생성
- [x] UI를 `플로팅 달력`에서 horizon 집계 기반 탭 구조로 변경
- [x] 상단 헤더에 `누적 업데이트 / 누적 문서 / 평균 점수 / 주요 출처` 요약 pill 추가
- [x] `2026-03-30` 실제 데이터 배치 재실행
- [x] `2026-03-30` 기준 일간/주간/월간/분기/반기 버킷 재생성
- [x] `site/` 전체 기준 `undefined`/`None` 문자열 미포함 재검증
- [x] 포트폴리오를 첫 탭으로 이동하고 `실행 가이드` 탭 추가
- [x] 상단 `1일/1주/1개월/3개월/6개월` 칩 제거
- [x] `기간별 투자 방향성` 탭 추가
- [x] 탭별 개별 스크롤 pane 구조 반영
- [x] 새로고침 시 `1일 / 최신 날짜` 기본 선택 반영
- [x] 최신 일간 리포트 고정 + 기간별 방향성 비교 탭 구조 반영
- [x] 점수/지표 칩 렌더링 추가
- [x] 출처 메타데이터를 본문 내부가 아니라 카드 하단 고정 위치로 재배치
- [x] 1일/1주/1개월/3개월/6개월별 질문과 메트릭 차별화 2차 반영
- [x] [`scripts/load_market_data.py`](/Users/seo/igzun-daily-report/scripts/load_market_data.py) 에 `--start-date/--end-date/--output` 추가
- [x] [`scripts/macro_analysis.py`](/Users/seo/igzun-daily-report/scripts/macro_analysis.py) 에 as-of 날짜 슬라이싱 추가
- [x] [`scripts/etf_recommender.py`](/Users/seo/igzun-daily-report/scripts/etf_recommender.py) 에 ETF price history cache 지원 추가
- [x] [`scripts/backfill_history.py`](/Users/seo/igzun-daily-report/scripts/backfill_history.py) 추가
- [x] [`scripts/storage_retention.py`](/Users/seo/igzun-daily-report/scripts/storage_retention.py) 추가
- [x] `2026-01-01 ~ 2026-03-30` Q1 백필 실행
- [x] Q1 백필 결과로 `site/` 일간/주간/월간/분기/반기 버킷 재생성
- [x] 오래된 raw/normalized 1차 archive + summary 생성
- [x] `daily_update.sh` 에 retention 훅 추가
- [x] `daily_update.sh` 를 KST 날짜 기준으로 보정
- [x] `11:00 KST` launch agent 설치 스크립트 추가 및 로컬 설치
- [x] cron/launchd 경로를 현재 저장소(`/Users/seo/igzun-daily-report`) 기준으로 정리
- [x] 포트폴리오에 `capitalPlan / targetAmounts / accountPlans` 추가
- [x] 실행 가이드에 `todayAmount / splitPlan / addRule / pauseRule / reviewRule` 추가
- [x] ETF 아이디어에 `macroContext / evidencePoints / positioning / watchPoint` 추가
- [x] 핵심 이슈 카드에 `portfolioImplication / executionGuide` 추가
- [x] 모든 기존 일간 결과(`site/20*-*-*/result.json`)를 새 구조로 재생성
- [x] horizon 집계(`site/horizons/*`)를 새 구조로 재생성

## 현재 진행 중

- [ ] 브라우저 기준 HTML 렌더링 최종 검증
- [ ] 포트폴리오 시사점 로직 정교화
- [ ] 포트폴리오 점수 산식 고도화
- [ ] ETF/테마 아이디어 설명 품질 개선 3차
- [ ] 기간별 지표 차별화 로직 추가 고도화
- [ ] Galaxy S25 Ultra 실기기 줄바꿈 / 칩 높이 확인
- [ ] `site/horizon_index.json` 의 retention/backfill 메타를 UI에 노출할지 결정
- [ ] 실제 보유 종목 입력 시 매도/축소 액션 자동 생성

## 남은 작업

### 수집

- [ ] `kr_brokerage_kb` 셀렉터/페이지 구조 재검증
- [ ] `kr_brokerage_mirae` 404 대응 및 실제 리서치 URL 재확인
- [ ] 신한/KB/미래에셋 등 직접 PDF 링크 제공 소스 우선 확장
- [ ] 일본/유럽 리서치 소스 추가
- [ ] source health check 리포트 추가
- [ ] 3일 이상 무수집 source stale 경고 추가
- [ ] snapshot-only source의 historical backfill 전략 설계

### 분석

- [x] 일간 데이터를 바탕으로 주간/월간/분기/반기 집계 스크립트 추가
- [ ] 리포트에서 단기 뉴스와 중기 방향성 분리
- [ ] 펀더멘털/기술적 시그널 동시 반영 설명 강화
- [x] 계좌별 현금/투입 가능 금액 반영 1차
- [x] horizon별 실행 예산 차등 반영 1차
- [x] horizon별 분할매수 리듬 차등 반영 1차
- [x] 기사 요약 -> 투자 시사점 -> 실행 메모 연결 1차

### 보고서

- [x] `build_site_report.py` 결과 스키마를 기존 프론트 호환형 `dataByPeriod` 구조로 맞춤
- [x] 레짐/핵심이슈/섹터/ETF/포트폴리오 블록 데이터 생성
- [x] 모든 필드 한국어화 1차 반영
- [x] 빈값 fallback 처리 1차 반영
- [x] 주간/월간/분기/반기 보고서 섹션 설계 1차 반영
- [x] `rebalancing` 블록 추가
- [x] `briefing.strategy`, `briefing.scoreChips`, `briefing.metricChips`, `portfolio.scoreChips` 추가
- [x] 핵심 이슈 상세 설명 포인트(`detailPoints`) 추가

### 운영

- [ ] cron 시각 분리 운영 검증
- [ ] 실패 시 재시도/부분성공 로그 기준 정리
- [ ] GitHub Pages 자동 배포 상태 점검
- [x] `daily_update.sh` 로 `build_horizon_views.py` 자동 반영 연결
- [x] `daily_update.sh` 로 `storage_retention.py` 자동 반영 연결
- [x] `11:00 KST` launch agent 로컬 설치 완료
- [ ] 작업 종료 시 `HANDOFF.md` 와 `TASKS.md` 갱신 자동 습관화

## 현재 작업 트리 체크

- [x] [`scripts/macro_analysis.py`](/Users/seo/igzun-daily-report/scripts/macro_analysis.py) 결과 검증
- [x] [`scripts/etf_recommender.py`](/Users/seo/igzun-daily-report/scripts/etf_recommender.py) 결과 검증
- [x] [`scripts/load_market_data.py`](/Users/seo/igzun-daily-report/scripts/load_market_data.py) 출력 검증
- [x] [`data/portfolio_state.json`](/Users/seo/igzun-daily-report/data/portfolio_state.json) 포맷 검증
- [x] [`site/template/index.html`](/Users/seo/igzun-daily-report/site/template/index.html) 새 UI 구조 반영
- [x] [`site/2026-03-30/result.json`](/Users/seo/igzun-daily-report/site/2026-03-30/result.json) 새 필드 검증
- [ ] 커밋 전 `git status --short` 재확인
