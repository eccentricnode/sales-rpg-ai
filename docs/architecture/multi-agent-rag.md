# Multi-Agent RAG Architecture

> The intelligence layer that makes Sales RPG suggestions world-class.
> Last updated: 2026-01-19

---

## Overview

The RAG (Retrieval-Augmented Generation) system is the core differentiator. Everything else is implementation detail. This document defines two tiers:

1. **Core RAG** - Shippable, effective, $20/month tier
2. **Agent Intelligence Layer** - Enterprise, best-in-class, premium tier

---

## Two RAG Targets

The system needs to understand two participants differently:

| Target | Purpose | What It Pulls |
|--------|---------|---------------|
| **Buyer RAG** | What do they need to hear? | Objection patterns, response templates, emotional triggers |
| **Salesman RAG** | How should they say it? | Style, tone, what's worked before, script sections, mindset cues |

**Key Insight:** The buyer analysis is simpler (pattern matching). The salesman analysis is gold (style + history + guidance).

---

## Tier 1: Core RAG System ($20/month)

### Architecture

```
Customer says X
       ↓
┌─────────────────────────────┐
│      EMBEDDING + SEARCH     │
│  Query: What was just said  │
│  Index: Script + Responses  │
└─────────────────────────────┘
       ↓
┌─────────────────────────────┐
│      CONTEXT INJECTION      │
│  Top 3-5 relevant chunks    │
│  + Conversation summary     │
└─────────────────────────────┘
       ↓
┌─────────────────────────────┐
│      SINGLE LLM CALL        │
│  "Given this context,       │
│   what should rep say?"     │
└─────────────────────────────┘
       ↓
Response suggestion
```

### What It Does

1. **Embed** customer's statement
2. **Search** knowledge base for relevant context
3. **Inject** top matches into prompt
4. **Generate** single response suggestion

### Knowledge Base Contents

- Sales script (structured by stage)
- Objection response templates
- Successful call patterns
- Product/service information

### Why It Works

- Fast (~1-2s latency)
- Simple to maintain
- Good enough for 80% of situations
- Shippable NOW

---

## Tier 2: Agent Intelligence Layer (Enterprise)

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   ORCHESTRATOR AGENT                     │
│     Analyzes all inputs, makes final decision           │
│     "What should the rep actually say right now?"       │
└─────────────────────────────────────────────────────────┘
        ↑              ↑              ↑
┌───────────┐  ┌───────────┐  ┌───────────┐
│ SUMMARIZER│  │ RETRIEVER │  │  READINESS│
│   AGENT   │  │   AGENT   │  │   AGENT   │
│           │  │   (RAG)   │  │           │
│ "Convo    │  │ "Relevant │  │ "Ready to │
│  so far   │  │  context  │  │  move on? │
│  is..."   │  │  is..."   │  │  Or dig   │
│           │  │           │  │  deeper?" │
└───────────┘  └───────────┘  └───────────┘
```

### Agent Responsibilities

#### 1. Summarizer Agent
- Compresses conversation history
- Tracks key information revealed
- Notes emotional state of buyer
- Output: "Here's what we know so far"

#### 2. Retriever Agent (RAG)
- Embeds current conversation state
- Searches multiple indexes:
  - Script sections
  - Historical successful responses
  - Salesman's personal style patterns
  - Buyer persona patterns
- Output: "Here's the relevant context"

#### 3. Readiness Agent
- Evaluates: "Do we have enough information?"
- Checks: "Is the buyer ready to move forward?"
- Decides: "Ask deeper questions or progress?"
- Output: "Go deeper on X" or "Ready to move to Y stage"

#### 4. Orchestrator Agent
- Receives inputs from all three agents
- Applies selling philosophy:
  - Be patient, let buyer finish
  - Acknowledge → Feel heard → Show we solve this
  - Ask "why" and uncover core issues
- Output: Final response suggestion with tone guidance

### Selling Philosophy Encoded

The agent system encodes this approach:

1. **Patience** - Wait for buyer to finish before responding
2. **Acknowledgment** - First, show you heard them
3. **Validation** - Make them feel understood
4. **Connection** - Show that what they describe is what we solve
5. **Depth** - Ask questions that uncover the real "why"
6. **Guidance** - Lead them to a better outcome, don't push

**Two modes:**
- "Selling to get the sale" - transactional, aggressive
- "Selling to guide the buyer" - consultative, trust-building

The agent system supports both but optimizes for guidance.

---

## Knowledge Base Structure

### Layer 1: General Sales Methodology
- Objection handling patterns
- Follow-up sequences
- Closing techniques
- Stage definitions

### Layer 2: Training Methodology (Hardly Selling)
- Dean's specific techniques
- Processed transcriptions
- Zettelkasten-style atomic notes

### Layer 3: Personal IP
- Austin's synthesized insights
- What's worked in real calls
- Personal style patterns

### Layer 4: Client-Specific
- Customer's product/service
- Their successful call patterns
- Their team's style preferences

---

## Embedding Strategy

### Chunking Approach
- Semantic chunking (by concept, not character count)
- Overlapping windows for context preservation
- Metadata tags: stage, objection_type, tone, outcome

### Embedding Model Options
| Model | Dimensions | Speed | Quality |
|-------|------------|-------|---------|
| OpenAI text-embedding-3-small | 1536 | Fast | Good |
| OpenAI text-embedding-3-large | 3072 | Medium | Better |
| Local (sentence-transformers) | 384-768 | Fast | Good enough |

### Vector Store
- Development: ChromaDB (local, simple)
- Production: Pinecone or Qdrant (scalable)

---

## Implementation Phases

### Phase 1: Core RAG (Ship This First)
- [ ] Set up ChromaDB
- [ ] Chunk and embed sales script
- [ ] Implement retrieval in existing pipeline
- [ ] Test: Does retrieval improve suggestions?

### Phase 2: Enhanced Retrieval
- [ ] Add historical call patterns
- [ ] Implement conversation summarization
- [ ] Add salesman style detection
- [ ] Test: Measurably better suggestions?

### Phase 3: Multi-Agent (Enterprise)
- [ ] Implement Summarizer Agent
- [ ] Implement Retriever Agent
- [ ] Implement Readiness Agent
- [ ] Implement Orchestrator Agent
- [ ] Semantic blueprints for each agent
- [ ] Test: Best-in-class quality?

---

## Pricing Tiers

| Tier | Features | Price |
|------|----------|-------|
| **Starter** | Core RAG, basic retrieval | $20/month |
| **Pro** | Enhanced retrieval, style matching | $99/month |
| **Enterprise** | Full agent system, custom training | $299+/month |

---

## Connection to Existing Infrastructure

### Current Pipeline
```
Audio → WhisperLive → DualBufferManager → LLM → Suggestion
```

### With Core RAG
```
Audio → WhisperLive → DualBufferManager → RAG → LLM → Suggestion
                                           ↑
                                    Vector search
```

### With Agent Layer
```
Audio → WhisperLive → DualBufferManager → Agent System → Suggestion
                                               ↑
                                    Summarizer + Retriever + Readiness
                                               ↓
                                         Orchestrator
```

---

## Success Metrics

| Metric | Core RAG Target | Agent Layer Target |
|--------|-----------------|-------------------|
| Suggestion relevance | 70% | 90% |
| Response latency | <2s | <5s |
| User satisfaction | 7/10 | 9/10 |
| Close rate improvement | +10% | +25% |

---

## References

- Dennis Richmond: "Context Engineering for Multi-Agent Systems"
- Existing project-spec.md for business context
- ContentEngine semantic blueprints for pattern

---

*This is the ONE thing. Everything else is implementation detail.*
