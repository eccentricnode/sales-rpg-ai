#!/usr/bin/env python3
"""
Multi-provider RAG comparison test for Sales RPG AI.

Loads the sales script through the RAG pipeline (chunk -> embed -> retrieve),
then compares RAG-based prompts vs full-script prompts across multiple LLM
providers. Shows token counts, latency, and output quality side by side.

Usage:
    python test_rag_providers.py
    python test_rag_providers.py --provider github
    python test_rag_providers.py --scenario "Discovery Phase"
    python test_rag_providers.py --provider openrouter --scenario "Price Objection"
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

# Load .env from project root
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# Ensure src/ is on the path so RAG imports work
sys.path.insert(0, str(Path(__file__).parent / "src"))

from openai import OpenAI

from rag.chunker import chunk_script
from rag.stage_detector import StageDetector
from rag.store import EmbeddingStore
from rag.retriever import ScriptRetriever
from realtime.prompts import get_script_guidance_prompt, get_rag_guidance_prompt, load_script

# ---------------------------------------------------------------------------
# Provider configuration
# ---------------------------------------------------------------------------

PROVIDERS = {
    "github": {
        "env_key": "GITHUB_TOKEN",
        "base_url": "https://models.github.ai/inference",
        "model": "gpt-4o-mini",
    },
    "openrouter": {
        "env_key": "OPENROUTER_API_KEY",
        "base_url": "https://openrouter.ai/api/v1",
        "model": "meta-llama/llama-3.3-70b-instruct:free",
    },
    "local": {
        "env_key": None,  # Uses "local" as dummy key
        "base_url": "http://localhost:8081/v1",
        "model": "phi-3.5-mini",
    },
}

# ---------------------------------------------------------------------------
# Test scenarios
# ---------------------------------------------------------------------------

TEST_SCENARIOS = [
    {
        "name": "Discovery Phase",
        "context": "Rep: So give me some context, what's the main thing that motivated you to book this call?",
        "latest": (
            "Prospect: Well, I've been in my current IT support role for about "
            "3 years now and I feel stuck. I keep seeing DevOps jobs that pay "
            "way more and I want to make that transition but I don't know where "
            "to start."
        ),
        "expected_stage": "Part 4",
    },
    {
        "name": "Price Objection",
        "context": (
            "Rep: So the investment for the community, all the content, "
            "the mentorship calls and our guarantee is just $3,500."
        ),
        "latest": (
            "Prospect: Wow, that's... that's a lot of money. I wasn't "
            "expecting it to be that much."
        ),
        "expected_stage": "objection",
    },
    {
        "name": "Temp Check",
        "context": (
            "Rep: Scale of 1-10, 1 being I never want to speak to this guy "
            "again and 10 being this will solve all my problems. Where are you at?"
        ),
        "latest": (
            "Prospect: I'd say probably a 7 or 8. I really like what you've "
            "shown me but I'm just not 100% sure yet."
        ),
        "expected_stage": "Part 11",
    },
    {
        "name": "Spouse Stall",
        "context": (
            "Rep: If we can help you solve these problems, are you ready to "
            "get started working on that now?"
        ),
        "latest": (
            "Prospect: I think so, but I really need to run this by my wife "
            "first before I make any financial decisions."
        ),
        "expected_stage": "objection",
    },
    {
        "name": "Buying Signal",
        "context": (
            "Rep: That's the full KubeCraft OS -- five interconnected systems "
            "that cover every part of the DevOps journey."
        ),
        "latest": (
            "Prospect: Okay, that all makes a lot of sense. So what's the "
            "next step? How do we get started?"
        ),
        "expected_stage": "Part 12",
    },
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 characters per token for English text."""
    return len(text) // 4


def build_user_message(context: str, latest: str) -> str:
    """Build the user message from context and latest utterance."""
    return (
        f"<conversation_so_far>\n{context}\n</conversation_so_far>\n\n"
        f"<latest>\n{latest}\n</latest>"
    )


def get_available_providers(filter_name: str | None = None) -> dict:
    """Return provider configs that have credentials available."""
    available = {}
    for name, config in PROVIDERS.items():
        if filter_name and name != filter_name:
            continue

        env_key = config["env_key"]
        if env_key is None:
            # Local provider -- always include, will fail gracefully at call time
            available[name] = config
        elif os.getenv(env_key):
            available[name] = config
        else:
            print(f"  [SKIP] {name}: {env_key} not set in environment")

    return available


