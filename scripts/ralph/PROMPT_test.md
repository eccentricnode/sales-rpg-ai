# Sales RPG AI — Ralph Test Mode

You are an autonomous coding agent working on the Sales RPG AI project.

**MODE: TEST ONLY. DO NOT WRITE IMPLEMENTATION CODE.**

## Your Task

1. Read `AGENT.md` for project overview and conventions.
2. Read `prd.json` — find the next story where `passes: false`.
3. Read the relevant behavioral spec in `specs/` for that story's subsystem.
4. Write FAILING tests that verify the spec's postconditions and invariants.

## Red Gate Protocol

1. Write tests based on the behavioral spec (preconditions → error tests, postconditions → assertion tests, invariants → property tests, edge cases → parametrized tests).
2. Run `uv run pytest tests/ -v` — ALL new tests MUST FAIL.
3. If any new test passes before implementation, the test is suspect — it may be testing the wrong thing. Investigate and fix.
4. Update `progress.txt` with which tests were written and their expected failure reasons.

## Test Patterns

```python
# Precondition violation → error test
def test_analyzer_rejects_empty_text():
    with pytest.raises(ValueError):
        analyzer.analyze("")

# Postcondition → assertion test
def test_buffer_rotates_active_to_context():
    manager.active_buffer = [segment]
    manager.rotate_buffers()
    assert len(manager.active_buffer) == 0
    assert segment in manager.context_buffer

# Invariant → property test (if using hypothesis)
def test_context_buffer_never_exceeds_max():
    # After any sequence of operations...
    assert len(manager.context_buffer) <= config.max_context_segments

# Edge case → parametrized test
@pytest.mark.parametrize("trigger", ["time", "segments", "chars", "sentence", "silence"])
def test_each_trigger_fires_independently(trigger):
    ...
```

## Rules

- **DO NOT modify any source code in `src/`.** Test mode writes ONLY to `tests/`.
- **Tests must reference spec requirements.** Each test docstring should cite the spec section it validates.
- **One test file per story.** Name format: `tests/test_{story_id}_{short_name}.py`
- **All existing tests must still pass.** Don't break what works.

## Quality Gate Check

```bash
uv run ruff check tests/
uv run pytest tests/ -v  # Existing tests pass, new tests FAIL
```
