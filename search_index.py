"""
In-memory inverted index over a Dataset's canonical fields.

Built once per dataset; queries hit the index instead of re-scanning records.
Plain-Python dicts: field -> token -> set(record_id). Also keeps the
normalised per-record field text (for phrase verification) and a global
vocabulary (for fuzzy search in a later phase). Zero third-party dependency,
fully offline. Designed behind a small interface so a SQLite FTS5 backend can
replace it later without changing callers.
"""

import re

from dataset import CANONICAL_FIELDS

# Unicode-aware tokeniser: alphanumeric runs, casefolded. Keeps IPC codes
# (h01m) and numbers (202317012934) intact; drops punctuation/whitespace.
_TOKEN = re.compile(r"\w+", re.UNICODE)

# Text fields worth indexing for free-text search (everything except pure
# provenance). Numbers get their own fields too so field-specific number
# search works.
INDEXED_FIELDS = [
    f for f in CANONICAL_FIELDS
    if f not in ("page",)
]


def tokenize(text):
    if not text:
        return []
    return [t.casefold() for t in _TOKEN.findall(text)]


class SearchIndex:

    def __init__(self, dataset):
        self.dataset = dataset
        # field -> token -> set(record_id)
        self._postings = {f: {} for f in INDEXED_FIELDS}
        # record_id -> field -> normalised lowercase text (for phrases)
        self._text = {}
        # global vocabulary (for fuzzy search, later phase)
        self.vocabulary = set()
        self.all_ids = set()
        self._build()

    def _build(self):
        for record in self.dataset.records:
            rid = record.id
            self.all_ids.add(rid)
            self._text[rid] = {}

            for field in INDEXED_FIELDS:
                value = record.get(field)
                self._text[rid][field] = value.casefold()

                tokens = tokenize(value)
                if not tokens:
                    continue

                field_postings = self._postings[field]
                for token in tokens:
                    field_postings.setdefault(token, set()).add(rid)
                    self.vocabulary.add(token)

    # -- query primitives -------------------------------------------------

    def postings(self, field, token):
        """Record ids whose `field` contains `token` (exact token match)."""
        return self._postings.get(field, {}).get(token, set())

    def field_text(self, record_id, field):
        """Normalised lowercase text of a field, for phrase verification."""
        return self._text.get(record_id, {}).get(field, "")

    def has_field_data(self, field):
        """True if any record carries data in this field (e.g. grants have no
        IPC, so IPC search over a grant-only dataset is empty)."""
        return bool(self._postings.get(field))
