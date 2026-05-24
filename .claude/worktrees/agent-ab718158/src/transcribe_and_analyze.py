#!/usr/bin/env python3
"""
Transcribe audio file and analyze for sales objections.

Usage:
    python src/transcribe_and_analyze.py <audio_file_path>
"""

import sys
import os
from pathlib import Path
from openai import OpenAI


# Load environment variables from .env file
env_file = Path(__file__).parent.parent / '.env'
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()


class TranscriptCapture:
    """Captures transcript output from WhisperLive client."""

    def __init__(self):
        self.transcript_text = ""
        self.segments = []

    def callback(self, text: str, segments: list):
        """
        Callback function for WhisperLive transcription.

        Args:
            text: The current transcript text (may be partial)
            segments: List of transcript segments with timing info
        """
        self.transcript_text = text
        self.segments = segments
        print(f"[TRANSCRIPTION] {text}")


def transcribe_audio(audio_path: str, host: str = "localhost", port: int = 9090) -> str:
    """
    Transcribe audio file using WhisperLive server.

    Args:
        audio_path: Path to audio file
        host: WhisperLive server host
        port: WhisperLive server port

    Returns:
        Complete transcript text
    """
    from whisper_live.client import TranscriptionClient

    print(f"\n{'='*60}")
    print(f"STEP 1: TRANSCRIBING AUDIO")
    print(f"{'='*60}")
    print(f"Audio file: {audio_path}")
    print(f"Server: {host}:{port}")
    print(f"{'='*60}\n")

    # Create transcript capture
    capture = TranscriptCapture()

    # Connect to WhisperLive server with callback
    client = TranscriptionClient(
        host=host,
        port=port,
        model='base',
        log_transcription=False,  # Disable default logging
        transcription_callback=capture.callback
    )

    # Transcribe the audio file
    try:
        client(audio_path)
    except KeyboardInterrupt:
        print("\n[INFO] Transcription interrupted by user")

    # Get the final transcript
    final_transcript = capture.transcript_text

    print(f"\n{'='*60}")
    print("TRANSCRIPTION COMPLETE")
    print(f"{'='*60}")
    print(f"Transcript length: {len(final_transcript)} characters")
    print(f"{'='*60}\n")

    return final_transcript


def analyze_objections(transcript: str, api_key: str = None) -> dict:
    """
    Analyze transcript for sales objections using OpenRouter API.

    Args:
        transcript: The transcript text to analyze
        api_key: OpenRouter API key (defaults to OPENROUTER_API_KEY env var)

    Returns:
        Analysis results as dict
    """
    print(f"\n{'='*60}")
    print(f"STEP 2: ANALYZING FOR OBJECTIONS")
    print(f"{'='*60}\n")

    # Get API key from environment if not provided
    if api_key is None:
        api_key = os.getenv('OPENROUTER_API_KEY')

    if not api_key:
        print("[WARNING] No OpenRouter API key found. Set OPENROUTER_API_KEY environment variable.")
        print("[WARNING] Skipping objection analysis.\n")
        return {
            "error": "No API key provided",
            "transcript": transcript
        }

    # Initialize OpenAI client with OpenRouter endpoint
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    # Construct analysis prompt
    prompt = f"""You are a sales expert analyzing a conversation for objections.

TRANSCRIPT:
{transcript}

TASK:
Analyze this transcript and identify any sales objections. For each objection found:

1. OBJECTION TYPE: Classify as one of:
   - PRICE: concerns about cost, budget, expense
   - TIME: not ready, need to think, timing issues
   - DECISION_MAKER: need to consult spouse/partner/boss
   - OTHER: any other objection

2. CONFIDENCE: How confident are you this is a real objection? (HIGH/MEDIUM/LOW)

3. IS_SMOKESCREEN: Is this a genuine concern or a smokescreen for something else? (YES/NO/MAYBE)

4. SUGGESTED_RESPONSES: Provide 3 specific response suggestions that would help address this objection.

FORMAT YOUR RESPONSE AS:
```
OBJECTION #1:
Type: [TYPE]
Confidence: [CONFIDENCE]
Smokescreen: [YES/NO/MAYBE]
Quote: "[exact quote from transcript]"

Suggested Responses:
1. [First response]
2. [Second response]
3. [Third response]

[Repeat for each objection found]
```

If NO objections found, respond with: "NO_OBJECTIONS_DETECTED"
"""

    try:
        # Make API call (using free model)
        print("[INFO] Calling OpenRouter API...")
        response = client.chat.completions.create(
            model="meta-llama/llama-3.3-70b-instruct:free",  # Free tier model
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=1500,
            temperature=0.7,
        )

        analysis = response.choices[0].message.content

        print(f"\n{'='*60}")
        print("ANALYSIS COMPLETE")
        print(f"{'='*60}\n")

        return {
            "success": True,
            "analysis": analysis,
            "transcript": transcript,
            "model": "meta-llama/llama-3.3-70b-instruct:free"
        }

    except Exception as e:
        print(f"[ERROR] API call failed: {e}\n")
        return {
            "error": str(e),
            "transcript": transcript
        }


def print_results(results: dict):
    """Pretty print the analysis results."""
    print(f"\n{'='*60}")
    print("FINAL RESULTS")
    print(f"{'='*60}\n")

    if "error" in results:
        print(f"❌ ERROR: {results['error']}\n")
        print("TRANSCRIPT:")
        print(results['transcript'])
        return

    print("📝 TRANSCRIPT:")
    print("-" * 60)
    print(results['transcript'])
    print("-" * 60)

    print("\n🔍 OBJECTION ANALYSIS:")
    print("-" * 60)
    print(results['analysis'])
    print("-" * 60)

    print(f"\n✅ Model used: {results.get('model', 'N/A')}")
    print(f"{'='*60}\n")


def main():
    """Main execution function."""
    if len(sys.argv) < 2:
        print("Usage: python src/transcribe_and_analyze.py <audio_file_path>")
        print("\nExample:")
        print("  python src/transcribe_and_analyze.py test.mp4")
        print("  python src/transcribe_and_analyze.py audio/sales_call.wav")
        sys.exit(1)

    audio_path = sys.argv[1]

    # Check if file exists
    if not Path(audio_path).exists():
        print(f"❌ ERROR: Audio file not found: {audio_path}")
        sys.exit(1)

    print(f"\n{'#'*60}")
    print("SALES OBJECTION DETECTOR")
    print(f"{'#'*60}\n")

    # Step 1: Transcribe audio
    transcript = transcribe_audio(audio_path)

    if not transcript or len(transcript.strip()) == 0:
        print("❌ ERROR: No transcript generated. Check if WhisperLive server is running.")
        sys.exit(1)

    # Step 2: Analyze for objections
    results = analyze_objections(transcript)

    # Step 3: Print results
    print_results(results)


if __name__ == "__main__":
    main()
