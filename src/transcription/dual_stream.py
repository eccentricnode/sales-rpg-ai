"""
Dual stream transcription with speaker labeling.

Transcribes microphone and system audio separately, labels speakers,
and merges results by timestamp.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Callable
import websockets

logger = logging.getLogger(__name__)


@dataclass
class TranscriptSegment:
    """A single transcript segment with speaker label."""

    speaker: str  # "SALES_REP" or "CUSTOMER"
    text: str
    start: float
    end: float
    is_final: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class MergedTranscript:
    """Complete merged transcript with speaker labels."""

    segments: List[TranscriptSegment]

    def to_text(self) -> str:
        """Convert to readable text format."""
        lines = []
        for seg in self.segments:
            lines.append(f"[{seg.speaker}] {seg.text}")
        return "\n".join(lines)

    def to_json(self) -> str:
        """Convert to JSON format."""
        return json.dumps([seg.to_dict() for seg in self.segments], indent=2)

    def to_srt(self) -> str:
        """Convert to SRT subtitle format."""
        lines = []
        for i, seg in enumerate(self.segments, 1):
            start_time = self._format_timestamp(seg.start)
            end_time = self._format_timestamp(seg.end)
            lines.append(f"{i}")
            lines.append(f"{start_time} --> {end_time}")
            lines.append(f"[{seg.speaker}] {seg.text}")
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        """Format timestamp for SRT format (HH:MM:SS,mmm)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


