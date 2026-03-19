# raw 기사/리포트 summary 생성 계획

목표: Reporting/input/raw 내 txt/html/pdf 원문에서 요약을 생성해 newsList[].summary에 넣음.

## 우선순위
1. txt 원문: 첫 문단/핵심 문장 추출 + 후속 LLM 요약
2. html 원문: 본문 정제 후 동일 처리
3. pdf 원문: OCR/텍스트 추출 후 동일 처리

## 현재 상태
- txt 원문은 즉시 규칙 기반 요약 가능
- LLM 요약은 후속 단계에서 chunk 기반으로 적용 필요
- 현재는 build_period_report.py / generate_date_reports.py에서 placeholder 또는 앞부분 축약 요약 사용 중
