#!/usr/bin/env bash
set -euo pipefail
ROOT="/Users/seo/.openclaw/workspace/igzun-daily-report"
OCRVENV="$ROOT/.venv_ocr/bin"
PDFVENV="$ROOT/.venv_pdf/bin"
TODAY=$(date +%F)

mkdir -p "$ROOT/data/account_snapshot_inbox/incoming_images" "$ROOT/data/account_snapshot_inbox/ocr_text" "$ROOT/data/account_snapshot_inbox/processed" "$ROOT/data/account_snapshot_inbox/failed"

# 1) OCR images if any
if [ -x "$OCRVENV/python" ]; then
  "$OCRVENV/python" "$ROOT/scripts/ocr_account_images.py" || true
fi

# 2) Parse OCR text files into snapshot json
latest_txt=$(ls -1t "$ROOT/data/account_snapshot_inbox/ocr_text"/*.txt 2>/dev/null | head -1 || true)
if [ -n "${latest_txt:-}" ]; then
  python3 "$ROOT/scripts/parse_account_snapshot_text.py" "$latest_txt" || true
fi

# 3) Apply latest snapshot to today's result
python3 "$ROOT/scripts/update_portfolio_from_snapshot.py" || true

# 4) Record completion notice for eco_report_bot routing
cat > "$ROOT/data/eco_report_bot_outbox_latest.json" <<EOF
{
  "bot": "eco_report_bot",
  "date": "$TODAY",
  "message": "계좌 캡쳐 반영 파이프라인 실행 완료. 최신 snapshot 적용을 시도했음."
}
EOF

echo "admin_bot intake pipeline done: $TODAY"
