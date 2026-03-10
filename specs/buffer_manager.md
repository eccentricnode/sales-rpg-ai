# Behavioral Contract: DualBufferManager

**File:** `src/realtime/buffer_manager.py`
**Purpose:** Accumulates transcript segments in an active buffer, triggers LLM analysis when conditions are met, rotates buffers to maintain context window.

## Preconditions

- `on_analysis_ready` callback must be provided for analysis to trigger (otherwise triggers silently no-op)
- `BufferConfig` must have positive thresholds for all 5 trigger conditions
- Segments passed to `on_transcript_chunk()` must have `text`, `start`, `end`, `completed` fields
- `start` and `end` must be float seconds (not string timestamps)
- System clock must be monotonic (time.time() used for elapsed calculations)

## Postconditions

### on_transcript_chunk(text, segments)
- Completed segments are added to `active_buffer` (deduplicated by `(start, end)` key)
- Incomplete segments (last segment where `completed=False`) are stored in `last_incomplete_segment`
- If `should_trigger_analysis()` returns True, `_trigger_analysis()` is called
- After trigger, `rotate_buffers()` moves active → context and resets active

### should_trigger_analysis() → bool
Returns True when ANY of these 5 conditions is met:
1. **Time elapsed:** `time.time() - last_analysis_time >= time_threshold_seconds` AND buffer has content
2. **Segment count:** `len(active_buffer) >= min_completed_segments`
3. **Character count:** total text in active_buffer `>= min_characters`
4. **Sentence ending:** active text ends with `.`, `?`, or `!` (when `sentence_end_triggers=True`)
5. **Silence gap:** gap between last completed segment's end and current incomplete segment's start `>= silence_threshold_seconds`

Special case: If active_buffer is empty but `last_incomplete_segment` exists and its text is new (not previously triggered), triggers on time threshold only.

### rotate_buffers()
- `active_buffer` contents appended to `context_buffer`
- `active_buffer` contents appended to `full_history`
- `active_buffer` reset to empty list
- `context_buffer` trimmed by `max_context_segments` count AND `context_window_seconds` time window
- `last_analysis_time` updated to current time
- `_check_state_trigger()` called (slow loop — fires every 60 seconds if callback provided)

### get_analysis_payload() → (active_text, context_text)
- Returns concatenated text from active_buffer and context_buffer
- If `last_incomplete_segment` exists, its text is appended to active_text
- Both strings are stripped of leading/trailing whitespace

### reset()
- All buffers cleared: active, context, full_history (NOTE: full_history is NOT cleared by current implementation — potential bug)
- All tracking state reset: processed keys, timing, incomplete segment

## Invariants

1. **No duplicate segments:** A segment with key `(start, end)` is processed at most once (tracked via `_processed_segment_keys`)
2. **Context buffer bounded:** After rotation, `len(context_buffer) <= max_context_segments` AND all segments within `context_window_seconds` of the latest
3. **Rotation always follows trigger:** `_trigger_analysis()` always calls `rotate_buffers()` after invoking callback
4. **Active buffer empties on rotation:** After `rotate_buffers()`, `active_buffer == []`
5. **Time monotonicity:** `last_analysis_time` only increases — **BUG: update is inside `_check_state_trigger()` which returns early if `on_state_analysis_ready` is None. Without a state callback, `last_analysis_time` never updates, causing time-threshold to fire on every chunk after initial threshold.** Fix: move update to `rotate_buffers()` directly.
6. **Incomplete segment is singular:** Only the LAST incomplete segment is tracked; previous incomplete segments are overwritten

## Edge Cases

1. **Simultaneous triggers:** Two conditions met at once → only one analysis fires (first `should_trigger_analysis()` check wins, rotation resets state)
2. **Empty active buffer with incomplete segment:** Special path — triggers only on time threshold with new text
3. **Duplicate segment delivery:** WhisperLive may re-send segments with same `(start, end)` — deduplicated by `_processed_segment_keys`
4. **Rapid successive chunks:** Multiple chunks within `time_threshold_seconds` → triggers on segment count or char count, not time
5. **Buffer swap race condition:** `_trigger_analysis()` calls callback THEN rotates — callback may see stale state if it reads buffers directly (current design: callback receives text copies, not buffer references ✓)
6. **Context trimming removes all segments:** If `context_window_seconds` is very small, context_buffer could be empty after trim
7. **full_history grows unbounded:** No trimming on `full_history` — potential memory issue in long calls
8. **reset() does not clear full_history:** Bug — `reset()` clears active and context but not full_history (line 294-301)
9. **`_processed_segment_keys` grows unbounded:** No trimming for long calls — set accumulates every key ever seen. Fix: prune keys older than `context_window_seconds` during `rotate_buffers()`.
10. **Dedup key collision on missing timestamps:** `Segment.from_dict()` defaults `start=0, end=0` — two segments with missing timestamps share key `(0.0, 0.0)`, causing silent data loss.
11. **No thread safety:** Buffer manager has no locks but may be called from different threads via callbacks. Not a current issue (single-threaded asyncio) but fragile.