def make_client(config: dict) -> OpenAI:
    """Create an OpenAI client for the given provider config."""
    env_key = config["env_key"]
    api_key = os.getenv(env_key) if env_key else "local"
    return OpenAI(base_url=config["base_url"], api_key=api_key)


def call_llm(client: OpenAI, model: str, system_prompt: str, user_msg: str) -> tuple[str, float]:
    """
    Send a chat completion request and return (response_text, elapsed_seconds).

    Returns ("ERROR: <message>", elapsed) on failure.
    """
    start = time.time()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=400,
            temperature=0.3,
        )
        elapsed = time.time() - start
        return response.choices[0].message.content or "", elapsed
    except Exception as e:
        elapsed = time.time() - start
        return f"ERROR: {e}", elapsed


def try_parse_json(text: str) -> dict | None:
    """Attempt to extract JSON from LLM response text."""
    # Try direct parse first
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass

    # Try extracting from markdown code block
    if "```" in text:
        lines = text.split("```")
        for block in lines[1::2]:  # odd-indexed blocks are inside fences
            block = block.strip()
            if block.startswith("json"):
                block = block[4:].strip()
            try:
                return json.loads(block)
            except (json.JSONDecodeError, TypeError):
                continue
    return None


def format_response(raw: str, max_width: int = 70) -> str:
    """Format LLM response for display, truncating if needed."""
    parsed = try_parse_json(raw)
    if parsed:
        formatted = json.dumps(parsed, indent=2)
    else:
        formatted = raw.strip()

    lines = formatted.split("\n")
    truncated = []
    for line in lines[:15]:
        if len(line) > max_width:
            truncated.append(line[:max_width] + "...")
        else:
            truncated.append(line)
    if len(lines) > 15:
        truncated.append(f"... ({len(lines) - 15} more lines)")
    return "\n".join(truncated)


# ---------------------------------------------------------------------------
# Pipeline initialization
# ---------------------------------------------------------------------------


def init_rag_pipeline() -> tuple[ScriptRetriever, list[dict]]:
    """
    Initialize the full RAG pipeline: chunk -> embed -> retriever.

    Returns (retriever, chunks).
    """
    script_path = str(
        Path(__file__).parent / "knowledge_base" / "kubecraft_script.md"
    )

    print("  [1/3] Chunking script...")
    chunks = chunk_script(script_path)
    print(f"         {len(chunks)} chunks created")

    print("  [2/3] Building embedding store (in-memory)...")
    store = EmbeddingStore()
    store.add_chunks(chunks)
    print(f"         {store.count()} chunks indexed")

    print("  [3/3] Creating hybrid retriever...")
    detector = StageDetector()
    retriever = ScriptRetriever(store, detector, chunks)
    print("         Retriever ready")

    return retriever, chunks


# ---------------------------------------------------------------------------
# Main test loop
# ---------------------------------------------------------------------------


