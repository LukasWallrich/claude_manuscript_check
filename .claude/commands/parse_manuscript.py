#!/usr/bin/env python3
"""
Parse a PDF manuscript via GROBID and output structured JSON to stdout.

Usage:
    python3 parse_manuscript.py "/path/to/paper.pdf"

Sends the PDF to the GROBID API, parses the returned TEI XML, and produces
a JSON report containing metadata, sections, figures, bibliography,
in-text citations, and a cross-reference quality report.

This script uses only the Python standard library (no external dependencies).
"""

import json
import os
import re
import sys
import uuid
import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from collections import defaultdict

GROBID_URL = "https://kermitt2-grobid.hf.space/api/processFulltextDocument"
GROBID_REFS_URL = "https://kermitt2-grobid.hf.space/api/processReferences"
TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_NS = "http://www.w3.org/XML/1998/namespace"

NS = {"tei": TEI_NS, "xml": XML_NS}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ns(tag):
    """Return a namespace-qualified tag name."""
    return f"{{{TEI_NS}}}{tag}"


def _xml_attr(element, attr):
    """Get an attribute in the xml: namespace (e.g. xml:id)."""
    return element.get(f"{{{XML_NS}}}{attr}")


def _all_text(element):
    """Recursively collect all text content from an element and its children."""
    if element is None:
        return ""
    parts = []
    if element.text:
        parts.append(element.text)
    for child in element:
        parts.append(_all_text(child))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts).strip()


def _build_multipart_body(pdf_path):
    """Build a multipart/form-data body for uploading the PDF."""
    boundary = f"----PythonBoundary{uuid.uuid4().hex}"
    body_parts = []

    filename = os.path.basename(pdf_path)
    with open(pdf_path, "rb") as f:
        file_data = f.read()

    body_parts.append(f"--{boundary}\r\n".encode())
    body_parts.append(
        f'Content-Disposition: form-data; name="input"; filename="{filename}"\r\n'.encode()
    )
    body_parts.append(b"Content-Type: application/pdf\r\n\r\n")
    body_parts.append(file_data)
    body_parts.append(b"\r\n")
    body_parts.append(f"--{boundary}--\r\n".encode())

    body = b"".join(body_parts)
    content_type = f"multipart/form-data; boundary={boundary}"
    return body, content_type


