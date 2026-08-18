"""
Combinable filters for the v6 discovery layer.

A `Filters` object holds optional criteria; unset criteria are ignored.
`apply()` returns the subset of records matching ALL set criteria (logical
AND), so filters combine as required. Reads canonical fields only; never
mutates records. Designed to run after a search (filter the result set) or
standalone (filter the whole dataset).
"""

from datetime import datetime

from facets import ipc_levels


def parse_date(value):
    """Parse a 'dd/mm/yyyy' string to a date, or None."""
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%d/%m/%Y").date()
    except (ValueError, AttributeError):
        return None


class Filters:

    def __init__(
        self,
        patent_type=None,        # None/"All" | "Published" | "Granted"
        journal_from=None,       # "dd/mm/yyyy"
        journal_to=None,
        applicants=None,         # iterable of exact applicant values
        inventors=None,          # iterable of exact inventor values
        ipc=None,                # iterable of IPC level strings (any depth)
        application_number=None,  # partial (substring)
        patent_number=None,      # partial (substring)
        pub_from=None,           # "dd/mm/yyyy"
        pub_to=None,
        sources=None,            # iterable of Source PDF basenames
    ):
        self.patent_type = patent_type or None
        self.journal_from = parse_date(journal_from)
        self.journal_to = parse_date(journal_to)
        self.applicants = set(applicants) if applicants else None
        self.inventors = set(inventors) if inventors else None
        self.ipc = {c.upper() for c in ipc} if ipc else None
        self.application_number = (application_number or "").strip().casefold() or None
        self.patent_number = (patent_number or "").strip().casefold() or None
        self.pub_from = parse_date(pub_from)
        self.pub_to = parse_date(pub_to)
        self.sources = set(sources) if sources else None

    def is_active(self):
        return any([
            self.patent_type and self.patent_type != "All",
            self.journal_from, self.journal_to,
            self.applicants, self.inventors, self.ipc,
            self.application_number, self.patent_number,
            self.pub_from, self.pub_to, self.sources,
        ])

    def _match(self, record):
        # Patent type
        if self.patent_type and self.patent_type != "All":
            if record.type != self.patent_type:
                return False

        # Journal date range
        if self.journal_from or self.journal_to:
            jd = parse_date(record.get("journal_date"))
            if jd is None:
                return False
            if self.journal_from and jd < self.journal_from:
                return False
            if self.journal_to and jd > self.journal_to:
                return False

        # Publication date range
        if self.pub_from or self.pub_to:
            pd = parse_date(record.get("publication_date"))
            if pd is None:
                return False
            if self.pub_from and pd < self.pub_from:
                return False
            if self.pub_to and pd > self.pub_to:
                return False

        # Applicant / inventor (exact facet-value membership)
        if self.applicants is not None:
            if record.get("applicant") not in self.applicants:
                return False
        if self.inventors is not None:
            if record.get("inventor") not in self.inventors:
                return False

        # IPC (hierarchical: selection at any level matches)
        if self.ipc is not None:
            if not (self.ipc & ipc_levels(record.get("ipc"))):
                return False

        # Numbers (partial / substring)
        if self.application_number is not None:
            if self.application_number not in record.get("application_number").casefold():
                return False
        if self.patent_number is not None:
            if self.patent_number not in record.get("patent_number").casefold():
                return False

        # Source PDF
        if self.sources is not None:
            if record.get("source_pdf") not in self.sources:
                return False

        return True

    def apply(self, records):
        """Return the records matching all active criteria."""
        if not self.is_active():
            return list(records)
        return [r for r in records if self._match(r)]
