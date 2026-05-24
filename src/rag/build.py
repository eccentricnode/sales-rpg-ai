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
# ruff: noqa: E402

import argparse
import os
import shutil
import sys
import time

# Ensure src/ is importable
src_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from rag.chunker import chunk_methodology, chunk_script
from rag.store import EmbeddingStore

# Default paths
SCRIPT_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "knowledge_base", "kubecraft_script.md")
)
METHODOLOGY_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "knowledge_base", "hardly_selling_methodology.md")
)
PERSIST_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "chromadb"))


def _sync_collection(store: EmbeddingStore, chunks: list[dict], collection_name: str, force: bool) -> bool:
    """Ensure one collection contains exactly the chunk count expected."""
    existing = store.count()
    if existing > 0 and not force:
        if existing == len(chunks):
            print(f"         {collection_name} already has {existing} chunks (up to date)")
            return False
        print(f"         {collection_name} has {existing} chunks but source has {len(chunks)} — rebuilding...")
        store._client.delete_collection(collection_name)
        store._collection = store._client.get_or_create_collection(
            name=collection_name,
            embedding_function=store._embedding_fn,
        )

    store.add_chunks(chunks)
    return True


def build(
    script_path: str = SCRIPT_PATH,
    methodology_path: str = METHODOLOGY_PATH,
    persist_dir: str = PERSIST_DIR,
    force: bool = False,
):
    """Chunk the sales script and Hardly Selling methodology, embed, and persist."""
    print("RAG Embedding Builder")
    print(f"{'=' * 50}")
    print(f"  Script:       {script_path}")
    print(f"  Methodology:  {methodology_path}")
    print(f"  Store:        {persist_dir}")
    print()

    # Force rebuild: wipe existing store
    if force and os.path.exists(persist_dir):
        print("  Removing existing store (--force)...")
        shutil.rmtree(persist_dir)

    # Ensure directory exists
    os.makedirs(persist_dir, exist_ok=True)

    # Chunk
    print("  [1/3] Chunking sources...")
    start = time.time()
    chunks = chunk_script(script_path)
    methodology_chunks = []
    if os.path.exists(methodology_path):
        methodology_chunks = chunk_methodology(methodology_path)
    else:
        print("         WARNING: methodology source not found; Layer 2 will be disabled")
    print(
        f"         {len(chunks)} script chunks, {len(methodology_chunks)} methodology chunks in {time.time() - start:.1f}s"
    )

    # Embed + persist
    print("  [2/3] Embedding and persisting...")
    start = time.time()
    store = EmbeddingStore(collection_name="sales_script", persist_dir=persist_dir)
    changed = _sync_collection(store, chunks, "sales_script", force=force)
    methodology_store = None
    if methodology_chunks:
        methodology_store = EmbeddingStore(collection_name="hardly_selling_methodology", persist_dir=persist_dir)
        changed = (
            _sync_collection(
                methodology_store,
                methodology_chunks,
                "hardly_selling_methodology",
                force=force,
            )
            or changed
        )

    if not changed:
        print("         Use --force to rebuild from scratch")
        print("\n  Done (no changes needed)")
        return
    total_chunks = store.count() + (methodology_store.count() if methodology_store else 0)
    print(f"         {total_chunks} chunks embedded in {time.time() - start:.1f}s")

    # Verify
    print("  [3/3] Verifying...")
    test_results = store.query("That's too expensive", top_k=3)
    print(f"         Test query returned {len(test_results)} results:")
    for r in test_results:
        section = r["metadata"].get("section", "?")
        print(f"           [{r['distance']:.3f}] {section}")
    if methodology_store is not None:
        test_results = methodology_store.query("go deeper into problem development", top_k=2)
        print(f"         Methodology query returned {len(test_results)} results:")
        for r in test_results:
            section = r["metadata"].get("section", "?")
            print(f"           [{r['distance']:.3f}] {section}")

    print(f"\n  Done. Embeddings persisted to {persist_dir}")
    print("  The app will load these automatically on next startup.")


def main():
    parser = argparse.ArgumentParser(description="Build RAG embedding store")
    parser.add_argument("--force", action="store_true", help="Rebuild from scratch")
    parser.add_argument("--script", default=SCRIPT_PATH, help="Path to sales script")
    parser.add_argument("--methodology", default=METHODOLOGY_PATH, help="Path to Hardly Selling methodology source")
    parser.add_argument("--output", default=PERSIST_DIR, help="ChromaDB persist directory")
    args = parser.parse_args()

    build(script_path=args.script, methodology_path=args.methodology, persist_dir=args.output, force=args.force)


if __name__ == "__main__":
    main()
