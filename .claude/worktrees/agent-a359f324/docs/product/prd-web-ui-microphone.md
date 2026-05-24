# PRD: Web-Based UI with Microphone Input

## Status
✅ **Implemented** (Phase 2)

## Problem

Testing the Sales AI application currently requires:
- Local Python environment setup
- PyAudio + PortAudio installation
- Docker audio passthrough (complex)

This creates friction for demos and makes Docker deployment incomplete.

## Relationship to Other PRDs

This PRD **complements** (not replaces) `prd-microphone-input.md`:

| PRD | Use Case | Input Method | Output |
|-----|----------|--------------|--------|
| `prd-microphone-input.md` | Local dev/testing | PyAudio CLI | Terminal |
| `prd-web-ui-microphone.md` | Demos/deployment | Browser MediaRecorder | Web UI |

**Both share the same core pipeline:**
- `DualBufferManager` - buffers transcript chunks
- `AnalysisOrchestrator` - async LLM calls
- `StreamingAnalyzer` - objection detection

The Web UI is an alternative **input/output layer**, not a replacement for the core.

## Solution

Build a **web-based UI** that:
1. Captures microphone audio in the browser (WebRTC/MediaRecorder API)
2. Streams audio to WhisperLive via WebSocket
3. Displays live transcript and objection detection
4. Runs entirely in Docker - user just opens a URL

**Tech Stack:**
- **Backend:** FastAPI (already a dependency)
- **Templating:** Jinja2 + HTMX for server-side rendering
- **Browser APIs:** MediaRecorder, WebSocket (vanilla JS)
- **No frameworks:** No React, Vue, or build tools

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Browser                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                     Web UI (:8080)                         │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌────────────────────┐ │ │
│  │  │ Mic Control │  │  Transcript │  │ Objection Alerts   │ │ │
│  │  │ [Start/Stop]│  │  (live)     │  │ + Suggestions      │ │ │
│  │  └──────┬──────┘  └─────────────┘  └────────────────────┘ │ │
│  │         │ MediaRecorder API                                │ │
│  │         ▼                                                  │ │
│  │  ┌─────────────┐                                           │ │
│  │  │  WebSocket  │ Audio chunks (binary)                     │ │
│  │  │  to :8080   │─────────────────────────────┐             │ │
│  │  └─────────────┘                             │             │ │
│  └──────────────────────────────────────────────│─────────────┘ │
└─────────────────────────────────────────────────│───────────────┘
                                                  │
┌─────────────────────────────────────────────────│───────────────┐
│                    Docker Network               │               │
│                                                 ▼               │
│  ┌─────────────────┐    ┌─────────────────────────────────────┐│
│  │  whisper-live   │    │          sales-ai-web               ││
│  │     :9090       │◄───│            :8080                    ││
│  │                 │    │                                     ││
│  │  Transcription  │    │  FastAPI + Jinja2 + HTMX            ││
│  │  via WebSocket  │───►│  - Proxy to WhisperLive             ││
│  │                 │    │  - Buffers Transcript               ││
│  └─────────────────┘    │  - Calls LocalAI / OpenRouter       ││
│                         │  - Pushes updates via WS            ││
│                         └─────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

---

## User Experience

### Flow

1. User runs `make up`
2. Opens `http://localhost:8080` in browser
3. Clicks "Start Recording" → browser asks for mic permission
4. Speaks → sees live transcript appear
5. Says objection → sees alert with suggested response
6. Clicks "Stop Recording" → sees session summary

### UI Layout

