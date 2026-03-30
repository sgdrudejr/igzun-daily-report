# DECISIONS

## 핵심 설계 결정

### 1. 수집 대상 정의는 코드가 아니라 registry로 관리한다

결정:

- source 정의는 [`collectors/registry/sources.yaml`](/Users/seo/igzun-daily-report/collectors/registry/sources.yaml) 에 모은다.

이유:

- 소스 추가/비활성화/우선순위 변경을 코드 수정 없이 처리하기 위함
- 여러 에이전트가 동시에 작업해도 변경 지점이 명확함
- cron 대상 분리와 source inventory 관리가 쉬움

### 2. 수집 진입점은 `collectors/runner.py` 하나로 고정한다

결정:

- 별도 수집 메인 스크립트를 만들지 않는다.

이유:

- 실행 경로가 하나여야 운영과 디버깅이 단순함
- `tier`, `source`, `dry-run` 옵션만으로 대부분의 운영 요구를 커버 가능

### 3. 저장 구조는 `raw -> normalized -> manifest -> bridge` 로 유지한다

결정:

- 저장 단계를 분리한다.

이유:

- raw는 재현성과 디버깅
- normalized는 downstream 공통 입력
- manifest는 운영 로그
- bridge는 기존 파이프라인 하위 호환 유지

### 4. dedup은 `content_hash` 기준 전역 중복 제거를 사용한다

결정:

- [`collectors/dedup.py`](/Users/seo/igzun-daily-report/collectors/dedup.py) 에서 `content_hash` 기반 전역 dedup 사용

이유:

- RSS/뉴스/리포트 메타가 여러 source에서 중복 등장할 수 있음
- 초기 단계에서는 단순하고 강한 dedup이 운영에 유리함

주의:

- 너무 공격적인 dedup일 수 있으므로 향후 source-aware dedup이 필요할 수 있음
- 하지만 현재 구조는 바꾸지 말고 확장 방식으로 가야 함

### 5. source URL과 fetched URL은 반드시 남긴다

결정:

- 문서 메타와 manifest 둘 다에 source 관련 URL을 남긴다.

이유:

- 사용자가 “어디서 수집했는지 로그가 필요하다”고 명시함
- 출처 검증, 재수집, 디버깅, 저작권/접근 정책 확인에 필요함

추가 운영 원칙:

- source 정의와 별개로, 원문 확보 경로는 [`collectors/registry/download_routes.yaml`](/Users/seo/igzun-daily-report/collectors/registry/download_routes.yaml) 에 정리한다.
- 이 파일에는 discovery URL, detail page pattern, PDF selector, artifact 저장 경로, 소스별 TODO를 기록한다.

### 6. 주요 IB 리포트는 당장 직접 수집 대상으로 두지 않는다

결정:

- Goldman Sachs, JP Morgan 등 기관 전용 리포트는 Tier 3 또는 문서화 대상

이유:

- 실제 접근 제한이 강함
- Phase 1의 목표는 자동 수집 가능한 구조 구축
- 대신 정책기관, 거시 API, 공개 리서치 메타, 공시, RSS를 우선 수집

### 7. 저작권 이슈가 있는 증권사 PDF는 메타데이터 우선 수집한다

결정:

- 네이버 금융 리서치 등은 PDF 본문 자동다운로드보다 메타데이터와 링크 중심

이유:

- 저작권/이용약관 이슈를 최소화
- source inventory 확보만으로도 후속 판단에 도움

추가 보정:

- 다만 공개 상세 본문이 있는 경우에는 HTML 본문을 실제로 수집한다.
- 공개 PDF 링크가 직접 노출되는 소스는 원문 PDF와 추출 텍스트를 같이 저장한다.
- 즉 "무조건 메타데이터만"이 아니라 "공개 접근 가능한 범위에서는 원문 확보"로 방향을 수정했다.

### 8. 기존 `refine_insights.py` 호환을 최우선으로 둔다

결정:

- bridge 출력 포맷은 기존 `refined_insights_inventory.json` 스키마를 유지한다.

이유:

- 기존 분석 파이프라인을 깨지 않고 collectors 레이어를 추가하기 위함
- 구조 변경보다 점진적 확장이 현재 프로젝트에 안전함

### 9. 분석과 보고서는 “단순 요약”이 아니라 투자 의사결정 지원을 목표로 한다

결정:

- 최종 리포트는 기사 나열형이 아니라 레짐/리스크/섹터/포트폴리오/ETF 아이디어 중심이어야 한다.

이유:

