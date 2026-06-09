"""
Embedding store for RAG retrieval.

Wraps ChromaDB + sentence-transformers into a simple interface for storing
and querying sales script chunks. Uses all-MiniLM-L6-v2 (384 dims) for
generating embeddings.
"""

import chromadb
from chromadb.utils import embedding_functions


class EmbeddingStore:
    """Vector store backed by ChromaDB with sentence-transformer embeddings."""

    def __init__(
        self,
        collection_name: str = "sales_script",
        persist_dir: str | None = None,
    ):
        """Initialize ChromaDB client and collection.

        Args:
            collection_name: Name of the ChromaDB collection.
            persist_dir: If None, use in-memory (ephemeral) storage.
                         If set, persist embeddings to this directory.
        """
        self._embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )

        if persist_dir:
            self._client = chromadb.PersistentClient(path=persist_dir)
        else:
            self._client = chromadb.EphemeralClient()

        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=self._embedding_fn,
        )

    def add_chunks(self, chunks: list[dict]) -> None:
        """Embed and store chunks in the collection.

        Args:
            chunks: List of chunk dicts, each with 'id', 'text', and 'metadata'.
                    Metadata values must be str, int, float, or bool for ChromaDB.
        """
        if not chunks:
            return

        ids = []
        documents = []
        metadatas = []

        for chunk in chunks:
            ids.append(chunk["id"])
            documents.append(chunk["text"])
            # ChromaDB metadata values must be str, int, float, or bool.
            # Convert None values to empty string.
            clean_meta = {}
            for k, v in chunk["metadata"].items():
                if v is None:
                    clean_meta[k] = ""
                else:
                    clean_meta[k] = v
            metadatas.append(clean_meta)

        self._collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

    def query(
        self,
        text: str,
        top_k: int = 3,
        where: dict | None = None,
    ) -> list[dict]:
        """Query the store for similar chunks.

        Args:
            text: Query text to find similar chunks for.
            top_k: Number of results to return.
            where: Optional ChromaDB metadata filter, e.g. {"type": "objection"}.

        Returns:
            List of result dicts, each with 'id', 'text', 'metadata', 'distance'.
            Results are sorted by distance (closest first).
        """
        kwargs = {
            "query_texts": [text],
            "n_results": min(top_k, self._collection.count()),
        }
        if where:
            kwargs["where"] = where

        results = self._collection.query(**kwargs)

        output = []
        for i in range(len(results["ids"][0])):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            # Restore None for empty part_number strings
            if meta.get("part_number") == "":
                meta["part_number"] = None
            output.append({
                "id": results["ids"][0][i],
                "text": results["documents"][0][i],
                "metadata": meta,
                "distance": results["distances"][0][i],
            })

        return output

    def count(self) -> int:
        """Return number of stored chunks."""
        return self._collection.count()


if __name__ == "__main__":
    import os
    from chunker import chunk_script

    # Resolve script path relative to this file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(script_dir, "..", "..", "knowledge_base", "kubecraft_script.md")
    script_path = os.path.normpath(script_path)

    chunks = chunk_script(script_path)
    store = EmbeddingStore()
    store.add_chunks(chunks)
    print(f"Stored {store.count()} chunks")

    # Test queries
    print("\n--- Query: 'That's too expensive' ---")
    results = store.query("That's too expensive")
    for r in results:
        print(f"  [{r['distance']:.3f}] {r['id']}: {r['text'][:80]}...")

    print("\n--- Query: 'spouse needs to agree' (filtered to objections) ---")
    results = store.query("spouse needs to agree", where={"type": "objection"})
    for r in results:
        print(f"  [{r['distance']:.3f}] {r['id']}: {r['text'][:80]}...")

    print("\n--- Query: 'how to open the call' ---")
    results = store.query("how to open the call")
    for r in results:
        print(f"  [{r['distance']:.3f}] {r['id']}: {r['text'][:80]}...")

    print("\n--- Query: 'customer wants to think about it' ---")
    results = store.query("customer wants to think about it", where={"type": "objection"})
    for r in results:
        print(f"  [{r['distance']:.3f}] {r['id']}: {r['text'][:80]}...")
