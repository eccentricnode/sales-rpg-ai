# AGENTS.md

- You are not alone in the codebase; do not revert edits made by others.
- Full tests: `uv run pytest -q`.
- Focused S5-05 slice: `uv run pytest -q tests/test_s5_acceptance.py::TestS5_05_Latency tests/test_latency_benchmark.py tests/test_behavioral.py::TestLLMProviderBehavior tests/test_behavioral.py::TestStreamingAnalyzerBehavior tests/test_behavioral.py::TestAnalysisOrchestratorBehavior -vv`.
- Fallback model can be configured with provider-specific `*_FALLBACK_MODEL` or global `LLM_FALLBACK_MODEL`.
