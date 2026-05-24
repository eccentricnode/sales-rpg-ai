# Meeting Notetaker Research — Sales RPG AI Entry Point

**Date:** 2026-03-09
**Purpose:** Evaluate approaches for capturing real-time audio from Zoom/Google Meet calls to feed the Sales RPG AI coaching engine.

**Key Requirement:** REAL-TIME audio streaming (5-20 second windows), not post-meeting transcription.

---

## Approach 1: Zoom Meeting SDK (DIY Bot)

**Can it provide real-time audio?** YES — PCM 16-bit LE at 16 kHz mono via Raw Data API.

**How it works:** Headless C++ bot joins meeting as participant, receives raw audio frames via Meeting SDK. Zoom provides official sample repos (meetingsdk-linux-raw-recording-sample, meetingsdk-headless-linux-sample).

**Setup complexity:** VERY HIGH
- C++ compilation (cmake + make) in Docker
- PulseAudio setup for headless environments
- One bot instance per meeting
- Must handle scaling infrastructure

**Cost:** Free SDK + ~$50-200/month infrastructure per server

**Marketplace approval:** Required for joining external meetings. Weeks-to-months review. Must include privacy policy, SSDLC documentation, security incident response plan. Bots must request recording permission and show disclaimer (mandatory since July 2023).

**Participant visibility:** YES — bot appears in participant list

**Latency:** <100ms for audio delivery

**Verdict:** Works but 2-4 months engineering to build production-ready. Recall.ai/Vexa already solved this.

---

## Approach 2: Google Meet API

**Can it provide real-time audio?** YES via Meet Media API — BUT still in Developer Preview with critical blocker.

**Critical Blocker:** ALL meeting participants must be enrolled in the Google Workspace Developer Preview Program. This makes it **unusable for sales calls with external prospects.**

**Alternative:** Headless Chrome bot that joins Meet as participant and captures audio via browser media APIs. This is what Recall.ai, Skribby, and MeetStream use today.

**Setup complexity:** VERY HIGH for Media API. HIGH for headless browser.

**Participant visibility:** YES

**Latency:** <100ms (Media API), 200-500ms (headless browser)

**Verdict:** Media API is a non-starter for external sales calls. Headless browser works but is complex to build and maintain.

---

## Approach 3: Recall.ai (Managed Service)

**Can it provide real-time audio?** YES — secure WebSocket at 16 kHz. Per-participant separation available.

