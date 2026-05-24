"""Desktop overlay module for floating coaching widget.

Provides an always-on-top overlay window that displays real-time
coaching suggestions during sales calls without requiring window switching.
"""

from src.overlay.overlay_widget import OverlayWidget
from src.overlay.overlay_hotkey import HotkeyManager

__all__ = ["OverlayWidget", "HotkeyManager"]
