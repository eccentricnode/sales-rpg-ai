# PRD: Dual Buffer Architecture for Real-Time LLM Analysis

## Status
✅ **Implemented** (Phase 2)

## Overview

This document describes the implementation plan for intercepting WhisperLive transcript chunks and implementing a dual buffer architecture for batched LLM analysis. This enables real-time objection detection during live sales calls.

**Update (Phase 2 Polish):** This architecture is now augmented by a [Gatekeeper Layer](prd-gatekeeper-rate-limiting.md) to optimize API costs.

---

## Problem Statement

The current implementation waits for complete transcription before analyzing for objections. This works for pre-recorded files but fails the core use case: **providing real-time suggestions during live calls**.

**Current Flow:**
```
Audio → Complete Transcription → Single LLM Call → Results
        (waits for entire file)   (after call ends)
```

**Required Flow:**
```
Audio → Streaming Chunks → Batched Analysis → Continuous Suggestions
        (as speech happens)  (every N seconds)   (during call)
```

---

## Goals

1. Detect objections within 2-3 seconds of being spoken
2. Avoid overwhelming the LLM with per-word API calls
3. Maintain context across analysis batches
4. Handle partial/incomplete sentences gracefully
5. Minimize false positives from incomplete context

---

## WhisperLive Hook Points Analysis

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    WhisperLive Client                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  WebSocket Server ──on_message()──► process_segments()          │
│                                            │                    │
│                                            ▼                    │
│                               transcription_callback(text, segs)│
│                                            │                    │
│                                            ▼                    │
│                               ┌─────────────────────┐           │
│                               │  OUR HOOK POINT     │           │
│                               │  (inject here)      │           │
│                               └─────────────────────┘           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Key Code Locations

**File:** `WhisperLive/whisper_live/client.py`

#### Hook Point 1: `transcription_callback` Parameter

**Location:** `Client.__init__()` line 41

```python
transcription_callback=None,  # Our injection point
```

**Usage:** `process_segments()` lines 150-156

```python
if self.transcription_callback and callable(self.transcription_callback):
    try:
        self.transcription_callback(" ".join(text), segments)
    except Exception as e:
        print(f"[WARN] transcription_callback raised: {e}")
    return
```

**Callback Signature:**
```python
def callback(text: str, segments: list) -> None
```

**Parameters:**
- `text`: Space-joined transcript of current segments (may be partial)
- `segments`: List of segment dictionaries

#### Segment Structure

Each segment in `segments` list:

```python
{
    "text": str,           # Transcribed text for this segment
    "start": float,        # Start time in seconds
    "end": float,          # End time in seconds
    "completed": bool,     # True if segment is finalized (won't change)
}
```

**Critical Insight:** The `completed` field distinguishes between:
- **Completed segments:** Finalized, won't change, safe to analyze
- **In-progress segments:** Still being transcribed, may change

#### Hook Point 2: `process_segments()` Method

**Location:** Lines 133-162

This method:
1. Deduplicates segment text
2. Tracks the last incomplete segment (`self.last_segment`)
3. Appends completed segments to `self.transcript`
4. Calls the callback with current state

**Key Logic (lines 139-144):**
```python
if i == len(segments) - 1 and not seg.get("completed", False):
    self.last_segment = seg  # Track incomplete segment
elif (self.server_backend == "faster_whisper" and seg.get("completed", False) and
      (not self.transcript or
        float(seg['start']) >= float(self.transcript[-1]['end']))):
    self.transcript.append(seg)  # Store completed segment
```

#### Hook Point 3: `TranscriptionClient` Class

**Location:** Lines 694-783

This is the high-level client our code uses. It wraps `Client` and passes through `transcription_callback`.

**Current Usage in Our Code:**
```python
client = TranscriptionClient(
    host=host,
    port=port,
    model='base',
    log_transcription=False,
    transcription_callback=capture.callback  # <-- Our hook
)
```

---

## Dual Buffer Architecture

### Concept

Two buffers work together to balance responsiveness with context:

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   Incoming Transcript Chunks                                    │
│            │                                                    │
│            ▼                                                    │
│   ┌─────────────────┐                                           │
│   │  ACTIVE BUFFER  │  Accumulates new chunks                   │
│   │  (growing)      │  Triggers analysis when ready             │
│   └────────┬────────┘                                           │
│            │                                                    │
│            │ Trigger Conditions Met                             │
│            ▼                                                    │
│   ┌─────────────────┐      ┌─────────────────┐                  │
│   │  CONTEXT BUFFER │ ──►  │  LLM ANALYSIS   │                  │
│   │  (last N secs)  │      │  (async call)   │                  │
│   └─────────────────┘      └────────┬────────┘                  │
│            ▲                        │                           │
│            │                        ▼                           │
│            │               ┌─────────────────┐                  │
│   Previous Active ──────►  │  SUGGESTIONS    │                  │
│   becomes Context          │  (to UI)        │                  │
│                            └─────────────────┘                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Buffer Definitions

