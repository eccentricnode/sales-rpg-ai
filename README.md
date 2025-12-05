# Sales AI - Real-Time Sales Objection Detection & Response System

An AI-powered proof-of-concept application that listens to sales conversations in real-time, detects objections, and suggests helpful responses to sales representatives.

https://www.loom.com/share/e62a965e174e4464af5715c63beecc26

## Overview

This project is a POC to test the core value proposition: **"Can AI detect sales objections and suggest useful responses in real-time?"**

The system uses speech-to-text transcription to monitor live conversations, pattern matching to identify common sales objections, and provides pre-written response suggestions to help sales reps handle objections more effectively.

## Current Status

**✅ PROOF OF CONCEPT COMPLETE** - The full pipeline works end-to-end!

The project currently includes:
- **✅ Audio Transcription**: WhisperLive integration for real-time speech-to-text
- **✅ Objection Detection**: AI-powered analysis using OpenRouter LLM (Llama 3.3 70B)
- **✅ Response Suggestions**: Context-aware responses for detected objections
- **Working Script**: `src/transcribe_and_analyze.py` - Complete pipeline from audio → analysis
- **Test Suite**: `test_objection_detection.py` - Validate objection detection with mock data
- **Web Interface Skeleton**: FastAPI-based web server with HTMX frontend (basic structure)
- **MVP Documentation**: Detailed specification for next phase (see `docs/mvp.md`)

## Features

### ✅ Implemented (Working Now!)

- **Audio/Video Transcription**: WhisperLive server integration with multiple format support (MP4, MP3, WAV, etc.)
- **AI Objection Detection**: LLM-powered analysis detecting 4 objection types:
  - **PRICE**: Cost, budget, expense concerns
  - **TIME**: Not ready, need to think, timing issues
  - **DECISION_MAKER**: Need to consult spouse/partner/boss
  - **OTHER**: Any other objections
- **Smart Response Suggestions**: 3 context-aware responses per detected objection
- **Confidence Scoring**: HIGH/MEDIUM/LOW confidence levels for each detection
- **Smokescreen Detection**: Identifies if objection is genuine or hiding another concern
- **Interrupt Support**: Press Ctrl+C to analyze partial transcripts
- **Environment Config**: Auto-loads API keys from `.env` file
- **Test Suite**: Mock transcript testing to validate detection accuracy

### 🚧 In Progress (Next Phase)

- Real-time microphone audio capture (live conversations)
- Live transcript streaming UI
- Desktop GUI (Tkinter) for sales reps
- Chunked real-time analysis (analyze as conversation happens)
- Response caching and customization

## Project Structure

```
sales-rpg-ai/
├── src/
│   ├── transcribe_and_analyze.py  # Main pipeline: Audio → Transcript → Analysis
│   └── README.md                   # Detailed technical documentation
├── test_objection_detection.py    # Test suite with mock sales transcripts
├── main.py                         # Legacy Whisper testing script
├── pyproject.toml                  # Dependencies (FastAPI, WhisperLive, OpenAI)
├── .env                            # API keys (OPENROUTER_API_KEY)
├── QUICKSTART.md                   # 5-minute setup guide
├── README.md                       # This file
├── templates/
│   └── index.html                  # HTMX web interface (skeleton)
├── docs/
│   └── mvp.md                      # MVP specification
├── WhisperLive/                    # Real-time transcription library
└── test.mp4, test2.mp4             # Sample audio files for testing
```

## Technology Stack

### Current (Working)

- **Python 3.10+**: Core language
- **WhisperLive**: Real-time speech-to-text transcription via WebSocket
  - Supports Whisper base model for speed/accuracy balance
  - Multiple audio formats (MP4, MP3, WAV, M4A, FLAC)
  - PyAV (FFmpeg) for audio processing
- **OpenRouter API**: AI-powered objection analysis
  - Model: `meta-llama/llama-3.3-70b-instruct:free`
  - Free tier with excellent detection accuracy
- **OpenAI Python SDK**: Compatible with OpenRouter endpoint
- **FastAPI**: Web framework for API endpoints
- **HTMX**: Frontend interactivity
- **Jinja2**: HTML templating
- **Uvicorn**: ASGI server
- **UV**: Modern Python package manager

### Planned for Next Phase

- **Tkinter**: Desktop GUI for sales reps
- **PyAudio/SoundDevice**: Real-time microphone capture for live calls
- **Chunked Analysis**: Stream transcripts to LLM in real-time

