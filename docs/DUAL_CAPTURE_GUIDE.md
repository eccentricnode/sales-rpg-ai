# Dual Audio Capture Implementation Guide

## Overview

This guide explains how to use the dual audio capture system for perfect speaker diarization in sales calls.

## What is Dual Audio Capture?

Instead of using ML models to guess who is speaking, we capture audio from two physically separate sources:

- **Microphone Input** → Sales representative speaking
- **System Audio Output** → Customer speaking (from Zoom/Discord/etc)

This provides **perfect diarization with zero ML overhead** - we know exactly who is speaking based on which audio source captured it.

## Installation

### Prerequisites

1. **Python 3.10+**
2. **PulseAudio/PipeWire** (standard on most Linux distributions)
3. **PyAudio** for microphone capture
4. **WhisperLive** for transcription

### Install Dependencies

```bash
cd /home/ajohnson/Work/sales-rpg-ai

# Install PyAudio
pip install pyaudio

# Or using system package manager
# Debian/Ubuntu:
sudo apt-get install python3-pyaudio

# Arch Linux:
sudo pacman -S python-pyaudio
```

### Verify Audio System

```bash
# Check PulseAudio/PipeWire is running
pactl info

# List microphones
pactl list sources short

# List system audio monitors
pactl list sources short | grep monitor
```

## Quick Start

### 1. Command Line Usage

#### Capture Only

```bash
# Capture 30 seconds of audio
python dual_capture_cli.py capture --duration 30

# Custom output directory
python dual_capture_cli.py capture \
    --duration 60 \
    --output-dir ./my_recordings \
    --session-id call_001
```

#### Capture + Transcribe

```bash
# Capture and transcribe in one command
python dual_capture_cli.py capture-and-transcribe --duration 60
```

#### Transcribe Existing Files

```bash
# Transcribe previously captured audio
python dual_capture_cli.py transcribe \
    /path/to/mic_audio.wav \
    /path/to/system_audio.wav
```

### 2. Python API Usage

#### Simple Capture

```python
import asyncio
from pathlib import Path
from src.audio import DualCaptureManager

async def capture_call():
    output_dir = Path("./recordings")

    async with DualCaptureManager(output_dir) as manager:
        # Start capturing
        mic_path, system_path = await manager.start("call_001")

        # Record for 60 seconds
        await asyncio.sleep(60)

        # Stop and get final paths
        mic_path, system_path = await manager.stop()

    print(f"Microphone: {mic_path}")
    print(f"System Audio: {system_path}")

asyncio.run(capture_call())
```

#### Capture + Transcribe

```python
import asyncio
from pathlib import Path
from src.audio import DualCaptureManager
from src.transcription import DualStreamTranscriber

async def capture_and_transcribe():
    output_dir = Path("./recordings")

    # Capture
    async with DualCaptureManager(output_dir) as manager:
        mic_path, system_path = await manager.start("call_001")
        await asyncio.sleep(60)
        mic_path, system_path = await manager.stop()

    # Transcribe
    transcriber = DualStreamTranscriber(
        whisper_host="localhost",
        whisper_port=9090
    )

    transcript = await transcriber.transcribe_streams(mic_path, system_path)

    # Print transcript
    for segment in transcript.segments:
        print(f"[{segment.speaker}] {segment.text}")

    # Save formats
    (output_dir / "transcript.txt").write_text(transcript.to_text())
    (output_dir / "transcript.json").write_text(transcript.to_json())
    (output_dir / "transcript.srt").write_text(transcript.to_srt())

asyncio.run(capture_and_transcribe())
```

#### Real-Time Callback

```python
import asyncio
from src.audio import DualCaptureManager
from src.transcription import DualStreamTranscriber

async def realtime_transcription():
    output_dir = Path("./recordings")

    # Callback for each segment
    def on_segment(segment):
        print(f"[{segment.speaker}] {segment.text}")

        # Send to your application
        # send_to_ui(segment)
        # save_to_database(segment)

    async with DualCaptureManager(output_dir) as manager:
        mic_path, system_path = await manager.start("call_001")

        # Start transcription in background
        transcriber = DualStreamTranscriber(on_segment=on_segment)
        transcribe_task = asyncio.create_task(
            transcriber.transcribe_streams(mic_path, system_path)
        )

        # Record for 60 seconds
        await asyncio.sleep(60)

        await manager.stop()
        transcript = await transcribe_task

asyncio.run(realtime_transcription())
```

### 3. Web API Usage

#### WebSocket Endpoint

The FastAPI web app includes a WebSocket endpoint for dual capture:

```javascript
// Connect to dual capture endpoint
const ws = new WebSocket("ws://localhost:8000/ws/dual-audio");

ws.onopen = () => {
    console.log("Connected to dual capture");
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.type === "transcript") {
        // Real-time transcript segment
        console.log(`[${data.speaker}] ${data.text}`);
        displayTranscript(data);
    }
    else if (data.type === "status") {
        console.log("Status:", data.message);
    }
    else if (data.type === "final_transcript") {
        // Complete transcript at end
        console.log("Final transcript:", data.json);
    }
};

// Stop capture
function stopCapture() {
    ws.send(JSON.stringify({ command: "stop" }));
}
```

## Testing

### Run Test Suite

```bash
# Run all tests
python tests/test_dual_capture.py

# Run specific test
python tests/test_dual_capture.py --test devices
python tests/test_dual_capture.py --test mic --duration 5
python tests/test_dual_capture.py --test dual --duration 10
python tests/test_dual_capture.py --test transcribe
```

