#!/usr/bin/env python3
"""
Real-time transcription with streaming analysis (Simplified).

Usage:
    python src/realtime_transcribe.py <audio_file_path>
    python src/realtime_transcribe.py --mic  # Use microphone input
"""

import sys
import os
import time
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

from realtime.buffer_manager import DualBufferManager, BufferConfig
from realtime.analysis_orchestrator import AnalysisOrchestrator, AnalysisResult, StreamingAnalyzer

class RealtimeObjectionDetector:
    def __init__(
        self,
        api_key: str,
        host: str = "localhost",
        port: int = 9090,
        config: BufferConfig = None,
        verbose: bool = False,
    ):
        self.host = host
        self.port = port
        self.verbose = verbose
        
        # Initialize components
        self.analyzer = StreamingAnalyzer(
            api_key=api_key,
            base_url=os.getenv("LOCAL_AI_BASE_URL", "http://localhost:8080/v1"),
            model=os.getenv("LOCAL_AI_MODEL", "phi-3.5-mini")
        )
        
        self.orchestrator = AnalysisOrchestrator(
            analyzer=self.analyzer,
            on_result=self.on_analysis_result
        )
        
        self.buffer_manager = DualBufferManager(
            config=config,
            on_analysis_ready=self.on_analysis_ready,
            on_state_analysis_ready=lambda x, y: None
        )

    def on_analysis_ready(self, active_text: str, context_text: str):
        if self.verbose:
            print(f"\n[Buffer Trigger] Analyzing: {active_text[:50]}...")
        self.orchestrator.submit_analysis(active_text, context_text)

    def on_analysis_result(self, result: AnalysisResult):
        print(f"\n--- Analysis Result ({result.latency_ms:.0f}ms) ---")
        print(f"Location: {result.state.script_location}")
        print(f"Suggestion: {result.state.suggestion}")
        if result.error:
            print(f"Error: {result.error}")
        print("------------------------------------------------")

    def start(self):
        print("Starting detector... (CLI mode not fully implemented in simplified version)")
        # Note: The full WhisperLive client logic was here. 
        # For this refactor, I'm just ensuring it imports correctly.
        # The Web UI is the primary interface now.

if __name__ == "__main__":
    print("Please use the Web UI: python src/web/run.py")
