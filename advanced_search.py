"""
Advanced search: Exact + Related (thesaurus) + Fuzzy, with per-field match
reasons and a heuristic relevance score.

Layered ON TOP of the frozen Phase 1 engine - it imports Phase 1 primitives
(`_evaluate`, `_FIELD_WEIGHTS`, `_FIELD_LABEL`, `SearchResult`) and does not
modify `search_engine.py`. With related and fuzzy both off, results equal the
Phase 1 exact search (same record ids), so this is a strict superset the UI
can call for every search.

Semantics:
- Exact: the parsed boolean query (AND/OR/NOT/phrase) matched in a field.
- Related: a curated-thesaurus expansion of a positive query term matched
  (recall-broadening; labeled Related, never Exact).
- Fuzzy: a close spelling variant of a positive query term matched.
Related/Fuzzy broaden recall on the query's positive terms; records they add
(not already exact) are included and labeled accordingly.
"""

from query_parser import parse, positive_terms
from search_index import tokenize
from search_engine import _evaluate, _FIELD_WEIGHTS, _FIELD_LABEL, SearchResult
import fuzzy as fuzzy_mod

# Match-type weights and precedence (Exact strongest).
_TYPE_WEIGHT = {"Exact": 1.0, "Related": 0.7, "Fuzzy": 0.5}
_TYPE_RANK = {"Exact": 3, "Related": 2, "Fuzzy": 1}


def _match_per_field(index, fields, value):
    """{field: set(ids)} where all tokens of `value` co-occur in that field
    (phrase-verified for multi-word values)."""
    tokens = tokenize(value)
    out = {}
    if not tokens:
        return out

    multiword = len(tokens) > 1
    phrase = value.casefold().strip()

    for field in fields:
        candidate = None
        for token in tokens:
            postings = index.postings(field, token)
            candidate = postings if candidate is None else (candidate & postings)
            if not candidate:
                break
        if not candidate:
            continue
        if multiword:
            candidate = {
                rid for rid in candidate if phrase in index.field_text(rid, field)
            }
        if candidate:
            out[field] = candidate
    return out


def search(dataset, index, query, fields,
           use_related=False, use_fuzzy=False, thesaurus=None,
           sort_by_relevance=True):
    """Run an advanced search; return ranked SearchResults with typed reasons."""

    ast = parse(query)
    exact_ids = _evaluate(ast, index, fields)
    terms = positive_terms(ast)

    # record_id -> {canonical_field: match_type}, keeping the strongest type.
    match = {}

    def add(ids_by_field, mtype):
        for field, ids in ids_by_field.items():
            for rid in ids:
                current = match.setdefault(rid, {}).get(field)
                if current is None or _TYPE_RANK[mtype] > _TYPE_RANK[current]:
                    match[rid][field] = mtype

    # Exact reasons: only for records that satisfied the boolean query.
    for term in terms:
        per_field = _match_per_field(index, fields, term)
        per_field = {f: (ids & exact_ids) for f, ids in per_field.items()}
        per_field = {f: ids for f, ids in per_field.items() if ids}
        add(per_field, "Exact")

    result_ids = set(exact_ids)

    if use_related and thesaurus is not None:
        for term in terms:
            for expansion in thesaurus.expand(term):
                per_field = _match_per_field(index, fields, expansion)
                for ids in per_field.values():
                    result_ids |= ids
                add(per_field, "Related")

    if use_fuzzy:
        for term in terms:
            for token in tokenize(term):
                if token in index.vocabulary:
                    continue  # exact form exists; no need to fuzz
                for variant in fuzzy_mod.candidates(token, index.vocabulary):
                    per_field = _match_per_field(index, fields, variant)
                    for ids in per_field.values():
                        result_ids |= ids
                    add(per_field, "Fuzzy")

    results = []
    for rid in result_ids:
        record = dataset.get(rid)
        if record is None:
            continue
        field_types = match.get(rid, {})

        # Reasons ordered strongest-first.
        reasons = sorted(
            ((mtype, _FIELD_LABEL.get(f, f)) for f, mtype in field_types.items()),
            key=lambda tf: -_TYPE_RANK[tf[0]],
        )

        score = sum(
            _FIELD_WEIGHTS.get(f, 0.3) * _TYPE_WEIGHT[mtype]
            for f, mtype in field_types.items()
        )
        relevance = min(100, round(score / max(len(fields), 1) * 100)) if field_types else 0

        results.append(SearchResult(record, reasons, relevance))

    if sort_by_relevance:
        results.sort(
            key=lambda r: (r.relevance, r.record.get("journal_date")),
            reverse=True,
        )

    return results
