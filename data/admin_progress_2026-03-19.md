# admin progress 2026-03-19

- quiet-dune 수집 작업 종료 확인함 (exit code 0)
- 2026-02-19 ~ 2026-03-19 raw 인벤토리 생성함
- raw 존재 날짜들에 대해 site/YYYY-MM-DD/index.html, result.json 생성함
- HTML에 출처보기(증권사/제목/날짜만 표시) 반영함
- 주요 이슈 제목/칩 한국어화 반영함
- period 확장: 1일, 3일, 1주, 1개월, 3개월, 6개월
- scoring_engine.py 추가함
- summarize_raws.py 추가함
- 다음 단계: scoring_engine.py를 build_period_report.py와 generate_date_reports.py에 더 깊게 연결하고, raw summary를 newsList.summary에 교체함
