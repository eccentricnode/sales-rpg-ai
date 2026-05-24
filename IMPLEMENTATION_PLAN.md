# Phase 5 Verification And Merge Plan

- **Ground truth from this planning pass**
  - Branch is `phase5/ralph-loop`; `IMPLEMENTATION_PLAN.md` was absent before this pass.
  - `src/lib` does not exist. Treat `src/realtime`, `src/rag`, `src/integrations`, and `src/web` as the shared implementation layer for Phase 5 work.
  - Existing `prd.json` marks S5-01..S5-08 as `passes: true`, but that is not honest until each story has current tool-verified evidence or a documented `[DEFERRED-VERIFY]` state.
  - Local probe: `pytest -q tests/test_s5_acceptance.py` => **1 failed, 22 passed**. Failure is S5-02 `test_partial_chunks_no_dropped_segments`: synthetic 500ms speech split into 100ms chunks produced zero segments.
  - Local probe: `pytest -q tests/test_behavioral.py` => **44 passed**.
  - Local probe: `pytest -q tests/test_latency_benchmark.py` => **3 passed**.
  - Local probe: Vexa bridge translation into `DualBufferManager` works for a synthetic `TranscriptEvent`, but this is not evidence of Zoom/Meet capture.
  - Local probe: `websockets.__version__` is `10.4`; `VexaClient.connect()` fails with `BaseEventLoop.create_connection() got an unexpected keyword argument 'additional_headers'`.
  - Local probe: no Vexa container/service is reachable at `127.0.0.1:8080`.
  - Local search: `verify_knowledge_base()` exists but is not called from app startup.
  - Added missing behavioral specs: `specs/05-vad_transcriber.md`, `specs/06-websocket_reconnection.md`, `specs/07-context_engine_layer2.md`, `specs/08-latency_optimization.md`, `specs/09-vexa_integration.md`, `specs/10-security_hardening.md`, `specs/11-overlay_widget.md`.

- **P0: Make `prd.json` honest before any merge**
  - Change any Phase 5 story without current probe evidence away from `passes: true`.
  - At minimum, set S5-02 to false because an acceptance probe fails.
  - Mark S5-06 and S5-08 `[DEFERRED-VERIFY]` unless a real Vexa/desktop meeting probe is completed from this machine.
  - Do not merge `phase5/ralph-loop` into `main` while optimistic `passes: true` remains unsupported.

- **P1: Fix or reclassify S5-02 mic cutoff**
  - Current status: failing.
  - First determine whether the failure is true chunk-boundary sample loss or Silero rejecting the sine-wave fixture.
  - Required probes:
    - `pytest -q tests/test_s5_acceptance.py::TestS5_02_MicCutoff::test_partial_chunks_no_dropped_segments -vv`
    - Add/use a mocked VAD + mocked Whisper continuity probe proving split speech across non-aligned chunks emits a completed segment.
    - Re-run `pytest -q tests/test_s5_acceptance.py tests/test_behavioral.py`.
  - Completion evidence must reference `specs/05-vad_transcriber.md` and `specs/buffer_manager.md`.

- **P2: Bring S5-06 Vexa integration to honest state**
  - Current status: partial code/docs only, not live verified.
  - Confirm and fix the local `websockets` API mismatch before any Vexa connection probe.
  - Confirm whether a FastAPI route and web UI control should exist; docs currently claim a "Join Meeting" button, but `src/web` has no matching implementation.
  - Required machine probes:
    - `rg -n "vexa|join|meeting" src/web src/web/templates src/integrations`
    - `curl -fsS http://127.0.0.1:8080/health` against a running Vexa deployment.
    - Vexa bot creation or attachment probe returning a meeting/session id.
    - Transcript stream probe showing Vexa events reach `DualBufferManager` and coaching flow.
  - `[DEFERRED-VERIFY]` human pre-flight if no live Vexa/meeting is available:
    - Start Vexa Lite with Docker and confirm the API/WebSocket endpoint is reachable.
    - Generate/export `VEXA_API_KEY`, `VEXA_HOST`, `VEXA_PORT`, and `VEXA_WS_PATH`.
    - Create a disposable Zoom or Google Meet call with two consenting speakers.
    - Admit the Vexa bot and confirm participant notice/consent.
    - Capture evidence showing bot join, transcript events from both sides, and Sales RPG AI receiving those events.

