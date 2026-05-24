#!/usr/bin/env python3
"""
E2E Pipeline Test for Sales RPG AI.

Tests the full audio pipeline against running Docker containers:
  1. WhisperLiveKit WebSocket connectivity
  2. Audio → Transcription (send real audio, verify transcript)
  3. Full pipeline via web app (audio → transcription → analysis)

Prerequisites:
  - docker compose up -d (whisper-live + sales-ai-web running)

Usage:
  python tests/test_e2e_pipeline.py
  python tests/test_e2e_pipeline.py --test connectivity
  python tests/test_e2e_pipeline.py --test transcription
  python tests/test_e2e_pipeline.py --test full_pipeline
"""

import argparse
import asyncio
import json
import struct
import sys
import time
from pathlib import Path

import websockets

# Configuration
WHISPER_HOST = "localhost"
WHISPER_PORT = 9090
WEB_HOST = "localhost"
WEB_PORT = 8080

# Test audio: JFK speech
AUDIO_FILE = Path(__file__).parent.parent / "WhisperLive" / "assets" / "jfk.flac"

SAMPLE_RATE = 16000
CHUNK_DURATION_S = 0.25  # 250ms chunks
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_DURATION_S)


def load_audio_as_s16le(path: Path) -> bytes:
    """Load an audio file and return raw s16le PCM at 16kHz mono."""
    try:
        import soundfile as sf
        import numpy as np
    except ImportError:
        print("ERROR: soundfile and numpy required. Install with: pip install soundfile numpy")
        sys.exit(1)

    data, sr = sf.read(str(path), dtype="float32")

    # Convert to mono if stereo
    if len(data.shape) > 1:
        data = data.mean(axis=1)

    # Resample to 16kHz if needed
    if sr != SAMPLE_RATE:
        from scipy.signal import resample
        num_samples = int(len(data) * SAMPLE_RATE / sr)
        data = resample(data, num_samples).astype("float32")

    # Convert to s16le
    s16_data = (data * 32768).clip(-32768, 32767).astype("int16")
    return s16_data.tobytes()


def chunk_audio(pcm_bytes: bytes, chunk_size_bytes: int) -> list[bytes]:
    """Split PCM bytes into chunks."""
    return [
        pcm_bytes[i : i + chunk_size_bytes]
        for i in range(0, len(pcm_bytes), chunk_size_bytes)
    ]


class TestResult:
    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.error = None
        self.details = {}
        self.start_time = time.time()

    def pass_(self, **details):
        self.passed = True
        self.details = details
        self.elapsed = time.time() - self.start_time

    def fail(self, error: str, **details):
        self.passed = False
        self.error = error
        self.details = details
        self.elapsed = time.time() - self.start_time

    def __str__(self):
        status = "PASS" if self.passed else "FAIL"
        msg = f"[{status}] {self.name} ({self.elapsed:.1f}s)"
        if self.error:
            msg += f"\n       Error: {self.error}"
        for k, v in self.details.items():
            msg += f"\n       {k}: {v}"
        return msg


# ─── Test 1: WhisperLiveKit Connectivity ───────────────────────────


async def test_connectivity() -> TestResult:
    """Verify WhisperLiveKit WebSocket accepts connections and sends config."""
    result = TestResult("WhisperLiveKit Connectivity")

    try:
        url = f"ws://{WHISPER_HOST}:{WHISPER_PORT}/asr"
        async with websockets.connect(url, close_timeout=5) as ws:
            # Should receive config message
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(msg)

            if data.get("type") == "config":
                result.pass_(
                    url=url,
                    config=data,
                )
            else:
                result.fail(
                    f"Expected config message, got: {data}",
                    url=url,
                )
    except asyncio.TimeoutError:
        result.fail("Timeout waiting for config message")
    except ConnectionRefusedError:
        result.fail(f"Connection refused at ws://{WHISPER_HOST}:{WHISPER_PORT}/asr. Is whisper-live running?")
    except Exception as e:
        result.fail(str(e))

    return result


# ─── Test 2: Audio → Transcription ─────────────────────────────────


