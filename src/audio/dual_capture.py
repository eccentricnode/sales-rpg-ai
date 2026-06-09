"""
Dual audio capture coordinator.

Manages simultaneous microphone and system audio capture.
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional, Tuple

from .mic_capture import MicrophoneCapture
from .system_capture import SystemAudioCapture

logger = logging.getLogger(__name__)


class DualCaptureManager:
    """Coordinate parallel microphone and system audio capture."""

    def __init__(
        self,
        output_dir: Path,
        mic_device: Optional[int] = None,
        system_device: Optional[str] = None,
    ):
        """
        Initialize dual capture manager.

        Args:
            output_dir: Directory where audio files will be saved
            mic_device: PyAudio device index for microphone (None = default)
            system_device: PulseAudio monitor name (None = auto-detect)
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.mic_capture = MicrophoneCapture(device_index=mic_device)
        self.system_capture = SystemAudioCapture(device_name=system_device)

        self.mic_path: Optional[Path] = None
        self.system_path: Optional[Path] = None

        self.is_capturing = False

    def get_output_paths(self, session_id: str = "session") -> Tuple[Path, Path]:
        """
        Generate output paths for mic and system audio files.

        Args:
            session_id: Identifier for this capture session

        Returns:
            Tuple of (mic_path, system_path)
        """
        mic_path = self.output_dir / f"{session_id}_mic.wav"
        system_path = self.output_dir / f"{session_id}_system.wav"
        return mic_path, system_path

    async def start(self, session_id: str = "session") -> Tuple[Path, Path]:
        """
        Start both microphone and system audio capture.

        Args:
            session_id: Identifier for this capture session

        Returns:
            Tuple of (mic_path, system_path) where audio is being saved
        """
        if self.is_capturing:
            raise RuntimeError("Already capturing")

        self.mic_path, self.system_path = self.get_output_paths(session_id)

        logger.info(f"Starting dual capture session: {session_id}")
        logger.info(f"  Microphone → {self.mic_path}")
        logger.info(f"  System Audio → {self.system_path}")

        # Start both captures in parallel
        try:
            await asyncio.gather(
                self.mic_capture.start(self.mic_path),
                self.system_capture.start(self.system_path),
            )
        except Exception as e:
            # If one fails, stop the other
            logger.error(f"Failed to start dual capture: {e}")
            await self._cleanup_on_error()
            raise

        self.is_capturing = True
        logger.info("Dual capture started successfully")

        return self.mic_path, self.system_path

    async def stop(self) -> Tuple[Path, Path]:
        """
        Stop both captures and finalize audio files.

        Returns:
            Tuple of (mic_path, system_path) with completed audio files
        """
        if not self.is_capturing:
            logger.warning("Not currently capturing")
            return self.mic_path, self.system_path

        logger.info("Stopping dual capture")

        # Stop both captures in parallel
        mic_path, system_path = await asyncio.gather(
            self.mic_capture.stop(),
            self.system_capture.stop(),
        )

        self.is_capturing = False
        logger.info("Dual capture stopped successfully")

        return mic_path, system_path

    async def _cleanup_on_error(self):
        """Clean up if startup fails."""
        try:
            if self.mic_capture.is_recording:
                await self.mic_capture.stop()
        except Exception:
            pass

        try:
            if self.system_capture.is_recording:
                await self.system_capture.stop()
        except Exception:
            pass

    def cleanup(self):
        """Clean up resources."""
        self.mic_capture.cleanup()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.is_capturing:
            await self.stop()
        self.cleanup()


async def test_dual_capture():
    """Test dual audio capture."""
    output_dir = Path("/tmp/dual_capture_test")

    print("=== Dual Audio Capture Test ===\n")

    # List available devices
    print("Available microphone devices:")
    mic = MicrophoneCapture()
    for device in mic.list_devices():
        print(f"  [{device['index']}] {device['name']}")
    mic.cleanup()

    print("\nAvailable system audio monitors:")
    for monitor in SystemAudioCapture.list_monitor_sources():
        print(f"  - {monitor['name']}")

    print(f"\nRecording both streams for 10 seconds to {output_dir}\n")

    async with DualCaptureManager(output_dir) as manager:
        mic_path, system_path = await manager.start("test_session")

        print(f"Microphone: {mic_path}")
        print(f"System Audio: {system_path}")
        print("\nSpeak into your microphone and play some system audio...")

        # Record for 10 seconds
        for i in range(10, 0, -1):
            print(f"\r{i} seconds remaining...", end="", flush=True)
            await asyncio.sleep(1)

        print("\n\nStopping capture...")
        mic_path, system_path = await manager.stop()

    print("\n=== Capture Complete ===")
    print(f"Microphone: {mic_path} ({mic_path.stat().st_size} bytes)")
    print(f"System Audio: {system_path} ({system_path.stat().st_size} bytes)")


if __name__ == "__main__":
    asyncio.run(test_dual_capture())
