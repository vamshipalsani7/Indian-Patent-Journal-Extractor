"""
Duplicate detection for the v6 discovery layer.

Multi-file workflows can accidentally load the same journal twice. This module
FLAGS likely duplicates for the user to review - it never deletes anything.

Duplicates are keyed within the same patent type (a published application and a
later granted patent can share an application number - that is the patent
lifecycle, not a duplicate, so cross-type matches are NOT flagged). Keys tried,
in order of confidence:
  1. (type, application_number)
  2. (type, patent_number)
  3. (type, title + journal_date)   - fallback when no number is present
"""

from collections import defaultdict


def _key(record):
    app = record.get("application_number").strip()
    if app:
        return (record.type, "app", app)

    pat = record.get("patent_number").strip()
    if pat:
        return (record.type, "pat", pat)

    title = record.get("title").strip().casefold()
    if title:
        return (record.type, "title", title, record.get("journal_date"))

    return None


def find_duplicates(dataset):
    """Return a list of duplicate groups; each group is a list of record ids
    sharing an identity key. Only groups with 2+ records are returned."""

    groups = defaultdict(list)
    for record in dataset.records:
        key = _key(record)
        if key is None:
            continue
        groups[key].append(record.id)

    return [ids for ids in groups.values() if len(ids) > 1]


def duplicate_count(groups):
    """Number of records that are redundant copies (total in dup groups minus
    one kept per group)."""
    return sum(len(ids) - 1 for ids in groups)


def remove_duplicates(records, remove_ids):
    """Return a NEW list with the given record ids removed. The caller decides
    what to remove; nothing is deleted automatically."""
    remove = set(remove_ids)
    return [r for r in records if r.id not in remove]
