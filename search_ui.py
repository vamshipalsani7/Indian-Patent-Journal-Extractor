"""
v6 Discovery / Search window (UI cleanup + stabilization pass).

A SEPARATE window layered on top of the extraction app. It never touches the
extraction UI or the Excel workflow: gui_v4.py hands it an already-built
Dataset. ALL search / filter / facet / export / annotation / category logic
comes from the frozen Phase 1-6 modules; this file is pure UI wiring.

(Analytics - the former Phase 7 - has been removed from this release.)

Data-shaping logic is factored into pure module-level helpers (testable without
a display); the widget classes only wire those helpers to customtkinter/ttk.
"""

import os
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox, simpledialog

import customtkinter as ctk

from search_index import SearchIndex, tokenize
from advanced_search import search as advanced_search
from query_parser import parse, positive_terms
import thesaurus as thesaurus_mod
import fuzzy as fuzzy_mod
import facets as facets_mod
from filters import Filters
import result_export
from store import Store, SavedSearches, SearchHistory
import annotations as annotations_mod
import categories as categories_mod


# ----- accents (restrained; keep the existing dark CustomTkinter theme) -----
ACCENT_SEARCH = "#2FA572"          # primary Search button
ACCENT_SEARCH_HOVER = "#26895C"
ACCENT_EXPORT = "#3B8ED0"          # Export (prominent but secondary)
PANEL = ("gray92", "gray17")
SECTION_HEADER = ("Arial", 13, "bold")

_ALL_SOURCES = "All sources"

# Searchable canonical fields offered as checkboxes (label, canonical key).
SEARCH_FIELDS = [
    ("Title", "title"),
    ("Abstract", "abstract"),
    ("Claims", "claims"),
    ("Applicant", "applicant"),
    ("Inventor", "inventor"),
    ("IPC", "ipc"),
    ("Application No", "application_number"),
    ("Patent No", "patent_number"),
    ("Priority", "priority"),
]

# Results table columns: (key, heading, width, numeric?). Title gets room.
RESULT_COLUMNS = [
    ("number", "App / Patent No", 140, False),
    ("title", "Title", 380, False),
    ("applicant", "Applicant", 190, False),
    ("ipc", "IPC", 110, False),
    ("type", "Type", 70, False),
    ("journal_date", "Journal Date", 95, False),
    ("relevance", "Rel%", 52, True),
    ("match", "Match", 170, False),
]

# Detail pane field order: (label, canonical key). Long fields last.
DETAIL_FIELDS = [
    ("Application Number", "application_number"),
    ("Patent Number", "patent_number"),
    ("Title", "title"),
    ("Applicant / Patentee", "applicant"),
    ("Inventor", "inventor"),
    ("IPC", "ipc"),
    ("Priority", "priority"),
    ("Filing Date", "filing_date"),
    ("Publication Date", "publication_date"),
    ("Journal Date", "journal_date"),
    ("Appropriate Office", "office"),
    ("Source PDF", "source_pdf"),
    ("Page", "page"),
    ("Abstract", "abstract"),
    ("Claims", "claims"),
]


# ---------------------------------------------------------------- pure helpers

def result_row(result):
    """Column values (dict) for one SearchResult in the results table."""
    rec = result.record
    number = rec.get("application_number") or rec.get("patent_number")
    return {
        "number": number,
        "title": rec.get("title"),
        "applicant": rec.get("applicant"),
        "ipc": rec.get("ipc"),
        "type": rec.type,
        "journal_date": rec.get("journal_date"),
        "relevance": result.relevance,
        "match": result.match_summary,
    }


def detail_pairs(record):
    """Ordered (label, value) pairs for the detail pane. '-' for empties."""
    pairs = [("Type", record.type)]
    for label, key in DETAIL_FIELDS:
        value = record.get(key).strip()
        pairs.append((label, value if value else "-"))
    return pairs


