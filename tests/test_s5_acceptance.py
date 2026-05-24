"""
Red Gate Tests — Acceptance criteria for S5-02 through S5-08.

Written BEFORE implementation. All tests must FAIL to prove features don't exist yet.
Ralph builds against these tests to make them PASS.

Story acceptance criteria from prd.json.
"""

import inspect
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np


# ──────────────────────────────────────────────────────────────
# S5-02: Fix mic cutoff bug with root-cause specification
# AC: VadTranscriber handles partial audio chunks without dropping segments
# AC: Test validates audio continuity across chunk boundaries
# ──────────────────────────────────────────────────────────────
class TestS5_02_MicCutoff(unittest.TestCase):
    """
    The mic cutoff bug: audio sometimes cuts off mid-sentence.
    Root cause is likely in VadTranscriber's handling of chunk boundaries —
    the remainder buffer or VAD state resets incorrectly between chunks.
    """

    def _make_speech_chunk(self, duration_ms: int, freq_hz: int = 440) -> bytes:
        """Generate synthetic Int16 PCM speech-like audio at 16kHz."""
        sample_rate = 16000
        num_samples = int(sample_rate * duration_ms / 1000)
        t = np.linspace(0, duration_ms / 1000, num_samples, endpoint=False)
        # Sine wave at speech-like frequency with amplitude that triggers VAD
        audio = (np.sin(2 * np.pi * freq_hz * t) * 16000).astype(np.int16)
        return audio.tobytes()

    def _make_silence_chunk(self, duration_ms: int) -> bytes:
        """Generate silent Int16 PCM audio."""
        sample_rate = 16000
        num_samples = int(sample_rate * duration_ms / 1000)
        return np.zeros(num_samples, dtype=np.int16).tobytes()

    def _make_vad_with_mocked_models(self, **kwargs):
        """Create a VadTranscriber that tests stream continuity, not model quality."""
        from src.realtime.vad_transcriber import VadTranscriber

        class FakeVadProbability:
            def __init__(self, value: float):
                self.value = value

            def item(self):
                return self.value

        class AmplitudeVad:
            def __call__(self, tensor, _sample_rate):
                audio = tensor.detach().cpu().numpy()
                return FakeVadProbability(0.95 if np.max(np.abs(audio)) > 0.01 else 0.0)

            def reset_states(self):
                pass

        def fake_load_vad(transcriber):
            transcriber._vad_model = AmplitudeVad()

        def fake_load_whisper(transcriber):
            transcriber._whisper = MagicMock()
            transcriber._whisper_lock = threading.Lock()

        def fake_transcribe_audio(audio):
            return "hello from split chunks" if np.max(np.abs(audio)) > 0.01 else ""

        with (
            patch.object(VadTranscriber, "_load_vad", fake_load_vad),
            patch.object(VadTranscriber, "_load_whisper", fake_load_whisper),
        ):
            vad = VadTranscriber(model="base", device="cpu", **kwargs)
            vad._transcribe_audio = fake_transcribe_audio
            return vad

    def test_partial_chunks_no_dropped_segments(self):
        """Audio split across chunk boundaries must not drop segments.

        Simulates a sentence split across two small chunks (like browser
        MediaRecorder producing 100ms chunks). The VadTranscriber remainder
        buffer must carry partial VAD windows across feed() calls. VAD and
        Whisper are mocked so this test only measures audio continuity; a pure
        sine fixture is not a valid probe of real Silero/Whisper acceptance.
        """
        vad = self._make_vad_with_mocked_models(silence_threshold_ms=300)

        # Feed speech in small chunks (simulating browser 100ms chunks)
        # Then silence to finalize
        all_segments = []
        speech = self._make_speech_chunk(500)  # 500ms of speech
        chunk_size = 3200  # 100ms at 16kHz, 2 bytes per sample = 3200 bytes

        for i in range(0, len(speech), chunk_size):
            chunk = speech[i : i + chunk_size]
            segments = vad.feed(chunk)
            all_segments.extend(segments)

        # Feed silence to trigger finalization
        silence = self._make_silence_chunk(500)
        for i in range(0, len(silence), chunk_size):
            chunk = silence[i : i + chunk_size]
            segments = vad.feed(chunk)
            all_segments.extend(segments)

        # Flush remaining
        final = vad.flush()
        all_segments.extend(final)

        # Must have at least one segment — no dropped audio
        self.assertEqual(len(all_segments), 1)
        self.assertEqual(all_segments[0]["text"], "hello from split chunks")
        self.assertTrue(all_segments[0]["completed"])
        self.assertAlmostEqual(all_segments[0]["start"], 0.0, places=3)
        self.assertGreaterEqual(all_segments[0]["end"], 0.48)
        self.assertEqual(len(vad._remainder), 0)

    def test_remainder_buffer_continuity(self):
        """Remainder samples from one feed() call must be prepended to the next.

        VAD processes in 512-sample windows. If a chunk has 700 samples,
        512 are processed and 188 must be saved. The next chunk must start
        with those 188 samples prepended.
        """
        try:
            vad = self._make_vad_with_mocked_models()
        except ImportError:
            self.skipTest("VadTranscriber dependencies not available")
        except Exception:
            self.skipTest("Cannot initialize VadTranscriber")

        # Feed a chunk that's NOT a multiple of VAD_CHUNK_SIZE (512 samples = 1024 bytes)
        # 700 samples = 1400 bytes → 512 processed, 188 remainder
        odd_chunk = self._make_speech_chunk(44)  # ~700 samples at 16kHz
        vad.feed(odd_chunk)

        # Remainder should exist
        self.assertGreater(
            len(vad._remainder), 0, "After feeding a non-aligned chunk, remainder buffer should have leftover samples."
        )

        # Feed another chunk — remainder should be prepended (not lost)
        remainder_before = len(vad._remainder)
        next_chunk = self._make_speech_chunk(100)  # 1600 samples
        vad.feed(next_chunk)

        # Total samples processed should account for remainder + new chunk
        # (remainder should have been consumed, not dropped)
        # This is a structural test — the key invariant is that no samples are lost
        total_expected = remainder_before + (1600)  # remainder + new samples
        # After processing, new remainder should be total_expected % 512
        expected_new_remainder = total_expected % vad.VAD_CHUNK_SIZE
        self.assertEqual(
            len(vad._remainder),
            expected_new_remainder,
            f"Remainder mismatch: expected {expected_new_remainder} samples, "
            f"got {len(vad._remainder)}. Samples may be lost across chunk boundaries.",
        )

    def test_root_cause_documented(self):
        """Root cause must be documented in specs/buffer_manager.md."""
        spec_path = Path(__file__).parent.parent / "specs" / "buffer_manager.md"
        self.assertTrue(spec_path.exists(), "specs/buffer_manager.md must exist")

        content = spec_path.read_text()
        # Must document the mic cutoff root cause
        self.assertTrue(
            "mic cutoff" in content.lower()
            or "audio continuity" in content.lower()
            or "chunk boundary" in content.lower()
            or "partial audio" in content.lower(),
            "specs/buffer_manager.md must document mic cutoff root cause. "
            "Look for 'mic cutoff', 'audio continuity', 'chunk boundary', or 'partial audio'.",
        )


