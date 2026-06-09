# PRD: BANT Extraction & Dashboard (Phase 3)

## 1. Problem Statement
Sales reps often forget to ask critical qualifying questions (Budget, Authority, Need, Timeline). Even when they do ask, they might forget the answers by the end of the call.

Currently, the AI detects *objections* (negatives) but ignores *qualifications* (positives).

## 2. Goals
To actively listen for and extract **BANT** criteria, displaying them in a "Live Checklist" on the UI.

## 3. User Stories

| ID | As a... | I want to... | So that... |
|----|---------|--------------|------------|
| 3.1 | Sales Rep | See a checklist of BANT items | I know what I still need to ask. |
| 3.2 | Sales Rep | See the extracted values (e.g., "$50k") | I don't have to rely on my memory. |
| 3.3 | Sales Rep | Be alerted if I try to close without BANT | I don't waste time pitching to an unqualified lead. |

## 4. Functional Requirements

### 4.1 Extraction Logic
The "Slow Loop" analyzer (see Conversation State PRD) shall specifically look for:

- **Budget**: Currency amounts, "too expensive", "within budget".
- **Authority**: "I need to ask...", "I sign the checks", "Committee".
- **Need**: "We struggle with...", "We are looking for...".
- **Timeline**: "By Q4", "Next month", "ASAP".

### 4.2 UI Updates
The Web UI (`index.html`) shall be updated to include a **"Qualification Panel"**:
- A sidebar or top bar showing the 4 BANT icons.
- **Status Indicators**:
    - ⚪ Grey: Unknown
    - 🟢 Green: Qualified (Value extracted)
    - 🔴 Red: Disqualified (e.g., "No budget")

### 4.3 "Missing Info" Alerts
If the call enters the **Closing** stage and BANT items are still unknown, the system shall generate a "Coaching Tip" (distinct from an objection) prompting the rep to ask the missing question.

*Example:*
> "⚠️ You are closing, but haven't established the Decision Maker yet. Ask: 'Who else needs to sign off on this?'"

## 5. Technical Approach

### 5.1 Data Structure
Extend the `AnalysisResult` or create a new `StateUpdate` event type for the WebSocket.

```json
{
  "type": "state_update",
  "bant": {
    "budget": { "status": "qualified", "value": "$10k/mo" },
    "authority": { "status": "unknown", "value": null },
    ...
  }
}
```

### 5.2 Frontend
- New CSS class `.bant-panel` in `styles.css`.
- New JS handler `handleStateUpdate(data)` in `audio-client.js`.

## 6. Success Metrics
- **Extraction Rate**: % of calls where at least 3/4 BANT items are correctly identified.
- **UI Engagement**: Users looking at the BANT panel (eye tracking proxy or survey).
