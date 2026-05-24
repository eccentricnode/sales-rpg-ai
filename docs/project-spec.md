# Sales AI RPG - Project Specification

> Consolidated from scattered notes, Claude conversations, and codebase analysis.
> Last updated: 2025-12-30

---

## Vision

**Sales AI RPG** is a real-time AI-powered sales coaching tool that provides live assistance during sales calls.

**The Core Concept:**
- Translucent desktop overlay (invisible to video calls)
- Listens to sales conversations in real-time
- Detects objections while the customer is still speaking
- Provides response suggestions 20-30 seconds before the objection is fully stated
- Mass Effect-style dialogue options appearing in real-time

**The Insight:** Detect at 2 seconds, customer speaks for 30 seconds = 28 seconds of preparation time.

---

## What You're Actually Building

Not just a sales tool. **A delivery mechanism for embedded expertise.**

The real asset is the Context Engine - layered sales knowledge that can be delivered multiple ways:
- Real-time coaching (live prompts during calls)
- Post-call analysis
- Training chatbot for new reps
- Script generator
- Searchable objection library
- API for other tools

---

## Context Engine Architecture

```
┌────────────────────────────────────────────────────────────┐
│                    CONTEXT ENGINE LAYERS                    │
├────────────────────────────────────────────────────────────┤
│ Layer 4: Client-Specific                                   │
│ - KubeCraft's calls, their product, their wins             │
│ - Per-customer customization                               │
│ - Status: NOT STARTED                                      │
├────────────────────────────────────────────────────────────┤
│ Layer 3: Your IP                                           │
│ - Your synthesized notes from training + experience        │
│ - The edge that makes this yours, not generic              │
│ - Status: SCATTERED (PKM, head, Claude chats)              │
├────────────────────────────────────────────────────────────┤
│ Layer 2: Training Methodology                              │
│ - Hardly Selling transcriptions (Dean's methodology)       │
│ - Needs Zettelkasten processing                            │
│ - Status: RAW TRANSCRIPTIONS, NOT PROCESSED                │
├────────────────────────────────────────────────────────────┤
│ Layer 1: General Sales Methodology                         │
│ - Objection handling, follow-up, closing patterns          │
│ - Currently: kubecraft_script.md (24KB)                    │
│ - Status: WORKING (script injection)                       │
└────────────────────────────────────────────────────────────┘
```

**Reference:** Dennis Richmond's "Context Engineering for Multi-Agent Systems" for the instruction architecture.

---

## Current Technical Architecture

### Stack
| Component | Technology | Status |
|-----------|------------|--------|
| Transcription | WhisperLive (Docker, port 9090) | Working |
| Local LLM | Phi-3.5 mini via LocalAI | Working (~5s latency) |
| Buffer System | DualBufferManager | Working |
| Analysis Pipeline | AnalysisOrchestrator (async) | Working |
| Web Server | FastAPI + WebSocket | Working |
| UI | Browser-based | Working |
| Package Manager | UV | Configured |

### Data Flow
```
Audio Input (Browser)
    ↓
WebSocket → FastAPI
    ↓
WhisperLive (transcription)
    ↓
DualBufferManager (accumulate + trigger)
    ↓
AnalysisOrchestrator (async LLM queue)
    ↓
Phi-3.5 (script location + suggestion)
    ↓
WebSocket → Browser UI
```

### Project Structure
```
sales-rpg-ai/
├── src/
│   ├── realtime/
│   │   ├── buffer_manager.py       # DualBufferManager
│   │   ├── analysis_orchestrator.py # Async LLM calls
│   │   ├── models.py               # ConversationState
│   │   └── prompts.py              # Prompt strategies
│   ├── web/
│   │   ├── app.py                  # FastAPI main
│   │   └── static/js/              # Audio capture
│   └── validation/
│       ├── db.py                   # SQLite validation
│       └── script_tester.py        # Model testing
├── knowledge_base/
│   └── kubecraft_script.md         # Sales script (24KB)
├── docs/
│   ├── mvp.md                      # Phase roadmap
│   ├── project-spec.md             # This document
│   └── product/                    # PRDs
└── docker-compose.yml              # Service orchestration
```

---

## Phase Status

| Phase | Goal | Status |
|-------|------|--------|
| Phase 1 | Proof of concept - can AI detect objections? | COMPLETE |
| Phase 2 | Real-time streaming | COMPLETE |
| Phase 3 | Context awareness (complex state machine) | CANCELLED (over-engineered) |
| Phase 4 | Minimal script-only pivot | COMPLETE |
| Phase 5 | Context Engine (this spec) | NOT STARTED |

---

## Known Issues

1. **Microphone Cutoff** (HIGH PRIORITY)
   - User's audio sometimes cuts off mid-sentence
   - Cause: WhisperLive VAD or browser chunking
   - Impact: LLM misses end of objections

