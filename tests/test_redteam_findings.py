"""
Red Gate Tests — Spec-derived from red team findings.

These tests MUST FAIL against current code (proving bugs exist).
After Ralph fixes the code, they must pass.

Red team findings (2026-03-10):
  #1 CRITICAL: last_analysis_time never updates without state callback
  #2 HIGH: analyze() return schema wrong in spec (fixed in spec, code correct)
  #3 HIGH: No concurrent recorder protection (integration test, not unit-testable here)
  #4 HIGH: Unbounded transcript growth in SummaryEngine
  #5 HIGH: analyze() can dereference None
  #6 HIGH: VAD path doesn't use DualBufferManager (architecture, not unit-testable)
  #7 MEDIUM: SummaryEngine race condition
  #8 MEDIUM: Azure deployment can be empty string
  #9 MEDIUM: _processed_segment_keys grows unbounded
  #10 MEDIUM: LLMConfig repr exposes API keys
"""

import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from src.realtime.buffer_manager import DualBufferManager, BufferConfig, Segment
from src.realtime.llm_provider import LLMConfig, get_llm_config


# ──────────────────────────────────────────────────────────────
# #1 CRITICAL: last_analysis_time never updates without state callback
# ──────────────────────────────────────────────────────────────
class TestLastAnalysisTimeUpdates(unittest.TestCase):
    """
    Spec: buffer_manager.md — Invariant #5
    Bug: last_analysis_time update is inside _check_state_trigger(), which
    returns early if on_state_analysis_ready is None. Without a state callback,
    last_analysis_time never updates after init, causing the time threshold to
    fire on every single chunk → LLM request flooding.
    """

    def test_last_analysis_time_updates_without_state_callback(self):
        """last_analysis_time must update on rotation even without state callback."""
        config = BufferConfig(
            time_threshold_seconds=5.0,
            min_completed_segments=100,  # High so only time triggers
            min_characters=10000,
            sentence_end_triggers=False,
            silence_threshold_seconds=100.0,
        )
        mock_analysis = MagicMock()
        # No state callback — this is the bug trigger
        manager = DualBufferManager(config, mock_analysis)

        # Set initial time
        with patch("time.time", return_value=1000.0):
            manager.last_analysis_time = 1000.0

        # First chunk at t=1006 (6s > 5s threshold) → should trigger
        seg1 = {"text": "Hello there.", "start": 0.0, "end": 1.0, "completed": True}
        with patch("time.time", return_value=1006.0):
            manager.on_transcript_chunk("Hello there.", [seg1])

        self.assertEqual(mock_analysis.call_count, 1, "First trigger should fire")

        # After rotation, last_analysis_time should be ~1006
        # Now send another chunk at t=1007 (only 1s later) → should NOT trigger
        seg2 = {"text": "How are you.", "start": 2.0, "end": 3.0, "completed": True}
        with patch("time.time", return_value=1007.0):
            manager.on_transcript_chunk("How are you.", [seg2])

        self.assertEqual(
            mock_analysis.call_count,
            1,
            "Second chunk 1s after rotation should NOT trigger (5s threshold). "
            "If this fails, last_analysis_time is not updating on rotation.",
        )

    def test_no_llm_flooding_without_state_callback(self):
        """Rapid chunks after first trigger must not each fire analysis."""
        config = BufferConfig(
            time_threshold_seconds=10.0,
            min_completed_segments=100,
            min_characters=10000,
            sentence_end_triggers=False,
            silence_threshold_seconds=100.0,
        )
        mock_analysis = MagicMock()
        manager = DualBufferManager(config, mock_analysis)

        # Initial trigger at t=1011 (11s > 10s)
        with patch("time.time", return_value=1000.0):
            manager.last_analysis_time = 1000.0

        seg = {"text": "Trigger chunk.", "start": 0.0, "end": 1.0, "completed": True}
        with patch("time.time", return_value=1011.0):
            manager.on_transcript_chunk("Trigger chunk.", [seg])

        self.assertEqual(mock_analysis.call_count, 1)

        # Now send 5 rapid chunks at t=1012..1016 — none should trigger
        for i in range(5):
            t = 1012.0 + i
            s = {"text": f"Rapid {i}.", "start": float(2 + i), "end": float(3 + i), "completed": True}
            with patch("time.time", return_value=t):
                manager.on_transcript_chunk(f"Rapid {i}.", [s])

        self.assertEqual(
            mock_analysis.call_count,
            1,
            f"Expected 1 trigger total, got {mock_analysis.call_count}. "
            "LLM request flooding detected.",
        )


