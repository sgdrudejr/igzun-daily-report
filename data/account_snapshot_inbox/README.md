# account snapshot inbox

## 역할
- 인입 bot: `admin_bot`
- 송출 bot: `eco_report_bot`

## 자동 인입 경로
admin_bot에서 받은 이미지 파일은 아래에 저장되면 자동 OCR 대상이 됨:
- `incoming_images/`

OCR 결과 텍스트:
- `ocr_text/`

처리 완료 이미지:
- `processed/`

실패 이미지:
- `failed/`

## 자동 파이프라인
- `scripts/ingest_admin_bot_pipeline.sh`
  1. 이미지 OCR
  2. OCR 텍스트 → snapshot JSON 변환
  3. snapshot → result.json 포트폴리오 반영
  4. eco_report_bot 송출용 outbox 파일 갱신

## 주의
현재는 Telegram 첨부 이미지가 이 폴더로 자동 저장되는 브리지까지는 미연결 상태임.
즉, 운영 측에서 이미지 저장 브리지 또는 수동 저장이 필요함.
