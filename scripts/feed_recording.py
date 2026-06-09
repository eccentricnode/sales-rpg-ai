#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["websockets>=10,<13"]
# ///
"""Batch-feed a recording through the live /ws/audio pipeline.

Mimics what the browser does (16kHz s16le mono PCM, ~4096-sample chunks at
realtime pace) so the recording exercises VAD + DualBufferManager +
AnalysisOrchestrator + LLM exactly like a real mic session would.

Usage: python scripts/feed_recording.py path/to/file.mp4 [--server ws://localhost:8080] [--speed 1.0]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import subprocess
import sys
from pathlib import Path

import websockets

SAMPLE_RATE = 16000
BYTES_PER_SAMPLE = 2  # s16le
CHUNK_SAMPLES = 4096
CHUNK_BYTES = CHUNK_SAMPLES * BYTES_PER_SAMPLE
CHUNK_SECONDS = CHUNK_SAMPLES / SAMPLE_RATE  # ~0.256s


def stream_pcm_from_media(path: Path):
    """Yield CHUNK_BYTES-sized PCM chunks from a media file using ffmpeg."""
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not on PATH — install it first (sudo pacman -S ffmpeg)")
    proc = subprocess.Popen(
        [
            "ffmpeg",
            "-loglevel", "error",
            "-i", str(path),
            "-ac", "1",
            "-ar", str(SAMPLE_RATE),
            "-f", "s16le",
            "-",
        ],
        stdout=subprocess.PIPE,
    )
    assert proc.stdout is not None
    try:
        while True:
            chunk = proc.stdout.read(CHUNK_BYTES)
            if not chunk:
                break
            if len(chunk) < CHUNK_BYTES:
                chunk = chunk + b"\x00" * (CHUNK_BYTES - len(chunk))
            yield chunk
    finally:
        proc.terminate()
        proc.wait(timeout=5)


async def receive_messages(ws):
    """Print every JSON message the server sends, until the connection closes."""
    try:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except Exception:
                print(f"[raw] {raw[:160]}")
                continue
            kind = msg.get("type", "?")
            if kind == "transcript":
                print(f"\n[TRANSCRIPT] {msg.get('text','').strip()}")
            elif kind == "analysis":
                kp = msg.get("key_points") or []
                kp_str = "\n      - " + "\n      - ".join(kp) if kp else " (none)"
                print(
                    f"\n[COACHING]  latency={msg.get('latency')}ms\n"
                    f"  script_location: {msg.get('script_location')!r}\n"
                    f"  key_points:{kp_str}\n"
                    f"  suggestion: {(msg.get('suggestion') or '').strip()}"
                )
            elif kind == "analysis_delta":
                pass  # too noisy
            elif kind == "summary":
                kp = msg.get("key_points") or []
                print(f"\n[SUMMARY] stage={msg.get('stage_hint')}  key_points={len(kp)}  latency={msg.get('latency')}ms")
            else:
                print(f"\n[{kind}] {json.dumps(msg)[:300]}")
    except websockets.ConnectionClosed:
        print("[ws] connection closed")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("recording", type=Path)
    ap.add_argument("--server", default="ws://localhost:8080")
    ap.add_argument("--speed", type=float, default=1.0,
                    help="Playback rate; >1 faster than realtime (caution: skews triggers)")
    args = ap.parse_args()

    if not args.recording.exists():
        sys.exit(f"recording not found: {args.recording}")

    url = f"{args.server.rstrip('/')}/ws/audio?role=recorder"
    print(f"[connect] {url}")
    print(f"[feed]    {args.recording}  speed={args.speed}x")

    async with websockets.connect(url, max_size=None) as ws:
        # Start receiver concurrently
        recv_task = asyncio.create_task(receive_messages(ws))

        sleep_per_chunk = CHUNK_SECONDS / args.speed
        chunks_sent = 0
        bytes_sent = 0
        for chunk in stream_pcm_from_media(args.recording):
            try:
                await ws.send(chunk)
            except websockets.ConnectionClosed:
                print("[ws] closed mid-send")
                break
            chunks_sent += 1
            bytes_sent += len(chunk)
            if chunks_sent % 40 == 0:
                seconds = chunks_sent * CHUNK_SECONDS
                print(f"[progress] sent {chunks_sent} chunks ({seconds:.1f}s of audio, {bytes_sent//1024} KiB)")
            await asyncio.sleep(sleep_per_chunk)

        print(f"[done] sent {chunks_sent} chunks; draining server for 8s …")
        try:
            await asyncio.wait_for(recv_task, timeout=8)
        except asyncio.TimeoutError:
            recv_task.cancel()
            print("[done] receiver drain timed out — exiting")


if __name__ == "__main__":
    asyncio.run(main())