#### Active Buffer
- **Purpose:** Accumulates incoming transcript chunks
- **Contents:** New text since last analysis
- **Trigger:** Flushes to analysis when conditions met
- **After flush:** Moves to context buffer, resets

#### Context Buffer
- **Purpose:** Provides surrounding context to LLM
- **Contents:** Previous N seconds of completed transcript
- **Size:** Rolling window (configurable, default 30 seconds)
- **Usage:** Prepended to active buffer for analysis

### Trigger Conditions

Analysis is triggered when ANY of these conditions are met:

| Condition | Default Value | Rationale |
|-----------|---------------|-----------|
| Time elapsed since last analysis | 15 seconds | "Slow Burn" batching for context |
| Completed segments accumulated | 10 segments | Wait for full paragraph |
| Character count in active buffer | 500 chars | Substantial context chunk |
| Sentence-ending punctuation detected | **Disabled** | Avoid triggering on every sentence |
| Silence detected (gap in segments) | 2.0 seconds | Significant pause only |

### State Machine

```
┌──────────────┐
│   IDLE       │
│ (waiting for │
│  first chunk)│
└──────┬───────┘
       │ First chunk received
       ▼
┌──────────────┐
│ ACCUMULATING │◄─────────────────────────┐
│ (filling     │                          │
│  active buf) │                          │
└──────┬───────┘                          │
       │ Trigger condition met            │
       ▼                                  │
┌──────────────┐                          │
│  ANALYZING   │                          │
│ (LLM call    │                          │
│  in flight)  │                          │
└──────┬───────┘                          │
       │ Response received                │
       │ Active → Context                 │
       │ Reset Active                     │
       └──────────────────────────────────┘
```

---

## Implementation Plan

### Component Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     New Components                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  DualBufferManager                      │    │
│  │  - active_buffer: List[Segment]                         │    │
│  │  - context_buffer: List[Segment]                        │    │
│  │  - last_analysis_time: float                            │    │
│  │  - config: BufferConfig                                 │    │
│  │                                                         │    │
│  │  + on_transcript_chunk(text, segments)  ←── callback    │    │
│  │  + should_trigger_analysis() -> bool                    │    │
│  │  + get_analysis_payload() -> str                        │    │
│  │  + rotate_buffers()                                     │    │
│  └─────────────────────────────────────────────────────────┘    │
│                           │                                     │
│                           │ triggers                            │
│                           ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  AnalysisOrchestrator                   │    │
│  │  - analyzer: ObjectionAnalyzer                          │    │
│  │  - result_callback: Callable                            │    │
│  │  - analysis_queue: Queue                                │    │
│  │  - worker_thread: Thread                                │    │
│  │                                                         │    │
│  │  + submit_analysis(payload)                             │    │
│  │  + _worker_loop()  ←── runs async                       │    │
│  │  + on_result(analysis)  ──► UI callback                 │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Class: DualBufferManager

**Responsibility:** Manage transcript buffers, decide when to trigger analysis

```python
class DualBufferManager:
    """
    Manages dual buffer system for batched LLM analysis.

    Receives transcript chunks from WhisperLive callback,
    accumulates in active buffer, and triggers analysis
    when conditions are met.
    """

    def __init__(self, config: BufferConfig, on_analysis_ready: Callable):
        """
        Args:
            config: Buffer configuration (thresholds, window sizes)
            on_analysis_ready: Callback when analysis should be triggered
                               Signature: (payload: str, context: str) -> None
        """

    def on_transcript_chunk(self, text: str, segments: list) -> None:
        """
        Callback for WhisperLive transcription_callback.

        Called each time WhisperLive sends updated transcript.
        Processes segments, updates buffers, checks triggers.
        """

    def should_trigger_analysis(self) -> bool:
        """Check if any trigger condition is met."""

    def get_analysis_payload(self) -> tuple[str, str]:
        """
        Returns (active_text, context_text) for analysis.

        active_text: New content to analyze for objections
        context_text: Previous content for LLM context
        """

    def rotate_buffers(self) -> None:
        """
        Move active buffer to context, reset active.
        Called after analysis is submitted.
        """
```

