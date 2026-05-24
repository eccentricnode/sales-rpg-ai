#!/usr/bin/env python3
"""
Test WhisperLiveKit diarization with GitHub Models or OpenRouter.

Usage:
    python test_diarization.py test.mp4
    python test_diarization.py --provider openrouter test.mp4
"""

import os
import sys
import argparse
from pathlib import Path
from openai import OpenAI

# Load environment variables
env_file = Path(__file__).parent / '.env'
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()


def get_provider_config(provider_name):
    """Get configuration for a specific provider."""
    provider = provider_name.lower()

    if provider == "github":
        token = os.getenv("GITHUB_TOKEN", "")
        model = os.getenv("GITHUB_MODEL", "gpt-4o-mini")
        base_url = "https://models.github.ai/inference"
        if not token:
            raise ValueError("GITHUB_TOKEN not set")
        return token, base_url, model

    elif provider == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY", "")
        model = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
        base_url = "https://openrouter.ai/api/v1"
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY not set")
        return api_key, base_url, model

    else:
        raise ValueError(f"Unknown provider: {provider}")


def transcribe_with_diarization(audio_path: str):
    """Transcribe audio with speaker diarization using WhisperLiveKit."""
    from whisperlivekit import TranscriptionEngine

    print(f"\n{'='*60}")
    print("TRANSCRIBING WITH SPEAKER DIARIZATION")
    print(f"{'='*60}")
    print(f"Audio file: {audio_path}")
    print(f"Tool: WhisperLiveKit + Sortformer")
    print(f"{'='*60}\n")

    # Initialize engine with diarization
    engine = TranscriptionEngine(
        model="base",
        diarization=True,  # Enable speaker diarization
        lan="en"
    )

    # Transcribe
    print("[INFO] Processing audio...")
    result = engine.transcribe_file(audio_path)

    # Extract segments
    segments = []
    for seg in result.get("segments", []):
        segments.append({
            "text": seg.get("text", "").strip(),
            "speaker": seg.get("speaker", "UNKNOWN"),
            "start": seg.get("start", 0.0),
            "end": seg.get("end", 0.0),
        })

    print(f"[INFO] Transcribed {len(segments)} segments")
    print(f"\n{'='*60}")
    print("TRANSCRIPT WITH SPEAKERS")
    print(f"{'='*60}\n")

    # Display transcript with speakers
    for i, seg in enumerate(segments[:10], 1):  # Show first 10
        print(f"[{seg['speaker']}] {seg['text']}")

    if len(segments) > 10:
        print(f"\n... ({len(segments) - 10} more segments)")

    return segments


def analyze_sales_objections(segments, provider="github"):
    """Analyze transcript for sales objections with speaker context."""

    print(f"\n{'='*60}")
    print("ANALYZING FOR OBJECTIONS")
    print(f"{'='*60}\n")

    # Get provider config
    api_key, base_url, model = get_provider_config(provider)

    # Build transcript with speaker labels
    transcript_lines = []
    for seg in segments:
        speaker = seg['speaker']
        text = seg['text']
        transcript_lines.append(f"{speaker}: {text}")

    transcript = "\n".join(transcript_lines)

    # Analysis prompt
    prompt = f"""You are analyzing a sales call transcript with speaker labels.

TRANSCRIPT (with speakers):
{transcript[:2000]}  # First 2000 chars

TASK:
1. Identify which speaker is the SALES REP and which is the CUSTOMER
2. Analyze CUSTOMER statements for objections (PRICE, TIME, DECISION_MAKER, OTHER)
3. For each objection, suggest a response

FORMAT:
```
SPEAKER IDENTIFICATION:
Sales Rep: [SPEAKER_XX]
Customer: [SPEAKER_YY]

OBJECTION #1:
Type: [TYPE]
Customer Quote: "[quote]"
Suggested Response: "[response]"
```

If no objections, respond: "NO_OBJECTIONS_DETECTED"
"""

    # Initialize client
    client = OpenAI(base_url=base_url, api_key=api_key)

    try:
        print(f"[INFO] Calling {provider.upper()} API ({model})...")
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.7,
        )

        analysis = response.choices[0].message.content

        print(f"\n{'='*60}")
        print("ANALYSIS RESULTS")
        print(f"{'='*60}\n")
        print(analysis)
        print(f"\n{'='*60}")
        print(f"Model: {model}")
        print(f"Provider: {provider}")
        print(f"Tokens: {response.usage.total_tokens}")
        print(f"{'='*60}\n")

        return analysis

    except Exception as e:
        print(f"[ERROR] API call failed: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Test diarization with LLM analysis")
    parser.add_argument("audio_file", help="Path to audio/video file")
    parser.add_argument("--provider", choices=["github", "openrouter"],
                       default=os.getenv("LLM_PROVIDER", "github"),
                       help="LLM provider to use")
    args = parser.parse_args()

    audio_path = args.audio_file
    if not Path(audio_path).exists():
        print(f"ERROR: File not found: {audio_path}")
        sys.exit(1)

    print(f"\n{'#'*60}")
    print("SALES RPG AI - DIARIZATION TEST")
    print(f"{'#'*60}\n")

    # Step 1: Transcribe with diarization
    segments = transcribe_with_diarization(audio_path)

    if not segments:
        print("ERROR: No transcript generated")
        sys.exit(1)

    # Step 2: Analyze with LLM
    analysis = analyze_sales_objections(segments, provider=args.provider)

    if analysis:
        print("\n✅ SUCCESS! Diarization + LLM analysis working!")
    else:
        print("\n❌ Analysis failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
