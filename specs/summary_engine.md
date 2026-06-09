# Behavioral Contract: SummaryEngine

**File:** `src/realtime/summary_engine.py`
**Purpose:** Timer-based rolling conversation summarizer. Accumulates transcript text and periodically generates summaries via LLM, detecting call phase, buyer archetype, pain indicators, and key points.

## Preconditions

- `client` must be a fully initialized OpenAI client instance
- `model` must be a valid model identifier for the configured provider
- `interval` must be positive float (seconds between automatic summaries, default: 300s / 5min)
- `on_summary` callback is optional — if None, summaries are generated but not broadcast

## Postconditions

### start()
- Sets `_running = True`
- Records `_last_summary_time = time.time()`
- Schedules first timer via `_schedule_next()`
- Timer is a daemon thread (won't prevent process exit)

### stop()
- Sets `_running = False`
- Cancels active timer if exists
- Does NOT flush or generate a final summary

### add_transcript(text)
- Appends `text.strip()` to `_transcript_lines` list
- Thread-safe via `threading.Lock`

### get_full_transcript() → str
- Returns newline-joined transcript lines
- Thread-safe via `threading.Lock`

### refresh()
- Triggers immediate `_generate_summary()` (manual trigger, bypasses timer)
- Synchronous — blocks until LLM response received

### _generate_summary()
- If transcript is empty (whitespace only), logs and returns without LLM call
- Builds prompt via `get_summary_prompt(transcript, previous_summary)`
- LLM called with: max_tokens=800, temperature=0.1, timeout=30s
- Response parsed as JSON with fields: `summary`, `key_points`, `pain_indicators`, `stage_hint`, `archetype_hint`
- On success: updates `current_summary`, `_previous_summary_text`, `_last_summary_time`, calls `on_summary`
- On JSON parse error: creates error SummaryResult, calls `on_summary` with error
- On any other error: creates error SummaryResult, calls `on_summary` with error

### time_until_next() → float
- Returns seconds until next automatic summary (clamped to >= 0)

## Invariants

1. **Timer continuity:** After each timer fires, next timer is scheduled (unless `_running` is False)
2. **Thread safety:** `_transcript_lines` access is always under `_lock`
3. **Rolling summary:** Each summary builds on the previous via `_previous_summary_text` (passed as context to prompt)
4. **Error isolation:** JSON parse errors and LLM errors don't crash the engine — error results are sent to callback
5. **Daemon threads:** All timers are daemon threads — engine doesn't prevent process shutdown
6. **Summary overwrites:** Each new summary replaces `current_summary` entirely (no history kept)

## Edge Cases

1. **No transcript accumulated:** `_generate_summary()` returns early without LLM call
2. **Timer fires during active LLM call:** Timer is non-reentrant — `_on_timer()` calls `_generate_summary()` synchronously, then schedules next. Long LLM calls delay the next timer.
3. **refresh() during timer-triggered summary:** Both could run concurrently — `_generate_summary()` is NOT thread-safe (reads `_transcript_lines` under lock, but LLM call and state updates are not synchronized)
4. **stop() during _generate_summary():** Timer cancelled but running `_generate_summary()` continues to completion (no cancellation mechanism)
5. **LLM returns partial JSON:** `json.loads()` fails, error result sent
6. **Very long transcripts:** Full transcript passed to LLM every time (no truncation) — may exceed model context window
7. **_previous_summary_text persists across stop/start:** If engine is stopped and restarted, previous summary context is retained (may be stale)
8. **Concurrent add_transcript and get_full_transcript:** Thread-safe via lock ✓
9. **Unbounded transcript growth:** `_transcript_lines` grows forever. Full transcript sent to LLM every cycle. Multi-hour calls will exceed model context window. Fix: implement sliding window or truncation with rolling summary as compression.
10. **Error result overwrites current_summary:** `current_summary` is updated even on errors — subsequent reads return error result with no staleness indicator.
11. **_previous_summary_text lost on error:** Set from `result.summary` which is empty on error, breaking rolling context chain.
