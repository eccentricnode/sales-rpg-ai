"""
Hybrid retriever combining stage-based (deterministic) and semantic
(embedding) retrieval for the KubeCraft sales script.

Strategy:
  1. Detect the call stage from the active utterance.
  2. If stage confidence is strong (>0.3):
     a. Pull the current Part +/- 1 adjacent Parts (deterministic).
     b. Pull top semantic matches NOT already in the adjacent set.
     c. Merge and return.
  3. If no stage match (fallback):
     a. Pure semantic retrieval using active text + trailing context.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .stage_detector import StageDetector

if TYPE_CHECKING:
    from .store import EmbeddingStore


# Minimum confidence from StageDetector to trust stage-based retrieval.
_STAGE_CONFIDENCE_THRESHOLD = 0.3

# How many characters of context_text tail to append for semantic queries.
_CONTEXT_TAIL_LENGTH = 200


class ScriptRetriever:
    """Hybrid retriever: stage-based deterministic + semantic embedding lookup.

    Supports multi-source retrieval by adding additional embedding stores
    via ``add_source()``.  The primary ``store`` (passed at init) is always
    queried; any extra sources added later are queried in parallel and their
    results merged by distance.
    """

    def __init__(
        self,
        store: EmbeddingStore,
        detector: StageDetector,
        chunks: list[dict],
        sources: list["EmbeddingStore"] | None = None,
    ) -> None:
        """
        Args:
            store: The primary embedding store with indexed chunks.
            detector: Stage detector for keyword-based detection.
            chunks: The raw chunk list (for adjacent section lookup).
            sources: Optional additional embedding stores to query alongside
                     the primary store (e.g. methodology knowledge base).
        """
        self.store = store
        self.detector = detector
        self.chunks = chunks
        self.last_stage: str | None = None
        self._extra_sources: list["EmbeddingStore"] = list(sources) if sources else []

    # ------------------------------------------------------------------
    # Multi-source management
    # ------------------------------------------------------------------

    def add_source(self, source: "EmbeddingStore") -> None:
        """Register an additional embedding store for multi-source retrieval.

        Args:
            source: An ``EmbeddingStore`` instance (e.g. Hardly Selling
                    methodology index) that will be queried alongside
                    the primary store on every retrieval call.
        """
        self._extra_sources.append(source)

    def retrieve(
        self,
        active_text: str,
        context_text: str = "",
        top_k: int = 3,
    ) -> list[str]:
        """
        Hybrid retrieval returning chunk text strings ordered by relevance.

        Args:
            active_text: The latest utterance to match against.
            context_text: Broader conversation context (optional).
            top_k: Maximum number of chunks to return.

        Returns:
            List of chunk text strings, ordered by relevance.
        """
        results = self.retrieve_with_metadata(active_text, context_text, top_k)
        return [r["text"] for r in results]

    def retrieve_with_metadata(
        self,
        active_text: str,
        context_text: str = "",
        top_k: int = 3,
    ) -> list[dict]:
        """
        Hybrid retrieval returning full chunk dicts with metadata.

        Each dict contains at minimum: {"id", "text", "metadata"}.

        Args:
            active_text: The latest utterance to match against.
            context_text: Broader conversation context (optional).
            top_k: Maximum number of chunks to return.

        Returns:
            List of chunk dicts ordered by relevance.
        """
        if not active_text or not active_text.strip():
            return []

        # Step 1: Detect stage (with continuity from last turn).
        # Feed the detector the recent context + latest utterance so it sees
        # the rep's stage-signaling keywords, not just the prospect's reply.
        detect_text = active_text
        if context_text:
            # Use the tail of context (last ~500 chars) + active text
            context_tail = context_text[-500:] if len(context_text) > 500 else context_text
            detect_text = context_tail + "\n" + active_text
        stage, confidence = self.detector.detect(detect_text, current_stage=self.last_stage)

        # Update last_stage for next turn's continuity bias.
        if stage is not None:
            self.last_stage = stage

        # Step 2: Branch on confidence.
        if confidence >= _STAGE_CONFIDENCE_THRESHOLD and stage is not None:
            return self._hybrid_retrieve(active_text, context_text, stage, top_k)
        else:
            # Low confidence — use last_stage for deterministic retrieval if available
            if self.last_stage is not None:
                return self._hybrid_retrieve(active_text, context_text, self.last_stage, top_k)
            return self._semantic_fallback(active_text, context_text, top_k)

    # ------------------------------------------------------------------
    # Internal retrieval strategies
    # ------------------------------------------------------------------

    def _hybrid_retrieve(
        self,
        active_text: str,
        context_text: str,
        stage: str,
        top_k: int,
    ) -> list[dict]:
        """
        Stage-aware hybrid retrieval.

        1. Get chunks from current Part +/- 1 adjacent Parts (deterministic).
        2. Fill remaining slots with semantic matches not already included.
        """
        part_number = self.detector.get_part_number(stage)

        # --- Deterministic: adjacent chunks ---
        adjacent = self._get_adjacent_chunks(part_number, window=1)

        # Cap deterministic results so we leave room for semantic diversity.
        max_deterministic = max(1, top_k - 1)
        deterministic_results = adjacent[:max_deterministic]
        seen_ids = {chunk.get("id") for chunk in deterministic_results}

        # --- Semantic: diverse results from the embedding store ---
        semantic_slots = top_k - len(deterministic_results)
        if semantic_slots > 0:
            # Ask for extra candidates to compensate for overlap filtering.
            query_text = self._build_semantic_query(active_text, context_text)
            candidates = self._safe_store_query(
                query_text,
                top_k=semantic_slots + len(seen_ids) + 2,
            )
            for candidate in candidates:
                if len(deterministic_results) >= top_k:
                    break
                if candidate.get("id") not in seen_ids:
                    deterministic_results.append(candidate)
                    seen_ids.add(candidate.get("id"))

        return deterministic_results[:top_k]

    def _semantic_fallback(
        self,
        active_text: str,
        context_text: str,
        top_k: int,
    ) -> list[dict]:
        """Pure semantic retrieval when stage detection has low confidence."""
        query_text = self._build_semantic_query(active_text, context_text)
        results = self._safe_store_query(query_text, top_k=top_k)
        return self._deduplicate(results)[:top_k]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_adjacent_chunks(
        self, part_number: int | None, window: int = 1
    ) -> list[dict]:
        """
        Return chunks from the current part and its neighbors.

        For objection handling (part_number=None), returns chunks tagged
        with 'objection' in their metadata section field.
        """
        if not self.chunks:
            return []

        if part_number is None:
            # Objection handling -- find chunks with objection-related sections.
            return [
                chunk
                for chunk in self.chunks
                if "objection" in chunk.get("metadata", {}).get("section", "").lower()
            ]

        # Collect chunks whose part_number falls within [part - window, part + window].
        lower = max(1, part_number - window)
        upper = part_number + window
        adjacent = []
        for chunk in self.chunks:
            chunk_part = chunk.get("metadata", {}).get("part_number")
            if chunk_part is not None and lower <= chunk_part <= upper:
                adjacent.append(chunk)

        return adjacent

    def _build_semantic_query(self, active_text: str, context_text: str) -> str:
        """
        Build the query string for semantic search.

        Combines the active utterance with the tail of the context for
        better embedding similarity.
        """
        query = active_text.strip()
        if context_text:
            tail = context_text.strip()[-_CONTEXT_TAIL_LENGTH:]
            if tail:
                query = f"{query} {tail}"
        return query

    def _safe_store_query(
        self, text: str, top_k: int = 3, where: dict | None = None
    ) -> list[dict]:
        """
        Query all registered embedding stores with error handling.

        Queries the primary store and every extra source added via
        ``add_source()``, merges results by distance, and returns the
        top-k closest matches across all sources.

        Returns an empty list if every store is unavailable or errors out,
        ensuring the retriever degrades gracefully.
        """
        all_results: list[dict] = []

        # Query primary store
        try:
            all_results.extend(self.store.query(text, top_k=top_k, where=where))
        except Exception:
            pass

        # Query extra sources (methodology, etc.)
        for source in self._extra_sources:
            try:
                all_results.extend(source.query(text, top_k=top_k, where=where))
            except Exception:
                pass

        # Sort by distance (closest first) and return top_k
        all_results.sort(key=lambda r: r.get("distance", float("inf")))
        return all_results[:top_k] if len(all_results) > top_k else all_results

    @staticmethod
    def _deduplicate(chunks: list[dict]) -> list[dict]:
        """Remove duplicate chunks by id, preserving order."""
        seen: set[str] = set()
        unique: list[dict] = []
        for chunk in chunks:
            chunk_id = chunk.get("id", id(chunk))
            if chunk_id not in seen:
                seen.add(chunk_id)
                unique.append(chunk)
        return unique


if __name__ == "__main__":
    # Quick integration test -- requires store.py and chunker.py to be built.
    from .chunker import chunk_script
    from .store import EmbeddingStore

    chunks = chunk_script("../../knowledge_base/kubecraft_script.md")
    store = EmbeddingStore()
    store.add_chunks(chunks)
    detector = StageDetector()
    retriever = ScriptRetriever(store, detector, chunks)

    test_cases = [
        "That sounds really expensive for what you're offering",
        "What motivated you to book this call today?",
        "I need to talk to my wife about this first",
        "Can you tell me more about the HomeLab OS?",
        "I'm feeling pretty good about everything, maybe an 8 out of 10",
    ]

    for query in test_cases:
        print(f"\nQuery: {query}")
        stage, conf = detector.detect(query)
        print(f"  Stage: {stage} (confidence: {conf:.2f})")
        results = retriever.retrieve_with_metadata(query)
        for r in results:
            section = r.get("metadata", {}).get("section", "unknown")
            text_preview = r.get("text", "")[:80]
            print(f"  -> [{section}] {text_preview}...")
