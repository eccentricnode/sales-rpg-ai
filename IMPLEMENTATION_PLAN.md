# Phase 5 Verify+Merge — Implementation Plan

## Status
- Iteration: 0 (pre-launch)
- Last action: Plan initialized by orchestrator. Loop has not yet run.
- Last commit: (safety snapshot of dirty tree)
- Next task: Pre-flight — confirm `pytest` runs at all

## Tasks

### Pre-flight
- [ ] Working tree clean (`git status -s` empty)
- [ ] `pytest` runs at all (deps installed, conftest loads, collection succeeds)
- [ ] `make up` brings the Docker stack up (FastAPI :8080, WhisperLive :9090, LocalAI)
- [ ] FastAPI `/health` or root route returns 200

### Story verification
- [ ] S5-01: LLM provider interface
- [ ] S5-02: Mic cutoff fix
- [ ] S5-03: WebSocket reconnect
- [ ] S5-04: Context engine Layer 2 (Hardly Selling)
- [ ] S5-05: Latency < 3s + streaming
- [ ] **S5-06: Vexa integration (HEADLINE)**
- [ ] S5-07: Security hardening
- [ ] S5-08: Desktop overlay UI

### Merge
- [ ] All verifications either passes or deferred (no fails)
- [ ] `prd.json` honest
- [ ] `phase5/ralph-loop` → `main` merge clean
- [ ] Merge commit lists verified + deferred
- [ ] `main` pushed

## Evidence Log

(Iterations append here.)
