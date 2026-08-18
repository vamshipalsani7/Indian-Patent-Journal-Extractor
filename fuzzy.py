"""
Bounded fuzzy matching for the v6 search layer.

Handles spelling variations / minor typos (e.g. "vehcle" -> "vehicle") by
finding close tokens in the index vocabulary via edit-distance similarity.
Deliberately conservative to avoid meaningless matches: a minimum token
length, a same-first-character and similar-length prefilter, and a high
similarity cutoff. Pure stdlib (difflib) - offline, no dependency.
"""

import difflib

_MIN_LEN = 4          # don't fuzzy-match very short tokens
_LEN_WINDOW = 2       # candidate length within +/- this of the token
_CUTOFF = 0.82        # difflib similarity ratio threshold
_MAX_RESULTS = 5      # cap variants per token


def candidates(token, vocabulary, max_results=_MAX_RESULTS, cutoff=_CUTOFF):
    """Return up to `max_results` vocabulary tokens close to `token`.

    Empty for short tokens or when nothing is close enough. The token itself
    is never returned.
    """
    if not token or len(token) < _MIN_LEN:
        return []

    first = token[0]
    lo, hi = len(token) - _LEN_WINDOW, len(token) + _LEN_WINDOW

    pool = [
        w for w in vocabulary
        if w != token and w and w[0] == first and lo <= len(w) <= hi
    ]

    return difflib.get_close_matches(token, pool, n=max_results, cutoff=cutoff)
