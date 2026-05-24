import queue
import threading
import time
import json
import os
from dataclasses import dataclass
from typing import Callable, Optional, List

from openai import OpenAI
from .models import ConversationState

# Load script content
SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "../../knowledge_base/kubecraft_script.md")
try:
    with open(SCRIPT_PATH, "r") as f:
        SCRIPT_CONTENT = f.read()
except FileNotFoundError:
    SCRIPT_CONTENT = "Error: Script file not found."

@dataclass
class AnalysisRequest:
    active_text: str
    context_text: str
    timestamp: float

@dataclass
class AnalysisResult:
    raw_response: str
    active_text: str
    timestamp: float
    latency_ms: float
    state: ConversationState
    error: Optional[str] = None

class StreamingAnalyzer:
    def __init__(self, api_key: str, base_url: str, model: str, fallback_model: Optional[str] = None):
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model
        self.fallback_model = fallback_model
        self.system_prompt = f"""You are a Sales Assistant.

        SALES SCRIPT:
        {SCRIPT_CONTENT}

        INSTRUCTIONS:
        1. Read the transcript snippet.
        2. Determine where we are in the script.
        3. Identify key information mentioned by the prospect.
        4. Suggest the next response based strictly on the script.

        OUTPUT FORMAT (JSON ONLY):
        {{
            "script_location": "Section Name",
            "key_points": ["point 1", "point 2"],
            "suggestion": "Verbatim response from script"
        }}
        """

    def analyze(self, text: str) -> str:
        """Analyze text using streaming LLM responses for lower latency."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": text}
            ],
            max_tokens=500,
            temperature=0.1,
            stop=["<|end|>", "<|end_of_text|>", "\n\n"],
            stream=True
        )

        # Collect streaming chunks into full response
        chunks = []
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                chunks.append(chunk.choices[0].delta.content)
        content = "".join(chunks)

        # Clean markdown
        if "```json" in content:
            content = content.split("```json")[1]
        if "```" in content:
            content = content.split("```")[0]

        return content.strip()

    def _try_with_fallback(self, text: str, timeout: float = 5.0) -> str:
        """Try primary model, fall back to fallback_model if timeout exceeded.

        Args:
            text: The text to analyze.
            timeout: Maximum seconds to wait for primary model (default 5.0).

        Returns:
            Analysis result from primary or fallback model.
        """
        result = [None]
        error = [None]

        def _run_primary():
            try:
                result[0] = self.analyze(text)
            except Exception as e:
                error[0] = e

        thread = threading.Thread(target=_run_primary)
        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive() or error[0] is not None:
            # Primary timed out or errored -- try fallback
            if self.fallback_model:
                original_model = self.model
                self.model = self.fallback_model
                try:
                    return self.analyze(text)
                finally:
                    self.model = original_model
            else:
                if error[0]:
                    raise error[0]
                raise TimeoutError(f"Primary model timed out after {timeout}s and no fallback configured")

        return result[0]

class AnalysisOrchestrator:
    def __init__(self, analyzer: StreamingAnalyzer, on_result: Callable[[AnalysisResult], None]):
        self.analyzer = analyzer
        self.on_result = on_result
        self.queue = queue.Queue()
        self.running = False
        self.worker_thread = None

    def start(self):
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

    def shutdown(self):
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=1.0)

    def submit_analysis(self, active_text: str, context_text: str):
        # For minimal approach, we just care about the active text + some context
        # But the prompt is designed for snippets. Let's combine them or just use active.
        # Let's use active_text for now as per script_tester.
        req = AnalysisRequest(active_text, context_text, time.time())
        self.queue.put(req)

    def _worker_loop(self):
        while self.running:
            try:
                req = self.queue.get(timeout=0.5)
                start_time = time.time()
                
                try:
                    raw_json = self.analyzer.analyze(req.active_text)
                    data = json.loads(raw_json)
                    
                    state = ConversationState(
                        script_location=data.get("script_location", "Unknown"),
                        key_points=data.get("key_points", []),
                        suggestion=data.get("suggestion", ""),
                        last_updated=time.time()
                    )
                    
                    result = AnalysisResult(
                        raw_response=raw_json,
                        active_text=req.active_text,
                        timestamp=time.time(),
                        latency_ms=(time.time() - start_time) * 1000,
                        state=state
                    )
                    self.on_result(result)
                    
                except Exception as e:
                    print(f"Analysis Error: {e}")
                    # Send error result
                    self.on_result(AnalysisResult(
                        raw_response="",
                        active_text=req.active_text,
                        timestamp=time.time(),
                        latency_ms=(time.time() - start_time) * 1000,
                        state=ConversationState(),
                        error=str(e)
                    ))
                    
                self.queue.task_done()
            except queue.Empty:
                continue
