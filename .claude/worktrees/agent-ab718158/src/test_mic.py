#!/usr/bin/env python3
"""Simple test script for microphone input with WhisperLive."""

from whisper_live.client import TranscriptionClient


def callback(text, segments):
    print(f">>> {text}")


if __name__ == "__main__":
    print("Creating WhisperLive client...")

    client = TranscriptionClient(
        host="localhost",
        port=9090,
        model="base",
        log_transcription=True,
        transcription_callback=callback,
    )

    print("Speak now! Press Ctrl+C to stop.")
    print("-" * 40)

    try:
        client()
    except KeyboardInterrupt:
        print("\nStopped.")
