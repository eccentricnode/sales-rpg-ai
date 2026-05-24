# Behavioral Contract: LLM Provider Interface

**File:** `src/realtime/llm_provider.py` (extracted from app.py in S5-01)
**Purpose:** Abstracts 7 LLM providers behind a common OpenAI-compatible interface. Returns typed LLMConfig dataclass for StreamingAnalyzer initialization.

## Preconditions

- `LLM_PROVIDER` env var must be one of: `local`, `github`, `openrouter`, `azure`, `azure_ai`, `openai`, `gemini`
- Provider-specific env vars must be set (see per-provider requirements below)
- Missing required env vars raise `ValueError` with descriptive message and signup URL

## Postconditions

### get_llm_config(provider: str | None = None) → LLMConfig
- Returns `LLMConfig(api_key, base_url, model, provider)` dataclass for the configured provider
- If `provider` is None, reads from `LLM_PROVIDER` env var (default: "local")
- Logs the provider and model being used
- All returned values are strings

### Per-Provider Contracts

| Provider | Required Env Vars | api_key | base_url | model |
|----------|------------------|---------|----------|-------|
| `local` | None | `"local"` | `LOCAL_AI_BASE_URL` | `LOCAL_AI_MODEL` |
| `github` | `GITHUB_TOKEN` | token value | `https://models.github.ai/inference` | `GITHUB_MODEL` |
| `openrouter` | `OPENROUTER_API_KEY` | key value | `https://openrouter.ai/api/v1` | `OPENROUTER_MODEL` |
| `azure` | `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT` | key value | `{endpoint}/openai/deployments/{deployment}` | `AZURE_OPENAI_DEPLOYMENT` |
| `azure_ai` | `AZURE_AI_API_KEY` | key value | `AZURE_AI_BASE_URL` | `AZURE_AI_MODEL` |
| `openai` | `OPENAI_API_KEY` | key value | `https://api.openai.com/v1` | `OPENAI_MODEL` |
| `gemini` | `GEMINI_API_KEY` | key value | `https://generativelanguage.googleapis.com/v1beta/openai/` | `GEMINI_MODEL` |

### Error Contract
- Unknown provider → `ValueError("Unknown LLM_PROVIDER: {provider}. Options: ...")`
- Missing required key → `ValueError("{KEY} not set. Get one at: {url}")`
- Azure special case: endpoint URL has trailing slash stripped, deployment appended to path

## Invariants

1. **All providers return same shape:** Always `LLMConfig(api_key: str, base_url: str, model: str, provider: str)` — no None values
2. **Provider name case-insensitive:** `LLM_PROVIDER` lowercased before matching
3. **Local provider needs no auth:** api_key is literal string `"local"`
4. **Base URLs are complete:** No path assembly needed by caller (except Azure which builds deployment path)
5. **Env var defaults:** All models have sensible defaults (gpt-4o-mini, phi-3.5-mini, llama-3.3-70b, gemini-2.0-flash)

## Edge Cases

1. **Empty string env var:** `GITHUB_TOKEN=""` passes the `if not` check → raises ValueError (correct behavior)
2. **Azure endpoint with trailing slash:** Stripped via `.rstrip('/')` before path assembly
3. **Provider env var set but wrong:** No validation of API key format — errors surface at first LLM call
4. **Multiple providers configured:** Only `LLM_PROVIDER` value is used — other keys ignored
5. **Hot-swapping providers:** Not supported — config read at startup only. Restart required.
6. **Rate limiting:** Not handled at this layer — propagates to StreamingAnalyzer error handling
7. **Azure deployment empty string:** `AZURE_OPENAI_DEPLOYMENT` defaults to `""`, producing malformed base_url and empty model. Fix: add `if not deployment:` to validation.
8. **LLMConfig repr exposes API keys:** Default dataclass `__repr__` prints full `api_key`. Fix: override `__repr__` to mask key.
9. **Empty model env vars not validated:** e.g., `GITHUB_MODEL=""` produces `model=""` — fails silently at LLM call time.

## Implementation (S5-01 Complete)

Extracted to `src/realtime/llm_provider.py`:
```python
@dataclass
class LLMConfig:
    api_key: str
    base_url: str
    model: str
    provider: str

def get_llm_config(provider: str | None = None) -> LLMConfig:
    """Returns typed config for the specified or default provider."""
```

This enables:
- Type checking on config fields
- Provider metadata via `.provider` attribute
- Future: provider health checks, fallback chains
