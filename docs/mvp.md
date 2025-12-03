
# Sales AI App - MVP (Just Test If It Works)

## Goal
Build the simplest possible version to test: **"Can AI detect sales objections and suggest useful responses?"**

## MVP Features (Bare Minimum)

### What It Does
- Listens to your microphone
- Shows live transcript
- Detects basic objections
- Shows suggested responses
- That's it.

## Simple UI
- Basic window (not invisible yet)
- Live transcript at top
- Detected objections in middle
- Response suggestions at bottom
- Start/stop button

## Tech Stack (Simplest)
- **Python** (fastest to build)
- **OpenAI Whisper** (local or API, whatever works)
- **Basic pattern matching** (no ML yet)
- **Tkinter UI** (built into Python)
- **No database** (hardcoded responses)

## Success Criteria
- Can it detect objections in real conversations? (70%+ accuracy)
- Are the suggested responses actually useful?
- Do sales reps want to use this?
- Does it feel helpful or annoying?

## What We're NOT Building (Yet)
- ❌ Invisible overlay
- ❌ <150ms processing
- ❌ Custom training
- ❌ Multiple objection types
- ❌ ML classification
- ❌ Advanced UI
- ❌ Cross-platform support

## Test Plan
1. Record 5-10 sales call roleplays
2. Run them through the MVP
3. Check: Did it catch the objections?
4. Check: Were the responses helpful?
5. Ask: Would you use this in real calls?

## If MVP Works
Then we optimize for speed, add invisible UI, more objections, custom responses, etc.

---

**Bottom Line**: Build the dumbest version that tests the core value prop in 2-4 weeks.
