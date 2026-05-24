# Ralph Verify-and-Merge Loop — Sales RPG AI Phase 5

You are running inside an autonomous loop. Each iteration is a fresh context with this exact prompt + access to the repo at `~/Work/active/sales-rpg-ai`. **Mutable state lives in `IMPLEMENTATION_PLAN.md` and git.** Read it first, do the next smallest verifiable action, update it, commit, exit.

## ULTIMATE GOAL

Honestly verify Phase 5 of Sales RPG AI end-to-end, then merge `phase5/ralph-loop` → `main`. Phase 5 has 8 stories (S5-01 through S5-08) all marked `passes: true` in `prd.json` with commits, but **none have been live-verified and the branch has never been merged**. Optimistic pass marks are the enemy. Tool-verified evidence is the friend.

The headline deliverable is **S5-06 (Vexa integration)** — a self-hosted Apache 2.0 OSS notetaker that joins Zoom/Meet/Teams calls as a participant and streams transcripts into the coaching engine. Austin wants this working.

## Operating rules (Huntley discipline)

1. **One small verified action per iteration.** Don't try to fix multiple stories at once.
2. **No `passes: true` without tool-verified evidence.** Every `passes: true` in `prd.json` must reference a probe result captured this iteration or earlier.
3. **`[DEFERRED-VERIFY]` is honorable.** If a probe is genuinely impossible from this machine (e.g., no real Zoom meeting to test against), write `passes: deferred` and document the exact pre-flight steps Austin needs to run.
4. **Commit every checkpoint.** Each verification or fix is its own commit on `phase5/ralph-loop`. Push after each commit.
5. **No new features.** Scope is verify-existing + fix-actually-broken + document-deferred + merge.
6. **codex exec is the substrate.** This prompt is run by codex.
7. **NO Forge agent.** Austin opted out — use codex exec directly.
8. **Python stays Python.** Do not rewrite to TypeScript.

## Per-iteration procedure

1. **Read `IMPLEMENTATION_PLAN.md`** — find the first unchecked task. If empty/missing, populate it from the Verification Checklist below.
2. **Re-read `prd.json`** for ground truth on what each story claims.
3. **Pick exactly one task.** Smallest verifiable unit.
4. **Execute the probe** (run tests, curl an endpoint, inspect a file, stand up a container, etc.) and capture evidence.
5. **Record the result** in `IMPLEMENTATION_PLAN.md` under that task with: probe used, command, output excerpt, verdict (`passes` / `fails: <why>` / `deferred: <reason + pre-flight>`).
6. **If `fails`:** fix the root cause with minimal diff. Re-run the probe. Update the result.
7. **Update `prd.json`** with the honest verdict for that story (only flip `passes` based on this iteration's evidence).
8. **Commit + push.** Message format: `verify S5-NN: <verdict> — <one-line evidence>`.
9. **Exit.** Do not start a second task this iteration. The loop will restart.

## Verification Checklist (populate IMPLEMENTATION_PLAN.md from this if empty)

### Pre-flight
- [ ] Working tree clean (`git status -s` empty)
- [ ] `pytest` runs at all (deps installed, conftest loads)
- [ ] `make up` brings the Docker stack up (FastAPI :8080, WhisperLive :9090, LocalAI)
- [ ] FastAPI `/health` or root route returns 200

### Story-by-story verification (probe each)
- [ ] S5-01: `src/realtime/llm_provider.py` exists, `LLMConfig` is a dataclass, all 7 providers implement same interface, tests pass
- [ ] S5-02: Mic cutoff fix — flush() remainder bug fix present in `src/realtime/buffer_manager.py`; root cause documented in `specs/buffer_manager.md`; chunk-boundary test exists and passes
- [ ] S5-03: WebSocket reconnect — drop detected ≤5s, client re-sends history, server handles half-open; reconnect test exists and passes
- [ ] S5-04: Context engine Layer 2 — Hardly Selling methodology loaded as retrievable RAG layer; multi-source retrieval (script + methodology) works
- [ ] S5-05: Latency < 3s end-to-end — streaming display in UI; latency benchmark records p50/p95; fallback model on >5s timeout
- [ ] **S5-06 (HEADLINE): Vexa integration** — Vexa Lite docker stack up (`docker compose -f docker-compose.lite.yml up -d` in vexa repo); `curl http://localhost:8080/health` returns ok; bot can request to join a Zoom or Meet meeting; transcripts stream to Sales RPG over WebSocket; both sides of conversation captured. **If no real Zoom meeting available from this machine, mark deferred and document exact pre-flight: vexa repo clone, env vars, Zoom test-meeting URL Austin needs to provide.**
- [ ] S5-07: Security hardening — `docs/threat_model.md` exists and covers audio/keys/WS; no hardcoded secrets (`rg -i "sk-or-v1-|sk-proj-" src/` returns nothing); WS origin validation present; RAG integrity check on startup
- [ ] S5-08: Desktop overlay — overlay UI launches, renders on top of meeting window, draggable/resizable, hotkey toggles visibility

### Merge
- [ ] All verifications either `passes` or `deferred` (no `fails`)
- [ ] `prd.json` `passes` field is honest for every story
- [ ] `phase5/ralph-loop` rebased/merged cleanly onto latest `main`
- [ ] Merge commit message lists `verified: [S5-NN, ...]` and `deferred: [S5-NN — reason, ...]`
- [ ] `main` pushed

## What to write to IMPLEMENTATION_PLAN.md

```markdown
# Phase 5 Verify+Merge — Implementation Plan

## Status
- Iteration: NN
- Last action: <one line>
- Last commit: <sha + message>
- Next task: <pick one from below>

## Tasks
[copy the Verification Checklist above, update checkboxes as you go]

## Evidence Log
### S5-NN — <iteration date>
- Probe: <command or tool>
- Output: <quoted excerpt, ≤10 lines>
- Verdict: <passes | fails: reason | deferred: reason + pre-flight>
- Commit: <sha>
```

## Blockers that require pinging Austin

Stop the loop and write `BLOCKER.md` in repo root if you hit:
- Missing credential (OPENROUTER_API_KEY, Vexa API key, etc.) — Austin sets env vars
- Real Zoom/Meet meeting required for live test (S5-06) — Austin schedules
- Ambiguous spec (two stories contradict)
- Scope decision (e.g., a story is fundamentally broken and needs redesign, not fix)

Exit non-zero so the outer loop knows to halt.

## Exit conditions

- Normal: one task verified + committed → exit 0, outer loop restarts
- Done: every checkbox checked + merge complete → write `DONE.md` with summary, exit 0
- Blocker: write `BLOCKER.md`, exit 2

## References

- `prd.json` — Phase 5 story acceptance criteria (ground truth)
- `docs/vexa-setup.md` — Vexa self-host setup steps
- `docs/notetaker-research.md` — why Vexa over Zoom SDK / Recall.ai
- `specs/` — per-subsystem behavioral specs
- `AGENT.md` — project overview and stack
