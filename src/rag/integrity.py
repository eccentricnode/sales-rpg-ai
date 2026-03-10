"""
Knowledge base integrity check for RAG pipeline.

Validates that knowledge base files exist, are non-empty, and have not
been tampered with since the last known-good state. Designed to run on
application startup before building or loading embeddings.
"""

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default knowledge base directory (relative to project root)
_PROJECT_ROOT = Path(__file__).parent.parent.parent
_DEFAULT_KB_DIR = _PROJECT_ROOT / "knowledge_base"
_CHECKSUM_FILE = _PROJECT_ROOT / "data" / "kb_checksums.json"


def _compute_file_checksum(file_path: Path) -> str:
    """Compute SHA-256 checksum of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            sha256.update(block)
    return sha256.hexdigest()


def verify_knowledge_base(
    kb_dir: Optional[Path] = None,
    checksum_file: Optional[Path] = None,
) -> dict:
    """Verify the integrity of knowledge base files on startup.

    Performs three checks:
    1. All expected files exist
    2. All files are non-empty
    3. If a checksum manifest exists, file checksums match

    Args:
        kb_dir: Path to the knowledge base directory. Defaults to
                ``<project_root>/knowledge_base/``.
        checksum_file: Path to the checksum manifest JSON file. Defaults to
                       ``<project_root>/data/kb_checksums.json``.

    Returns:
        A dict with keys:
        - ``valid`` (bool): True if all checks passed
        - ``files_checked`` (int): Number of files verified
        - ``errors`` (list[str]): List of error messages (empty if valid)
    """
    kb_dir = kb_dir or _DEFAULT_KB_DIR
    checksum_file = checksum_file or _CHECKSUM_FILE

    errors: list[str] = []
    files_checked = 0

    # Check 1: Knowledge base directory exists
    if not kb_dir.exists():
        errors.append(f"Knowledge base directory not found: {kb_dir}")
        return {"valid": False, "files_checked": 0, "errors": errors}

    # Check 2: Find all knowledge base files
    kb_files = list(kb_dir.glob("*.md")) + list(kb_dir.glob("*.txt"))
    if not kb_files:
        errors.append(f"No knowledge base files found in {kb_dir}")
        return {"valid": False, "files_checked": 0, "errors": errors}

    # Check 3: All files are non-empty
    for kb_file in kb_files:
        files_checked += 1
        if kb_file.stat().st_size == 0:
            errors.append(f"Empty knowledge base file: {kb_file.name}")

    # Check 4: Checksum verification (if manifest exists)
    if checksum_file.exists():
        try:
            with open(checksum_file, "r") as f:
                known_checksums = json.load(f)

            for filename, expected_hash in known_checksums.items():
                file_path = kb_dir / filename
                if not file_path.exists():
                    errors.append(f"Missing file referenced in checksum manifest: {filename}")
                    continue

                actual_hash = _compute_file_checksum(file_path)
                if actual_hash != expected_hash:
                    errors.append(
                        f"Checksum mismatch for {filename}: "
                        f"expected {expected_hash[:12]}..., got {actual_hash[:12]}..."
                    )
        except (json.JSONDecodeError, KeyError) as e:
            errors.append(f"Invalid checksum manifest: {e}")

    result = {
        "valid": len(errors) == 0,
        "files_checked": files_checked,
        "errors": errors,
    }

    if result["valid"]:
        logger.info(
            f"Knowledge base integrity check passed: {files_checked} files verified"
        )
    else:
        logger.warning(
            f"Knowledge base integrity check FAILED: {errors}"
        )

    return result


def integrity_check(kb_dir: Optional[Path] = None) -> bool:
    """Convenience wrapper that returns True/False for startup checks.

    Args:
        kb_dir: Path to the knowledge base directory.

    Returns:
        True if the knowledge base passes integrity verification.
    """
    result = verify_knowledge_base(kb_dir=kb_dir)
    return result["valid"]


def generate_checksums(
    kb_dir: Optional[Path] = None,
    checksum_file: Optional[Path] = None,
) -> dict[str, str]:
    """Generate and save a checksum manifest for the current knowledge base state.

    Run this after updating knowledge base files to create a new baseline.

    Args:
        kb_dir: Path to the knowledge base directory.
        checksum_file: Path to save the checksum manifest.

    Returns:
        Dict mapping filename to SHA-256 hex digest.
    """
    kb_dir = kb_dir or _DEFAULT_KB_DIR
    checksum_file = checksum_file or _CHECKSUM_FILE

    checksums: dict[str, str] = {}
    for kb_file in sorted(kb_dir.glob("*.md")) + sorted(kb_dir.glob("*.txt")):
        checksums[kb_file.name] = _compute_file_checksum(kb_file)

    # Ensure output directory exists
    checksum_file.parent.mkdir(parents=True, exist_ok=True)

    with open(checksum_file, "w") as f:
        json.dump(checksums, f, indent=2)

    logger.info(f"Generated checksums for {len(checksums)} files -> {checksum_file}")
    return checksums


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--generate":
        checksums = generate_checksums()
        print(f"Generated checksums for {len(checksums)} files")
        for name, digest in checksums.items():
            print(f"  {name}: {digest[:16]}...")
    else:
        result = verify_knowledge_base()
        print(f"Valid: {result['valid']}")
        print(f"Files checked: {result['files_checked']}")
        if result["errors"]:
            print("Errors:")
            for err in result["errors"]:
                print(f"  - {err}")
        sys.exit(0 if result["valid"] else 1)
