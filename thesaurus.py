"""
Local, editable thesaurus for RELATED / semantic search.

Related search broadens recall using a curated synonym/expansion map - NOT
machine-learning embeddings and NOT any external/paid API. It is fully offline
and user-editable (thesaurus.json next to this module). Related matches are
always labeled "Related", never silently treated as exact.

Design: `thesaurus.json` holds `groups` (lists of conceptually related terms).
`expand(term)` returns the other members of every group the term belongs to.
Matching is case-insensitive on the whole term/phrase.
"""

import json
import os

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_PATH = os.path.join(_THIS_DIR, "thesaurus.json")

# Built-in fallback so related search still works if the JSON is missing.
_FALLBACK_GROUPS = [
    ["pesticide", "insecticide", "herbicide", "fungicide", "agrochemical",
     "crop protection", "pest control"],
    ["electric vehicle", "ev", "electric car", "battery electric vehicle", "bev"],
    ["artificial intelligence", "ai", "machine learning", "ml", "deep learning",
     "neural network"],
]


class Thesaurus:

    def __init__(self, groups):
        # term -> set of group indices it belongs to
        self._term_groups = {}
        self._groups = []
        for group in groups:
            normalised = [t.strip().casefold() for t in group if t and t.strip()]
            if len(normalised) < 2:
                continue
            gi = len(self._groups)
            self._groups.append(normalised)
            for term in normalised:
                self._term_groups.setdefault(term, set()).add(gi)

    def expand(self, term):
        """Return related terms for `term` (its group-mates), excluding itself."""
        key = (term or "").strip().casefold()
        if not key:
            return []
        related = set()
        for gi in self._term_groups.get(key, ()):
            related.update(self._groups[gi])
        related.discard(key)
        return sorted(related)

    def __len__(self):
        return len(self._groups)


def load(path=None):
    """Load the thesaurus from JSON (default: alongside this module).
    Falls back to a small built-in set if the file is absent/invalid."""
    path = path or _DEFAULT_PATH
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        groups = data.get("groups", [])
        if groups:
            return Thesaurus(groups)
    except (OSError, ValueError):
        pass
    return Thesaurus(_FALLBACK_GROUPS)