async def test_transcription() -> TestResult:
    """Send real audio to WhisperLiveKit and verify transcription."""
    result = TestResult("Audio → Transcription")

    if not AUDIO_FILE.exists():
        result.fail(f"Test audio not found: {AUDIO_FILE}")
        return result

    try:
        pcm_bytes = load_audio_as_s16le(AUDIO_FILE)
        chunk_size_bytes = CHUNK_SAMPLES * 2  # 2 bytes per s16 sample
        chunks = chunk_audio(pcm_bytes, chunk_size_bytes)

        url = f"ws://{WHISPER_HOST}:{WHISPER_PORT}/asr"
        transcribed_texts = []

        async with websockets.connect(url, close_timeout=5) as ws:
            # Receive config
            config_msg = await asyncio.wait_for(ws.recv(), timeout=5)

            # Send audio chunks at roughly real-time pace
            send_start = time.time()
            for i, chunk in enumerate(chunks):
                await ws.send(chunk)
                # Pace at ~2x real-time to not overwhelm
                await asyncio.sleep(CHUNK_DURATION_S / 2)

            send_elapsed = time.time() - send_start

            # Collect transcription results for a few seconds after sending
            recv_start = time.time()
            while time.time() - recv_start < 10:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=2)
                    data = json.loads(msg)

                    if data.get("type") == "ready_to_stop":
                        break

                    lines = data.get("lines", [])
                    for line in lines:
                        text = line.get("text", "").strip()
                        if text and text not in transcribed_texts:
                            transcribed_texts.append(text)

                    buffer = data.get("buffer_transcription", "").strip()
                    if buffer:
                        transcribed_texts.append(f"[buffer] {buffer}")
                except asyncio.TimeoutError:
                    break

        full_transcript = " ".join(t for t in transcribed_texts if not t.startswith("[buffer]"))

        if full_transcript:
            # Check for key JFK words
            jfk_keywords = ["country", "ask", "what", "can", "do"]
            found_keywords = [w for w in jfk_keywords if w.lower() in full_transcript.lower()]

            result.pass_(
                audio_duration=f"{len(pcm_bytes) / (SAMPLE_RATE * 2):.1f}s",
                chunks_sent=len(chunks),
                send_time=f"{send_elapsed:.1f}s",
                transcript=full_transcript[:200],
                keyword_matches=f"{len(found_keywords)}/{len(jfk_keywords)} ({', '.join(found_keywords)})",
            )
        else:
            result.fail(
                "No transcription received",
                chunks_sent=len(chunks),
                send_time=f"{send_elapsed:.1f}s",
                raw_responses=len(transcribed_texts),
            )

    except ConnectionRefusedError:
        result.fail("Connection refused. Is whisper-live running?")
    except Exception as e:
        result.fail(str(e))

    return result


# ─── Test 3: Full Pipeline (Web App) ──────────────────────────────


