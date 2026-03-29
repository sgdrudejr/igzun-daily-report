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
- [x] 마지막 반영 커밋 확인: `43b4c84`

## 현재 진행 중

- [ ] 브라우저 기준 HTML 렌더링 최종 검증
- [ ] 포트폴리오 시사점 로직 정교화
- [ ] 포트폴리오 점수 산식 고도화
- [ ] ETF/테마 아이디어 설명 품질 개선

## 남은 작업

### 수집

- [ ] `kr_brokerage_kb` 셀렉터/페이지 구조 재검증
- [ ] `kr_brokerage_mirae` 404 대응 및 실제 리서치 URL 재확인
- [ ] 일본/유럽 리서치 소스 추가
- [ ] source health check 리포트 추가
- [ ] 3일 이상 무수집 source stale 경고 추가

### 분석

- [ ] 일간 데이터를 바탕으로 주간/월간/분기 집계 스크립트 추가
- [ ] 리포트에서 단기 뉴스와 중기 방향성 분리
- [ ] 펀더멘털/기술적 시그널 동시 반영 설명 강화
- [ ] 계좌별 현금/투입 가능 금액 반영

### 보고서

- [x] `build_site_report.py` 결과 스키마를 기존 프론트 호환형 `dataByPeriod` 구조로 맞춤
- [x] 레짐/핵심이슈/섹터/ETF/포트폴리오 블록 데이터 생성
- [ ] 모든 필드 한국어화
- [ ] 빈값 fallback 처리 일관화
- [ ] 주간/월간 보고서 섹션 설계

### 운영

- [ ] cron 시각 분리 운영 검증
- [ ] 실패 시 재시도/부분성공 로그 기준 정리
- [ ] GitHub Pages 자동 배포 상태 점검
- [ ] 작업 종료 시 `HANDOFF.md` 와 `TASKS.md` 갱신 자동 습관화

## 현재 작업 트리 체크

- [ ] [`scripts/build_site_report.py`](/Users/seo/igzun-daily-report/scripts/build_site_report.py) 검토 후 커밋 여부 결정
- [ ] [`scripts/macro_analysis.py`](/Users/seo/igzun-daily-report/scripts/macro_analysis.py) 결과 검증
- [ ] [`scripts/etf_recommender.py`](/Users/seo/igzun-daily-report/scripts/etf_recommender.py) 결과 검증
- [ ] [`scripts/load_market_data.py`](/Users/seo/igzun-daily-report/scripts/load_market_data.py) 출력 검증
- [ ] [`data/portfolio_state.json`](/Users/seo/igzun-daily-report/data/portfolio_state.json) 포맷 검증
