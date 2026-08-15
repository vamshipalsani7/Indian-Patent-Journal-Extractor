import os
import re

from datetime import datetime

import fitz

from patent_extractor import extract_patents
from journal_utils import get_journal_metadata
from patterns import patterns
from cleaner import clean


# ------------------------------------------------------------------
# Content-driven journal-date resolution
# ------------------------------------------------------------------
#
# Some Indian Patent Journal issues are split across more than one PDF.
# Only the first part carries the front-matter header ("ISSUE NO." /
# "DATE:"); the remaining part(s) have no header at all. Those parts,
# however, still carry field (43) Publication Date on every patent
# record, and within a single issue that date is the journal date.
#
# So a headerless PDF can identify its own journal date from its
# content, with no reliance on filenames.
# ------------------------------------------------------------------

# Reuse the exact (43) Publication Date pattern the extractor uses,
# so there is a single source of truth for the field.
_PUBLICATION_DATE_PATTERN = patterns["Publication Date"]

# Once this many publication dates have been seen and they are all
# identical, the journal date is treated as confidently established
# and the remaining pages are not read.
_CONFIDENT_SAMPLE = 25


def _resolve_date_from_content(pdf_path):
    """
    Determine a journal's publication date from the patent records
    themselves, using field (43) Publication Date.

    Nearly every record in a journal carries the same (43) date, so the
    scan stops early as soon as a confident, unanimous value is found,
    and only falls back to a full scan (returning the most common value)
    if the early sample is not unanimous.

    Returns a "dd/mm/yyyy" string, or None if no (43) date is found.
    """

    try:
        doc = fitz.open(pdf_path)
    except Exception:
        return None

    counts = {}
    collected = 0
    confident = None

    try:
        for page in doc:

            match = re.search(
                _PUBLICATION_DATE_PATTERN,
                page.get_text(),
                re.DOTALL,
            )

            if not match:
                continue

            value = clean(match.group(1))

            if not value:
                continue

            counts[value] = counts.get(value, 0) + 1
            collected += 1

            # Early stop: enough samples seen and all identical.
            if collected >= _CONFIDENT_SAMPLE and len(counts) == 1:
                confident = value
                break

    finally:
        doc.close()

    if confident is not None:
        return confident

    if not counts:
        return None

    # Not unanimous within the sample: take the most common value.
    return max(counts, key=counts.get)


def _resolve_identity(pdf_path, header_metadata, date_to_issue):
    """
    Resolve (journal_date_str, issue) for a single PDF.

    Date resolution order:
      1. Journal header date (preferred, cheap - page 1 only).
      2. Mode of (43) Publication Date from the patent records.

    Issue resolution:
      1. Journal header issue, when present.
      2. Date -> Issue lookup built from header-bearing PDFs.
      3. "Not Found" (the record is still kept and correctly dated).

    Returns (None, "Not Found") when no date can be established.
    """

    header_date = None
    header_issue = "Not Found"

    if header_metadata is not None:
        if header_metadata.get("date") not in (None, "Not Found"):
            header_date = header_metadata["date"]
        if header_metadata.get("issue") not in (None, "Not Found"):
            header_issue = header_metadata["issue"]

    # ---- Date ----
    if header_date is not None:
        journal_date_str = header_date          # preferred, no body read
    else:
        journal_date_str = _resolve_date_from_content(pdf_path)

    if journal_date_str is None:
        return None, "Not Found"

    # ---- Issue ----
    if header_issue != "Not Found":
        issue = header_issue
    else:
        issue = date_to_issue.get(journal_date_str, "Not Found")

    return journal_date_str, issue


def extract_date_range(
    folder_path,
    from_date,
    to_date,
    progress_callback=None,
    status_callback=None,
):

    pdf_files = []

    # Search recursively inside all subfolders
    for root, dirs, files in os.walk(folder_path):

        for file in files:

            if file.lower().endswith(".pdf"):

                pdf_files.append(
                    os.path.join(root, file)
                )

    pdf_files.sort()

    if status_callback:
        status_callback(f"Found {len(pdf_files)} PDF(s).")

    # --------------------------------------------------------------
    # Pass 1 - read page-1 header metadata for every PDF (cheap) and
    # build a Date -> Issue lookup from the header-bearing journals.
    # --------------------------------------------------------------

    header_metadata_by_pdf = {}
    date_to_issue = {}

    for pdf in pdf_files:

        metadata = get_journal_metadata(pdf)

        header_metadata_by_pdf[pdf] = metadata

        if metadata is None:
            continue

        if metadata["date"] == "Not Found":
            continue

        if metadata["issue"] == "Not Found":
            continue

        date_to_issue[metadata["date"]] = metadata["issue"]

    # --------------------------------------------------------------
    # Pass 2 - resolve each journal's date/issue (falling back to
    # content when the header is missing), filter by range, then
    # extract and annotate.
    # --------------------------------------------------------------

    all_patents = []

    matched = 0

    for pdf in pdf_files:

        journal_date_str, issue = _resolve_identity(
            pdf,
            header_metadata_by_pdf.get(pdf),
            date_to_issue,
        )

        if journal_date_str is None:

            if status_callback:
                status_callback(
                    f"Skipped (no journal date found): "
                    f"{os.path.basename(pdf)}"
                )

            continue

        try:
            journal_date = datetime.strptime(
                journal_date_str,
                "%d/%m/%Y",
            ).date()
        except ValueError:
            continue

        if not (from_date <= journal_date <= to_date):
            continue

        matched += 1

        if status_callback:
            status_callback(
                f"Journal {matched}\n"
                f"Issue : {issue}\n"
                f"Date  : {journal_date_str}"
            )

        patents = extract_patents(
            pdf,
            progress_callback=progress_callback
        )

        for patent in patents:

            patent["Journal Issue"] = issue
            patent["Journal Date"] = journal_date_str
            patent["Source PDF"] = os.path.basename(pdf)

        all_patents.extend(patents)

    return all_patents


# ---------------------------------------------------
# TEST
# ---------------------------------------------------

if __name__ == "__main__":

    folder = r"C:\Users\91630\OneDrive\Desktop\Patent extractor\input"

    from_date = datetime.strptime(
        "03/07/2026",
        "%d/%m/%Y"
    ).date()

    to_date = datetime.strptime(
        "31/07/2026",
        "%d/%m/%Y"
    ).date()

    patents = extract_date_range(
        folder,
        from_date,
        to_date
    )

    print("\n--------------------------------------")
    print(f"Total patents extracted : {len(patents)}")
    print("--------------------------------------")

    if patents:

        print("\nFirst Patent\n")

        for key, value in patents[0].items():
            print(f"{key}: {value}")
