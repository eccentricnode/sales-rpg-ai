# Behavioral Contract: StreamingAnalyzer & AnalysisOrchestrator

**Files:** `src/realtime/analysis_orchestrator.py`
**Purpose:** StreamingAnalyzer wraps OpenAI-compatible LLM calls for coaching analysis. AnalysisOrchestrator provides async queue-based execution on a daemon thread.

## Preconditions

### StreamingAnalyzer.__init__(api_key, base_url, model)
- `api_key` must be a non-empty string (or "local" for LocalAI)
- `base_url` must be a valid HTTP(S) URL for the OpenAI-compatible API
- `model` must be a model identifier supported by the provider
- If `USE_RAG=true` (env var), RAG pipeline initializes: chunker → embeddings → retriever
- RAG requires `knowledge_base/kubecraft_script.md` to exist
- RAG requires `sentence-transformers` and `chromadb` packages

### StreamingAnalyzer.analyze(active_text, context_text)
- `active_text` must be non-empty (current: no validation — empty text silently produces bad output)
- `context_text` can be empty string (no prior context)

### AnalysisOrchestrator.__init__(analyzer, on_result)
- `analyzer` must be a fully initialized StreamingAnalyzer
- `on_result` must be a callable accepting AnalysisResult

## Postconditions

### StreamingAnalyzer.analyze(active_text, context_text) → str
- Returns JSON string with fields: `script_location`, `key_points`, `suggestion`
- If `context_text` provided, wraps in `<conversation_so_far>` / `<latest>` XML tags
- If RAG enabled, retrieves top-3 relevant script sections per request
- System prompt is either full script guidance (non-RAG) or RAG guidance with retrieved sections
- LLM called with: max_tokens=500, temperature=0.1, timeout=30s
- Stop sequences: `<|end|>`, `<|end_of_text|>`, `<|im_end|>`, `\n\n`
- Markdown code fences cleaned from response before return

### StreamingAnalyzer.recommend(summary, key_points, stage, context_text) → str
- Returns JSON string with fields: `stage`, `questions`, `reasoning`
- Uses semantic blueprint system — maps stage to one of 4 blueprint templates (discovery, pitch, objection, close)
- Unknown stages default to discovery blueprint
- RAG sections retrieved if retriever available
- LLM called with: max_tokens=600, temperature=0.2, timeout=30s

### AnalysisOrchestrator.submit_analysis(active_text, context_text)
- Creates AnalysisRequest and puts on queue
- Non-blocking — returns immediately

### AnalysisOrchestrator._worker_loop()
- Runs on daemon thread, polls queue with 0.5s timeout
- For each request: calls analyzer.analyze(), parses JSON, creates ConversationState
- On success: calls `on_result` with AnalysisResult containing state and latency
- On failure: calls `on_result` with AnalysisResult containing error string and empty state
- Thread exits when `self.running` set to False

## Invariants

1. **Single worker thread:** Only one `_worker_loop` thread runs at a time
2. **Queue ordering:** Analysis requests processed FIFO
3. **Error isolation:** A failed analysis does not crash the worker thread — error caught, result sent, loop continues
4. **Latency measurement:** `latency_ms` measures wall-clock time of `analyze()` call only (not queue wait time)
5. **RAG is optional:** System works identically with or without RAG — just uses full script instead of retrieved sections
6. **JSON cleaning:** Markdown code fences are always stripped before returning (handles ```json ... ``` wrapping)

## Edge Cases

1. **LLM returns invalid JSON:** `json.loads()` raises, caught in worker loop, error result sent
2. **LLM timeout (>30s):** OpenAI client raises timeout error, caught in worker loop
3. **Queue backpressure:** No queue size limit — long LLM latency causes unbounded queue growth
4. **RAG initialization failure:** If ChromaDB or embedding model fails to load, caught in `_init_rag()`, logged, but analyzer continues without RAG
5. **Empty active_text:** No validation — LLM receives empty prompt, produces garbage response
6. **Provider API rate limiting:** No retry logic — 429 errors propagate as analysis errors
7. **Concurrent submit_analysis calls:** Thread-safe via `queue.Queue` (inherently thread-safe)
8. **shutdown() during active analysis:** Worker thread joined with 1.0s timeout — may be killed mid-analysis
9. **analyze() None dereference:** `response.choices[0].message.content` can be None. `recommend()` guards with `or ""` but `analyze()` does not. Fix: add `content = ... or ""`.
10. **start() can be called twice:** No guard prevents creating duplicate worker threads consuming from the same queue.
11. **Queue not drained on shutdown:** Pending items silently dropped when worker thread exits.

## LLM Provider Interface Contract

All 7 providers satisfy this interface (implemented in `src/realtime/llm_provider.py`):

```python
def get_llm_config(provider: str | None = None) -> LLMConfig:
    """Returns LLMConfig(api_key, base_url, model, provider) for the configured provider."""
```

**Providers:**
| Provider | Env Vars Required | Base URL |
|----------|------------------|----------|
| `local` | None | `LOCAL_AI_BASE_URL` (default: localhost:8080/v1) |
| `github` | `GITHUB_TOKEN` | `https://models.github.ai/inference` |
| `openrouter` | `OPENROUTER_API_KEY` | `https://openrouter.ai/api/v1` |
| `azure` | `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT` | `{endpoint}/openai/deployments/{deployment}` |
| `azure_ai` | `AZURE_AI_API_KEY` | `AZURE_AI_BASE_URL` (default: models.inference.ai.azure.com) |
| `openai` | `OPENAI_API_KEY` | `https://api.openai.com/v1` |
| `gemini` | `GEMINI_API_KEY` | `https://generativelanguage.googleapis.com/v1beta/openai/` |

**Error contract:** Missing required env vars raise `ValueError` with descriptive message including signup URL.