- **P3: Make S5-05 latency claims runtime-real**
  - Current status: structural and simulated tests pass, but runtime behavior is unproven.
  - `StreamingAnalyzer.analyze()` uses `stream=True` but collects the full response before returning, so UI incremental display is not proven.
  - `_try_with_fallback()` exists but the worker path calls `analyze()` directly.
  - Required probes:
    - Search and document runtime call path: `rg -n "analyze\\(|_try_with_fallback|stream=True" src/realtime src/web`.
    - Probe time-to-first-token reaching the UI before full response completion.
    - Probe primary timeout at 5 seconds invoking the fallback model in the production worker path.
    - Run a real or provider-backed benchmark recording p50 < 3s and p95 < 5s.

- **P4: Complete S5-04 Hardly Selling retrieval layer**
  - Current status: methodology file and `ScriptRetriever.add_source()` exist, but RAG initialization only loads `kubecraft_script.md`.
  - Required probes:
    - `rg -n "hardly_selling_methodology|add_source|chunk_script" src/realtime src/rag knowledge_base`
    - `USE_RAG=true` analyzer initialization shows both script and methodology sources loaded.
    - Retrieval query returns methodology content with source metadata.
    - Coaching or recommendation output references a specific Hardly Selling technique when relevant.

- **P5: Enforce S5-07 security startup behavior**
  - Current status: docs and helpers exist; startup enforcement is missing.
  - Required probes:
    - `rg -n "verify_knowledge_base|integrity_check" src/web src/realtime src/rag`
    - App startup probe showing the integrity check runs before RAG content is trusted.
    - Tampered or empty knowledge-base probe fails according to documented policy.
    - `pytest -q tests/test_behavioral.py tests/test_s5_acceptance.py::TestS5_07_Security`.

- **P6: Live-prove or defer S5-08 overlay**
  - Current status: structural code exists; desktop behavior is unverified here.
  - Required probes:
    - `python -m tkinter`
    - Start the app and launch the overlay against `ws://localhost:8000/ws/audio?role=monitor`.
    - Send a synthetic monitor WebSocket message and verify the overlay updates.
  - `[DEFERRED-VERIFY]` human pre-flight if no graphical desktop/meeting window is available:
    - Run from an actual graphical desktop session with Tk installed.
    - Open Zoom or Google Meet and keep it focused.
    - Launch `src/overlay/overlay_widget.py`.
    - Confirm topmost behavior, drag, resize, live coaching update, and show/hide hotkey while Zoom/Meet is focused.
    - Capture screenshot or screen recording evidence.

- **P7: Runtime-prove S5-03 reconnection**
  - Current status: structural tests pass, but scheduled cleanup and recorder resume semantics are not proven.
  - Required probes:
    - Start the server, connect a monitor WebSocket, then forcibly drop it and show stale cleanup within 5 seconds.
    - Reconnect a monitor and verify transcript history replay.
    - Decide and document whether recorder-session resume is in scope or explicitly unsupported.

- **P8: Reconfirm S5-01 provider extraction after changes**
  - Current status: lowest risk; behavioral provider tests pass.
  - Required probes:
    - `pytest -q tests/test_behavioral.py::TestLLMProviderBehavior`
    - Smoke `get_llm_config()` for all seven providers with expected env vars or expected missing-env errors.
    - Confirm `src/web/app.py` imports `get_llm_config()` rather than carrying inline provider config.

- **Merge gate**
  - Every S5 story must be either honestly probe-passing or marked `[DEFERRED-VERIFY]` with the exact pre-flight steps above.
  - Run the selected Phase 5 test/probe set and record command output in the final verification log.
  - Ensure the working tree is clean except intentional evidence/spec/plan/PRD updates.
  - Only then rebase/merge `phase5/ralph-loop` into `main`.
