# Behavioral Contract: Context Engine Layer 2

**Files:** `src/realtime/analysis_orchestrator.py`, `src/realtime/prompts.py`, `src/rag/*`
**Purpose:** Load Hardly Selling methodology as a retrievable second context layer alongside the sales script.

## Preconditions

- `knowledge_base/kubecraft_script.md` exists and remains the primary sales script source.
- `knowledge_base/hardly_selling_methodology.md` or equivalent methodology source exists.
- `USE_RAG=true` enables retrieval-augmented prompt construction.
- The retrieval stack uses `EmbeddingStore`, `StageDetector`, and `ScriptRetriever`.

## Postconditions

- The methodology source is indexed as a separate retrievable source, not only embedded in static prompt text.
- Retrieval can return both script and methodology chunks for the same utterance.
- Call phase or stage influences which methodology sections are selected.
- Coaching recommendations reference named Hardly Selling techniques when methodology context is relevant.
- Missing methodology files degrade with an explicit warning or disabled Layer 2 state, not silent fake success.

## Required Probe Evidence

- Probe showing `ScriptRetriever` queries at least two sources when Layer 2 is enabled.
- Probe showing a phase-specific query retrieves methodology content for that phase.
- Probe showing recommendation prompt construction includes source-aware methodology context.
- Test confirming the system still works when Layer 2 is disabled.

## Edge Cases

- Duplicate content across script and methodology should be deduplicated or source-labeled.
- Retrieval failures in the methodology source must not prevent script-only coaching.
- Source metadata should be preserved when downstream code needs to explain why a suggestion was selected.
