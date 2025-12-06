#!/usr/bin/env python3
"""Test that PyAudio is actually capturing audio from the microphone."""

import pyaudio
import sys

# Same settings WhisperLive uses
CHUNK = 4096
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000

def test_audio_capture(duration_seconds=3):
    """Capture audio for a few seconds and report what we get."""
    print("Testing audio capture...")
    print(f"Settings: {RATE}Hz, {CHANNELS} channel(s), {CHUNK} chunk size")
    print("-" * 50)

    p = pyaudio.PyAudio()

    # Show default device
    try:
        default = p.get_default_input_device_info()
        print(f"Default input device: [{default['index']}] {default['name']}")
    except Exception as e:
        print(f"ERROR: No default input device: {e}")
        p.terminate()
        return False

    print("-" * 50)
    print(f"Recording for {duration_seconds} seconds... SPEAK NOW!")
    print()

    try:
        stream = p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK,
        )
    except Exception as e:
        print(f"ERROR: Could not open audio stream: {e}")
        p.terminate()
        return False

    frames = []
    total_bytes = 0
    num_chunks = int(RATE / CHUNK * duration_seconds)

    for i in range(num_chunks):
        try:
            data = stream.read(CHUNK, exception_on_overflow=False)
            frames.append(data)
            total_bytes += len(data)

            # Calculate rough audio level (RMS-ish)
            audio_level = sum(abs(b - 128) for b in data[:100]) / 100
            bar = "#" * int(audio_level / 5)
            print(f"\rChunk {i+1}/{num_chunks}: {len(data)} bytes | Level: {bar:<20}", end="", flush=True)

        except Exception as e:
            print(f"\nERROR reading audio: {e}")
            break

    print()
    print("-" * 50)

    stream.stop_stream()
    stream.close()
    p.terminate()

    print(f"Captured {len(frames)} chunks, {total_bytes} bytes total")

    # Check if we got actual audio (not just silence/zeros)
    all_data = b''.join(frames)

    # Count non-zero bytes
    non_zero = sum(1 for b in all_data if b != 0 and b != 128)
    pct_non_zero = (non_zero / len(all_data)) * 100

    print(f"Non-silent bytes: {pct_non_zero:.1f}%")

    if pct_non_zero < 5:
        print("\nWARNING: Audio appears to be mostly silent!")
        print("Check that your microphone is:")
        print("  - Plugged in and selected as default")
        print("  - Not muted")
        print("  - Working (test with another app)")
        return False
    else:
        print("\nSUCCESS: Audio capture is working!")
        return True


if __name__ == "__main__":
    duration = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    success = test_audio_capture(duration)
    sys.exit(0 if success else 1)