**What it offers:**
- Pre-built bots for Zoom, Google Meet, Microsoft Teams
- Real-time audio streaming via WebSocket (mixed or per-participant)
- Built-in real-time transcription
- Participant detection (who's speaking, join/leave events)
- Handles Zoom compliance requirements automatically

**Setup complexity:** LOW — REST API to create bots, days to integrate

**Cost:** $0.50/hour (Pay As You Go, prorated to the second). Built-in transcription: +$0.15/hour.

**Participant visibility:** YES — bot appears as named participant

**Latency:** 200-500ms

**Verdict:** Fastest path to production. Handles all the hard infrastructure.

---

## Approach 4: On-Machine (Cluely-Style)

**How it works:** Desktop app captures system audio via OS-level loopback (WASAPI/Core Audio/PulseAudio) + microphone. Overlay window invisible to screen sharing. No bot joins the meeting.

**Can it provide real-time audio?** YES — local capture at <10ms.

**Open source clones:** cheap-cluely (Python, Whisper + Gemini), Natively (privacy-first)

**Setup complexity:** MEDIUM for building your own

**Cost:** Free + transcription API costs. No per-meeting infrastructure.

**CRITICAL LEGAL ISSUE:** No participant notification. In 2-party consent jurisdictions (California, EU, many US states), recording without consent is **illegal.** Cluely has faced significant controversy for exactly this reason. macOS shows a purple indicator dot but that's insufficient for legal compliance.

**Participant visibility:** NO — completely invisible

**Verdict:** REJECTED for a sales tool. Secret recording of prospects creates legal liability and reputational risk. Not viable as a go-to-market strategy.

---

## Approach 5: Alternative Services

### Vexa (Self-Hosted, Open Source) — STANDOUT
- **Apache 2.0 licensed, fully self-hostable**
- Supports Google Meet, Microsoft Teams, Zoom
- Real-time WebSocket transcripts with sub-second delivery
- Docker self-host with "Vexa Lite" (no GPU required)
- GDPR/data sovereignty compliant (data never leaves your infra)
- **Best option for full control and eliminating per-hour costs**

### Skribby — $0.35/hour
- 30% cheaper than Recall.ai
- 10+ transcription model options
- Supports Zoom, Google Meet, Teams
- Newer/smaller company

### MeetingBaaS — Token-based pricing
- Calendar integration built-in
- More complex pricing model

### MeetStream — Newer entrant
- Meeting bot API for Meet, Zoom, Teams
- Less documentation available

### AssemblyAI Streaming — Transcription only
- $0.15/hour for real-time streaming via WebSocket
- ~300ms P50 latency
- Would pair with a bot service for audio source

### Deepgram Nova-3 — Transcription only
- $0.46/hour for real-time streaming
- Very low latency, $200 free credit

### Fireflies.ai / Otter.ai — NOT suitable
- Consumer products, no raw audio API
- Cannot feed audio to external LLM

---

## Comparison Matrix

| Approach | Real-Time? | Latency | Setup | Cost/Hour | Visible? | Legal Risk |
|----------|-----------|---------|-------|-----------|----------|------------|
| Zoom SDK (DIY) | YES | <100ms | VERY HIGH (months) | ~$0.02 | YES | LOW |
| Google Meet API | YES | <100ms | BLOCKED (dev preview) | ~$0.02 | YES | LOW |
| Recall.ai | YES | 200-500ms | LOW (days) | $0.50 | YES | LOW |
| Skribby | YES | ~200ms | LOW (days) | $0.35 | YES | LOW |
| Vexa (self-hosted) | YES | Sub-second | MEDIUM (days) | $0 + infra | YES | LOW |
| On-Machine (Cluely) | YES | <10ms | MEDIUM | $0 | NO | **HIGH** |
| AssemblyAI | Text only | ~300ms | LOW | $0.15 | N/A | N/A |
| Deepgram | Text only | <200ms | LOW | $0.46 | N/A | N/A |

---

## RECOMMENDATION

### Phase 1 — Fast Path to Market (1-2 weeks): Recall.ai

Use **Recall.ai** as meeting bot infrastructure:
1. REST API creates a bot per meeting
2. Bot joins Zoom/Meet/Teams as participant
3. Real-time audio streams via WebSocket
4. Feed audio to Sales RPG AI's existing buffer → analyzer pipeline
5. Cost: $0.50/hr per meeting (acceptable for high-ticket sales coaching)

**Why Recall.ai first:** Days to integrate, handles compliance, supports all 3 platforms. Lets you validate the product with real users before investing in infrastructure.

### Phase 2 — Own the Stack: Vexa (Self-Hosted)

Once product-market fit is validated:
1. Self-host Vexa in Docker
2. Receive real-time transcripts via WebSocket
3. Feed to LLM coaching engine
4. Cost: $50-100/month server regardless of volume
5. Full data sovereignty (important for sales conversations with PII)

### Do NOT Pursue

- **Google Meet Media API** — Developer Preview, requires all participants enrolled
- **DIY Zoom SDK** — Months of C++ for what Recall.ai already solves
- **Cluely/on-machine** — Illegal in 2-party consent jurisdictions. Prospects should NOT be secretly recorded by a sales coaching tool. This kills trust and creates liability.
- **Fireflies/Otter** — Consumer products, no raw audio API

### Integration Architecture

```
Meeting (Zoom/Meet/Teams)
    |
    v
Recall.ai Bot (Phase 1) / Vexa (Phase 2)
    | (WebSocket, 200-500ms latency)
    v
Sales RPG AI — Audio Stream Handler
    | (buffer 5-20 second windows)
    v
VadTranscriber or AssemblyAI Streaming
    |
    v
DualBufferManager → StreamingAnalyzer
    |
    v
Real-time coaching (overlay/sidebar)
```

This architecture reuses the existing Sales RPG AI pipeline — the only new component is the audio source (meeting bot replaces browser microphone).
