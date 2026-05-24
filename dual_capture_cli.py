#!/usr/bin/env python3
"""
CLI tool for dual audio capture and transcription.

Quick start:
    # Capture only
    python dual_capture_cli.py capture --duration 30

    # Capture + transcribe
    python dual_capture_cli.py capture-and-transcribe --duration 60

    # Transcribe existing files
    python dual_capture_cli.py transcribe mic.wav system.wav
"""

import asyncio
import sys
from pathlib import Path
import argparse

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.audio import DualCaptureManager
from src.transcription import DualStreamTranscriber


async def cmd_capture(args):
    """Capture audio from mic and system."""
    output_dir = Path(args.output_dir)

    print(f"Starting dual audio capture for {args.duration} seconds")
    print(f"Output: {output_dir}\n")
    print("🎤 Speak into your microphone")
    print("🔊 Play audio on your system\n")

    async with DualCaptureManager(output_dir) as manager:
        mic_path, system_path = await manager.start(args.session_id)

        print(f"Microphone → {mic_path}")
        print(f"System Audio → {system_path}\n")

        # Countdown
        for i in range(args.duration, 0, -1):
            print(f"\rRecording... {i:3d}s remaining", end="", flush=True)
            await asyncio.sleep(1)

        print("\n\nStopping capture...")
        mic_path, system_path = await manager.stop()

    print(f"\n✅ Capture complete!")
    print(f"   Mic: {mic_path} ({mic_path.stat().st_size:,} bytes)")
    print(f"   System: {system_path} ({system_path.stat().st_size:,} bytes)")


async def cmd_transcribe(args):
    """Transcribe existing audio files."""
    mic_path = Path(args.mic_file)
    system_path = Path(args.system_file)

    if not mic_path.exists():
        print(f"❌ Microphone file not found: {mic_path}")
        return 1

    if not system_path.exists():
        print(f"❌ System audio file not found: {system_path}")
        return 1

    print("Starting transcription...")
    print(f"  Mic: {mic_path}")
    print(f"  System: {system_path}\n")

    def on_segment(segment):
        """Print segments as they arrive."""
        print(f"[{segment.speaker}] {segment.text}")

    transcriber = DualStreamTranscriber(
        whisper_host=args.whisper_host,
        whisper_port=args.whisper_port,
        on_segment=on_segment if args.live else None,
    )

    transcript = await transcriber.transcribe_streams(mic_path, system_path)

    print(f"\n✅ Transcription complete: {len(transcript.segments)} segments")

    # Save outputs
    output_dir = mic_path.parent
    (output_dir / "transcript.txt").write_text(transcript.to_text())
    (output_dir / "transcript.json").write_text(transcript.to_json())
    (output_dir / "transcript.srt").write_text(transcript.to_srt())

    print(f"\nSaved to {output_dir}/:")
    print("  - transcript.txt")
    print("  - transcript.json")
    print("  - transcript.srt")

    if not args.live:
        print("\n" + "=" * 60)
        print(transcript.to_text())
        print("=" * 60)


async def cmd_capture_and_transcribe(args):
    """Capture and transcribe in one command."""
    output_dir = Path(args.output_dir)

    print(f"Dual capture + transcription ({args.duration}s)")
    print(f"Output: {output_dir}\n")
    print("🎤 Speak into your microphone")
    print("🔊 Play audio on your system\n")

    # Capture
    async with DualCaptureManager(output_dir) as manager:
        mic_path, system_path = await manager.start(args.session_id)

        print(f"Microphone → {mic_path}")
        print(f"System Audio → {system_path}\n")

        for i in range(args.duration, 0, -1):
            print(f"\rRecording... {i:3d}s remaining", end="", flush=True)
            await asyncio.sleep(1)

        print("\n\nStopping capture...")
        mic_path, system_path = await manager.stop()

    print(f"\n✅ Capture complete!")

    # Transcribe
    print("\nStarting transcription...\n")

    def on_segment(segment):
        print(f"[{segment.speaker}] {segment.text}")

    transcriber = DualStreamTranscriber(
        whisper_host=args.whisper_host,
        whisper_port=args.whisper_port,
        on_segment=on_segment,
    )

    transcript = await transcriber.transcribe_streams(mic_path, system_path)

    print(f"\n✅ Transcription complete: {len(transcript.segments)} segments")

    # Save
    (output_dir / "transcript.txt").write_text(transcript.to_text())
    (output_dir / "transcript.json").write_text(transcript.to_json())
    (output_dir / "transcript.srt").write_text(transcript.to_srt())

    print(f"\nSaved to {output_dir}/")


def main():
    parser = argparse.ArgumentParser(
        description="Dual audio capture and transcription CLI"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Capture command
    capture_parser = subparsers.add_parser("capture", help="Capture audio only")
    capture_parser.add_argument(
        "--duration", type=int, default=30, help="Recording duration in seconds"
    )
    capture_parser.add_argument(
        "--output-dir",
        default="/tmp/sales-rpg-ai/dual_capture",
        help="Output directory",
    )
    capture_parser.add_argument(
        "--session-id", default="session", help="Session identifier"
    )

    # Transcribe command
    transcribe_parser = subparsers.add_parser(
        "transcribe", help="Transcribe existing files"
    )
    transcribe_parser.add_argument("mic_file", help="Microphone audio file")
    transcribe_parser.add_argument("system_file", help="System audio file")
    transcribe_parser.add_argument(
        "--whisper-host", default="localhost", help="WhisperLive host"
    )
    transcribe_parser.add_argument(
        "--whisper-port", type=int, default=9090, help="WhisperLive port"
    )
    transcribe_parser.add_argument(
        "--live", action="store_true", help="Show segments as they arrive"
    )

    # Capture and transcribe command
    both_parser = subparsers.add_parser(
        "capture-and-transcribe", help="Capture and transcribe"
    )
    both_parser.add_argument(
        "--duration", type=int, default=30, help="Recording duration in seconds"
    )
    both_parser.add_argument(
        "--output-dir",
        default="/tmp/sales-rpg-ai/dual_capture",
        help="Output directory",
    )
    both_parser.add_argument("--session-id", default="session", help="Session ID")
    both_parser.add_argument(
        "--whisper-host", default="localhost", help="WhisperLive host"
    )
    both_parser.add_argument(
        "--whisper-port", type=int, default=9090, help="WhisperLive port"
    )

    args = parser.parse_args()

    if args.command == "capture":
        asyncio.run(cmd_capture(args))
    elif args.command == "transcribe":
        asyncio.run(cmd_transcribe(args))
    elif args.command == "capture-and-transcribe":
        asyncio.run(cmd_capture_and_transcribe(args))


if __name__ == "__main__":
    main()
