# Behavioral Contract: WebSocket Reconnection

**Files:** `src/web/app.py`, `src/web/static/js/audio-client.js`
**Purpose:** Detect dropped WebSocket clients quickly and let clients reconnect without losing transcript or coaching context.

## Preconditions

- WebSocket requests must pass `validate_origin()` before acceptance.
- Recorder and monitor clients must identify their role through `/ws/audio?role=...`.
- `ConnectionManager.transcript_history` is the in-memory transcript replay source for reconnecting clients.

## Postconditions

- Connection drops are detected within 5 seconds by a heartbeat, timeout, ping, or scheduled stale-connection cleanup.
- Reconnecting monitor clients receive all retained transcript history on connect.
- Reconnecting recorder clients receive an explicit `recorder_resume.supported=false` policy because live audio streams cannot be resumed safely from in-memory server state.
- Half-open monitor connections are removed without waiting indefinitely for the next transcript broadcast.
- Coaching state needed by the UI is preserved or replayed through the reconnection payload.

## Required Probe Evidence

- Unit or integration probe showing invalid origins are rejected before acceptance.
- Probe showing a reconnecting monitor receives transcript history, coaching/session state, and the explicit recorder resume policy.
- Probe showing a stale/half-open connection is removed within the 5-second SLA.
- Live or TestClient/WebSocket probe showing runtime code schedules or invokes stale-connection cleanup.

## Edge Cases

- Multiple recorder connections must not silently reset each other's session state.
- Reconnection after server restart can only replay persisted state if persistence exists; otherwise the loss must be explicit.
- History replay must be bounded to avoid unbounded memory growth during long calls.
