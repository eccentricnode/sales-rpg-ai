#!/usr/bin/env python3
"""
Build (or rebuild) the RAG embedding store.

Run this once after changing the sales script, like a database migration.
The app will load the pre-built embeddings from disk instead of
re-embedding on every startup.

Usage:
    python src/rag/build.py              # Build embeddings
    python src/rag/build.py --force      # Rebuild from scratch
    python -m rag.build                  # If src/ is in PYTHONPATH
"""

import argparse
import os
import shutil
import sys
import time

# Ensure src/ is importable
src_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from rag.chunker import chunk_script
from rag.store import EmbeddingStore

# Default paths
SCRIPT_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "knowledge_base", "kubecraft_script.md")
)
PERSIST_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "chromadb")
)


def build(script_path: str = SCRIPT_PATH, persist_dir: str = PERSIST_DIR, force: bool = False):
    """Chunk the sales script, embed, and persist to disk."""
    print(f"RAG Embedding Builder")
    print(f"{'=' * 50}")
    print(f"  Script:    {script_path}")
    print(f"  Store:     {persist_dir}")
    print()

    # Force rebuild: wipe existing store
    if force and os.path.exists(persist_dir):
        print("  Removing existing store (--force)...")
        shutil.rmtree(persist_dir)

    # Ensure directory exists
    os.makedirs(persist_dir, exist_ok=True)

    # Chunk
    print("  [1/3] Chunking script...")
    start = time.time()
    chunks = chunk_script(script_path)
    print(f"         {len(chunks)} chunks in {time.time() - start:.1f}s")

    # Embed + persist
    print("  [2/3] Embedding and persisting...")
    start = time.time()
    store = EmbeddingStore(persist_dir=persist_dir)

    # If store already has data and not forced, check if counts match
    existing = store.count()
    if existing > 0 and not force:
        if existing == len(chunks):
            print(f"         Store already has {existing} chunks (up to date)")
            print(f"         Use --force to rebuild from scratch")
            print(f"\n  Done (no changes needed)")
            return
        else:
            print(f"         Store has {existing} chunks but script has {len(chunks)} — rebuilding...")
            # Delete and recreate collection
            store._client.delete_collection("sales_script")
            store._collection = store._client.get_or_create_collection(
                name="sales_script",
                embedding_function=store._embedding_fn,
            )

    store.add_chunks(chunks)
    print(f"         {store.count()} chunks embedded in {time.time() - start:.1f}s")

    # Verify
    print("  [3/3] Verifying...")
    test_results = store.query("That's too expensive", top_k=3)
    print(f"         Test query returned {len(test_results)} results:")
    for r in test_results:
        section = r["metadata"].get("section", "?")
        print(f"           [{r['distance']:.3f}] {section}")

    print(f"\n  Done. Embeddings persisted to {persist_dir}")
    print(f"  The app will load these automatically on next startup.")


def main():
    parser = argparse.ArgumentParser(description="Build RAG embedding store")
    parser.add_argument("--force", action="store_true", help="Rebuild from scratch")
    parser.add_argument("--script", default=SCRIPT_PATH, help="Path to sales script")
    parser.add_argument("--output", default=PERSIST_DIR, help="ChromaDB persist directory")
    args = parser.parse_args()

    build(script_path=args.script, persist_dir=args.output, force=args.force)


if __name__ == "__main__":
    main()
