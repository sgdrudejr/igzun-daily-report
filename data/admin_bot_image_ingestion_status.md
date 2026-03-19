# admin_bot image ingestion status

현재 상태:
- incoming_images 폴더 감시 구조 생성됨
- OCR 가상환경 생성됨 (.venv_ocr)
- pytesseract 설치됨
- tesseract 및 한글 언어팩 설치 중/또는 설치 후 사용 가능
- ingest_admin_bot_pipeline.sh가 OCR → snapshot JSON → result 반영 흐름을 실행함

남은 실제 연결점:
- Telegram admin_bot 첨부 이미지가 workspace `data/account_snapshot_inbox/incoming_images/`로 자동 저장되는 브리지
- 현재 이 브리지는 세션 도구상 미연결 상태이므로, 수동 저장 또는 별도 메시지 첨부 저장 훅 필요
