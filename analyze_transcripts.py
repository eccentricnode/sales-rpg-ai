#!/usr/bin/env python3
"""
Transcript Analysis Pipeline
Processes all 133 Gemini call notes from the zip, extracts patterns,
and builds the playbook insights document.

Priority: Dec/Jan closes first, then all others.
"""

import json
import os
import re
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path

from docx import Document
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
ZIP_PATH = Path("/home/ajohnson/Downloads/drive-download-20260218T093050Z-1-001.zip")
EXTRACT_DIR = Path("/tmp/sales_transcripts")
OUTPUT_DIR = Path("knowledge_base")
FULL_ANALYSIS_PATH = OUTPUT_DIR / "full_transcript_analysis.json"
INSIGHTS_PATH = OUTPUT_DIR / "closing_patterns.md"

# GitHub gpt-4o-mini
client = OpenAI(
    base_url="https://models.github.ai/inference",
    api_key=os.getenv("GITHUB_TOKEN"),
)
MODEL = os.getenv("GITHUB_MODEL", "gpt-4o-mini")

# ── Known closes from transcript_analysis.json (to seed outcome data) ─────────
KNOWN_CLOSES = {
    "Derrick Gill": {"outcome": "close", "revenue": "$3500", "date": "2025-11-06"},
    "Esteban Masegosa": {"outcome": "close", "revenue": "$3500", "date": "2025-11-03"},
    "Fernando Souza": {"outcome": "close", "revenue": "$3440", "date": "2026-01-09"},
    "Jeremy Farr": {"outcome": "close", "revenue": "$4000", "date": "2025-12-29"},
    "Jeroen Hammega": {"outcome": "close", "revenue": "$3500", "date": "2025-10-26"},
    "Joshua Danielson": {"outcome": "close", "revenue": "$4000", "date": "2026-01-08"},
    "Matus Demko": {"outcome": "close", "revenue": "$3500", "date": "2025-12-01"},
    "Ryan Stush": {"outcome": "close", "revenue": "$3500", "date": "2025-12-05"},
    "Scott Medway": {"outcome": "close", "revenue": "$3500", "date": "2025-12-12"},
}

PRIORITY_MONTHS = {"2025-12", "2026-01"}  # Dec/Jan priority


# ── Helpers ───────────────────────────────────────────────────────────────────

def extract_zip():
    EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
    if len(list(EXTRACT_DIR.glob("*.docx"))) == 0:
        with zipfile.ZipFile(ZIP_PATH) as zf:
            zf.extractall(EXTRACT_DIR)
    files = list(EXTRACT_DIR.glob("*.docx"))
    print(f"Found {len(files)} transcript files")
    return files


def parse_date_from_filename(filename: str) -> str:
    """Extract YYYY-MM date from filename."""
    m = re.search(r"(\d{4})_(\d{2})_(\d{2})", filename)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return "unknown"


def extract_prospect_name(filename: str) -> str:
    """Extract prospect name from Gemini filename."""
    name = filename.replace(".docx", "")
    # Remove date suffix
    name = re.sub(r"\s*-\s*\d{4}_\d{2}_\d{2}.*", "", name)
    # Remove "and Austin Johnson" suffix
    name = re.sub(r"\s*(and|x|X)\s*Austin Johnson.*", "", name, flags=re.IGNORECASE)
    # Remove common prefixes
    name = re.sub(r"^(Qualification Call With |Qualification Call - |1_1 KubeCraft Strategy Session )", "", name)
    return name.strip()


def read_docx_text(path: Path) -> tuple[str, str]:
    """Read docx, return (notes_section, transcript_section)."""
    doc = Document(path)
    full_text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())

    # Split at transcript marker
    if "📖 Transcript" in full_text or "Transcript" in full_text:
        parts = re.split(r"📖\s*Transcript|^Transcript$", full_text, maxsplit=1, flags=re.MULTILINE)
        notes = parts[0].strip()
        transcript = parts[1].strip() if len(parts) > 1 else ""
    else:
        notes = full_text
        transcript = ""

    return notes, transcript