# ──────────────────────────────────────────────────────────────
# S5-03: WebSocket error handling and reconnection spec
# AC: WebSocket connection drop detected within 5 seconds
# AC: Client reconnection re-sends transcript history
# AC: Server handles half-open connections gracefully
# AC: Test validates reconnection preserves coaching state
# ──────────────────────────────────────────────────────────────
class TestS5_03_WebSocketReconnection(unittest.TestCase):
    """WebSocket error handling and reconnection."""

    def test_connection_drop_detection_timeout(self):
        """Server must detect connection drops within 5 seconds.

        This requires a heartbeat/ping mechanism. Currently no ping
        interval is configured on the server-side WebSocket.
        """

        # Check that the app has WebSocket ping configuration
        # or a heartbeat mechanism in the connection manager
        from src.web.app import ConnectionManager

        manager = ConnectionManager()

        # ConnectionManager should have a heartbeat/ping interval
        has_heartbeat = (
            hasattr(manager, "ping_interval")
            or hasattr(manager, "heartbeat_interval")
            or hasattr(manager, "connection_timeout")
        )
        self.assertTrue(
            has_heartbeat,
            "ConnectionManager must have a heartbeat/ping mechanism to detect "
            "connection drops within 5 seconds. Currently has no such attribute.",
        )

    def test_reconnection_sends_transcript_history(self):
        """On reconnection, client must receive full transcript history.

        This already works for monitors via ConnectionManager.connect(),
        but there's no mechanism for a recorder to resume a session.
        """
        from src.web.app import ConnectionManager

        manager = ConnectionManager()

        # Add some transcript history
        manager.transcript_history = [
            {"type": "transcript", "text": "Hello", "start": 0, "end": 1, "is_final": True},
            {"type": "transcript", "text": "World", "start": 1, "end": 2, "is_final": True},
        ]

        # There should be a method to get session state for reconnection
        has_session_state = hasattr(manager, "get_session_state") or hasattr(manager, "get_reconnection_payload")
        self.assertTrue(
            has_session_state,
            "ConnectionManager must have get_session_state() or similar for reconnection to preserve coaching state.",
        )

    def test_half_open_connection_cleanup(self):
        """Server must handle half-open connections (client gone, no FIN).

        This requires periodic liveness checks on active_connections.
        """
        from src.web.app import ConnectionManager

        manager = ConnectionManager()

        has_cleanup = (
            hasattr(manager, "cleanup_stale_connections")
            or hasattr(manager, "check_connections")
            or hasattr(manager, "_cleanup_task")
        )
        self.assertTrue(
            has_cleanup,
            "ConnectionManager must have a mechanism to clean up half-open connections. "
            "Currently relies only on broadcast failure detection.",
        )