def _send_to_grobid(pdf_path):
    """Send a PDF to GROBID and return the TEI XML string."""
    body, content_type = _build_multipart_body(pdf_path)
    req = urllib.request.Request(
        GROBID_URL,
        data=body,
        headers={"Content-Type": content_type},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        return resp.read().decode("utf-8")


def _send_to_grobid_references(pdf_path):
    """Send a PDF to GROBID's dedicated references endpoint and return TEI XML."""
    body, content_type = _build_multipart_body(pdf_path)
    req = urllib.request.Request(
        GROBID_REFS_URL,
        data=body,
        headers={"Content-Type": content_type},
        method="POST",
    )
    resp = urllib.request.urlopen(req, timeout=300)
    if resp.status == 204:
        return ""
    return resp.read().decode("utf-8")


def _extract_references_text_from_pdf(pdf_path):
    """Extract individual reference strings from the PDF using pypdf.

    Scans pages from the end looking for reference-formatted text, then splits
    the text into individual reference entries.
    """
    try:
        import pypdf
    except ImportError:
        return []

    reader = pypdf.PdfReader(pdf_path)
    total_pages = len(reader.pages)

    # Find where references start by scanning backwards for the "References" heading
    ref_start_page = None
    for i in range(total_pages - 1, max(total_pages - 80, -1), -1):
        text = reader.pages[i].extract_text() or ""
        if re.search(r"(?m)^\s*References\s*$", text):
            ref_start_page = i
            break

    if ref_start_page is None:
        return []

    # Extract all text from reference pages
    ref_text = ""
    for i in range(ref_start_page, total_pages):
        page_text = reader.pages[i].extract_text() or ""
        lines = page_text.split("\n")
        cleaned_lines = []
        for line in lines:
            stripped = line.strip()
            # Skip running headers (all caps with page numbers)
            if re.match(r"^[A-Z\s:&,\-]+\d+\s*$", stripped):
                continue
            cleaned_lines.append(line)
        ref_text += "\n".join(cleaned_lines) + "\n"

    # Split into individual references
    # References typically start with author names: "LastName, F." or "* LastName, F."
    raw_refs = re.split(
        r"\n(?=\*?\s*[A-Z][A-Za-zÀ-ÿ\-']+,\s+[A-Z]\.)",
        ref_text,
    )

    references = []
    for ref in raw_refs:
        ref = ref.strip()
        if len(ref) < 30:
            continue
        if ref.lower().startswith("references"):
            continue
        if re.match(r"^(Appendix|Supplement|Table|Figure|Note)\b", ref, re.IGNORECASE):
            continue
        ref = re.sub(r"\s+", " ", ref).strip()
        # Remove leading "* " marker used for included studies
        ref_clean = re.sub(r"^\*\s*", "", ref)
        if ref_clean:
            references.append(ref_clean)

    return references


def _parse_reference_locally(ref_text, index):
    """Parse a single reference string into structured fields using regex.

    Handles common APA-style formats:
      Author, A. B., & Author, C. D. (2020). Title. Journal, 1(2), 3-4.
    """
    entry = {
        "id": f"b{index}",
        "authors": None,
        "year": None,
        "title": None,
        "journal": None,
        "volume": None,
        "pages": None,
        "doi": None,
        "raw": ref_text,
        "is_complete": False,
        "missing_fields": [],
    }

    # Extract year: (2020) or (2020, January) or (in press)
    year_match = re.search(r"\((\d{4})[a-z]?(?:,\s*[A-Za-z]+)?\)", ref_text)
    if year_match:
        entry["year"] = year_match.group(1)
        # Authors are everything before the year parenthetical
        authors_text = ref_text[: year_match.start()].strip().rstrip(",").strip()
        if authors_text:
            entry["authors"] = authors_text

        after_year = ref_text[year_match.end() :].strip()
        # Remove leading ". " after year
        after_year = re.sub(r"^\.\s*", "", after_year)

        # Title is typically the next sentence (up to the first period followed by
        # a space and an uppercase letter or italic marker)
        title_match = re.match(r"(.+?\.)\s+(?=[A-Z])", after_year)
        if title_match:
            entry["title"] = title_match.group(1)
            remainder = after_year[title_match.end() :].strip()

            # Journal, volume, pages pattern: Journal Name, 12(3), 45-67.
            journal_match = re.match(
                r"([^,]+),\s*(\d+)(?:\(([^)]+)\))?,?\s*([\d\-–]+)?",
                remainder,
            )
            if journal_match:
                entry["journal"] = journal_match.group(1).strip().rstrip(".")
                entry["volume"] = journal_match.group(2)
                entry["pages"] = journal_match.group(4)
        else:
            # If no clear title/journal split, store everything as title
            entry["title"] = after_year.split(".")[0].strip() if after_year else None

    # Extract DOI
    doi_match = re.search(r"https?://doi\.org/(10\.\S+)", ref_text)
    if doi_match:
        entry["doi"] = doi_match.group(1).rstrip(".")
    else:
        doi_match = re.search(r"\bdoi:\s*(10\.\S+)", ref_text, re.IGNORECASE)
        if doi_match:
            entry["doi"] = doi_match.group(1).rstrip(".")

    # Completeness check
    missing = []
    if not entry["title"]:
        missing.append("title")
    if not entry["year"]:
        missing.append("year")
    if not entry["journal"]:
        missing.append("journal")
    if not entry["volume"]:
        missing.append("volume")
    if not entry["pages"]:
        missing.append("pages")
    entry["missing_fields"] = missing
    entry["is_complete"] = len(missing) == 0

    return entry


def extract_bibliography_from_refs_response(tei_xml):
    """Extract bibliography entries from GROBID's processReferences response.

    The response wraps biblStruct elements in a <listBibl> inside a <TEI> document.
    We need to handle the case where the response may be a fragment or a full TEI doc.
    """
    bibliography = []
    if not tei_xml:
        return bibliography
    try:
        root = ET.fromstring(tei_xml)
    except ET.ParseError:
        try:
            root = ET.fromstring(f"<wrapper>{tei_xml}</wrapper>")
        except ET.ParseError:
            return bibliography

    for bib_struct in root.iter(_ns("biblStruct")):
        entry = _parse_bib_struct(bib_struct)
        bibliography.append(entry)

    return bibliography


def extract_bibliography_via_local_parse(pdf_path):
    """Fallback: extract reference text from PDF and parse locally with regex."""
    ref_strings = _extract_references_text_from_pdf(pdf_path)
    if not ref_strings:
        return []

    print(
        f"Extracted {len(ref_strings)} reference strings from PDF, "
        "parsing locally...",
        file=sys.stderr,
    )

    bibliography = []
    for i, ref_text in enumerate(ref_strings):
        entry = _parse_reference_locally(ref_text, i)
        bibliography.append(entry)

    return bibliography


def _jaccard(tokens_a, tokens_b):
    """Jaccard similarity between two sets of tokens."""
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union) if union else 0.0


