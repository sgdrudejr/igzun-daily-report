# 운영 노트

## bot 역할
- 인입: `admin_bot`
- 송출: `eco_report_bot`

## 오전 11시 일일 작업
- 로컬 cron: `cron/jobs.cron`
- 실행 스크립트: `scripts/daily_update.sh`

## 계좌 인입 흐름
1. admin_bot으로 캡쳐 수신
2. OCR 또는 수동 정리
3. `data/account_snapshot_inbox/YYYY-MM-DD_snapshot.json` 저장
4. `scripts/update_portfolio_from_snapshot.py` 실행
5. 결과는 당일 `site/YYYY-MM-DD/result.json` 포트폴리오 섹션에 반영

## 송출 흐름
- 최종 대시보드/리포트 전달 대상은 eco_report_bot
- 실제 Telegram 라우팅은 운영 연결 후 붙임
