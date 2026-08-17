"""
Journal-number helper, shared by both extraction modes.

Every page of an IPO weekly journal (published or granted sections alike)
carries the footer:

    "The Patent Office Journal No. 29/2026 Dated 17/07/2026"

This module reads that journal number so output workbooks can be named by
the range of journals processed, e.g. "Granted_Patents_29_to_32.xlsx".
It is naming metadata only and does not touch record extraction.
"""

import re

import fitz  # PyMuPDF


_NUMBER = re.compile(
    r"Patent\s+Office\s+Journal\s+No\.?\s*(\d+)\s*/\s*\d+",
    re.IGNORECASE,
)


def _number_for(pdf_path):
    """Return the journal number (int) for one PDF, or None."""

    try:
        doc = fitz.open(pdf_path)
    except Exception:
        return None

    try:
        # The footer is on every page; the first page suffices, but scan a
        # few in case the first page's footer is missing.
        for page in doc[:5]:
            match = _NUMBER.search(page.get_text())
            if match:
                return int(match.group(1))
    finally:
        doc.close()

    return None


def journal_number_range(pdf_files):
    """Return (low, high) journal numbers across the PDFs, or None."""

    numbers = [n for n in (_number_for(p) for p in pdf_files) if n is not None]

    if not numbers:
        return None

    return (min(numbers), max(numbers))
