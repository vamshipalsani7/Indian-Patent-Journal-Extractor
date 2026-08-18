"""
Read-only analytics for the v6 discovery layer (Phase 7).

Pure, headless-testable functions that DERIVE everything from a list of
PatentRecords (dataset.records, or a filtered subset). Nothing here mutates the
dataset, a record, record.raw, annotations, or extraction/export output.

Reuses the existing parsers rather than inventing new ones:
- IPC parsing via facets.ipc_levels (Phase 2).
- Technology categories via a Phase 6 Categories instance (passed in).

Grant records legitimately lack IPC / Inventor / Abstract; those simply
contribute nothing to the relevant analytic (never an error).
"""

from collections import Counter, defaultdict
from datetime import datetime

from facets import ipc_levels


# --------------------------------------------------------------- date helpers

def _date_key(value):
    """Sortable key for a 'dd/mm/yyyy' journal date; unknowns sort last."""
    try:
        return (0, datetime.strptime(value.strip(), "%d/%m/%Y").date())
    except (ValueError, AttributeError):
        return (1, datetime.max)


def journal_dates(records):
    """Distinct journal dates present, in chronological order."""
    dates = {r.get("journal_date").strip() for r in records if r.get("journal_date").strip()}
    return sorted(dates, key=_date_key)


def group_by_date(records):
    """Ordered {journal_date: [records]} chronologically."""
    groups = defaultdict(list)
    for r in records:
        groups[r.get("journal_date").strip()].append(r)
    return {d: groups[d] for d in sorted(groups, key=_date_key)}


# ------------------------------------------------------------------- counting

def _distinct(records, field):
    return {r.get(field).strip() for r in records if r.get(field).strip()}


def distinct_applicants(records):
    return _distinct(records, "applicant")


def counts_by_journal_date(records):
    """[(date, count)] chronologically."""
    counter = Counter(r.get("journal_date").strip() for r in records
                      if r.get("journal_date").strip())
    return [(d, counter[d]) for d in sorted(counter, key=_date_key)]


def published_granted_by_date(records):
    """[(date, published, granted)] chronologically."""
    pub = Counter()
    gr = Counter()
    for r in records:
        d = r.get("journal_date").strip()
        if not d:
            continue
        if r.type == "Published":
            pub[d] += 1
        else:
            gr[d] += 1
    dates = sorted(set(pub) | set(gr), key=_date_key)
    return [(d, pub.get(d, 0), gr.get(d, 0)) for d in dates]


def source_activity(records):
    """[(source_pdf, count)] descending."""
    counter = Counter(r.get("source_pdf").strip() for r in records
                      if r.get("source_pdf").strip())
    return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))


def published_vs_granted(records):
    total = len(records)
    pub = sum(1 for r in records if r.type == "Published")
    gr = total - pub
    return {
        "total": total,
        "published": pub,
        "granted": gr,
        "published_pct": round(100 * pub / total) if total else 0,
        "granted_pct": round(100 * gr / total) if total else 0,
    }


# ----------------------------------------------------------------- applicants

def top_applicants(records, n=20):
    counter = Counter(r.get("applicant").strip() for r in records
                      if r.get("applicant").strip())
    return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[:n]


def applicant_trend(records, applicant):
    """[(date, count)] for one applicant, chronologically."""
    counter = Counter()
    for r in records:
        if r.get("applicant").strip() == applicant:
            d = r.get("journal_date").strip()
            if d:
                counter[d] += 1
    return [(d, counter[d]) for d in sorted(counter, key=_date_key)]


# ----------------------------------------------------------------------- IPC

_IPC_LEVEL_LEN = {"section": 1, "class": 3, "subclass": 4}


def top_ipc(records, level="section", n=15):
    """Top IPC codes at a level. A record counts once per distinct code it has
    at that level (multi-code records are handled correctly)."""
    length = _IPC_LEVEL_LEN.get(level)
    counter = Counter()
    for r in records:
        codes = ipc_levels(r.get("ipc"))
        if length is None:            # "group" = deepest
            codes = {c for c in codes if len(c) > 4}
        else:
            codes = {c for c in codes if len(c) == length}
        for c in codes:
            counter[c] += 1
    return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[:n]


