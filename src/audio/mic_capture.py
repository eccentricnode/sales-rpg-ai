"""
Microphone audio capture using PyAudio.

Captures microphone input and saves to WAV file with proper async handling.
"""

import asyncio
import logging
import wave
from pathlib import Path
from typing import Optional

try:
    import pyaudio
except ImportError:
    raise ImportError(
        "PyAudio is required for microphone capture. "
        "Install it with: pip install pyaudio"
    )

logger = logging.getLogger(__name__)


class MicrophoneCapture:
    """Capture microphone input using PyAudio."""

    # Audio settings matching WhisperLive requirements
    CHUNK = 4096
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000

    def __init__(
        self,
        device_index: Optional[int] = None,
        chunk_size: int = CHUNK,
        sample_rate: int = RATE,
    ):
        """
        Initialize microphone capture.

        Args:
            device_index: PyAudio device index. None uses default input device.
            chunk_size: Number of frames per buffer
            sample_rate: Sample rate in Hz (16000 for WhisperLive)
        """
        self.device_index = device_index
        self.chunk_size = chunk_size
        self.sample_rate = sample_rate

        self.pyaudio_instance: Optional[pyaudio.PyAudio] = None
        self.stream: Optional[pyaudio.Stream] = None
        self.wav_file: Optional[wave.Wave_write] = None
        self.output_path: Optional[Path] = None

        self.is_recording = False
        self._record_task: Optional[asyncio.Task] = None

    def get_default_device_info(self) -> dict:
        """Get information about the default input device."""
        if not self.pyaudio_instance:
            self.pyaudio_instance = pyaudio.PyAudio()

        try:
            return self.pyaudio_instance.get_default_input_device_info()
        except Exception as e:
            logger.error(f"Failed to get default input device: {e}")
            raise

    def list_devices(self) -> list[dict]:
        """List all available audio input devices."""
        if not self.pyaudio_instance:
            self.pyaudio_instance = pyaudio.PyAudio()

        devices = []
        for i in range(self.pyaudio_instance.get_device_count()):
            info = self.pyaudio_instance.get_device_info_by_index(i)
            if info.get("maxInputChannels", 0) > 0:
                devices.append(
                    {
                        "index": i,
                        "name": info["name"],
                        "channels": info["maxInputChannels"],
                        "sample_rate": int(info["defaultSampleRate"]),
                    }
                )
        return devices

    async def start(self, output_path: Path) -> None:
        """
        Start recording microphone to WAV file.

        Args:
            output_path: Path where the WAV file will be saved
        """
        if self.is_recording:
            raise RuntimeError("Already recording")

        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize PyAudio
        if not self.pyaudio_instance:
            self.pyaudio_instance = pyaudio.PyAudio()

        # Log device info
        if self.device_index is None:
            device_info = self.get_default_device_info()
            logger.info(
                f"Using default input device: [{device_info['index']}] "
                f"{device_info['name']}"
            )
        else:
            device_info = self.pyaudio_instance.get_device_info_by_index(
                self.device_index
            )
            logger.info(
                f"Using input device: [{self.device_index}] {device_info['name']}"
            )

        # Open WAV file
        self.wav_file = wave.open(str(self.output_path), "wb")
        self.wav_file.setnchannels(self.CHANNELS)
        self.wav_file.setsampwidth(
            self.pyaudio_instance.get_sample_size(self.FORMAT)
        )
        self.wav_file.setframerate(self.sample_rate)

        # Open audio stream
        try:
            self.stream = self.pyaudio_instance.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.sample_rate,
                input=True,
                input_device_index=self.device_index,
                frames_per_buffer=self.chunk_size,
            )
        except Exception as e:
            self.wav_file.close()
            raise RuntimeError(f"Failed to open audio stream: {e}")

        self.is_recording = True
        self._record_task = asyncio.create_task(self._record_loop())
        logger.info(f"Started microphone recording to {self.output_path}")

    async def _record_loop(self) -> None:
        """Main recording loop that runs in the background."""
        try:
            while self.is_recording:
                # Read audio data in executor to avoid blocking
                data = await asyncio.get_event_loop().run_in_executor(
                    None, self.stream.read, self.chunk_size, False
                )

                # Write to WAV file
                if self.wav_file:
                    self.wav_file.writeframes(data)

                # Small sleep to yield control
                await asyncio.sleep(0.001)

        except Exception as e:
            logger.error(f"Error in recording loop: {e}")
            self.is_recording = False

    async def stop(self) -> Path:
        """
        Stop recording and finalize the WAV file.

        Returns:
            Path to the completed WAV file
        """
        if not self.is_recording:
            logger.warning("Not currently recording")
            return self.output_path

        self.is_recording = False

        # Wait for record task to complete
        if self._record_task:
            try:
                await asyncio.wait_for(self._record_task, timeout=2.0)
            except asyncio.TimeoutError:
                logger.warning("Record task did not complete in time, cancelling")
                self._record_task.cancel()

        # Clean up audio stream
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None

        # Close WAV file
        if self.wav_file:
            self.wav_file.close()
            self.wav_file = None

        logger.info(f"Stopped microphone recording, saved to {self.output_path}")
        return self.output_path

    def cleanup(self) -> None:
        """Clean up PyAudio resources."""
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception:
                pass
            self.stream = None

        if self.wav_file:
            try:
                self.wav_file.close()
            except Exception:
                pass
            self.wav_file = None

        if self.pyaudio_instance:
            try:
                self.pyaudio_instance.terminate()
            except Exception:
                pass
            self.pyaudio_instance = None

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.is_recording:
            await self.stop()
        self.cleanup()
