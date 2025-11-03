# Sales AI - Real-Time Sales Objection Detection & Response System

An AI-powered proof-of-concept application that listens to sales conversations in real-time, detects objections, and suggests helpful responses to sales representatives.

https://www.loom.com/share/e62a965e174e4464af5715c63beecc26

## Overview

This project is a POC to test the core value proposition: **"Can AI detect sales objections and suggest useful responses in real-time?"**

The system uses speech-to-text transcription to monitor live conversations, pattern matching to identify common sales objections, and provides pre-written response suggestions to help sales reps handle objections more effectively.

## Current Status

The project currently includes:
- **Whisper Transcription Testing**: A Python script (`main.py`) that transcribes audio/video files using OpenAI's Whisper model with performance metrics
- **Web Interface Skeleton**: A FastAPI-based web server with HTMX frontend (basic structure in place)
- **MVP Documentation**: Detailed specification for the minimum viable product (see `docs/mvp.md`)

## Features

### Implemented
- Audio/video transcription using Whisper
- Performance benchmarking (processing time, real-time ratio)
- Segmented transcript generation with timestamps
- Results export to JSON and text formats
- Basic web server structure with FastAPI
- HTMX-powered frontend template

### Planned (MVP)
- Real-time microphone audio capture
- Live transcript display
- Sales objection detection (3 types: Price, Time, Spouse)
- Response suggestion system
- Simple desktop UI (Tkinter)

## Project Structure

```
sales-ai/
├── main.py                 # Whisper transcription testing script
├── pyproject.toml         # Python dependencies and project metadata
├── templates/
│   └── index.html         # HTMX-based web interface
├── docs/
│   └── mvp.md            # MVP specification and roadmap
├── test.mp4              # Sample audio/video for testing
└── test-transcript-*.{txt,json}  # Generated transcription outputs
```

## Technology Stack

### Current
- **Python 3.10+**: Core language
- **OpenAI Whisper**: Speech-to-text transcription
- **FastAPI**: Web framework for API endpoints
- **HTMX**: Frontend interactivity without JavaScript complexity
- **Jinja2**: HTML templating
- **Uvicorn**: ASGI server

### Planned for MVP
- **Pattern Matching**: Simple keyword-based objection detection
- **Tkinter**: Desktop GUI (built into Python)
- **PyAudio/SoundDevice**: Real-time microphone capture

## Installation

### Prerequisites
- Python 3.10 or higher
- UV package manager (recommended) or pip

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd sales-ai
```

2. Install dependencies using UV:
```bash
uv sync
```

Or using pip:
```bash
pip install -e .
```

3. For Whisper functionality, you may need to install ffmpeg:
```bash
# Ubuntu/Debian
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html
```

## Usage

### Transcription Testing

To test the Whisper transcription with performance metrics:

1. Place an audio or video file in the project directory (e.g., `test.mp4`)

2. Edit `main.py` to configure:
   - `AUDIO_FILE`: Path to your audio/video file
   - `MODEL_NAME`: Whisper model size (`tiny`, `base`, `small`, `medium`, `large`)

3. Run the transcription:
```bash
python main.py
```

The script will:
- Load the Whisper model
- Transcribe the audio with timing metrics
- Display results in the console
- Save outputs as `test-transcript-TIMESTAMP-DURATION.{txt,json}`

### Performance Metrics

The transcription script measures:
- **Model load time**: Time to load the Whisper model
- **Processing time**: Total time to transcribe the audio
- **Audio duration**: Length of the input audio
- **Processing ratio**: Processing time / audio duration
- **Real-time status**: Whether processing is faster or slower than real-time

Example output:
```
Audio duration: 75.00s (1.25 minutes)
Processing time: 45.23s (0.75 minutes)
Processing ratio: 0.60x (FASTER than real-time)
```

### Web Server (In Development)

To run the basic web interface:

```bash
uvicorn main:app --reload
```

Visit `http://localhost:8000` in your browser (note: functionality is limited in current version).

## MVP Roadmap

See `docs/mvp.md` for detailed MVP specifications.

### Target Objection Types (Phase 1)

1. **Price Objections**: "expensive", "cost", "budget", "price"
2. **Time Objections**: "think about it", "not ready", "later"
3. **Spouse/Decision-Maker Objections**: "talk to my wife", "discuss", "ask"

### Success Criteria
- 70%+ objection detection accuracy
- Response suggestions are actionable and helpful
- Sales reps find the tool valuable (not annoying)
- Latency is acceptable for real-time use

### Out of Scope (For Now)
- Invisible overlay UI
- <150ms processing latency
- Machine learning classification
- Custom response training
- Multi-language support
- Cloud deployment

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
