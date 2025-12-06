#!/usr/bin/env python3
"""
Real-time transcription with streaming objection analysis.

This script integrates WhisperLive with the dual buffer architecture
for real-time objection detection during live audio.

Usage:
    python src/realtime_transcribe.py <audio_file_path>
    python src/realtime_transcribe.py --mic  # Use microphone input
"""

import sys
import os
from pathlib import Path

# Load environment variables from .env file
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()

from realtime import (
    BufferConfig,
    DualBufferManager,
    AnalysisOrchestrator,
    AnalysisResult,
    StreamingAnalyzer,
)


class RealtimeObjectionDetector:
    """
    Real-time objection detector that integrates WhisperLive
    with dual buffer analysis.
    """

    def __init__(
        self,
        api_key: str,
        host: str = "localhost",
        port: int = 9090,
        config: BufferConfig = None,
        verbose: bool = False,
    ):
        """
        Initialize the real-time detector.

        Args:
            api_key: OpenRouter API key
            host: WhisperLive server host
            port: WhisperLive server port
            config: Buffer configuration (uses defaults if not provided)
            verbose: If True, show all LLM responses (not just objections)
        """
        self.host = host
        self.port = port
        self.config = config or BufferConfig()
        self.verbose = verbose

        # Stats
        self.objections_detected = 0
        self.total_analyses = 0

        # Create the streaming analyzer
        self.analyzer = StreamingAnalyzer(api_key=api_key)

        # Create the orchestrator
        self.orchestrator = AnalysisOrchestrator(
            analyzer=self.analyzer,
            on_result=self._on_analysis_result,
        )

        # Create the buffer manager
        self.buffer_manager = DualBufferManager(
            config=self.config,
            on_analysis_ready=self._on_analysis_ready,
        )

    def _on_analysis_ready(self, active_text: str, context_text: str) -> None:
        """Called when buffer manager triggers analysis."""
        print(f"\n[ANALYSIS] Submitting: \"{active_text[:50]}...\"" if len(active_text) > 50 else f"\n[ANALYSIS] Submitting: \"{active_text}\"")
        self.orchestrator.submit_analysis(active_text, context_text)

    def _on_analysis_result(self, result: AnalysisResult) -> None:
        """Called when analysis completes."""
        self.total_analyses += 1

        if result.error:
            print(f"\n[ERROR] Analysis failed: {result.error}")
            return

        if result.has_objection:
            self.objections_detected += 1
            self._display_objection(result)
        elif self.verbose:
            self._display_verbose_result(result)
        else:
            print(f"[RESULT] No objection detected ({result.latency_ms:.0f}ms)")

    def _display_verbose_result(self, result: AnalysisResult) -> None:
        """Display full LLM response (verbose mode)."""
        print(f"\n[LLM RESPONSE] ({result.latency_ms:.0f}ms)")
        print(f"Text analyzed: \"{result.active_text}\"")
        if result.context_text:
            ctx = result.context_text[:80] + "..." if len(result.context_text) > 80 else result.context_text
            print(f"Context: \"{ctx}\"")
        print("-" * 40)
        print(result.raw_response)
        print("-" * 40 + "\n")

    def _display_objection(self, result: AnalysisResult) -> None:
        """Display detected objection prominently."""
        print("\n" + "!" * 60)
        print("!!! OBJECTION DETECTED !!!")
        print("!" * 60)
        print(f"\nText analyzed: \"{result.active_text}\"")
        print(f"\nLLM Response:\n{result.raw_response}")
        print(f"\nLatency: {result.latency_ms:.0f}ms")
        print("!" * 60 + "\n")

    def _on_transcript_chunk(self, text: str, segments: list) -> None:
        """
        Callback for WhisperLive transcription.

        Passes chunks to buffer manager and displays transcript.
        """
        # Display the current transcript
        print(f"[TRANSCRIPT] {text}")

        # Pass to buffer manager
        self.buffer_manager.on_transcript_chunk(text, segments)

    def run_file(self, audio_path: str) -> None:
        """
        Run real-time analysis on an audio file.

        Args:
            audio_path: Path to audio file
        """
        from whisper_live.client import TranscriptionClient

        print(f"\n{'='*60}")
        print("REAL-TIME OBJECTION DETECTOR")
        print(f"{'='*60}")
        print(f"Audio file: {audio_path}")
        print(f"Server: {self.host}:{self.port}")
        print(f"Config: {self.config}")
        print(f"{'='*60}\n")

        # Start the orchestrator
        self.orchestrator.start()

        # Create WhisperLive client
        client = TranscriptionClient(
            host=self.host,
            port=self.port,
            model="base",
            log_transcription=False,
            transcription_callback=self._on_transcript_chunk,
        )

        # Run transcription
        try:
            client(audio_path)
        except KeyboardInterrupt:
            print("\n[INFO] Interrupted by user")

        # Wait a bit for pending analyses to complete
        print("\n[INFO] Waiting for pending analyses...")
        import time
        time.sleep(3)

        # Shutdown
        self.orchestrator.shutdown()

        # Print summary
        self._print_summary()

    def run_microphone(self) -> None:
        """Run real-time analysis on microphone input."""
        from whisper_live.client import TranscriptionClient
        import sys

        print(f"\n{'='*60}")
        print("REAL-TIME OBJECTION DETECTOR (MICROPHONE)")
        print(f"{'='*60}")
        print(f"Server: {self.host}:{self.port}")
        print(f"Config: {self.config}")
        print(f"{'='*60}")
        print("\nListening... Press Ctrl+C to stop.\n")
        sys.stdout.flush()

        # Start the orchestrator
        self.orchestrator.start()

        # Create WhisperLive client
        try:
            client = TranscriptionClient(
                host=self.host,
                port=self.port,
                model="base",
                log_transcription=False,
                transcription_callback=self._on_transcript_chunk,
            )
        except Exception as e:
            print(f"\n[ERROR] Failed to connect to WhisperLive: {e}")
            print(f"Make sure WhisperLive server is running on {self.host}:{self.port}")
            self.orchestrator.shutdown()
            return

        # Run transcription from microphone
        try:
            client()  # No argument = microphone
        except KeyboardInterrupt:
            print("\n[INFO] Stopped by user")
        except OSError as e:
            if "No Default Input Device" in str(e):
                print("\n[ERROR] No microphone detected.")
                print("Run --list-devices to see available devices.")
            else:
                print(f"\n[ERROR] Audio error: {e}")

        # Wait a bit for pending analyses to complete
        print("\n[INFO] Waiting for pending analyses...")
        import time
        time.sleep(3)

        # Shutdown
        self.orchestrator.shutdown()

        # Print summary
        self._print_summary()

    def _print_summary(self) -> None:
        """Print session summary."""
        print(f"\n{'='*60}")
        print("SESSION SUMMARY")
        print(f"{'='*60}")
        print(f"Total analyses: {self.total_analyses}")
        print(f"Objections detected: {self.objections_detected}")
        print(f"Orchestrator stats:")
        print(f"  - Requests: {self.orchestrator.total_requests}")
        print(f"  - Completed: {self.orchestrator.total_completed}")
        print(f"  - Errors: {self.orchestrator.total_errors}")
        print(f"{'='*60}\n")


