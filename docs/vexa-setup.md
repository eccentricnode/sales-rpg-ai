# Vexa Self-Hosted Setup Guide for Sales RPG AI

**Purpose:** Deploy a self-hosted Vexa instance and connect it to Sales RPG AI for real-time meeting transcript coaching.

**Why Vexa:** Apache 2.0 licensed, self-hostable, supports Zoom/Google Meet/Teams, real-time WebSocket transcripts, GDPR-compliant when self-hosted (data stays on your infrastructure).

---

## Prerequisites

- Docker and Docker Compose installed
- 4GB+ RAM available for Vexa services
- Network access to meeting platforms (Zoom, Meet, Teams)
- Python 3.10+ with Sales RPG AI dependencies installed

---

## 1. Self-Host Vexa with Docker

Pull and run Vexa Lite (no GPU required):

```bash
# Clone the Vexa repository
git clone https://github.com/vexa-ai/vexa.git
cd vexa

# Start Vexa Lite with Docker Compose
docker compose -f docker-compose.lite.yml up -d
```

Vexa Lite runs the following services:
- **vexa-api** (port 8080): REST API and WebSocket endpoint
- **vexa-worker**: Background meeting bot orchestration
- **postgres**: Transcript storage
- **redis**: Job queue and caching

Verify Vexa is running:

```bash
curl http://localhost:8080/health
# Expected: {"status": "ok"}
```

---

## 2. Configure Environment Variables

Add the following to your Sales RPG AI `.env` file:

```bash
# Vexa connection settings
VEXA_HOST=localhost          # Vexa server hostname
VEXA_PORT=8080               # Vexa API port
VEXA_API_KEY=your-api-key    # Generate via Vexa admin panel
VEXA_WS_PATH=/ws/transcripts # WebSocket endpoint (default)
```

If running Vexa on a remote server, replace `localhost` with the server IP or hostname.

---

## 3. Generate an API Key

Access the Vexa admin panel:

```bash
# Open the Vexa admin interface
open http://localhost:8080/admin

# Or generate a key via CLI
docker exec vexa-api vexa-cli create-api-key --name "sales-rpg-ai"
```

Copy the generated key into your `VEXA_API_KEY` environment variable.

---

## 4. Connect to a Meeting

### Option A: Python Script

```python
import asyncio
from src.integrations.vexa_client import VexaClient, VexaConfig, create_vexa_pipeline_bridge
from src.realtime.buffer_manager import DualBufferManager

async def main():
    # Set up the coaching pipeline
    def on_analysis(active_text, context_text):
        print(f"Coaching trigger: {active_text}")

    buffer_mgr = DualBufferManager(on_analysis_ready=on_analysis)

    # Connect to Vexa
    config = VexaConfig()  # Reads from env vars
    client = VexaClient(config)
    await client.connect()

    # Bridge Vexa transcripts into the coaching pipeline
    create_vexa_pipeline_bridge(client, buffer_mgr)

    # Create a bot for a Zoom call
    meeting_id = await client.create_meeting_bot(
        "https://zoom.us/j/1234567890",
        bot_name="Sales Coach"
    )
    print(f"Bot joining meeting: {meeting_id}")

    # Start receiving real-time transcripts
    await client.start_streaming()

    # Keep running until meeting ends or interrupted
    try:
        while client.streaming:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        await client.stop_streaming()
        await client.disconnect()

asyncio.run(main())
```

### Option B: Via the Sales RPG AI Web Interface

Once the Vexa integration is enabled, the web UI provides a "Join Meeting" button:

1. Start the Sales RPG AI server: `uv run python -m src.web.run`
2. Open `http://localhost:8000` in your browser
3. Enter a Zoom, Google Meet, or Teams meeting URL
4. Click "Join Meeting" to dispatch a Vexa bot
5. Real-time coaching suggestions appear as the meeting progresses

---

## 5. Connecting to Specific Platforms

### Zoom

```
Meeting URL format: https://zoom.us/j/MEETING_ID?pwd=PASSWORD
```

The Vexa bot joins as a participant named "Sales Coach" (configurable). Zoom will show the standard recording consent dialog to all participants.

### Google Meet

```
Meeting URL format: https://meet.google.com/abc-defg-hij
```

The bot joins via headless browser. All participants see the bot in the participant list.

### Microsoft Teams

```
Meeting URL format: https://teams.microsoft.com/l/meetup-join/...
```

Teams meetings require the bot to be admitted by the meeting organizer.

---

## 6. Architecture Overview

```
Meeting (Zoom / Meet / Teams)
    |
    v
Self-hosted Vexa (Docker)
    | Real-time WebSocket transcripts
    v
VexaClient (src/integrations/vexa_client.py)
    | TranscriptEvent objects
    v
Pipeline Bridge (create_vexa_pipeline_bridge)
    | Segment dicts
    v
DualBufferManager (src/realtime/buffer_manager.py)
    | Buffered text batches
    v
StreamingAnalyzer (src/realtime/analysis_orchestrator.py)
    | Coaching suggestions
    v
Web UI / Overlay (real-time display)
```

---

## 7. Troubleshooting

### Bot fails to join meeting

- Verify Vexa services are running: `docker compose ps`
- Check Vexa logs: `docker compose logs vexa-worker`
- Ensure the meeting URL is correct and the meeting is active
- For Teams: the organizer must admit the bot from the lobby

### No transcripts received

- Check WebSocket connection: the client logs connection status
- Verify `VEXA_API_KEY` is set correctly
- Check Vexa worker logs for transcription errors
- Ensure the meeting has audio (unmuted participants)

### High latency

- Vexa Lite transcription adds ~500ms-1s latency
- For lower latency, use Vexa with GPU acceleration (requires NVIDIA GPU)
- Check network latency between Sales RPG AI and the Vexa server

### Connection drops

- VexaClient has automatic reconnection (up to 10 attempts by default)
- If the Vexa server restarts, the client will reconnect and re-subscribe
- Monitor logs for "Reconnecting to Vexa" messages

---

## 8. Privacy and Compliance

- **Participant notification:** Vexa bots appear as named participants, providing visible notice of recording. This satisfies transparency requirements for most jurisdictions.
- **Data sovereignty:** All transcript data stays on your self-hosted infrastructure. No data sent to third-party services.
- **GDPR compliance:** Self-hosted Vexa means you control data retention, deletion, and access. Configure Vexa's data retention policies according to your compliance requirements.
- **Consent:** Meeting participants can see the bot and choose to leave if they do not consent. Configure the bot name to clearly indicate recording (e.g., "Sales Coach - Recording").
- **Two-party consent:** In jurisdictions requiring all-party consent (California, EU, etc.), the visible bot participant satisfies the notice requirement. Consult legal counsel for your specific jurisdiction.

See `docs/notetaker-research.md` for detailed research on legal considerations across different meeting capture approaches.
