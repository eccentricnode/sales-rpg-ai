#!/usr/bin/env bash
# Ralph Loop for Sales RPG AI
# Usage: ./scripts/ralph/loop.sh [plan|build|test]
#
# Modes:
#   plan  — Gap analysis only. No code changes. (PROMPT_plan.md)
#   test  — Write tests only. No implementation. Red Gate. (PROMPT_test.md)
#   build — Implement one story per loop. (PROMPT_build.md)

set -euo pipefail

MODE="${1:-build}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

case "$MODE" in
  plan)
    PROMPT_FILE="$SCRIPT_DIR/PROMPT_plan.md"
    ;;
  test)
    PROMPT_FILE="$SCRIPT_DIR/PROMPT_test.md"
    ;;
  build)
    PROMPT_FILE="$SCRIPT_DIR/PROMPT_build.md"
    ;;
  *)
    echo "Usage: $0 [plan|build|test]"
    exit 1
    ;;
esac

if [ ! -f "$PROMPT_FILE" ]; then
  echo "ERROR: $PROMPT_FILE not found"
  exit 1
fi

echo "━━━ Ralph Loop: $MODE mode ━━━"
echo "Prompt: $PROMPT_FILE"
echo "Project: $PROJECT_ROOT"
echo ""

cd "$PROJECT_ROOT"

while :; do
  echo ""
  echo "━━━ Ralph iteration starting ($MODE) ━━━"
  echo "$(date '+%Y-%m-%d %H:%M:%S')"
  echo ""

  cat "$PROMPT_FILE" | claude -p --dangerously-skip-permissions --model opus

  echo ""
  echo "━━━ Ralph iteration complete ━━━"
  echo "$(date '+%Y-%m-%d %H:%M:%S')"
  echo ""

  # Brief pause between iterations
  sleep 2
done
