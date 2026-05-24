#!/usr/bin/env python3
"""
LLM Inference Latency Load Test.

Fires analysis requests directly at LocalAI to measure cold/warm latency.
Does NOT go through the web app or whisper — isolates pure LLM performance.

Usage:
  python tests/test_llm_latency.py
  python tests/test_llm_latency.py --requests 20
  python tests/test_llm_latency.py --base-url https://models.inference.ai.azure.com/v1 --api-key $AZURE_AI_API_KEY --model gpt-4o-mini
"""

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

from openai import OpenAI

# Load the actual sales script and prompt used in production
SCRIPT_PATH = Path(__file__).parent.parent / "knowledge_base" / "kubecraft_script.md"
PROMPT_TEMPLATE = """You are a real-time Sales Assistant helping a sales rep during a live call.

SALES SCRIPT:
{script}

INSTRUCTIONS:
1. You will receive the conversation transcript. If wrapped in <conversation_so_far> and <latest> tags, use the full conversation for context but focus your suggestion on the <latest> content.
2. Determine where we are in the script based on the full conversation.
3. Identify key information mentioned by the prospect (pain points, objections, buying signals).
4. Suggest the next response based strictly on the script. Be specific and actionable.

OUTPUT FORMAT (JSON ONLY):
{{
    "script_location": "Section Name",
    "key_points": ["point 1", "point 2"],
    "suggestion": "Verbatim response from script"
}}"""

# Simulated conversation snippets at different stages
TEST_TRANSCRIPTS = [
    "Hey how's it going? My name is Austin, nice to meet you.",
    "Yeah I've been struggling with my confidence honestly. I just feel like I'm stuck in my career.",
    "I've tried a few things, you know, online courses, YouTube videos. Nothing really stuck though.",
    "<conversation_so_far>\nHey how's it going? My name is Austin.\nI've been struggling with confidence.\n</conversation_so_far>\n\n<latest>\nSo what exactly does the program include?\n</latest>",
    "<conversation_so_far>\nI've tried online courses. Nothing stuck.\nThe program includes mentorship, community, and content.\n</conversation_so_far>\n\n<latest>\nThat sounds good but I'm not sure I can afford it right now.\n</latest>",
    "Okay I'm interested. What's the investment?",
    "<conversation_so_far>\nI'm interested. What's the investment?\nThe investment is $3,500.\n</conversation_so_far>\n\n<latest>\nHmm that's a lot of money. Let me think about it.\n</latest>",
]


def run_load_test(base_url: str, api_key: str, model: str, num_requests: int):
    script_content = SCRIPT_PATH.read_text()
    system_prompt = PROMPT_TEMPLATE.format(script=script_content)

    client = OpenAI(base_url=base_url, api_key=api_key)

    print(f"{'=' * 70}")
    print(f"LLM LATENCY LOAD TEST")
    print(f"{'=' * 70}")
    print(f"Endpoint:  {base_url}")
    print(f"Model:     {model}")
    print(f"Requests:  {num_requests}")
    print(f"Prompt:    ~{len(system_prompt)} chars system prompt")
    print(f"{'=' * 70}\n")

    latencies = []
    errors = 0

    for i in range(num_requests):
        transcript = TEST_TRANSCRIPTS[i % len(TEST_TRANSCRIPTS)]
        label = "COLD" if i == 0 else f"WARM-{i}"

        start = time.time()
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": transcript},
                ],
                max_tokens=500,
                temperature=0.1,
                timeout=120,
                stop=["<|end|>", "<|end_of_text|>", "<|im_end|>", "\n\n"],
            )
            elapsed = time.time() - start
            content = response.choices[0].message.content.strip()

            # Try to parse JSON
            try:
                if "```json" in content:
                    content = content.split("```json")[1]
                if "```" in content:
                    content = content.split("```")[0]
                data = json.loads(content.strip())
                location = data.get("script_location", "?")
                valid_json = True
            except (json.JSONDecodeError, IndexError):
                location = "INVALID JSON"
                valid_json = False

            latencies.append(elapsed)
            tokens_in = response.usage.prompt_tokens if response.usage else "?"
            tokens_out = response.usage.completion_tokens if response.usage else "?"

            status = "OK" if valid_json else "BAD JSON"
            print(f"  [{label:>7}] {elapsed:6.2f}s  {status:>8}  loc={location:<20}  tokens={tokens_in}/{tokens_out}")

        except Exception as e:
            elapsed = time.time() - start
            errors += 1
            print(f"  [{label:>7}] {elapsed:6.2f}s  ERROR: {e}")

    # Statistics
    if latencies:
        warm_latencies = latencies[1:] if len(latencies) > 1 else latencies

        print(f"\n{'=' * 70}")
        print(f"RESULTS ({len(latencies)} successful, {errors} errors)")
        print(f"{'=' * 70}")
        print(f"  Cold start:    {latencies[0]:.2f}s")

        if warm_latencies:
            print(f"\n  Warm stats ({len(warm_latencies)} requests):")
            print(f"    Min:         {min(warm_latencies):.2f}s")
            print(f"    Max:         {max(warm_latencies):.2f}s")
            print(f"    Mean:        {statistics.mean(warm_latencies):.2f}s")
            print(f"    Median:      {statistics.median(warm_latencies):.2f}s")
            if len(warm_latencies) >= 5:
                sorted_l = sorted(warm_latencies)
                p95_idx = int(len(sorted_l) * 0.95)
                print(f"    P95:         {sorted_l[p95_idx]:.2f}s")

        print(f"\n  All requests:  {statistics.mean(latencies):.2f}s mean")
        print(f"{'=' * 70}")
    else:
        print(f"\nAll {errors} requests failed!")

    return 0 if errors == 0 else 1


def main():
    parser = argparse.ArgumentParser(description="LLM Latency Load Test")
    parser.add_argument("--base-url", default="http://localhost:8081/v1",
                        help="OpenAI-compatible API base URL")
    parser.add_argument("--api-key", default="local",
                        help="API key")
    parser.add_argument("--model", default="qwen2.5-7b",
                        help="Model name")
    parser.add_argument("--requests", type=int, default=10,
                        help="Number of requests to send")
    args = parser.parse_args()

    sys.exit(run_load_test(args.base_url, args.api_key, args.model, args.requests))


if __name__ == "__main__":
    main()
