# PRD: Microphone Input for Live Demo (CLI)

## Problem

We have built a real-time objection detection system (Phase 2 core), but it's only been tested with pre-recorded audio files. To validate the product with real users and demonstrate value, we need **live microphone input** working end-to-end.

The current `--mic` flag in `realtime_transcribe.py` is implemented but **untested on Linux**. We need to verify it works, identify blockers, and ensure a smooth demo experience.

---

## Relationship to Other PRDs

This PRD **complements** `prd-web-ui-microphone.md`:

| PRD | Use Case | Input Method | Output |
|-----|----------|--------------|--------|
| `prd-microphone-input.md` (this) | Local dev/testing | PyAudio CLI | Terminal |
| `prd-web-ui-microphone.md` | Demos/deployment | Browser MediaRecorder | Web UI |

**Both share the same core pipeline:**
- `DualBufferManager` - buffers transcript chunks
- `AnalysisOrchestrator` - async LLM calls
- `StreamingAnalyzer` - objection detection

This CLI approach is useful for:
- **Developers** testing locally without Docker
- **Debugging** audio issues directly
- **Quick iteration** without browser overhead

---

## Solution

Enable and validate live microphone input on Linux, ensuring:
1. Audio capture works with the system's default microphone
2. Transcription streams to WhisperLive correctly
3. Objection detection triggers and displays suggestions in real-time
4. Clean start/stop experience for demos

---

## Acceptance Criteria

- [ ] `python src/realtime_transcribe.py --mic` captures audio from Linux microphone
- [ ] Live speech appears as `[TRANSCRIPT]` output within ~1 second
- [ ] Objections in speech trigger `!!! OBJECTION DETECTED !!!` with suggestions
- [ ] Ctrl+C cleanly stops recording and shows session summary
- [ ] Works for at least 5 minutes continuously without errors
- [ ] Dependencies are documented (PyAudio, PortAudio, etc.)

---

## Technical Analysis

### Existing Implementation

The microphone path already exists in `realtime_transcribe.py:184-217`:

```python
def run_microphone(self) -> None:
    client = TranscriptionClient(
        host=self.host,
        port=self.port,
        model="base",
        log_transcription=False,
        transcription_callback=self._on_transcript_chunk,
    )
    client()  # No argument = microphone
```

This calls WhisperLive's `TranscriptionClient` without an audio file argument, which triggers the `record()` method in `WhisperLive/whisper_live/client.py:579`.

### WhisperLive's Microphone Implementation

WhisperLive uses **PyAudio** for microphone capture (`client.py:7`):

```python
import pyaudio

# In TranscriptionTeeClient.__init__:
self.p = pyaudio.PyAudio()
self.stream = self.p.open(
    format=self.format,
    channels=self.channels,
    rate=self.rate,
    input=True,
    frames_per_buffer=self.chunk,
)
```

Configuration (from `client.py:329-332`):
- Format: `pyaudio.paInt16` (16-bit)
- Channels: 1 (mono)
- Sample rate: 16000 Hz
- Chunk size: 4096 frames

### Linux Dependencies

PyAudio requires **PortAudio** system library:

```bash
# Arch Linux (primary test platform)
sudo pacman -S portaudio

# Debian/Ubuntu
sudo apt-get install portaudio19-dev python3-pyaudio

# Fedora
sudo dnf install portaudio-devel
```

**Arch Linux Notes:**
- Arch uses **PipeWire** by default (since ~2022), which provides PulseAudio compatibility
- PyAudio works through PipeWire's PulseAudio layer - no extra config needed
- Ensure `pipewire-pulse` is installed: `pacman -Q pipewire-pulse`
- If using pure ALSA (no PipeWire), may need additional configuration

### Potential Issues

| Issue | Risk | Mitigation |
|-------|------|------------|
| PortAudio not installed | High | Document in setup, check on startup |
| Wrong audio device selected | Medium | Add device listing/selection |
| Permission denied (audio group) | Medium | Document user group requirement |
| PulseAudio/PipeWire conflicts | Low | Test on common Linux setups |
| Buffer overflows at high CPU | Low | WhisperLive handles with `exception_on_overflow=False` |