def analyze_call(prospect_name: str, date: str, notes: str, transcript: str, is_close: bool) -> dict:
    """Send call to LLM for structured analysis."""

    # For closes: include more transcript for question mapping
    # For others: notes summary is enough
    if is_close and transcript:
        # Include up to 6000 chars of transcript for detailed mapping
        content = f"NOTES:\n{notes[:3000]}\n\nTRANSCRIPT EXCERPT:\n{transcript[:6000]}"
    else:
        content = f"NOTES:\n{notes[:4000]}"

    system = """You are a sales call analyst. Analyze this KubeCraft DevOps coaching sales call.

Extract a structured JSON with these exact fields:

{
  "buyer_archetype": "pain_buyer|vision_buyer|convenience_buyer|crisis_buyer|tire_kicker|unclear",
  "archetype_confidence": "high|medium|low",
  "archetype_signals": ["signal 1", "signal 2"],
  "outcome": "close|loss|unknown",
  "revenue": "$X or null",
  "call_duration": "short (<30min)|medium (30-50min)|long (>50min)",
  "script_phases_completed": ["Open", "Set Agenda", "Why Here", "Pain", "Goals", "Blocker", "NOW Tie-Down", "Pre-Pitch", "Pitch", "Temp Check", "Close"],
  "discovery_questions_used": [
    {"question": "exact question text", "timestamp": "HH:MM:SS or null", "prospect_response_summary": "what they said"}
  ],
  "key_turning_point": "the moment that determined the outcome",
  "close_trigger": "what specifically caused the close (if closed)",
  "loss_reason": "why it didn't close (if lost)",
  "objections_raised": ["objection 1"],
  "objections_handled_well": ["technique 1"],
  "objections_mishandled": ["mistake 1"],
  "pain_indicators": ["exact prospect words showing pain/urgency"],
  "archetype_detection_moment": "timestamp or phase when archetype became clear",
  "call_notes": "2-3 sentence summary of key learnings"
}

Be precise. Extract exact question text from the transcript. Timestamps should be from the transcript (format HH:MM:SS).
Return ONLY valid JSON."""

    user = f"Prospect: {prospect_name}\nDate: {date}\n\n{content}"

    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=1200,
            temperature=0.1,
        )
        raw = resp.choices[0].message.content or ""
        # Strip markdown fences
        raw = re.sub(r"```json\s*", "", raw)
        raw = re.sub(r"```\s*", "", raw)
        result = json.loads(raw.strip())
        result["prospect_name"] = prospect_name
        result["date"] = date
        return result
    except Exception as e:
        return {
            "prospect_name": prospect_name,
            "date": date,
            "error": str(e),
            "outcome": "unknown",
        }


def sort_key(path: Path) -> tuple:
    """Sort: closes first, then by date descending (Dec/Jan priority)."""
    name = extract_prospect_name(path.name)
    date = parse_date_from_filename(path.name)
    is_close = any(k.lower() in name.lower() for k in KNOWN_CLOSES.keys())
    month = date[:7]
    is_priority = month in PRIORITY_MONTHS
    # Sort: priority closes first, then priority others, then rest
    tier = 0 if (is_close and is_priority) else 1 if is_close else 2 if is_priority else 3
    return (tier, date)


