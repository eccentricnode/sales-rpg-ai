# Behavioral Contract: Latency Optimization

**Files:** `src/realtime/analysis_orchestrator.py`, `src/web/app.py`, `src/web/static/js/audio-client.js`
**Purpose:** Keep coaching suggestions responsive enough for live sales calls.

## Preconditions

- `StreamingAnalyzer` is initialized with a primary model and, when configured, a faster fallback model.
- Runtime analysis flows through `AnalysisOrchestrator` or another measured path that records latency.
- Browser UI can receive incremental coaching output if streaming is enabled.

## Postconditions

- End-to-end latency from accepted transcript segment to displayed coaching suggestion is below 3 seconds for p50.
- p95 latency is recorded and remains below the configured threshold, currently 5 seconds.
- LLM responses stream incrementally to the UI; collecting every chunk server-side before display does not satisfy this behavior.
- If the primary model exceeds 5 seconds or errors in a timeout-compatible way, runtime code attempts the configured fallback model.
- Benchmarks record real measured timings, not only simulated sleeps.

## Required Probe Evidence

- Benchmark with p50 and p95 values from the actual coaching path.
- Probe showing first streamed LLM chunk reaches the UI before the full response is complete.
- Probe showing runtime fallback is invoked from the production analysis path, not only by a direct unit test of a helper.
- Regression test covering timeout behavior without leaking background threads.

## Edge Cases

- A timed-out primary request may continue in the background if implemented with threads; the fallback path must avoid corrupting shared model state.
- Streaming JSON may be incomplete until the final chunk; UI must distinguish partial display from parsed final state.
- Slow local models should produce honest failed or deferred evidence, not synthetic passing latency.
