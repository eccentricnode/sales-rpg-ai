#!/usr/bin/env python3
"""
End-to-end tests for dual audio capture and transcription.

Tests the complete pipeline:
1. Dual audio capture (mic + system)
2. Dual stream transcription with speaker labels
3. Real-time performance validation
"""

import asyncio
import sys
import time
from pathlib import Path

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from src.audio import DualCaptureManager, MicrophoneCapture, SystemAudioCapture
except ImportError as exc:
    pytest.skip(f"Dual capture hardware dependencies are unavailable: {exc}", allow_module_level=True)

from src.transcription import DualStreamTranscriber


class DualCaptureTests:
    """Test suite for dual audio capture."""

    def __init__(self, output_dir: Path = None):
        if output_dir is None:
            output_dir = Path("/tmp/sales-rpg-ai/test_dual_capture")
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def test_list_devices(self):
        """Test 1: List available audio devices."""
        print("\n" + "=" * 70)
        print("TEST 1: List Available Audio Devices")
        print("=" * 70)

        # List microphones
        print("\nAvailable Microphone Devices:")
        mic = MicrophoneCapture()
        devices = mic.list_devices()

        if not devices:
            print("  ⚠ WARNING: No microphone devices found!")
            return False

        for device in devices:
            print(f"  [{device['index']}] {device['name']}")
            print(f"      Channels: {device['channels']}, Rate: {device['sample_rate']}Hz")

        default = mic.get_default_device_info()
        print(f"\n  Default: [{default['index']}] {default['name']}")
        mic.cleanup()

        # List system audio monitors
        print("\nAvailable System Audio Monitors:")
        monitors = SystemAudioCapture.list_monitor_sources()

        if not monitors:
            print("  ⚠ WARNING: No monitor sources found!")
            print("  System audio capture will not work.")
            return False

        for monitor in monitors:
            print(f"  [{monitor['index']}] {monitor['name']}")

        default_monitor = SystemAudioCapture.get_default_monitor()
        print(f"\n  Selected: {default_monitor}")

        print("\n✅ PASS: Device enumeration successful")
        return True

    async def test_microphone_capture(self, duration: int = 5):
        """Test 2: Capture microphone audio."""
        print("\n" + "=" * 70)
        print(f"TEST 2: Microphone Capture ({duration} seconds)")
        print("=" * 70)

        output_path = self.output_dir / "test_mic.wav"

        print(f"\nRecording to: {output_path}")
        print("🎤 SPEAK INTO YOUR MICROPHONE NOW!\n")

        try:
            async with MicrophoneCapture() as capture:
                await capture.start(output_path)

                # Countdown
                for i in range(duration, 0, -1):
                    print(f"\r  Recording... {i} seconds remaining", end="", flush=True)
                    await asyncio.sleep(1)

                result_path = await capture.stop()

            print("\n")

            # Check file
            if not result_path.exists():
                print("❌ FAIL: Audio file not created")
                return False

            file_size = result_path.stat().st_size
            print(f"✅ PASS: Captured {file_size:,} bytes")

            # Validate it's not silent
            if file_size < 10000:
                print("⚠ WARNING: File seems too small, might be silent")

            return True

        except Exception as e:
            print(f"\n❌ FAIL: {e}")
            return False

    async def test_system_audio_capture(self, duration: int = 5):
        """Test 3: Capture system audio."""
        print("\n" + "=" * 70)
        print(f"TEST 3: System Audio Capture ({duration} seconds)")
        print("=" * 70)

        output_path = self.output_dir / "test_system.wav"

        print(f"\nRecording to: {output_path}")
        print("🔊 PLAY SOME AUDIO ON YOUR SYSTEM NOW!\n")

        try:
            async with SystemAudioCapture() as capture:
                await capture.start(output_path)

                # Countdown
                for i in range(duration, 0, -1):
                    print(f"\r  Recording... {i} seconds remaining", end="", flush=True)
                    await asyncio.sleep(1)

                result_path = await capture.stop()

            print("\n")

            # Check file
            if not result_path.exists():
                print("❌ FAIL: Audio file not created")
                return False

            file_size = result_path.stat().st_size
            print(f"✅ PASS: Captured {file_size:,} bytes")

            return True

        except Exception as e:
            print(f"\n❌ FAIL: {e}")
            return False

    async def test_dual_capture(self, duration: int = 10):
        """Test 4: Simultaneous microphone and system audio capture."""
        print("\n" + "=" * 70)
        print(f"TEST 4: Dual Capture ({duration} seconds)")
        print("=" * 70)

        print(f"\nOutput directory: {self.output_dir}")
        print("🎤 SPEAK INTO MICROPHONE AND PLAY SYSTEM AUDIO!\n")

        try:
            async with DualCaptureManager(self.output_dir) as manager:
                start_time = time.time()
                mic_path, system_path = await manager.start("test_dual")

                print(f"Microphone: {mic_path}")
                print(f"System Audio: {system_path}\n")

                # Countdown
                for i in range(duration, 0, -1):
                    print(f"\r  Recording... {i} seconds remaining", end="", flush=True)
                    await asyncio.sleep(1)

                mic_path, system_path = await manager.stop()
                elapsed = time.time() - start_time

            print("\n")

            # Check both files
            mic_size = mic_path.stat().st_size
            system_size = system_path.stat().st_size

            print(f"Microphone: {mic_size:,} bytes")
            print(f"System Audio: {system_size:,} bytes")
            print(f"Duration: {elapsed:.2f}s")

            if mic_size > 0 and system_size > 0:
                print("✅ PASS: Both streams captured successfully")
                return True, mic_path, system_path
            else:
                print("❌ FAIL: One or both streams are empty")
                return False, None, None

        except Exception as e:
            print(f"\n❌ FAIL: {e}")
            import traceback

            traceback.print_exc()
            return False, None, None

    async def test_transcription(self, mic_path: Path, system_path: Path):
        """Test 5: Transcribe both audio streams with speaker labels."""
        print("\n" + "=" * 70)
        print("TEST 5: Dual Stream Transcription")
        print("=" * 70)

        if not mic_path or not system_path:
            print("⏭ SKIP: No audio files to transcribe")
            return False

        if not mic_path.exists() or not system_path.exists():
            print("⏭ SKIP: Audio files not found")
            return False

        print("\nTranscribing both streams with WhisperLive...")
        print("(This may take a while depending on audio length)\n")

        try:
            transcriber = DualStreamTranscriber(
                whisper_host="localhost",
                whisper_port=9090,
            )

            start_time = time.time()
            transcript = await transcriber.transcribe_streams(mic_path, system_path)
            elapsed = time.time() - start_time

            print(f"\n✅ Transcription complete in {elapsed:.2f}s")
            print(f"Total segments: {len(transcript.segments)}")

            if len(transcript.segments) == 0:
                print("⚠ WARNING: No transcript segments generated")
                print("   This could mean:")
                print("   - Audio was silent")
                print("   - WhisperLive server is not running")
                print("   - Connection issues")
                return False

            # Count segments by speaker
            sales_rep_count = sum(1 for s in transcript.segments if s.speaker == "SALES_REP")
            customer_count = sum(1 for s in transcript.segments if s.speaker == "CUSTOMER")

            print("\nSpeaker breakdown:")
            print(f"  SALES_REP: {sales_rep_count} segments")
            print(f"  CUSTOMER: {customer_count} segments")

            # Show first few segments
            print("\nFirst segments:")
            for i, seg in enumerate(transcript.segments[:5]):
                print(f"  [{seg.speaker}] {seg.text}")

            # Save outputs
            (self.output_dir / "transcript.txt").write_text(transcript.to_text())
            (self.output_dir / "transcript.json").write_text(transcript.to_json())
            (self.output_dir / "transcript.srt").write_text(transcript.to_srt())

            print(f"\n💾 Saved transcripts to {self.output_dir}/")

            print("✅ PASS: Transcription successful")
            return True

        except Exception as e:
            print(f"\n❌ FAIL: {e}")
            import traceback

            traceback.print_exc()
            return False

    async def test_performance(self):
        """Test 6: Real-time performance validation."""
        print("\n" + "=" * 70)
        print("TEST 6: Performance Validation")
        print("=" * 70)

        # Test capture latency
        print("\nTesting capture startup latency...")
        async with DualCaptureManager(self.output_dir) as manager:
            start_time = time.time()
            await manager.start("perf_test")
            startup_latency = time.time() - start_time

            await asyncio.sleep(1)
            await manager.stop()

        print(f"  Capture startup: {startup_latency * 1000:.1f}ms")

        if startup_latency > 1.0:
            print("  ⚠ WARNING: Startup latency > 1 second")
        else:
            print("  ✅ Good latency")

        print("\n✅ PASS: Performance test complete")
        return True

    async def run_all_tests(self):
        """Run complete test suite."""
        print("\n" + "=" * 70)
        print("DUAL AUDIO CAPTURE TEST SUITE")
        print("=" * 70)
        print(f"\nOutput directory: {self.output_dir}")

        results = {}

        # Test 1: List devices
        results["devices"] = await self.test_list_devices()

        # Test 2: Mic capture
        results["mic_capture"] = await self.test_microphone_capture(duration=5)

        # Test 3: System audio capture
        results["system_capture"] = await self.test_system_audio_capture(duration=5)

        # Test 4: Dual capture
        dual_result = await self.test_dual_capture(duration=10)
        if isinstance(dual_result, tuple):
            results["dual_capture"], mic_path, system_path = dual_result
        else:
            results["dual_capture"] = dual_result
            mic_path = system_path = None

        # Test 5: Transcription
        results["transcription"] = await self.test_transcription(mic_path, system_path)

        # Test 6: Performance
        results["performance"] = await self.test_performance()

        # Summary
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)

        passed = sum(1 for v in results.values() if v)
        total = len(results)

        for test_name, passed_test in results.items():
            status = "✅ PASS" if passed_test else "❌ FAIL"
            print(f"{status}: {test_name}")

        print(f"\nTotal: {passed}/{total} tests passed")

        if passed == total:
            print("\n🎉 ALL TESTS PASSED!")
            return 0
        else:
            print(f"\n⚠ {total - passed} test(s) failed")
            return 1


async def main():
    """Main test runner."""
    import argparse

    parser = argparse.ArgumentParser(description="Test dual audio capture")
    parser.add_argument(
        "--test",
        choices=["devices", "mic", "system", "dual", "transcribe", "perf", "all"],
        default="all",
        help="Which test to run (default: all)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=10,
        help="Recording duration in seconds (default: 10)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/tmp/sales-rpg-ai/test_dual_capture"),
        help="Output directory for test files",
    )

    args = parser.parse_args()

    tests = DualCaptureTests(output_dir=args.output_dir)

    if args.test == "all":
        return await tests.run_all_tests()
    elif args.test == "devices":
        await tests.test_list_devices()
    elif args.test == "mic":
        await tests.test_microphone_capture(args.duration)
    elif args.test == "system":
        await tests.test_system_audio_capture(args.duration)
    elif args.test == "dual":
        await tests.test_dual_capture(args.duration)
    elif args.test == "transcribe":
        # Use existing files
        mic_path = args.output_dir / "test_dual_mic.wav"
        system_path = args.output_dir / "test_dual_system.wav"
        await tests.test_transcription(mic_path, system_path)
    elif args.test == "perf":
        await tests.test_performance()

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