def _tokenize(text):
    """Return a set of lowercase alphanumeric tokens from text."""
    if not text:
        return set()
    return {
        t
        for t in "".join(c if c.isalnum() or c.isspace() else " " for c in text.lower()).split()
        if t
    }


# ---------------------------------------------------------------------------
# Extraction functions
# ---------------------------------------------------------------------------

def extract_grobid_version(root):
    """Extract the GROBID version from the TEI header."""
    for app in root.iter(_ns("application")):
        version = app.get("version")
        if version:
            return version
    return None


def extract_metadata(root):
    """Extract title, authors, abstract, and keywords."""
    metadata = {
        "title": None,
        "authors": [],
        "abstract": None,
        "abstract_word_count": 0,
        "keywords": [],
    }

    # Title
    for title_el in root.iter(_ns("titleStmt")):
        t = title_el.find(_ns("title"))
        if t is not None:
            metadata["title"] = _all_text(t) or None

    # Authors from sourceDesc/biblStruct/analytic/author
    source_desc = root.find(f".//{_ns('sourceDesc')}")
    if source_desc is not None:
        bibl_struct = source_desc.find(_ns("biblStruct"))
        if bibl_struct is not None:
            analytic = bibl_struct.find(_ns("analytic"))
            author_container = analytic if analytic is not None else bibl_struct.find(_ns("monogr"))
            if author_container is not None:
                for author_el in author_container.findall(_ns("author")):
                    author_info = _extract_author(author_el)
                    if author_info["name"]:
                        metadata["authors"].append(author_info)

    # Abstract
    for profile_desc in root.iter(_ns("profileDesc")):
        abstract_el = profile_desc.find(_ns("abstract"))
        if abstract_el is not None:
            abstract_text = _all_text(abstract_el)
            metadata["abstract"] = abstract_text or None
            if abstract_text:
                metadata["abstract_word_count"] = len(abstract_text.split())

        # Keywords
        text_class = profile_desc.find(_ns("textClass"))
        if text_class is not None:
            keywords_el = text_class.find(_ns("keywords"))
            if keywords_el is not None:
                for term in keywords_el.findall(_ns("term")):
                    term_text = _all_text(term)
                    if term_text:
                        metadata["keywords"].append(term_text)

    return metadata


def _extract_author(author_el):
    """Extract author name and affiliations from an author element."""
    name_parts = []
    pers_name = author_el.find(_ns("persName"))
    if pers_name is not None:
        forenames = pers_name.findall(_ns("forename"))
        surname = pers_name.find(_ns("surname"))
        for fn in forenames:
            fn_text = _all_text(fn)
            if fn_text:
                name_parts.append(fn_text)
        if surname is not None:
            sn_text = _all_text(surname)
            if sn_text:
                name_parts.append(sn_text)

    affiliations = []
    for aff in author_el.findall(_ns("affiliation")):
        aff_parts = []
        for org_name in aff.findall(_ns("orgName")):
            org_text = _all_text(org_name)
            if org_text:
                aff_parts.append(org_text)
        if aff_parts:
            affiliations.append(", ".join(aff_parts))
        else:
            raw_aff = _all_text(aff)
            if raw_aff:
                affiliations.append(raw_aff)

    return {"name": " ".join(name_parts) if name_parts else None, "affiliations": affiliations}


def extract_sections(root):
    """Extract document section headings and levels from body divs."""
    sections = []
    body = root.find(f".//{_ns('body')}")
    if body is None:
        return sections

    _walk_divs_for_sections(body, sections, level=0)
    return sections


