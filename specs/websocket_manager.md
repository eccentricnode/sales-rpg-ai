# Behavioral Contract: WebSocket Server & ConnectionManager

**File:** `src/web/app.py`
**Purpose:** FastAPI WebSocket server handling real-time audio streaming, transcript broadcasting, and coaching delivery. ConnectionManager handles multi-client broadcasting.

## Preconditions

### ConnectionManager
- WebSocket connections must be accepted before adding to active_connections
- Transcript history is stored in memory (no persistence across restarts)

### /ws/audio endpoint
- `role` query parameter: `"recorder"` (default) or `"monitor"`
- Monitor role: receive-only (no audio processing)
- Recorder role: sends audio bytes, receives transcripts + analysis
- LLM provider must be configured via env vars (raises ValueError if missing required keys)
- VadTranscriber or WhisperLiveKit must be available depending on `TRANSCRIPTION_ENGINE` setting

## Postconditions

### ConnectionManager.connect(websocket)
- Accepts WebSocket connection
- Adds to `active_connections` list
- Sends full `transcript_history` to new connection (catch-up)

### ConnectionManager.disconnect(websocket)
- Removes from `active_connections` if present
- Silent no-op if websocket not in list

### ConnectionManager.broadcast(message)
- Sends `message` dict as JSON to ALL active connections
- Dead connections (send fails) are removed from list
- Transcript messages (type="transcript") are stored in `transcript_history`

### ConnectionManager.reset()
- Clears `transcript_history`
- Sends `{"type": "reset"}` to all active connections
- Errors during reset broadcast are silently caught

### /ws/audio — Monitor role
- Accepts connection via ConnectionManager
- Receives transcript_history on connect
- Keeps connection alive by reading (discarding) text messages
- Disconnects cleanly on WebSocketDisconnect

### /ws/audio — Recorder role (VAD engine)
- Accepts WebSocket connection directly (not via ConnectionManager — recorder is NOT in active_connections)
- Resets ConnectionManager (clears history for new session — side effect: sends reset to all monitors)
- Initializes: LLM config → StreamingAnalyzer → SummaryEngine (5min interval)
- **NOTE:** VAD path does NOT use DualBufferManager or AnalysisOrchestrator — segments go directly to WebSocket + SummaryEngine. No buffer-triggered LLM analysis in this path.
- Main loop: receives binary audio chunks → feeds to VadTranscriber → broadcasts transcript segments
- Text messages parsed as JSON commands (`refresh_summary`, `recommend`) via `handle_command()`
- On disconnect: flushes VadTranscriber for remaining segments, stops SummaryEngine
- Errors logged with exc_info

### /ws/audio — Recorder role (WhisperLiveKit engine)
- Same initialization as VAD but connects to external WhisperLiveKit WebSocket
- Retry logic: up to 5 attempts with exponential backoff (max 16s delay)
- Relay loop: browser audio → WhisperLive WebSocket → parse transcripts → broadcast
- Tracks `prev_line_texts` for incremental transcript delivery (only sends new/updated lines)
- Buffer text (partial transcription) sent as non-final segments

### /ws/dual-audio
- Requires PyAudio (not available in Docker)
- Captures both microphone and system audio
- Creates session directory in `/tmp/sales-rpg-ai/dual_capture/`
- Initializes DualCaptureManager + DualStreamTranscriber
- Optionally initializes DualBufferManager + AnalysisOrchestrator (if LLM configured)
- Waits for "stop" command from frontend
- Returns final transcript in text, JSON, and SRT formats

## Invariants

1. **Single recorder:** `reset()` called on new recorder connection — only one active recording session
2. **Monitor catch-up:** New monitor connections receive full transcript history
3. **Dead connection cleanup:** Failed broadcasts remove dead connections (no zombie accumulation)
4. **SummaryEngine lifecycle:** Started on connection, stopped in finally block (guaranteed cleanup)
5. **Audio chunk logging:** Every 50th chunk logged (not every chunk — prevents log flooding)
6. **VadTranscriber flush:** On disconnect, remaining audio is flushed and broadcast (finally block)

## Edge Cases

1. **No LLM configured:** Recorder role fails fast with close code 1011 and descriptive reason
2. **VadTranscriber init failure:** WebSocket closed with 1011 and error description
3. **WhisperLiveKit unavailable:** 5 retries with exponential backoff, then close with error message
4. **WhisperLiveKit dies mid-session:** `whisper_alive` flag set False, audio relay stops, transcripts continue from buffer
5. **Client disconnects mid-audio:** WebSocketDisconnect caught, VadTranscriber flushed, SummaryEngine stopped
6. **Broadcast during disconnect:** Dead connections removed from list, no crash
7. **Concurrent recorder + monitor:** Recorder processes audio, monitor receives broadcasts — works correctly
8. **Multiple recorders:** Second recorder calls `reset()`, clearing first recorder's history — no protection against this
9. **DualCapture not available:** `/ws/dual-audio` returns error and closes immediately
10. **Summary callback from thread:** Uses `asyncio.run_coroutine_threadsafe()` to bridge thread → async — correct but error handling is minimal
11. **No concurrent recorder protection:** Two tabs can connect as recorder simultaneously, each with independent VadTranscriber. Second calls `reset()`, stomping first's history. Fix: add global lock or reject second recorder.
12. **transcript_history grows unbounded:** New monitor connections receive massive catch-up payload for long sessions.
13. **No auth on WebSocket endpoints:** Anyone with network access can connect as recorder or monitor.
14. **Health endpoint leaks config:** `/health` exposes whisper host, port, provider, connection count.