- 사용자 목표가 명확함: 3~6개월 관점의 보유/축소/보류 판단
- 일간 뉴스 소비가 아니라 누적된 시장 감각과 포트폴리오 의사결정 보조가 목적

### 10. 한국어 리포트를 기본으로 한다

결정:

- 최종 보고서/설명/인사이트는 한국어가 기본

이유:

- 사용자 요구 사항
- ETF 티커, 지수 코드 등 필요한 경우에만 영어 유지

### 11. `undefined` 같은 출력은 허용하지 않는다

결정:

- 리포트 렌더링 단계에서 fallback을 강제한다.

이유:

- 최종 산출물 품질 요구
- 보고서가 사용자-facing 결과물이기 때문

현재 상태:

- [`scripts/build_site_report.py`](/Users/seo/igzun-daily-report/scripts/build_site_report.py) 에 fallback 유틸을 넣고 `result.json` 기준 검증까지 완료함

### 12. 프론트 구조는 유지하고 내용만 투자 판단 중심으로 바꾼다

결정:

- 기존 사이트가 기대하는 `dataByPeriod -> briefing/newsList/portfolio/recommendations` 구조는 유지한다.
- 대신 각 구간의 내용은 단순 기사 나열이 아니라 레짐 판단, 핵심 리스크, 섹터 영향, 포트폴리오 시사점, ETF 아이디어 중심으로 구성한다.

이유:

- 기존 HTML/JS를 최소 수정으로 재사용할 수 있다.
- 구조를 깨지 않으면서 보고서 의미를 투자 판단 중심으로 올릴 수 있다.

### 13. 포트폴리오는 수익률이 아니라 레짐 적합도로 점수화한다

결정:

- 현재 포트폴리오 점수는 손익률이 아니라 `레짐 적합도 + 분산도 + 현금 운용 상태`를 합쳐 계산한다.

이유:

- 사용자의 현재 상태는 전액 현금일 수 있고, 이는 손실이 아니라 대기 포지션이다.
- 지금 필요한 것은 "잘 벌었는가" 보다 "현재 레짐에 맞는 배치인가"를 판단하는 점수다.
- 따라서 점수는 리스크 관리와 배분 적합도를 보여주는 용도로 사용한다.

### 14. 기간 선택 UI는 상단 선택 칩이 아니라 별도 방향성 탭으로 간다

결정:

- 기본 화면은 최신 일간 리포트로 고정한다.
- `1일/1주/1개월/3개월/6개월` 상단 선택 칩은 제거한다.
- 대신 `기간별 투자 방향성` 탭에서 일간/주간/월간/분기/반기 버킷을 한 번에 비교한다.

이유:

- 사용자는 1일/1주/1개월/3개월/6개월마다 보는 질문이 다르다.
- 하지만 상단 선택 칩은 공간을 많이 쓰고, 매번 전체 리포트를 갈아끼우는 방식이 복잡하게 느껴질 수 있다.
- 최신 일간 리포트를 기본으로 유지하면서, horizon 비교는 별도 탭에서 모아 보여주는 편이 더 단순하고 목적 중심이다.

### 15. 여러 에이전트가 번갈아 작업하므로 문서화는 필수 작업이다

결정:

- 작업 후 반드시 [`HANDOFF.md`](/Users/seo/igzun-daily-report/HANDOFF.md) 와 [`TASKS.md`](/Users/seo/igzun-daily-report/TASKS.md) 를 업데이트한다.

이유:

- 현재 프로젝트는 다중 에이전트 협업 환경
- 문서 없이는 상태 인수인계가 끊김

### 16. 주간/월간/분기/반기 뷰는 별도 JSON 파일로 누적 생성한다

결정:

- 일간 `site/{date}/result.json` 은 원본 결과로 유지한다.
- 주간/월간/분기/반기 뷰는 [`scripts/build_horizon_views.py`](/Users/seo/igzun-daily-report/scripts/build_horizon_views.py) 가 별도 `site/horizons/*` JSON 으로 생성한다.

이유:

- 기존 `dataByPeriod` 구조를 깨지 않고도 기간별 집계 레이어를 추가할 수 있다.
- UI는 `site/horizon_index.json` 만 읽어도 기간 선택 탭을 구성할 수 있다.
- 추후 horizon별 지표 차별화 로직을 넣어도 일간 결과와 분리해서 진화시킬 수 있다.

### 17. 같은 포트폴리오도 기간마다 다른 질문으로 해석한다

결정:

- 동일한 현재 자산배분이라도 1일/1주/1개월/3개월/6개월에서 다른 판단 문장과 실행 가이드를 만든다.

이유:

