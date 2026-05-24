# Behavioral Contract: Vexa Notetaker Integration

**Files:** `src/integrations/vexa_client.py`, `src/web/app.py`, `src/web/templates/index.html`
**Purpose:** Connect a self-hosted Vexa meeting bot to Sales RPG AI so Zoom or Google Meet conversations can feed the coaching pipeline.

## Preconditions

- A self-hosted Vexa deployment is reachable from this machine.
- `VEXA_HOST`, `VEXA_PORT`, `VEXA_API_KEY`, and `VEXA_WS_PATH` are configured.
- A real Zoom or Google Meet session is available for a bot join test.
- Meeting participants consent to the notetaker according to local law and company policy.

## Postconditions

- Sales RPG AI can dispatch or connect to a Vexa bot for a Zoom or Google Meet URL.
- Transcript events from Vexa are converted into the shared segment contract: `text`, `start`, `end`, `completed`.
- Both sides of the meeting conversation are captured by the Vexa transcript stream.
- Vexa transcripts feed the same buffering, summary, and coaching path used by other transcript sources.
- Setup and privacy/compliance documentation match the implemented UI/API surface.

## Required Probe Evidence

- Local connectivity probe against the configured Vexa server.
- Probe that creates or attaches to a meeting bot and records a Vexa meeting/session id.
- Live meeting probe showing at least two speakers or both conversation sides in transcript events.
- Probe showing Vexa transcript events reach `DualBufferManager` and trigger/cooperate with analysis.
- Documentation review confirming setup instructions match actual routes and UI controls.

## Deferred Verification

If no Vexa stack or real meeting is available locally, mark the story `[DEFERRED-VERIFY]` and require these human pre-flight steps:

1. Start Vexa and confirm its API/WebSocket endpoint is reachable from the Sales RPG AI host.
2. Generate and export a valid `VEXA_API_KEY`.
3. Create a disposable Zoom or Google Meet call with two human or synthetic speakers.
4. Allow the Vexa bot into the meeting and confirm participant notice/consent.
5. Capture logs or screenshots showing bot join, transcript events from both sides, and Sales RPG AI receiving those events.

## Edge Cases

- Vexa API client code must match the installed `websockets` version's header argument.
- The integration must report bot join failures, invalid meeting URLs, and missing API keys clearly.
- Web UI claims such as "Join Meeting" must not exist in documentation unless the control exists in code.