### Test Checklist

1. **Device Enumeration** - Lists all microphones and monitors
2. **Microphone Capture** - Records mic input to WAV
3. **System Audio Capture** - Records system output to WAV
4. **Dual Capture** - Records both simultaneously
5. **Transcription** - Transcribes with speaker labels
6. **Performance** - Validates real-time latency

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Sales Call Application                    │
│                    (Zoom, Discord, etc.)                     │
└───────────────────────────┬─────────────────────────────────┘
                            │
            ┌───────────────┴───────────────┐
            │                               │
            ▼                               ▼
    ┌──────────────┐              ┌──────────────────┐
    │  Microphone  │              │  System Output   │
    │    Input     │              │    (Monitor)     │
    └──────┬───────┘              └────────┬─────────┘
           │                               │
           │ MicrophoneCapture             │ SystemAudioCapture
           │ (PyAudio)                     │ (pactl)
           │                               │
           ▼                               ▼
    ┌──────────────┐              ┌──────────────────┐
    │ mic_audio.wav│              │system_audio.wav  │
    └──────┬───────┘              └────────┬─────────┘
           │                               │
           │                               │
           └───────────┬───────────────────┘
                       │
                       ▼
            ┌──────────────────────┐
            │ DualStreamTranscriber│
            └──────────┬───────────┘
                       │
         ┌─────────────┴─────────────┐
         ▼                           ▼
┌─────────────────┐        ┌─────────────────┐
│  WhisperLive    │        │  WhisperLive    │
│  (Mic Stream)   │        │ (System Stream) │
└────────┬────────┘        └────────┬────────┘
         │                           │
         │ [SALES_REP] segments      │ [CUSTOMER] segments
         │                           │
         └─────────────┬─────────────┘
                       │
                       ▼
              ┌────────────────┐
              │ Merged by Time │
              └────────┬───────┘
                       │
                       ▼
          ┌────────────────────────┐
          │  Final Transcript with │
          │    Speaker Labels      │
          └────────────────────────┘
```

### Modules

- **src/audio/mic_capture.py** - Microphone input capture
- **src/audio/system_capture.py** - System audio output capture
- **src/audio/dual_capture.py** - Coordinator for both streams
- **src/transcription/dual_stream.py** - Transcription with speaker labels
- **src/web/app.py** - FastAPI WebSocket endpoint

## Output Formats

### Text Format

```
[SALES_REP] Hi, how can I help you today?
[CUSTOMER] I'm interested in your premium plan.
[SALES_REP] Great choice! Let me tell you about the features.
```

### JSON Format

```json
[
  {
    "speaker": "SALES_REP",
    "text": "Hi, how can I help you today?",
    "start": 0.5,
    "end": 2.3,
    "is_final": false
  },
  {
    "speaker": "CUSTOMER",
    "text": "I'm interested in your premium plan.",
    "start": 2.8,
    "end": 4.5,
    "is_final": false
  }
]
```

### SRT Format

```srt
1
00:00:00,500 --> 00:00:02,300
[SALES_REP] Hi, how can I help you today?

2
00:00:02,800 --> 00:00:04,500
[CUSTOMER] I'm interested in your premium plan.
```

## Troubleshooting

### No Microphone Detected

```bash
# List all input devices
pactl list sources short

# Test microphone
python src/test_audio_capture.py
```

### No System Audio Monitor

```bash
# List monitor sources
pactl list sources short | grep monitor

# If none found, check if PulseAudio/PipeWire is running
pactl info
```

### WhisperLive Connection Failed

```bash
# Check WhisperLive is running
curl http://localhost:9090

# Start WhisperLive server
cd WhisperLive
python -m whisper_live.server
```

### Audio Files Empty

- Check microphone is not muted
- Verify system audio is playing during capture
- Test with longer duration (increase --duration)

## Performance

### Latency Characteristics

- **Audio Capture**: <10ms (hardware direct access)
- **Transcription**: ~300-500ms per segment (WhisperLive)
- **Merge Operation**: <10ms (simple timestamp sort)
- **Total End-to-End**: ~500ms

### Resource Usage

- **CPU**: Moderate (dual transcription streams)
- **Memory**: ~50MB per audio stream
- **Disk I/O**: Minimal (streaming WAV writes)
- **Network**: Local only (WhisperLive on localhost)

## Production Deployment

### Requirements

1. WhisperLive server running
2. Sufficient CPU for dual transcription (2+ cores recommended)
3. PulseAudio/PipeWire configured
4. Audio devices available and not in use

### Recommended Setup

```bash
# Start WhisperLive server
cd WhisperLive
python -m whisper_live.server --port 9090 &

# Start web application
cd /home/ajohnson/Work/sales-rpg-ai
python src/web/run.py
```

### Docker Deployment

See `docker-compose.yml` for containerized deployment with GPU support.

## Future Enhancements

1. **VAD Integration** - Voice Activity Detection to reduce silent segments
2. **Dynamic Device Selection** - Runtime device switching
3. **Multi-Party Support** - >2 speakers with additional streams
4. **Quality Monitoring** - Detect and alert on poor audio quality
5. **Automatic Gain Control** - Normalize volume differences

## Support

For issues or questions:
1. Check this guide
2. Run test suite: `python tests/test_dual_capture.py`
3. Check logs in `/tmp/sales-rpg-ai/`
4. Review architecture docs: `docs/audio-capture-architecture.md`