- 사용자는 "1일로 보면 매수, 6개월로 보면 비중 조절" 같은 복수 해석이 가능해야 한다고 명시했다.

### 18. LLM은 당일 데이터만이 아니라 누적 로컬 데이터를 함께 읽어야 한다

결정:

- [`scripts/build_research_context.py`](/Users/seo/igzun-daily-report/scripts/build_research_context.py) 를 두고,
  `llm_insights.py` 는 `data/research_context/{date}.json` 을 함께 읽어 딥리서치형 상위 문맥을 사용한다.

이유:

- 사용자 목표는 단순 뉴스 요약이 아니라 "지금까지 쌓인 데이터 위에서 더 강한 인사이트" 이다.
- 당일 문서만 보면 브로커/중앙은행/공시의 누적 변화, 최근 7일과 30일의 주제 반복, 과거 판단 변화가 반영되지 않는다.
- 로컬에 이미 쌓인 horizon 집계, archive summary, normalized docs, portfolio state를 재활용하면 LLM 품질을 크게 올릴 수 있다.
- 그래서 포트폴리오 탭은 상태 해석, 실행 가이드는 매수/보류/비중조절 액션으로 분리했다.
- 기간마다 `question`, `deploy_ratio`, `action_label` 을 다르게 두는 편이 목적에 맞다.

### 18. 탭 스크롤은 섹션별로 분리한다

결정:

- 전역 window scroll 이 아니라 각 섹션 탭을 독립 pane scroll 로 운영한다.

이유:

- 사용자는 시장 브리핑에서 내린 스크롤 위치가 핵심 이슈 탭에 그대로 이어지는 현재 동작을 문제로 지적했다.
- 탭별 개별 scroll pane 이 가장 단순하고 안정적인 해결책이다.

### 19. 상단 컨트롤은 2행보다 1행 압축을 우선한다

결정:

- `기간 유형 칩 + 기간 선택 드롭다운` 조합으로 상단 컨트롤을 1행에 압축한다.

이유:

- 모바일에서 2행 헤더는 본문 가시 영역을 줄인다.
- 기간 선택은 option 이 많아질 수 있어 드롭다운이 칩열보다 공간 효율이 좋다.

### 20. 점수와 핵심 지표는 텍스트보다 칩 우선으로 노출한다

결정:

- 총점, 매크로/기술/퀀트/FX 점수와 VIX, RSI, DXY 같은 핵심 지표는 칩으로 먼저 보여준다.

이유:

- 모바일에서 긴 설명문 앞에 숫자 핵심을 빠르게 파악할 수 있다.
- 기간별로 어떤 지표가 강조되는지 한눈에 구분할 수 있다.

### 21. 포트폴리오 가이드는 "비중"만이 아니라 "금액 + 속도"를 함께 제시한다

결정:

- 포트폴리오 탭에는 `capitalPlan`, `targetAmounts`, `accountPlans` 를 넣는다.
- 실행 가이드 탭에는 `todayAmount`, `splitPlan`, `addRule`, `pauseRule`, `reviewRule` 를 넣는다.

이유:

- 사용자는 "얼마를 어디에 투자해야 하는지"와 "매수를 어떤 방식으로 해야 하는지"를 구체적으로 원했다.
- 단순 비중 제안만으로는 실제 집행 단계에서 도움이 부족하다.
- 같은 자산이라도 1일/1주/1개월/3개월/6개월마다 집행 속도가 달라야 하므로 금액과 속도를 함께 보여줘야 한다.

### 22. 핵심 이슈 카드는 요약에서 끝나지 않고 포트폴리오 시사점까지 연결한다

결정:

- `newsList` 의 각 카드에 `portfolioImplication`, `executionGuide` 를 추가한다.

이유:

- 사용자는 예시 HTML처럼 더 인사이트풀한 카드 구조를 원했다.
- 기사 핵심 내용만 요약하면 투자 판단으로 이어지지 않는다.
- 그래서 `기사 핵심 내용 -> 핵심 내용 정리 -> 투자 시사점 -> 실행 메모` 흐름으로 바꾸었다.

### 23. ETF 아이디어는 랭킹보다 설명이 더 중요하므로 매크로 문맥과 비중 상한을 같이 준다

결정:

- ETF 아이디어 카드에 `macroContext`, `evidencePoints`, `positioning`, `watchPoint` 를 추가한다.

이유:

- 사용자는 "왜 사야 하는지, 무엇을 우려해야 하는지, RSI와 금리/정책을 어떻게 함께 읽어야 하는지"를 원했다.
- 점수 랭킹만으로는 실제 매수 판단을 하기 어렵다.
- 코어 ETF와 위성 ETF는 역할과 허용 비중이 다르므로, 포지션 상한을 설명으로 남기는 편이 실전적이다.

