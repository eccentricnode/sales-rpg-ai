# MVP Pivot: The "Script Context" Hypothesis

**Date:** December 15, 2025
**Status:** In Progress

## 1. The Pivot Goal

We are temporarily pausing the original Phase 4 roadmap (Hybrid Intelligence) to validate a critical hypothesis:

> **Hypothesis:** A small local model (Phi-3.5) equipped with the specific **Sales Script** as context can achieve performance parity with a large cloud model (Claude/GPT-4) for objection detection and stage tracking.

### Why this matters
If this hypothesis is true, we can:
1.  **Eliminate Cloud Costs**: Run entirely offline without expensive API calls.
2.  **Reduce Latency**: Local inference is significantly faster than round-tripping to the cloud.
3.  **Simplify Architecture**: No need for complex "Hybrid Escalation" logic if the local model is "smart enough" when given the right cheat sheet.

## 2. The Validation Plan

To prove this, we are building a dedicated **Validation Loop**:

1.  **Input**: Real call transcripts (or synthetic test cases).
2.  **Process**: Feed them into LocalAI with the Sales Script injected into the system prompt.
3.  **Output**: Capture the AI's analysis (Stage, Objections, BANT).
4.  **Eval**: Compare against "Ground Truth" (what a human/Claude would say).

### The Roadmap

#### ✅ Task 1: Database Foundation (Completed)
We need a place to store our test data.
- **Deliverables**:
    - [x] SQL Schema for `calls`, `expected_outputs`, `test_runs`, `test_results`.
    - [x] Python `ValidationDB` class for CRUD operations.
    - [x] Unit tests to verify data storage.
- **Outcome**: We have a local SQLite database (scalable to Supabase) ready to log our experiments.

#### ✅ Task 2: Test Framework (Completed)
We need a script to run the tests.
- **Deliverables**:
    - [x] `ScriptManager` to load and format the sales script.
    - [x] `TestRunner` to iterate through transcripts and query the AI.
    - [x] Integration with `ValidationDB` to log raw outputs.
    - [x] **Minimal Mode**: A simplified "Script Only" test mode that bypasses complex BANT logic.

#### ⏳ Task 3: Evaluation System (Pending)
We need a way to score the results.
- **Deliverables**:
    - [ ] "Ground Truth" generator (manual entry or Claude-assisted).
    - [ ] Scoring logic (Did it catch the objection? Did it identify the right stage?).
    - [ ] Reporting dashboard (Pass/Fail rates).

## 3. Current Status

**Phase**: Task 2 Complete.

**Key Finding (Dec 16, 2025):**
The "Minimal Script-Only" approach (`script_tester.py minimal`) works exceptionally well. By stripping away the complex BANT/Profile extraction and focusing purely on **Script Location + Key Points + Suggestion**, the local model (Phi-3.5) provides highly accurate, context-aware responses.

**Decision:**
We will prioritize this "Script-First" core functionality over the BANT/Profile features for the immediate MVP. The complex state management is a "future problem"; the core value is navigating the script effectively.

We have the infrastructure to *store* results. Now we need to build the engine to *generate* them.
