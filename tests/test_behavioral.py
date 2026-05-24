"""
Behavioral integration tests for Sales RPG AI Phase 5.

These tests verify actual functionality — not file existence or attribute presence.
They exercise real code paths with mocked external dependencies (LLM APIs, WebSockets).
"""

import asyncio
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure project root is on path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# ──────────────────────────────────────────────────────────────
# Buffer Manager: End-to-end behavioral tests
# ──────────────────────────────────────────────────────────────
class TestBufferManagerBehavior(unittest.TestCase):
    """DualBufferManager triggers analysis at the right time with the right data."""

    def setUp(self):
        from src.realtime.buffer_manager import BufferConfig, DualBufferManager

        self.callbacks = []
        self.config = BufferConfig(
            time_threshold_seconds=100,  # high so time doesn't interfere
            min_completed_segments=2,
            min_characters=500,
            silence_threshold_seconds=100,
            sentence_end_triggers=False,
        )
        self.manager = DualBufferManager(
            config=self.config,
            on_analysis_ready=lambda a, c: self.callbacks.append((a, c)),
        )

    def test_triggers_on_segment_count(self):
        """Two completed segments triggers analysis callback with their text."""
        self.manager.on_transcript_chunk(
            "Hello there",
            [
                {"text": "Hello there", "start": 0.0, "end": 1.5, "completed": True},
            ],
        )
        self.assertEqual(len(self.callbacks), 0, "Should not trigger on 1 segment")

        self.manager.on_transcript_chunk(
            "how are you",
            [
                {"text": "how are you", "start": 1.5, "end": 3.0, "completed": True},
            ],
        )
        self.assertEqual(len(self.callbacks), 1, "Should trigger on 2 segments")
        active_text, context_text = self.callbacks[0]
        self.assertIn("Hello there", active_text)
        self.assertIn("how are you", active_text)

    def test_rotation_moves_active_to_context(self):
        """After trigger, active buffer empties and context holds previous segments."""
        self.manager.on_transcript_chunk(
            "seg one",
            [
                {"text": "seg one", "start": 0.0, "end": 1.0, "completed": True},
            ],
        )
        self.manager.on_transcript_chunk(
            "seg two",
            [
                {"text": "seg two", "start": 1.0, "end": 2.0, "completed": True},
            ],
        )
        # After trigger + rotation
        self.assertEqual(len(self.manager.active_buffer), 0, "Active buffer should be empty after rotation")
        self.assertGreater(len(self.manager.context_buffer), 0, "Context buffer should have segments")

    def test_dedup_prevents_reprocessing(self):
        """Same segment sent twice is only processed once."""
        seg = {"text": "Hello", "start": 0.0, "end": 1.0, "completed": True}
        self.manager.on_transcript_chunk("Hello", [seg])
        self.manager.on_transcript_chunk("Hello", [seg])
        self.assertEqual(len(self.manager.active_buffer), 1)

    def test_no_llm_flooding_without_state_callback(self):
        """Without on_state_analysis_ready, last_analysis_time still updates on rotation.

        This was the LLM flooding bug: last_analysis_time was only updated inside
        _check_state_trigger() which returned early without a state callback.
        """
        from src.realtime.buffer_manager import BufferConfig, DualBufferManager

        config = BufferConfig(
            time_threshold_seconds=0.01,  # very low
            min_completed_segments=100,
            min_characters=10000,
            silence_threshold_seconds=100,
            sentence_end_triggers=False,
        )
        callbacks = []
        mgr = DualBufferManager(
            config=config,
            on_analysis_ready=lambda a, c: callbacks.append(1),
            on_state_analysis_ready=None,  # No state callback — the bug trigger
        )
        # First chunk triggers on time (elapsed > 0.01s)
        time.sleep(0.02)
        mgr.on_transcript_chunk(
            "Hello",
            [
                {"text": "Hello", "start": 0.0, "end": 1.0, "completed": True},
            ],
        )
        count_after_first = len(callbacks)

        # Second chunk immediately — should NOT trigger because last_analysis_time was just updated
        mgr.on_transcript_chunk(
            "World",
            [
                {"text": "World", "start": 1.0, "end": 2.0, "completed": True},
            ],
        )
        self.assertEqual(
            len(callbacks),
            count_after_first,
            "Second immediate chunk should NOT trigger (last_analysis_time must update on rotation)",
        )

    def test_sentence_end_triggers_analysis(self):
        """Sentence-ending punctuation triggers analysis."""
        self.config.sentence_end_triggers = True
        self.manager.on_transcript_chunk(
            "The price is too high.",
            [
                {"text": "The price is too high.", "start": 0.0, "end": 2.0, "completed": True},
            ],
        )
        self.assertEqual(len(self.callbacks), 1, "Sentence ending should trigger analysis")

    def test_context_buffer_trimming(self):
        """Context buffer is trimmed to max_context_segments after rotation."""
        self.config.max_context_segments = 3
        self.config.min_completed_segments = 1  # trigger on every segment

        for i in range(10):
            self.manager.on_transcript_chunk(
                f"seg {i}",
                [
                    {"text": f"seg {i}", "start": float(i), "end": float(i + 1), "completed": True},
                ],
            )
        self.assertLessEqual(
            len(self.manager.context_buffer), 3, "Context buffer must be trimmed to max_context_segments"
        )

    def test_reset_clears_everything(self):
        """reset() clears active, context, full_history, and tracking state."""
        self.manager.on_transcript_chunk(
            "Hello",
            [
                {"text": "Hello", "start": 0.0, "end": 1.0, "completed": True},
            ],
        )
        self.manager.on_transcript_chunk(
            "World",
            [
                {"text": "World", "start": 1.0, "end": 2.0, "completed": True},
            ],
        )
        self.manager.reset()
        self.assertEqual(len(self.manager.active_buffer), 0)
        self.assertEqual(len(self.manager.context_buffer), 0)
        self.assertEqual(len(self.manager.full_history), 0)
        self.assertEqual(len(self.manager._processed_segment_keys), 0)

    def test_incomplete_segment_included_in_payload(self):
        """get_analysis_payload() includes the last incomplete segment text."""
        self.manager.on_transcript_chunk(
            "Hello partial",
            [
                {"text": "Hello", "start": 0.0, "end": 1.0, "completed": True},
                {"text": "partial", "start": 1.0, "end": 1.5, "completed": False},
            ],
        )
        active, _ = self.manager.get_analysis_payload()
        self.assertIn("partial", active, "Incomplete segment should be in active payload")

    def test_processed_keys_pruned_on_rotation(self):
        """_processed_segment_keys doesn't grow unbounded — pruned to context window."""
        self.config.max_context_segments = 2
        self.config.min_completed_segments = 1

        for i in range(20):
            self.manager.on_transcript_chunk(
                f"s{i}",
                [
                    {"text": f"s{i}", "start": float(i), "end": float(i + 1), "completed": True},
                ],
            )
        # Keys should be pruned to only those in context buffer
        self.assertLessEqual(
            len(self.manager._processed_segment_keys),
            len(self.manager.context_buffer) + 1,  # +1 for rounding
            "Processed keys should be pruned during rotation",
        )


