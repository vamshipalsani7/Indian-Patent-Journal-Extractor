"""
Data-quality report for the v6 discovery layer.

Computes summary statistics over a loaded Dataset for an (expandable) details
panel. Kept intentionally simple. Some figures - PDFs processed vs unreadable -
originate in the extraction/GUI step, not the dataset, so they are accepted as
optional inputs and reported when available rather than invented here.
"""

from duplicates import find_duplicates, duplicate_count

# Canonical fields considered "key" per patent type (empty = missing).
_KEY_FIELDS = {
    "Published": ["title", "applicant", "application_number"],
    "Granted": ["title", "applicant", "application_number", "patent_number"],
}


def report(dataset, pdfs_processed=None, unreadable_pdfs=None):
    """Return a data-quality summary dict.

    `pdfs_processed` (int) and `unreadable_pdfs` (list) are optional and come
    from the extraction run; when None they are reported as 'n/a'.
    """

    total = len(dataset)
    by_type = {"Published": 0, "Granted": 0}
    missing_records = 0
    missing_by_field = {}

    for record in dataset.records:
        by_type[record.type] = by_type.get(record.type, 0) + 1

        key_fields = _KEY_FIELDS.get(record.type, ["title", "application_number"])
        record_has_missing = False
        for field in key_fields:
            if not record.get(field).strip():
                missing_by_field[field] = missing_by_field.get(field, 0) + 1
                record_has_missing = True
        if record_has_missing:
            missing_records += 1

    dup_groups = find_duplicates(dataset)

    distinct_sources = {
        r.get("source_pdf") for r in dataset.records if r.get("source_pdf").strip()
    }

    return {
        "records_extracted": total,
        "published": by_type.get("Published", 0),
        "granted": by_type.get("Granted", 0),
        "records_with_missing_fields": missing_records,
        "missing_by_field": dict(
            sorted(missing_by_field.items(), key=lambda kv: -kv[1])
        ),
        "potential_duplicates": duplicate_count(dup_groups),
        "duplicate_groups": len(dup_groups),
        "distinct_source_pdfs": len(distinct_sources),
        "pdfs_processed": "n/a" if pdfs_processed is None else pdfs_processed,
        "unreadable_pdfs": [] if unreadable_pdfs is None else list(unreadable_pdfs),
    }
