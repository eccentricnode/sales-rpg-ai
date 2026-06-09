"""
Summary Engine for rolling conversation summaries.

Generates a distilled summary of the conversation on a timer (~5 min)
or on manual trigger. The summary captures key points, pain indicators,
emotional signals, and archetype hints — feeding the recommendation engine.
"""

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from openai import OpenAI

from .prompts import get_summary_prompt

logger = logging.getLogger(__name__)

# Default interval between automatic summaries (seconds)
DEFAULT_SUMMARY_INTERVAL = 300  # 5 minutes


@dataclass
class SummaryResult:
    """Result from a summary generation."""
    summary: str = ""
    key_points: list[str] = field(default_factory=list)
    pain_indicators: list[str] = field(default_factory=list)
    stage_hint: str = "unknown"
    archetype_hint: str = "unknown"
    timestamp: float = 0.0
    latency_ms: float = 0.0
    error: Optional[str] = None


class SummaryEngine:
    """
    Timer-based conversation summarizer.

    Accumulates transcript text and periodically generates a rolling
    summary via LLM. Also supports manual refresh.
    """

    def __init__(
        self,
        client: OpenAI,
        model: str,
        on_summary: Optional[Callable[[SummaryResult], None]] = None,
        interval: float = DEFAULT_SUMMARY_INTERVAL,
    ) -> None:
        self.client = client
        self.model = model
        self.on_summary = on_summary
        self.interval = interval

        # Transcript accumulator (bounded to prevent unbounded memory growth)
        self._transcript_lines: list[str] = []
        self._max_transcript_lines = 1200  # ~84K chars at ~70 chars/line, safely under 100K
        self._lock = threading.Lock()

        # Current summary state
        self.current_summary: Optional[SummaryResult] = None
        self._previous_summary_text: str = ""

        # Timer
        self._timer: Optional[threading.Timer] = None
        self._running = False
        self._last_summary_time: float = 0.0

    def start(self) -> None:
        """Start the summary timer."""
        self._running = True
        self._last_summary_time = time.time()
        self._schedule_next()
        logger.info(f"SummaryEngine started (interval={self.interval}s)")

    def stop(self) -> None:
        """Stop the summary timer."""
        self._running = False
        if self._timer:
            self._timer.cancel()
            self._timer = None
        logger.info("SummaryEngine stopped")

    def add_transcript(self, text: str) -> None:
        """Add a transcript line to the accumulator (bounded)."""
        with self._lock:
            self._transcript_lines.append(text.strip())
            # Trim oldest lines to prevent unbounded growth in long calls
            if len(self._transcript_lines) > self._max_transcript_lines:
                self._transcript_lines = self._transcript_lines[-self._max_transcript_lines:]

    def get_full_transcript(self) -> str:
        """Get the full accumulated transcript."""
        with self._lock:
            return "\n".join(self._transcript_lines)

    def refresh(self) -> None:
        """Force an immediate summary generation (manual trigger)."""
        logger.info("SummaryEngine: Manual refresh triggered")
        self._generate_summary()

    def time_until_next(self) -> float:
        """Seconds until the next automatic summary."""
        elapsed = time.time() - self._last_summary_time
        return max(0, self.interval - elapsed)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _schedule_next(self) -> None:
        """Schedule the next automatic summary."""
        if not self._running:
            return
        self._timer = threading.Timer(self.interval, self._on_timer)
        self._timer.daemon = True
        self._timer.start()

    def _on_timer(self) -> None:
        """Timer callback."""
        if not self._running:
            return
        self._generate_summary()
        self._schedule_next()

    def _generate_summary(self) -> None:
        """Generate a summary from the accumulated transcript."""
        transcript = self.get_full_transcript()
        if not transcript.strip():
            logger.info("SummaryEngine: No transcript to summarize")
            return

        start_time = time.time()
        try:
            prompt = get_summary_prompt(transcript, self._previous_summary_text)

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": "Generate the conversation summary now."},
                ],
                max_tokens=800,
                temperature=0.1,
                timeout=30,
            )

            content = response.choices[0].message.content or ""

            # Clean markdown
            if "```json" in content:
                content = content.split("```json")[1]
            if "```" in content:
                content = content.split("```")[0]

            data = json.loads(content.strip())

            result = SummaryResult(
                summary=data.get("summary", ""),
                key_points=data.get("key_points", []),
                pain_indicators=data.get("pain_indicators", []),
                stage_hint=data.get("stage_hint", "unknown"),
                archetype_hint=data.get("archetype_hint", "unknown"),
                timestamp=time.time(),
                latency_ms=(time.time() - start_time) * 1000,
            )

            self.current_summary = result
            self._previous_summary_text = result.summary
            self._last_summary_time = time.time()

            logger.info(
                f"SummaryEngine: Summary generated in {result.latency_ms:.0f}ms "
                f"(stage={result.stage_hint}, points={len(result.key_points)})"
            )

            if self.on_summary:
                self.on_summary(result)

        except json.JSONDecodeError as e:
            logger.error(f"SummaryEngine: Failed to parse JSON: {e}")
            result = SummaryResult(
                timestamp=time.time(),
                latency_ms=(time.time() - start_time) * 1000,
                error=f"JSON parse error: {e}",
            )
            self.current_summary = result
            if self.on_summary:
                self.on_summary(result)

        except Exception as e:
            logger.error(f"SummaryEngine: Error generating summary: {e}", exc_info=True)
            result = SummaryResult(
                timestamp=time.time(),
                latency_ms=(time.time() - start_time) * 1000,
                error=str(e),
            )
            if self.on_summary:
                self.on_summary(result)
