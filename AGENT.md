# Sales RPG AI — Agent Instructions

## Project Overview

Real-time AI-powered sales coaching tool. Listens to live sales calls via audio transcription, tracks progress through a sales script, provides real-time coaching suggestions.

**Stack:** Python 3.10+ | FastAPI | WebSocket | OpenAI-compatible LLM APIs | ChromaDB (RAG) | Docker

## Architecture

```
Browser (mic) → WebSocket → FastAPI (app.py)
                                ↓
                     VadTranscriber (Whisper + VAD)
                                ↓
                     DualBufferManager (trigger logic)
                                ↓
                     StreamingAnalyzer (LLM coaching)
                                ↓
                     WebSocket broadcast → Browser UI
                                ↓
                     SummaryEngine (5-min rolling summaries)
```

## Core Subsystems

| Subsystem | File | Spec | Purpose |
|-----------|------|------|---------|
| WebSocket Server | `src/web/app.py` | `specs/websocket_manager.md` | FastAPI routes, WebSocket handling, LLM config |
| Buffer Manager | `src/realtime/buffer_manager.py` | `specs/buffer_manager.md` | Dual buffer with 5 trigger conditions |
| Analysis Orchestrator | `src/realtime/analysis_orchestrator.py` | `specs/analysis_orchestrator.md` | Async LLM queue, RAG integration |
| Summary Engine | `src/realtime/summary_engine.py` | `specs/summary_engine.md` | Timer-based rolling conversation summary |
| LLM Provider Interface | `src/web/app.py:get_llm_config()` | `specs/llm_provider.md` | 7-provider abstraction |
| Prompts | `src/realtime/prompts.py` | — | Hardly Selling framework, semantic blueprints |
| RAG Pipeline | `src/rag/` | — | Chunk → embed → retrieve script sections |
| Models | `src/realtime/models.py` | — | ConversationState dataclass |

## Build Commands

```bash
# Install dependencies
uv sync

# Run the app
uv run uvicorn src.web.app:app --host 0.0.0.0 --port 8080 --reload

# Docker
make up      # Start all services
make down    # Stop all services
make logs    # Follow logs
```

## Quality Gates (ALL must pass before commit)

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/ --ignore-missing-imports
uv run pytest tests/ -v
```

## Critical Rules

1. **Read specs before modifying code.** Every core subsystem has a behavioral spec in `specs/`. Read the spec first to understand preconditions, postconditions, and invariants.
2. **One story per loop.** Pick the highest-priority story from `prd.json` where `passes: false`. Implement it. Mark it `passes: true`. Commit. Stop.
3. **Tests before code (Red Gate).** Write failing tests that verify the spec's postconditions BEFORE writing implementation code. All new tests must FAIL before you implement.
4. **Don't assume — search.** Before creating new code, search the codebase for existing patterns. `src/web/app.py` is the main entry point. RAG is in `src/rag/`. Tests are in `tests/`.
5. **client_id and session state from server only.** Never trust client-side data for security-sensitive operations.
6. **No JS frameworks.** Frontend is vanilla JS + WebSocket. Keep it simple.
7. **Sync SQLAlchemy not used here.** This project uses OpenAI SDK + ChromaDB. No ORM.
8. **All LLM calls go through StreamingAnalyzer.** Don't create new OpenAI clients — use the existing orchestrator pattern.
9. **Buffer manager invariants are sacred.** The 5 trigger conditions interact with each other. Read the spec before modifying trigger logic.

## Environment Variables (.env)

| Variable | Purpose | Default |
|----------|---------|---------|
| `TRANSCRIPTION_ENGINE` | `vad` or `whisperlivekit` | `vad` |
| `LLM_PROVIDER` | `github\|openrouter\|azure\|openai\|gemini\|azure_ai\|local` | `local` |
| `USE_RAG` | Enable RAG pipeline | `false` |
| `VAD_WHISPER_MODEL` | Whisper model size | `base` |
| `VAD_DEVICE` | `cuda` or `cpu` | `cuda` |

## Project Conventions

- **Logging:** Use `logging.getLogger(__name__)` — no print statements
- **Error handling:** Log errors with `exc_info=True` for stack traces
- **JSON responses:** All LLM outputs are JSON. Clean markdown fences before parsing.
- **Threading:** SummaryEngine and AnalysisOrchestrator use daemon threads. Use `asyncio.run_coroutine_threadsafe()` to send WebSocket messages from threads.
- **Buffer rotation:** After analysis triggers, active buffer moves to context buffer. This is an invariant — never skip rotation.