```
┌─────────────────────────────────────────────────────────────┐
│  Sales AI - Real-Time Objection Detection                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  [🎤 Start Recording]  [⏹ Stop]     Status: Ready   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  LIVE TRANSCRIPT                                     │   │
│  │  ─────────────────────────────────────────────────  │   │
│  │  Hi, thanks for meeting with me today. I wanted     │   │
│  │  to discuss our enterprise solution...              │   │
│  │  _                                                  │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  ⚠️  OBJECTION DETECTED                              │   │
│  │  ─────────────────────────────────────────────────  │   │
│  │  Type: PRICE | Confidence: HIGH                     │   │
│  │  "That's way too expensive for our budget"          │   │
│  │                                                     │   │
│  │  💡 Suggested Response:                             │   │
│  │  "I understand budget is a concern. Can you tell    │   │
│  │   me more about your constraints so we can find     │   │
│  │   a solution that works?"                           │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  SESSION STATS                                       │   │
│  │  Duration: 2:34 | Objections: 3 | Analyses: 12      │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Technical Design

### Backend: FastAPI

```
src/
├── web/
│   ├── __init__.py
│   ├── app.py              # FastAPI application
│   ├── routes.py           # HTTP routes
│   ├── websocket.py        # WebSocket handlers
│   └── templates/
│       ├── base.html       # Base template
│       ├── index.html      # Main page
│       └── partials/
│           ├── transcript.html    # HTMX partial
│           └── objection.html     # HTMX partial
│   └── static/
│       ├── app.js          # Vanilla JS for mic/WebSocket
│       └── style.css       # Minimal CSS
```

### Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Main UI page |
| `/ws/audio` | WebSocket | Receives audio from browser, proxies to WhisperLive |
| `/ws/updates` | WebSocket | Sends transcript + objection updates to browser |
| `/api/status` | GET | Health check |

### Data Flow

```
Browser Mic ──► /ws/audio ──► WhisperLive (:9090)
                                   │
                                   ▼
                            Transcript callback
                                   │
                                   ▼
                            DualBufferManager
                                   │
                                   ▼
                            AnalysisOrchestrator
                                   │
                                   ▼
                            /ws/updates ──► Browser UI
```

### Browser JavaScript (Vanilla)

```javascript
// Microphone capture using MediaRecorder API
const startRecording = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus'
    });

    const ws = new WebSocket('ws://localhost:8080/ws/audio');

    mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0 && ws.readyState === WebSocket.OPEN) {
            ws.send(event.data);
        }
    };

    mediaRecorder.start(100); // Send chunks every 100ms
};
```

### HTMX Updates

```html
<!-- Transcript updates via SSE or WebSocket -->
<div id="transcript" hx-ext="ws" ws-connect="/ws/updates">
    <div id="transcript-content" hx-swap-oob="beforeend">
        <!-- New transcript chunks appended here -->
    </div>
</div>

<!-- Objection alerts -->
<div id="objections" hx-swap-oob="afterbegin">
    <!-- New objections prepended here -->
</div>
```

---

## Acceptance Criteria

- [ ] `make up` starts web UI at `http://localhost:8080`
- [ ] Browser mic permission request works
- [ ] Audio streams to WhisperLive correctly
- [ ] Live transcript appears within ~1 second of speech
- [ ] Objections display with type, quote, and suggestion
- [ ] Start/Stop controls work cleanly
- [ ] Works in Chrome and Firefox
- [ ] No JavaScript framework dependencies
- [ ] Mobile-responsive (basic)

---

## Implementation Tasks

### Task 1: Create FastAPI Web Application Structure

Create `src/web/` module:
- `app.py` - FastAPI app initialization
- `routes.py` - HTTP routes
- Mount static files and templates

### Task 2: Create Base HTML Templates

Create Jinja2 templates:
- `base.html` - HTML boilerplate, HTMX script
- `index.html` - Main page layout

### Task 3: Implement Microphone Capture (JavaScript)

Create `static/app.js`:
- MediaRecorder API for mic capture
- WebSocket connection to backend
- Start/Stop controls
- Error handling (no mic, permission denied)

### Task 4: Implement Audio WebSocket Proxy

Create `/ws/audio` endpoint:
- Receive audio chunks from browser
- Convert format if needed (WebM → PCM)
- Forward to WhisperLive WebSocket
- Receive transcripts back

### Task 5: Integrate DualBufferManager

Connect transcript flow:
- WhisperLive callback → DualBufferManager
- Trigger analysis → AnalysisOrchestrator
- Results → WebSocket to browser

### Task 6: Implement Updates WebSocket

Create `/ws/updates` endpoint:
- Send transcript updates (HTMX partials)
- Send objection alerts (HTMX partials)
- Handle multiple connected clients

### Task 7: Create HTMX Partials

Create partial templates:
- `transcript.html` - Single transcript chunk
- `objection.html` - Objection alert card

### Task 8: Add Styling

