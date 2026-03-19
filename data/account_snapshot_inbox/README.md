# account snapshot inbox

admin_bot로 받은 보유 캡쳐본은 OCR 또는 수동 정리 후 이 폴더에 저장함.

권장 파일 형식
- `YYYY-MM-DD_snapshot.json` : account_snapshot_schema.json 준수
- `YYYY-MM-DD_snapshot.txt` : 캡쳐 OCR 텍스트 원문

운영 흐름
1. 캡쳐 수신
2. OCR 또는 수동 정리
3. JSON 저장
4. `scripts/update_portfolio_from_snapshot.py` 실행
