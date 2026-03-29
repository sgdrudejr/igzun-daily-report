#!/usr/bin/env bash
set -euo pipefail
ROOT="/Users/seo/igzun-daily-report"
VENV="$ROOT/.venv/bin"
export TZ="Asia/Seoul"
TODAY=$(TZ=Asia/Seoul date +%F)

mkdir -p "$ROOT/output"

# 0) 자동 수집 파이프라인 (collectors)
"$VENV/python" -m collectors.runner --date "$TODAY" --base-dir "$ROOT" || true
"$VENV/python" -m collectors.bridge --date "$TODAY" --base-dir "$ROOT" || true

# 1) collect reports/news raw (legacy)
# /Users/seo/.openclaw/workspace/2_Project/Automation/jobs/run_collection.sh "$TODAY" reports || true

# 2) process PDFs / refine insights / integrate
"$VENV/python" "$ROOT/scripts/process_pdfs.py" || true
"$VENV/python" "$ROOT/scripts/refine_insights.py" || true
"$VENV/python" "$ROOT/scripts/integrate_refined_insights.py" || true

# 3) market data + quant
"$VENV/python" "$ROOT/scripts/load_market_data.py" || true
"$VENV/python" "$ROOT/scripts/apply_market_quant.py" || true

# 3b) multi-period macro analysis + ETF recommendations
"$VENV/python" "$ROOT/scripts/macro_analysis.py" --date "$TODAY" --base-dir "$ROOT" || true
"$VENV/python" "$ROOT/scripts/etf_recommender.py" --date "$TODAY" --base-dir "$ROOT" || true

# 4) site report 생성 (result.json + date_status.json)
"$VENV/python" "$ROOT/scripts/build_site_report.py" --date "$TODAY" --base-dir "$ROOT" || true
"$VENV/python" "$ROOT/scripts/storage_retention.py" --base-dir "$ROOT" --today "$TODAY" --delete-originals || true
"$VENV/python" "$ROOT/scripts/build_horizon_views.py" --base-dir "$ROOT" || true

# 5) admin_bot image intake -> OCR -> snapshot -> portfolio apply
bash "$ROOT/scripts/ingest_admin_bot_pipeline.sh" || true
"$VENV/python" "$ROOT/scripts/update_portfolio_from_snapshot.py" || true

# 6) GitHub Pages 자동 배포
cd "$ROOT"
if git diff --quiet && git diff --cached --quiet; then
    echo "no changes to commit for $TODAY"
else
    git add data/macro_analysis/ data/etf_recommendations/ data/manifests/ \
            data/normalized/ data/market_data_latest.json data/market_quant_snapshot.json \
            data/archive_summaries/ data/backfills/ data/storage_retention/ \
            site/ || true
    git commit -m "daily: $TODAY" || true
    git push || true
fi

echo "daily update done: $TODAY"
