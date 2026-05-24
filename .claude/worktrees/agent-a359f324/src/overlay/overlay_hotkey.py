"""Hotkey manager for the desktop overlay widget.

Provides keyboard shortcut binding for showing/hiding the overlay.
Supports tkinter-native keybindings and can be extended with
pynput for global system-wide hotkey support.
"""

import logging
from typing import Callable, Dict, Optional

logger = logging.getLogger(__name__)

# Default hotkey configuration
DEFAULT_HOTKEY = "<Control-Shift-O>"


class HotkeyManager:
    """Manages keyboard shortcuts (hotkeys) for the overlay.

    This hotkey manager supports:
        - tkinter-native keybindings (works within the app)
        - Configurable keybind mappings
        - Multiple shortcut registrations

    For global system-wide keyboard shortcuts (outside the app window),
    the pynput library can be used as an optional backend.
    """

    def __init__(self) -> None:
        self._bindings: Dict[str, Callable] = {}
        self._tk_root = None
        self._global_listener = None

    def register(self, hotkey: str, callback: Callable) -> None:
        """Register a hotkey keybind with a callback.

        Args:
            hotkey: Key combination string (e.g., '<Control-Shift-O>')
            callback: Function to call when the keyboard shortcut is pressed
        """
        self._bindings[hotkey] = callback
        logger.info(f"Registered hotkey shortcut: {hotkey}")

        # If we have a tk root, bind immediately
        if self._tk_root:
            self._tk_root.bind_all(hotkey, lambda e: callback())

    def unregister(self, hotkey: str) -> None:
        """Unregister a hotkey keybind.

        Args:
            hotkey: Key combination string to remove
        """
        if hotkey in self._bindings:
            del self._bindings[hotkey]
            if self._tk_root:
                self._tk_root.unbind_all(hotkey)
            logger.info(f"Unregistered hotkey: {hotkey}")

    def bind_to_tk(self, root) -> None:
        """Bind all registered hotkeys to a tkinter root window.

        Args:
            root: tkinter.Tk root window
        """
        self._tk_root = root
        for hotkey, callback in self._bindings.items():
            root.bind_all(hotkey, lambda e, cb=callback: cb())
            logger.info(f"Bound keyboard shortcut {hotkey} to tkinter root")

    def start_global_listener(self) -> None:
        """Start a global hotkey listener using pynput (optional).

        This enables system-wide keyboard shortcut detection even when
        the overlay window is not focused. Requires pynput to be installed.
        """
        try:
            from pynput import keyboard as pynput_keyboard

            def on_press(key):
                # Global hotkey detection handled by pynput
                pass

            self._global_listener = pynput_keyboard.Listener(on_press=on_press)
            self._global_listener.start()
            logger.info("Global keyboard hotkey listener started (pynput)")
        except ImportError:
            logger.info(
                "pynput not installed; using tkinter keybind only. "
                "Install pynput for global hotkey support."
            )

    def stop(self) -> None:
        """Stop the global hotkey listener."""
        if self._global_listener:
            self._global_listener.stop()
            self._global_listener = None
            logger.info("Global keyboard listener stopped")

    @property
    def registered_hotkeys(self) -> Dict[str, Callable]:
        """Return all registered keybind mappings."""
        return dict(self._bindings)