### Class: BufferConfig

**Responsibility:** Configuration for buffer behavior

```python
@dataclass
class BufferConfig:
    """Configuration for dual buffer system."""

    # Trigger thresholds
    time_threshold_seconds: float = 3.0
    min_completed_segments: int = 2
    min_characters: int = 150
    silence_threshold_seconds: float = 1.5

    # Context window
    context_window_seconds: float = 30.0
    max_context_segments: int = 20

    # Analysis behavior
    include_incomplete_segment: bool = False  # Include last partial segment?
    sentence_end_triggers: bool = True        # Trigger on . ? !
```

### Class: AnalysisOrchestrator

**Responsibility:** Manage async LLM calls, deliver results

```python
class AnalysisOrchestrator:
    """
    Orchestrates async LLM analysis calls.

    Receives analysis requests from DualBufferManager,
    executes them in background thread, delivers results
    via callback.
    """

    def __init__(self, analyzer: ObjectionAnalyzer, on_result: Callable):
        """
        Args:
            analyzer: The LLM analyzer instance
            on_result: Callback for analysis results
                       Signature: (result: AnalysisResult) -> None
        """

    def submit_analysis(self, active_text: str, context_text: str) -> None:
        """
        Submit text for async analysis.

        Non-blocking. Results delivered via on_result callback.
        """

    def shutdown(self) -> None:
        """Gracefully shutdown worker thread."""
```

### Modified Prompt Strategy

The LLM prompt must be adapted for streaming analysis:

```python
STREAMING_ANALYSIS_PROMPT = """You are analyzing a LIVE sales conversation for objections.

CONTEXT (previous conversation):
{context_text}

NEW CONTENT (analyze this for objections):
{active_text}

IMPORTANT:
- Focus analysis on NEW CONTENT only
- Use CONTEXT to understand the conversation flow
- The NEW CONTENT may be mid-sentence or incomplete
- Only flag HIGH confidence objections (avoid false positives)
- If NEW CONTENT is too short/unclear, respond with "INSUFFICIENT_CONTENT"

For each objection found in NEW CONTENT:
1. TYPE: PRICE | TIME | DECISION_MAKER | OTHER
2. CONFIDENCE: HIGH | MEDIUM (skip LOW - too noisy for real-time)
3. QUOTE: Exact words from NEW CONTENT
4. RESPONSE: One best response suggestion (keep it brief for real-time display)

Format:
OBJECTION: [TYPE] | [CONFIDENCE]
> "[quote]"
SUGGEST: [response]

If no objections: "NO_OBJECTIONS"
"""
```

---

## Data Flow Sequence

```
Time →

WhisperLive          DualBufferManager       AnalysisOrchestrator      UI
    │                       │                        │                  │
    │  callback(text, segs) │                        │                  │
    │──────────────────────►│                        │                  │
    │                       │                        │                  │
    │                       │ add to active_buffer   │                  │
    │                       │ check triggers         │                  │
    │                       │                        │                  │
    │  callback(text, segs) │                        │                  │
    │──────────────────────►│                        │                  │
    │                       │                        │                  │
    │                       │ trigger condition met! │                  │
    │                       │                        │                  │
    │                       │ submit_analysis()      │                  │
    │                       │───────────────────────►│                  │
    │                       │                        │                  │
    │                       │ rotate_buffers()       │                  │
    │                       │                        │                  │
    │  callback(text, segs) │                        │ (analyzing...)   │
    │──────────────────────►│                        │                  │
    │                       │                        │                  │
    │                       │ accumulating...        │                  │
    │                       │                        │                  │
    │                       │                        │ on_result()      │
    │                       │                        │─────────────────►│
    │                       │                        │                  │
    │                       │                        │           Display│
    │                       │                        │         Suggestion
```

---

## Integration with Existing Code

### Current Code (transcribe_and_analyze.py)

```python
# Current: Simple capture
capture = TranscriptCapture()
client = TranscriptionClient(
    ...
    transcription_callback=capture.callback
)
```

### New Code

```python
# New: Dual buffer with streaming analysis
def on_objection_detected(result: AnalysisResult):
    """Called when objection detected - update UI."""
    display_suggestion(result)

buffer_config = BufferConfig(
    time_threshold_seconds=3.0,
    context_window_seconds=30.0,
)

analyzer = ObjectionAnalyzer(api_key=os.getenv('OPENROUTER_API_KEY'))
orchestrator = AnalysisOrchestrator(analyzer, on_result=on_objection_detected)

buffer_manager = DualBufferManager(
    config=buffer_config,
    on_analysis_ready=orchestrator.submit_analysis
)

client = TranscriptionClient(
    ...
    transcription_callback=buffer_manager.on_transcript_chunk
)
```