def _walk_divs_for_sections(parent, sections, level):
    """Recursively walk div elements to extract section headings."""
    for div in parent.findall(_ns("div")):
        head = div.find(_ns("head"))
        if head is not None:
            heading_text = _all_text(head)
            # Determine level from @n attribute or nesting depth
            n_attr = head.get("n")
            if n_attr:
                # Count dots to determine level: "1" -> 1, "1.1" -> 2, "1.1.1" -> 3
                computed_level = n_attr.count(".") + 1
            else:
                computed_level = level + 1
            if heading_text:
                sections.append({"heading": heading_text, "level": computed_level})
        # Recurse into nested divs
        _walk_divs_for_sections(div, sections, level + 1)


def extract_figures(root):
    """Extract figure labels and captions."""
    figures = []
    for fig in root.iter(_ns("figure")):
        fig_id = _xml_attr(fig, "id")
        # Skip tables (figure[@type='table'])
        fig_type = fig.get("type")

        label_el = fig.find(_ns("head"))
        caption_el = fig.find(_ns("figDesc"))

        label = _all_text(label_el) if label_el is not None else None
        caption = _all_text(caption_el) if caption_el is not None else None

        # Only include if there is some content
        if label or caption or fig_id:
            entry = {
                "id": fig_id,
                "label": label,
                "caption": caption,
            }
            if fig_type:
                entry["type"] = fig_type
            figures.append(entry)

    return figures


def extract_bibliography(root):
    """Extract bibliography entries from listBibl/biblStruct."""
    bibliography = []
    for bibl in root.iter(_ns("listBibl")):
        for bib_struct in bibl.findall(_ns("biblStruct")):
            entry = _parse_bib_struct(bib_struct)
            bibliography.append(entry)
    return bibliography


def _get_first_text(parent, path):
    """Find the first matching element and return its text, or None."""
    if parent is None:
        return None
    el = parent.find(path)
    if el is not None:
        text = _all_text(el)
        return text if text else None
    return None


def _parse_bib_struct(bib_struct):
    """Parse a single biblStruct element into a dictionary."""
    bib_id = _xml_attr(bib_struct, "id")
    analytic = bib_struct.find(_ns("analytic"))
    monogr = bib_struct.find(_ns("monogr"))

    # Authors: prefer analytic authors, fall back to monogr
    authors_text = _extract_bib_authors(analytic) or _extract_bib_authors(monogr) or None

    # Title: prefer analytic title, fall back to monogr title (non-journal)
    title = None
    if analytic is not None:
        title = _get_first_text(analytic, _ns("title"))
    if not title and monogr is not None:
        # Get monogr title that is not journal-level
        for t in monogr.findall(_ns("title")):
            level = t.get("level", "")
            if level != "j":
                text = _all_text(t)
                if text:
                    title = text
                    break

    # Journal
    journal = None
    if monogr is not None:
        for t in monogr.findall(_ns("title")):
            if t.get("level") == "j":
                text = _all_text(t)
                if text:
                    journal = text
                    break

    # Year
    year = None
    if monogr is not None:
        imprint = monogr.find(_ns("imprint"))
        if imprint is not None:
            date_el = imprint.find(_ns("date"))
            if date_el is not None:
                when = date_el.get("when")
                if when:
                    year = when[:4] if len(when) >= 4 else when
                else:
                    year = _all_text(date_el) or None

    # Volume
    volume = None
    if monogr is not None:
        imprint = monogr.find(_ns("imprint"))
        if imprint is not None:
            for bs in imprint.findall(_ns("biblScope")):
                if bs.get("unit") == "volume":
                    volume = _all_text(bs) or bs.get("from") or bs.get("to") or None
                    break

    # Pages
    pages = None
    if monogr is not None:
        imprint = monogr.find(_ns("imprint"))
        if imprint is not None:
            for bs in imprint.findall(_ns("biblScope")):
                if bs.get("unit") == "page":
                    from_p = bs.get("from", "")
                    to_p = bs.get("to", "")
                    text_p = _all_text(bs)
                    if from_p and to_p:
                        pages = f"{from_p}-{to_p}" if from_p != to_p else from_p
                    elif text_p:
                        pages = text_p
                    elif from_p:
                        pages = from_p
                    break

    # DOI
    doi = None
    for container in [analytic, monogr]:
        if container is not None:
            for idno in container.findall(_ns("idno")):
                if idno.get("type") == "DOI":
                    doi = _all_text(idno) or None
                    if doi:
                        break
        if doi:
            break

    # Raw reference text
    raw = None
    note = bib_struct.find(_ns("note"))
    if note is not None and note.get("type") == "raw_reference":
        raw = _all_text(note) or None
    if not raw:
        # Try to reconstruct from rawString element
        for rs in bib_struct.iter(_ns("rawString")):
            raw = _all_text(rs) or None
            break

    # Completeness check
    missing_fields = []
    if not title:
        missing_fields.append("title")
    if not year:
        missing_fields.append("year")
    if not journal:
        missing_fields.append("journal")
    if not volume:
        missing_fields.append("volume")
    if not pages:
        missing_fields.append("pages")

    is_complete = len(missing_fields) == 0

    return {
        "id": bib_id,
        "authors": authors_text,
        "year": year,
        "title": title,
        "journal": journal,
        "volume": volume,
        "pages": pages,
        "doi": doi,
        "raw": raw,
        "is_complete": is_complete,
        "missing_fields": missing_fields,
    }