---

## Implementation Tasks

### Task 1: Verify Linux Dependencies

**Goal**: Ensure PyAudio and PortAudio are properly installed.

1. Check if `pyaudio` is in dependencies (it's a transitive dep of whisper-live)
2. Test import: `python -c "import pyaudio; print('OK')"`
3. If missing, document installation steps

### Task 2: List Available Audio Devices

**Goal**: Add device listing to help users identify correct microphone.

Add `--list-devices` flag that prints:
```
Available audio input devices:
  [0] Built-in Microphone
  [1] USB Headset
  [2] ...
```

### Task 3: Test Basic Microphone Capture

**Goal**: Verify audio is being captured and sent to WhisperLive.

1. Run `python src/realtime_transcribe.py --mic --verbose`
2. Speak into microphone
3. Verify `[TRANSCRIPT]` lines appear
4. Verify `[LLM RESPONSE]` lines appear

### Task 4: Test Objection Detection Flow

**Goal**: Verify objections are detected in live speech.

1. Run `python src/realtime_transcribe.py --mic`
2. Speak phrases containing objections:
   - "That's too expensive for our budget"
   - "I need to talk to my manager about this"
   - "We're not ready to make a decision right now"
3. Verify `!!! OBJECTION DETECTED !!!` banners appear

### Task 5: Add Graceful Error Handling

**Goal**: Provide clear errors when microphone access fails.

Handle common failures:
- No microphone available
- Permission denied
- PortAudio not installed

Example:
```python
try:
    client()
except OSError as e:
    if "No Default Input Device" in str(e):
        print("ERROR: No microphone detected.")
        print("Check your audio settings or specify a device with --device")
    elif "PortAudio" in str(e):
        print("ERROR: PortAudio not installed.")
        print("Run: sudo apt-get install portaudio19-dev")
```

### Task 6: Add Device Selection (Optional)

**Goal**: Allow users to specify which microphone to use.

Add `--device <id>` flag to select audio input device by index.

### Task 7: Document Setup and Usage

**Goal**: Update README with microphone setup instructions.

Add section:
```markdown
## Microphone Setup (Linux)

### Prerequisites
sudo apt-get install portaudio19-dev

### Usage
python src/realtime_transcribe.py --mic

### Troubleshooting
- List devices: python src/realtime_transcribe.py --list-devices
- Select device: python src/realtime_transcribe.py --mic --device 1
```

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Time to first transcript | < 2 seconds from speaking |
| Objection detection latency | < 5 seconds end-to-end |
| Continuous operation | 5+ minutes without error |
| Setup time for new user | < 5 minutes with docs |

---

## Out of Scope

- GUI/visual interface (Phase 2 remaining)
- Windows/macOS support (Linux only for now)
- Multiple microphone streams
- Echo cancellation / noise reduction
- Recording/playback of sessions

---

## Dependencies

### System (Linux)
- PortAudio (`portaudio19-dev` or equivalent)
- Working microphone
- User in `audio` group (if permission issues)

### Python (via whisper-live)
- PyAudio (transitive dependency)

---

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| PyAudio install fails | Medium | High | Provide alternative (sounddevice) |
| Audio quality too poor | Low | Medium | Document microphone requirements |
| WhisperLive drops connection | Low | High | Add reconnection logic |

---

## Timeline Estimate

| Task | Effort |
|------|--------|
| Verify dependencies | 15 min |
| List audio devices | 30 min |
| Test basic capture | 15 min |
| Test objection flow | 15 min |
| Error handling | 30 min |
| Device selection | 30 min (optional) |
| Documentation | 20 min |
| **Total** | **~2-3 hours** |

---

## Next Steps

1. Verify PyAudio is available in current environment
2. Test `--mic` flag with current implementation
3. Identify and fix any blockers
4. Add device listing feature
5. Update documentation
