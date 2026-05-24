"""
Chunker for KubeCraft sales script.

Parses the sales script markdown into retrievable chunks for RAG embedding.
Each chunk is a dict with id, text, and metadata fields.

Chunking strategy:
  - Preamble: 4 Beliefs, Pre-Call Checklist, 3 Rules, No-Show Protocol (combined)
  - Parts 1-12: Each ## PART header becomes one chunk
  - Objection core principle: "Use Their Own Words" as standalone chunk
  - Testing objections: standalone chunk
  - Individual objection types: each #### header becomes a chunk
  - Quick Reference + Key Reminders: combined into one reference chunk
"""

import os
import re


def _slugify(text: str) -> str:
    """Convert a section title to a snake_case identifier."""
    text = text.lower().strip()
    # Remove special characters, keep alphanumeric and spaces
    text = re.sub(r"[^a-z0-9\s]", "", text)
    # Collapse whitespace and replace with underscore
    text = re.sub(r"\s+", "_", text.strip())
    return text


def _extract_part_number(header: str) -> int | None:
    """Extract part number from a PART header like '## PART 3: ...'"""
    match = re.search(r"PART\s+(\d+)", header)
    if match:
        return int(match.group(1))
    return None


def _extract_part_short_title(header: str) -> str:
    """Extract short title from header like '## PART 3: Understand Why They're Here' -> 'understand_why_theyre_here'"""
    match = re.search(r"PART\s+\d+:\s*(.+)", header)
    if match:
        return _slugify(match.group(1))
    return _slugify(header)