# ──────────────────────────────────────────────────────────────
# S5-04: Context engine Layer 2 (Hardly Selling transcriptions)
# AC: Hardly Selling methodology loaded as retrievable context layer
# AC: Context engine selects relevant methodology sections per call phase
# AC: Coaching suggestions reference specific Hardly Selling techniques
# AC: RAG pipeline supports multi-source retrieval (script + methodology)
# ──────────────────────────────────────────────────────────────
class TestS5_04_ContextEngine(unittest.TestCase):
    """Context engine Layer 2 with Hardly Selling methodology."""

    def test_hardly_selling_as_rag_source(self):
        """Hardly Selling methodology must be a separate retrievable RAG source.

        Currently embedded inline in prompts.py. Should be a knowledge_base
        document indexed by the RAG pipeline alongside the sales script.
        """
        # Check for Hardly Selling as a separate knowledge base document
        kb_dir = Path(__file__).parent.parent / "knowledge_base"
        hardly_selling_files = list(kb_dir.glob("*hardly*")) + list(kb_dir.glob("*methodology*"))

        self.assertGreater(
            len(hardly_selling_files),
            0,
            "Hardly Selling methodology must exist as a separate file in knowledge_base/ "
            "for RAG retrieval. Currently embedded inline in prompts.py.",
        )

    def test_multi_source_retrieval(self):
        """RAG pipeline must support retrieving from multiple sources."""
        # Check if retriever supports multiple sources/collections
        from src.rag.retriever import ScriptRetriever

        # ScriptRetriever should accept multiple stores or have multi-source capability
        has_multi_source = (
            hasattr(ScriptRetriever, "add_source")
            or "sources" in ScriptRetriever.__init__.__code__.co_varnames
            or "stores" in ScriptRetriever.__init__.__code__.co_varnames
        )
        self.assertTrue(
            has_multi_source,
            "ScriptRetriever must support multi-source retrieval (script + methodology). "
            "Currently only supports a single store.",
        )

    def test_phase_specific_methodology_selection(self):
        """Context engine must select relevant Hardly Selling sections per call phase."""
        # There should be a mapping from call phases to methodology sections
        from src.realtime.prompts import SEMANTIC_BLUEPRINTS

        # Each blueprint should reference specific Hardly Selling techniques
        for stage, blueprint in SEMANTIC_BLUEPRINTS.items():
            self.assertIn(
                "hardly" if isinstance(blueprint, str) else "",
                blueprint.lower() if isinstance(blueprint, str) else "",
                f"Blueprint for '{stage}' must reference Hardly Selling techniques. "
                f"Currently uses generic prompts without methodology references.",
            )


