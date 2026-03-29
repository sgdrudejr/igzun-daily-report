#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CRONFILE="$ROOT/cron/jobs.cron"

mkdir -p "$ROOT/output"

if [ ! -f "$CRONFILE" ]; then
  echo "Cron file not found: $CRONFILE" >&2
  exit 1
fi

crontab "$CRONFILE"
echo "Installed crontab from $CRONFILE"