def collect_highlight_terms(query, thesaurus, use_related, use_fuzzy, vocabulary):
    """Surface terms to highlight: the query's positive terms plus, when
    enabled, their thesaurus expansions and fuzzy variants."""
    terms = set()
    positives = positive_terms(parse(query))
    for term in positives:
        t = term.strip()
        if t:
            terms.add(t)
    if use_related and thesaurus is not None:
        for term in positives:
            terms.update(thesaurus.expand(term))
    if use_fuzzy:
        for term in positives:
            for token in tokenize(term):
                if token in vocabulary:
                    continue
                terms.update(fuzzy_mod.candidates(token, vocabulary))
    return {t for t in terms if len(t) >= 2}


def highlight_spans(text, terms):
    """Sorted, merged (start, end) spans of case-insensitive term matches."""
    if not text or not terms:
        return []
    low = text.casefold()
    spans = []
    for term in terms:
        t = term.casefold().strip()
        if len(t) < 2:
            continue
        start = 0
        while True:
            i = low.find(t, start)
            if i < 0:
                break
            spans.append((i, i + len(t)))
            start = i + len(t)
    if not spans:
        return []
    spans.sort()
    merged = [spans[0]]
    for s, e in spans[1:]:
        if s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


# ------------------------------------------------------------------- UI window

