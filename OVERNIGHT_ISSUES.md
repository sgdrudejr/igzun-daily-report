# OVERNIGHT_ISSUES

## 비차단 이슈
### 1. LLM 심화문장 품질 한계
- 현상: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` 모두 미설정이라 [/Users/seo/igzun-daily-report/scripts/llm_insights.py](/Users/seo/igzun-daily-report/scripts/llm_insights.py) 는 규칙 기반 fallback으로 동작함
- 영향: 리포트 구조는 개선됐지만, 제미나이 딥리서치급 자유 서술 깊이는 아직 제한적임
- 현재 대응: `So What 3줄`, `현상 -> 이유 -> 포트폴리오 영향`, SPY/QQQ/GLD/TLT 중심 설명은 fallback에도 반영 완료

### 2. 일부 수집 경고
- 현상: 네이버/KB/신한 수집 중 `InsecureRequestWarning` 발생
- 영향: 현재는 경고 수준이며 배치를 막지는 않음
- 현재 대응: 수집은 계속 성공하며 결과물도 생성됨

### 3. 일부 증권사 원문 PDF 제약
- 현상: 일부 증권사 상세 본문/PDF는 로그인 또는 권한 제약이 있음
- 영향: 메타데이터, 리스트, 일부 상세 정보까지만 자동화 가능
- 현재 대응: 공개 범위 내에서 계속 수집, 막힌 경우는 fallback 설명과 다른 공개 소스로 보강
