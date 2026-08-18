"""
Rule-based, multi-label technology categorisation (v6 Phase 6).

ANALYSIS METADATA ONLY. `classify()` returns a list of category names for a
record; it NEVER modifies the record or any extracted field (IPC, Title,
Applicant, Inventor, Abstract, ...). This is not an official patent
classification - it is a transparent, editable keyword/IPC rule layer
(categories.json).

Matching per category: any keyword hit OR any IPC-prefix hit.
- single-word keyword -> matched as a whole token (so "ai" won't match "email")
- multi-word / hyphenated keyword -> matched as a substring
- IPC prefix -> matched against the record's hierarchical IPC level strings
"""

import json
import os

from search_index import tokenize
from facets import ipc_levels

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_PATH = os.path.join(_THIS_DIR, "categories.json")

_FALLBACK = [
    {"name": "Artificial Intelligence / ML",
     "keywords": ["artificial intelligence", "machine learning", "neural network"],
     "ipc": ["G06N"]},
    {"name": "Batteries / EV",
     "keywords": ["battery", "electric vehicle", "lithium ion"],
     "ipc": ["H01M", "B60L"]},
]


class Categories:

    def __init__(self, definitions):
        self.definitions = definitions

    def names(self):
        return [c["name"] for c in self.definitions]

    def classify(self, record):
        """Return the list of category names matching this record (may be
        empty; may contain several). The record is not modified."""
        text = " ".join([
            record.get("title"), record.get("abstract"), record.get("applicant"),
        ]).casefold()
        tokens = set(tokenize(text))
        levels = ipc_levels(record.get("ipc"))

        matched = []
        for cat in self.definitions:
            if self._matches(cat, text, tokens, levels):
                matched.append(cat["name"])
        return matched

    @staticmethod
    def _matches(cat, text, tokens, levels):
        for keyword in cat.get("keywords", []):
            key = keyword.strip().casefold()
            if not key:
                continue
            if " " in key or "-" in key:
                if key in text:
                    return True
            elif key in tokens:
                return True
        for prefix in cat.get("ipc", []):
            if prefix.upper() in levels:
                return True
        return False


def load(path=None):
    """Load categories from JSON (default: alongside this module); falls back
    to a small built-in set if the file is missing/invalid."""
    path = path or _DEFAULT_PATH
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        definitions = data.get("categories", [])
        if definitions:
            return Categories(definitions)
    except (OSError, ValueError):
        pass
    return Categories(_FALLBACK)
