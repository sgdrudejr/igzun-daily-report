# Shared Memory / 공유 상태

공통 읽기/쓰기 파일
- 전역 상태: `/Users/seo/.openclaw/workspace/global_state.json`
- 최신 계좌 스냅샷: `/Users/seo/.openclaw/workspace/igzun-daily-report/data/account_snapshot_latest.json`
- 최신 대시보드 결과: `/Users/seo/.openclaw/workspace/igzun-daily-report/site/YYYY-MM-DD/result.json`

운영 원칙
1. admin_bot이 새 계좌/OCR 데이터를 만들면 `account_snapshot_latest.json`을 갱신함
2. 메인 세션/리포트 파이프라인은 작업 시작 시 `global_state.json`을 먼저 읽음
3. eco_report_bot은 송출 전 `global_state.json.latest_dashboard_status`를 참조함

현재 구현됨
- `parse_account_snapshot_text.py`가 latest snapshot과 global_state를 같이 갱신함
- `update_portfolio_from_snapshot.py`가 latest snapshot을 우선 사용하고 dashboard status를 갱신함
