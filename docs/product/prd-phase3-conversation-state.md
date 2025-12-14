# PRD: Conversation State Manager (Phase 3)

## 1. Problem Statement
Currently, the Sales AI analyzes every sentence in isolation. It treats a "price objection" in the first minute of a call (likely a disqualifier) exactly the same as a "price objection" in the closing minute (a negotiation signal).

This "stateless" behavior leads to:
1.  **Context-Blind Suggestions**: Suggesting deep negotiation tactics when the user is just saying hello.
2.  **Repetitive Advice**: Flagging the same issue multiple times without realizing it was already addressed.
3.  **Missed Strategic Context**: Failing to recognize when a call has moved from "Discovery" to "Closing."

## 2. Goals
To implement a **Conversation State Manager** that tracks the macro-level progress of the sales call.

### Key Objectives
- **Stage Detection**: Automatically classify the call into stages (Opening, Discovery, Pitch, Objection Handling, Closing).
- **Contextual Sensitivity**: Adjust objection detection thresholds based on the current stage.
- **Information Extraction**: Track key data points (BANT - Budget, Authority, Need, Timeline) as they are revealed.

## 3. User Stories

| ID | As a... | I want to... | So that... |
|----|---------|--------------|------------|
| 3.1 | Sales Rep | See what "Stage" the AI thinks I'm in | I know if the AI is following the conversation flow correctly. |
| 3.2 | Sales Rep | Receive stage-appropriate advice | I don't get closing tactics during the discovery phase. |
| 3.3 | Sales Manager | See a summary of stages after the call | I can analyze where my reps are spending the most time. |

## 4. Functional Requirements

### 4.1 Stage Detection Logic
The system shall classify the conversation into one of the following stages based on the transcript history:

1.  **Opening (0-5 mins)**: Greetings, agenda setting, rapport building.
2.  **Discovery**: Question asking, pain point identification, qualification.
3.  **Presentation**: Solution mapping, demoing features, value proposition.
4.  **Objection Handling**: Addressing specific concerns raised by the prospect.
5.  **Closing**: Discussing pricing, next steps, contracts, or implementation.

### 4.2 Contextual Prompting
The `AnalysisOrchestrator` shall inject the `current_stage` into the system prompt for the LLM.

*Example Prompt Injection:*
> "Current Call Stage: DISCOVERY. Focus on uncovering pain points. Do not suggest closing tactics yet."

### 4.3 BANT Tracking (Stretch Goal)
The system shall attempt to extract and store:
- **Budget**: Monetary constraints mentioned.
- **Authority**: Decision-making power (e.g., "I need to ask my boss").
- **Need**: Core problem statement.
- **Timeline**: When they need the solution.

## 5. Technical Approach (Lightweight)

Instead of a heavy RAG/Vector DB approach, we will use **Periodic Summary Prompts**.

1.  **The "Slow Loop"**: Every 60 seconds (or every 10 transcript segments), a separate LLM call is made.
2.  **The Prompt**: "Analyze the last N minutes of transcript. Classify the sales stage. Extract any new BANT info."
3.  **State Update**: The result updates a global `ConversationState` object.
4.  **The "Fast Loop"**: The real-time objection detector reads from `ConversationState` to adjust its behavior.

## 6. Success Metrics
- **Stage Accuracy**: >80% agreement with human labeling of call stages.
- **Latency Impact**: Zero impact on the "Fast Loop" (objection detection) latency.
- **User Feedback**: "The advice feels more relevant to where I am in the call."
