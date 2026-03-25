#!/usr/bin/env python3
"""Extract a page map from a PDF using opendataloader-pdf.

Produces a compact JSON mapping sections, figures, and tables to page numbers,
enabling targeted PDF reading by the analysis agent.

Usage: python3 extract_page_map.py "/path/to/paper.pdf"
Output: JSON to stdout and /tmp/manuscript_page_map.json
"""

import json
import os
import re
import sys
import tempfile


def run_opendataloader(pdf_path):
    """Run opendataloader-pdf and return the parsed JSON."""
    try:
        import opendataloader_pdf
    except ImportError:
        return None, "opendataloader-pdf not installed (pip install opendataloader-pdf)"

    output_dir = tempfile.mkdtemp(prefix="odl_")
    try:
        # Suppress Java log output that opendataloader writes to stdout/stderr
        import io
        import contextlib
        with contextlib.redirect_stdout(io.StringIO()), \
             contextlib.redirect_stderr(io.StringIO()):
            opendataloader_pdf.convert(
                input_path=pdf_path,
                output_dir=output_dir,
                format="json",
            )
    except Exception as e:
        return None, f"opendataloader-pdf failed: {e}"

    basename = os.path.splitext(os.path.basename(pdf_path))[0]
    json_path = os.path.join(output_dir, f"{basename}.json")
    if not os.path.exists(json_path):
        return None, f"Expected output not found at {json_path}"

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data, None


REFERENCE_HEADINGS = re.compile(
    r"^(references|bibliography|works cited|literature cited|ref[eé]rences)$", re.I
)
FIGURE_CAPTION = re.compile(r"^(figure|fig\.?)\s+\d", re.I)
TABLE_CAPTION = re.compile(r"^table\s+\d", re.I)


def build_page_map(data):
    """Build a compact page map from opendataloader elements."""
    kids = data.get("kids", [])
    total_pages = data.get("number of pages", 0)

    # Extract headings
    headings = []
    for el in kids:
        if el.get("type") == "heading":
            level = el.get("heading level")
            if level is not None:
                try:
                    level = int(level)
                except (ValueError, TypeError):
                    continue
                headings.append({
                    "heading": el.get("content", "").strip(),
                    "level": level,
                    "page": el.get("page number"),
                    "bbox": el.get("bounding box"),
                })

    # Build sections with page ranges
    sections = []
    for i, h in enumerate(headings):
        section = {
            "heading": h["heading"][:100],
            "level": h["level"],
            "start_page": h["page"],
        }
        # Find end page: page before the next heading of same or higher level
        end_page = total_pages
        for j in range(i + 1, len(headings)):
            if headings[j]["level"] <= h["level"]:
                # Section ends on the page before this next heading
                # (or same page if they share a page)
                end_page = max(h["page"], headings[j]["page"] - 1)
                break
        section["end_page"] = end_page
        sections.append(section)

    # Find figures and tables
    figures = []
    tables = []

    for el in kids:
        el_type = el.get("type", "")
        page = el.get("page number")
        bbox = el.get("bounding box")
        content = el.get("content", "").strip()

        if el_type == "image" and bbox:
            # Skip tiny images (logos, icons) — require minimum area
            if len(bbox) == 4:
                width = abs(bbox[2] - bbox[0])
                height = abs(bbox[3] - bbox[1])
                if width > 100 and height > 100:
                    # Look for a nearby caption
                    caption = _find_nearby_caption(kids, el, "figure")
                    figures.append({
                        "page": page,
                        "bbox": bbox,
                        "caption_preview": caption[:100] if caption else None,
                    })

        elif el_type == "table" and bbox:
            caption = _find_nearby_caption(kids, el, "table")
            tables.append({
                "page": page,
                "bbox": bbox,
                "caption_preview": caption[:100] if caption else None,
            })

    # Also find figure/table captions in paragraphs (opendataloader sometimes
    # marks captions as paragraphs, and the actual figure as a preceding image)
    for el in kids:
        if el.get("type") in ("paragraph", "caption"):
            content = el.get("content", "").strip()
            page = el.get("page number")
            if FIGURE_CAPTION.match(content):
                # Check we don't already have a figure on this page with this caption
                if not any(f["page"] == page and f.get("caption_preview", "").startswith(content[:30])
                           for f in figures):
                    figures.append({
                        "page": page,
                        "bbox": el.get("bounding box"),
                        "caption_preview": content[:100],
                    })
            elif TABLE_CAPTION.match(content):
                if not any(t["page"] == page and t.get("caption_preview", "").startswith(content[:30])
                           for t in tables):
                    tables.append({
                        "page": page,
                        "bbox": el.get("bounding box"),
                        "caption_preview": content[:100],
                    })

    # Build page summary
    page_summary = {
        "title_page": [1],
        "abstract": [],
        "references": [],
        "figures": sorted(set(f["page"] for f in figures)),
        "tables": sorted(set(t["page"] for t in tables)),
    }

    for s in sections:
        heading_lower = s["heading"].lower().strip()
        if heading_lower == "abstract":
            page_summary["abstract"] = [s["start_page"]]
        elif REFERENCE_HEADINGS.match(heading_lower):
            page_summary["references"] = list(range(s["start_page"], s["end_page"] + 1))

    return {
        "available": True,
        "total_pages": total_pages,
        "sections": sections,
        "figures": figures,
        "tables": tables,
        "page_summary": page_summary,
    }


def _find_nearby_caption(kids, target_el, caption_type):
    """Find a caption-like paragraph near a figure/table element."""
    target_page = target_el.get("page number")
    target_idx = None
    for i, el in enumerate(kids):
        if el is target_el:
            target_idx = i
            break
    if target_idx is None:
        return None

    pattern = FIGURE_CAPTION if caption_type == "figure" else TABLE_CAPTION

    # Search nearby elements (within 3 positions before/after)
    for offset in [1, -1, 2, -2, 3, -3]:
        idx = target_idx + offset
        if 0 <= idx < len(kids):
            el = kids[idx]
            if el.get("page number") == target_page:
                content = el.get("content", "").strip()
                if el.get("type") in ("caption", "paragraph") and pattern.match(content):
                    return content
    return None


def main():
    if len(sys.argv) < 2:
        print("Usage: extract_page_map.py <pdf_path>", file=sys.stderr)
        sys.exit(1)

    pdf_path = sys.argv[1]
    if not os.path.exists(pdf_path):
        result = {"available": False, "error": f"PDF not found: {pdf_path}"}
        print(json.dumps(result, indent=2))
        sys.exit(0)

    data, error = run_opendataloader(pdf_path)
    if error:
        result = {"available": False, "error": error}
        print(json.dumps(result, indent=2))
        with open("/tmp/manuscript_page_map.json", "w") as f:
            json.dump(result, f, indent=2)
        sys.exit(0)

    page_map = build_page_map(data)

    output = json.dumps(page_map, indent=2, ensure_ascii=False)
    print(output)
    with open("/tmp/manuscript_page_map.json", "w") as f:
        f.write(output)

    print(f"Page map written to /tmp/manuscript_page_map.json", file=sys.stderr)


if __name__ == "__main__":
    main()