2. **Latency**
   - Current: ~5 seconds round trip
   - Target (production): <150ms
   - Acceptable for MVP given streaming advantage

3. **Context Engine Disabled**
   - The "slow loop" for state analysis is stubbed out
   - Placeholder: `on_state_analysis_ready=lambda x, y: None`

---

## Objection Types

| Type | Triggers | Status |
|------|----------|--------|
| PRICE | "expensive", "budget", "cost", "afford" | Implemented |
| TIME | "think about it", "busy", "not ready", "later" | Implemented |
| DECISION_MAKER | "talk to my wife", "need approval", "discuss with team" | Implemented |
| COMPETITION | "looking at others", "competitor name", "comparing" | Implemented |
| AUTHORITY | "need approval", "ask my boss" | Planned |

---

## Business Model

### Pricing Tiers
| Version | Target | Price |
|---------|--------|-------|
| V1 (MVP) | Individual salespeople | $500-1k install |
| V2 | Sales managers | $1-2k |
| V3 | Teams (embeddings from their calls) | $2-5k |
| V4 | Enterprise | $5k+/seat |
| Consulting | Large orgs | $50k+ projects |

### SaaS Model
| Tier | Price |
|------|-------|
| Individual | $99-299/month |
| Team | $499-999/month |
| Enterprise | $5k-20k/month |

### Unit Economics (Target)
- CAC: $1,000
- LTV: $12,000+ (3+ year retention)
- LTV:CAC Ratio: 12:1
- Gross Margin: 85%+

### Cost Analysis
- Cloud APIs: $2,400/month (100 users) - too expensive + latency
- Local processing: $2K upfront + $250/month - recommended
- Break-even: 2-3 months

---

## Validation

### Your Results
- Went from 5% to 25% close rate using AI-assisted systems
- Closed $106k in 4 months of high-ticket sales

### External Validation
- Amazon Startup Advisor: "Salesforce would buy this in a heartbeat"
- Advised on patents, legal setup, business structure

### Success Metrics
| Stage | Target |
|-------|--------|
| MVP | 70%+ objection detection accuracy |
| Production | 85%+ accuracy |
| Business Impact | 15-25% win rate improvement |
| Speed (Production) | <150ms processing |

---

## Warm Leads

1. **KubeCraft** - Current employer, first install target
2. **Dean (Hardly Selling)** - His methodology as a tool
3. **Maker School community** - Sales-focused audience
4. **Friend (agreed to test)** - Early user feedback

---

## Strategic Considerations

### IP Ownership
- If built while employed at KubeCraft, they may own it legally
- Need written agreement before deploying on their data
- Build Layers 2-3 on your own time, Layer 4 with agreement

### The Sales Question
- "How do you sell something to people who are selling things?"
- First customer = proof it works
- Second customer = proof it's repeatable
- If it works for you + works at KubeCraft + team can sell = validated

---

## Gap Analysis

| Component | Status | Blocker |
|-----------|--------|---------|
| Audio capture | DONE | - |
| Transcription | DONE | - |
| Real-time pipeline | DONE | - |
| Local LLM | DONE | - |
| Context Layer 1 (general) | PARTIAL | Script injection works |
| Context Layer 2 (Hardly Selling) | BLOCKED | Need to ZK transcriptions |
| Context Layer 3 (your IP) | BLOCKED | Notes scattered |
| Context Layer 4 (client-specific) | NOT STARTED | Needs Layer 2-3 first |
| Production UI (invisible overlay) | NOT STARTED | Future |
| Speed optimization | NOT STARTED | Future |

**The blocker is the Context Engine, not the infrastructure.**

---

## Next Steps

### Immediate (Context Engine Foundation)
1. [ ] ZK the Hardly Selling transcriptions → Layer 2
2. [ ] Consolidate scattered notes → Layer 3
3. [ ] Read Dennis Richmond book, extract instruction patterns
4. [ ] Design context injection point in existing pipeline

### Short-term (Validation)
5. [ ] Test with KubeCraft (with written IP agreement)
6. [ ] User testing in live calls
7. [ ] Script refinement based on feedback

### Medium-term (Production)
8. [ ] Invisible overlay UI
9. [ ] Latency optimization (<150ms)
10. [ ] Multi-customer deployment

---

## Time Allocation (Current)

- 1-2 hours: RPG (creative flow, capture ideas, build incrementally)
- 1-2 hours: Maker School (income bridge)
- 4-6 hours: KubeCraft (survival income)

---

## References

- **Dennis Richmond**: "Context Engineering for Multi-Agent Systems"
- **Hardly Selling**: Training transcriptions (raw, needs processing)
- **kubecraft_script.md**: Current sales script (24KB)
- **PAI System**: Personal AI Infrastructure for context patterns

---

*This document consolidates context from multiple Claude.ai conversations, the existing codebase, and Austin's scattered notes. It should be the single source of truth for project direction.*
