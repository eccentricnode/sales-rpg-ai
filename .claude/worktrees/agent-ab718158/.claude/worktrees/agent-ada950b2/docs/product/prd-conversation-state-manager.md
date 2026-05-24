# PRD: Conversation State & Phase Detection

## Status
Draft

## Problem
The current system detects objections in isolation. It lacks "macro-awareness" of the conversation.
- **Context Blindness**: It treats a price question in the "Introduction" (likely a disqualifier) the same as in the "Closing" (a negotiation signal).
- **Statelessness**: It doesn't remember if the user already established the budget 5 minutes ago.

## Solution
Implement a `ConversationStateManager` that runs in parallel to the objection detector to track the "Big Picture."

## Core Components

### 1. The Phases
The system will classify the call into one of 5 states:
1.  **Introduction**: Building rapport, setting agenda.
2.  **Discovery**: Asking questions, understanding pain points.
3.  **Pitch**: Presenting the solution/product.
4.  **Objection Handling**: Addressing concerns.
5.  **Closing**: Asking for the business/next steps.

### 2. The State Manager
A background worker that analyzes the transcript every **45-60 seconds**.

**Inputs:**
- Full conversation history (or large sliding window).

**Outputs:**
- `current_phase`: (Enum)
- `summary`: (String) 2-3 sentence summary of what has happened so far.
- `extracted_info`: (JSON) Budget, Authority, Need, Timeline (BANT).

## Architecture

```mermaid
flowchart TD
    A[Transcript Stream] -->|Fast Loop (15s)| B[Objection Detector]
    A -->|Slow Loop (60s)| C[State Manager]
    
    C -->|Updates| D[Shared State]
    D -->|Context| B
    D -->|Display| E[UI Dashboard]
```

## Integration
The `ObjectionAnalyzer` will now receive the `current_phase` as context.
- **If Phase == Discovery**: Be less sensitive to "Price" mentions (it's just info gathering).
- **If Phase == Closing**: Be HIGHLY sensitive to "Think about it" (stall tactic).

## Implementation Plan
1.  Create `ConversationStateManager` class.
2.  Define `StateAnalysisPrompt` for the LLM.
3.  Run it in a separate thread in `AnalysisOrchestrator`.
4.  Expose state to the UI.