def _extract_bib_authors(container):
    """Extract a formatted author string from a container element."""
    if container is None:
        return None
    authors = []
    for author_el in container.findall(_ns("author")):
        pers_name = author_el.find(_ns("persName"))
        if pers_name is not None:
            forenames = []
            for fn in pers_name.findall(_ns("forename")):
                fn_text = _all_text(fn)
                if fn_text:
                    forenames.append(fn_text)
            surname = pers_name.find(_ns("surname"))
            sn_text = _all_text(surname) if surname is not None else ""
            if sn_text:
                if forenames:
                    authors.append(f"{sn_text}, {' '.join(forenames)}")
                else:
                    authors.append(sn_text)
        else:
            # Try orgName for institutional authors
            org_name = author_el.find(_ns("orgName"))
            if org_name is not None:
                org_text = _all_text(org_name)
                if org_text:
                    authors.append(org_text)
            else:
                # Fallback to raw text
                raw = _all_text(author_el)
                if raw:
                    authors.append(raw)

    return "; ".join(authors) if authors else None


def extract_citations_in_text(root):
    """Extract in-text citation references from the body."""
    citations = []
    body = root.find(f".//{_ns('body')}")
    if body is None:
        return citations

    _walk_for_citations(body, citations, current_section=None)
    return citations


def _walk_for_citations(element, citations, current_section):
    """Recursively walk elements to find <ref type='bibr'> citations."""
    # Update current section if we encounter a head element
    if element.tag == _ns("div"):
        head = element.find(_ns("head"))
        if head is not None:
            section_name = _all_text(head)
            if section_name:
                current_section = section_name

    for child in element:
        if child.tag == _ns("ref") and child.get("type") == "bibr":
            target = child.get("target")
            if target and target.startswith("#"):
                target = target[1:]  # Remove leading '#'
            text = _all_text(child)
            citations.append({
                "target": target if target else None,
                "text": text if text else None,
                "section": current_section,
            })
        # Recurse
        _walk_for_citations(child, citations, current_section)