### 24. 수집 대상은 링크 요약이 아니라 원문 확보를 우선한다

결정:

- 링크 제목과 짧은 메타 텍스트만 저장하는 방식은 지양한다.
- HTML 상세 본문이 있으면 본문을 끌어오고, PDF 링크가 있으면 실제 파일과 텍스트를 저장한다.

이유:

- 사용자는 "링크에 있는 글자 몇 개"가 아니라 실제 리포트를 다운로드해서 분석하길 원한다.
- downstream 분석이 제대로 되려면 `RawDocument.content` 자체가 원문 수준으로 충분히 길어야 한다.
- 따라서 `collectors/document_enricher.py` 를 runner에 붙여 수집 직후 원문 보강을 수행하게 했다.

- 사용자는 숫자 가독성과 시인성을 원했다.
- 모바일에서는 짧은 수치 요약을 칩으로 먼저 보여주고, 설명은 본문에서 풀어주는 편이 더 읽기 쉽다.

### 21. historical backfill은 current snapshot source와 분리해 취급한다

결정:

- 과거 날짜 재생성은 [`scripts/backfill_history.py`](/Users/seo/igzun-daily-report/scripts/backfill_history.py) 로 수행하되, 기본 수집 source는 `fred_api`, `opendart` 같은 historical-safe source로 제한한다.

이유:

- RSS/스크래퍼/ECOS 일부는 현재 시점 snapshot 성격이 강해 과거를 그대로 재현했다고 보기 어렵다.
- 과거 데이터를 채운다는 이유로 snapshot source까지 섞으면 리포트 신뢰도가 떨어진다.
- 따라서 “무엇을 백필했고 무엇을 건너뛰었는지”를 `data/backfills/*.json` 에 명시적으로 남기는 쪽이 안전하다.

### 22. 과거 시점 계산은 as-of 기준으로 자른다

결정:

- [`scripts/load_market_data.py`](/Users/seo/igzun-daily-report/scripts/load_market_data.py) 는 `--start-date`, `--end-date`, `--output` 을 지원한다.
- [`scripts/macro_analysis.py`](/Users/seo/igzun-daily-report/scripts/macro_analysis.py) 와 [`scripts/etf_recommender.py`](/Users/seo/igzun-daily-report/scripts/etf_recommender.py) 는 특정 날짜 기준으로 history를 자른 뒤 계산한다.

이유:

- 단순히 오늘 기준 데이터를 가지고 과거 날짜 파일만 만드는 것은 백필이 아니라 위장된 최신값 복사다.
- 1월/2월/3월 보고서가 각각 그 시점의 시장 레짐과 ETF 모멘텀을 반영하려면 as-of slicing 이 필수다.

### 23. 저장공간 정리는 archive + summary 이중 구조로 간다

결정:

- 오래된 `raw/normalized/manifests` 는 [`scripts/storage_retention.py`](/Users/seo/igzun-daily-report/scripts/storage_retention.py) 로 summary JSON 과 archive 파일로 넘긴다.
- 단, 원문을 지우기 전에 `compact_raw`, `compact_normalized`, `chunks` 를 먼저 생성해 나중에 용량을 적게 쓰면서도 재분석 가능하도록 한다.
- archive 파일은 로컬 보관용으로 두고 `.gitignore` 처리한다.
- Git 에는 `data/archive_summaries/`, `data/storage_retention/status.json` 같은 작은 메타만 올린다.

이유:

- Mac mini 저장공간 문제를 해결하려면 원문 그대로 영구 보관하는 방식은 맞지 않다.
- 하지만 완전 삭제만 하면 출처/메타/카운트/예시가 사라져 운영 추적성이 떨어진다.
- summary + archive 구조면 웹과 Git 에는 가벼운 메타만 남기고, 필요 시 로컬 archive로 복원할 수 있다.

## 현재 열려 있는 결정 보류 항목

- `build_site_report.py` 의 최종 result schema를 기존 site와 얼마나 맞출지
- HTML을 기존 템플릿 연장으로 갈지, 새 한국어 리포트 레이아웃으로 갈지
- 주간/월간/분기 보고서 파일 구조를 어디에 둘지
- 포트폴리오 제안 로직을 정적 규칙 기반으로 둘지, 추가 분석 레이어를 둘지

위 항목은 새 구조를 섣불리 만들지 말고, 기존 흐름을 유지하는 범위에서 결정해야 한다.
