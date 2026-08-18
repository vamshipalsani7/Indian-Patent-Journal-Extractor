"""
Search engine for the v6 layer (Phase 1: exact / phrase / boolean,
field-specific). Fuzzy and related/thesaurus search are added in a later
phase; the result structure already carries a match-type per field so those
can slot in without changing callers.

Evaluates a parsed query AST against a SearchIndex, restricted to a set of
selected canonical fields, and returns ranked results with match reasons.
"""

from query_parser import parse, positive_terms, Term, Phrase, And, Or, Not
from search_index import tokenize

# Field weights for the heuristic relevance score. Higher = more important.
_FIELD_WEIGHTS = {
    "title": 1.0,
    "abstract": 0.7,
    "claims": 0.7,
    "applicant": 0.6,
    "inventor": 0.6,
    "ipc": 0.5,
    "application_number": 0.5,
    "patent_number": 0.5,
    "priority": 0.3,
    "publication_date": 0.2,
    "journal_date": 0.2,
    "source_pdf": 0.2,
    "office": 0.2,
}

# Human labels for canonical fields (for match-reason display).
_FIELD_LABEL = {
    "title": "Title",
    "abstract": "Abstract",
    "claims": "Claims",
    "applicant": "Applicant",
    "inventor": "Inventor",
    "ipc": "IPC",
    "application_number": "Application No",
    "patent_number": "Patent No",
    "priority": "Priority",
    "publication_date": "Publication Date",
    "journal_date": "Journal Date",
    "source_pdf": "Source PDF",
    "office": "Office",
}


class SearchResult:
    def __init__(self, record, reasons, relevance):
        self.record = record
        self.reasons = reasons          # list[(match_type, field_label)]
        self.relevance = relevance      # heuristic integer percent

    @property
    def match_summary(self):
        return ", ".join(f"{t} — {f}" for t, f in self.reasons)


def _term_ids(index, fields, value):
    """Ids where ALL tokens of `value` appear together in one field, unioned
    across the selected fields."""
    tokens = tokenize(value)
    if not tokens:
        return set()

    result = set()
    for field in fields:
        per_field = None
        for token in tokens:
            postings = index.postings(field, token)
            per_field = postings if per_field is None else (per_field & postings)
            if not per_field:
                break
        if per_field:
            result |= per_field
    return result


def _phrase_ids(index, fields, value):
    """Ids where the exact phrase appears contiguously in one field."""
    tokens = tokenize(value)
    if not tokens:
        return set()

    phrase = value.casefold().strip()
    result = set()
    for field in fields:
        candidate = None
        for token in tokens:
            postings = index.postings(field, token)
            candidate = postings if candidate is None else (candidate & postings)
            if not candidate:
                break
        if not candidate:
            continue
        for rid in candidate:
            if phrase in index.field_text(rid, field):
                result.add(rid)
    return result


def _evaluate(node, index, fields):
    if node is None:
        return set(index.all_ids)
    if isinstance(node, Term):
        return _term_ids(index, fields, node.value)
    if isinstance(node, Phrase):
        return _phrase_ids(index, fields, node.value)
    if isinstance(node, Not):
        return set(index.all_ids) - _evaluate(node.child, index, fields)
    if isinstance(node, And):
        ids = None
        for item in node.items:
            got = _evaluate(item, index, fields)
            ids = got if ids is None else (ids & got)
            if not ids:
                return set()
        return ids or set()
    if isinstance(node, Or):
        ids = set()
        for item in node.items:
            ids |= _evaluate(item, index, fields)
        return ids


def _reasons_and_score(index, dataset, rid, fields, terms):
    """Per-field exact-match reasons + heuristic relevance for one record."""
    reasons = []
    score = 0.0
    for field in fields:
        text = index.field_text(rid, field)
        if not text:
            continue
        for value in terms:
            v = value.casefold().strip()
            if v and v in text:
                reasons.append(("Exact", _FIELD_LABEL.get(field, field)))
                score += _FIELD_WEIGHTS.get(field, 0.3)
                break
    # Normalise to a whole-percent heuristic (capped at 100).
    relevance = min(100, round(score / max(len(fields), 1) * 100)) if reasons else 0
    return reasons, relevance


def search(dataset, index, query, fields, sort_by_relevance=True):
    """Run a query and return ranked SearchResults.

    `fields` is the list of canonical fields to search in (field-specific
    search). Returns results sorted by heuristic relevance (then journal date
    descending) when `sort_by_relevance`, else in dataset order.
    """

    ast = parse(query)
    ids = _evaluate(ast, index, fields)

    terms = positive_terms(ast)

    results = []
    for rid in ids:
        record = dataset.get(rid)
        if record is None:
            continue
        reasons, relevance = _reasons_and_score(index, dataset, rid, fields, terms)
        results.append(SearchResult(record, reasons, relevance))

    if sort_by_relevance:
        results.sort(
            key=lambda r: (r.relevance, r.record.get("journal_date")),
            reverse=True,
        )

    return results