## Mic Cutoff Root Cause (S5-02)

**Symptom:** Audio sometimes cuts off mid-sentence during real-time transcription. Users report that the tail end of utterances is silently dropped, producing incomplete transcripts.

**Root cause:** The mic cutoff bug originates in `VadTranscriber.feed()` and its interaction with chunk boundaries. Browser `MediaRecorder` sends audio in arbitrarily-sized chunks (typically 100ms = 1600 samples at 16kHz). Silero VAD processes audio in fixed 512-sample windows. When a chunk is not aligned to 512 samples, the remainder is carried over to the next `feed()` call via `_remainder`. Three specific failure modes cause audio continuity loss:

### 1. `flush()` discards remainder when not in speaking state

`VadTranscriber.flush()` (line 236) only processes `_remainder` if `_is_speaking` is True:

```python
if len(self._remainder) > 0 and self._is_speaking:
    self._speech_buffer = np.concatenate([self._speech_buffer, self._remainder])
```

If the final chunk ends with partial audio that hasn't yet triggered a VAD speech detection (because fewer than 512 samples remain), those samples are silently discarded. This clips the onset of speech that spans the final chunk boundary.

**Fix:** In `flush()`, process the remainder through VAD regardless of speaking state. Pad with zeros to reach `VAD_CHUNK_SIZE` if needed, so the VAD can make a final speech/silence decision on the trailing samples.

### 2. `_speech_start_sample` set after remainder prepending skews timestamps

When `_process_vad_window()` detects speech onset, it sets `_speech_start_sample = self._total_samples_fed`. However, `_total_samples_fed` is only incremented at the end of `feed()` (line 141) using the raw input chunk length, not accounting for remainder samples being re-processed. This means the speech start timestamp is relative to the global sample counter before the current chunk, which is correct for the timeline. But if `_finalize_utterance()` is called during the same `feed()` call, the `_total_samples_fed` has not yet been updated, so the end timestamp may slightly undercount. This is a minor precision issue but does not cause dropped audio.

### 3. `_finalize_utterance()` resets state mid-chunk at chunk boundary

When `_finalize_utterance()` fires during `feed()` processing (due to max utterance length or silence threshold), it resets `_is_speaking`, `_speech_buffer`, and `_silence_samples`. Subsequent VAD windows in the same `feed()` call then start fresh. If the audio at that point is mid-word (e.g., a brief dip in VAD probability causes a false silence detection near a chunk boundary), the utterance is split and the beginning of the next word may be below the minimum utterance threshold (160ms), causing it to be discarded as noise. This produces the characteristic "last word cut off" symptom.

**Fix:** Add a look-ahead of 1-2 VAD windows before committing to finalization. Alternatively, lower the silence threshold near chunk boundaries, or carry a small pre-roll buffer into the next utterance.

### Audio continuity invariant

The partial audio continuity contract is: every sample fed via `feed()` must either be (a) processed through a complete VAD window, (b) stored in `_remainder` for the next call, or (c) included in a finalized utterance's `_speech_buffer`. No sample may be silently dropped. The `flush()` bug violates (a) by discarding remainder samples that never reach a full VAD window.

### Chunk boundary alignment

The fundamental architectural tension is that browser `MediaRecorder` produces chunks at its own cadence (typically 100-250ms), while Silero VAD requires exactly 512-sample windows (32ms). The remainder buffer bridges this mismatch, but the current implementation does not guarantee audio continuity across all edge cases at chunk boundaries. Specifically, the remainder buffer is correctly prepended in `feed()` (line 126-128), but `flush()` and `_finalize_utterance()` do not fully account for partial audio left in the remainder.
