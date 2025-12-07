"""
Analysis Orchestrator for async LLM calls.

This module manages asynchronous LLM analysis requests, executing them
in a background thread and delivering results via callback.
"""

import queue
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

from openai import OpenAI


STREAMING_ANALYSIS_PROMPT = """You are analyzing a LIVE sales conversation for objections.

CONTEXT (previous conversation):
{context_text}

NEW CONTENT (analyze this for objections):
{active_text}

IMPORTANT:
- Focus analysis on NEW CONTENT only
- Use CONTEXT to understand the conversation flow
- The NEW CONTENT may be mid-sentence or incomplete
- Only flag HIGH confidence objections (avoid false positives)
- If NEW CONTENT is too short/unclear, respond with "INSUFFICIENT_CONTENT"

For each objection found in NEW CONTENT:
1. TYPE: PRICE | TIME | DECISION_MAKER | OTHER
2. CONFIDENCE: HIGH | MEDIUM (skip LOW - too noisy for real-time)
3. QUOTE: Exact words from NEW CONTENT
4. RESPONSE: One best response suggestion (keep it brief for real-time display)

Format:
OBJECTION: [TYPE] | [CONFIDENCE]
> "[quote]"
SUGGEST: [response]

If no objections: "NO_OBJECTIONS"
"""


@dataclass
class AnalysisRequest:
    """Request for LLM analysis."""

    active_text: str
    context_text: str
    timestamp: float


@dataclass
class AnalysisResult:
    """Result from LLM analysis."""

    raw_response: str
    active_text: str
    context_text: str
    timestamp: float
    latency_ms: float
    has_objection: bool
    error: Optional[str] = None