class DualStreamTranscriber:
    """Transcribe microphone and system audio with speaker labels."""

    def __init__(
        self,
        whisper_host: str = "localhost",
        whisper_port: int = 9090,
        language: str = "en",
        model: str = "base",
        use_vad: bool = False,
        on_segment: Optional[Callable[[TranscriptSegment], None]] = None,
    ):
        """
        Initialize dual stream transcriber.

        Args:
            whisper_host: WhisperLive server hostname
            whisper_port: WhisperLive server port
            language: Language code for transcription
            model: Whisper model to use
            use_vad: Enable voice activity detection
            on_segment: Callback for each transcribed segment
        """
        self.whisper_host = whisper_host
        self.whisper_port = whisper_port
        self.language = language
        self.model = model
        self.use_vad = use_vad
        self.on_segment = on_segment

        self.mic_segments: List[TranscriptSegment] = []
        self.system_segments: List[TranscriptSegment] = []

        self.is_transcribing = False

    async def transcribe_streams(
        self, mic_audio_path: Path, system_audio_path: Path
    ) -> MergedTranscript:
        """
        Transcribe both audio streams and merge results.

        Args:
            mic_audio_path: Path to microphone audio WAV file
            system_audio_path: Path to system audio WAV file

        Returns:
            Merged transcript with speaker labels
        """
        logger.info("Starting dual stream transcription")
        logger.info(f"  Mic: {mic_audio_path}")
        logger.info(f"  System: {system_audio_path}")

        self.mic_segments = []
        self.system_segments = []
        self.is_transcribing = True

        try:
            # Transcribe both streams in parallel
            await asyncio.gather(
                self._transcribe_file(mic_audio_path, "SALES_REP", self.mic_segments),
                self._transcribe_file(
                    system_audio_path, "CUSTOMER", self.system_segments
                ),
            )

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            raise
        finally:
            self.is_transcribing = False

        # Merge segments by timestamp
        merged = self._merge_segments()

        logger.info(
            f"Transcription complete: {len(merged.segments)} total segments "
            f"({len(self.mic_segments)} mic, {len(self.system_segments)} system)"
        )

        return merged

    async def transcribe_streams_realtime(
        self,
        mic_websocket,
        system_websocket,
        on_mic_segment: Optional[Callable[[dict], None]] = None,
        on_system_segment: Optional[Callable[[dict], None]] = None,
    ):
        """
        Transcribe live audio streams from WebSocket connections.

        This is for real-time transcription where audio is streamed continuously.

        Args:
            mic_websocket: WebSocket sending microphone audio
            system_websocket: WebSocket sending system audio
            on_mic_segment: Callback for microphone segments
            on_system_segment: Callback for system segments
        """
        self.is_transcribing = True

        try:
            await asyncio.gather(
                self._handle_realtime_stream(
                    mic_websocket, "SALES_REP", on_mic_segment
                ),
                self._handle_realtime_stream(
                    system_websocket, "CUSTOMER", on_system_segment
                ),
            )
        finally:
            self.is_transcribing = False

    async def _transcribe_file(
        self, audio_path: Path, speaker: str, segments_list: List[TranscriptSegment]
    ):
        """
        Transcribe a single audio file via WhisperLive.

        Args:
            audio_path: Path to audio file
            speaker: Speaker label for all segments
            segments_list: List to append segments to
        """
        if not audio_path.exists():
            logger.error(f"Audio file not found: {audio_path}")
            return

        whisper_url = f"ws://{self.whisper_host}:{self.whisper_port}"

        try:
            async with websockets.connect(whisper_url) as ws:
                # Send configuration
                config = {
                    "uid": f"dual-stream-{speaker}",
                    "language": self.language,
                    "task": "transcribe",
                    "model": self.model,
                    "use_vad": self.use_vad,
                }
                await ws.send(json.dumps(config))

                # Create tasks for sending and receiving
                send_task = asyncio.create_task(self._send_audio_file(ws, audio_path))
                recv_task = asyncio.create_task(
                    self._receive_segments(ws, speaker, segments_list)
                )

                # Wait for both to complete
                await asyncio.gather(send_task, recv_task)

        except Exception as e:
            logger.error(f"Error transcribing {speaker} stream: {e}")
            raise

    async def _send_audio_file(self, ws, audio_path: Path):
        """Send audio file to WhisperLive server."""
        import wave

        try:
            with wave.open(str(audio_path), "rb") as wf:
                chunk_size = 8192
                while True:
                    frames = wf.readframes(chunk_size)
                    if not frames:
                        break
                    await ws.send(frames)
                    await asyncio.sleep(0.01)  # Rate limit

            # Signal end of audio
            await ws.send(json.dumps({"type": "END_OF_AUDIO"}))

        except Exception as e:
            logger.error(f"Error sending audio: {e}")

    async def _receive_segments(
        self, ws, speaker: str, segments_list: List[TranscriptSegment]
    ):
        """Receive transcript segments from WhisperLive."""
        try:
            while True:
                msg = await ws.recv()
                data = json.loads(msg)

                if "segments" in data:
                    for seg in data["segments"]:
                        text = seg.get("text", "").strip()
                        if text:
                            segment = TranscriptSegment(
                                speaker=speaker,
                                text=text,
                                start=seg.get("start", 0),
                                end=seg.get("end", 0),
                                is_final=seg.get("is_last", False),
                            )
                            segments_list.append(segment)

                            # Call callback if provided
                            if self.on_segment:
                                self.on_segment(segment)

                            logger.debug(f"[{speaker}] {text}")

        except websockets.exceptions.ConnectionClosed:
            logger.debug(f"{speaker} stream connection closed")
        except Exception as e:
            logger.error(f"Error receiving segments for {speaker}: {e}")

    async def _handle_realtime_stream(
        self, audio_websocket, speaker: str, on_segment: Optional[Callable]
    ):
        """Handle real-time audio stream transcription."""
        whisper_url = f"ws://{self.whisper_host}:{self.whisper_port}"

        try:
            async with websockets.connect(whisper_url) as whisper_ws:
                # Send configuration
                config = {
                    "uid": f"realtime-{speaker}",
                    "language": self.language,
                    "task": "transcribe",
                    "model": self.model,
                    "use_vad": self.use_vad,
                }
                await whisper_ws.send(json.dumps(config))

                # Create forwarding and receiving tasks
                forward_task = asyncio.create_task(
                    self._forward_audio(audio_websocket, whisper_ws)
                )
                recv_task = asyncio.create_task(
                    self._receive_realtime(whisper_ws, speaker, on_segment)
                )

                await asyncio.gather(forward_task, recv_task)

        except Exception as e:
            logger.error(f"Error in realtime stream for {speaker}: {e}")

    async def _forward_audio(self, source_ws, dest_ws):
        """Forward audio from source WebSocket to WhisperLive."""
        try:
            while True:
                msg = await source_ws.recv()
                if isinstance(msg, bytes):
                    await dest_ws.send(msg)
        except websockets.exceptions.ConnectionClosed:
            pass

    async def _receive_realtime(
        self, ws, speaker: str, on_segment: Optional[Callable]
    ):
        """Receive real-time transcript segments."""
        try:
            while True:
                msg = await ws.recv()
                data = json.loads(msg)

                if "segments" in data:
                    for seg in data["segments"]:
                        text = seg.get("text", "").strip()
                        if text and on_segment:
                            segment_data = {
                                "speaker": speaker,
                                "text": text,
                                "start": seg.get("start", 0),
                                "end": seg.get("end", 0),
                                "is_final": seg.get("is_last", False),
                            }
                            on_segment(segment_data)

        except websockets.exceptions.ConnectionClosed:
            pass

    def _merge_segments(self) -> MergedTranscript:
        """Merge mic and system segments by timestamp."""
        all_segments = self.mic_segments + self.system_segments
        all_segments.sort(key=lambda s: s.start)
        return MergedTranscript(segments=all_segments)

    def get_current_transcript(self) -> MergedTranscript:
        """Get current merged transcript (useful during streaming)."""
        return self._merge_segments()


async def test_dual_transcription():
    """Test dual stream transcription."""
    mic_path = Path("/tmp/dual_capture_test/test_session_mic.wav")
    system_path = Path("/tmp/dual_capture_test/test_session_system.wav")

    if not mic_path.exists() or not system_path.exists():
        print("Audio files not found. Run dual_capture test first.")
        return

    print("=== Dual Stream Transcription Test ===\n")

    def on_segment(segment: TranscriptSegment):
        """Print segments as they arrive."""
        print(f"[{segment.speaker}] {segment.text}")

    transcriber = DualStreamTranscriber(
        whisper_host="localhost",
        whisper_port=9090,
        on_segment=on_segment,
    )

    print("Transcribing both streams...\n")
    transcript = await transcriber.transcribe_streams(mic_path, system_path)

    print("\n=== Final Merged Transcript ===\n")
    print(transcript.to_text())

    print(f"\n=== Stats ===")
    print(f"Total segments: {len(transcript.segments)}")

    # Save outputs
    output_dir = Path("/tmp/dual_capture_test")
    (output_dir / "transcript.txt").write_text(transcript.to_text())
    (output_dir / "transcript.json").write_text(transcript.to_json())
    (output_dir / "transcript.srt").write_text(transcript.to_srt())

    print(f"\nSaved transcripts to {output_dir}")


if __name__ == "__main__":
    asyncio.run(test_dual_transcription())