async def test_full_pipeline() -> TestResult:
    """Test the full pipeline: audio → transcription → summary → recommendation."""
    result = TestResult("Full Pipeline (Web App)")

    if not AUDIO_FILE.exists():
        result.fail(f"Test audio not found: {AUDIO_FILE}")
        return result

    try:
        pcm_bytes = load_audio_as_s16le(AUDIO_FILE)
        chunk_size_bytes = CHUNK_SAMPLES * 2
        chunks = chunk_audio(pcm_bytes, chunk_size_bytes)

        url = f"ws://{WEB_HOST}:{WEB_PORT}/ws/audio"
        transcripts = []
        summaries = []
        recommendations = []
        errors = []

        async with websockets.connect(url, close_timeout=10) as ws:
            # Create receiver task
            async def receive_messages():
                try:
                    while True:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        msg_type = data.get("type", "")

                        if msg_type == "transcript":
                            transcripts.append(data)
                        elif msg_type == "summary":
                            summaries.append(data)
                        elif msg_type == "recommendation":
                            recommendations.append(data)
                        elif msg_type == "error":
                            errors.append(data)
                        elif msg_type == "reset":
                            pass
                except websockets.exceptions.ConnectionClosed:
                    pass
                except asyncio.CancelledError:
                    pass

            recv_task = asyncio.create_task(receive_messages())

            # Send audio chunks at ~real-time pace
            for chunk in chunks:
                await ws.send(chunk)
                await asyncio.sleep(CHUNK_DURATION_S / 2)

            # Wait for transcription to complete
            await asyncio.sleep(5)

            # Trigger a manual summary refresh via text command
            await ws.send(json.dumps({"command": "refresh_summary"}))
            await asyncio.sleep(15)  # Wait for LLM summary

            # Trigger a recommendation via text command
            await ws.send(json.dumps({"command": "recommend"}))
            await asyncio.sleep(15)  # Wait for LLM recommendation

            recv_task.cancel()
            try:
                await recv_task
            except asyncio.CancelledError:
                pass

        # Evaluate results
        transcript_texts = [t.get("text", "") for t in transcripts if t.get("is_final")]
        full_transcript = " ".join(transcript_texts)
        has_transcript = bool(full_transcript.strip())
        has_summary = any(s.get("summary") for s in summaries if not s.get("error"))
        has_recommendation = any(r.get("questions") for r in recommendations if not r.get("error"))

        details = {
            "transcript_segments": len(transcript_texts),
            "transcript_preview": full_transcript[:150],
            "summaries_received": len(summaries),
            "recommendations_received": len(recommendations),
            "errors": len(errors),
        }

        if has_summary:
            s = next(s for s in summaries if s.get("summary"))
            details["summary_preview"] = s["summary"][:100]
            details["stage_hint"] = s.get("stage_hint", "")
            details["key_points"] = len(s.get("key_points", []))

        if has_recommendation:
            r = next(r for r in recommendations if r.get("questions"))
            details["rec_stage"] = r.get("stage", "")
            details["rec_questions"] = len(r.get("questions", []))
            details["rec_question_1"] = r["questions"][0][:80] if r.get("questions") else ""

        if has_transcript and has_summary and has_recommendation:
            result.pass_(**details)
        elif has_transcript and has_summary:
            result.fail("Summary works but recommendation failed", **details)
        elif has_transcript:
            summary_errors = [s.get("error") for s in summaries if s.get("error")]
            rec_errors = [r.get("error") for r in recommendations if r.get("error")]
            result.fail(
                f"Transcription works but summary/recommendation failed. "
                f"Summary errors: {summary_errors}, Rec errors: {rec_errors}",
                **details,
            )
        else:
            result.fail("No transcription received", **details)

    except ConnectionRefusedError:
        result.fail(f"Connection refused at {url}. Is sales-ai-web running?")
    except Exception as e:
        result.fail(str(e))

    return result


# ─── Runner ────────────────────────────────────────────────────────


async def run_tests(test_names: list[str]) -> list[TestResult]:
    tests = {
        "connectivity": test_connectivity,
        "transcription": test_transcription,
        "full_pipeline": test_full_pipeline,
    }

    results = []
    for name in test_names:
        if name not in tests:
            print(f"Unknown test: {name}")
            continue

        print(f"\n{'=' * 60}")
        print(f"Running: {name}")
        print(f"{'=' * 60}")

        result = await tests[name]()
        results.append(result)
        print(result)

    return results


def main():
    parser = argparse.ArgumentParser(description="E2E Pipeline Tests")
    parser.add_argument(
        "--test",
        choices=["connectivity", "transcription", "full_pipeline", "all"],
        default="all",
        help="Which test to run (default: all)",
    )
    parser.add_argument("--whisper-host", default=WHISPER_HOST)
    parser.add_argument("--whisper-port", type=int, default=WHISPER_PORT)
    parser.add_argument("--web-host", default=WEB_HOST)
    parser.add_argument("--web-port", type=int, default=WEB_PORT)
    args = parser.parse_args()

    # Update module-level config from CLI args
    test_e2e_pipeline = sys.modules[__name__]
    test_e2e_pipeline.WHISPER_HOST = args.whisper_host
    test_e2e_pipeline.WHISPER_PORT = args.whisper_port
    test_e2e_pipeline.WEB_HOST = args.web_host
    test_e2e_pipeline.WEB_PORT = args.web_port

    if args.test == "all":
        test_names = ["connectivity", "transcription", "full_pipeline"]
    else:
        test_names = [args.test]

    print("=" * 60)
    print("SALES RPG AI - E2E PIPELINE TESTS")
    print("=" * 60)
    print(f"WhisperLiveKit: ws://{WHISPER_HOST}:{WHISPER_PORT}/asr")
    print(f"Web App:        ws://{WEB_HOST}:{WEB_PORT}/ws/audio")

    results = asyncio.run(run_tests(test_names))

    # Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"  [{status}] {r.name}")

    print(f"\n{passed}/{total} tests passed")
    print(f"{'=' * 60}")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