class StreamingAnalyzer:
    """
    Handles LLM API calls for streaming objection analysis.

    Uses the modified prompt strategy for real-time analysis.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        model: str = "meta-llama/llama-3.3-70b-instruct:free",
    ):
        """
        Initialize the streaming analyzer.

        Args:
            api_key: OpenRouter API key
            base_url: API endpoint URL
            model: Model identifier to use
        """
        # If using LocalAI, the API key is ignored but required by SDK
        if "local-ai" in base_url or "localhost" in base_url:
            api_key = "sk-local-ai-placeholder"
            
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model

    def analyze(self, active_text: str, context_text: str) -> str:
        """
        Analyze text for objections.

        Args:
            active_text: New content to analyze
            context_text: Previous conversation context

        Returns:
            Raw LLM response string
        """
        prompt = STREAMING_ANALYSIS_PROMPT.format(
            active_text=active_text,
            context_text=context_text if context_text else "(conversation just started)",
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.3,  # Lower temperature for more consistent analysis
            stop=["<|eot_id|>", "<|end_of_text|>"],  # Explicitly stop generation
        )

        # Handle empty/null responses (can happen with rate limiting)
        if not response.choices:
            raise ValueError("Empty response from API (possible rate limiting)")

        content = response.choices[0].message.content
        if content is None:
            raise ValueError("Null content in API response")

        return content


class AnalysisOrchestrator:
    """
    Orchestrates async LLM analysis calls.

    Receives analysis requests from DualBufferManager,
    executes them in background thread, delivers results
    via callback.
    """

    def __init__(
        self,
        analyzer: StreamingAnalyzer,
        on_result: Callable[[AnalysisResult], None],
        max_queue_size: int = 10,
    ):
        """
        Initialize the orchestrator.

        Args:
            analyzer: The LLM analyzer instance
            on_result: Callback for analysis results
                      Signature: (result: AnalysisResult) -> None
            max_queue_size: Maximum pending analysis requests
        """
        self.analyzer = analyzer
        self.on_result = on_result
        self.max_queue_size = max_queue_size

        # Analysis queue
        self._queue: queue.Queue[Optional[AnalysisRequest]] = queue.Queue(
            maxsize=max_queue_size
        )

        # Worker thread
        self._worker_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()

        # Stats
        self.total_requests = 0
        self.total_completed = 0
        self.total_errors = 0

    def start(self) -> None:
        """Start the worker thread."""
        if self._worker_thread is not None and self._worker_thread.is_alive():
            return

        self._shutdown_event.clear()
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

    def submit_analysis(self, active_text: str, context_text: str) -> bool:
        """
        Submit text for async analysis.

        Non-blocking. Results delivered via on_result callback.

        Args:
            active_text: New content to analyze
            context_text: Previous conversation context

        Returns:
            True if request was queued, False if queue is full
        """
        # Auto-start worker if needed
        if self._worker_thread is None or not self._worker_thread.is_alive():
            self.start()

        request = AnalysisRequest(
            active_text=active_text,
            context_text=context_text,
            timestamp=time.time(),
        )

        try:
            self._queue.put_nowait(request)
            self.total_requests += 1
            return True
        except queue.Full:
            # Queue is full, drop the request
            print("[WARN] Analysis queue full, dropping request")
            return False

    def shutdown(self, timeout: float = 5.0) -> None:
        """
        Gracefully shutdown worker thread.

        Args:
            timeout: Maximum seconds to wait for shutdown
        """
        self._shutdown_event.set()

        # Send sentinel to unblock queue.get()
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass

        if self._worker_thread is not None:
            self._worker_thread.join(timeout=timeout)

    def _worker_loop(self) -> None:
        """Background worker that processes analysis requests."""
        while not self._shutdown_event.is_set():
            try:
                # Wait for a request (with timeout to check shutdown)
                request = self._queue.get(timeout=0.5)

                if request is None:
                    # Sentinel value, shutdown requested
                    break

                # Process the request
                result = self._process_request(request)

                # Deliver result via callback
                try:
                    self.on_result(result)
                except Exception as e:
                    print(f"[WARN] on_result callback raised: {e}")

            except queue.Empty:
                # Timeout, check shutdown and continue
                continue
            except Exception as e:
                print(f"[ERROR] Worker loop error: {e}")
                self.total_errors += 1

    def _process_request(self, request: AnalysisRequest) -> AnalysisResult:
        """Process a single analysis request."""
        start_time = time.time()
        error = None
        raw_response = ""
        has_objection = False

        try:
            raw_response = self.analyzer.analyze(
                request.active_text, request.context_text
            )
            self.total_completed += 1

            # Simple check for objection presence
            has_objection = (
                "OBJECTION:" in raw_response
                and "NO_OBJECTIONS" not in raw_response
            )

        except Exception as e:
            error = str(e)
            self.total_errors += 1

        latency_ms = (time.time() - start_time) * 1000

        return AnalysisResult(
            raw_response=raw_response,
            active_text=request.active_text,
            context_text=request.context_text,
            timestamp=request.timestamp,
            latency_ms=latency_ms,
            has_objection=has_objection,
            error=error,
        )


# Simple test
if __name__ == "__main__":
    import os
    from pathlib import Path

    # Load environment variables
    env_file = Path(__file__).parent.parent.parent / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()

    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        print("=" * 60)
        print("MOCK TEST (no API key)")
        print("=" * 60)
        print("\nSet OPENROUTER_API_KEY to test with real LLM calls.")
        print("\nTesting orchestrator mechanics without API...\n")

        # Test with mock analyzer
        class MockAnalyzer:
            def analyze(self, active_text: str, context_text: str) -> str:
                time.sleep(0.1)  # Simulate latency
                if "price" in active_text.lower():
                    return 'OBJECTION: [PRICE] | [HIGH]\n> "too expensive"\nSUGGEST: Discuss value proposition'
                return "NO_OBJECTIONS"

        results = []

        def on_result(result: AnalysisResult):
            results.append(result)
            print(f"\n{'='*60}")
            print("RESULT RECEIVED")
            print(f"{'='*60}")
            print(f"Active text: {result.active_text}")
            print(f"Has objection: {result.has_objection}")
            print(f"Latency: {result.latency_ms:.0f}ms")
            print(f"Response: {result.raw_response}")
            print(f"{'='*60}\n")

        orchestrator = AnalysisOrchestrator(
            analyzer=MockAnalyzer(),
            on_result=on_result,
        )

        print("Submitting test requests...")
        orchestrator.submit_analysis("Hello, nice to meet you", "")
        orchestrator.submit_analysis("The price is too expensive for us", "Hello, nice to meet you")
        orchestrator.submit_analysis("Let me think about it", "The price is too expensive")

        # Wait for processing
        time.sleep(1)
        orchestrator.shutdown()

        print(f"\nTotal results: {len(results)}")
        print(f"Objections found: {sum(1 for r in results if r.has_objection)}")

    else:
        print("=" * 60)
        print("LIVE TEST (with OpenRouter API)")
        print("=" * 60)

        analyzer = StreamingAnalyzer(api_key=api_key)

        def on_result(result: AnalysisResult):
            print(f"\n{'='*60}")
            print("RESULT RECEIVED")
            print(f"{'='*60}")
            print(f"Active text: {result.active_text}")
            print(f"Has objection: {result.has_objection}")
            print(f"Latency: {result.latency_ms:.0f}ms")
            if result.error:
                print(f"Error: {result.error}")
            else:
                print(f"Response:\n{result.raw_response}")
            print(f"{'='*60}\n")

        orchestrator = AnalysisOrchestrator(
            analyzer=analyzer,
            on_result=on_result,
        )

        print("\nSubmitting test requests to LLM...")
        print("(This may take a few seconds per request)\n")

        # Test 1: No objection
        print("[Test 1] Greeting (no objection expected)")
        orchestrator.submit_analysis(
            "Hello, thanks for taking the time to meet with me today.",
            "",
        )

        # Wait for first result
        time.sleep(5)

        # Test 2: Price objection
        print("[Test 2] Price objection expected")
        orchestrator.submit_analysis(
            "That's way too expensive for our budget right now.",
            "Hello, thanks for taking the time to meet with me today.",
        )

        # Wait for second result
        time.sleep(5)

        # Test 3: Decision maker objection
        print("[Test 3] Decision maker objection expected")
        orchestrator.submit_analysis(
            "I need to run this by my manager before we can move forward.",
            "That's way too expensive for our budget right now.",
        )

        # Wait for results
        time.sleep(5)

        orchestrator.shutdown()

        print("\n" + "=" * 60)
        print(f"Test complete!")
        print(f"Total requests: {orchestrator.total_requests}")
        print(f"Completed: {orchestrator.total_completed}")
        print(f"Errors: {orchestrator.total_errors}")
        print("=" * 60)
