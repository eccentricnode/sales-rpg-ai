# Quick Start Guide - Sales Objection Detector

## What This Does

Transcribes audio files and analyzes them for sales objections in real-time.

**Full Pipeline**: Audio File → WhisperLive → Transcript → OpenRouter AI → Objection Analysis

## Setup (5 minutes)

### 1. Start WhisperLive Server

Make sure your WhisperLive Docker server is running on port 9090:

```bash
# Check if running
docker ps | grep 9090

# If not running, start it
# (use your existing docker command)
```

### 2. Get OpenRouter API Key (Required for Objection Analysis)

1. Visit <https://openrouter.ai/>
2. Sign up for free account
3. Get your API key
4. Add to `.env` file:

```bash
# Create .env file in project root
OPENROUTER_API_KEY=sk-or-v1-your-key-here
```

**Note**: Without the API key, you'll get the transcript but not the objection analysis. The script auto-loads from `.env`.

### 3. Install Dependencies

```bash
# This will install all required packages including whisper-live
uv sync
```

**Note**: This will download ~3GB of dependencies (PyTorch, CUDA libraries, etc.). It may take a few minutes.

## Usage

### Run the Script

```bash
uv run python src/transcribe_and_analyze.py test.mp4
```

Or activate the virtual environment first:

```bash
source .venv/bin/activate
python src/transcribe_and_analyze.py test.mp4
```

### With Custom Audio File

```bash
uv run python src/transcribe_and_analyze.py path/to/your/audio.mp4
```

## What You'll See

```
############################################################
SALES OBJECTION DETECTOR
############################################################

============================================================
STEP 1: TRANSCRIBING AUDIO
============================================================
Audio file: test.mp4
Server: localhost:9090
============================================================

[TRANSCRIPTION] That sounds expensive...
[TRANSCRIPTION] That sounds expensive. I'll need to think about it...

============================================================
TRANSCRIPTION COMPLETE
============================================================

============================================================
STEP 2: ANALYZING FOR OBJECTIONS
============================================================

[INFO] Calling OpenRouter API...

============================================================
FINAL RESULTS
============================================================

📝 TRANSCRIPT:
------------------------------------------------------------
That sounds expensive. I'll need to think about it...
------------------------------------------------------------

🔍 OBJECTION ANALYSIS:
------------------------------------------------------------
OBJECTION #1:
Type: PRICE
Confidence: HIGH
Smokescreen: MAYBE
Quote: "That sounds expensive"

Suggested Responses:
1. "I understand budget is a concern. Let me show you the ROI..."
2. "What specific aspect of the pricing concerns you most?"
3. "Many clients initially felt the same way, but found..."
------------------------------------------------------------
```

## Success Criteria ✅

- [x] Script runs without errors
- [x] Audio file is transcribed
- [x] Transcript is displayed
- [x] Objections are detected (if API key provided)
- [x] Response suggestions are shown
- [x] Full pipeline completes end-to-end

## Troubleshooting

### "No module named 'openai'"
**Solution**: Use `uv run python ...` or activate virtual environment first

### "Audio file not found"
**Solution**: Check the file path. Use relative or absolute path.

### "No transcript generated"
**Solution**:
1. Check WhisperLive server is running: `docker ps | grep 9090`
2. Test server connection: `curl http://localhost:9090`

### "No OpenRouter API key found"
**Solution**:
- Set environment variable: `export OPENROUTER_API_KEY="your-key"`
- Or run without it (you'll still get transcripts, just no analysis)

## What's Next?

Now that the full pipeline works, you can:

1. **Test with real sales calls**: Try with your actual recorded sales conversations
2. **Adjust the prompt**: Edit [src/transcribe_and_analyze.py](src/transcribe_and_analyze.py) to customize objection detection
3. **Add real-time mic input**: Modify script to use live microphone instead of files
4. **Build the UI**: Create Tkinter interface as per MVP spec

## Technical Details

- **Transcription Model**: Whisper `base` (good balance of speed/accuracy)
- **AI Model**: `meta-llama/llama-3.3-70b-instruct:free` (OpenRouter free tier)
- **Audio Formats Supported**: MP4, MP3, WAV, M4A, FLAC, etc. (anything FFmpeg can read)
- **Server**: WhisperLive WebSocket (localhost:9090)
- **Detection Types**: PRICE, TIME, DECISION_MAKER, OTHER
- **Features**: Confidence scoring, smokescreen detection, 3 responses per objection

## Files Created

```
src/
├── transcribe_and_analyze.py    # Main script
└── README.md                     # Detailed documentation
```

## MVP Status

**✅ PROOF OF CONCEPT COMPLETE**

Core value proposition tested:
> "Can AI detect sales objections and suggest useful responses?"

**Answer**: YES! The full pipeline works end-to-end.

Next phase: Build real-time mic input + simple UI (as per [docs/mvp.md](docs/mvp.md))
