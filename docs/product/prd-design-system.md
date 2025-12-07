# PRD: UI/UX Design System (Nord Theme)

## Status
✅ **Draft**

## 1. Problem Statement
The current MVP interface lacks visual cohesion and fails to effectively communicate critical information at a glance.
- **Readability**: Plain text logs are hard to parse during live calls.
- **Status Recognition**: Users cannot instantly distinguish between different objection types (e.g., Price vs. Time).
- **Visual Fatigue**: High-contrast or inconsistent colors cause eye strain during prolonged use.

## 2. Goals & Objectives
- **Visual Consistency**: Implement a unified design language based on the **Nord** color palette.
- **Information Hierarchy**: Use color and typography to guide the user's attention to the most important information (objections and suggestions).
- **Dark Mode Optimization**: Ensure the interface is comfortable to use in low-light environments.
- **Accessibility**: Maintain sufficient contrast ratios for text and interactive elements.

## 3. User Stories

| ID | As a... | I want to... | So that... |
|----|---------|--------------|------------|
| US.1 | Salesperson | See objections color-coded by type | I can instantly recognize the nature of the objection without reading the full text. |
| US.2 | User | Have a clear visual distinction between my speech and the prospect's | I can easily follow the conversation flow in the transcript. |
| US.3 | User | Use a dark-themed interface | I reduce eye strain during long work sessions. |
| US.4 | User | See confidence levels visualized | I know how much to trust the AI's analysis. |

## 4. Functional Requirements

### 4.1 Theming Engine
- **FR 4.1.1**: The application MUST use CSS variables for all color definitions.
- **FR 4.1.2**: The base theme MUST be "Nord" (Dark Mode).

### 4.2 Component Styling
- **FR 4.2.1**: **Objection Badges** must use specific colors for each type:
    - Price: Red (`#BF616A`)
    - Time: Orange (`#D08770`)
    - Decision: Yellow (`#EBCB8B`)
    - Other: Purple (`#B48EAD`)
- **FR 4.2.2**: **Transcript Lines** must have a colored left border indicating the speaker:
    - Salesperson: Blue (`#81A1C1`)
    - Prospect: Orange (`#D08770`)
- **FR 4.2.3**: **Suggestion Cards** must have a hover state that highlights the border color.

### 4.3 Layout & Typography
- **FR 4.3.1**: The interface must use a sans-serif system font stack.
- **FR 4.3.2**: Text colors must follow the hierarchy: Primary (`#ECEFF4`), Secondary (`#D8DEE9`), Muted (`#E5E9F0`).

## 5. Success Metrics
- **User Feedback**: Positive sentiment regarding readability and aesthetics.
- **Reaction Time**: Reduced time for users to identify objection types (measured via user testing).
- **Consistency**: 100% of UI components utilize the defined CSS variables.

## 6. Implementation Plan
1.  **Define Variables**: Create `styles.css` with the root CSS variables.
2.  **Refactor Components**: Update existing HTML templates to use the new classes (`objection-badge`, `transcript-line`, etc.).
3.  **Verify Contrast**: Check all text/background combinations for WCAG AA compliance.