# ──────────────────────────────────────────────────────────────
# S5-05: Optimize latency below 3 seconds for coaching suggestions
# AC: End-to-end latency from speech to coaching suggestion < 3 seconds
# AC: Streaming LLM responses display incrementally in UI
# AC: Latency benchmark test records p50 and p95 measurements
# AC: Fallback to faster model if primary model exceeds 5s timeout
# ──────────────────────────────────────────────────────────────
class TestS5_05_Latency(unittest.TestCase):
    """Latency optimization below 3 seconds."""

    def test_streaming_response_support(self):
        """StreamingAnalyzer must support streaming (chunked) LLM responses.

        Currently uses non-streaming chat.completions.create().
        Must use stream=True for incremental display.
        """
        from src.realtime.analysis_orchestrator import StreamingAnalyzer

        source = inspect.getsource(StreamingAnalyzer.analyze)
        self.assertIn(
            "stream",
            source.lower(),
            "StreamingAnalyzer.analyze() must use streaming responses (stream=True). "
            "Currently uses blocking non-streaming calls.",
        )

    def test_model_fallback_on_timeout(self):
        """Must fallback to faster model if primary exceeds 5s timeout.

        Currently no fallback mechanism exists.
        """
        from src.realtime.analysis_orchestrator import StreamingAnalyzer

        has_fallback = (
            hasattr(StreamingAnalyzer, "fallback_model")
            or hasattr(StreamingAnalyzer, "_try_with_fallback")
            or "fallback" in inspect.getsource(StreamingAnalyzer.__init__).lower()
        )

        self.assertTrue(
            has_fallback,
            "StreamingAnalyzer must have a fallback model for when primary exceeds 5s. "
            "Currently no fallback mechanism exists.",
        )

    def test_latency_benchmark_infrastructure(self):
        """Latency benchmark test must record and assert p50 < 3s and p95 < 5s."""
        benchmark_files = list(Path(__file__).parent.glob("*latency*")) + list(
            Path(__file__).parent.glob("*benchmark*")
        )

        # Check for a benchmark that actually asserts p50/p95 thresholds
        found_assertions = False
        for f in benchmark_files:
            content = f.read_text()
            # Must have actual threshold assertions, not just mentions
            if (
                "p50" in content
                and "p95" in content
                and ("assert" in content.lower() or "< 3" in content or "< 5" in content)
            ):
                found_assertions = True
                break

        self.assertTrue(
            found_assertions,
            "Must have a latency benchmark asserting p50 < 3s and p95 < 5s thresholds. "
            "test_llm_latency.py exists but lacks threshold assertions.",
        )


