#!/usr/bin/env bash
set -euo pipefail
CRONFILE="/Users/seo/.openclaw/workspace/igzun-daily-report/cron/jobs.cron"
if [ ! -f "$CRONFILE" ]; then
  echo "Cron file not found: $CRONFILE" >&2
  exit 1
fi
crontab "$CRONFILE"
echo "Installed crontab from $CRONFILE"