def build_cross_reference_report(bibliography, citations):
    """Build a cross-reference quality report."""
    report = {
        "unlinked_citations": [],
        "uncited_references": [],
        "potential_duplicates": [],
        "incomplete_references": [],
    }

    # Set of bibliography IDs that are cited
    cited_ids = set()
    bib_ids = {entry["id"] for entry in bibliography if entry["id"]}

    for cit in citations:
        if cit["target"] is None:
            report["unlinked_citations"].append({
                "text": cit["text"],
                "section": cit["section"],
                "note": "GROBID could not link to bibliography",
            })
        elif cit["target"] in bib_ids:
            cited_ids.add(cit["target"])
        else:
            # Target doesn't match any bib entry
            report["unlinked_citations"].append({
                "text": cit["text"],
                "section": cit["section"],
                "note": f"Target '{cit['target']}' not found in bibliography",
            })

    # Uncited references
    for entry in bibliography:
        if entry["id"] and entry["id"] not in cited_ids:
            report["uncited_references"].append({
                "id": entry["id"],
                "authors": entry["authors"],
                "title": entry["title"],
                "year": entry["year"],
            })

    # Potential duplicates: same first author surname + year, then title similarity
    bib_by_key = defaultdict(list)
    for entry in bibliography:
        first_author_surname = _get_first_surname(entry["authors"])
        if first_author_surname and entry["year"]:
            key = (first_author_surname.lower(), entry["year"])
            bib_by_key[key].append(entry)

    seen_pairs = set()
    for key, entries in bib_by_key.items():
        if len(entries) < 2:
            continue
        for i in range(len(entries)):
            for j in range(i + 1, len(entries)):
                pair_key = tuple(sorted([entries[i]["id"] or "", entries[j]["id"] or ""]))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                tokens_i = _tokenize(entries[i]["title"])
                tokens_j = _tokenize(entries[j]["title"])
                sim = _jaccard(tokens_i, tokens_j)
                if sim > 0.5:
                    first_surname = _get_first_surname(entries[i]["authors"])
                    reason = (
                        f"Same first author ({first_surname}) and year ({entries[i]['year']}), "
                        f"similar titles (Jaccard={sim:.2f})"
                    )
                    report["potential_duplicates"].append({
                        "ids": [entries[i]["id"], entries[j]["id"]],
                        "reason": reason,
                    })

    # Incomplete references
    for entry in bibliography:
        if entry["missing_fields"]:
            report["incomplete_references"].append({
                "id": entry["id"],
                "title": entry["title"],
                "missing": entry["missing_fields"],
            })

    return report


def _match_citations_to_bibliography(report, bibliography):
    """Try to match unlinked citations to bibliography entries using text similarity.

    Citation text is typically "Author (Year)", "Author & Author (Year)",
    or "Author et al. (Year)". We match the first surname and year against
    the bibliography.
    """
    # Build a lookup: (lowercase_first_surname, year) -> list of bib entry IDs
    bib_lookup = defaultdict(list)
    for entry in bibliography:
        surname = _get_first_surname(entry["authors"])
        if surname and entry["year"]:
            bib_lookup[(surname.lower(), entry["year"])].append(entry["id"])

    matched_bib_ids = set()
    still_unlinked = []

    for cit in report["unlinked_citations"]:
        text = cit.get("text", "") or ""
        # Try to extract first author surname and year from citation text
        # Patterns: "Author (Year)", "Author, Year", "Author et al., Year"
        m = re.match(
            r"([A-Za-zÀ-ÿ\-']+)(?:\s+(?:&|and)\s+[A-Za-zÀ-ÿ\-']+)?"
            r"(?:\s+et\s+al\.?)?"
            r"[,\s]*\(?(\d{4})[a-z]?\)?",
            text.strip(),
        )
        if m:
            surname = m.group(1).lower()
            year = m.group(2)
            matches = bib_lookup.get((surname, year), [])
            if matches:
                for mid in matches:
                    matched_bib_ids.add(mid)
                continue
        still_unlinked.append(cit)

    report["unlinked_citations"] = still_unlinked

    # Update uncited references: remove any that were matched
    report["uncited_references"] = [
        ref for ref in report["uncited_references"]
        if ref["id"] not in matched_bib_ids
    ]


def _get_first_surname(authors_str):
    """Extract the first author's surname from the formatted author string."""
    if not authors_str:
        return None
    # Format is "Surname, Forename; Surname2, Forename2"
    # or "Surname, F. B., & Surname2, ..."
    first_author = authors_str.split(";")[0].strip()
    surname = first_author.split(",")[0].strip()
    return surname if surname else None


