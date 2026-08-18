"""
Local JSON persistence for the v6 discovery layer (Phase 6).

Everything is offline and local - no cloud, database, or network. Handles
missing / empty / malformed / first-run files gracefully (returns the caller's
default rather than raising). Writes are atomic (temp file + os.replace).

Contains:
- Store: generic load/save of named JSON documents in a per-user data folder.
- SavedSearches: named, reloadable search-state documents.
- SearchHistory: a bounded list of recent search states (newest first).
"""

import json
import os
import tempfile


def _default_dir():
    """A per-user, writable data directory (works for a packaged exe, unlike
    the install folder which may be read-only)."""
    base = os.environ.get("APPDATA") or os.path.join(
        os.path.expanduser("~"), ".config")
    return os.path.join(base, "IndianPatentJournalExtractor")


class Store:
    """Generic named-JSON store. `directory` is injectable for testing."""

    def __init__(self, directory=None):
        self.directory = directory or _default_dir()

    def _path(self, name):
        return os.path.join(self.directory, name)

    def load(self, name, default):
        """Return the JSON document `name`, or `default` if it is missing,
        empty, malformed, or unreadable (never raises)."""
        try:
            with open(self._path(name), "r", encoding="utf-8") as fh:
                text = fh.read().strip()
            if not text:
                return default
            return json.loads(text)
        except (FileNotFoundError, ValueError, OSError):
            return default

    def save(self, name, data):
        """Atomically write a JSON document. Best-effort: never raises on a
        storage problem (annotations must not break the UI)."""
        try:
            os.makedirs(self.directory, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=self.directory, suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(data, fh, ensure_ascii=False, indent=1)
                os.replace(tmp, self._path(name))
            finally:
                if os.path.exists(tmp):
                    os.remove(tmp)
        except OSError:
            pass


class SavedSearches:
    """Named search-state documents that fully reproduce a search config."""

    FILENAME = "saved_searches.json"

    def __init__(self, store):
        self.store = store
        self.data = self.store.load(self.FILENAME, {})
        if not isinstance(self.data, dict):
            self.data = {}

    def save(self, name, state):
        name = (name or "").strip()
        if not name:
            raise ValueError("A saved search needs a name.")
        self.data[name] = state
        self.store.save(self.FILENAME, self.data)

    def load(self, name):
        return self.data.get(name)

    def delete(self, name):
        self.data.pop(name, None)
        self.store.save(self.FILENAME, self.data)

    def names(self):
        return sorted(self.data.keys())


class SearchHistory:
    """Bounded most-recent-first list of search states (deduplicated)."""

    FILENAME = "search_history.json"

    def __init__(self, store, limit=20):
        self.store = store
        self.limit = limit
        self.data = self.store.load(self.FILENAME, [])
        if not isinstance(self.data, list):
            self.data = []

    def add(self, state):
        # Drop an identical prior entry, push to front, bound the length.
        self.data = [s for s in self.data if s != state]
        self.data.insert(0, state)
        del self.data[self.limit:]
        self.store.save(self.FILENAME, self.data)

    def items(self):
        return list(self.data)

    def clear(self):
        self.data = []
        self.store.save(self.FILENAME, self.data)
