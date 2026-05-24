"""Audio capture modules for dual-stream transcription.

Imports are lazy to avoid requiring PyAudio in environments where
only browser-based audio capture is used (e.g., Docker containers).
"""


def __getattr__(name):
    if name == "MicrophoneCapture":
        from .mic_capture import MicrophoneCapture
        return MicrophoneCapture
    elif name == "SystemAudioCapture":
        from .system_capture import SystemAudioCapture
        return SystemAudioCapture
    elif name == "DualCaptureManager":
        from .dual_capture import DualCaptureManager
        return DualCaptureManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["MicrophoneCapture", "SystemAudioCapture", "DualCaptureManager"]
