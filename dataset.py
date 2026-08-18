"""
Unified in-memory dataset for the v6 search/discovery layer.

The two v5 extraction backends emit records with DIFFERENT schemas and some
fields present in only one type. This module normalises both into a single
canonical view for searching, while keeping each record's ORIGINAL dict
untouched for faithful Excel export. It never modifies extracted data and
never fabricates values - a field a record type does not have is "".

v6 consumes extractor output; it does not import into the extraction engine.
"""

# Canonical searchable field names (stable across both patent types).
CANONICAL_FIELDS = [
    "title",
    "abstract",
    "claims",
    "applicant",
    "inventor",
    "ipc",
    "application_number",
    "patent_number",
    "filing_date",
    "priority",
    "publication_date",
    "journal_date",
    "source_pdf",
    "page",
    "office",
]

# Map canonical field -> raw key, per patent type. None = not present in that
# schema. "priority" is special-cased (composed) below.
_PUBLISHED_MAP = {
    "title": "Title",
    "abstract": "Abstract",
    "claims": None,
    "applicant": "Applicant",
    "inventor": "Inventor",
    "ipc": "IPC",
    "application_number": "Application No",
    "patent_number": None,
    "filing_date": "Filing Date",
    "publication_date": "Publication Date",
    "journal_date": "Journal Date",
    "source_pdf": "Source PDF",
    "page": "Page",
    "office": None,
}

_GRANTED_MAP = {
    "title": "Title of Invention",
    "abstract": None,
    "claims": None,
    "applicant": "Name of Patentee",
    "inventor": None,
    "ipc": None,
    "application_number": "Application Number",
    "patent_number": "Patent Number",
    "filing_date": "Date of Application",
    "publication_date": "Date of Publication of Abstract u/s 11(A)",
    "journal_date": "Journal Date",
    "source_pdf": "Source PDF",
    "page": "Page",
    "office": "Appropriate Office",
    "priority": "Date of Priority",
}


def _as_str(value):
    return "" if value is None else str(value)


def _published_priority(raw):
    parts = [
        raw.get("Priority Document No", ""),
        raw.get("Priority Date", ""),
        raw.get("Priority Country", ""),
    ]
    return " ".join(p for p in (_as_str(x).strip() for x in parts) if p)


class PatentRecord:
    """One extracted patent, with a raw dict and a canonical view."""

    def __init__(self, raw, patent_type, source_path=""):
        self.raw = raw
        self.type = patent_type            # "Published" | "Granted"
        self.source_path = source_path     # absolute PDF path, for open/link
        self.canonical = self._build_canonical()
        self.id = self._build_id()

    def _build_canonical(self):
        raw = self.raw

        if self.type == "Published":
            field_map = _PUBLISHED_MAP
        else:
            field_map = _GRANTED_MAP

        canonical = {}
        for field in CANONICAL_FIELDS:
            if field == "priority":
                if self.type == "Published":
                    canonical[field] = _published_priority(raw)
                else:
                    canonical[field] = _as_str(raw.get(field_map.get(field)))
                continue

            key = field_map.get(field)
            canonical[field] = _as_str(raw.get(key)) if key else ""

        return canonical

    def _build_id(self):
        c = self.canonical
        return "|".join([
            self.type,
            c.get("application_number", ""),
            c.get("patent_number", ""),
            c.get("journal_date", ""),
            c.get("page", ""),
        ])

    def get(self, field):
        return self.canonical.get(field, "")


class Dataset:
    """A searchable collection of PatentRecords (Published and/or Granted)."""

    def __init__(self):
        self.records = []
        self._by_id = {}

    @classmethod
    def from_records(cls, raw_records, patent_type, source_paths=None):
        """Convenience constructor for a single batch of extractor output.

        Equivalent to ``Dataset().add_records(...)``. Use ``add_records`` to
        append further batches (e.g. loading more PDFs, or mixing Published
        and Granted) into the same dataset.
        """
        return cls().add_records(raw_records, patent_type, source_paths)

    def add_records(self, raw_records, patent_type, source_paths=None):
        """Add extractor output. `source_paths` maps a Source PDF basename to
        its absolute path, for open/link features."""

        source_paths = source_paths or {}

        for raw in raw_records:
            record = PatentRecord(
                raw,
                patent_type,
                source_path=source_paths.get(raw.get("Source PDF", ""), ""),
            )
            self.records.append(record)
            self._by_id[record.id] = record

        return self

    def get(self, record_id):
        return self._by_id.get(record_id)

    def __len__(self):
        return len(self.records)
