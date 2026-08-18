"""
User annotations (v6 Phase 6): Important stars, personal tags, and custom
user categories.

CRITICAL: annotations are stored SEPARATELY from extracted patent data. They
are keyed by the record's stable id and never written into record.raw or the
dataset. Persistence is via store.Store (local JSON).
"""


def _blank():
    return {"important": False, "tags": [], "categories": []}


class Annotations:

    FILENAME = "annotations.json"

    def __init__(self, store):
        self.store = store
        self.data = self.store.load(self.FILENAME, {})
        if not isinstance(self.data, dict):
            self.data = {}

    # -- read -------------------------------------------------------------

    def get(self, record_id):
        """Return a copy of the annotation for a record (defaults if none)."""
        entry = self.data.get(record_id)
        if not entry:
            return _blank()
        return {
            "important": bool(entry.get("important", False)),
            "tags": list(entry.get("tags", [])),
            "categories": list(entry.get("categories", [])),
        }

    def is_important(self, record_id):
        return bool(self.data.get(record_id, {}).get("important", False))

    def tags(self, record_id):
        return list(self.data.get(record_id, {}).get("tags", []))

    def categories(self, record_id):
        return list(self.data.get(record_id, {}).get("categories", []))

    def all_tags(self):
        """Every distinct tag in use, sorted."""
        seen = set()
        for entry in self.data.values():
            seen.update(entry.get("tags", []))
        return sorted(seen)

    # -- write ------------------------------------------------------------

    def _entry(self, record_id):
        return self.data.setdefault(record_id, _blank())

    def set_important(self, record_id, value):
        self._entry(record_id)["important"] = bool(value)
        self._commit(record_id)

    def toggle_important(self, record_id):
        new_value = not self.is_important(record_id)
        self.set_important(record_id, new_value)
        return new_value

    def add_tag(self, record_id, tag):
        tag = (tag or "").strip()
        if not tag:
            return
        tags = self._entry(record_id)["tags"]
        if tag not in tags:
            tags.append(tag)
        self._commit(record_id)

    def remove_tag(self, record_id, tag):
        entry = self.data.get(record_id)
        if entry and tag in entry.get("tags", []):
            entry["tags"].remove(tag)
        self._commit(record_id)

    def add_category(self, record_id, category):
        category = (category or "").strip()
        if not category:
            return
        cats = self._entry(record_id)["categories"]
        if category not in cats:
            cats.append(category)
        self._commit(record_id)

    def remove_category(self, record_id, category):
        entry = self.data.get(record_id)
        if entry and category in entry.get("categories", []):
            entry["categories"].remove(category)
        self._commit(record_id)

    # -- persistence ------------------------------------------------------

    def _commit(self, record_id):
        # Drop entries that carry no information, keeping the file small.
        entry = self.data.get(record_id)
        if entry and not entry.get("important") and not entry.get("tags") \
                and not entry.get("categories"):
            self.data.pop(record_id, None)
        self.store.save(self.FILENAME, self.data)