def build_insights_doc(analyses: list[dict]) -> str:
    """Synthesize all analyses into the playbook insights markdown."""
    closes = [a for a in analyses if a.get("outcome") == "close" and "error" not in a]
    losses = [a for a in analyses if a.get("outcome") == "loss" and "error" not in a]

    # Archetype close rates
    archetype_stats: dict[str, dict] = {}
    for a in analyses:
        if "error" in a:
            continue
        arch = a.get("buyer_archetype", "unclear")
        if arch not in archetype_stats:
            archetype_stats[arch] = {"closes": 0, "total": 0, "revenue": 0}
        archetype_stats[arch]["total"] += 1
        if a.get("outcome") == "close":
            archetype_stats[arch]["closes"] += 1
            rev = a.get("revenue") or ""
            rev_num = int(re.sub(r"[^\d]", "", rev)) if rev else 0
            archetype_stats[arch]["revenue"] += rev_num

    # All discovery questions from closes
    close_questions: list[dict] = []
    for a in closes:
        for q in a.get("discovery_questions_used", []):
            close_questions.append({
                "prospect": a["prospect_name"],
                "date": a["date"],
                "archetype": a.get("buyer_archetype", "unclear"),
                "question": q.get("question", ""),
                "timestamp": q.get("timestamp"),
                "response": q.get("prospect_response_summary", ""),
            })

    # Close triggers
    close_triggers = [
        {"prospect": a["prospect_name"], "date": a["date"], "archetype": a.get("buyer_archetype"),
         "trigger": a.get("close_trigger", ""), "revenue": a.get("revenue")}
        for a in closes if a.get("close_trigger")
    ]

    # Build markdown
    lines = [
        "# Sales Closing Patterns — KubeCraft",
        f"*Generated {datetime.now().strftime('%Y-%m-%d')} from {len(analyses)} call transcripts*",
        "",
        "---",
        "",
        "## 1. Performance Overview",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total calls analyzed | {len(analyses)} |",
        f"| Confirmed closes | {len(closes)} |",
        f"| Confirmed losses | {len(losses)} |",
        f"| Unknown outcome | {len(analyses) - len(closes) - len(losses)} |",
        f"| Overall close rate | {len(closes)/len(analyses)*100:.0f}% |",
        "",
        "---",
        "",
        "## 2. Close Rate by Buyer Archetype",
        "",
        "| Archetype | Closes | Total | Close Rate | Revenue |",
        "|-----------|--------|-------|------------|---------|",
    ]

    for arch, stats in sorted(archetype_stats.items(), key=lambda x: -x[1]["closes"]):
        rate = stats["closes"] / stats["total"] * 100 if stats["total"] else 0
        rev = f"${stats['revenue']:,}" if stats["revenue"] else "—"
        lines.append(f"| {arch} | {stats['closes']} | {stats['total']} | {rate:.0f}% | {rev} |")

    lines += [
        "",
        "---",
        "",
        "## 3. Every Confirmed Close — What Worked",
        "",
    ]

    for a in sorted(closes, key=lambda x: x.get("date", ""), reverse=True):
        lines += [
            f"### {a['prospect_name']} ({a.get('date', '')}) — {a.get('revenue', 'unknown')}",
            f"**Archetype:** {a.get('buyer_archetype', 'unclear')} ({a.get('archetype_confidence', '')})",
            f"**Close trigger:** {a.get('close_trigger', '—')}",
            f"**Key turning point:** {a.get('key_turning_point', '—')}",
            "",
        ]
        if a.get("discovery_questions_used"):
            lines.append("**Discovery questions that led to this close:**")
            for q in a.get("discovery_questions_used", []):
                ts = f" _{q.get('timestamp')}_" if q.get("timestamp") else ""
                lines.append(f"- {q.get('question', '')}  {ts}")
                if q.get("prospect_response_summary"):
                    lines.append(f"  → *{q['prospect_response_summary']}*")
            lines.append("")
        if a.get("objections_handled_well"):
            lines.append("**Objections handled well:**")
            for obj in a.get("objections_handled_well", []):
                lines.append(f"- {obj}")
            lines.append("")

    lines += [
        "---",
        "",
        "## 4. Discovery Questions That Closed Deals",
        "",
        "Questions that appeared in closed calls, with the prospect response that created momentum:",
        "",
    ]

    # Dedupe and rank questions by frequency
    q_freq: dict[str, list] = {}
    for q in close_questions:
        text = q["question"].strip().lower()
        if len(text) < 10:
            continue
        if text not in q_freq:
            q_freq[text] = []
        q_freq[text].append(q)

    for q_text, instances in sorted(q_freq.items(), key=lambda x: -len(x[1])):
        display = instances[0]["question"]
        lines.append(f"**\"{display}\"** *(used in {len(instances)} close{'s' if len(instances)>1 else ''})*")
        for inst in instances[:3]:
            lines.append(f"- {inst['prospect']} ({inst['archetype']}): *{inst['response'][:150]}*")
        lines.append("")

    lines += [
        "---",
        "",
        "## 5. Common Loss Patterns",
        "",
    ]

    for a in sorted(losses, key=lambda x: x.get("date", ""), reverse=True)[:15]:
        lines += [
            f"### {a['prospect_name']} ({a.get('date', '')})",
            f"**Archetype:** {a.get('buyer_archetype', 'unclear')}",
            f"**Loss reason:** {a.get('loss_reason', '—')}",
            f"**What could have been different:** {', '.join(a.get('objections_mishandled', ['—']))}",
            "",
        ]

    lines += [
        "---",
        "",
        "## 6. Encodable Rules (Decision Tree Foundation)",
        "",
        "Derived from close/loss patterns across all calls:",
        "",
        "### Detection Rules (Parts 3-4 of script)",
        "| Signal | → Archetype | Action |",
        "|--------|-------------|--------|",
        "| Laid off, months unemployed, family pressure | Pain Buyer | Go 5 layers deep on pain, consequence stack |",
        "| Employed, wants growth, 2-5yr goals | Vision Buyer | Vision/identity questions, no urgency pressure |",
        "| Direct, knows what they want, asks pricing | Convenience Buyer | Give clean options fast, skip long discovery |",
        "| Urgency + 'I can't afford upfront' | Crisis Buyer | BNPL/deposit path or ethical DQ |",
        "| Vague, 'just looking', won't share info | Tire Kicker | DQ by minute 8-10 |",
        "",
        "### Close Rules",
        "| Archetype | Close Technique | Key Move |",
        "|-----------|-----------------|----------|",
        "| Pain Buyer | Consequence stacking | Use their exact words from discovery |",
        "| Vision Buyer | ROI math + identity | Make the future vivid and personal |",
        "| Convenience Buyer | Remove friction | Clean pricing, no over-explanation |",
        "| Crisis Buyer | BNPL or DQ | Never pressure someone who can't afford it |",
        "",
    ]

    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("Sales Transcript Analysis Pipeline")
    print("=" * 50)

    # Load existing analysis to skip already-done calls
    existing = {}
    if FULL_ANALYSIS_PATH.exists():
        with open(FULL_ANALYSIS_PATH) as f:
            data = json.load(f)
            for call in data.get("calls", []):
                existing[call.get("prospect_name", "")] = call
        print(f"Loaded {len(existing)} existing analyses")

    # Get all files, sorted by priority
    files = extract_zip()
    files.sort(key=sort_key)

    print(f"\nProcessing {len(files)} transcripts (closes first, Dec/Jan priority)")
    print("─" * 50)

    analyses = list(existing.values())
    new_count = 0
    error_count = 0

    for i, path in enumerate(files):
        prospect_name = extract_prospect_name(path.name)
        date = parse_date_from_filename(path.name)

        # Skip if already analyzed
        if prospect_name in existing:
            print(f"  [{i+1:3d}/{len(files)}] SKIP  {prospect_name} (already done)")
            continue

        is_close = any(k.lower() in prospect_name.lower() for k in KNOWN_CLOSES.keys())
        flag = "★ CLOSE" if is_close else "      "
        print(f"  [{i+1:3d}/{len(files)}] {flag} {prospect_name} ({date})", end="", flush=True)

        try:
            notes, transcript = read_docx_text(path)
            if len(notes) < 100:
                print(f" → SKIP (empty)")
                continue

            result = analyze_call(prospect_name, date, notes, transcript, is_close)

            if "error" in result:
                print(f" → ERROR: {result['error'][:60]}")
                error_count += 1
            else:
                print(f" → {result.get('outcome', '?')} ({result.get('buyer_archetype', '?')})")
                analyses.append(result)
                new_count += 1

            # Save incrementally
            OUTPUT_DIR.mkdir(exist_ok=True)
            with open(FULL_ANALYSIS_PATH, "w") as f:
                json.dump({
                    "generated": datetime.now().isoformat(),
                    "total_calls": len(analyses),
                    "closes": sum(1 for a in analyses if a.get("outcome") == "close"),
                    "losses": sum(1 for a in analyses if a.get("outcome") == "loss"),
                    "calls": sorted(analyses, key=lambda x: x.get("date", ""), reverse=True),
                }, f, indent=2)

            # Rate limit: GitHub gpt-4o-mini allows ~15 req/min on free tier
            time.sleep(4.5)

        except Exception as e:
            print(f" → FAIL: {e}")
            error_count += 1

    print(f"\n{'─'*50}")
    print(f"New analyses: {new_count} | Errors: {error_count} | Total: {len(analyses)}")

    # Generate insights doc
    print("\nGenerating closing patterns document...")
    insights = build_insights_doc(analyses)
    with open(INSIGHTS_PATH, "w") as f:
        f.write(insights)

    print(f"✓ Full analysis: {FULL_ANALYSIS_PATH}")
    print(f"✓ Closing patterns: {INSIGHTS_PATH}")
    print("\nDone.")


if __name__ == "__main__":
    main()
