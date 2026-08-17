"""
Granted-patents extraction for Indian Patent Office journals.

This is a completely independent backend from the publication extractor.
It does NOT import or reuse any publication parsing logic. The only shared
pieces are genuinely generic utilities: `cleaner.clean` (whitespace
normalisation) and `excel_writer.save_to_excel` (used by the GUI layer,
which already sanitises Excel-illegal characters).

IPO weekly journals are split across "Part" PDFs and contain several
sections (FER tables, Granted Patents, restoration/other notices, ...).
The granted-patents section is a bordered table introduced by the header:

    "Publication Under Section 43(2) in Respect of the Grant"

with columns:

    Serial Number | Patent Number | Application Number | Date of Application
    | Date of Priority | Title of Invention | Name of Patentee
    | Date of Publication of Abstract u/s 11(A) | Appropriate Office

Only the granted-patents section is extracted. FER tables (6 columns) and
all other sections are ignored, both by bounding extraction to the grant
section and by a per-table column-schema guard.
"""

import os
import re
from datetime import datetime

import fitz  # PyMuPDF

from cleaner import clean


# Section header that opens the granted-patents table (space/case tolerant).
_GRANT_START = re.compile(
    r"Publication\s+Under\s+Section\s+43\s*\(\s*2\s*\)\s+in\s+Respect\s+of\s+the\s+Grant",
    re.IGNORECASE,
)

# Headers that mark the start of a DIFFERENT section - the grant section
# ends when one of these is reached.
_SECTION_END = re.compile(
    r"PUBLICATION\s+U/R\s*84"
    r"|PUBLICATION\s+U/S\.?\s*61"
    r"|PUBLICATION\s+UNDER\s+SECTION\s+57"
    r"|WEEKLY\s+ISSUED\s+FER"
    r"|Introduction\s+to\s+Designs"
    r"|COPYRIGHT",
    re.IGNORECASE,
)

# Journal issue date, printed in every page footer:
#   "The Patent Office Journal No. 29/2026 Dated 17/07/2026"
_JOURNAL_DATE = re.compile(
    r"Patent\s+Office\s+Journal\s+No\.?\s*\d+/\d+\s+Dated\s+(\d{2}/\d{2}/\d{4})",
    re.IGNORECASE,
)

# A granted-patent row's Patent Number is a 5-7 digit integer; the
# Application Number is a long digit string (optionally with a trailing
# letter). Used to validate table rows and reject header/other rows.
_PATENT_NO = re.compile(r"^\s*\d{5,7}\s*$")
_APP_NO = re.compile(r"^\s*\d{6,}[A-Za-z]?\s*$")

# Ordered output field names. The table is anchored on the Patent Number
# column; "Serial Number" sits one column before it, the rest follow it.
_COLUMNS = [
    "Serial Number",
    "Patent Number",
    "Application Number",
    "Date of Application",
    "Date of Priority",
    "Title of Invention",
    "Name of Patentee",
    "Date of Publication of Abstract u/s 11(A)",
    "Appropriate Office",
]

# The four IPO appropriate offices. PyMuPDF sometimes wraps a cell mid-word
# (e.g. "KOLKA\nTA"); after cleaning that becomes "KOLKA TA". Normalise the
# office field back to its canonical spelling.
_OFFICES = {"DELHI", "MUMBAI", "CHENNAI", "KOLKATA", "AHMEDABAD"}


def _normalise_office(value):
    collapsed = value.replace(" ", "").upper()
    for office in _OFFICES:
        if collapsed == office:
            return office
    return value


def _journal_date(pages_text):
    """Return the journal issue date 'dd/mm/yyyy' from any page footer, or ''."""

    for text in pages_text:
        m = _JOURNAL_DATE.search(text)
        if m:
            return m.group(1)
    return ""


def _grant_page_range(pages_text):
    """Return range(start, end) of pages belonging to the grant section.

    Start = first page carrying the grant header. End = first later page
    that opens a different section. Returns None when the file has no
    grant section at all.
    """

    starts = [i for i, t in enumerate(pages_text) if _GRANT_START.search(t)]
    if not starts:
        return None

    start = min(starts)
    end = len(pages_text)

    for i in range(start + 1, len(pages_text)):
        if _SECTION_END.search(pages_text[i]) and not _GRANT_START.search(pages_text[i]):
            end = i
            break

    return range(start, end)


