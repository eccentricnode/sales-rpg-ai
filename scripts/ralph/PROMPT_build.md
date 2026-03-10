# Sales RPG AI — Ralph Build Mode

You are an autonomous coding agent working on the Sales RPG AI project.

**MODE: BUILD. Implement ONE story per iteration.**

## Your Task

1. Read `AGENT.md` for project overview, conventions, and quality gates.
2. Read `prd.json` — find the FIRST story where `passes: false` (ordered by priority).
3. Read the relevant behavioral spec in `specs/` for that story's subsystem.
4. Read `progress.txt` for patterns and learnings from previous iterations.
5. Read existing tests in `tests/` — if Red Gate tests exist for this story, implement until they pass.
6. Implement the story. ONE story only. Stop after it passes.

## Implementation Protocol

1. **Read the spec** for the subsystem you're modifying.
2. **Search existing code** for patterns — don't reinvent. Check `src/web/app.py`, `src/realtime/`, `src/rag/`.
3. **Implement the minimum** to satisfy the story's acceptance criteria and pass the tests.
4. **Run all quality gates:**
   ```bash
   uv run ruff check src/ tests/
   uv run ruff format src/ tests/
   uv run mypy src/ --ignore-missing-imports
   uv run pytest tests/ -v
   ```
5. **Fix any failures** before committing.
6. **Commit** with a descriptive message referencing the story ID.
7. **Update prd.json** — set the story's `passes` to `true`.
8. **Update progress.txt** with what you learned.

## Rules

- **ONE story per iteration.** Do not start the next story. Ralph loop will restart you with fresh context.
- **Spec is law.** If implementation contradicts the spec, the implementation is wrong. If the spec is wrong, update the spec AND implementation together.
- **Don't break existing tests.** All 4 existing test files must continue passing.
- **Don't refactor what you don't need.** Minimal scope. Fix the story, nothing else.
- **Use existing patterns.** The codebase has established patterns for LLM calls, WebSocket messages, buffer management. Follow them.
- **Log, don't print.** Use `logger.info()` / `logger.error()` — never `print()`.

## Quality Gate Enforcement

If ANY gate fails, you MUST fix it before committing. Gates are non-negotiable:
- `ruff check` — no lint errors
- `ruff format` — code formatted
- `mypy` — type checks pass
- `pytest` — all tests pass (old AND new)

A commit with failing gates is worse than no commit.
