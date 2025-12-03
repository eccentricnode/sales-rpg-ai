# Transcribe and Analyze Script

Simple proof-of-concept script that tests the full pipeline: Audio → Transcription → Objection Analysis

## Architecture

```
Audio file → WhisperLive → Transcript → OpenRouter API → Objection Analysis → Print
```

## Prerequisites

1. **WhisperLive Server Running**
   ```bash
   # Should be running on localhost:9090
   # If using Docker:
   docker run -p 9090:9090 whisperlive-server
   ```

2. **OpenRouter API Key** (optional, for objection analysis)
   ```bash
   export OPENROUTER_API_KEY="your-key-here"
   ```

   Get a free API key at: https://openrouter.ai/

## Installation

```bash
# Install dependencies
uv sync
```

## Usage

### Basic Usage
```bash
python src/transcribe_and_analyze.py path/to/audio.mp4
```

### Example
```bash
# Transcribe test video
python src/transcribe_and_analyze.py test.mp4

# Transcribe WAV file
python src/transcribe_and_analyze.py audio/sales_call.wav
```

## Features

### 1. Audio Transcription
- Connects to WhisperLive server (localhost:9090)
- Supports multiple audio formats (MP4, MP3, WAV, etc.)
- Uses `base` Whisper model for speed/accuracy balance
- Captures transcript via callback

### 2. Objection Analysis
- Sends transcript to OpenRouter API
- Uses free tier model: `meta-llama/llama-3.2-3b-instruct:free`
- Analyzes for objection types:
  - **PRICE**: cost, budget, expense concerns
  - **TIME**: not ready, need to think
  - **DECISION_MAKER**: need to consult spouse/boss
  - **OTHER**: any other objections
- Provides:
  - Confidence level (HIGH/MEDIUM/LOW)
  - Smokescreen detection
  - 3 suggested responses per objection

## Output Format

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

[TRANSCRIPTION] This is getting expensive...
[TRANSCRIPTION] This is getting expensive, I need to think about it...

============================================================
TRANSCRIPTION COMPLETE
============================================================
Transcript length: 52 characters
============================================================

============================================================
STEP 2: ANALYZING FOR OBJECTIONS
============================================================

[INFO] Calling OpenRouter API...

============================================================
ANALYSIS COMPLETE
============================================================

============================================================
FINAL RESULTS
============================================================

📝 TRANSCRIPT:
------------------------------------------------------------
This is getting expensive, I need to think about it...
------------------------------------------------------------

🔍 OBJECTION ANALYSIS:
------------------------------------------------------------
OBJECTION #1:
Type: PRICE
Confidence: HIGH
Smokescreen: MAYBE
Quote: "This is getting expensive"

Suggested Responses:
1. "I understand budget is important. Let me break down the ROI..."
2. "What specifically about the price concerns you?"
3. "Many clients felt the same way initially, but found..."

OBJECTION #2:
Type: TIME
Confidence: MEDIUM
Smokescreen: YES
Quote: "I need to think about it"

Suggested Responses:
1. "What specific aspects would you like to think about?"
2. "I appreciate you taking time to consider this carefully..."
3. "What information would help you make a decision today?"
------------------------------------------------------------

✅ Model used: meta-llama/llama-3.2-3b-instruct:free
============================================================
```

## Script Workflow

1. **Validate Input**: Check if audio file exists
2. **Transcribe**: Connect to WhisperLive, stream audio, capture transcript
3. **Analyze**: Send transcript to OpenRouter for objection detection
4. **Display**: Pretty-print transcript and analysis

## Troubleshooting

### WhisperLive Server Not Running
```
❌ ERROR: No transcript generated. Check if WhisperLive server is running.
```
**Solution**: Start the WhisperLive server on port 9090

### No API Key
```
[WARNING] No OpenRouter API key found. Set OPENROUTER_API_KEY environment variable.
[WARNING] Skipping objection analysis.
```
**Solution**: Set the environment variable or analysis will be skipped

### File Not Found
```
❌ ERROR: Audio file not found: test.mp4
```
**Solution**: Provide valid path to audio file

## Technical Details

### TranscriptCapture Class
- Custom callback handler for WhisperLive
- Captures transcript text and segments in real-time
- Prints transcription progress

### OpenRouter Integration
- Endpoint: `https://openrouter.ai/api/v1`
- Compatible with OpenAI SDK
- Free tier model for testing
- Structured prompt for consistent analysis

## Next Steps

This script proves the full pipeline works. Future enhancements:
- [ ] Real-time microphone input
- [ ] GUI interface (Tkinter)
- [ ] Response suggestion caching
- [ ] Multiple LLM model support
- [ ] Confidence threshold filtering
- [ ] Export results to JSON/CSV

## Testing

Test with included files:
```bash
# Test with MP4 video
python src/transcribe_and_analyze.py test.mp4

# Test with another video
python src/transcribe_and_analyze.py test2.mp4
```
