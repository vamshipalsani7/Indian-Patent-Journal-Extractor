"""
Facet counts and IPC hierarchy for the v6 discovery layer.

All facets are DERIVED FROM THE LOADED DATA - nothing is hard-coded. Used by
the Applicant / Inventor / Source explorers and the IPC tree. Reads only the
canonical fields of a Dataset; never modifies records.

Note (from the schema audit): only Published records carry IPC and Inventor
data, so those facets reflect Published records only. Applicant/Source cover
both types.
"""

import re
from collections import Counter, defaultdict


# IPC symbol: Section (A-H) + class (2 digits) + subclass (letter) + optional
# main-group number, e.g. "A61K 31/00", "H01M10/48".
_IPC_RE = re.compile(r"([A-HYa-hy])\s*(\d{2})\s*([A-Za-z])\s*(\d+)?")


def ipc_levels(text):
    """Return the set of hierarchical IPC level strings present in `text`.

    For "A61K 31/00" -> {"A", "A61", "A61K", "A61K31"}. Empty for no codes.
    The full set lets a selection at ANY level match a record.
    """
    levels = set()
    if not text:
        return levels

    for section, klass, subclass, group in _IPC_RE.findall(text):
        section = section.upper()
        subclass = subclass.upper()
        sec = section
        cls = f"{section}{klass}"
        sub = f"{cls}{subclass}"
        levels.add(sec)
        levels.add(cls)
        levels.add(sub)
        if group:
            levels.add(f"{sub}{group}")

    return levels


def _counter_to_sorted(counter):
    """(value, count) pairs sorted by count desc, then value asc."""
    return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))


def value_counts(dataset, field):
    """Distinct non-empty values of a canonical field with record counts."""
    counter = Counter()
    for record in dataset.records:
        value = record.get(field).strip()
        if value:
            counter[value] += 1
    return _counter_to_sorted(counter)


def applicant_counts(dataset):
    return value_counts(dataset, "applicant")


def inventor_counts(dataset):
    return value_counts(dataset, "inventor")


def source_counts(dataset):
    return value_counts(dataset, "source_pdf")


def ipc_counts(dataset):
    """Record count per IPC level string (every level, all depths)."""
    counter = Counter()
    for record in dataset.records:
        for level in ipc_levels(record.get("ipc")):
            counter[level] += 1
    return _counter_to_sorted(counter)


def ipc_hierarchy(dataset):
    """Nested IPC tree with per-node record counts.

    Shape: { "A": {"count": N, "children": { "A61": {...} } } }.
    A record contributes to a node if it has any code under that node.
    """
    # Per record, the distinct levels it belongs to (dedup so a record with
    # two A61K codes counts once for A61K).
    section = defaultdict(lambda: {"count": 0, "children": {}})

    for record in dataset.records:
        levels = ipc_levels(record.get("ipc"))
        if not levels:
            continue

        # Group this record's levels by depth via string length grouping.
        secs = {l for l in levels if len(l) == 1}
        clss = {l for l in levels if len(l) == 3}
        subs = {l for l in levels if len(l) == 4}
        grps = {l for l in levels if len(l) > 4}

        for s in secs:
            node = section[s]
            node["count"] += 1
            for c in (c for c in clss if c.startswith(s)):
                cnode = node["children"].setdefault(
                    c, {"count": 0, "children": {}})
                cnode["count"] += 1
                for sub in (x for x in subs if x.startswith(c)):
                    snode = cnode["children"].setdefault(
                        sub, {"count": 0, "children": {}})
                    snode["count"] += 1
                    for g in (x for x in grps if x.startswith(sub)):
                        gnode = snode["children"].setdefault(
                            g, {"count": 0, "children": {}})
                        gnode["count"] += 1

    return dict(section)


def filter_facet(pairs, query):
    """Substring-filter a facet (value,count) list for search/autocomplete."""
    if not query:
        return pairs
    q = query.casefold()
    return [(v, c) for v, c in pairs if q in v.casefold()]
