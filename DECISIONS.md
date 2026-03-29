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

### 14. 여러 에이전트가 번갈아 작업하므로 문서화는 필수 작업이다

결정:

- 작업 후 반드시 [`HANDOFF.md`](/Users/seo/igzun-daily-report/HANDOFF.md) 와 [`TASKS.md`](/Users/seo/igzun-daily-report/TASKS.md) 를 업데이트한다.

이유:

- 현재 프로젝트는 다중 에이전트 협업 환경
- 문서 없이는 상태 인수인계가 끊김

## 현재 열려 있는 결정 보류 항목

- `build_site_report.py` 의 최종 result schema를 기존 site와 얼마나 맞출지
- HTML을 기존 템플릿 연장으로 갈지, 새 한국어 리포트 레이아웃으로 갈지
- 주간/월간/분기 보고서 파일 구조를 어디에 둘지
- 포트폴리오 제안 로직을 정적 규칙 기반으로 둘지, 추가 분석 레이어를 둘지

위 항목은 새 구조를 섣불리 만들지 말고, 기존 흐름을 유지하는 범위에서 결정해야 한다.