# ──────────────────────────────────────────────────────────────
# S5-06: Meeting notetaker integration via Vexa
# AC: Audio capture works from Zoom or Google Meet calls
# AC: Both sides of conversation captured (not just mic)
# AC: Integration documented with setup instructions
# AC: Privacy/compliance implications documented
# ──────────────────────────────────────────────────────────────
class TestS5_06_MeetingNotetaker(unittest.TestCase):
    """Meeting notetaker integration via Vexa."""

    def test_vexa_integration_module_exists(self):
        """A Vexa integration module must exist."""
        vexa_files = (
            list(Path(__file__).parent.parent.glob("src/**/vexa*"))
            + list(Path(__file__).parent.parent.glob("src/**/notetaker*"))
            + list(Path(__file__).parent.parent.glob("src/**/meeting_bot*"))
        )
        self.assertGreater(
            len(vexa_files),
            0,
            "Must have a Vexa integration module (src/**/vexa*.py or similar). "
            "No meeting bot integration code exists yet.",
        )

    def test_vexa_setup_documented(self):
        """Setup instructions must exist for Vexa integration."""
        docs_dir = Path(__file__).parent.parent / "docs"
        setup_files = list(docs_dir.glob("*vexa*")) + list(docs_dir.glob("*notetaker-setup*"))

        self.assertGreater(
            len(setup_files),
            0,
            "Must have Vexa setup documentation in docs/. docs/notetaker-research.md exists but no setup instructions.",
        )

    def test_privacy_compliance_documented(self):
        """Privacy/compliance implications must be documented."""
        docs_dir = Path(__file__).parent.parent / "docs"

        # Check notetaker-research.md and any compliance docs
        compliance_found = False
        for doc in docs_dir.glob("*.md"):
            content = doc.read_text().lower()
            if ("compliance" in content or "gdpr" in content or "consent" in content) and (
                "vexa" in content or "notetaker" in content or "meeting" in content
            ):
                compliance_found = True
                break

        self.assertTrue(
            compliance_found,
            "Privacy/compliance implications for meeting capture must be documented. "
            "Need dedicated section covering consent, data handling, GDPR.",
        )


# ──────────────────────────────────────────────────────────────
# S5-07: Security hardening and threat model
# AC: Threat model document covers audio data, LLM API keys, WebSocket
# AC: API keys loaded from env vars only (no hardcoded secrets)
# AC: WebSocket endpoint validates origin header
# AC: LLM prompt injection mitigations documented and tested
# AC: RAG knowledge base integrity check on startup
# ──────────────────────────────────────────────────────────────
class TestS5_07_Security(unittest.TestCase):
    """Security hardening and threat model."""

    def test_threat_model_document_exists(self):
        """Threat model must exist covering audio, API keys, WebSocket."""
        threat_model_paths = (
            list(Path(__file__).parent.parent.glob("docs/*threat*"))
            + list(Path(__file__).parent.parent.glob("specs/*threat*"))
            + list(Path(__file__).parent.parent.glob("*THREAT*"))
        )
        self.assertGreater(
            len(threat_model_paths), 0, "Must have a threat model document. None found in docs/ or specs/."
        )

    def test_no_hardcoded_secrets(self):
        """No API keys hardcoded in source files."""
        src_dir = Path(__file__).parent.parent / "src"
        violations = []

        secret_patterns = [
            "sk-",  # OpenAI key prefix
            "ghp_",  # GitHub token prefix
            "AZURE_OPENAI_API_KEY",  # Hardcoded assignment (not env var read)
        ]

        for py_file in src_dir.rglob("*.py"):
            content = py_file.read_text()
            for line_num, line in enumerate(content.splitlines(), 1):
                # Skip comments and env var reads
                stripped = line.strip()
                if stripped.startswith("#") or "getenv" in line or "os.environ" in line:
                    continue
                # Check for hardcoded key assignments
                if ("api_key" in line.lower() or "token" in line.lower()) and "=" in line:
                    for pattern in secret_patterns[:2]:  # Check prefixes
                        if f'"{pattern}' in line or f"'{pattern}" in line:
                            violations.append(f"{py_file.name}:{line_num}: {stripped[:80]}")

        self.assertEqual(len(violations), 0, "Hardcoded secrets found:\n" + "\n".join(violations))

    def test_websocket_validates_origin(self):
        """WebSocket endpoint must validate Origin header."""
        app_path = Path(__file__).parent.parent / "src" / "web" / "app.py"
        content = app_path.read_text()

        origin_check = "origin" in content.lower() and (
            "allowed_origins" in content.lower()
            or "check_origin" in content.lower()
            or "validate_origin" in content.lower()
            or "cors" in content.lower()
        )
        self.assertTrue(
            origin_check, "WebSocket endpoints must validate Origin header. No origin validation found in app.py."
        )

    def test_prompt_injection_mitigations(self):
        """LLM prompt injection mitigations must be documented with specific defenses."""
        # Must have a dedicated threat model or security doc with specific mitigations
        docs_dir = Path(__file__).parent.parent / "docs"
        specs_dir = Path(__file__).parent.parent / "specs"

        has_specific_mitigations = False
        for search_dir in [docs_dir, specs_dir]:
            if search_dir.exists():
                for doc in search_dir.glob("*.md"):
                    content = doc.read_text().lower()
                    # Must have SPECIFIC mitigations, not just a mention
                    if (
                        "prompt injection" in content
                        and (
                            "mitigation" in content
                            or "defense" in content
                            or "sanitiz" in content
                            or "input validation" in content
                        )
                        and ("transcript" in content or "audio" in content or "user input" in content)
                    ):
                        has_specific_mitigations = True
                        break

        self.assertTrue(
            has_specific_mitigations,
            "Must document specific prompt injection mitigations for transcript/audio input. "
            "A passing mention in MVP reflection is insufficient — need a dedicated security section.",
        )

    def test_rag_integrity_check_on_startup(self):
        """RAG knowledge base must have explicit integrity check on startup."""
        # Must have a dedicated integrity check function that validates
        # knowledge base files haven't been tampered with
        rag_dir = Path(__file__).parent.parent / "src" / "rag"
        if not rag_dir.exists():
            self.skipTest("RAG module not available")

        integrity_found = False
        for py_file in rag_dir.rglob("*.py"):
            content = py_file.read_text()
            # Must have a dedicated integrity check, not just a generic verify/build
            if (
                "integrity_check" in content
                or "verify_knowledge_base" in content
                or "checksum" in content
                or "hash_check" in content
            ):
                integrity_found = True
                break

        self.assertTrue(
            integrity_found,
            "RAG knowledge base must have explicit integrity_check() or verify_knowledge_base() "
            "function. Generic build/verify functions don't count.",
        )


