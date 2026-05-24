# Dual Audio Stream Capture Architecture

## Overview

This document describes the architecture for capturing and transcribing two separate audio streams simultaneously to achieve perfect speaker diarization in sales calls.

## The Problem

Traditional speech recognition with diarization requires ML models to guess who is speaking based on voice characteristics. This is error-prone and computationally expensive.

## Our Solution: Source Separation

Instead of guessing speakers, we capture audio from two physically separate sources:

1. **Microphone Input** → Sales representative audio
2. **System Audio Output** → Customer audio (from Zoom/Discord/etc)

This provides perfect diarization with zero ML overhead - we know exactly who is speaking based on which audio source captured it.

## Technical Architecture

```
Sales Call Application (Zoom/Discord/etc)
    │
    ├─> Microphone → pactl/PyAudio → mic_audio.wav → WhisperLive → [SALES_REP] segments
    │
    └─> System Output → PulseAudio Monitor → system_audio.wav → WhisperLive → [CUSTOMER] segments
         │
         ▼
    Timestamp-based merge → Unified transcript with speaker labels
```

## Audio Capture Implementation

### Platform: Linux with PulseAudio/PipeWire

PipeWire provides full PulseAudio compatibility, so `pactl` commands work seamlessly.

### Available Audio Sources

List sources (microphones and monitors):
```bash
pactl list sources short
```

Example output:
```
687  alsa_input.pci-0000_74_00.6.analog-stereo               # Built-in mic
688  alsa_output.usb-Schiit_Audio_Schiit_Modi_-00.analog-stereo.monitor  # System audio monitor
691  alsa_input.usb-Shure_Inc_Shure_MV7__MV7__12...mono-fallback  # USB microphone
```

### Capture Methods

#### Method 1: pactl (Recommended for System Audio)

Advantages:
- Clean, simple command-line interface
- Built-in WAV file output
- Handles resampling automatically
- Works perfectly with monitor sources

```bash
# Capture microphone
pactl record --device=alsa_input.usb-Shure_Inc_Shure_MV7... \
             --file-format=wav \
             --rate=16000 \
             --channels=1 \
             mic_audio.wav

# Capture system audio (monitor source)
pactl record --device=alsa_output.usb-Schiit_Audio...monitor \
             --file-format=wav \
             --rate=16000 \
             --channels=1 \
             system_audio.wav
```

#### Method 2: PyAudio (Alternative for Microphone)

Advantages:
- More control over buffer management
- Already used in test_audio_capture.py
- Good for streaming scenarios

```python
import pyaudio
import wave

CHUNK = 4096
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000

p = pyaudio.PyAudio()
stream = p.open(format=FORMAT, channels=CHANNELS,
                rate=RATE, input=True,
                frames_per_buffer=CHUNK)

# Read and write chunks
frames = []
for i in range(num_chunks):
    data = stream.read(CHUNK)
    frames.append(data)

# Save to WAV
wf = wave.open("mic_audio.wav", "wb")
wf.setnchannels(CHANNELS)
wf.setsampwidth(p.get_sample_size(FORMAT))
wf.setframerate(RATE)
wf.writeframes(b''.join(frames))
wf.close()
```

## Audio Format Requirements

WhisperLive expects:
- **Sample Rate**: 16kHz (16000 Hz)
- **Channels**: Mono (1 channel)
- **Format**: 16-bit PCM (paInt16)
- **Encoding**: WAV

Both capture methods must produce audio matching these specifications.

## Transcription Pipeline

### Parallel Transcription

Both audio streams are transcribed simultaneously using separate WhisperLive connections:

```python
# Two independent WhisperLive clients
mic_client = TranscriptionClient(
    host="localhost",
    port=9090,
    lang="en"
)

system_client = TranscriptionClient(
    host="localhost",
    port=9091,  # Different port or separate server instance
    lang="en"
)

# Stream both files concurrently
asyncio.gather(
    mic_client.transcribe_file("mic_audio.wav"),
    system_client.transcribe_file("system_audio.wav")
)
```

### Speaker Labeling

Each transcription segment is labeled based on its source:

```python
# Microphone stream → Sales rep
for segment in mic_segments:
    segment["speaker"] = "SALES_REP"

# System audio stream → Customer
for segment in system_segments:
    segment["speaker"] = "CUSTOMER"
```

### Timestamp-Based Merge

Segments from both streams are merged chronologically:

```python
all_segments = sorted(
    mic_segments + system_segments,
    key=lambda s: s["start"]
)

# Result:
# [
#   {"speaker": "SALES_REP", "text": "Hi, how are you?", "start": 0.5, "end": 2.1},
#   {"speaker": "CUSTOMER", "text": "I'm doing well", "start": 2.3, "end": 4.0},
#   ...
# ]
```

## Async Architecture

All capture and transcription operations run asynchronously to maintain real-time performance:

```python
async def dual_capture_and_transcribe():
    # Start both captures
    mic_task = asyncio.create_task(capture_microphone())
    system_task = asyncio.create_task(capture_system_audio())

    # Start both transcriptions
    mic_transcribe = asyncio.create_task(transcribe_mic_stream())
    system_transcribe = asyncio.create_task(transcribe_system_stream())

    # Wait for completion or cancellation
    await asyncio.gather(
        mic_task, system_task,
        mic_transcribe, system_transcribe
    )
```

## Lifecycle Management

### Startup
1. Detect available audio devices
2. Select microphone source (or use default)
3. Identify system audio monitor
4. Start both capture processes
5. Initialize WhisperLive connections
6. Begin transcription

### Runtime
1. Audio continuously captured to WAV files
2. Transcription runs in real-time
3. Segments labeled and merged
4. Results streamed to WebSocket clients

### Shutdown
1. Stop capture processes gracefully
2. Close WhisperLive connections
3. Flush remaining audio data
4. Finalize WAV files

## Performance Characteristics

### Latency
- **Audio Capture**: Near-zero latency (direct hardware access)
- **Transcription**: ~300-500ms per segment (WhisperLive)
- **Merge Operation**: <10ms (simple sort)
- **Total**: ~500ms end-to-end latency

### Resource Usage
- **CPU**: Moderate (two transcription streams)
- **Memory**: Low (~50MB per audio stream)
- **Disk I/O**: Minimal (streaming WAV writes)

## Deployment Considerations

### Production Requirements
1. WhisperLive server running and accessible
2. PulseAudio/PipeWire configured
3. Appropriate audio devices available
4. Sufficient CPU for dual transcription

### Error Handling
- Device not found → Fallback to default or notify user
- Transcription failure → Continue other stream, log error
- Connection loss → Attempt reconnect with backoff

### Testing
- Mock audio devices for CI/CD
- Pre-recorded test audio files
- Latency benchmarks
- Speaker label accuracy validation

## Future Enhancements

1. **VAD Integration**: Voice Activity Detection to reduce silent segments
2. **Dynamic Device Selection**: Allow runtime device switching
3. **Multi-Party Support**: Support >2 speakers with additional streams
4. **Quality Monitoring**: Detect and alert on poor audio quality
5. **Automatic Gain Control**: Normalize volume differences

## References

- PulseAudio Documentation: https://www.freedesktop.org/wiki/Software/PulseAudio/
- PipeWire Documentation: https://pipewire.org/
- WhisperLive: https://github.com/collabora/WhisperLive
- PyAudio: https://people.csail.mit.edu/hubert/pyaudio/
