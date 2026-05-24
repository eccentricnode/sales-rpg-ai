"""
System audio capture using PulseAudio/PipeWire.

Captures system audio output (e.g., from Zoom/Discord) via monitor sources.
"""

import asyncio
import logging
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class SystemAudioCapture:
    """Capture system audio output using PulseAudio monitor sources."""

    # Audio settings matching WhisperLive requirements
    RATE = 16000
    CHANNELS = 1

    def __init__(
        self,
        device_name: Optional[str] = None,
        sample_rate: int = RATE,
        channels: int = CHANNELS,
    ):
        """
        Initialize system audio capture.

        Args:
            device_name: PulseAudio monitor device name. None auto-detects.
            sample_rate: Sample rate in Hz (16000 for WhisperLive)
            channels: Number of audio channels (1 for mono)
        """
        self.device_name = device_name
        self.sample_rate = sample_rate
        self.channels = channels

        self.process: Optional[asyncio.subprocess.Process] = None
        self.output_path: Optional[Path] = None
        self.is_recording = False

    @staticmethod
    def list_monitor_sources() -> list[dict]:
        """
        List all available monitor sources (system audio outputs).

        Returns:
            List of monitor source information dicts
        """
        try:
            result = subprocess.run(
                ["pactl", "list", "sources", "short"],
                capture_output=True,
                text=True,
                check=True,
            )

            monitors = []
            for line in result.stdout.strip().split("\n"):
                if ".monitor" in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        monitors.append(
                            {
                                "index": parts[0],
                                "name": parts[1],
                                "driver": parts[2] if len(parts) > 2 else "unknown",
                            }
                        )

            return monitors

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to list monitor sources: {e}")
            return []
        except FileNotFoundError:
            logger.error("pactl command not found. Is PulseAudio/PipeWire installed?")
            return []

    @staticmethod
    def get_default_monitor() -> Optional[str]:
        """
        Get the default system audio monitor source.

        Returns:
            Monitor source name, or None if not found
        """
        monitors = SystemAudioCapture.list_monitor_sources()
        if not monitors:
            logger.warning("No monitor sources found")
            return None

        # Prefer non-HDMI monitors (usually the main system audio)
        for monitor in monitors:
            if "hdmi" not in monitor["name"].lower():
                logger.info(f"Selected monitor: {monitor['name']}")
                return monitor["name"]

        # Fall back to first monitor
        logger.info(f"Using first available monitor: {monitors[0]['name']}")
        return monitors[0]["name"]

    async def start(self, output_path: Path) -> None:
        """
        Start recording system audio to WAV file.

        Args:
            output_path: Path where the WAV file will be saved
        """
        if self.is_recording:
            raise RuntimeError("Already recording")

        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        # Auto-detect monitor if not specified
        if not self.device_name:
            self.device_name = self.get_default_monitor()
            if not self.device_name:
                raise RuntimeError(
                    "No monitor sources found. "
                    "Cannot capture system audio without a monitor source."
                )

        # Build pactl command
        cmd = [
            "pactl",
            "record",
            f"--device={self.device_name}",
            "--file-format=wav",
            f"--rate={self.sample_rate}",
            f"--channels={self.channels}",
            str(self.output_path),
        ]

        logger.info(f"Starting system audio capture from {self.device_name}")
        logger.debug(f"Command: {' '.join(cmd)}")

        # Start pactl process
        try:
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to start pactl: {e}")

        self.is_recording = True
        logger.info(f"Started system audio recording to {self.output_path}")

        # Monitor process in background
        asyncio.create_task(self._monitor_process())

    async def _monitor_process(self) -> None:
        """Monitor the pactl process for errors."""
        if not self.process:
            return

        try:
            # Wait for process to exit (it shouldn't until we stop it)
            returncode = await self.process.wait()

            if returncode != 0 and self.is_recording:
                stderr = await self.process.stderr.read()
                logger.error(
                    f"pactl process exited with code {returncode}: "
                    f"{stderr.decode()}"
                )
                self.is_recording = False

        except Exception as e:
            logger.error(f"Error monitoring pactl process: {e}")
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

        # Terminate pactl process
        if self.process:
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                logger.warning("pactl did not terminate in time, killing")
                self.process.kill()
                await self.process.wait()
            except Exception as e:
                logger.error(f"Error stopping pactl: {e}")

            self.process = None

        logger.info(f"Stopped system audio recording, saved to {self.output_path}")
        return self.output_path

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.is_recording:
            await self.stop()


async def test_system_capture():
    """Test system audio capture."""
    output_path = Path("/tmp/test_system_audio.wav")

    print("Available monitor sources:")
    for monitor in SystemAudioCapture.list_monitor_sources():
        print(f"  - {monitor['name']}")

    print(f"\nRecording system audio for 5 seconds to {output_path}")

    async with SystemAudioCapture() as capture:
        await capture.start(output_path)
        await asyncio.sleep(5)
        result_path = await capture.stop()

    print(f"Recording complete: {result_path}")
    print(f"File size: {result_path.stat().st_size} bytes")


if __name__ == "__main__":
    asyncio.run(test_system_capture())
