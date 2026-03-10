"""VadTranscriber: Silero VAD + batch faster-whisper transcription.

Processes audio as a stream of Int16 PCM chunks. Silero VAD detects
speech boundaries, then complete utterances are batch-transcribed
by faster-whisper.

This is a self-contained copy for the eval repo. When the class
stabilizes, it will be imported from the sales-rpg-ai package.
"""

import logging
import queue
import threading
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

# Silero VAD expects 16kHz audio in specific window sizes
_SILERO_VALID_SAMPLES = {256, 512, 1024, 1536}


class VadTranscriber:
    """Turn-based speech-to-text using VAD + batch Whisper.

    Usage:
        transcriber = VadTranscriber(model="base", device="cpu")
        for chunk in audio_stream:
            segments = transcriber.feed(chunk)
            for seg in segments:
                print(seg["text"])
        final = transcriber.flush()
    """

    SAMPLE_RATE = 16000
    VAD_CHUNK_SIZE = 512  # 32ms at 16kHz — valid Silero window

    def __init__(
        self,
        model: str = "base",
        device: str = "cpu",
        language: str = "en",
        silence_threshold_ms: int = 400,
        max_utterance_seconds: float = 30.0,
        vad_threshold: float = 0.5,
        beam_size: int = 1,
        condition_on_previous_text: bool = False,
    ):
        self.model_name = model
        self.device = device
        self.language = language
        self.silence_threshold_ms = silence_threshold_ms
        self.max_utterance_seconds = max_utterance_seconds
        self.vad_threshold = vad_threshold
        self.beam_size = beam_size
        self.condition_on_previous_text = condition_on_previous_text

        # Silence threshold in samples
        self._silence_threshold_samples = int(
            (silence_threshold_ms / 1000.0) * self.SAMPLE_RATE
        )
        self._max_utterance_samples = int(max_utterance_seconds * self.SAMPLE_RATE)

        # VAD state
        self._remainder = np.array([], dtype=np.float32)
        self._speech_buffer = np.array([], dtype=np.float32)
        self._is_speaking = False
        self._silence_samples = 0
        self._speech_start_sample = 0  # Global sample position of speech start
        self._total_samples_fed = 0  # Total samples processed so far

        # Transcription output queue
        self._output_segments: list[dict] = []

        # Load models
        self._load_vad()
        self._load_whisper()

        logger.info(
            f"VadTranscriber initialized: model={model}, device={device}, "
            f"silence={silence_threshold_ms}ms, max_utterance={max_utterance_seconds}s"
        )

    def _load_vad(self):
        """Load Silero VAD model."""
        import torch

        self._vad_model, _ = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
            onnx=True,
        )
        self._vad_model.reset_states()

    def _load_whisper(self):
        """Load faster-whisper model."""
        from faster_whisper import WhisperModel

        compute_type = "float16" if self.device == "cuda" else "int8"
        self._whisper = WhisperModel(
            self.model_name,
            device=self.device,
            compute_type=compute_type,
        )
        self._whisper_lock = threading.Lock()

    def feed(self, chunk_bytes: bytes) -> list[dict]:
        """Feed Int16 PCM bytes. Returns list of completed segments.

        Each segment dict:
            {"text": str, "start": float, "end": float, "completed": True}

        Returns empty list most of the time. Returns 1 segment when
        silence exceeds threshold after speech, or when max utterance
        length is hit.
        """
        self._output_segments = []

        # Convert Int16 bytes to float32 [-1.0, 1.0]
        int16_audio = np.frombuffer(chunk_bytes, dtype=np.int16)
        float_audio = int16_audio.astype(np.float32) / 32768.0

        # Prepend remainder from previous chunk
        if len(self._remainder) > 0:
            float_audio = np.concatenate([self._remainder, float_audio])
            self._remainder = np.array([], dtype=np.float32)

        # Process in VAD_CHUNK_SIZE windows
        i = 0
        while i + self.VAD_CHUNK_SIZE <= len(float_audio):
            window = float_audio[i : i + self.VAD_CHUNK_SIZE]
            self._process_vad_window(window)
            i += self.VAD_CHUNK_SIZE

        # Save leftover samples for next call
        if i < len(float_audio):
            self._remainder = float_audio[i:]

        self._total_samples_fed += len(int16_audio)

        return self._output_segments

    def _process_vad_window(self, window: np.ndarray):
        """Process a single VAD window (512 samples)."""
        import torch

        tensor = torch.from_numpy(window)
        speech_prob = self._vad_model(tensor, self.SAMPLE_RATE).item()

        if speech_prob >= self.vad_threshold:
            # Speech detected
            if not self._is_speaking:
                self._is_speaking = True
                self._speech_start_sample = self._total_samples_fed
                self._speech_buffer = np.array([], dtype=np.float32)
                self._silence_samples = 0

            self._speech_buffer = np.concatenate([self._speech_buffer, window])
            self._silence_samples = 0

            # Check max utterance length
            if len(self._speech_buffer) >= self._max_utterance_samples:
                self._finalize_utterance()
        else:
            # Silence detected
            if self._is_speaking:
                # Still accumulate silence into buffer (may be mid-word pause)
                self._speech_buffer = np.concatenate([self._speech_buffer, window])
                self._silence_samples += self.VAD_CHUNK_SIZE

                if self._silence_samples >= self._silence_threshold_samples:
                    self._finalize_utterance()
            # If not speaking and silence, do nothing

    def _finalize_utterance(self):
        """Transcribe completed utterance and emit segment."""
        min_utterance_samples = int(0.16 * self.SAMPLE_RATE)  # 160ms minimum
        speech_only = self._speech_buffer

        # Trim trailing silence from buffer
        if self._silence_samples > 0:
            trim_samples = min(self._silence_samples, len(speech_only))
            speech_only = speech_only[:-trim_samples] if trim_samples > 0 else speech_only

        if len(speech_only) < min_utterance_samples:
            # Too short — noise or click, skip
            self._is_speaking = False
            self._speech_buffer = np.array([], dtype=np.float32)
            self._silence_samples = 0
            return

        # Compute timestamps
        start_seconds = self._speech_start_sample / self.SAMPLE_RATE
        end_seconds = start_seconds + len(speech_only) / self.SAMPLE_RATE

        # Transcribe with faster-whisper
        text = self._transcribe_audio(speech_only)

        if text.strip():
            self._output_segments.append({
                "text": text.strip(),
                "start": round(start_seconds, 3),
                "end": round(end_seconds, 3),
                "completed": True,
            })

        # Reset state
        self._is_speaking = False
        self._speech_buffer = np.array([], dtype=np.float32)
        self._silence_samples = 0

    def _transcribe_audio(self, audio: np.ndarray) -> str:
        """Batch-transcribe audio array using faster-whisper."""
        with self._whisper_lock:
            segments, _ = self._whisper.transcribe(
                audio,
                language=self.language,
                beam_size=self.beam_size,
                condition_on_previous_text=self.condition_on_previous_text,
                no_speech_threshold=0.6,
                log_prob_threshold=-1.0,
                suppress_blank=True,
            )
            return " ".join(seg.text for seg in segments)

    def flush(self) -> list[dict]:
        """Emit any remaining buffered audio as a final segment.

        Called when the audio stream ends. Returns 0-1 segments.

        Fixes mic cutoff bug (S5-02): remainder samples are now processed
        through VAD regardless of speaking state, ensuring no partial audio
        is silently dropped at chunk boundaries.
        """
        self._output_segments = []

        # Process any remaining samples through VAD, regardless of speaking
        # state. This fixes the mic cutoff bug where remainder samples were
        # discarded if _is_speaking was False at stream end.
        if len(self._remainder) > 0:
            # Pad remainder to VAD_CHUNK_SIZE with zeros so VAD can process it
            padded = np.zeros(self.VAD_CHUNK_SIZE, dtype=np.float32)
            padded[: len(self._remainder)] = self._remainder
            self._process_vad_window(padded)
            self._remainder = np.array([], dtype=np.float32)

        # If still speaking after processing remainder, append any leftover
        # remainder to speech buffer and finalize
        if self._is_speaking and len(self._speech_buffer) > 0:
            self._finalize_utterance()

        return self._output_segments
