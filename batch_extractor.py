"""
Published-patents multi-file orchestration.

This module does NOT change the publication backend. It orchestrates the
existing, unmodified publication extractor across a list of selected PDFs:
it calls `extract_patents` (unchanged) on each file, resolves each file's
journal date by reusing the existing, unmodified helpers, annotates every
record with Journal Date and Source PDF, merges the results, and returns
them stably sorted by journal date.

The journal-date resolution mirrors the Version 4 date-range behaviour so
multi-part journals (where only the first part carries the front-matter
header) still resolve correctly:
  1. Page-1 header date via journal_utils.get_journal_metadata.
  2. Fallback to the content-driven (43) Publication Date resolver in
     range_extractor, for headerless parts.
"""

import os
from datetime import datetime

from patent_extractor import extract_patents
from journal_utils import get_journal_metadata
from range_extractor import _resolve_date_from_content


def _resolve_journal_date(pdf_path):
    """Resolve a published journal's date: header first, then content."""

    metadata = get_journal_metadata(pdf_path)

    if metadata and metadata.get("date") not in (None, "Not Found"):
        return metadata["date"]

    return _resolve_date_from_content(pdf_path)


def extract_published(pdf_files, progress_callback=None, status_callback=None):
    """Extract published patents from one or more PDFs and merge them.

    Reuses the unchanged publication extractor. Annotates each record with
    Journal Date and Source PDF, then returns the merged list stably sorted
    by journal date (records that share a date keep their in-file order).
    """

    all_patents = []
    total = len(pdf_files)

    for index, pdf in enumerate(pdf_files, start=1):

        basename = os.path.basename(pdf)

        if status_callback:
            status_callback(f"Processing {basename} ({index}/{total})...")

        journal_date = _resolve_journal_date(pdf)

        patents = extract_patents(pdf, progress_callback=progress_callback)

        for patent in patents:
            patent["Journal Date"] = journal_date if journal_date else ""
            patent["Source PDF"] = basename

        all_patents.extend(patents)

    # Stable sort by journal date; records with an unparseable/missing date
    # sort last while keeping their relative order.
    def _key(patent):
        value = patent.get("Journal Date", "")
        try:
            return (0, datetime.strptime(value, "%d/%m/%Y"))
        except ValueError:
            return (1, datetime.max)

    all_patents.sort(key=_key)

    return all_patents