## Quick Start

**See [QUICKSTART.md](QUICKSTART.md) for the 5-minute setup guide!**

### Prerequisites

- Python 3.10 or higher
- UV package manager (or pip)
- WhisperLive Docker server running on port 9090
- OpenRouter API key (free at https://openrouter.ai)

### Setup (3 Steps)

1. **Install dependencies:**
```bash
uv sync  # Installs ~3GB of dependencies (PyTorch, CUDA, etc.)
```

2. **Configure API key** - Add to `.env` file:
```bash
OPENROUTER_API_KEY=sk-or-v1-your-key-here
```

3. **Run the script:**
```bash
uv run python src/transcribe_and_analyze.py test.mp4
```

That's it! The script will transcribe the audio and detect objections.

## Usage

### Basic Usage - Transcribe & Analyze

```bash
# Transcribe an audio/video file and detect objections
uv run python src/transcribe_and_analyze.py test.mp4

# Use any audio format
uv run python src/transcribe_and_analyze.py path/to/sales-call.mp3

# Press Ctrl+C during transcription to analyze partial transcript
```

### Test Objection Detection

Test the AI detection with mock sales conversations:

```bash
uv run python test_objection_detection.py
```

This validates the detection works with known objections.

### What You'll See

```
OBJECTION #1:
Type: PRICE
Confidence: HIGH
Smokescreen: NO
Quote: "That's too expensive"

Suggested Responses:
1. "I understand budget is a concern. Let me show you the ROI..."
2. "What specific aspect of the pricing concerns you?"
3. "Many clients felt the same way initially, but found..."
```

## Current Results

### ✅ Objection Detection Working

The AI successfully detects and classifies:

1. **PRICE** - Cost, budget, expense concerns
2. **TIME** - Not ready, need to think, timing issues
3. **DECISION_MAKER** - Need to consult spouse/partner/boss
4. **OTHER** - Any other objections

### ✅ Success Metrics Achieved

- ✅ Detects objections accurately (validated with test suite)
- ✅ Provides 3 actionable responses per objection
- ✅ Confidence scoring (HIGH/MEDIUM/LOW)
- ✅ Smokescreen detection (genuine vs. hidden concerns)
- ✅ Works with pre-recorded and interruptible live transcription

### 🚧 Next Phase (MVP)

See [docs/mvp.md](docs/mvp.md) for next phase:

- Real-time microphone input
- Live transcript streaming
- Desktop UI (Tkinter)
- Chunked analysis (analyze as you speak)
- Response customization

## Output Formats

### Text Format (.txt)
Human-readable format with:
- Metadata (timestamp, file info, performance metrics)
- Full transcript
- Segmented transcript with timestamps

### JSON Format (.json)
Structured data including:
```json
{
  "metadata": {
    "timestamp": "ISO-8601 timestamp",
    "audio_file": "filename",
    "model": "model_name",
    "audio_duration_seconds": 75.0,
    "processing_time_seconds": 45.23,
    "processing_ratio": 0.6031
  },
  "transcript": "full transcript text",
  "segments": [
    {
      "start": 0.0,
      "end": 5.5,
      "text": "segment text"
    }
  ],
  "language": "detected_language"
}
```

## Development

### Testing Transcription

1. Use various audio files to test model accuracy
2. Compare different Whisper model sizes (tiny to large)
3. Measure performance trade-offs
4. Test with sales call recordings

### Next Steps

1. Implement real-time microphone capture
2. Build live transcript streaming
3. Add pattern-matching objection detection
4. Create response suggestion system
5. Build simple Tkinter UI
6. Conduct user testing with sales reps

## Performance Considerations

### Whisper Model Comparison

| Model  | Size   | Speed      | Accuracy |
|--------|--------|------------|----------|
| Tiny   | ~39MB  | Very Fast  | Lower    |
| Base   | ~74MB  | Fast       | Good     |
| Small  | ~244MB | Medium     | Better   |
| Medium | ~769MB | Slow       | Great    |
| Large  | ~1.5GB | Very Slow  | Best     |

For real-time usage, `tiny` or `base` models are recommended. The `base` model provides a good balance of speed and accuracy.

## Contributing

This is a proof-of-concept project. Contributions and feedback are welcome as the project evolves.

## License

[To be determined]

## Contact

[To be determined]

## Acknowledgments

- OpenAI Whisper for speech-to-text capabilities
- FastAPI and HTMX communities for excellent frameworks
