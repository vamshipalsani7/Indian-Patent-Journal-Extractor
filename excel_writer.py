import re

import pandas as pd


# Characters that Excel / openpyxl forbid inside a worksheet cell
# (control codes 0x00-0x08, 0x0B-0x0C, 0x0E-0x1F). PDF text extraction
# can leave one of these in a field - e.g. a stray NUL (0x00) inside an
# Abstract - which makes openpyxl raise IllegalCharacterError and abort
# the whole workbook. Stripping them lets any journal be written. Only
# non-printable control codes are removed; visible text is never altered.
_ILLEGAL_XLSX_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _sanitize(value):
    """Remove worksheet-illegal control characters from a string cell."""

    if isinstance(value, str):
        return _ILLEGAL_XLSX_CHARS.sub("", value)

    return value


def save_to_excel(patents, output_file):

    cleaned = [
        {key: _sanitize(value) for key, value in patent.items()}
        for patent in patents
    ]

    df = pd.DataFrame(cleaned)
    df.to_excel(output_file, index=False)
