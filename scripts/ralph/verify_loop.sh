#!/usr/bin/env bash
# Ralph Verify+Merge Loop — uses codex exec (per Austin's substrate preference)
# Usage: ./scripts/ralph/verify_loop.sh
# Stops when DONE.md or BLOCKER.md appears in repo root.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PROMPT_FILE="$PROJECT_ROOT/PROMPT_verify.md"
LOG_DIR="$PROJECT_ROOT/.ralph-runs/$(date +%Y%m%d-%H%M%S)"

mkdir -p "$LOG_DIR"
cd "$PROJECT_ROOT"

echo "━━━ Ralph Verify Loop ━━━"
echo "Project:  $PROJECT_ROOT"
echo "Prompt:   $PROMPT_FILE"
echo "Logs:     $LOG_DIR"
echo "Substrate: codex exec (gpt-5.5, danger-full-access)"
echo ""

ITER=0
while :; do
  ITER=$((ITER+1))
  TS=$(date '+%Y-%m-%d %H:%M:%S')
  ITER_LOG="$LOG_DIR/iter-$(printf '%03d' $ITER).log"

  echo ""
  echo "━━━ iteration $ITER @ $TS ━━━"

  # Stop conditions
  if [ -f "$PROJECT_ROOT/DONE.md" ]; then
    echo "DONE.md detected — verification + merge complete. Exiting."
    exit 0
  fi
  if [ -f "$PROJECT_ROOT/BLOCKER.md" ]; then
    echo "BLOCKER.md detected — human needed. Exiting."
    cat "$PROJECT_ROOT/BLOCKER.md"
    exit 2
  fi

  # Run codex exec with the static prompt + IMPLEMENTATION_PLAN.md context
  codex exec \
    --sandbox danger-full-access \
    --skip-git-repo-check \
    --cd "$PROJECT_ROOT" \
    -c model_reasoning_effort=high \
    "$(cat "$PROMPT_FILE")" 2>&1 | tee "$ITER_LOG"

  CODEX_RC=${PIPESTATUS[0]}
  echo "[iter $ITER] codex exit=$CODEX_RC" >> "$LOG_DIR/summary.log"

  # Push whatever the iteration committed
  git push 2>&1 | tail -3 || echo "(push failed or no remote — continuing)"

  # Short cooldown so we can ctrl-c cleanly
  sleep 2
done