class SearchWindow(ctk.CTkToplevel):

    def __init__(self, master, dataset):
        super().__init__(master)

        self.dataset = dataset
        self.index = SearchIndex(dataset)
        self.thesaurus = thesaurus_mod.load()
        self.results = []
        self.row_to_id = {}
        self.highlight_terms = set()
        self.selected_record = None

        # local persistence, annotations, categories
        self.store = Store()
        self.annotations = annotations_mod.Annotations(self.store)
        self.categories = categories_mod.load()
        self.saved = SavedSearches(self.store)
        self.history = SearchHistory(self.store)

        # which canonical fields carry data (drives (n/a) handling)
        self._has = {k: self.index.has_field_data(k) for _, k in SEARCH_FIELDS}
        self._applicant_values = [v for v, _ in facets_mod.applicant_counts(dataset)]
        self._inventor_values = [v for v, _ in facets_mod.inventor_counts(dataset)]
        self._sources = [_ALL_SOURCES] + [s for s, _ in facets_mod.source_counts(dataset)]

        self.title("Patent Discovery & Search")
        try:
            mx, my = master.winfo_rootx(), master.winfo_rooty()
            self.geometry(f"1240x780+{max(mx + 30, 0)}+{max(my + 20, 0)}")
        except Exception:
            self.geometry("1240x780")
        self.minsize(1040, 640)

        self._apply_ttk_dark_style()
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_top()
        self._build_body()
        self._build_status()

        self.run_query()
        self.after(60, self._bring_to_front)

    # -- window foreground ------------------------------------------------

    def _bring_to_front(self):
        try:
            self.deiconify()
            self.lift()
            self.attributes("-topmost", True)
            self.after(250, lambda: self.attributes("-topmost", False))
            self.focus_force()
        except Exception:
            pass

    def _apply_ttk_dark_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("default")
        except tk.TclError:
            pass
        style.configure("Treeview", background="#242424", fieldbackground="#242424",
                        foreground="#e6e6e6", rowheight=25, borderwidth=0)
        style.configure("Treeview.Heading", background="#2b2b2b",
                        foreground="#e6e6e6", relief="flat", font=("Arial", 10, "bold"))
        style.map("Treeview", background=[("selected", "#1f6aa5")])
        style.map("Treeview.Heading", background=[("active", "#3a3a3a")])

    # -- top: search area -------------------------------------------------

    def _build_top(self):
        top = ctk.CTkFrame(self, fg_color=PANEL)
        top.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))
        top.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(top, text="🔍  Search", font=("Arial", 18, "bold")).grid(
            row=0, column=0, sticky="w", padx=14, pady=(10, 2))

        # Search input (prominent) + Search button (accent)
        searchrow = ctk.CTkFrame(top, fg_color="transparent")
        searchrow.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 6))
        searchrow.grid_columnconfigure(0, weight=1)
        self.query_var = tk.StringVar()
        entry = ctk.CTkEntry(
            searchrow, textvariable=self.query_var, height=42,
            font=("Arial", 14),
            placeholder_text="Search patents...   (AND / OR / NOT, \"phrases\", parentheses)")
        entry.grid(row=0, column=0, sticky="ew", padx=(2, 8))
        entry.bind("<Return>", lambda e: self._do_search())
        ctk.CTkButton(searchrow, text="Search", width=130, height=42,
                      font=("Arial", 14, "bold"),
                      fg_color=ACCENT_SEARCH, hover_color=ACCENT_SEARCH_HOVER,
                      command=self._do_search).grid(row=0, column=1)

        # Modes + fields
        modes = ctk.CTkFrame(top, fg_color="transparent")
        modes.grid(row=2, column=0, sticky="w", padx=12, pady=(0, 2))
        ctk.CTkLabel(modes, text="Modes:", text_color="gray70").pack(side="left", padx=(2, 6))
        self.related_var = tk.BooleanVar(value=False)
        self.fuzzy_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(modes, text="Related", variable=self.related_var,
                        command=self.run_query).pack(side="left", padx=6)
        ctk.CTkCheckBox(modes, text="Fuzzy", variable=self.fuzzy_var,
                        command=self.run_query).pack(side="left", padx=6)

        fields = ctk.CTkFrame(top, fg_color="transparent")
        fields.grid(row=3, column=0, sticky="w", padx=12, pady=(0, 2))
        ctk.CTkLabel(fields, text="Search in:", text_color="gray70").pack(side="left", padx=(2, 6))
        self.field_vars = {}
        for label, key in SEARCH_FIELDS:
            has = self._has[key]
            var = tk.BooleanVar(value=has)
            self.field_vars[key] = var
            cb = ctk.CTkCheckBox(fields, text=label if has else f"{label} (n/a)",
                                 variable=var, command=self.run_query)
            if not has:
                var.set(False)
                cb.configure(state="disabled")
            cb.pack(side="left", padx=4)

        # Action row: Save / Saved / Recent / Export / Clear History
        actions = ctk.CTkFrame(top, fg_color="transparent")
        actions.grid(row=4, column=0, sticky="ew", padx=12, pady=(4, 10))
        ctk.CTkButton(actions, text="💾 Save Search", width=120,
                      command=self._save_search).pack(side="left", padx=(2, 6))
        self.saved_var = tk.StringVar(value="Saved searches ▼")
        self.saved_menu = ctk.CTkOptionMenu(actions, variable=self.saved_var, width=190,
                                            values=["Saved searches ▼"], command=self._load_saved)
        self.saved_menu.pack(side="left", padx=4)
        ctk.CTkButton(actions, text="Delete", width=64,
                      command=self._delete_saved).pack(side="left", padx=(0, 10))
        self.recent_var = tk.StringVar(value="Recent searches ▼")
        self.recent_menu = ctk.CTkOptionMenu(actions, variable=self.recent_var, width=210,
                                             values=["Recent searches ▼"], command=self._load_recent)
        self.recent_menu.pack(side="left", padx=4)
        ctk.CTkButton(actions, text="Clear History", width=100,
                      command=self._clear_history).pack(side="left", padx=(0, 10))
        ctk.CTkButton(actions, text="⬇ Export Results", width=150,
                      fg_color=ACCENT_EXPORT,
                      command=self._export_results).pack(side="left", padx=4)
        ctk.CTkLabel(actions, text="(saved & recent are stored locally on this PC)",
                     text_color="gray55", font=("Arial", 10)).pack(side="left", padx=10)
        self._refresh_search_menus()

    # -- body: left / center / right --------------------------------------

    def _build_body(self):
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=10, pady=4)
        body.grid_columnconfigure(0, minsize=300)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(2, minsize=380)
        body.grid_rowconfigure(0, weight=1)

        self._build_left(body)
        self._build_results(body)
        self._build_detail(body)

    def _build_left(self, parent):
        left = ctk.CTkFrame(parent, width=300)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.grid_propagate(False)
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)
        self._build_filters(left)
        self._build_explore(left)

    def _build_filters(self, parent):
        box = ctk.CTkScrollableFrame(parent, label_text="FILTERS", height=250)
        box.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 4))

        self.f_type = tk.StringVar(value="All")
        self._labeled(box, "Patent Type")
        ctk.CTkOptionMenu(box, values=["All", "Published", "Granted"],
                          variable=self.f_type).pack(fill="x", padx=8, pady=(0, 6))

        self._labeled(box, "Journal Date (dd/mm/yyyy)")
        drow = ctk.CTkFrame(box, fg_color="transparent")
        drow.pack(fill="x", padx=8, pady=(0, 6))
        self.f_jfrom = tk.StringVar()
        self.f_jto = tk.StringVar()
        ctk.CTkEntry(drow, textvariable=self.f_jfrom, placeholder_text="From",
                     width=110).pack(side="left", expand=True, fill="x", padx=(0, 4))
        ctk.CTkEntry(drow, textvariable=self.f_jto, placeholder_text="To",
                     width=110).pack(side="left", expand=True, fill="x", padx=(4, 0))

        self.f_applicant = tk.StringVar()
        self._labeled(box, "Applicant")
        ctk.CTkEntry(box, textvariable=self.f_applicant,
                     placeholder_text="Search applicant...").pack(fill="x", padx=8, pady=(0, 6))

        self.f_inventor = tk.StringVar()
        self._labeled(box, "Inventor" + ("" if self._has["inventor"] else "  (n/a)"))
        inv = ctk.CTkEntry(box, textvariable=self.f_inventor,
                           placeholder_text="Search inventor...")
        inv.pack(fill="x", padx=8, pady=(0, 6))
        if not self._has["inventor"]:
            inv.configure(state="disabled")

        self.f_ipc = tk.StringVar()
        self._labeled(box, "IPC" + ("" if self._has["ipc"] else "  (n/a)"))
        ipc = ctk.CTkEntry(box, textvariable=self.f_ipc,
                           placeholder_text="Search IPC (e.g. H01M)...")
        ipc.pack(fill="x", padx=8, pady=(0, 6))
        if not self._has["ipc"]:
            ipc.configure(state="disabled")

        self.f_number = tk.StringVar()
        self._labeled(box, "Application / Patent Number")
        ctk.CTkEntry(box, textvariable=self.f_number,
                     placeholder_text="Enter number...").pack(fill="x", padx=8, pady=(0, 6))

        self.f_source = tk.StringVar(value=_ALL_SOURCES)
        self._labeled(box, "Source PDF")
        ctk.CTkOptionMenu(box, values=self._sources, variable=self.f_source,
                          width=260).pack(fill="x", padx=8, pady=(0, 6))

        brow = ctk.CTkFrame(box, fg_color="transparent")
        brow.pack(fill="x", padx=8, pady=(4, 8))
        ctk.CTkButton(brow, text="Apply Filters", command=self.run_query).pack(
            side="left", expand=True, fill="x", padx=(0, 4))
        ctk.CTkButton(brow, text="Clear", width=70, fg_color="gray40",
                      command=self._clear_filters).pack(side="left", padx=(4, 0))

    @staticmethod
    def _labeled(parent, text):
        ctk.CTkLabel(parent, text=text, anchor="w", font=("Arial", 11, "bold"),
                     text_color="gray75").pack(fill="x", padx=8, pady=(4, 0))

    def _build_explore(self, parent):
        wrap = ctk.CTkFrame(parent)
        wrap.grid(row=1, column=0, sticky="nsew", padx=6, pady=(4, 6))
        wrap.grid_rowconfigure(1, weight=1)
        wrap.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(wrap, text="EXPLORE DATA", font=SECTION_HEADER).grid(
            row=0, column=0, sticky="w", padx=10, pady=(8, 2))
        tabs = ctk.CTkTabview(wrap)
        tabs.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 8))
        tabs.add("Applicant")
        tabs.add("Inventor")
        tabs.add("IPC")
        self._build_facet_tab(tabs.tab("Applicant"), "applicant",
                              facets_mod.applicant_counts(self.dataset), self.f_applicant)
        self._build_facet_tab(tabs.tab("Inventor"), "inventor",
                              facets_mod.inventor_counts(self.dataset), self.f_inventor)
        self._build_ipc_tab(tabs.tab("IPC"))

    def _build_facet_tab(self, parent, field, pairs, target_var):
        search_var = tk.StringVar()
        ctk.CTkEntry(parent, textvariable=search_var,
                     placeholder_text=f"Find {field}...").pack(fill="x", padx=4, pady=4)
        scroll = ctk.CTkScrollableFrame(parent)
        scroll.pack(fill="both", expand=True, padx=2, pady=2)

        def refresh(*_):
            for w in scroll.winfo_children():
                w.destroy()
            shown = facets_mod.filter_facet(pairs, search_var.get())[:300]
            if not shown:
                ctk.CTkLabel(scroll, text="(no data)", text_color="gray55").pack(padx=6, pady=6)
                return
            for value, count in shown:
                ctk.CTkButton(
                    scroll, text=f"{value[:38]}  ({count})", anchor="w", height=24,
                    fg_color="transparent", hover=True,
                    command=lambda v=value: self._apply_facet(target_var, v)
                ).pack(fill="x", padx=2, pady=1)

        search_var.trace_add("write", refresh)
        refresh()

    def _build_ipc_tab(self, parent):
        if not self._has["ipc"]:
            ctk.CTkLabel(parent, text="No IPC data in this dataset.",
                         text_color="gray55").pack(padx=10, pady=10)
            return
        tree = ttk.Treeview(parent, show="tree", height=16)
        tree.pack(fill="both", expand=True, padx=2, pady=2)
        hierarchy = facets_mod.ipc_hierarchy(self.dataset)

        def add_nodes(parent_iid, node_dict):
            for code, node in sorted(node_dict.items(), key=lambda kv: -kv[1]["count"]):
                iid = tree.insert(parent_iid, "end",
                                  text=f"{code}  ({node['count']})", values=(code,))
                add_nodes(iid, node["children"])

        add_nodes("", hierarchy)

        def on_select(_):
            sel = tree.selection()
            if sel:
                self._apply_facet(self.f_ipc, tree.item(sel[0], "values")[0])

        tree.bind("<<TreeviewSelect>>", on_select)

    # -- center: results --------------------------------------------------

    def _build_results(self, parent):
        frame = ctk.CTkFrame(parent)
        frame.grid(row=0, column=1, sticky="nsew", padx=4)
        frame.grid_rowconfigure(1, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(frame, text="RESULTS", font=SECTION_HEADER).grid(
            row=0, column=0, sticky="w", padx=10, pady=(8, 2))

        cols = [c[0] for c in RESULT_COLUMNS]
        self.tree = ttk.Treeview(frame, columns=cols, show="headings")
        for key, heading, width, numeric in RESULT_COLUMNS:
            self.tree.heading(key, text=heading,
                              command=lambda k=key, n=numeric: self._sort_by(k, n))
            self.tree.column(key, width=width, minwidth=40, anchor="w",
                             stretch=(key == "title"))
        self.tree.grid(row=1, column=0, sticky="nsew")

        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        vsb.grid(row=1, column=1, sticky="ns")
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        hsb.grid(row=2, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.bind("<<TreeviewSelect>>", self._on_select_result)
        self._sort_state = {}

    # -- right: patent details + notes ------------------------------------

    def _build_detail(self, parent):
        frame = ctk.CTkFrame(parent, width=380)
        frame.grid(row=0, column=2, sticky="nsew", padx=(8, 0))
        frame.grid_propagate(False)
        frame.grid_rowconfigure(1, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=(8, 2))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="PATENT DETAILS", font=SECTION_HEADER).grid(
            row=0, column=0, sticky="w")
        ctk.CTkButton(header, text="📄 Open Source PDF", width=150,
                      command=self._open_selected_pdf).grid(row=0, column=1, sticky="e")

        self.detail = tk.Text(frame, wrap="word", font=("Consolas", 10),
                              background="#1a1a1a", foreground="#e6e6e6",
                              insertbackground="#e6e6e6", relief="flat", padx=8, pady=8)
        self.detail.grid(row=1, column=0, sticky="nsew", padx=(8, 0), pady=(0, 6))
        dsb = ttk.Scrollbar(frame, orient="vertical", command=self.detail.yview)
        dsb.grid(row=1, column=1, sticky="ns", pady=(0, 6))
        self.detail.configure(yscrollcommand=dsb.set, state="disabled")
        self.detail.tag_configure("label", foreground="#7fb3ff")
        self.detail.tag_configure("hl", background="#c8a200", foreground="#000000")

        self._build_notes(frame)

    def _build_notes(self, parent):
        notes = ctk.CTkFrame(parent)
        notes.grid(row=2, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 8))
        ctk.CTkLabel(notes, text="MY NOTES & CLASSIFICATION",
                     font=("Arial", 12, "bold"), text_color="#7fb3ff").pack(
            anchor="w", padx=8, pady=(6, 2))

        row1 = ctk.CTkFrame(notes, fg_color="transparent")
        row1.pack(fill="x", padx=8, pady=2)
        self.star_btn = ctk.CTkButton(row1, text="☆ Mark Important", width=150,
                                      command=self._toggle_important)
        self.star_btn.pack(side="left", padx=2)
        self.auto_cat_label = ctk.CTkLabel(row1, text="Categories (auto): —",
                                           anchor="w", wraplength=200, font=("Arial", 10))
        self.auto_cat_label.pack(side="left", padx=8)

        addrow = ctk.CTkFrame(notes, fg_color="transparent")
        addrow.pack(fill="x", padx=8, pady=2)
        self.tag_var = tk.StringVar()
        ctk.CTkEntry(addrow, textvariable=self.tag_var, width=150,
                     placeholder_text="personal tag / category").pack(side="left", padx=2)
        ctk.CTkButton(addrow, text="+ Tag", width=64,
                      command=self._add_tag).pack(side="left", padx=2)
        ctk.CTkButton(addrow, text="+ Category", width=88,
                      command=self._add_user_category).pack(side="left", padx=2)

        self.chips_frame = ctk.CTkFrame(notes, fg_color="transparent")
        self.chips_frame.pack(fill="x", padx=8, pady=(2, 8))

    def _build_status(self):
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 8))
        self.status_var = tk.StringVar(value="Ready.")
        ctk.CTkLabel(bar, textvariable=self.status_var, anchor="w").pack(side="left")

    # -- query / filters --------------------------------------------------

    def _selected_fields(self):
        return [k for k, v in self.field_vars.items() if v.get()]

    def _resolve_facet(self, values, text):
        """Substring text -> the set of matching exact facet values (reuses the
        Phase 2 Filters exact-set API). Returns a never-empty set when text is
        given (a sentinel yields 'no results' rather than 'ignore filter')."""
        text = (text or "").strip()
        if not text:
            return None
        low = text.casefold()
        matched = {v for v in values if low in v.casefold()}
        return matched or {"\x00__no_match__"}

    def _active_filters(self):
        applicants = self._resolve_facet(self._applicant_values, self.f_applicant.get())
        inventors = (self._resolve_facet(self._inventor_values, self.f_inventor.get())
                     if self._has["inventor"] else None)
        ipc_text = self.f_ipc.get().strip()
        ipc = ([c.upper() for c in ipc_text.replace(",", " ").split()]
               if ipc_text and self._has["ipc"] else None)
        src = self.f_source.get()
        sources = [src] if src and src != _ALL_SOURCES else None
        filters = Filters(
            patent_type=self.f_type.get(),
            journal_from=self.f_jfrom.get(), journal_to=self.f_jto.get(),
            applicants=applicants, inventors=inventors, ipc=ipc, sources=sources,
        )
        return filters, self.f_number.get().strip()

    def run_query(self, *_):
        query = self.query_var.get().strip()
        fields = self._selected_fields() or [k for _, k in SEARCH_FIELDS if self._has[k]]
        use_related = self.related_var.get()
        use_fuzzy = self.fuzzy_var.get()

        results = advanced_search(self.dataset, self.index, query, fields,
                                  use_related=use_related, use_fuzzy=use_fuzzy,
                                  thesaurus=self.thesaurus)

        filters, number = self._active_filters()
        if filters.is_active():
            kept = {r.id for r in filters.apply([r.record for r in results])}
            results = [r for r in results if r.record.id in kept]
        if number:
            n = number.casefold()
            results = [r for r in results
                       if n in r.record.get("application_number").casefold()
                       or n in r.record.get("patent_number").casefold()]

        self.results = results
        self.highlight_terms = collect_highlight_terms(
            query, self.thesaurus, use_related, use_fuzzy, self.index.vocabulary)
        self._populate_results()

    def _populate_results(self):
        self.tree.delete(*self.tree.get_children())
        self.row_to_id.clear()
        for result in self.results:
            row = result_row(result)
            iid = self.tree.insert("", "end",
                                   values=tuple(str(row[c[0]]) for c in RESULT_COLUMNS))
            self.row_to_id[iid] = result.record.id
        self.status_var.set(f"Results: {len(self.results):,} patents")

    def _sort_by(self, key, numeric):
        reverse = self._sort_state.get(key, False)

        def sort_key(result):
            value = result_row(result)[key]
            if numeric:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return 0.0
            return str(value).casefold()

        self.results.sort(key=sort_key, reverse=reverse)
        self._sort_state[key] = not reverse
        self._populate_results()

    def _apply_facet(self, target_var, value):
        target_var.set(value)
        self.run_query()

    def _clear_filters(self):
        self.f_type.set("All")
        for var in (self.f_jfrom, self.f_jto, self.f_applicant, self.f_inventor,
                    self.f_ipc, self.f_number):
            var.set("")
        self.f_source.set(_ALL_SOURCES)
        self.run_query()

    # -- detail + selection ----------------------------------------------

    def _on_select_result(self, _):
        sel = self.tree.selection()
        if not sel:
            return
        record = self.dataset.get(self.row_to_id.get(sel[0]))
        if record is not None:
            self._show_detail(record)

    def _show_detail(self, record):
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        for label, value in detail_pairs(record):
            self.detail.insert("end", f"{label}\n", ("label",))
            start = self.detail.index("end-1c")
            self.detail.insert("end", f"{value}\n\n")
            for s, e in highlight_spans(value, self.highlight_terms):
                self.detail.tag_add("hl", f"{start}+{s}c", f"{start}+{e}c")
        self.detail.configure(state="disabled")
        self.selected_record = record
        self._refresh_annotations(record)

    # -- export / open pdf ------------------------------------------------

    def _export_results(self):
        if not self.results:
            messagebox.showwarning("Export Results", "There are no results to export.")
            return
        selection = self.tree.selection()
        if selection:
            ids = {self.row_to_id[i] for i in selection if i in self.row_to_id}
            to_export = [r for r in self.results if r.record.id in ids]
        else:
            to_export = list(self.results)
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", filetypes=[("Excel Workbook", "*.xlsx")],
            initialfile="Patent_Search_Results.xlsx", title="Export Results to Excel")
        if not path:
            return
        try:
            count = result_export.export_results(to_export, path)
            messagebox.showinfo("Export complete", f"{count} record(s) exported to\n\n{path}")
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))

    def _open_selected_pdf(self):
        if self.selected_record is None:
            messagebox.showinfo("Open Source PDF", "Select a result first.")
            return
        record = self.selected_record
        try:
            page = result_export.open_source_pdf(record.source_path, record.get("page"))
            self.status_var.set(f"Opened {os.path.basename(record.source_path)} — see page {page}.")
        except Exception as exc:
            messagebox.showwarning("Cannot open PDF", str(exc))

    # -- saved searches / history ----------------------------------------

    def _current_state(self):
        return {
            "query": self.query_var.get(), "related": self.related_var.get(),
            "fuzzy": self.fuzzy_var.get(), "fields": self._selected_fields(),
            "type": self.f_type.get(), "journal_from": self.f_jfrom.get(),
            "journal_to": self.f_jto.get(), "applicant": self.f_applicant.get(),
            "inventor": self.f_inventor.get(), "ipc": self.f_ipc.get(),
            "number": self.f_number.get(), "source": self.f_source.get(),
        }

    def _apply_state(self, state):
        if not state:
            return
        self.query_var.set(state.get("query", ""))
        self.related_var.set(bool(state.get("related", False)))
        self.fuzzy_var.set(bool(state.get("fuzzy", False)))
        wanted = set(state.get("fields", []))
        for key, var in self.field_vars.items():
            if self._has[key]:
                var.set(key in wanted)
        self.f_type.set(state.get("type", "All"))
        self.f_jfrom.set(state.get("journal_from", ""))
        self.f_jto.set(state.get("journal_to", ""))
        self.f_applicant.set(state.get("applicant", ""))
        self.f_inventor.set(state.get("inventor", ""))
        self.f_ipc.set(state.get("ipc", ""))
        self.f_number.set(state.get("number", ""))
        self.f_source.set(state.get("source", _ALL_SOURCES))
        self.run_query()

    def _do_search(self):
        self.run_query()
        state = self._current_state()
        filters, number = self._active_filters()
        if state.get("query") or number or filters.is_active():
            self.history.add(state)
            self._refresh_search_menus()

    def _refresh_search_menus(self):
        self.saved_menu.configure(values=["Saved searches ▼"] + self.saved.names())
        recent = ["Recent searches ▼"] + [
            (s.get("query") or "(filters only)") for s in self.history.items()]
        self.recent_menu.configure(values=recent)

    def _save_search(self):
        name = simpledialog.askstring("Save Search", "Name this search:", parent=self)
        if not name:
            return
        try:
            self.saved.save(name, self._current_state())
            self._refresh_search_menus()
            self.status_var.set(f"Saved search '{name}'.")
        except ValueError as exc:
            messagebox.showwarning("Save Search", str(exc))

    def _load_saved(self, name):
        if name and name != "Saved searches ▼":
            self._apply_state(self.saved.load(name))

    def _delete_saved(self):
        name = self.saved_var.get()
        if name and name != "Saved searches ▼":
            self.saved.delete(name)
            self.saved_var.set("Saved searches ▼")
            self._refresh_search_menus()

    def _load_recent(self, label):
        for state in self.history.items():
            if (state.get("query") or "(filters only)") == label:
                self._apply_state(state)
                return

    def _clear_history(self):
        self.history.clear()
        self._refresh_search_menus()
        self.recent_var.set("Recent searches ▼")

    # -- annotations ------------------------------------------------------

    def _refresh_annotations(self, record):
        important = self.annotations.is_important(record.id)
        self.star_btn.configure(text="⭐ Important" if important else "☆ Mark Important")
        auto = self.categories.classify(record)
        self.auto_cat_label.configure(
            text="Categories (auto): " + (", ".join(auto) if auto else "—"))
        for widget in self.chips_frame.winfo_children():
            widget.destroy()
        for tag in self.annotations.tags(record.id):
            ctk.CTkButton(self.chips_frame, text=f"🏷 {tag}  ✕", height=22,
                          fg_color="#334a66",
                          command=lambda t=tag: self._remove_tag(t)).pack(
                side="left", padx=2, pady=2)
        for cat in self.annotations.categories(record.id):
            ctk.CTkButton(self.chips_frame, text=f"📁 {cat}  ✕", height=22,
                          fg_color="#2b4a2b",
                          command=lambda c=cat: self._remove_user_category(c)).pack(
                side="left", padx=2, pady=2)

    def _toggle_important(self):
        if self.selected_record is None:
            return
        self.annotations.toggle_important(self.selected_record.id)
        self._refresh_annotations(self.selected_record)

    def _add_tag(self):
        if self.selected_record is None:
            return
        self.annotations.add_tag(self.selected_record.id, self.tag_var.get())
        self.tag_var.set("")
        self._refresh_annotations(self.selected_record)

    def _add_user_category(self):
        if self.selected_record is None:
            return
        self.annotations.add_category(self.selected_record.id, self.tag_var.get())
        self.tag_var.set("")
        self._refresh_annotations(self.selected_record)

    def _remove_tag(self, tag):
        if self.selected_record is not None:
            self.annotations.remove_tag(self.selected_record.id, tag)
            self._refresh_annotations(self.selected_record)

    def _remove_user_category(self, category):
        if self.selected_record is not None:
            self.annotations.remove_category(self.selected_record.id, category)
            self._refresh_annotations(self.selected_record)


def open_search_window(master, dataset):
    """Launcher entry point used by the additive hook in gui_v4.py."""
    window = SearchWindow(master, dataset)
    window.after(80, window._bring_to_front)
    return window