---

## Edge Cases & Handling

| Edge Case | Handling Strategy |
|-----------|-------------------|
| Very fast speech | Character threshold triggers analysis even without completed segments |
| Long silence | Silence threshold triggers analysis of accumulated content |
| Incomplete sentence at trigger | Context buffer carries forward; next analysis has full sentence |
| LLM response slower than trigger interval | Queue analysis requests; don't block accumulation |
| Empty active buffer at trigger | Skip analysis, reset timer |
| Very short utterances ("yes", "no") | Minimum character threshold prevents wasteful API calls |
| Mid-word cutoff | `include_incomplete_segment=False` by default; only analyze completed segments |
| Network latency spike | Orchestrator handles timeout; continues accumulating |
| Repeated/duplicate segments | `process_segments()` already deduplicates |

---

## Configuration Recommendations

### For Sales Calls (default)

```python
BufferConfig(
    time_threshold_seconds=3.0,      # Responsive but not spammy
    min_completed_segments=2,         # Natural speech boundaries
    min_characters=150,               # ~20-30 words
    context_window_seconds=30.0,      # Good context without overwhelming LLM
)
```

### For Fast-Paced Conversations

```python
BufferConfig(
    time_threshold_seconds=2.0,       # Faster response
    min_completed_segments=1,         # Trigger on each segment
    min_characters=100,               # Smaller batches
    context_window_seconds=20.0,      # Less context, faster processing
)
```

### For High Accuracy (fewer false positives)

```python
BufferConfig(
    time_threshold_seconds=5.0,       # Larger batches
    min_completed_segments=3,         # More complete thoughts
    min_characters=250,               # More context per analysis
    context_window_seconds=45.0,      # Rich context
)
```

---

## File Structure

```
src/
├── transcribe_and_analyze.py      # Existing (modify for integration)
├── realtime/
│   ├── __init__.py
│   ├── buffer_manager.py          # DualBufferManager, BufferConfig
│   ├── analysis_orchestrator.py   # AnalysisOrchestrator
│   └── streaming_analyzer.py      # Modified prompts for streaming
└── ui/
    └── (Phase 2 - Tkinter UI)
```

---

## Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Detection latency | < 3 seconds | Time from speech end to suggestion display |
| False positive rate | < 10% | Manual review of flagged objections |
| API calls per minute | < 20 | During active conversation |
| Context coherence | Objections correctly attributed | Manual review |
| Memory usage | Stable over 30+ min call | No buffer growth beyond config |

---

## Open Questions

1. **Should we support multiple concurrent analysis calls?**
   - Pro: Faster response if LLM is slow
   - Con: Complexity, potential race conditions, higher cost

2. **Should context buffer include LLM responses?**
   - Pro: LLM knows what suggestions were already given
   - Con: Larger prompts, higher cost

3. **How to handle objection "resolution"?**
   - If salesperson addresses an objection, should we track that?
   - Could prevent re-flagging the same objection

4. **Configurable per-objection-type thresholds?**
   - PRICE objections might need different handling than TIME
   - Could add type-specific confidence thresholds

---

## Dependencies

- WhisperLive (existing) - No modifications needed
- OpenAI SDK (existing) - No modifications needed
- Python threading (stdlib) - For async orchestration
- Python queue (stdlib) - For analysis request queue
- dataclasses (stdlib) - For BufferConfig

---

## Implementation Status

1. ✅ Review and approve this PRD
2. ✅ Create `src/realtime/` module structure
3. ✅ Implement `BufferConfig` dataclass
4. ✅ Implement `DualBufferManager` class
5. ✅ Implement `AnalysisOrchestrator` class
6. ✅ Create `realtime_transcribe.py` for integration
7. ⬜ Write unit tests for buffer trigger logic
8. ✅ Integration test with live WhisperLive server
9. ⬜ Tune default configuration values
10. ✅ Document usage and configuration options (see CHANGELOG.md)

### Additional Implementations (2025-12-05)

- ✅ `StreamingAnalyzer` class with optimized prompt
- ✅ Verbose mode (`--verbose` flag) for debugging
- ✅ `test_realtime_flow.py` for testing without WhisperLive
- ✅ Error handling for API rate limiting
