import sys
import traceback

import fitz
import re

from patterns import patterns
from cleaner import clean


class PatentExtractionError(Exception):
    """Raised when a single patent record fails to parse.

    Carries enough context (page, application number, title, parser
    stage) for the GUI to show a precise, actionable error instead of a
    raw exception dump.
    """

    def __init__(
        self,
        message,
        stage="",
        application="",
        title="",
        page=None,
    ):
        super().__init__(message)
        self.stage = stage
        self.application = application
        self.title = title
        self.page = page


def _log(message):
    """Print a debug line safely.

    In a --windowed PyInstaller build sys.stdout is None, so a bare
    print() would raise. Logging must never break extraction, so any
    failure here is swallowed.
    """

    try:
        print(message)
        sys.stdout.flush()
    except Exception:
        pass


def extract_patents(pdf_path, progress_callback=None):

    doc = fitz.open(pdf_path)

    patents = []
    total_pages = len(doc)
    patent_number = 0

    for page_number, page in enumerate(doc):

        if progress_callback:
            progress_callback(page_number + 1, total_pages)

        text = page.get_text()

        if "(21)" not in text:
            continue

        patent_number += 1
        patent = {}
        current_field = None

        # Each patent is parsed individually. If anything goes wrong, the
        # exact patent (number, application, title, page, stage) is logged
        # and re-raised with that context - never silently skipped.
        try:

            for field, pattern in patterns.items():

                current_field = field

                match = re.search(pattern, text, re.DOTALL)

                if match:
                    patent[field] = clean(match.group(1))
                else:
                    patent[field] = ""

            patent["Page"] = page_number + 1

            _log(
                f"Processing patent {patent_number}... "
                f"Application No: {patent.get('Application No', '')} | "
                f"Title: {patent.get('Title', '')[:60]} | "
                f"Page: {page_number + 1}"
            )

        except Exception as exc:

            _log(traceback.format_exc())
            _log(f"Application No: {patent.get('Application No', '')}")
            _log(f"Title: {patent.get('Title', '')}")
            _log(f"Page: {page_number + 1}")

            raise PatentExtractionError(
                str(exc),
                stage=f"field parsing ({current_field})",
                application=patent.get("Application No", ""),
                title=patent.get("Title", ""),
                page=page_number + 1,
            ) from exc

        patents.append(patent)

    return patents