# ──────────────────────────────────────────────────────────────
# LLM Provider: Each provider returns correct LLMConfig
# ──────────────────────────────────────────────────────────────
class TestLLMProviderBehavior(unittest.TestCase):
    """get_llm_config() returns correct typed LLMConfig for each provider."""

    def test_local_provider_needs_no_key(self):
        """Local provider works without any API key env var."""
        from src.realtime.llm_provider import get_llm_config

        cfg = get_llm_config("local")
        self.assertEqual(cfg.provider, "local")
        self.assertEqual(cfg.api_key, "local")
        self.assertIn("localhost", cfg.base_url)
        self.assertTrue(cfg.model)  # non-empty

    def test_github_provider_requires_token(self):
        """GitHub provider raises ValueError without GITHUB_TOKEN."""
        from src.realtime.llm_provider import get_llm_config

        with patch.dict(os.environ, {"GITHUB_TOKEN": ""}, clear=False):
            # Force empty token
            env_backup = os.environ.pop("GITHUB_TOKEN", None)
            try:
                with self.assertRaises(ValueError) as ctx:
                    get_llm_config("github")
                self.assertIn("GITHUB_TOKEN", str(ctx.exception))
            finally:
                if env_backup:
                    os.environ["GITHUB_TOKEN"] = env_backup

    def test_azure_requires_all_three_vars(self):
        """Azure provider requires key + endpoint + deployment."""
        from src.realtime.llm_provider import get_llm_config

        with patch.dict(
            os.environ,
            {
                "AZURE_OPENAI_API_KEY": "test-key",
                "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com",
                "AZURE_OPENAI_DEPLOYMENT": "",  # missing
            },
            clear=False,
        ):
            with self.assertRaises(ValueError):
                get_llm_config("azure")

    def test_azure_builds_correct_base_url(self):
        """Azure provider builds base_url from endpoint + deployment."""
        from src.realtime.llm_provider import get_llm_config

        with patch.dict(
            os.environ,
            {
                "AZURE_OPENAI_API_KEY": "test-key",
                "AZURE_OPENAI_ENDPOINT": "https://myinstance.openai.azure.com/",
                "AZURE_OPENAI_DEPLOYMENT": "gpt-4",
            },
            clear=False,
        ):
            cfg = get_llm_config("azure")
            self.assertIn("myinstance.openai.azure.com", cfg.base_url)
            self.assertIn("gpt-4", cfg.base_url)
            self.assertFalse(cfg.base_url.count("//") > 1, "Should not double-slash endpoint")

    def test_unknown_provider_raises(self):
        """Unknown provider name raises ValueError with list of valid options."""
        from src.realtime.llm_provider import get_llm_config

        with self.assertRaises(ValueError) as ctx:
            get_llm_config("nonexistent")
        self.assertIn("nonexistent", str(ctx.exception))

    def test_llmconfig_repr_masks_api_key(self):
        """LLMConfig.__repr__ masks API key to prevent accidental logging."""
        from src.realtime.llm_provider import LLMConfig

        cfg = LLMConfig(api_key="sk-1234567890abcdef", base_url="http://x", model="m", provider="p")
        r = repr(cfg)
        self.assertNotIn("1234567890abcdef", r, "Full API key should not appear in repr")
        self.assertIn("sk-1***", r, "First 4 chars + mask should appear")

    def test_all_seven_providers_exist(self):
        """All 7 providers are in SUPPORTED_PROVIDERS list."""
        from src.realtime.llm_provider import SUPPORTED_PROVIDERS

        expected = {"local", "github", "openrouter", "azure", "azure_ai", "openai", "gemini"}
        self.assertEqual(set(SUPPORTED_PROVIDERS), expected)


