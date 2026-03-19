#!/usr/bin/env bash
set -euo pipefail
ROOT="/Users/seo/.openclaw/workspace/igzun-daily-report"
VENV="$ROOT/.venv_pdf/bin"
TODAY=$(date +%F)

# 1) collect reports/news raw
/Users/seo/.openclaw/workspace/2_Project/Automation/jobs/run_collection.sh "$TODAY" reports || true

# 2) process PDFs / refine insights / integrate
"$VENV/python" "$ROOT/scripts/process_pdfs.py" || true
python3 "$ROOT/scripts/refine_insights.py" || true
python3 "$ROOT/scripts/integrate_refined_insights.py" || true

# 3) market data + quant
"$VENV/python" "$ROOT/scripts/load_market_data.py" || true
"$VENV/python" "$ROOT/scripts/apply_market_quant.py" || true

# 4) dated reports / statuses
python3 "$ROOT/scripts/generate_date_reports.py" || true
python3 "$ROOT/scripts/build_date_status.py" || true

# 5) portfolio snapshot apply if available
python3 "$ROOT/scripts/update_portfolio_from_snapshot.py" || true

echo "daily update done: $TODAY"