def generate_warnings(citations, bibliography, report):
    """Generate parse warnings based on the analysis."""
    warnings = []

    unlinked_count = len(report["unlinked_citations"])
    if unlinked_count > 0:
        warnings.append(
            f"{unlinked_count} citation(s) could not be linked to bibliography entries - "
            "verify manually"
        )

    dup_count = len(report["potential_duplicates"])
    if dup_count > 0:
        warnings.append(
            f"{dup_count} potential duplicate bibliography entry pair(s) detected"
        )

    uncited_count = len(report["uncited_references"])
    if uncited_count > 0:
        warnings.append(
            f"{uncited_count} bibliography entry/entries not cited in the text"
        )

    incomplete_count = len(report["incomplete_references"])
    if incomplete_count > 0:
        warnings.append(
            f"{incomplete_count} bibliography entry/entries have missing fields "
            "(some may be valid for non-journal items like books or reports)"
        )

    return warnings


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 parse_manuscript.py <path_to_pdf>", file=sys.stderr)
        sys.exit(1)

    pdf_path = sys.argv[1]
    if not os.path.isfile(pdf_path):
        error_result = {
            "grobid_failed": True,
            "error": f"File not found: {pdf_path}",
        }
        print(json.dumps(error_result, indent=2))
        sys.exit(0)

    # Send PDF to GROBID
    print(f"Sending PDF to GROBID: {pdf_path}", file=sys.stderr)
    try:
        tei_xml = _send_to_grobid(pdf_path)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        error_result = {
            "grobid_failed": True,
            "error": f"GROBID API request failed: {e}",
        }
        print(json.dumps(error_result, indent=2))
        sys.exit(0)
    except Exception as e:
        error_result = {
            "grobid_failed": True,
            "error": f"Unexpected error contacting GROBID: {e}",
        }
        print(json.dumps(error_result, indent=2))
        sys.exit(0)

    # Check that GROBID returned XML, not an HTML error/queue page
    if tei_xml.lstrip().startswith("<!DOCTYPE html") or tei_xml.lstrip().startswith("<html"):
        print(
            "GROBID returned HTML instead of XML (server busy/rate-limited), "
            "proceeding with PDF-only fallback...",
            file=sys.stderr,
        )
        tei_xml = None
    else:
        # Save raw GROBID XML for reuse by metacheck
        try:
            with open("/tmp/manuscript_grobid.xml", "w", encoding="utf-8") as f:
                f.write(tei_xml)
        except OSError:
            print("Warning: Could not save GROBID XML for reuse", file=sys.stderr)

    root = None
    if tei_xml:
        print("GROBID response received, parsing TEI XML...", file=sys.stderr)
        try:
            root = ET.fromstring(tei_xml)
        except ET.ParseError as e:
            print(f"Failed to parse GROBID TEI XML: {e}", file=sys.stderr)
            print("Proceeding with PDF-only fallback...", file=sys.stderr)

    # Extract all components from GROBID XML (if available)
    if root is not None:
        grobid_version = extract_grobid_version(root)
        metadata = extract_metadata(root)
        sections = extract_sections(root)
        figures = extract_figures(root)
        bibliography = extract_bibliography(root)
    else:
        grobid_version = None
        metadata = {"title": None, "authors": [], "abstract": None,
                     "abstract_word_count": 0, "keywords": []}
        sections = []
        figures = []
        bibliography = []

    # Fallback: if bibliography is empty, try GROBID's dedicated references endpoint
    if not bibliography:
        print(
            "Bibliography empty from fulltext endpoint, trying /api/processReferences...",
            file=sys.stderr,
        )
        try:
            refs_xml = _send_to_grobid_references(pdf_path)
            bibliography = extract_bibliography_from_refs_response(refs_xml)
            if bibliography:
                print(
                    f"References fallback recovered {len(bibliography)} entries",
                    file=sys.stderr,
                )
        except Exception as e:
            print(
                f"References endpoint failed: {e}",
                file=sys.stderr,
            )

    # Second fallback: extract references from PDF text and parse locally
    if not bibliography:
        print(
            "Trying local PDF text extraction fallback...",
            file=sys.stderr,
        )
        try:
            bibliography = extract_bibliography_via_local_parse(pdf_path)
            if bibliography:
                print(
                    f"Local parse fallback recovered {len(bibliography)} entries",
                    file=sys.stderr,
                )
            else:
                print(
                    "Local parse fallback also returned no entries",
                    file=sys.stderr,
                )
        except Exception as e:
            print(
                f"Local parse fallback failed: {e}",
                file=sys.stderr,
            )

    citations = extract_citations_in_text(root) if root is not None else []
    cross_ref_report = build_cross_reference_report(bibliography, citations)

    # If GROBID couldn't link citations, try text-based matching
    if bibliography and cross_ref_report["unlinked_citations"]:
        _match_citations_to_bibliography(cross_ref_report, bibliography)

    warnings = generate_warnings(citations, bibliography, cross_ref_report)

    # Assemble output
    result = {
        "metadata": metadata,
        "sections": sections,
        "figures": figures,
        "bibliography": bibliography,
        "citations_in_text": citations,
        "cross_reference_report": cross_ref_report,
        "grobid_version": grobid_version,
        "parse_warnings": warnings,
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