Create `static/style.css`:
- Clean, minimal design
- Objection alerts stand out (color/animation)
- Mobile responsive

### Task 9: Update Docker Configuration

Modify `docker-compose.yml`:
- Expose port 8080 for web UI
- Set environment variables
- Health check for web service

### Task 10: Update Makefile

Add targets:
- `make web` - Open browser to UI
- Update `make up` to show URL

---

## Audio Format Considerations

**Browser output:** WebM/Opus (MediaRecorder default)

**WhisperLive expects:** PCM 16-bit, 16kHz, mono

**Options:**
1. **Client-side conversion:** Use AudioContext to output PCM (more JS code)
2. **Server-side conversion:** Use ffmpeg to convert WebM → PCM (simpler)
3. **Check WhisperLive:** May already handle WebM/Opus

Recommend: Start with option 2 (ffmpeg server-side) for simplicity.

---

## Dependencies

### Python (add to pyproject.toml)
- `fastapi` (already present)
- `uvicorn` (already present)
- `jinja2` (already present)
- `websockets` (for WebSocket support)
- `python-multipart` (already present)

### Frontend (CDN, no npm)
- HTMX: `<script src="https://unpkg.com/htmx.org@1.9.10"></script>`
- htmx websocket extension

### System
- ffmpeg (for audio conversion, already in Docker)

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Time from page load to recording | < 3 seconds |
| Transcript latency | < 2 seconds |
| Objection detection latency | < 5 seconds end-to-end |
| Works without errors | 5+ minute session |

---

## Out of Scope

- User authentication
- Session persistence/history
- Multiple simultaneous users
- Audio recording/playback
- Custom styling/themes

---

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Browser mic API differences | Medium | Medium | Test Chrome + Firefox |
| Audio format conversion issues | Medium | High | Use ffmpeg, test thoroughly |
| WebSocket connection drops | Low | Medium | Add reconnection logic |
| HTMX complexity | Low | Low | Keep partials simple |

---

## Timeline Estimate

| Task | Effort |
|------|--------|
| FastAPI structure | 20 min |
| Base templates | 20 min |
| Mic capture JS | 45 min |
| Audio WebSocket proxy | 45 min |
| Buffer integration | 30 min |
| Updates WebSocket | 30 min |
| HTMX partials | 20 min |
| Styling | 30 min |
| Docker updates | 15 min |
| Testing | 30 min |
| **Total** | **~5 hours** |

---

## Integration with Docker PRD

The Docker deployment PRD (`prd-docker-deployment.md`) should include:

1. Web UI service on port 8080
2. `make web` target to open browser
3. Both CLI and Web UI available in container

**Final `make up` experience:**
```bash
make up
# Services starting...
# WhisperLive: ws://localhost:9090
# Web UI: http://localhost:8080
#
# Options:
#   - Open http://localhost:8080 for Web UI demo
#   - Run 'make shell' then 'python src/realtime_transcribe.py --mic' for CLI
```

## Relationship Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                     Input Sources                                │
│  ┌─────────────────┐              ┌─────────────────────────┐   │
│  │  CLI --mic      │              │  Web UI (Browser)       │   │
│  │  (PyAudio)      │              │  (MediaRecorder API)    │   │
│  │  prd-microphone │              │  prd-web-ui-microphone  │   │
│  └────────┬────────┘              └────────────┬────────────┘   │
│           │                                    │                │
│           └──────────────┬─────────────────────┘                │
│                          ▼                                      │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                 Shared Core Pipeline                       │  │
│  │                                                           │  │
│  │   WhisperLive → DualBufferManager → AnalysisOrchestrator │  │
│  │                                    → StreamingAnalyzer    │  │
│  │                                                           │  │
│  │   (src/realtime/buffer_manager.py)                        │  │
│  │   (src/realtime/analysis_orchestrator.py)                 │  │
│  └───────────────────────────────────────────────────────────┘  │
│                          │                                      │
│           ┌──────────────┴─────────────────┐                    │
│           ▼                                ▼                    │
│  ┌─────────────────┐              ┌─────────────────────────┐   │
│  │  Terminal Output│              │  HTMX Web Updates       │   │
│  │  (print)        │              │  (WebSocket partials)   │   │
│  └─────────────────┘              └─────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```
