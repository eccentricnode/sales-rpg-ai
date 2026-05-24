# Sales AI RPG — Design System

## Overview
This document outlines the visual design system for the Sales AI RPG application. The design is built upon the **Nord** color palette, offering a clean, flat, and cool-toned aesthetic optimized for dark mode usage.

## 1. Color Palette (Nord Theme)

We utilize CSS variables to maintain consistency and allow for easy theming updates.

### Base Colors
| Variable | Hex | Nord ID | Usage |
|----------|-----|---------|-------|
| `--bg-primary` | `#2E3440` | nord0 | Main page background |
| `--bg-secondary` | `#3B4252` | nord1 | Cards, panels, sidebars |
| `--bg-elevated` | `#434C5E` | nord2 | Hover states, modals, inputs |
| `--bg-highlight` | `#4C566A` | nord3 | Active states, borders |

### Typography Colors
| Variable | Hex | Nord ID | Usage |
|----------|-----|---------|-------|
| `--text-primary` | `#ECEFF4` | nord6 | Headings, primary content |
| `--text-secondary` | `#D8DEE9` | nord4 | Body text, secondary info |
| `--text-muted` | `#E5E9F0` | nord5 | Placeholders, hints, metadata |

### Accent & Actions
| Variable | Hex | Nord ID | Usage |
|----------|-----|---------|-------|
| `--accent-primary` | `#88C0D0` | nord8 | Primary buttons, links, focus rings |
| `--accent-hover` | `#8FBCBB` | nord7 | Hover states for interactive elements |
| `--accent-deep` | `#5E81AC` | nord10 | Active/Pressed states |

### Semantic Status Colors
Used primarily for objection detection and system status.

| Variable | Hex | Nord ID | Meaning |
|----------|-----|---------|---------|
| `--status-price` | `#BF616A` | nord11 | Price Objections / Errors |
| `--status-time` | `#D08770` | nord12 | Time Objections / Warnings |
| `--status-decision` | `#EBCB8B` | nord13 | Decision Maker Objections |
| `--status-success` | `#A3BE8C` | nord14 | Success / Handled / Low Risk |
| `--status-other` | `#B48EAD` | nord15 | Other Objections |

### Transcript Speaker Colors
| Variable | Hex | Nord ID | Speaker |
|----------|-----|---------|---------|
| `--speaker-salesperson` | `#81A1C1` | nord9 | You (The User) |
| `--speaker-prospect` | `#D08770` | nord12 | The Prospect (Client) |

---

## 2. CSS Implementation

Copy the following into the root stylesheet (e.g., `styles.css`).

```css
:root {
  /* Backgrounds */
  --bg-primary: #2E3440;
  --bg-secondary: #3B4252;
  --bg-elevated: #434C5E;
  --bg-highlight: #4C566A;

  /* Text */
  --text-primary: #ECEFF4;
  --text-secondary: #D8DEE9;
  --text-muted: #E5E9F0;

  /* Accent */
  --accent-primary: #88C0D0;
  --accent-hover: #8FBCBB;
  --accent-deep: #5E81AC;

  /* Status */
  --status-price: #BF616A;
  --status-time: #D08770;
  --status-decision: #EBCB8B;
  --status-success: #A3BE8C;
  --status-other: #B48EAD;

  /* Speakers */
  --speaker-salesperson: #81A1C1;
  --speaker-prospect: #D08770;
}

body {
  background-color: var(--bg-primary);
  color: var(--text-primary);
  font-family: system-ui, -apple-system, sans-serif;
}
```

---

## 3. Component Library

### 3.1 Objection Badges
Small indicators used to tag detected objections.

```css
.objection-badge {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
}

.objection-price {
  background: rgba(191, 97, 106, 0.2);
  color: var(--status-price);
  border: 1px solid var(--status-price);
}

.objection-time {
  background: rgba(208, 135, 112, 0.2);
  color: var(--status-time);
  border: 1px solid var(--status-time);
}

.objection-decision {
  background: rgba(235, 203, 139, 0.2);
  color: var(--status-decision);
  border: 1px solid var(--status-decision);
}

.objection-other {
  background: rgba(180, 142, 173, 0.2);
  color: var(--status-other);
  border: 1px solid var(--status-other);
}
```

### 3.2 Transcript Lines
Visual distinction between speakers in the live transcript log.

```css
.transcript-line {
  padding: 8px 12px;
  margin: 4px 0;
  border-radius: 4px;
  border-left: 3px solid transparent;
  background: var(--bg-secondary);
}

.transcript-salesperson {
  background: rgba(129, 161, 193, 0.1);
  border-left-color: var(--speaker-salesperson);
}

.transcript-prospect {
  background: rgba(208, 135, 112, 0.1);
  border-left-color: var(--speaker-prospect);
}
```

### 3.3 Suggestion Cards
Interactive cards displaying AI-generated responses.

```css
.suggestion-card {
  background: var(--bg-secondary);
  border: 1px solid var(--bg-highlight);
  border-radius: 8px;
  padding: 16px;
  transition: all 0.2s ease;
  cursor: pointer;
}

.suggestion-card:hover {
  background: var(--bg-elevated);
  border-color: var(--accent-primary);
  transform: translateY(-1px);
}

.suggestion-number {
  color: var(--accent-primary);
  font-weight: 700;
  margin-right: 8px;
}
```

### 3.4 Confidence Indicators
Visual cues for the AI's certainty level.

```css
.confidence-high { color: var(--status-success); }
.confidence-medium { color: var(--status-decision); }
.confidence-low { color: var(--status-price); }
```

---

## 4. Example Layout

```html
<div class="objection-panel" style="background: var(--bg-secondary); border-radius: 8px; padding: 16px;">
  
  <!-- Header -->
  <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
    <span class="objection-badge objection-price">PRICE</span>
    <span class="confidence-high">● HIGH CONFIDENCE</span>
  </div>
  
  <!-- Quote -->
  <p style="color: var(--text-secondary); margin-bottom: 16px; font-style: italic;">
    "That sounds a bit expensive for what we're looking at..."
  </p>
  
  <!-- Suggestions -->
  <div class="suggestion-card">
    <span class="suggestion-number">1.</span>
    <span style="color: var(--text-primary);">What specific aspect of the pricing concerns you most?</span>
  </div>
  
</div>
```
