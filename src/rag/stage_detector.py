"""
Keyword-based sales call stage detection.

Given a text utterance, detects which Part of the KubeCraft sales script
the conversation is currently in. Uses case-insensitive keyword matching
with confidence scoring based on hit density.
"""

from __future__ import annotations


class StageDetector:
    """Detects the current sales call stage from conversational text."""

    # Maps stage names to keyword/phrase lists for detection.
    # Keywords are ordered roughly by specificity (most distinctive first).
    STAGE_KEYWORDS: dict[str, list[str]] = {
        "part_1_open": [
            "nice to meet you",
            "how are you",
            "good to see you",
            "welcome",
            "hey there",
            "rapport",
            "greeting",
        ],
        "part_2_set_agenda": [
            "overview of this call",
            "does that sound good",
            "same page",
            "set the agenda",
            "quick overview",
            "ask some questions",
            "pen and pad",
            "take notes",
            "great fit",
            "point you in a different direction",
        ],
        "part_3_why_here": [
            "motivated",
            "book this call",
            "brought you here",
            "context",
            "main thing",
            "what caused",
            "tell me more",
            "why are you here",
            "what made you",
        ],
        "part_4_pain_problem": [
            "current role",
            "how long",
            "pain",
            "problem",
            "linux",
            "kubernetes",
            "containers",
            "technical baseline",
            "applied to jobs",
            "previous attempts",
            "career change",
            "what are you doing for work",
            "job search",
            "applications",
            "transition",
            "family situation",
            "spouse feel about",
        ],
        "part_5_what_they_want": [
            "end goal",
            "ideal income",
            "6-12 months",
            "six to twelve months",
            "how would your life",
            "how would life look",
            "what kind of role",
            "income level",
            "how soon",
            "dream role",
            "what does that do for you",
        ],
        "part_6_blocker": [
            "holding you back",
            "blocker",
            "what's stopping",
            "summarize",
            "summarise",
            "pain and dream",
            "what i'm hearing",
            "waste anymore time",
            "missing a proven system",
        ],
        "part_7_now_tiedown": [
            "now thing",
            "ready",
            "get help now",
            "willing",
            "is this a now",
            "ready and willing",
            "get started now",
            "work on that now",
            "promise land",
            "get to work",
        ],
        "part_8_pre_pitch": [
            "break down step by step",
            "step by step",
            "break it down",
            "how we do that",
            "where do you want to go from here",
            "our specialty",
            "exact situation",
            "transition to offer",
        ],
        "part_9_pitch": [
            "kubecraft os",
            "devops os",
            "homelab os",
            "homelab",
            "jobmagnet os",
            "jobmagnet",
            "focus os",
            "interview os",
            "operating system for your career",
            "five interconnected",
            "hands-on linux",
            "portfolio",
            "enterprise-grade",
            "linkedin",
            "personal branding",
            "interview practice",
        ],
        "part_10_shut_up": [
            "where do you want to go from here",
            "any questions",
            "what questions",
            "does that make sense",
            "how does it work",
            "what does support look like",
            "1:1 or group",
            "one on one",
        ],
        "part_11_temp_check": [
            "gut check",
            "temp check",
            "how are you feeling",
            "how do you feel about everything",
            "feeling about everything",
            "quick gut check",
            "before we discuss the investment",
            "do you feel like it's exactly",
            "what would make this a 10",
        ],
        "part_12_close": [
            "investment",
            "3500",
            "$3,500",
            "3,500",
            "payment",
            "get started",
            "next step",
            "let's do it",
            "let's get started",
            "lock the price",
            "lock in",
            "what's next",
            "ready to get started",
        ],
        "objection_handling": [
            "think about it",
            "too expensive",
            "spouse",
            "wife",
            "husband",
            "talk to",
            "shop around",
            "not sure",
            "need time",
            "january",
            "can't afford",
            "a lot of money",
            "fear",
            "scared",
            "what if it doesn't work",
            "compare",
            "other options",
            "payment plan",
        ],
    }

    # Mapping from stage name to part number.
    _STAGE_TO_PART: dict[str, int | None] = {
        "part_1_open": 1,
        "part_2_set_agenda": 2,
        "part_3_why_here": 3,
        "part_4_pain_problem": 4,
        "part_5_what_they_want": 5,
        "part_6_blocker": 6,
        "part_7_now_tiedown": 7,
        "part_8_pre_pitch": 8,
        "part_9_pitch": 9,
        "part_10_shut_up": 10,
        "part_11_temp_check": 11,
        "part_12_close": 12,
        "objection_handling": None,
    }

    # Keywords that appear in multiple stages need disambiguation.
    # "scale of" + "1-10" could be Part 4 (technical baseline) or Part 11 (temp check).
    # We use context keywords to disambiguate.
    _SCALE_TECH_CONTEXT = {"linux", "kubernetes", "containers", "skills", "technical"}
    _SCALE_TEMP_CONTEXT = {"feeling", "gut", "check", "investment", "everything"}

    def detect(self, text: str, current_stage: str | None = None) -> tuple[str, float]:
        """
        Detect the current call stage from text.

        Args:
            text: The latest utterance or recent conversation.
            current_stage: The previously detected stage (for continuity).

        Returns:
            (stage_name, confidence) where confidence is 0.0-1.0.
            If no match found: (current_stage or "part_1_open", 0.0).
        """
        if not text or not text.strip():
            return (current_stage or "part_1_open", 0.0)

        text_lower = text.lower()

        # Disambiguate "scale of 1-10" / "1 to 10" between Part 4 and Part 11.
        scale_context = self._detect_scale_context(text_lower)

        # Score each stage by counting keyword hits.
        scores: dict[str, float] = {}
        for stage_name, keywords in self.STAGE_KEYWORDS.items():
            hits = 0
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    hits += 1

            if hits == 0:
                continue

            # Normalize: confidence = hits / total_keywords, capped at 1.0.
            # More hits = higher confidence, but we also weight by keyword count
            # so stages with fewer keywords are not unfairly disadvantaged.
            raw_confidence = hits / len(keywords)
            # Boost slightly for multiple hits (compounding signal).
            boosted = min(1.0, raw_confidence + (hits - 1) * 0.05)
            scores[stage_name] = boosted

        # Apply scale disambiguation if needed.
        if scale_context == "tech" and "part_11_temp_check" in scores:
            scores["part_11_temp_check"] *= 0.3
        elif scale_context == "temp" and "part_4_pain_problem" in scores:
            scores["part_4_pain_problem"] *= 0.3

        # Handle "scale of 1-10" / "1 to 10" as direct signal.
        if self._has_scale_pattern(text_lower):
            if scale_context == "tech":
                scores["part_4_pain_problem"] = max(
                    scores.get("part_4_pain_problem", 0.0), 0.5
                )
            elif scale_context == "temp":
                scores["part_11_temp_check"] = max(
                    scores.get("part_11_temp_check", 0.0), 0.5
                )

        if not scores:
            # No keyword matches -- maintain current stage with zero confidence.
            return (current_stage or "part_1_open", 0.0)

        # Find the best scoring stage.
        best_stage = max(scores, key=lambda s: scores[s])
        best_score = scores[best_stage]

        # Continuity bias: if current_stage matches one of the scored stages and
        # the best score isn't significantly higher, prefer staying in current stage.
        if current_stage and current_stage in scores:
            current_score = scores[current_stage]
            # Only switch if the new stage scores at least 0.15 higher.
            if best_score - current_score < 0.15:
                return (current_stage, current_score)

        return (best_stage, best_score)

    def get_part_number(self, stage_name: str) -> int | None:
        """
        Convert stage name to part number (1-12).

        Returns None for objection_handling or unknown stage names.
        """
        return self._STAGE_TO_PART.get(stage_name)

    def get_all_stage_names(self) -> list[str]:
        """Return all recognized stage names."""
        return list(self.STAGE_KEYWORDS.keys())

    def _detect_scale_context(self, text_lower: str) -> str | None:
        """
        Determine if a 'scale of 1-10' reference is about technical
        baseline (Part 4) or temp check (Part 11).

        Returns 'tech', 'temp', or None if no scale reference found.
        """
        if not self._has_scale_pattern(text_lower):
            return None

        words = set(text_lower.split())
        tech_hits = len(words & self._SCALE_TECH_CONTEXT)
        temp_hits = len(words & self._SCALE_TEMP_CONTEXT)

        if tech_hits > temp_hits:
            return "tech"
        elif temp_hits > tech_hits:
            return "temp"
        return None

    @staticmethod
    def _has_scale_pattern(text_lower: str) -> bool:
        """Check if text contains a 1-10 scale reference."""
        scale_patterns = [
            "scale of 1",
            "1 to 10",
            "1-10",
            "one to ten",
            "scale of one",
        ]
        return any(p in text_lower for p in scale_patterns)