# ──────────────────────────────────────────────────────────────
# ConnectionManager: Behavioral tests
# ──────────────────────────────────────────────────────────────
class TestConnectionManagerBehavior(unittest.TestCase):
    """ConnectionManager handles WebSocket lifecycle correctly."""

    def _run_async(self, coro):
        """Helper to run async tests."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def _make_mock_ws(self):
        ws = AsyncMock()
        ws.send_json = AsyncMock()
        return ws

    def test_connect_sends_history(self):
        """New connections receive session state and full transcript history."""
        from src.web.app import ConnectionManager

        mgr = ConnectionManager()
        mgr.transcript_history = [
            {"type": "transcript", "text": "Hello"},
            {"type": "transcript", "text": "World"},
        ]
        ws = self._make_mock_ws()

        self._run_async(mgr.connect(ws))

        # Should have called accept() + 2 history sends
        ws.accept.assert_called_once()
        self.assertEqual(ws.send_json.call_count, 3)
        self.assertEqual(ws.send_json.call_args_list[0].args[0]["type"], "session_state")
        self.assertIn(ws, mgr.active_connections)

    def test_broadcast_stores_transcripts(self):
        """Broadcast stores transcript and coaching messages for reconnect replay."""
        from src.web.app import ConnectionManager

        mgr = ConnectionManager()
        ws = self._make_mock_ws()
        mgr.active_connections = [ws]

        msg = {"type": "transcript", "text": "test"}
        self._run_async(mgr.broadcast(msg))
        self._run_async(mgr.broadcast({"type": "analysis", "suggestion": "ask a follow-up"}))

        self.assertEqual(len(mgr.transcript_history), 1)
        self.assertEqual(len(mgr.coaching_history), 1)
        ws.send_json.assert_called_with({"type": "analysis", "suggestion": "ask a follow-up"})

    def test_broadcast_removes_dead_connections(self):
        """Broadcast removes connections that raise on send."""
        from src.web.app import ConnectionManager

        mgr = ConnectionManager()
        dead_ws = self._make_mock_ws()
        dead_ws.send_json.side_effect = Exception("connection closed")
        alive_ws = self._make_mock_ws()
        mgr.active_connections = [dead_ws, alive_ws]

        self._run_async(mgr.broadcast({"type": "analysis", "data": "x"}))

        self.assertNotIn(dead_ws, mgr.active_connections)
        self.assertIn(alive_ws, mgr.active_connections)

    def test_disconnect_removes_connection(self):
        """disconnect() removes the WebSocket from active list."""
        from src.web.app import ConnectionManager

        mgr = ConnectionManager()
        ws = self._make_mock_ws()
        mgr.active_connections = [ws]
        mgr.disconnect(ws)
        self.assertNotIn(ws, mgr.active_connections)

    def test_reset_clears_history_and_notifies(self):
        """reset() clears replay history and sends reset to all connections."""
        from src.web.app import ConnectionManager

        mgr = ConnectionManager()
        ws = self._make_mock_ws()
        mgr.active_connections = [ws]
        mgr.transcript_history = [{"type": "transcript", "text": "old"}]
        mgr.coaching_history = [{"type": "analysis", "suggestion": "old"}]

        self._run_async(mgr.reset())

        self.assertEqual(len(mgr.transcript_history), 0)
        self.assertEqual(len(mgr.coaching_history), 0)
        ws.send_json.assert_called_with({"type": "reset"})

    def test_get_session_state_returns_payload(self):
        """get_session_state() returns history and connection count."""
        from src.web.app import ConnectionManager

        mgr = ConnectionManager()
        mgr.transcript_history = [{"type": "transcript", "text": "hi"}]
        mgr.active_connections = [self._make_mock_ws(), self._make_mock_ws()]

        state = mgr.get_session_state()
        self.assertEqual(len(state["transcript_history"]), 1)
        self.assertEqual(state["recorder_resume"]["supported"], False)
        self.assertEqual(state["active_connections"], 2)

    def test_cleanup_stale_removes_failed_pings(self):
        """cleanup_stale_connections() removes connections that fail ping."""
        from src.web.app import ConnectionManager

        mgr = ConnectionManager()
        good_ws = self._make_mock_ws()
        bad_ws = self._make_mock_ws()
        bad_ws.send_json.side_effect = Exception("gone")
        mgr.active_connections = [good_ws, bad_ws]

        self._run_async(mgr.cleanup_stale_connections())

        self.assertIn(good_ws, mgr.active_connections)
        self.assertNotIn(bad_ws, mgr.active_connections)

    def test_has_connection_timeout(self):
        """ConnectionManager has connection_timeout for drop detection."""
        from src.web.app import ConnectionManager

        mgr = ConnectionManager()
        self.assertLessEqual(mgr.connection_timeout, 5.0, "Connection timeout must be <= 5s for drop detection")

    def test_scheduled_cleanup_loop_removes_stale_connections(self):
        """Runtime cleanup task automatically removes half-open connections."""
        from src.web import app as app_module
        from src.web.app import ConnectionManager

        async def probe():
            original_manager = app_module.manager
            original_task = app_module.connection_cleanup_task
            mgr = ConnectionManager()
            mgr.ping_interval = 0.01
            good_ws = self._make_mock_ws()
            bad_ws = self._make_mock_ws()
            bad_ws.send_json.side_effect = Exception("gone")
            mgr.active_connections = [good_ws, bad_ws]
            app_module.manager = mgr
            app_module.connection_cleanup_task = None
            try:
                app_module.start_connection_cleanup_task()
                deadline = time.time() + 1.0
                while bad_ws in mgr.active_connections and time.time() < deadline:
                    await asyncio.sleep(0.01)
                self.assertNotIn(bad_ws, mgr.active_connections)
                self.assertIn(good_ws, mgr.active_connections)
            finally:
                await app_module.stop_connection_cleanup_task()
                app_module.manager = original_manager
                app_module.connection_cleanup_task = original_task

        self._run_async(probe())

    def test_monitor_websocket_reconnect_replays_session_state(self):
        """Actual monitor WebSocket receives session state and replay history."""
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi[testclient] not installed")

        from src.web import app as app_module

        app_module.manager.transcript_history = [{"type": "transcript", "text": "Hello", "is_final": True}]
        app_module.manager.coaching_history = [{"type": "analysis", "suggestion": "Ask why now"}]
        app_module.knowledge_base_integrity_status = None

        with patch.object(
            app_module,
            "verify_knowledge_base",
            return_value={"valid": True, "files_checked": 2, "errors": []},
        ):
            with TestClient(app_module.app) as client:
                with client.websocket_connect(
                    "/ws/audio?role=monitor",
                    headers={"origin": "http://localhost:8000"},
                ) as websocket:
                    session_state = websocket.receive_json()
                    transcript = websocket.receive_json()
                    coaching = websocket.receive_json()

        self.assertEqual(session_state["type"], "session_state")
        self.assertEqual(session_state["recorder_resume"]["supported"], False)
        self.assertEqual(transcript["text"], "Hello")
        self.assertEqual(coaching["suggestion"], "Ask why now")
        app_module.manager.transcript_history = []
        app_module.manager.coaching_history = []


# ──────────────────────────────────────────────────────────────
# Origin Validation: Actually validates origins
# ──────────────────────────────────────────────────────────────
class TestOriginValidation(unittest.TestCase):
    """validate_origin() accepts/rejects based on ALLOWED_ORIGINS."""

    def _make_ws_with_origin(self, origin):
        """Create a mock WebSocket with the given origin header."""
        ws = MagicMock()
        if origin is None:
            ws.scope = {"headers": []}
        else:
            ws.scope = {"headers": [(b"origin", origin.encode("utf-8"))]}
        return ws

    def test_allows_valid_origin(self):
        from src.web.app import validate_origin

        ws = self._make_ws_with_origin("http://localhost:8000")
        self.assertTrue(validate_origin(ws))

    def test_rejects_invalid_origin(self):
        from src.web.app import validate_origin

        ws = self._make_ws_with_origin("http://evil.example.com")
        self.assertFalse(validate_origin(ws))

    def test_allows_no_origin(self):
        """No Origin header (same-origin or non-browser) is allowed."""
        from src.web.app import validate_origin

        ws = self._make_ws_with_origin(None)
        self.assertTrue(validate_origin(ws))


# ──────────────────────────────────────────────────────────────
# StreamingAnalyzer: Mocked LLM behavioral tests
# ──────────────────────────────────────────────────────────────
class TestStreamingAnalyzerBehavior(unittest.TestCase):
    """StreamingAnalyzer processes streaming responses and handles fallback."""

    def _make_mock_chunk(self, content):
        """Create a mock streaming chunk."""
        chunk = MagicMock()
        choice = MagicMock()
        choice.delta.content = content
        chunk.choices = [choice]
        return chunk

    @patch.dict(os.environ, {"USE_RAG": "false"}, clear=False)
    def test_analyze_collects_streaming_chunks(self):
        """analyze() collects streaming chunks into a complete response."""
        # We need to reload the module to pick up USE_RAG=false
        from src.realtime.analysis_orchestrator import StreamingAnalyzer

        analyzer = StreamingAnalyzer(api_key="test", base_url="http://fake", model="test-model")

        # Mock the client
        mock_response = [
            self._make_mock_chunk('{"script_location":'),
            self._make_mock_chunk(' "Opening",'),
            self._make_mock_chunk(' "key_points": [],'),
            self._make_mock_chunk(' "suggestion": "Ask about needs"}'),
        ]
        analyzer.client = MagicMock()
        analyzer.client.chat.completions.create.return_value = iter(mock_response)

        result = analyzer.analyze("Hello, I'm interested in your product")
        parsed = json.loads(result)
        self.assertEqual(parsed["script_location"], "Opening")
        self.assertEqual(parsed["suggestion"], "Ask about needs")

    @patch.dict(os.environ, {"USE_RAG": "false"}, clear=False)
    def test_analyze_cleans_markdown_wrapping(self):
        """analyze() strips ```json``` markdown from LLM response."""
        from src.realtime.analysis_orchestrator import StreamingAnalyzer

        analyzer = StreamingAnalyzer(api_key="test", base_url="http://fake", model="m")

        mock_response = [
            self._make_mock_chunk('```json\n{"key": "value"}\n```'),
        ]
        analyzer.client = MagicMock()
        analyzer.client.chat.completions.create.return_value = iter(mock_response)

        result = analyzer.analyze("test")
        parsed = json.loads(result)
        self.assertEqual(parsed["key"], "value")

    @patch.dict(os.environ, {"USE_RAG": "false"}, clear=False)
    def test_fallback_triggers_on_timeout(self):
        """_try_with_fallback() switches to fallback_model on timeout."""
        from src.realtime.analysis_orchestrator import StreamingAnalyzer

        analyzer = StreamingAnalyzer(
            api_key="test", base_url="http://fake", model="slow-model", fallback_model="fast-model"
        )

        models_used = []

        def mock_analyze(text, context=""):
            models_used.append(analyzer.model)
            if analyzer.model == "slow-model":
                time.sleep(2)  # Simulate slow response
                return '{"result": "slow"}'
            return '{"result": "fast"}'

        analyzer.analyze = mock_analyze
        result = analyzer._try_with_fallback("test", timeout=0.1)
        parsed = json.loads(result)
        self.assertEqual(parsed["result"], "fast", "Should have used fallback model")
        self.assertIn("fast-model", models_used, "Fallback model should have been tried")

    @patch.dict(os.environ, {"USE_RAG": "false"}, clear=False)
    def test_fallback_raises_without_fallback_model(self):
        """_try_with_fallback() raises TimeoutError when no fallback configured."""
        from src.realtime.analysis_orchestrator import StreamingAnalyzer

        analyzer = StreamingAnalyzer(api_key="test", base_url="http://fake", model="slow-model", fallback_model=None)

        def mock_analyze(text, context=""):
            time.sleep(2)
            return '{"result": "slow"}'

        analyzer.analyze = mock_analyze
        with self.assertRaises(TimeoutError):
            analyzer._try_with_fallback("test", timeout=0.1)


# ──────────────────────────────────────────────────────────────
# AnalysisOrchestrator: Submit → callback lifecycle
# ──────────────────────────────────────────────────────────────
class TestAnalysisOrchestratorBehavior(unittest.TestCase):
    """AnalysisOrchestrator processes queue and delivers results via callback."""

    @patch.dict(os.environ, {"USE_RAG": "false"}, clear=False)
    def test_submit_triggers_callback(self):
        """Submitted analysis is processed and callback receives result."""
        from src.realtime.analysis_orchestrator import AnalysisOrchestrator, StreamingAnalyzer

        analyzer = StreamingAnalyzer(api_key="test", base_url="http://fake", model="m")

        mock_response = iter(
            [
                MagicMock(
                    choices=[
                        MagicMock(
                            delta=MagicMock(
                                content='{"script_location": "Opening", "key_points": [], "suggestion": "test"}'
                            )
                        )
                    ]
                )
            ]
        )
        analyzer.client = MagicMock()
        analyzer.client.chat.completions.create.return_value = mock_response

        results = []
        orch = AnalysisOrchestrator(analyzer, on_result=lambda r: results.append(r))
        orch.start()

        try:
            # Need to re-mock for each call since iter is consumed
            def make_response(*args, **kwargs):
                chunk = MagicMock()
                chunk.choices = [
                    MagicMock(
                        delta=MagicMock(
                            content='{"script_location": "Opening", "key_points": [], "suggestion": "test"}'
                        )
                    )
                ]
                return iter([chunk])

            analyzer.client.chat.completions.create.side_effect = make_response

            orch.submit_analysis("Hello", "")
            time.sleep(1)  # Allow worker to process
            self.assertGreater(len(results), 0, "Callback should receive at least one result")
            self.assertIsNone(results[0].error, f"Result should not have error: {results[0].error}")
            self.assertEqual(results[0].state.script_location, "Opening")
        finally:
            orch.shutdown()

    @patch.dict(os.environ, {"USE_RAG": "false"}, clear=False)
    def test_error_delivered_via_callback(self):
        """LLM errors are caught and delivered as AnalysisResult with error field."""
        from src.realtime.analysis_orchestrator import AnalysisOrchestrator, StreamingAnalyzer

        analyzer = StreamingAnalyzer(api_key="test", base_url="http://fake", model="m")
        analyzer.client = MagicMock()
        analyzer.client.chat.completions.create.side_effect = Exception("API error")

        results = []
        orch = AnalysisOrchestrator(analyzer, on_result=lambda r: results.append(r))
        orch.start()

        try:
            orch.submit_analysis("Hello", "")
            time.sleep(1)
            self.assertGreater(len(results), 0)
            self.assertIsNotNone(results[0].error, "Error result should have error field set")
        finally:
            orch.shutdown()


# ──────────────────────────────────────────────────────────────
# SummaryEngine: Behavioral tests
# ──────────────────────────────────────────────────────────────
class TestSummaryEngineBehavior(unittest.TestCase):
    """SummaryEngine accumulates transcripts and generates summaries."""

    def test_transcript_accumulation(self):
        """add_transcript() accumulates lines retrievable via get_full_transcript()."""
        from src.realtime.summary_engine import SummaryEngine

        mock_client = MagicMock()
        engine = SummaryEngine(client=mock_client, model="m")

        engine.add_transcript("Hello")
        engine.add_transcript("World")
        transcript = engine.get_full_transcript()
        self.assertIn("Hello", transcript)
        self.assertIn("World", transcript)

    def test_transcript_bounded(self):
        """Transcript accumulator trims to _max_transcript_lines."""
        from src.realtime.summary_engine import SummaryEngine

        mock_client = MagicMock()
        engine = SummaryEngine(client=mock_client, model="m")

        for i in range(2000):
            engine.add_transcript(f"Line {i}")

        lines = engine.get_full_transcript().split("\n")
        self.assertLessEqual(
            len(lines),
            engine._max_transcript_lines,
            f"Transcript should be bounded to {engine._max_transcript_lines} lines",
        )

    def test_summary_generation_with_mock_llm(self):
        """refresh() calls LLM and parses JSON into SummaryResult."""
        from src.realtime.summary_engine import SummaryEngine

        mock_client = MagicMock()

        response_json = json.dumps(
            {
                "summary": "Customer discussed pricing",
                "key_points": ["Price concern", "Budget limit"],
                "pain_indicators": ["budget"],
                "stage_hint": "discovery",
                "archetype_hint": "analytical",
            }
        )

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=response_json))]
        mock_client.chat.completions.create.return_value = mock_response

        results = []
        engine = SummaryEngine(
            client=mock_client,
            model="m",
            on_summary=lambda r: results.append(r),
        )
        engine.add_transcript("We talked about the pricing structure")
        engine.refresh()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].summary, "Customer discussed pricing")
        self.assertEqual(results[0].stage_hint, "discovery")
        self.assertIsNone(results[0].error)

    def test_summary_handles_json_parse_error(self):
        """Bad JSON from LLM produces SummaryResult with error field."""
        from src.realtime.summary_engine import SummaryEngine

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="not valid json"))]
        mock_client.chat.completions.create.return_value = mock_response

        results = []
        engine = SummaryEngine(
            client=mock_client,
            model="m",
            on_summary=lambda r: results.append(r),
        )
        engine.add_transcript("some text")
        engine.refresh()

        self.assertEqual(len(results), 1)
        self.assertIsNotNone(results[0].error)
        self.assertIn("JSON", results[0].error)


# ──────────────────────────────────────────────────────────────
# RAG Integrity: Behavioral tests
# ──────────────────────────────────────────────────────────────
class TestRAGIntegrityBehavior(unittest.TestCase):
    """verify_knowledge_base() catches missing, empty, and tampered files."""

    def test_missing_directory_fails(self):
        """Missing knowledge base directory returns valid=False."""
        from src.rag.integrity import verify_knowledge_base

        result = verify_knowledge_base(kb_dir=Path("/nonexistent/path"))
        self.assertFalse(result["valid"])
        self.assertGreater(len(result["errors"]), 0)

    def test_empty_directory_fails(self):
        """Empty knowledge base directory returns valid=False."""
        from src.rag.integrity import verify_knowledge_base

        with tempfile.TemporaryDirectory() as td:
            result = verify_knowledge_base(kb_dir=Path(td))
            self.assertFalse(result["valid"])

    def test_valid_files_pass(self):
        """Directory with non-empty .md files passes."""
        from src.rag.integrity import verify_knowledge_base

        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "script.md").write_text("# Sales Script\nHello!")
            result = verify_knowledge_base(kb_dir=Path(td))
            self.assertTrue(result["valid"])
            self.assertEqual(result["files_checked"], 1)

    def test_empty_file_fails(self):
        """Empty knowledge base file is flagged."""
        from src.rag.integrity import verify_knowledge_base

        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "empty.md").write_text("")
            result = verify_knowledge_base(kb_dir=Path(td))
            self.assertFalse(result["valid"])
            self.assertTrue(any("Empty" in e or "empty" in e for e in result["errors"]))

    def test_checksum_mismatch_detected(self):
        """Tampered file (wrong checksum) is detected."""
        from src.rag.integrity import verify_knowledge_base

        with tempfile.TemporaryDirectory() as td:
            kb_dir = Path(td) / "kb"
            kb_dir.mkdir()
            (kb_dir / "script.md").write_text("Original content")

            checksum_file = Path(td) / "checksums.json"
            checksum_file.write_text(json.dumps({"script.md": "0000000000000000"}))

            result = verify_knowledge_base(kb_dir=kb_dir, checksum_file=checksum_file)
            self.assertFalse(result["valid"])
            self.assertTrue(any("mismatch" in e.lower() for e in result["errors"]))

    def test_actual_knowledge_base_passes(self):
        """The real project knowledge_base/ passes integrity check."""
        from src.rag.integrity import verify_knowledge_base

        kb_dir = project_root / "knowledge_base"
        if not kb_dir.exists():
            self.skipTest("knowledge_base/ not present")
        result = verify_knowledge_base(kb_dir=kb_dir)
        self.assertTrue(result["valid"], f"Real KB failed: {result['errors']}")


class TestStartupIntegrityBehavior(unittest.TestCase):
    """FastAPI startup runs the RAG integrity gate before serving content."""

    def test_startup_invokes_knowledge_base_integrity_check(self):
        """TestClient lifespan calls the startup hook and records non-sensitive status."""
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi[testclient] not installed")

        from src.web import app as app_module

        calls = []

        def fake_verify():
            calls.append(True)
            return {"valid": True, "files_checked": 2, "errors": []}

        app_module.knowledge_base_integrity_status = None
        with patch.object(app_module, "verify_knowledge_base", side_effect=fake_verify):
            with TestClient(app_module.app) as client:
                resp = client.get("/health")

        self.assertTrue(calls, "FastAPI startup must invoke verify_knowledge_base()")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["knowledge_base_integrity"], {"valid": True, "files_checked": 2})

    def test_startup_integrity_failure_blocks_app_start(self):
        """A failed integrity check raises before the app trusts RAG sources."""
        from src.web import app as app_module

        with patch.object(
            app_module,
            "verify_knowledge_base",
            return_value={"valid": False, "files_checked": 0, "errors": ["tampered script.md"]},
        ):
            with self.assertRaisesRegex(RuntimeError, "tampered script.md"):
                app_module.run_startup_integrity_check()


# ──────────────────────────────────────────────────────────────
# FastAPI Health Endpoint
# ──────────────────────────────────────────────────────────────
class TestHealthEndpoint(unittest.TestCase):
    """Health endpoint returns expected payload."""

    def test_health_returns_ok(self):
        """GET /health returns status=ok with connection info."""
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi[testclient] not installed")

        from src.web.app import app

        client = TestClient(app)
        resp = client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("active_connections", data)
        self.assertIn("llm_provider", data)


if __name__ == "__main__":
    unittest.main()
