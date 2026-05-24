#!/usr/bin/env bash
# Ralph Verify+Merge Loop — codex exec substrate.
# Usage: ./scripts/ralph/verify_loop.sh [plan|build]
#   plan  — one shot, runs PROMPT_plan_verify.md (generates IMPLEMENTATION_PLAN.md)
#   build — loops, runs PROMPT_build_verify.md until DONE.md or BLOCKER.md

set -uo pipefail

MODE="${1:-build}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

case "$MODE" in
  plan)  PROMPT_FILE="$PROJECT_ROOT/PROMPT_plan_verify.md" ;;
  build) PROMPT_FILE="$PROJECT_ROOT/PROMPT_build_verify.md" ;;
  *) echo "Usage: $0 [plan|build]"; exit 1 ;;
esac

LOG_DIR="$PROJECT_ROOT/.ralph-runs/$(date +%Y%m%d-%H%M%S)-$MODE"
mkdir -p "$LOG_DIR"
cd "$PROJECT_ROOT"

echo "━━━ Ralph $MODE loop ━━━"
echo "Project:   $PROJECT_ROOT"
echo "Prompt:    $PROMPT_FILE"
echo "Logs:      $LOG_DIR"
echo "Substrate: codex exec (gpt-5.5, danger-full-access)"

run_codex() {
  local iter_log="$1"
  codex exec \
    --sandbox danger-full-access \
    --skip-git-repo-check \
    --cd "$PROJECT_ROOT" \
    -c model_reasoning_effort=high \
    "$(cat "$PROMPT_FILE")" 2>&1 | tee "$iter_log"
}

if [ "$MODE" = "plan" ]; then
  run_codex "$LOG_DIR/plan.log"
  echo "[plan] codex exit=${PIPESTATUS[0]}"
  git push 2>&1 | tail -3 || true
  exit 0
fi

ITER=0
while :; do
  ITER=$((ITER+1))
  echo ""
  echo "━━━ build iter $ITER @ $(date '+%Y-%m-%d %H:%M:%S') ━━━"

  if [ -f "$PROJECT_ROOT/DONE.md" ]; then
    echo "DONE.md detected — exiting."
    exit 0
  fi
  if [ -f "$PROJECT_ROOT/BLOCKER.md" ]; then
    echo "BLOCKER.md detected — exiting."
    cat "$PROJECT_ROOT/BLOCKER.md"
    exit 2
  fi

  run_codex "$LOG_DIR/iter-$(printf '%03d' $ITER).log"
  echo "[iter $ITER] codex exit=${PIPESTATUS[0]}" >> "$LOG_DIR/summary.log"
  git push 2>&1 | tail -3 || true
  sleep 2
done