if __name__ == "__main__":
    detector = StageDetector()

    test_cases = [
        ("Hey John, nice to meet you! How are you doing today?", None),
        ("Let me give you a quick overview of this call. Does that sound good?", None),
        ("What motivated you to book this call today?", None),
        ("What's your current role? How long have you been there?", None),
        ("On a scale of 1-10, how would you rate your linux skills?", None),
        ("What's your end goal for the next 6-12 months?", None),
        ("What's holding you back from achieving that?", None),
        ("Is this a NOW thing for you? Are you ready to get help now?", None),
        ("Let me break down step by step how we help people in your situation.", None),
        ("The first system is DevOps OS, which builds your core skills.", None),
        ("So where do you want to go from here?", None),
        ("How are you feeling about everything? Scale of 1-10?", None),
        ("The investment is $3,500. Let's get started.", None),
        ("I need to talk to my wife about this first.", None),
        ("That sounds too expensive, I need to think about it.", None),
        # Test continuity bias
        ("Tell me more about that.", "part_3_why_here"),
        ("How long have you been dealing with this?", "part_3_why_here"),
        ("", None),
    ]

    print("Stage Detection Test Results")
    print("=" * 70)
    for text, current in test_cases:
        stage, confidence = detector.detect(text, current)
        part = detector.get_part_number(stage)
        part_str = f"Part {part}" if part else "Objection"
        current_str = f" (from: {current})" if current else ""
        print(f"\n  Input: \"{text[:60]}...\"" if len(text) > 60 else f"\n  Input: \"{text}\"")
        print(f"  Stage: {stage} ({part_str}) | Confidence: {confidence:.2f}{current_str}")
