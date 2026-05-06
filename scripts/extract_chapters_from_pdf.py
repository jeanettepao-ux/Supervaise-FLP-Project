"""Extract per-chapter texts from 'A Centenary of Justice' PDF using title search.

Approach:
1. Pull all PDF text per page via pypdf.
2. Treat pages 18+ as body (TOC + front matter is pages 1-17).
3. For each known chapter title, find its first occurrence in body text using
   whitespace-tolerant regex.
4. Sort matches by position, slice body into 20 per-chapter text blobs.
5. Save each as source_materials/centenary_chapters/ch{NN}-{slug}.txt.
6. Report which chapters were found / where / which need manual review.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pypdf import PdfReader

PDF = Path(r"C:\Users\ASUS\Downloads\A CENTENARY OF JUSTICE (3).pdf")
OUT = Path("source_materials/centenary_chapters")
BODY_START_PAGE = 17  # 0-indexed; PDF pages 1-17 are front matter / TOC

# Best-known chapter titles. Multiple candidate phrases per chapter so we can
# fall back if the primary phrase doesn't match cleanly in extracted text.
# Ordered by specificity — first candidate is preferred, fallbacks follow.
CHAPTERS: list[tuple[int, str, list[str]]] = [
    (1, "A Renaissance in the Judiciary",
     ["Renaissance in the Judiciary"]),
    (2, "Old Doctrines and New Paradigms",
     ["Old Doctrines and New Paradigms", "Old Doctrines"]),
    (3, "Obra Maestra",
     ["Obra maestra", "Obra Maestra"]),
    (4, "The Supreme Court Centenary and the Academe",
     ["Centenary and the Academe", "Supreme Court Centenary and"]),
    (5, "Mediation, an Old Method with a New Twist",
     ["Mediation, an Old Method", "Mediation an Old Method"]),
    (6, "A Meaningful Centenary",
     ["A Meaningful Centenary", "Meaningful Centenary"]),
    (7, "Employee Participation During the Centenary",
     ["Employee Participation During", "Employee Participation"]),
    (8, "The Inspiration of the Judiciary",
     ["Inspiration of the Judiciary"]),
    (9, "A Benchbook for Judicial Excellence",
     ["Benchbook for Judicial Excellence", "Benchbook for Judicial"]),
    (10, "Ready for the Bio-Age",
     ["Ready for the Bio-Age", "Ready for the Bio Age"]),
    (11, "E-Values for Lawyers",
     ["E-Values for Lawyers", "E Values for Lawyers"]),
    (12, "Even the Supreme Court Needs Public Relations",
     ["Even the Supreme Court Needs"]),
    (13, "Estrada v. Desierto and Estrada",
     ["Estrada v. Desierto and Estrada", "Estrada v Desierto and Estrada", "Estrada v. Desierto"]),
    (14, "The Death Penalty",
     # "The Death Penalty" by itself is too generic and false-matches in Ch 2.
     # Use a phrase only that chapter would contain.
     ["heinousness", "Death Penalty Law", "anti-death penalty"]),
    (15, "Cruz v. Secretary of Environment",
     ["Cruz v. Secretary", "Cruz v Secretary", "indigenous peoples", "ancestral domain"]),
    (16, "Ang Bagong Bayani-OFW Labor",
     ["Ang Bagong Bayani", "Bagong Bayani"]),
    (17, "Perez v. Estrada",
     ["Perez v. Estrada", "Perez v Estrada", "Live Radio-TV Coverage", "Live Radio TV"]),
    (18, "Firestone Ceramics v. Court of Appeals",
     ["Firestone Ceramics"]),
    (19, "Bengson v. House of Representatives",
     ["Bengson v. House", "Bengson v House", "natural-born citizen", "loss of Philippine citizenship"]),
    (20, "Social Weather Stations v. Comelec",
     ["Social Weather Stations", "exit poll", "exit polls"]),
]


def slugify(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s).strip("-")
    return s[:60] or "untitled"


def whitespace_tolerant(phrase: str) -> str:
    """Build a regex that matches the phrase with any whitespace between words."""
    return r"\s+".join(re.escape(w) for w in phrase.split())


def find_first_after(body: str, candidates: list[str], min_offset: int = 0) -> tuple[int, str] | None:
    """Return (position, candidate) of first match for any candidate at or after min_offset."""
    best = None
    for cand in candidates:
        pat = whitespace_tolerant(cand)
        for m in re.finditer(pat, body, re.IGNORECASE):
            if m.start() >= min_offset:
                if best is None or m.start() < best[0]:
                    best = (m.start(), cand)
                break  # only the FIRST match for this candidate
    return best


def main() -> None:
    print(f"loading {PDF.name}...")
    reader = PdfReader(str(PDF))
    pages = [(p.extract_text() or "") for p in reader.pages]
    print(f"  {len(pages)} pages")

    # Build body text (skip pages before BODY_START_PAGE) with offset->page tracking
    body_text = ""
    offset_to_page: list[tuple[int, int]] = []  # (char_offset, pdf_page_1idx)
    for i in range(BODY_START_PAGE, len(pages)):
        offset_to_page.append((len(body_text), i + 1))
        body_text += pages[i] + "\n"
    print(f"  body text: {len(body_text):,} chars from PDF pages {BODY_START_PAGE+1}-{len(pages)}\n")

    def offset_to_pdf_page(offset: int) -> int:
        page = BODY_START_PAGE + 1
        for off, p in offset_to_page:
            if off > offset:
                break
            page = p
        return page

    print("=== chapter title search (sequential) ===")
    found: list[tuple[int, str, int, str]] = []
    not_found: list[tuple[int, str]] = []
    cursor = 0  # body offset; each chapter must be found at or after this point

    for ch_num, title, candidates in CHAPTERS:
        result = find_first_after(body_text, candidates, min_offset=cursor)
        if result is None:
            not_found.append((ch_num, title))
            print(f"  ch{ch_num:>2}  NOT FOUND   {title}")
            continue
        offset, cand = result
        page = offset_to_pdf_page(offset)
        print(f"  ch{ch_num:>2}  p{page:>3}  offset={offset:>6}  via {cand!r}")
        found.append((ch_num, title, offset, cand))
        cursor = offset + 1  # next chapter must be later than this match

    if not_found:
        print(f"\n  NOT FOUND: {len(not_found)} chapters: {[n for n, _ in not_found]}")

    # Slice and write
    print("\n=== writing chapter files ===")
    OUT.mkdir(parents=True, exist_ok=True)
    # First, clear out any old chapter files
    for f in OUT.glob("ch*.txt"):
        f.unlink()

    for i, (ch_num, title, start, _) in enumerate(found):
        end = found[i + 1][2] if i + 1 < len(found) else len(body_text)
        chunk = body_text[start:end].strip()
        word_count = len(chunk.split())
        slug = f"ch{ch_num:02d}-{slugify(title)}"
        path = OUT / f"{slug}.txt"
        path.write_text(chunk, encoding="utf-8")
        first_line = chunk.split("\n", 1)[0][:60]
        print(f"  {path.name:50}  {word_count:>5}w  starts: {first_line!r}")

    print(f"\nfound {len(found)} of 20 chapters. {len(not_found)} not found.")


if __name__ == "__main__":
    main()
