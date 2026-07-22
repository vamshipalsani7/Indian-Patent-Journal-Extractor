import fitz
import re

from patterns import patterns
from cleaner import clean


def extract_patents(pdf_path, progress_callback=None):

    doc = fitz.open(pdf_path)

    patents = []
    total_pages = len(doc)

    for page_number, page in enumerate(doc):
        if progress_callback:
         progress_callback(page_number + 1, total_pages)

        text = page.get_text()

        if "(21)" not in text:
            continue

        patent = {}

        for field, pattern in patterns.items():

            match = re.search(pattern, text, re.DOTALL)

            if match:
                patent[field] = clean(match.group(1))
            else:
                patent[field] = ""

        patent["Page"] = page_number + 1

        patents.append(patent)

    return patents