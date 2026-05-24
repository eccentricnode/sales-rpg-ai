"""
Dual Buffer Manager for real-time transcript analysis.

This module implements a dual buffer architecture for batched LLM analysis
of streaming transcripts from WhisperLive.
"""

import time
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class BufferConfig:
    """Configuration for dual buffer system."""

    # Trigger thresholds
    time_threshold_seconds: float = 3.0   # Reverted to fast response
    min_completed_segments: int = 2       # Reverted to fast response
    min_characters: int = 150             # Reverted to fast response
    silence_threshold_seconds: float = 1.5 # Reverted to fast response

    # Context window
    context_window_seconds: float = 30.0
    max_context_segments: int = 20

    # Analysis behavior
    include_incomplete_segment: bool = False
    sentence_end_triggers: bool = True    # Re-enabled for responsiveness


@dataclass
class Segment:
    """Represents a transcript segment."""

    text: str
    start: float
    end: float
    completed: bool

    @classmethod
    def from_dict(cls, data: dict) -> "Segment":
        """Create Segment from WhisperLive segment dict."""
        return cls(
            text=data.get("text", ""),
            start=float(data.get("start", 0)),
            end=float(data.get("end", 0)),
            completed=data.get("completed", False),
        )


class DualBufferManager:
    """
    Manages dual buffer system for batched LLM analysis.

    Receives transcript chunks from WhisperLive callback,
    accumulates in active buffer, and triggers analysis
    when conditions are met.
    """

    def __init__(
        self,
        config: Optional[BufferConfig] = None,
        on_analysis_ready: Optional[Callable[[str, str], None]] = None,
        on_state_analysis_ready: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize the dual buffer manager.

        Args:
            config: Buffer configuration (thresholds, window sizes).
                   Uses defaults if not provided.
            on_analysis_ready: Callback when analysis should be triggered.
                              Signature: (active_text: str, context_text: str) -> None
            on_state_analysis_ready: Callback when state analysis should be triggered.
                                    Signature: (full_transcript: str) -> None
        """
        self.config = config or BufferConfig()
        self.on_analysis_ready = on_analysis_ready
        self.on_state_analysis_ready = on_state_analysis_ready

        # Active buffer: accumulates new segments
        self.active_buffer: list[Segment] = []

        # Context buffer: previous segments for context
        self.context_buffer: list[Segment] = []
        
        # Full history: all completed segments for state analysis
        self.full_history: list[Segment] = []

        # Track the last incomplete segment (may change)
        self.last_incomplete_segment: Optional[Segment] = None

        # Timing
        self.last_analysis_time: float = time.time()
        self.last_state_analysis_time: float = time.time()
        self.last_segment_end_time: float = 0.0

        # Track processed segment IDs to avoid duplicates
        self._processed_segment_keys: set[tuple[float, float]] = set()

    def on_transcript_chunk(self, text: str, segments: list) -> None:
        """
        Callback for WhisperLive transcription_callback.

        Called each time WhisperLive sends updated transcript.
        Processes segments, updates buffers, checks triggers.

        Args:
            text: Space-joined transcript of current segments
            segments: List of segment dictionaries from WhisperLive
        """
        for i, seg_dict in enumerate(segments):
            segment = Segment.from_dict(seg_dict)
            seg_key = (segment.start, segment.end)

            # Track the last incomplete segment
            is_last = i == len(segments) - 1
            if is_last and not segment.completed:
                self.last_incomplete_segment = segment
                continue

            # Skip already processed segments
            if seg_key in self._processed_segment_keys:
                continue

            # Only add completed segments to active buffer
            if segment.completed:
                self.active_buffer.append(segment)
                self._processed_segment_keys.add(seg_key)
                self.last_segment_end_time = segment.end

        # Check if we should trigger analysis
        if self.should_trigger_analysis():
            self._trigger_analysis()

    def should_trigger_analysis(self) -> bool:
        """
        Check if any trigger condition is met.

        Returns:
            True if analysis should be triggered, False otherwise.
        """
        # Don't trigger if active buffer is empty
        if not self.active_buffer:
            return False

        config = self.config
        now = time.time()

        # Condition 1: Time elapsed since last analysis
        time_elapsed = now - self.last_analysis_time
        if time_elapsed >= config.time_threshold_seconds:
            return True

        # Condition 2: Minimum completed segments accumulated
        if len(self.active_buffer) >= config.min_completed_segments:
            return True

        # Condition 3: Character count threshold
        active_text = self._get_buffer_text(self.active_buffer)
        if len(active_text) >= config.min_characters:
            return True

        # Condition 4: Sentence-ending punctuation
        if config.sentence_end_triggers:
            if active_text.rstrip().endswith((".", "?", "!")):
                return True

        # Condition 5: Silence detected (gap between segments)
        if self.last_incomplete_segment:
            # Check gap between last completed and current incomplete
            if self.active_buffer:
                last_completed_end = self.active_buffer[-1].end
                current_start = self.last_incomplete_segment.start
                gap = current_start - last_completed_end
                if gap >= config.silence_threshold_seconds:
                    return True

        return False

    def get_analysis_payload(self) -> tuple[str, str]:
        """
        Get the text payload for analysis.

        Returns:
            Tuple of (active_text, context_text) for analysis.
            active_text: New content to analyze for objections
            context_text: Previous content for LLM context
        """
        active_text = self._get_buffer_text(self.active_buffer)
        context_text = self._get_buffer_text(self.context_buffer)

        # Optionally include incomplete segment
        if self.config.include_incomplete_segment and self.last_incomplete_segment:
            active_text += " " + self.last_incomplete_segment.text

        return active_text.strip(), context_text.strip()

    def rotate_buffers(self) -> None:
        """
        Move active buffer to context, reset active.

        Called after analysis is submitted. Maintains context window
        by trimming old segments based on config.
        """
        # Add active buffer to full history
        self.full_history.extend(self.active_buffer)

        # Move active buffer contents to context buffer
        self.context_buffer.extend(self.active_buffer)

        # Trim context buffer to window size
        self._trim_context_buffer()

        # Reset active buffer
        self.active_buffer = []
        
        # Check if we should trigger state analysis (Slow Loop)
        self._check_state_trigger()

    def _check_state_trigger(self) -> None:
        """Check if it's time to run the Slow Loop state analysis."""
        if not self.on_state_analysis_ready:
            return
            
        # Trigger every 60 seconds
        if time.time() - self.last_state_analysis_time > 60.0:
            full_text = self._get_buffer_text(self.full_history)
            if full_text.strip():
                self.on_state_analysis_ready(full_text)
                self.last_state_analysis_time = time.time()

        # Update timing
        self.last_analysis_time = time.time()

    def _trigger_analysis(self) -> None:
        """Internal method to trigger analysis."""
        active_text, context_text = self.get_analysis_payload()

        # Call the callback if provided
        if self.on_analysis_ready:
            self.on_analysis_ready(active_text, context_text)

        # Rotate buffers after triggering
        self.rotate_buffers()

    def _get_buffer_text(self, buffer: list[Segment]) -> str:
        """Get concatenated text from a buffer."""
        return " ".join(seg.text for seg in buffer)

    def _trim_context_buffer(self) -> None:
        """Trim context buffer to configured window size."""
        config = self.config

        # Trim by segment count
        if len(self.context_buffer) > config.max_context_segments:
            self.context_buffer = self.context_buffer[-config.max_context_segments :]

        # Trim by time window
        if self.context_buffer:
            latest_end = self.context_buffer[-1].end
            cutoff_time = latest_end - config.context_window_seconds

            self.context_buffer = [
                seg for seg in self.context_buffer if seg.end >= cutoff_time
            ]

    def reset(self) -> None:
        """Reset all buffers and state."""
        self.active_buffer = []
        self.context_buffer = []
        self.last_incomplete_segment = None
        self.last_analysis_time = time.time()
        self.last_segment_end_time = 0.0
        self._processed_segment_keys = set()


# Simple test
if __name__ == "__main__":
    print("Testing DualBufferManager...")
    print("=" * 60)

    # Track if trigger was called
    trigger_count = 0
    trigger_reasons = []

    def on_trigger(active_text: str, context_text: str):
        global trigger_count
        trigger_count += 1
        print(f"\n{'='*60}")
        print("TRIGGER")
        print(f"{'='*60}")
        print(f"Active text: {active_text}")
        if context_text:
            print(f"Context text: {context_text}")
        print(f"{'='*60}\n")

    # Create manager with hardcoded config
    config = BufferConfig(
        time_threshold_seconds=3.0,
        min_completed_segments=2,
        min_characters=150,
        silence_threshold_seconds=1.5,
        context_window_seconds=30.0,
        max_context_segments=20,
        include_incomplete_segment=False,
        sentence_end_triggers=True,
    )

    manager = DualBufferManager(config=config, on_analysis_ready=on_trigger)

    # Simulate incoming transcript chunks
    print("Simulating transcript chunks...")

    # Test 1: min_completed_segments trigger
    print("\n" + "-" * 60)
    print("TEST 1: min_completed_segments trigger (2 segments)")
    print("-" * 60)

    print("\n[Chunk 1] Single completed segment (no trigger)")
    manager.on_transcript_chunk(
        "Hello there",
        [{"text": "Hello there", "start": 0.0, "end": 1.5, "completed": True}],
    )
    print(f"  Active buffer size: {len(manager.active_buffer)}")
    print(f"  Trigger count: {trigger_count}")

    print("\n[Chunk 2] Second completed segment (should TRIGGER)")
    manager.on_transcript_chunk(
        "Hello there how are you today",
        [
            {"text": "Hello there", "start": 0.0, "end": 1.5, "completed": True},
            {"text": "how are you today", "start": 1.5, "end": 3.0, "completed": True},
        ],
    )
    print(f"  Context buffer now has: {len(manager.context_buffer)} segments")
    print(f"  Trigger count: {trigger_count}")

    # Test 2: sentence_end_triggers
    print("\n" + "-" * 60)
    print("TEST 2: sentence_end_triggers (ends with period)")
    print("-" * 60)

    print("\n[Chunk 3] Sentence ending with period (should TRIGGER)")
    manager.on_transcript_chunk(
        "I need to think about this.",
        [{"text": "I need to think about this.", "start": 3.5, "end": 5.0, "completed": True}],
    )
    print(f"  Trigger count: {trigger_count}")

    # Test 3: min_characters trigger
    print("\n" + "-" * 60)
    print("TEST 3: min_characters trigger (>= 150 chars)")
    print("-" * 60)

    # Disable sentence-end trigger for this test
    manager.config.sentence_end_triggers = False
    manager.reset()

    long_text = "This is a much longer segment that contains enough characters to trigger the analysis based on the character count threshold alone and we need more words here"
    print(f"\n[Chunk 4] Long text ({len(long_text)} chars, should TRIGGER)")
    manager.on_transcript_chunk(
        long_text,
        [{"text": long_text, "start": 0.0, "end": 8.0, "completed": True}],
    )
    print(f"  Trigger count: {trigger_count}")

    # Test 4: Context preservation
    print("\n" + "-" * 60)
    print("TEST 4: Context buffer preservation")
    print("-" * 60)

    manager.reset()
    manager.config.sentence_end_triggers = True

    # Add first segment
    manager.on_transcript_chunk(
        "The price is too high.",
        [{"text": "The price is too high.", "start": 0.0, "end": 2.0, "completed": True}],
    )
    print(f"  First trigger, context should be empty")

    # Add second segment - context should now contain first
    print("\n[Chunk 5] Second sentence (should show context from previous)")
    manager.on_transcript_chunk(
        "I need to talk to my manager.",
        [{"text": "I need to talk to my manager.", "start": 2.5, "end": 4.5, "completed": True}],
    )
    print(f"  Trigger count: {trigger_count}")

    print("\n" + "=" * 60)
    print(f"TEST COMPLETE! Total triggers: {trigger_count}")
    print("=" * 60)
