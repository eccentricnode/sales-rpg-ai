"""Desktop overlay widget for real-time coaching suggestions.

Uses tkinter (stdlib) to create a floating, always-on-top, draggable,
and resizable window that displays coaching suggestions, transcript,
and analysis results from the Sales RPG AI server via WebSocket.
"""

import json
import logging
import threading
import tkinter as tk
from tkinter import ttk
from typing import Optional

logger = logging.getLogger(__name__)

# Default overlay configuration
DEFAULT_WIDTH = 400
DEFAULT_HEIGHT = 300
DEFAULT_OPACITY = 0.92
DEFAULT_WS_URL = "ws://localhost:8000/ws/audio?role=monitor"
HOTKEY_TOGGLE = "<Control-Shift-O>"


class OverlayWidget:
    """Floating desktop overlay for coaching suggestions.

    Features:
        - Always-on-top window (wm_attributes '-topmost')
        - Draggable via title bar mouse events
        - Resizable via configurable dimensions and resize handles
        - Hotkey to show/hide (Ctrl+Shift+O by default)
        - WebSocket client for live coaching data
        - Semi-transparent background option
    """

    def __init__(
        self,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        opacity: float = DEFAULT_OPACITY,
        ws_url: str = DEFAULT_WS_URL,
        hotkey: str = HOTKEY_TOGGLE,
    ) -> None:
        self.width = width
        self.height = height
        self.opacity = opacity
        self.ws_url = ws_url
        self.hotkey_binding = hotkey
        self._visible = True
        self._drag_data = {"x": 0, "y": 0}

        self.root: Optional[tk.Tk] = None
        self._ws_thread: Optional[threading.Thread] = None
        self._ws_connected = False

    def create_window(self) -> tk.Tk:
        """Create and configure the overlay window."""
        self.root = tk.Tk()
        self.root.title("Sales RPG AI - Coaching Overlay")

        # Always-on-top: wm_attributes with -topmost flag
        self.root.wm_attributes("-topmost", True)

        # Semi-transparent background
        self.root.attributes("-alpha", self.opacity)

        # Window size and position (bottom-right corner)
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = screen_w - self.width - 20
        y = screen_h - self.height - 60
        self.root.geometry(f"{self.width}x{self.height}+{x}+{y}")

        # Allow resizing
        self.root.resizable(True, True)
        self.root.minsize(250, 150)

        # Remove default window decorations for a cleaner overlay look
        self.root.overrideredirect(False)

        # Build the UI
        self._build_ui()

        # Bind draggable behavior on the title frame
        self._bind_drag_events()

        # Bind hotkey for show/hide toggle
        self._bind_hotkey()

        return self.root

    def _build_ui(self) -> None:
        """Build the overlay UI components."""
        # Main frame with dark theme
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # Title bar (draggable area)
        self.title_frame = tk.Frame(main_frame, bg="#1a1a2e", height=30)
        self.title_frame.pack(fill=tk.X)
        self.title_frame.pack_propagate(False)

        title_label = tk.Label(
            self.title_frame,
            text="Coaching Overlay",
            fg="#e0e0e0",
            bg="#1a1a2e",
            font=("Helvetica", 10, "bold"),
        )
        title_label.pack(side=tk.LEFT, padx=8)

        # Close button
        close_btn = tk.Button(
            self.title_frame,
            text="x",
            command=self.hide,
            fg="#e0e0e0",
            bg="#1a1a2e",
            bd=0,
            font=("Helvetica", 10),
        )
        close_btn.pack(side=tk.RIGHT, padx=4)

        # Coaching suggestions area
        suggestion_label = tk.Label(
            main_frame,
            text="Coaching Suggestions",
            fg="#aaaaaa",
            bg="#16213e",
            font=("Helvetica", 9),
            anchor=tk.W,
        )
        suggestion_label.pack(fill=tk.X, padx=4, pady=(4, 0))

        self.suggestion_text = tk.Text(
            main_frame,
            height=5,
            wrap=tk.WORD,
            bg="#0f3460",
            fg="#e0e0e0",
            font=("Helvetica", 10),
            bd=0,
            padx=6,
            pady=4,
        )
        self.suggestion_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        self.suggestion_text.insert("1.0", "Waiting for coaching data...")
        self.suggestion_text.config(state=tk.DISABLED)

        # Transcript area
        transcript_label = tk.Label(
            main_frame,
            text="Live Transcript",
            fg="#aaaaaa",
            bg="#16213e",
            font=("Helvetica", 9),
            anchor=tk.W,
        )
        transcript_label.pack(fill=tk.X, padx=4, pady=(4, 0))

        self.transcript_text = tk.Text(
            main_frame,
            height=3,
            wrap=tk.WORD,
            bg="#1a1a2e",
            fg="#cccccc",
            font=("Helvetica", 9),
            bd=0,
            padx=6,
            pady=4,
        )
        self.transcript_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=(2, 4))
        self.transcript_text.config(state=tk.DISABLED)

        # Status bar
        self.status_var = tk.StringVar(value="Disconnected")
        status_bar = tk.Label(
            main_frame,
            textvariable=self.status_var,
            fg="#666666",
            bg="#16213e",
            font=("Helvetica", 8),
            anchor=tk.W,
        )
        status_bar.pack(fill=tk.X, padx=4, pady=(0, 2))

    def _bind_drag_events(self) -> None:
        """Bind mouse events for draggable window behavior."""
        self.title_frame.bind("<Button-1>", self._on_drag_start)
        self.title_frame.bind("<B1-Motion>", self._on_drag_motion)

        # Also bind to children of title frame
        for child in self.title_frame.winfo_children():
            child.bind("<Button-1>", self._on_drag_start)
            child.bind("<B1-Motion>", self._on_drag_motion)

    def _on_drag_start(self, event: tk.Event) -> None:
        """Record the initial position for drag."""
        self._drag_data["x"] = event.x_root - self.root.winfo_x()
        self._drag_data["y"] = event.y_root - self.root.winfo_y()

    def _on_drag_motion(self, event: tk.Event) -> None:
        """Move the window during drag."""
        x = event.x_root - self._drag_data["x"]
        y = event.y_root - self._drag_data["y"]
        self.root.geometry(f"+{x}+{y}")

    def _bind_hotkey(self) -> None:
        """Bind hotkey for show/hide toggle.

        Uses tkinter's keyboard binding for the overlay hotkey shortcut.
        The default keybind is Ctrl+Shift+O.
        """
        if self.root:
            self.root.bind_all(self.hotkey_binding, self._toggle_visibility)
            logger.info(f"Hotkey bound: {self.hotkey_binding} for overlay toggle")

    def _toggle_visibility(self, event: Optional[tk.Event] = None) -> None:
        """Toggle overlay visibility via hotkey."""
        if self._visible:
            self.hide()
        else:
            self.show()

    def show(self) -> None:
        """Show the overlay window."""
        if self.root:
            self.root.deiconify()
            self.root.wm_attributes("-topmost", True)
            self._visible = True

    def hide(self) -> None:
        """Hide the overlay window."""
        if self.root:
            self.root.withdraw()
            self._visible = False

    def update_suggestion(self, text: str) -> None:
        """Update the coaching suggestion display."""
        if self.suggestion_text:
            self.suggestion_text.config(state=tk.NORMAL)
            self.suggestion_text.delete("1.0", tk.END)
            self.suggestion_text.insert("1.0", text)
            self.suggestion_text.config(state=tk.DISABLED)

    def update_transcript(self, text: str) -> None:
        """Update the transcript display."""
        if self.transcript_text:
            self.transcript_text.config(state=tk.NORMAL)
            self.transcript_text.delete("1.0", tk.END)
            self.transcript_text.insert("1.0", text)
            self.transcript_text.config(state=tk.DISABLED)
            self.transcript_text.see(tk.END)

    def set_status(self, status: str) -> None:
        """Update the status bar."""
        if self.status_var:
            self.status_var.set(status)

    def connect_websocket(self) -> None:
        """Start WebSocket client in background thread.

        Connects to the Sales RPG AI server at /ws/audio?role=monitor
        and receives coaching suggestions, transcript, and analysis results.
        """
        self._ws_thread = threading.Thread(
            target=self._ws_listener,
            daemon=True,
            name="overlay-ws-client",
        )
        self._ws_thread.start()

    def _ws_listener(self) -> None:
        """WebSocket listener loop (runs in background thread)."""
        try:
            import websockets.sync.client as ws_client
        except ImportError:
            logger.warning("websockets not installed; overlay running without live data")
            self.root.after(0, lambda: self.set_status("websockets not installed"))
            return

        while True:
            try:
                self.root.after(0, lambda: self.set_status("Connecting..."))
                with ws_client.connect(self.ws_url) as ws:
                    self._ws_connected = True
                    self.root.after(0, lambda: self.set_status("Connected"))

                    for message in ws:
                        try:
                            data = json.loads(message)
                            msg_type = data.get("type", "")

                            if msg_type == "transcript":
                                text = data.get("text", "")
                                self.root.after(
                                    0, lambda t=text: self.update_transcript(t)
                                )
                            elif msg_type in ("analysis", "coaching"):
                                text = data.get("text", data.get("suggestion", ""))
                                self.root.after(
                                    0, lambda t=text: self.update_suggestion(t)
                                )
                        except json.JSONDecodeError:
                            pass

            except Exception as e:
                self._ws_connected = False
                logger.warning(f"WebSocket error: {e}, reconnecting in 3s...")
                self.root.after(0, lambda: self.set_status("Reconnecting..."))
                import time
                time.sleep(3)

    def run(self) -> None:
        """Create and run the overlay (blocking main loop)."""
        self.create_window()
        self.connect_websocket()
        self.root.mainloop()

    def destroy(self) -> None:
        """Clean up and destroy the overlay."""
        if self.root:
            self.root.destroy()
            self.root = None


def main() -> None:
    """Entry point for the overlay widget."""
    import argparse

    parser = argparse.ArgumentParser(description="Sales RPG AI Coaching Overlay")
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT)
    parser.add_argument("--opacity", type=float, default=DEFAULT_OPACITY)
    parser.add_argument("--ws-url", default=DEFAULT_WS_URL)
    args = parser.parse_args()

    overlay = OverlayWidget(
        width=args.width,
        height=args.height,
        opacity=args.opacity,
        ws_url=args.ws_url,
    )
    overlay.run()


if __name__ == "__main__":
    main()
