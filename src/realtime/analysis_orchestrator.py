import os
import queue
import threading
import time
import json
import logging
from dataclasses import dataclass
from typing import Callable, Optional, List

from openai import OpenAI
from .models import ConversationState
from .prompts import load_script, get_script_guidance_prompt, get_rag_guidance_prompt, get_recommendation_prompt

logger = logging.getLogger(__name__)

# Load script content at module level
SCRIPT_CONTENT = load_script()

# RAG toggle — set USE_RAG=true in .env to use retrieval-augmented prompts
USE_RAG = os.getenv("USE_RAG", "false").lower() in ("true", "1", "yes")

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
    def __init__(self, api_key: str, base_url: str, model: str):
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model
        self.retriever = None

        if USE_RAG:
            self._init_rag()
            self.system_prompt = None  # built per-request from retrieved sections
        else:
            self.system_prompt = get_script_guidance_prompt(SCRIPT_CONTENT)

    def _init_rag(self):
        """Initialize the RAG pipeline: chunk → embed → retriever.

        Loads pre-built embeddings from disk if available (built via
        `python src/rag/build.py`). Falls back to in-memory embedding
        if no persisted store exists.
        """
        import sys
        # Ensure src/ is importable (needed when running from project root in Docker)
        src_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
        if src_dir not in sys.path:
            sys.path.insert(0, src_dir)

        from rag.chunker import chunk_script
        from rag.store import EmbeddingStore
        from rag.stage_detector import StageDetector
        from rag.retriever import ScriptRetriever

        script_path = os.path.normpath(os.path.join(
            os.path.dirname(__file__), "..", "..", "knowledge_base", "kubecraft_script.md"
        ))
        persist_dir = os.path.normpath(os.path.join(
            os.path.dirname(__file__), "..", "..", "data", "chromadb"
        ))

        # Always need chunks for the stage detector / retriever
        logger.info("RAG: Chunking sales script...")
        chunks = chunk_script(script_path)
        logger.info(f"RAG: {len(chunks)} chunks parsed")

        # Try loading pre-built embeddings from disk
        if os.path.exists(persist_dir):
            store = EmbeddingStore(persist_dir=persist_dir)
            if store.count() > 0:
                logger.info(f"RAG: Loaded {store.count()} pre-built embeddings from {persist_dir}")
            else:
                logger.warning("RAG: Persist dir exists but empty — embedding in-memory")
                store = EmbeddingStore()
                store.add_chunks(chunks)
                logger.info(f"RAG: {store.count()} chunks embedded (in-memory)")
        else:
            logger.info("RAG: No pre-built store found — embedding in-memory (run `python src/rag/build.py` to persist)")
            store = EmbeddingStore()
            store.add_chunks(chunks)
            logger.info(f"RAG: {store.count()} chunks embedded (in-memory)")

        detector = StageDetector()
        self.retriever = ScriptRetriever(store, detector, chunks)
        logger.info("RAG: Pipeline ready")

    def analyze(self, active_text: str, context_text: str = "") -> str:
        # Build user message with context if available
        if context_text:
            user_message = f"<conversation_so_far>\n{context_text}\n</conversation_so_far>\n\n<latest>\n{active_text}\n</latest>"
        else:
            user_message = active_text

        # Build system prompt — RAG retrieves relevant sections per-request
        if self.retriever:
            sections = self.retriever.retrieve(active_text, context_text, top_k=3)
            system_prompt = get_rag_guidance_prompt(sections)
        else:
            system_prompt = self.system_prompt

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=500,
            temperature=0.1,
            timeout=30,
            stop=["<|end|>", "<|end_of_text|>", "<|im_end|>", "\n\n"]
        )
        content = response.choices[0].message.content or ""

        # Clean markdown
        if "```json" in content:
            content = content.split("```json")[1]
        if "```" in content:
            content = content.split("```")[0]

        return content.strip()

    def recommend(self, summary: str, key_points: list[str], stage: str, context_text: str = "") -> str:
        """
        Generate stage-specific recommendations using semantic blueprints.

        Takes the current summary, detected stage, and RAG context to
        produce tailored questions via the appropriate blueprint prompt.
        """
        # Get RAG sections for script context
        rag_sections = []
        if self.retriever and summary:
            rag_sections = self.retriever.retrieve(summary, context_text, top_k=3)

        # Build the stage-specific blueprint prompt
        system_prompt = get_recommendation_prompt(
            stage=stage,
            summary=summary,
            key_points=key_points,
            rag_sections=rag_sections,
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Generate recommendations now."},
            ],
            max_tokens=600,
            temperature=0.2,
            timeout=30,
        )
        content = response.choices[0].message.content or ""

        # Clean markdown
        if "```json" in content:
            content = content.split("```json")[1]
        if "```" in content:
            content = content.split("```")[0]

        return content.strip()


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
        req = AnalysisRequest(active_text, context_text, time.time())
        self.queue.put(req)

    def _worker_loop(self):
        while self.running:
            try:
                req = self.queue.get(timeout=0.5)
                start_time = time.time()
                
                try:
                    raw_json = self.analyzer.analyze(req.active_text, req.context_text)
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
                    logger.error(f"Analysis error: {e}", exc_info=True)
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
