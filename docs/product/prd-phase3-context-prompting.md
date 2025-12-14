# PRD: Context-Aware Prompting (Phase 3)

## 1. Problem Statement
Even if we know the "Stage" of the call (from the Conversation State Manager), the current LLM prompts are static. They use a "one-size-fits-all" instruction set that forces the model to look for generic objections.

We need a way to dynamically swap or modify the system prompt based on the active context to improve relevance and reduce hallucinations.

## 2. Goals
To implement a **Dynamic Prompt Engine** that assembles the system prompt at runtime based on the current conversation state.

## 3. Functional Requirements

### 3.1 Prompt Templates
The system shall support modular prompt templates for different scenarios:

- **`base_prompt`**: The core JSON formatting rules and persona definition.
- **`stage_instructions`**: Specific rules for the current stage (e.g., "In Discovery, listen for pain points").
- **`bant_context`**: A summary of what we already know (e.g., "Budget: $50k, Timeline: Q4").

### 3.2 Dynamic Assembly
Before every analysis request, the `AnalysisOrchestrator` shall construct the final prompt:

```text
[Base Prompt]
+
[Current Stage Instructions]
+
[Known BANT Info]
+
[Transcript Segment]
```

### 3.3 Stage-Specific Rules

| Stage | Instruction Focus | Sensitivity Adjustments |
|-------|-------------------|-------------------------|
| **Opening** | Rapport, Agenda | Ignore "Price" mentions (usually just curiosity). |
| **Discovery** | Pain Points, Qualification | High sensitivity to "Current Solution" complaints. |
| **Presentation** | Feature Mapping | Listen for "How does X work?" (Buying signals). |
| **Closing** | Commitment, Negotiation | High sensitivity to "Price" and "Timing" objections. |

## 4. Technical Implementation

### 4.1 `PromptManager` Class
A new class responsible for:
1.  Loading prompt templates from YAML/JSON files.
2.  Accepting a `ConversationState` object.
3.  Returning the fully formatted system string.

### 4.2 Configuration
Prompt templates should be stored in `src/realtime/prompts/` as separate files, allowing non-engineers (Product/Sales Ops) to tweak the coaching advice without touching code.

## 5. Success Metrics
- **Relevance Score**: Increase in "Helpful" ratings for suggestions.
- **False Positive Reduction**: Decrease in "Price" objections flagged during the Opening phase.