# ──────────────────────────────────────────────────────────────
# #5 HIGH: analyze() can dereference None
# ──────────────────────────────────────────────────────────────
class TestAnalyzeNoneContent(unittest.TestCase):
    """
    Spec: analysis_orchestrator.md — Edge case #9
    Bug: response.choices[0].message.content can be None.
    recommend() guards with `or ""` but analyze() does not.
    """

    def test_analyze_handles_none_content(self):
        """analyze() must not crash when LLM returns None content."""
        from unittest.mock import patch, MagicMock
        from src.realtime.analysis_orchestrator import StreamingAnalyzer

        # Create analyzer with mock client
        with patch("src.realtime.analysis_orchestrator.OpenAI"):
            analyzer = StreamingAnalyzer(
                api_key="test-key",
                base_url="http://localhost:8080/v1",
                model="test-model",
            )

        # Mock LLM response with None content
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None
        analyzer.client.chat.completions.create.return_value = mock_response

        # Should not raise AttributeError
        try:
            result = analyzer.analyze("some text", "some context")
            # Result should be empty or handle gracefully
            self.assertIsNotNone(result)
        except (AttributeError, TypeError) as e:
            self.fail(
                f"analyze() crashed on None content: {e}. "
                "Must guard with `content = ... or ''` like recommend() does."
            )


# ──────────────────────────────────────────────────────────────
# #8 MEDIUM: Azure deployment can be empty string
# ──────────────────────────────────────────────────────────────
class TestAzureDeploymentValidation(unittest.TestCase):
    """
    Spec: llm_provider.md — Edge case #7
    Bug: AZURE_OPENAI_DEPLOYMENT defaults to "" but is not validated.
    Produces malformed base_url and empty model.
    """

    def test_azure_rejects_empty_deployment(self):
        """Azure provider must reject empty deployment name."""
        env = {
            "AZURE_OPENAI_API_KEY": "test-key",
            "AZURE_OPENAI_ENDPOINT": "https://myendpoint.openai.azure.com",
            "AZURE_OPENAI_DEPLOYMENT": "",
        }
        with patch.dict("os.environ", env, clear=False):
            with self.assertRaises(ValueError, msg="Empty deployment should raise ValueError"):
                get_llm_config("azure")

    def test_azure_rejects_missing_deployment(self):
        """Azure provider must reject when deployment env var not set."""
        env = {
            "AZURE_OPENAI_API_KEY": "test-key",
            "AZURE_OPENAI_ENDPOINT": "https://myendpoint.openai.azure.com",
        }
        # Remove AZURE_OPENAI_DEPLOYMENT if it exists
        with patch.dict("os.environ", env, clear=False):
            with patch.dict("os.environ", {}, clear=False):
                # getenv returns "" by default for this var
                with self.assertRaises(ValueError, msg="Missing deployment should raise ValueError"):
                    get_llm_config("azure")


# ──────────────────────────────────────────────────────────────
# #9 MEDIUM: _processed_segment_keys grows unbounded
# ──────────────────────────────────────────────────────────────
class TestProcessedKeysCleanup(unittest.TestCase):
    """
    Spec: buffer_manager.md — Edge case #9
    Bug: _processed_segment_keys accumulates every key ever seen.
    Should be pruned during rotation.
    """

    def test_processed_keys_bounded_after_rotation(self):
        """_processed_segment_keys should not grow without bound."""
        config = BufferConfig(
            time_threshold_seconds=1.0,
            min_completed_segments=2,
            min_characters=10000,
            sentence_end_triggers=False,
            silence_threshold_seconds=100.0,
        )
        mock_analysis = MagicMock()
        manager = DualBufferManager(config, mock_analysis)

        # Feed 100 unique segments, triggering many rotations
        with patch("time.time", return_value=1000.0):
            manager.last_analysis_time = 1000.0

        for i in range(100):
            seg = {"text": f"Segment {i}.", "start": float(i), "end": float(i + 0.5), "completed": True}
            with patch("time.time", return_value=1000.0 + i):
                manager.on_transcript_chunk(f"Segment {i}.", [seg])

        # After many rotations, processed keys should be bounded
        # (only keys for segments still in context_buffer + active_buffer)
        max_expected = len(manager.context_buffer) + len(manager.active_buffer) + 50  # generous margin
        self.assertLessEqual(
            len(manager._processed_segment_keys),
            max_expected,
            f"_processed_segment_keys has {len(manager._processed_segment_keys)} entries "
            f"but only {len(manager.context_buffer) + len(manager.active_buffer)} segments in buffers. "
            "Keys should be pruned during rotation.",
        )


