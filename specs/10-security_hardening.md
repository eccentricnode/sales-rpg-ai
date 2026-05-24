# Behavioral Contract: Security Hardening

**Files:** `src/web/app.py`, `src/realtime/llm_provider.py`, `src/rag/integrity.py`, `docs/threat_model.md`
**Purpose:** Protect audio data, transcript content, LLM credentials, WebSocket access, prompts, and RAG knowledge sources.

## Preconditions

- API keys and tokens are supplied through environment variables or secret managers.
- WebSocket endpoints receive an Origin header from browser clients.
- Knowledge base files are present before RAG initialization.

## Postconditions

- No hardcoded provider API keys or bearer tokens exist in source code.
- WebSocket endpoints validate `Origin` before accepting browser connections.
- Threat model documentation covers audio data, transcripts, LLM API keys, WebSockets, prompt injection, and RAG integrity.
- Prompt injection defenses are documented and tested for transcript/audio-derived user input.
- RAG knowledge base integrity checks run during application startup before retrieved content is trusted.

## Required Probe Evidence

- Secret scan or focused source grep with no hardcoded credential findings.
- Origin validation probe showing allowed origins pass and disallowed origins fail.
- Startup probe showing `verify_knowledge_base()` or `integrity_check()` is invoked.
- Red-team prompt injection test or equivalent verifying malicious transcript text cannot override system/developer instructions.

## Edge Cases

- No-Origin non-browser clients may be allowed only when this is documented and deliberate.
- Integrity manifests can be absent during development, but missing files and empty files must still fail.
- Health endpoints must not leak secrets or sensitive deployment details.
