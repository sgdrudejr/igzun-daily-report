#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/seo/igzun-daily-report"
SOURCE_SKILL="$ROOT/skills/llmsummary/SKILL.md"

CODEX_SKILL_DIR="/Users/seo/.codex/skills/llmsummary"
mkdir -p "$CODEX_SKILL_DIR"
cp "$SOURCE_SKILL" "$CODEX_SKILL_DIR/SKILL.md"

CLAUDE_BASE="/Users/seo/Library/Application Support/Claude/local-agent-mode-sessions/skills-plugin"
CLAUDE_TARGET=""

while IFS= read -r dir; do
  CLAUDE_TARGET="$dir/llmsummary"
done < <(find "$CLAUDE_BASE" -type d -path "*/skills" 2>/dev/null | sort)

if [[ -n "$CLAUDE_TARGET" ]]; then
  mkdir -p "$CLAUDE_TARGET"
  cp "$SOURCE_SKILL" "$CLAUDE_TARGET/SKILL.md"
  echo "installed Claude skill: $CLAUDE_TARGET/SKILL.md"
else
  echo "Claude skills directory not found; skipped Claude install"
fi

echo "installed Codex skill: $CODEX_SKILL_DIR/SKILL.md"