# ──────────────────────────────────────────────────────────────
# #10 MEDIUM: LLMConfig repr exposes API keys
# ──────────────────────────────────────────────────────────────
class TestLLMConfigReprSafety(unittest.TestCase):
    """
    Spec: llm_provider.md — Edge case #8
    Bug: Default dataclass __repr__ prints full api_key in logs/tracebacks.
    """

    def test_repr_masks_api_key(self):
        """LLMConfig repr must not expose full API key."""
        config = LLMConfig(
            api_key="sk-1234567890abcdef1234567890abcdef",
            base_url="https://api.openai.com/v1",
            model="gpt-4o-mini",
            provider="openai",
        )
        repr_str = repr(config)
        self.assertNotIn(
            "sk-1234567890abcdef1234567890abcdef",
            repr_str,
            "Full API key exposed in repr(). Override __repr__ to mask it.",
        )

    def test_str_masks_api_key(self):
        """LLMConfig str must not expose full API key."""
        config = LLMConfig(
            api_key="ghp_abcdefghijklmnopqrstuvwxyz123456",
            base_url="https://models.github.ai/inference",
            model="gpt-4o-mini",
            provider="github",
        )
        str_output = str(config)
        self.assertNotIn(
            "ghp_abcdefghijklmnopqrstuvwxyz123456",
            str_output,
            "Full API key exposed in str(). Override __repr__ to mask it.",
        )


# ──────────────────────────────────────────────────────────────
# #4 HIGH: Unbounded transcript growth in SummaryEngine
# ──────────────────────────────────────────────────────────────
class TestSummaryEngineTranscriptBound(unittest.TestCase):
    """
    Spec: summary_engine.md — Edge case #9
    Bug: _transcript_lines grows forever. Full transcript sent to LLM every
    cycle. Multi-hour calls exceed model context window.
    """

    def test_transcript_has_max_size(self):
        """SummaryEngine should bound transcript size."""
        from src.realtime.summary_engine import SummaryEngine

        mock_client = MagicMock()
        engine = SummaryEngine(client=mock_client, model="test")

        # Simulate 2-hour call: ~7200 transcript lines
        for i in range(7200):
            engine.add_transcript(f"This is transcript line number {i} with some realistic length content.")

        transcript = engine.get_full_transcript()
        # A reasonable bound: 100K characters (fits in most model context windows)
        # Full 7200 lines × ~70 chars = ~504K characters — way too much
        max_chars = 100_000
        self.assertLessEqual(
            len(transcript),
            max_chars,
            f"Transcript is {len(transcript)} chars after 7200 lines. "
            f"Must be bounded to ~{max_chars} chars to avoid exceeding model context window.",
        )


# ──────────────────────────────────────────────────────────────
# Buffer manager reset() should clear full_history
# Spec: buffer_manager.md — Edge case #8
# ──────────────────────────────────────────────────────────────
class TestResetClearsFullHistory(unittest.TestCase):
    """
    Spec: buffer_manager.md — Edge case #8
    Bug: reset() clears active and context but NOT full_history.
    """

    def test_reset_clears_full_history(self):
        """reset() must clear full_history."""
        config = BufferConfig()
        manager = DualBufferManager(config, MagicMock())

        # Add some segments to full_history via rotation
        manager.active_buffer = [
            Segment(text="Test segment", start=0.0, end=1.0, completed=True)
        ]
        manager.rotate_buffers()
        self.assertGreater(len(manager.full_history), 0, "Setup: full_history should have data")

        manager.reset()
        self.assertEqual(
            len(manager.full_history),
            0,
            "reset() must clear full_history. Currently it only clears active and context.",
        )


if __name__ == "__main__":
    unittest.main()