def run_scenario(
    scenario: dict,
    retriever: ScriptRetriever,
    full_script_prompt: str,
    providers: dict,
) -> dict:
    """
    Run one test scenario across all providers with both RAG and full-script prompts.

    Returns a results dict for the summary table.
    """
    name = scenario["name"]
    context = scenario["context"]
    latest = scenario["latest"]
    expected = scenario["expected_stage"]
    user_msg = build_user_message(context, latest)

    print(f"\n{'='*72}")
    print(f"  SCENARIO: {name}")
    print(f"  Expected Stage: {expected}")
    print(f"{'='*72}")
    print(f"\n  Context: {context[:80]}...")
    print(f"  Latest:  {latest[:80]}...")

    # --- RAG retrieval ---
    print(f"\n  --- Retrieval ---")
    retrieved_texts = retriever.retrieve(latest, context, top_k=3)
    retrieved_meta = retriever.retrieve_with_metadata(latest, context, top_k=3)

    # Show stage detection
    detector = retriever.detector
    stage, confidence = detector.detect(latest)
    part = detector.get_part_number(stage)
    stage_label = f"Part {part}" if part else "Objection Handling"
    print(f"  Stage detected: {stage} ({stage_label}) | confidence: {confidence:.2f}")

    # Show retrieved chunks
    for i, meta in enumerate(retrieved_meta):
        section = meta.get("metadata", {}).get("section", "unknown")
        text_len = len(meta.get("text", ""))
        distance = meta.get("distance", "N/A")
        if isinstance(distance, float):
            distance = f"{distance:.3f}"
        print(f"  Chunk {i+1}: [{section}] ({text_len} chars, dist={distance})")

    # --- Build prompts ---
    rag_prompt = get_rag_guidance_prompt(retrieved_texts)
    rag_tokens = estimate_tokens(rag_prompt + user_msg)
    full_tokens = estimate_tokens(full_script_prompt + user_msg)

    print(f"\n  Token estimates:")
    print(f"    RAG prompt:  ~{rag_tokens:,} tokens ({len(rag_prompt):,} chars)")
    print(f"    Full prompt: ~{full_tokens:,} tokens ({len(full_script_prompt):,} chars)")
    print(f"    Reduction:   {(1 - rag_tokens / full_tokens) * 100:.0f}%")

    # --- Call each provider ---
    scenario_results = {
        "name": name,
        "expected": expected,
        "detected": stage_label,
        "rag_tokens": rag_tokens,
        "full_tokens": full_tokens,
        "providers": {},
    }

    for provider_name, config in providers.items():
        print(f"\n  --- Provider: {provider_name.upper()} ({config['model']}) ---")

        try:
            client = make_client(config)
        except Exception as e:
            print(f"    [SKIP] Could not create client: {e}")
            continue

        # RAG prompt
        print(f"    [RAG]  Sending...")
        rag_response, rag_time = call_llm(client, config["model"], rag_prompt, user_msg)
        rag_ok = not rag_response.startswith("ERROR:")

        if rag_ok:
            print(f"    [RAG]  Response ({rag_time:.1f}s):")
            for line in format_response(rag_response).split("\n"):
                print(f"           {line}")
        else:
            print(f"    [RAG]  {rag_response}")

        # Full-script prompt
        print(f"    [FULL] Sending...")
        full_response, full_time = call_llm(
            client, config["model"], full_script_prompt, user_msg
        )
        full_ok = not full_response.startswith("ERROR:")

        if full_ok:
            print(f"    [FULL] Response ({full_time:.1f}s):")
            for line in format_response(full_response).split("\n"):
                print(f"           {line}")
        else:
            print(f"    [FULL] {full_response}")

        # Parse and compare
        rag_parsed = try_parse_json(rag_response) if rag_ok else None
        full_parsed = try_parse_json(full_response) if full_ok else None

        rag_location = rag_parsed.get("script_location", "?") if rag_parsed else "parse_fail"
        full_location = full_parsed.get("script_location", "?") if full_parsed else "parse_fail"

        if rag_ok and full_ok:
            print(f"\n    Comparison:")
            print(f"      RAG  script_location: {rag_location}")
            print(f"      FULL script_location: {full_location}")
            print(f"      RAG  time: {rag_time:.1f}s | FULL time: {full_time:.1f}s")

        scenario_results["providers"][provider_name] = {
            "rag_ok": rag_ok,
            "full_ok": full_ok,
            "rag_time": rag_time,
            "full_time": full_time,
            "rag_location": rag_location,
            "full_location": full_location,
        }

    return scenario_results