# ------------------------------------------------------------------ categories

def category_counts(records, categories):
    """[(category, count)] descending, MULTI-LABEL: a record adds 1 to each of
    its categories, so the sum may exceed len(records) (that is correct and
    does not corrupt the record total, which is reported separately)."""
    counter = Counter()
    with_any = 0
    for r in records:
        cats = categories.classify(r)
        if cats:
            with_any += 1
        for c in cats:
            counter[c] += 1
    ordered = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    return ordered, with_any


def category_trend(records, categories):
    """[(date, {category: count})] chronologically (multi-label per record)."""
    per_date = defaultdict(Counter)
    for r in records:
        d = r.get("journal_date").strip()
        if not d:
            continue
        for c in categories.classify(r):
            per_date[d][c] += 1
    return [(d, dict(per_date[d])) for d in sorted(per_date, key=_date_key)]


# -------------------------------------------------------------------- overview

def overview(records, categories=None, top_n=5):
    ov = {
        "total": len(records),
        "published": sum(1 for r in records if r.type == "Published"),
        "granted": sum(1 for r in records if r.type == "Granted"),
        "applicants": len(distinct_applicants(records)),
        "sources": len(_distinct(records, "source_pdf")),
        "journal_dates": len(journal_dates(records)),
        "top_categories": [],
    }
    if categories is not None:
        ordered, _ = category_counts(records, categories)
        ov["top_categories"] = ordered[:top_n]
    return ov


# ----------------------------------------------------------------- comparison

def _delta_table(counter_a, counter_b, top=10):
    """[(key, count_a, count_b, delta)] over the union of the two counters,
    sorted by absolute change descending."""
    keys = set(counter_a) | set(counter_b)
    rows = [(k, counter_a.get(k, 0), counter_b.get(k, 0),
             counter_b.get(k, 0) - counter_a.get(k, 0)) for k in keys]
    rows.sort(key=lambda r: (-abs(r[3]), -max(r[1], r[2]), r[0]))
    return rows[:top]


def compare_groups(records_a, records_b, categories=None, top=10):
    """Compare two journal/date groups. Read-only; derives everything from the
    two record lists. `new` applicants are in B but not A; `recurring` are in
    both; `dropped` are in A but not B."""
    apps_a = distinct_applicants(records_a)
    apps_b = distinct_applicants(records_b)

    app_counter_a = Counter(r.get("applicant").strip() for r in records_a
                            if r.get("applicant").strip())
    app_counter_b = Counter(r.get("applicant").strip() for r in records_b
                            if r.get("applicant").strip())

    ipc_a = Counter()
    ipc_b = Counter()
    for r in records_a:
        for c in {c for c in ipc_levels(r.get("ipc")) if len(c) == 3}:
            ipc_a[c] += 1
    for r in records_b:
        for c in {c for c in ipc_levels(r.get("ipc")) if len(c) == 3}:
            ipc_b[c] += 1

    result = {
        "total_a": len(records_a),
        "total_b": len(records_b),
        "applicants_a": len(apps_a),
        "applicants_b": len(apps_b),
        "new_applicants": sorted(apps_b - apps_a),
        "recurring_applicants": sorted(apps_a & apps_b),
        "dropped_applicants": sorted(apps_a - apps_b),
        "applicant_changes": _delta_table(app_counter_a, app_counter_b, top),
        "ipc_changes": _delta_table(ipc_a, ipc_b, top),
        "published_granted_a": published_vs_granted(records_a),
        "published_granted_b": published_vs_granted(records_b),
    }

    if categories is not None:
        cat_a = Counter()
        cat_b = Counter()
        for r in records_a:
            for c in categories.classify(r):
                cat_a[c] += 1
        for r in records_b:
            for c in categories.classify(r):
                cat_b[c] += 1
        result["category_changes"] = _delta_table(cat_a, cat_b, top)

    return result
