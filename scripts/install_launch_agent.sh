#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLIST_SRC="$ROOT/cron/com.seo.igzun-daily-report.daily.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.seo.igzun-daily-report.daily.plist"
LABEL="com.seo.igzun-daily-report.daily"
GUI_DOMAIN="gui/$(id -u)"

mkdir -p "$HOME/Library/LaunchAgents" "$ROOT/output"
cp "$PLIST_SRC" "$PLIST_DST"

launchctl bootout "$GUI_DOMAIN" "$PLIST_DST" 2>/dev/null || true
launchctl bootstrap "$GUI_DOMAIN" "$PLIST_DST"
launchctl enable "$GUI_DOMAIN/$LABEL"

echo "Installed launch agent: $LABEL"
echo "Plist: $PLIST_DST"
