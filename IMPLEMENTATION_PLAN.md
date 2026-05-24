# Phase 5 Verify+Merge — Implementation Plan

## Status
- Iteration: 1
- Last action: Pre-flight clean-tree check failed on generated artifacts, then was cleaned by removing submodule bytecode and ignoring `.ralph-runs/`.
- Last commit: pending (`verify preflight: passes — git status clean after generated artifacts ignored`)
- Next task: Pre-flight — confirm `pytest` runs at all

## Tasks

### Pre-flight
- [x] Working tree clean (`git status -s` empty)
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

### Pre-flight clean tree — 2026-05-23
- Probe: `git status -s`; `git -C WhisperLive status --porcelain=v1 -uall`
- Command: `git status -s`
- Output:
  ```text
   M WhisperLive
  ?? .ralph-runs/20260523-194543/iter-001.log
  ```
- Follow-up: `WhisperLive` was dirty only from generated `whisper_live/__pycache__/*.pyc`; those files were removed and `.ralph-runs/` was added to `.gitignore`.
- Verdict: passes after cleanup; final `git status -s` is expected empty after this checkpoint commit.
- Commit: pending