# ──────────────────────────────────────────────────────────────
# S5-08: Overlay UI for desktop (floating coaching widget)
# AC: Desktop overlay renders on top of Zoom/Meet window
# AC: Coaching suggestions appear without switching windows
# AC: Overlay is draggable and resizable
# AC: Hotkey to show/hide overlay
# ──────────────────────────────────────────────────────────────
class TestS5_08_OverlayUI(unittest.TestCase):
    """Overlay UI for desktop (floating coaching widget)."""

    def test_overlay_module_exists(self):
        """Desktop overlay module must exist."""
        overlay_files = (
            list(Path(__file__).parent.parent.glob("src/**/overlay*"))
            + list(Path(__file__).parent.parent.glob("src/**/widget*"))
            + list(Path(__file__).parent.parent.glob("src/**/desktop*"))
        )
        self.assertGreater(
            len(overlay_files), 0, "Must have a desktop overlay module. No overlay/widget/desktop module found in src/."
        )

    def test_overlay_is_always_on_top(self):
        """Overlay window must have always-on-top flag."""
        overlay_files = list(Path(__file__).parent.parent.rglob("*overlay*"))

        if not overlay_files:
            self.fail("No overlay module exists yet.")

        found_always_on_top = False
        for f in overlay_files:
            if f.suffix == ".py":
                content = f.read_text()
                if (
                    "always_on_top" in content.lower()
                    or "topmost" in content.lower()
                    or "set_keep_above" in content.lower()
                    or "wm_attributes" in content.lower()
                ):
                    found_always_on_top = True
                    break

        self.assertTrue(found_always_on_top, "Overlay must have always-on-top window flag.")

    def test_hotkey_binding_exists(self):
        """Overlay must have a hotkey to show/hide."""
        overlay_files = list(Path(__file__).parent.parent.rglob("*overlay*"))

        if not overlay_files:
            self.fail("No overlay module exists yet.")

        found_hotkey = False
        for f in overlay_files:
            if f.suffix == ".py":
                content = f.read_text()
                if (
                    "hotkey" in content.lower()
                    or "keyboard" in content.lower()
                    or "shortcut" in content.lower()
                    or "keybind" in content.lower()
                ):
                    found_hotkey = True
                    break

        self.assertTrue(found_hotkey, "Overlay must have hotkey binding to show/hide.")


if __name__ == "__main__":
    unittest.main()