def print_summary(all_results: list[dict]) -> None:
    """Print a summary comparison table."""
    print(f"\n\n{'#'*72}")
    print("  SUMMARY")
    print(f"{'#'*72}\n")

    # --- Token comparison ---
    print("  Token Reduction (RAG vs Full Script):")
    print(f"  {'Scenario':<20} {'RAG':>8} {'Full':>8} {'Saved':>8} {'%':>6}")
    print(f"  {'-'*20} {'-'*8} {'-'*8} {'-'*8} {'-'*6}")
    for r in all_results:
        saved = r["full_tokens"] - r["rag_tokens"]
        pct = (1 - r["rag_tokens"] / r["full_tokens"]) * 100
        print(
            f"  {r['name']:<20} {r['rag_tokens']:>8,} {r['full_tokens']:>8,} "
            f"{saved:>8,} {pct:>5.0f}%"
        )
    print()

    # --- Stage detection accuracy ---
    print("  Stage Detection:")
    print(f"  {'Scenario':<20} {'Expected':<15} {'Detected':<20}")
    print(f"  {'-'*20} {'-'*15} {'-'*20}")
    for r in all_results:
        match = "OK" if _stage_matches(r["expected"], r["detected"]) else "MISMATCH"
        print(f"  {r['name']:<20} {r['expected']:<15} {r['detected']:<20} {match}")
    print()

    # --- Per-provider results ---
    all_providers = set()
    for r in all_results:
        all_providers.update(r["providers"].keys())

    for provider in sorted(all_providers):
        print(f"  Provider: {provider.upper()}")
        print(f"  {'Scenario':<20} {'RAG Loc':<18} {'Full Loc':<18} {'RAG t':>6} {'Full t':>6}")
        print(f"  {'-'*20} {'-'*18} {'-'*18} {'-'*6} {'-'*6}")
        for r in all_results:
            pr = r["providers"].get(provider)
            if pr:
                rag_t = f"{pr['rag_time']:.1f}s" if pr["rag_ok"] else "ERR"
                full_t = f"{pr['full_time']:.1f}s" if pr["full_ok"] else "ERR"
                print(
                    f"  {r['name']:<20} {pr['rag_location']:<18} "
                    f"{pr['full_location']:<18} {rag_t:>6} {full_t:>6}"
                )
            else:
                print(f"  {r['name']:<20} {'SKIP':<18} {'SKIP':<18}")
        print()


def _stage_matches(expected: str, detected: str) -> bool:
    """Check if detected stage matches expected (loose match)."""
    expected_lower = expected.lower()
    detected_lower = detected.lower()
    if expected_lower in detected_lower:
        return True
    if "objection" in expected_lower and "objection" in detected_lower:
        return True
    return False


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Multi-provider RAG comparison test for Sales RPG AI"
    )
    parser.add_argument(
        "--provider",
        help="Test only this provider (github, openrouter, local)",
    )
    parser.add_argument(
        "--scenario",
        help='Test only this scenario by name (e.g. "Discovery Phase")',
    )
    args = parser.parse_args()

    print(f"\n{'#'*72}")
    print("  RAG vs FULL-SCRIPT PROVIDER COMPARISON TEST")
    print(f"{'#'*72}\n")

    # --- Check available providers ---
    print("Checking providers...")
    providers = get_available_providers(args.provider)
    if not providers:
        print("\n  No providers available. Set API keys in .env:")
        for name, config in PROVIDERS.items():
            env_key = config["env_key"] or "(always available)"
            print(f"    {name}: {env_key}")
        sys.exit(1)
    print(f"\n  Available: {', '.join(providers.keys())}\n")

    # --- Initialize RAG pipeline ---
    print("Initializing RAG pipeline...")
    try:
        retriever, chunks = init_rag_pipeline()
    except Exception as e:
        print(f"\n  FATAL: Could not initialize RAG pipeline: {e}")
        print("  Make sure chromadb and sentence-transformers are installed:")
        print("    pip install chromadb sentence-transformers")
        sys.exit(1)

    # --- Load full script for comparison ---
    print("\nLoading full script for comparison...")
    full_script = load_script()
    if full_script.startswith("Error:"):
        print(f"  WARNING: {full_script}")
        print("  Full-script comparison will be skipped.")
        full_script_prompt = ""
    else:
        full_script_prompt = get_script_guidance_prompt(full_script)
        print(f"  Full script: {len(full_script):,} chars (~{estimate_tokens(full_script):,} tokens)")

    # --- Filter scenarios ---
    scenarios = TEST_SCENARIOS
    if args.scenario:
        scenarios = [s for s in scenarios if s["name"].lower() == args.scenario.lower()]
        if not scenarios:
            print(f"\n  Unknown scenario: '{args.scenario}'")
            print(f"  Available: {', '.join(s['name'] for s in TEST_SCENARIOS)}")
            sys.exit(1)

    # --- Run tests ---
    all_results = []
    for scenario in scenarios:
        result = run_scenario(scenario, retriever, full_script_prompt, providers)
        all_results.append(result)

    # --- Summary ---
    print_summary(all_results)

    print("Done.")


if __name__ == "__main__":
    main()
