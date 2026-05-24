# Behavioral Contract: VadTranscriber Audio Continuity

**File:** `src/realtime/vad_transcriber.py`
**Purpose:** Convert streaming Int16 PCM audio into completed transcript segments without losing samples across arbitrary chunk boundaries.

## Preconditions

- Input chunks are 16 kHz mono Int16 PCM bytes.
- Silero VAD processes fixed windows of `VAD_CHUNK_SIZE` samples.
- Browser or meeting audio chunks may arrive at sizes that are not multiples of `VAD_CHUNK_SIZE`.
- Whisper transcription may be mocked in continuity tests; chunk-continuity tests must not depend on a specific synthetic waveform being accepted as speech by Silero.

## Postconditions

- Every sample passed to `feed()` is either processed in a VAD window, stored in `_remainder`, or included in a finalized utterance buffer.
- `_remainder` from one `feed()` call is prepended to the next call before VAD windowing.
- `flush()` processes any trailing `_remainder` instead of dropping it silently.
- A finalized speech utterance emits a segment with `text`, `start`, `end`, and `completed=True`.
- Tests distinguish true sample loss from fixture/model rejection.

## Required Probe Evidence

- Structural probe with non-aligned chunks showing `_remainder` length follows `(old_remainder + new_samples) % VAD_CHUNK_SIZE`.
- Mocked VAD/Whisper probe showing speech split across chunks produces at least one completed segment.
- Real VAD smoke probe may be retained, but failure must be interpreted carefully if the waveform is not speech-like to Silero.
- Regression run: `pytest -q tests/test_s5_acceptance.py tests/test_behavioral.py`.

## Edge Cases

- Final chunks shorter than `VAD_CHUNK_SIZE` must still be evaluated during `flush()`.
- Very short speech below the minimum utterance duration may be discarded intentionally and should not count as sample loss.
- False silence inside a word can split utterances; this should not discard the following speech onset.
