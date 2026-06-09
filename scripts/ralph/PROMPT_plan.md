# Sales RPG AI — Ralph Plan Mode

You are an autonomous coding agent working on the Sales RPG AI project.

**MODE: PLAN ONLY. DO NOT WRITE CODE.**

## Your Task

1. Read `AGENT.md` for project overview and conventions.
2. Read `prd.json` for the current story backlog and status.
3. Read `progress.txt` for patterns and learnings from previous iterations.
4. Read the behavioral specs in `specs/` to understand system contracts.
5. Analyze the codebase to identify gaps between current state and the next story's acceptance criteria.

## Output

Update `progress.txt` with:
- Current state assessment (what works, what's broken, what's missing)
- Gap analysis for the next unimplemented story (`passes: false`)
- Recommended approach (specific files to modify, specific changes needed)
- Risks and edge cases to watch for
- Estimated complexity (simple/medium/complex)

## Rules

- **DO NOT modify any source code files.** Plan mode is read-only except for `progress.txt`.
- **DO NOT create new files** except updating `progress.txt`.
- **Search before assuming.** Use grep/find to verify what exists before claiming something is missing.
- **Be specific.** "Fix the buffer" is useless. "Modify `buffer_manager.py:140` to add a guard for simultaneous trigger firing" is useful.
- **Read the spec first.** Every subsystem has a behavioral contract in `specs/`. Your plan must reference spec requirements.

## Quality Gate Check

Before finishing, verify all gates pass:
```bash
uv run ruff check src/ tests/
uv run mypy src/ --ignore-missing-imports
uv run pytest tests/ -v
```

Report any failures in `progress.txt` as blockers for the next build iteration.
