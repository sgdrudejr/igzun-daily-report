#!/usr/bin/env bash
set -euo pipefail

# deploy.sh - generates HTML+JSON report and either does a dry-run or real deploy
# Usage: ./deploy.sh [dry-run|real]

MODE=${1:-dry-run}
ROOT_DIR="/Users/seo/.openclaw/workspace/igzun-daily-report"
OUTPUT_DIR="$ROOT_DIR/output"
SITE_DIR="$ROOT_DIR/site"
TS_DATE=$(date +"%Y-%m-%d")
TS_FULL=$(date +"%Y-%m-%d-%H%M%S")
RUN_DIR="$OUTPUT_DIR/${MODE}run/$TS_FULL"
LOGFILE="$RUN_DIR/log.txt"
HTML_FILE="$RUN_DIR/result.html"
JSON_FILE="$RUN_DIR/result.json"

mkdir -p "$RUN_DIR"
mkdir -p "$SITE_DIR/$TS_DATE"
exec > >(tee -a "$LOGFILE") 2>&1

echo "Running deploy.sh mode=$MODE at $(date)"

# ---- Use provided template if exists at templates/report.html, else fallback sample ----
TEMPLATE="$ROOT_DIR/templates/report.html"

DATA_TITLE="오픈 클로 AI 리포트"

if [ -f "$TEMPLATE" ]; then
  echo "Using HTML template: $TEMPLATE"
  # Insert minimal metadata into JSON and copy template to HTML_FILE
  cat > "$JSON_FILE" <<EOF
{
  "title": "${DATA_TITLE}",
  "generated_at": "$(date --iso-8601=seconds 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ)",
  "path_date": "${TS_DATE}"
}
EOF
  cp "$TEMPLATE" "$HTML_FILE"
else
  echo "Template not found, writing simple placeholder HTML"
  cat > "$JSON_FILE" <<EOF
{
  "title": "${DATA_TITLE}",
  "generated_at": "$(date --iso-8601=seconds 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ)",
  "path_date": "${TS_DATE}" 
}
EOF
  cat > "$HTML_FILE" <<EOF
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>${DATA_TITLE}</title>
</head>
<body>
  <h1>${DATA_TITLE}</h1>
  <p>Generated at: $(date)</p>
  <p>Replace templates/report.html with your full design to render a richer report.</p>
  <pre>JSON: $(cat "$JSON_FILE")</pre>
</body>
</html>
EOF
fi

# Copy result into dated site folder
SITE_DAY_DIR="$SITE_DIR/$TS_DATE"
cp "$HTML_FILE" "$SITE_DAY_DIR/index.html"
cp "$JSON_FILE" "$SITE_DAY_DIR/result.json"

# Update root index.html to redirect to today's page (so Pages shows latest)
ROOT_INDEX="$ROOT_DIR/index.html"
cat > "$ROOT_INDEX" <<EOF
<!doctype html>
<html>
<head>
  <meta http-equiv="refresh" content="0; url=./site/${TS_DATE}/" />
  <meta charset="utf-8" />
  <title>${DATA_TITLE} - ${TS_DATE}</title>
</head>
<body>
  If you are not redirected, <a href="./site/${TS_DATE}/">open today's report</a>.
</body>
</html>
EOF

# Also write a simple archive listing (index) for site root and dates.json
ARCHIVE_INDEX="$SITE_DIR/index.html"
DATES_JSON="$SITE_DIR/dates.json"
cat > "$ARCHIVE_INDEX" <<EOF
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>igzun-daily-report archive</title>
</head>
<body>
  <h1>Archive</h1>
  <ul>
EOF

# collect dates sorted desc
DATES_LIST=""
for d in $(ls -1 "$SITE_DIR" | grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' | sort -r); do
  echo "  <li><a href=\"./${d}/\">${d}</a></li>" >> "$ARCHIVE_INDEX"
  DATES_LIST+="\"${d}\"," 
done

echo "</ul></body></html>" >> "$ARCHIVE_INDEX"

# write dates.json (array of dates)
DATES_LIST="[${DATES_LIST%,}]"
cat > "$DATES_JSON" <<EOF
${DATES_LIST}
EOF

echo "Wrote dates list to $DATES_JSON"


echo "Wrote: $HTML_FILE"
echo "Wrote: $JSON_FILE"
echo "Published to site folder: $SITE_DAY_DIR/index.html"

echo "Updated index at $ROOT_INDEX"

# Hooks: notification hook (no-op if not present)
HOOK="$ROOT_DIR/scripts/hooks/post_deploy.sh"
if [ -x "$HOOK" ]; then
  echo "Running post-deploy hook..."
  "$HOOK" "$MODE" "$RUN_DIR" || echo "post-deploy hook failed (non-fatal)"
else
  echo "No post-deploy hook found or not executable: $HOOK"
fi

# If real mode, commit and push index.html and site/ (site contains dated pages)
if [ "$MODE" = "real" ]; then
  echo "Preparing git commit and push..."
  cd "$ROOT_DIR"
  # ensure index.html and site are added; keep output/ ignored
  git add index.html site || echo "git add failed"
  MSG="chore(daily-report): update generated site [ci skip]"
  git commit -m "$MSG" || echo "git commit returned non-zero (maybe nothing to commit)"
  echo "Now pushing to remote..."
  git push origin main
  echo "Push finished"
fi

echo "Done"
