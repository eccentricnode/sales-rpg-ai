# Behavioral Contract: Desktop Overlay Widget

**Files:** `src/overlay/*`
**Purpose:** Display live coaching suggestions in a floating desktop window without requiring the rep to switch away from Zoom or Google Meet.

## Preconditions

- A graphical desktop session is available.
- The Sales RPG AI web server exposes monitor WebSocket updates.
- The overlay can connect to `ws://localhost:8000/ws/audio?role=monitor` or a configured equivalent.

## Postconditions

- Overlay window renders on top of the active Zoom or Google Meet window.
- Coaching suggestions and transcript updates appear without switching windows.
- The overlay is draggable and resizable.
- A show/hide hotkey is available; if global hotkeys are claimed, they work while the overlay is unfocused.
- Closing or hiding the overlay does not stop the underlying call or recorder session.

## Required Probe Evidence

- Desktop launch probe showing the overlay window can be created in the target environment.
- Visual or automated probe showing the window is topmost over Zoom or Meet.
- Probe showing a monitor WebSocket message updates the overlay text.
- Probe showing drag, resize, and hotkey show/hide behavior.

## Deferred Verification

If no graphical desktop or Zoom/Meet window is available locally, mark the story `[DEFERRED-VERIFY]` and require these human pre-flight steps:

1. Start the Sales RPG AI server and connect a monitor WebSocket.
2. Launch Zoom or Google Meet in a desktop session.
3. Launch the overlay from `src/overlay/overlay_widget.py`.
4. Confirm the overlay remains topmost, can be dragged/resized, and displays a synthetic or live coaching message.
5. Confirm the configured hotkey hides and restores the overlay while Zoom or Meet is focused.

## Edge Cases

- Tkinter-only keybindings are focused-window shortcuts, not true global hotkeys.
- Headless or Wayland-only environments may require explicit support or deferred verification.
- Overlay failures should be logged without crashing the web app or recorder.