def _patent_anchor(row):
    """Return the column index of the Patent Number cell, or None.

    A granted-patent row has a 5-7 digit Patent Number immediately followed
    by a long Application Number. Anchoring on this pair makes column
    mapping robust to spurious leading/trailing columns that PyMuPDF's
    table detector occasionally introduces (9- vs 10-column tables).
    """

    for i in range(len(row) - 1):
        cell = (row[i] or "").strip()
        nxt = (row[i + 1] or "").strip()
        if _PATENT_NO.match(cell) and _APP_NO.match(nxt):
            return i
    return None


def _rows_from_page(page):
    """Extract granted-patent rows from one page via table detection."""

    records = []

    tables = page.find_tables()

    for table in tables.tables:

        # The grant table has 9 data columns; the detector may add a
        # spurious 10th. FER tables (6 columns) and notices are shorter and
        # will not anchor, so they are rejected row-by-row below.
        if table.col_count < len(_COLUMNS):
            continue

        for row in table.extract():

            anchor = _patent_anchor(row)
            if anchor is None:
                continue

            # Serial Number is one column before the Patent Number anchor;
            # the remaining eight fields follow it in order.
            start = anchor - 1
            if start < 0 or start + len(_COLUMNS) > len(row):
                continue

            record = {}
            for offset, field in enumerate(_COLUMNS):
                cell = row[start + offset]
                record[field] = clean(cell if cell is not None else "")

            record["Appropriate Office"] = _normalise_office(
                record["Appropriate Office"]
            )

            records.append(record)

    return records


def extract_grants(pdf_files, progress_callback=None, status_callback=None):
    """Extract granted patents from one or more journal PDFs.

    Iterates the selected PDFs, extracts only the granted-patents section
    from each, annotates every record with Journal Date, Source PDF and
    Page, merges them, and returns the list stably sorted by Journal Date.
    """

    all_records = []

    total_pages = 0
    doc_handles = []

    # Open all documents up front so progress can be reported cumulatively.
    for pdf in pdf_files:
        doc = fitz.open(pdf)
        doc_handles.append((pdf, doc))
        total_pages += len(doc)

    processed_pages = 0

    try:
        for pdf, doc in doc_handles:

            basename = os.path.basename(pdf)

            if status_callback:
                status_callback(f"Scanning {basename}...")

            pages_text = [page.get_text() for page in doc]
            journal_date = _journal_date(pages_text)

            page_range = _grant_page_range(pages_text)

            if page_range is None:
                if status_callback:
                    status_callback(
                        f"No granted-patents section found in {basename}."
                    )
                processed_pages += len(doc)
                if progress_callback:
                    progress_callback(processed_pages, total_pages)
                continue

            file_count = 0

            for page_index in page_range:

                records = _rows_from_page(doc[page_index])

                for record in records:
                    record["Journal Date"] = journal_date
                    record["Source PDF"] = basename
                    record["Page"] = page_index + 1

                all_records.extend(records)
                file_count += len(records)

                processed_pages += 1
                if progress_callback:
                    progress_callback(processed_pages, total_pages)

            # Pages outside the grant range still count toward progress.
            processed_pages += len(doc) - len(page_range)
            if progress_callback:
                progress_callback(min(processed_pages, total_pages), total_pages)

            if status_callback:
                status_callback(
                    f"{basename}: {file_count} granted patent(s)."
                )

    finally:
        for _, doc in doc_handles:
            doc.close()

    # Merge order: stable sort by journal date so records sharing a date
    # keep their in-journal (serial) order. Records with an unparseable or
    # missing date sort last.
    def _key(record):
        value = record.get("Journal Date", "")
        try:
            return (0, datetime.strptime(value, "%d/%m/%Y"))
        except ValueError:
            return (1, datetime.max)

    all_records.sort(key=_key)

    return all_records