def list_audio_devices():
    """List available audio input devices."""
    try:
        import pyaudio
        p = pyaudio.PyAudio()
        print("Available audio input devices:")
        print("-" * 50)
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info["maxInputChannels"] > 0:
                default = " (default)" if i == p.get_default_input_device_info()["index"] else ""
                print(f"  [{i}] {info['name']}{default}")
        p.terminate()
        print("-" * 50)
        print("\nUse --device <id> to select a specific device (not yet implemented)")
    except Exception as e:
        print(f"ERROR: Could not list audio devices: {e}")
        print("\nMake sure PortAudio is installed:")
        print("  Arch Linux: sudo pacman -S portaudio")
        print("  Ubuntu/Debian: sudo apt-get install portaudio19-dev")


def main():
    """Main entry point."""
    # Handle --list-devices before API key check
    if "--list-devices" in sys.argv:
        list_audio_devices()
        sys.exit(0)

    # Check for API key
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("ERROR: OPENROUTER_API_KEY environment variable not set.")
        print("Set it in your .env file or export it.")
        sys.exit(1)

    # Parse arguments
    args = sys.argv[1:]
    verbose = "--verbose" in args or "-v" in args
    args = [a for a in args if a not in ("--verbose", "-v")]

    if len(args) < 1:
        print("Usage:")
        print("  python src/realtime_transcribe.py <audio_file_path> [--verbose]")
        print("  python src/realtime_transcribe.py --mic [--verbose]")
        print("  python src/realtime_transcribe.py --list-devices")
        print("\nOptions:")
        print("  <audio_file_path>  Path to audio/video file to analyze")
        print("  --mic              Use microphone input for live analysis")
        print("  --list-devices     List available audio input devices")
        print("  --verbose, -v      Show all LLM responses (not just objections)")
        sys.exit(1)

    # Configure buffer (using defaults from PRD)
    config = BufferConfig(
        time_threshold_seconds=3.0,
        min_completed_segments=2,
        min_characters=150,
        silence_threshold_seconds=1.5,
        context_window_seconds=30.0,
        sentence_end_triggers=True,
    )

    # Create detector
    detector = RealtimeObjectionDetector(
        api_key=api_key,
        config=config,
        verbose=verbose,
    )

    # Run based on input type
    if args[0] == "--mic":
        detector.run_microphone()
    else:
        audio_path = args[0]
        if not Path(audio_path).exists():
            print(f"ERROR: File not found: {audio_path}")
            sys.exit(1)
        detector.run_file(audio_path)


if __name__ == "__main__":
    main()
