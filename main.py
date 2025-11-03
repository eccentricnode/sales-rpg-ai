# test_transcription.py
import whisper
import time
import json
from datetime import datetime

def transcribe_with_timing(audio_file, model_name="base"):
    """
    Transcribe audio file with timing measurement and save results.

    Args:
        audio_file: Path to audio/video file
        model_name: Whisper model to use (tiny, base, small, medium, large)

    Returns:
        dict: Transcription results with metadata
    """
    # Load model
    print(f"Loading Whisper model '{model_name}'...")
    model_load_start = time.time()
    model = whisper.load_model(model_name)
    model_load_time = time.time() - model_load_start
    print(f"Model loaded in {model_load_time:.2f}s")

    # Transcribe with timing
    print(f"Transcribing '{audio_file}'...")
    transcription_start = time.time()
    result = model.transcribe(audio_file)
    transcription_end = time.time()

    # Calculate metrics
    processing_time = transcription_end - transcription_start
    audio_duration = result.get("segments", [{}])[-1].get("end", 0) if result.get("segments") else 0

    # If audio duration is available, calculate ratio
    if audio_duration > 0:
        processing_ratio = processing_time / audio_duration
        realtime_status = "FASTER" if processing_ratio < 1.0 else "SLOWER"
        ratio_text = f"{processing_ratio:.2f}x ({realtime_status} than real-time)"
    else:
        processing_ratio = None
        ratio_text = "N/A (duration unknown)"

    # Prepare metadata
    timestamp = datetime.now()
    metadata = {
        "timestamp": timestamp.isoformat(),
        "audio_file": audio_file,
        "model": model_name,
        "audio_duration_seconds": round(audio_duration, 2),
        "processing_time_seconds": round(processing_time, 2),
        "model_load_time_seconds": round(model_load_time, 2),
        "processing_ratio": round(processing_ratio, 4) if processing_ratio else None,
        "realtime_status": realtime_status if processing_ratio else None
    }

    # Print results to console
    print("\n" + "="*60)
    print("TRANSCRIPTION COMPLETE")
    print("="*60)
    print(f"Audio file: {audio_file}")
    print(f"Model: {model_name}")
    print(f"Audio duration: {audio_duration:.2f}s ({audio_duration/60:.2f} minutes)")
    print(f"Processing time: {processing_time:.2f}s ({processing_time/60:.2f} minutes)")
    print(f"Processing ratio: {ratio_text}")
    print("="*60)

    print("\n=== TRANSCRIPT ===")
    print(result["text"])

    print("\n=== SEGMENTS ===")
    for segment in result["segments"]:
        print(f"[{segment['start']:.2f}s -> {segment['end']:.2f}s] {segment['text']}")

    # Save results
    save_results(metadata, result, processing_time, timestamp)

    return {
        "metadata": metadata,
        "result": result
    }

def save_results(metadata, result, processing_time, timestamp):
    """Save transcription results to text and JSON files."""

    # Generate filename components
    timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")
    processing_time_str = f"{int(processing_time)}s"
    base_filename = f"test-transcript-{timestamp_str}-{processing_time_str}"

    txt_filename = f"{base_filename}.txt"
    json_filename = f"{base_filename}.json"

    # Save text file
    with open(txt_filename, "w", encoding="utf-8") as f:
        # Write header
        f.write("="*70 + "\n")
        f.write("WHISPER TRANSCRIPTION RESULTS\n")
        f.write("="*70 + "\n\n")

        # Write metadata
        f.write("METADATA:\n")
        f.write(f"  Timestamp: {metadata['timestamp']}\n")
        f.write(f"  Audio File: {metadata['audio_file']}\n")
        f.write(f"  Model: {metadata['model']}\n")
        f.write(f"  Audio Duration: {metadata['audio_duration_seconds']}s ({metadata['audio_duration_seconds']/60:.2f} minutes)\n")
        f.write(f"  Processing Time: {metadata['processing_time_seconds']}s ({metadata['processing_time_seconds']/60:.2f} minutes)\n")
        f.write(f"  Model Load Time: {metadata['model_load_time_seconds']}s\n")

        if metadata['processing_ratio']:
            f.write(f"  Processing Ratio: {metadata['processing_ratio']:.4f}x ({metadata['realtime_status']} than real-time)\n")

        f.write("\n" + "="*70 + "\n\n")

        # Write full transcript
        f.write("FULL TRANSCRIPT:\n")
        f.write("-"*70 + "\n")
        f.write(result["text"] + "\n")
        f.write("-"*70 + "\n\n")

        # Write segmented transcript
        f.write("SEGMENTED TRANSCRIPT WITH TIMESTAMPS:\n")
        f.write("-"*70 + "\n")
        for segment in result["segments"]:
            start = segment['start']
            end = segment['end']
            text = segment['text']
            f.write(f"[{start:7.2f}s -> {end:7.2f}s] {text}\n")
        f.write("-"*70 + "\n")

    # Save JSON file
    json_data = {
        "metadata": metadata,
        "transcript": result["text"],
        "segments": [
            {
                "start": seg["start"],
                "end": seg["end"],
                "text": seg["text"]
            }
            for seg in result["segments"]
        ],
        "language": result.get("language", "unknown")
    }

    with open(json_filename, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Results saved:")
    print(f"  - Text file: {txt_filename}")
    print(f"  - JSON file: {json_filename}")

if __name__ == "__main__":
    # Configuration
    AUDIO_FILE = "test.mp4"
    MODEL_NAME = "base"  # Options: tiny, base, small, medium, large

    # Run transcription with timing
    transcribe_with_timing(AUDIO_FILE, MODEL_NAME)