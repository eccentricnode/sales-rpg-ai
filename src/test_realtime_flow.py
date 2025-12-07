#!/usr/bin/env python3
"""
Test script to verify the realtime LLM analysis flow.

Simulates transcript chunks without needing WhisperLive server.
Shows all LLM responses so you can verify the system is working.

Usage:
    python src/test_realtime_flow.py
"""

import os
import sys
import time
from pathlib import Path

# Load environment variables
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()

sys.path.insert(0, str(Path(__file__).parent))

from realtime import (
    BufferConfig,
    DualBufferManager,
    AnalysisOrchestrator,
    AnalysisResult,
    StreamingAnalyzer,
)


def main():
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("ERROR: Set OPENROUTER_API_KEY in .env file")
        sys.exit(1)

    print("=" * 70)
    print("REALTIME FLOW TEST - Simulated Transcript Chunks")
    print("=" * 70)
    print("\nThis test simulates WhisperLive sending transcript chunks.")
    print("You'll see the LLM response for EVERY analysis trigger.\n")

    # Results collector
    results = []

    def on_result(result: AnalysisResult):
        results.append(result)
        print("\n" + "=" * 70)
        if result.error:
            print(f"[ERROR] {result.error}")
        else:
            print(f"[LLM RESPONSE] Latency: {result.latency_ms:.0f}ms")
            print(f"[ANALYZED TEXT] \"{result.active_text}\"")
            if result.context_text:
                ctx = result.context_text[:80] + "..." if len(result.context_text) > 80 else result.context_text
                print(f"[CONTEXT] \"{ctx}\"")
            print("-" * 70)
            print(result.raw_response)
            print("-" * 70)
            print(f"Objection detected: {result.has_objection}")
        print("=" * 70 + "\n")

    # Create components
    analyzer = StreamingAnalyzer(api_key=api_key)
    orchestrator = AnalysisOrchestrator(analyzer=analyzer, on_result=on_result)

    # Use "Slow Burn" config to verify batching behavior
    config = BufferConfig(
        time_threshold_seconds=15.0,   # Wait 15s
        min_completed_segments=10,     # Wait for paragraph
        min_characters=500,            # Wait for context
        sentence_end_triggers=False,   # Disable instant triggers
    )

    buffer_manager = DualBufferManager(
        config=config,
        on_analysis_ready=orchestrator.submit_analysis,
    )

    # Simulated conversation - each chunk is what WhisperLive would send
    # Format: (text, segments) - segments have completed=True to simulate finalized speech
    conversation = [
        {
            "description": "Greeting (no objection expected)",
            "text": "Hi thanks for meeting with me today.",
            "segments": [
                {"text": "Hi thanks for meeting with me today.", "start": 0.0, "end": 2.0, "completed": True}
            ],
        },
        {
            "description": "Price objection",
            "text": "That's way too expensive for our budget.",
            "segments": [
                {"text": "That's way too expensive for our budget.", "start": 2.5, "end": 5.0, "completed": True}
            ],
        },
        {
            "description": "Decision maker objection",
            "text": "I need to run this by my manager first.",
            "segments": [
                {"text": "I need to run this by my manager first.", "start": 5.5, "end": 8.0, "completed": True}
            ],
        },
        {
            "description": "Time objection",
            "text": "We're not ready to make a decision right now.",
            "segments": [
                {"text": "We're not ready to make a decision right now.", "start": 8.5, "end": 11.0, "completed": True}
            ],
        },
    ]

    # Process each chunk
    for i, chunk in enumerate(conversation):
        print(f"\n>>> CHUNK {i+1}: {chunk['description']}")
        print(f">>> Sending: \"{chunk['text']}\"")

        # Feed to buffer manager (simulates WhisperLive callback)
        buffer_manager.on_transcript_chunk(chunk["text"], chunk["segments"])

        # Wait for LLM response before next chunk
        time.sleep(5)

    # Final wait for any pending
    print("\n[Waiting for any pending analyses...]")
    time.sleep(3)

    orchestrator.shutdown()

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"Total chunks sent: {len(conversation)}")
    print(f"Total LLM responses: {len(results)}")
    print(f"Objections detected: {sum(1 for r in results if r.has_objection)}")
    print(f"Errors: {sum(1 for r in results if r.error)}")
    print("=" * 70)


if __name__ == "__main__":
    main()