def chunk_script(script_path: str) -> list[dict]:
    """Parse the sales script into retrievable chunks.

    Args:
        script_path: Path to the kubecraft_script.md file.

    Returns:
        List of chunk dicts, each with 'id', 'text', and 'metadata' keys.
    """
    with open(script_path, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.split("\n")
    chunks = []

    # --- Identify section boundaries ---
    # Find all ## headers and their line indices
    h2_indices = []
    for i, line in enumerate(lines):
        if line.startswith("## ") and not line.startswith("### "):
            h2_indices.append((i, line.strip()))

    # Find all #### headers within Objection Handling for individual objections
    h4_indices = []
    for i, line in enumerate(lines):
        if line.startswith("#### "):
            h4_indices.append((i, line.strip()))

    # --- Build section map from ## headers ---
    sections = []
    for idx, (line_num, header) in enumerate(h2_indices):
        # Determine end of this section (start of next ## header, or end of file)
        if idx + 1 < len(h2_indices):
            end_line = h2_indices[idx + 1][0]
        else:
            end_line = len(lines)
        sections.append(
            {
                "header": header,
                "start": line_num,
                "end": end_line,
                "text": "\n".join(lines[line_num:end_line]).strip(),
            }
        )

    # --- 1. Preamble chunk: everything before PART 1 ---
    preamble_sections = []
    preamble_headers = {"The 4 Beliefs", "Pre-Call Checklist", "The 3 Rules of Sales", "No-Show Protocol"}
    for sec in sections:
        clean_header = sec["header"].lstrip("# ").strip()
        if clean_header in preamble_headers:
            preamble_sections.append(sec["text"])

    if preamble_sections:
        chunks.append(
            {
                "id": "preamble",
                "text": "\n\n".join(preamble_sections),
                "metadata": {
                    "section": "Preamble: 4 Beliefs, Pre-Call Checklist, 3 Rules, No-Show Protocol",
                    "type": "preamble",
                    "part_number": None,
                    "source": "kubecraft_script",
                },
            }
        )

    # --- 2. Part chunks (PART 1 through PART 12) ---
    for sec in sections:
        part_num = _extract_part_number(sec["header"])
        if part_num is not None:
            short_title = _extract_part_short_title(sec["header"])
            chunk_id = f"part_{part_num}_{short_title}"
            section_title = sec["header"].lstrip("# ").strip()
            chunks.append(
                {
                    "id": chunk_id,
                    "text": sec["text"],
                    "metadata": {
                        "section": section_title,
                        "type": "script",
                        "part_number": part_num,
                        "source": "kubecraft_script",
                    },
                }
            )

    # --- 3. Objection Handling section ---
    # Find the "Objection Handling" h2 section
    objection_section = None
    for sec in sections:
        if "Objection Handling" in sec["header"]:
            objection_section = sec
            break

    if objection_section:
        obj_start = objection_section["start"]
        obj_end = objection_section["end"]

        # 3a. Core Principle: "Use Their Own Words" (from ### header to next ### or #### header)
        core_principle_start = None
        core_principle_end = None
        for i in range(obj_start, obj_end):
            if lines[i].startswith("### The Core Principle"):
                core_principle_start = i
            elif (
                core_principle_start is not None
                and (lines[i].startswith("### ") or lines[i].startswith("#### "))
                and i > core_principle_start
            ):
                core_principle_end = i
                break
        if core_principle_start and not core_principle_end:
            core_principle_end = obj_end

        if core_principle_start:
            chunks.append(
                {
                    "id": "objection_core_principle",
                    "text": "\n".join(lines[core_principle_start:core_principle_end]).strip(),
                    "metadata": {
                        "section": "Objection Handling: Core Principle - Use Their Own Words",
                        "type": "objection",
                        "part_number": None,
                        "source": "kubecraft_script",
                    },
                }
            )

        # 3b. Testing Objections
        testing_start = None
        testing_end = None
        for i in range(obj_start, obj_end):
            if lines[i].startswith("### Testing Objections"):
                testing_start = i
            elif (
                testing_start is not None
                and (lines[i].startswith("### ") or lines[i].startswith("#### "))
                and i > testing_start
            ):
                testing_end = i
                break
        if testing_start and not testing_end:
            testing_end = obj_end

        if testing_start:
            chunks.append(
                {
                    "id": "objection_testing",
                    "text": "\n".join(lines[testing_start:testing_end]).strip(),
                    "metadata": {
                        "section": "Objection Handling: Testing Objections",
                        "type": "objection",
                        "part_number": None,
                        "source": "kubecraft_script",
                    },
                }
            )

        # 3c. Individual objection types by #### headers
        # Filter h4 indices to only those within the objection section
        obj_h4s = [(i, h) for i, h in h4_indices if obj_start <= i < obj_end]

        for idx, (line_num, header) in enumerate(obj_h4s):
            # End is next h4 header, or next ### header, or end of objection section
            if idx + 1 < len(obj_h4s):
                end = obj_h4s[idx + 1][0]
            else:
                # Find next ### after this h4
                end = obj_end
                for i in range(line_num + 1, obj_end):
                    if lines[i].startswith("### ") and not lines[i].startswith("#### "):
                        end = i
                        break

            objection_name = header.lstrip("# ").strip()
            slug = _slugify(objection_name)
            # Remove "objection" suffix if it's there to avoid redundancy
            chunk_id = f"objection_{slug}"

            chunks.append(
                {
                    "id": chunk_id,
                    "text": "\n".join(lines[line_num:end]).strip(),
                    "metadata": {
                        "section": f"Objection: {objection_name}",
                        "type": "objection",
                        "part_number": None,
                        "source": "kubecraft_script",
                    },
                }
            )

    # --- 4. Reference chunk: Quick Reference + Key Reminders + Bottom Line ---
    reference_sections = []
    for sec in sections:
        clean = sec["header"].lstrip("# ").strip()
        if "Quick Reference" in clean or "Key Reminders" in clean:
            reference_sections.append(sec["text"])

    # Also grab "The Bottom Line" subsection if it exists within Objection Handling
    if objection_section:
        for i in range(objection_section["start"], objection_section["end"]):
            if lines[i].startswith("### The Bottom Line"):
                bottom_start = i
                bottom_end = objection_section["end"]
                for j in range(i + 1, objection_section["end"]):
                    if lines[j].startswith("## "):
                        bottom_end = j
                        break
                reference_sections.insert(0, "\n".join(lines[bottom_start:bottom_end]).strip())
                break

    if reference_sections:
        chunks.append(
            {
                "id": "reference",
                "text": "\n\n".join(reference_sections),
                "metadata": {
                    "section": "Quick Reference + Key Reminders",
                    "type": "reference",
                    "part_number": None,
                    "source": "kubecraft_script",
                },
            }
        )

    return chunks


def chunk_methodology(methodology_path: str) -> list[dict]:
    """Parse the Hardly Selling methodology into retrievable chunks.

    Chunks are intentionally source-labeled so downstream prompts can explain
    which context layer produced a suggestion.
    """
    with open(methodology_path, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.split("\n")
    chunks = []

    # Chunk every h2 section, with h3 phase/object headers split out where they
    # make retrieval more stage-specific.
    header_indices = []
    for i, line in enumerate(lines):
        if line.startswith("## ") or line.startswith("### "):
            header_indices.append((i, line.strip()))

    for idx, (line_num, header) in enumerate(header_indices):
        end = header_indices[idx + 1][0] if idx + 1 < len(header_indices) else len(lines)
        text = "\n".join(lines[line_num:end]).strip()
        if not text:
            continue

        title = header.lstrip("# ").strip()
        section_type = "methodology"
        if "phase" in title.lower():
            section_type = "methodology_phase"
        elif "buyer" in title.lower() or "archetype" in title.lower():
            section_type = "methodology_archetype"
        elif "objection" in title.lower():
            section_type = "methodology_objection"
        elif "close" in title.lower() or "tie-down" in title.lower():
            section_type = "methodology_close"

        chunks.append(
            {
                "id": f"methodology_{_slugify(title)}",
                "text": text,
                "metadata": {
                    "section": title,
                    "type": section_type,
                    "part_number": None,
                    "source": "hardly_selling_methodology",
                },
            }
        )

    return chunks


def get_chunk_by_id(chunks: list[dict], chunk_id: str) -> dict | None:
    """Get a specific chunk by its ID.

    Args:
        chunks: List of chunk dicts from chunk_script().
        chunk_id: The chunk identifier to search for.

    Returns:
        The matching chunk dict, or None if not found.
    """
    for chunk in chunks:
        if chunk["id"] == chunk_id:
            return chunk
    return None


def get_adjacent_chunks(chunks: list[dict], part_number: int, window: int = 1) -> list[dict]:
    """Get chunks for current part +/- window adjacent parts.

    Args:
        chunks: List of chunk dicts from chunk_script().
        part_number: The center part number (1-12).
        window: Number of adjacent parts to include on each side.

    Returns:
        List of chunks whose part_number falls within [part_number - window, part_number + window].
    """
    low = part_number - window
    high = part_number + window
    return [
        chunk
        for chunk in chunks
        if chunk["metadata"]["part_number"] is not None and low <= chunk["metadata"]["part_number"] <= high
    ]


if __name__ == "__main__":
    # Use path relative to this file's location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(script_dir, "..", "..", "knowledge_base", "kubecraft_script.md")
    script_path = os.path.normpath(script_path)

    chunks = chunk_script(script_path)

    print(f"Total chunks: {len(chunks)}")
    print("=" * 70)
    for chunk in chunks:
        text_preview = chunk["text"][:100].replace("\n", " ")
        print(f"  ID: {chunk['id']}")
        print(f"  Section: {chunk['metadata']['section']}")
        print(f"  Type: {chunk['metadata']['type']}")
        print(f"  Part: {chunk['metadata']['part_number']}")
        print(f"  Length: {len(chunk['text'])} chars")
        print(f"  Preview: {text_preview}...")
        print("-" * 70)

    # Test helper functions
    print("\n--- get_chunk_by_id test ---")
    c = get_chunk_by_id(chunks, "part_7_acknowledge_the_gap_now_tiedown")
    if c:
        print(f"Found: {c['metadata']['section']}")
    else:
        # Try finding a part 7 chunk by iteration
        for ch in chunks:
            if ch["metadata"].get("part_number") == 7:
                print(f"Part 7 chunk ID is actually: {ch['id']}")
                break

    print("\n--- get_adjacent_chunks test (part 5, window=1) ---")
    adj = get_adjacent_chunks(chunks, 5, window=1)
    for a in adj:
        print(f"  Part {a['metadata']['part_number']}: {a['metadata']['section']}")
