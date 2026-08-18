"""
Indian Patent Journal Extractor
Version 6.0

GUI

Author:
Praveen Reddy Thumukuntla
"""

import customtkinter as ctk
from tkinter import ttk
from tkinter import filedialog
from tkinter import messagebox
import tkinter as tk
import os
import sys
import traceback
from datetime import datetime


def _resource_path(name):
    """Resolve a bundled resource both when run from source and when frozen
    into a PyInstaller onefile exe (files live under sys._MEIPASS then)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)

# ---------------- Backend ---------------- #
# Published patents  -> existing (unchanged) publication backend,
#                       orchestrated for multi-file by batch_extractor.
# Granted patents    -> independent grant backend.
# Both share the generic, sanitising Excel writer.
from batch_extractor import extract_published
from grant_extractor import extract_grants
from excel_writer import save_to_excel
from patent_extractor import PatentExtractionError
from journal_number import journal_number_range

# ---------------- v6 discovery layer (additive) ---------------- #
# Consumes extractor output; does not alter extraction or Excel flow.
from dataset import Dataset

# ---------------- Appearance ---------------- #

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# ---------------- Constants ---------------- #

WINDOW_WIDTH = 820
WINDOW_HEIGHT = 650

ENTRY_WIDTH = 620
PROGRESS_WIDTH = 620

TITLE_FONT = ("Arial", 26, "bold")
SUBTITLE_FONT = ("Arial", 13)
SECTION_FONT = ("Arial", 15, "bold")
STATUS_FONT = ("Arial", 12)

APP_VERSION = "Version 6.0"

# --------------------------------------------------


class PatentExtractorApp:

    def __init__(self):

        self.root = ctk.CTk()

        self.root.title(
            f"Indian Patent Journal Extractor - {APP_VERSION}"
        )

        self.root.geometry(
            f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}"
        )

        self.root.minsize(
            WINDOW_WIDTH,
            WINDOW_HEIGHT
        )

        # Application/window icon (branding). Safe no-op if unavailable.
        try:
            self.root.iconbitmap(_resource_path("icon.ico"))
        except Exception:
            pass

        # ---------------- Variables ---------------- #

        # "published" -> published patent applications (existing backend)
        # "granted"   -> granted patents (independent backend)
        self.mode = tk.StringVar(value="published")

        # One or more selected PDF files (multi-file selection).
        self.selected_pdfs = []

        self.output_folder = None

        # v6: in-memory dataset from the last extraction (for Search/Explore).
        self.dataset = None

        self.build_ui()

    # --------------------------------------------------

    def build_ui(self):

        self.create_menu()

        self.create_title()

        self.create_mode_section()

        self.create_source_section()

        self.create_action_section()

        self.create_progress_section()

        self.create_footer()

        self.toggle_mode()

    # --------------------------------------------------

    def create_menu(self):

        menu = tk.Menu(self.root)

        file_menu = tk.Menu(menu, tearoff=False)

        file_menu.add_command(
            label="Exit",
            command=self.root.destroy
        )

        menu.add_cascade(
            label="File",
            menu=file_menu
        )

        help_menu = tk.Menu(menu, tearoff=False)

        help_menu.add_command(
            label="About",
            command=self.show_about
        )

        menu.add_cascade(
            label="Help",
            menu=help_menu
        )

        self.root.config(menu=menu)

    # --------------------------------------------------

    def create_title(self):

        title = ctk.CTkLabel(
            self.root,
            text="Indian Patent Journal Extractor",
            font=TITLE_FONT
        )

        title.pack(
            pady=(18, 0)
        )

        subtitle = ctk.CTkLabel(
            self.root,
            text=APP_VERSION,
            font=SUBTITLE_FONT,
            text_color="gray75"
        )

        subtitle.pack(
            pady=(0, 18)
        )

    # --------------------------------------------------

    def create_mode_section(self):

        frame = ctk.CTkFrame(self.root)

        frame.pack(
            fill="x",
            padx=20,
            pady=10
        )

        heading = ctk.CTkLabel(
            frame,
            text="Extraction Type",
            font=SECTION_FONT
        )

        heading.pack(
            anchor="w",
            padx=15,
            pady=(12, 8)
        )

        self.published_radio = ctk.CTkRadioButton(
            frame,
            text="Published Patents",
            variable=self.mode,
            value="published",
            command=self.toggle_mode
        )

        self.published_radio.pack(
            anchor="w",
            padx=20,
            pady=4
        )

        self.granted_radio = ctk.CTkRadioButton(
            frame,
            text="Granted Patents",
            variable=self.mode,
            value="granted",
            command=self.toggle_mode
        )

        self.granted_radio.pack(
            anchor="w",
            padx=20,
            pady=(4, 12)
        )

    # --------------------------------------------------

    def create_source_section(self):

        frame = ctk.CTkFrame(self.root)

        frame.pack(
            fill="x",
            padx=20,
            pady=10
        )

        heading = ctk.CTkLabel(
            frame,
            text="Selected Source",
            font=SECTION_FONT
        )

        heading.pack(
            anchor="w",
            padx=15,
            pady=(12, 8)
        )

        self.source_label = ctk.CTkLabel(
            frame,
            text="No PDF(s) selected",
            width=ENTRY_WIDTH,
            height=34,
            corner_radius=8,
            fg_color=("gray90", "gray20"),
            anchor="w",
            padx=10
        )

        self.source_label.pack(
            padx=15,
            pady=5
        )

        self.browse_btn = ctk.CTkButton(
            frame,
            text="Select PDF File(s)",
            width=180,
            command=self.browse_source
        )

        self.browse_btn.pack(
            pady=(8, 15)
        )

    # --------------------------------------------------

    def create_action_section(self):

        self.action_frame = ctk.CTkFrame(self.root)
        frame = self.action_frame

        frame.pack(
            fill="x",
            padx=20,
            pady=10
        )

        self.extract_btn = ctk.CTkButton(
            frame,
            text="Extract",
            width=220,
            height=40,
            command=self.extract
        )

        self.extract_btn.pack(
            pady=(15, 8)
        )

        self.open_btn = ctk.CTkButton(
            frame,
            text="📂 Open Output Folder",
            width=220,
            height=35,
            command=self.open_output_folder
        )

        self.open_btn.pack(
            pady=(0, 8)
        )

        # v6: opens the discovery/search window for the last extraction.
        self.search_btn = ctk.CTkButton(
            frame,
            text="🔍 Search / Explore",
            width=220,
            height=35,
            state="disabled",
            command=self.open_search
        )

        self.search_btn.pack(
            pady=(0, 15)
        )

    # --------------------------------------------------

    def create_progress_section(self):

        frame = ctk.CTkFrame(self.root)

        frame.pack(
            fill="x",
            padx=20,
            pady=10
        )

        heading = ctk.CTkLabel(
            frame,
            text="Progress",
            font=SECTION_FONT
        )

        heading.pack(
            anchor="w",
            padx=15,
            pady=(12, 8)
        )

        self.progress = ttk.Progressbar(
            frame,
            orient="horizontal",
            mode="determinate",
            length=PROGRESS_WIDTH
        )

        self.progress.pack(
            pady=10
        )

        self.status = ctk.CTkLabel(
            frame,
            text="Ready.",
            font=STATUS_FONT
        )

        self.status.pack(
            pady=(0, 15)
        )

    # --------------------------------------------------

    def create_footer(self):

        footer = ctk.CTkFrame(
            self.root,
            fg_color="transparent"
        )

        footer.pack(
            side="bottom",
            fill="x",
            padx=15,
            pady=10
        )

        label = ctk.CTkLabel(
            footer,
            text="© 2026\nPraveen Reddy Thumukuntla",
            font=("Constantia", 11, "italic"),
            text_color="gray70",
            justify="right"
        )

        label.pack(
            side="right"
        )

    # --------------------------------------------------

    def _source_text(self):
        """Label text describing the current PDF selection."""

        count = len(self.selected_pdfs)

        if count == 0:
            return "No PDF(s) selected"

        if count == 1:
            return f"📄 {os.path.basename(self.selected_pdfs[0])}"

        return f"📄 {count} PDF(s) selected"

    # --------------------------------------------------

    def toggle_mode(self):
        """Both modes share the same select-file(s) workflow; only the
        status text differs."""

        self.source_label.configure(text=self._source_text())

        if self.mode.get() == "published":
            self.status.configure(text="Published Patents mode.")
        else:
            self.status.configure(text="Granted Patents mode.")

    # --------------------------------------------------

    def browse_source(self):

        selected = filedialog.askopenfilenames(
            title="Select Patent Journal PDF File(s)",
            filetypes=[("PDF Files", "*.pdf")]
        )

        if selected:

            self.selected_pdfs = list(selected)

            self.source_label.configure(text=self._source_text())

            self.status.configure(
                text=f"{len(self.selected_pdfs)} PDF(s) selected."
            )

    # --------------------------------------------------

    def show_about(self):

        messagebox.showinfo(
            "About",
            "Indian Patent Journal Extractor\n\n"
            "Version 6.0\n\n"
            "Developed by\n"
            "Praveen Reddy Thumukuntla\n\n"
            "© 2026"
        )

    # --------------------------------------------------
    # Backend integration
    # --------------------------------------------------

    def set_controls_state(self, state):
        """Enable/disable interactive controls during a run."""

        self.browse_btn.configure(state=state)
        self.extract_btn.configure(state=state)
        self.open_btn.configure(state=state)
        self.search_btn.configure(state=state)
        self.published_radio.configure(state=state)
        self.granted_radio.configure(state=state)

    # --------------------------------------------------

    def update_progress(self, current, total):
        """Progress callback shared by both backend routes."""

        if total:
            self.progress["value"] = (current / total) * 100

        self.status.configure(
            text=f"Processing page {current} of {total}..."
        )

        self.root.update_idletasks()

    # --------------------------------------------------

    def update_status(self, message):
        """Status callback used by both backend routes."""

        self.status.configure(text=message)

        self.root.update_idletasks()

    # --------------------------------------------------

    def extract(self):
        """Dispatch the Extract button between the two modes."""

        if self.mode.get() == "published":
            self.run_extraction(
                extract_published,
                "Published",
                "published patents",
            )
        else:
            self.run_extraction(
                extract_grants,
                "Granted",
                "granted patents",
            )

    # --------------------------------------------------

    def run_extraction(self, extractor, label, noun):
        """Shared run flow for both modes.

        `extractor(pdf_files, progress_callback, status_callback)` returns
        a merged, chronologically sorted list of record dicts. The two
        modes differ only by which extractor is passed in.
        """

        if not self.selected_pdfs:
            messagebox.showerror(
                "Error",
                "Please select one or more PDF file(s) first."
            )
            return

        stage = "starting"

        try:
            self.set_controls_state("disabled")
            self.progress["value"] = 0

            self.status.configure(text=f"Extracting {noun}...")
            self.root.update()

            stage = "extraction"
            records = extractor(
                self.selected_pdfs,
                progress_callback=self.update_progress,
                status_callback=self.update_status,
            )

            # Nothing extracted: do not create an empty workbook or report
            # success.
            if not records:
                self.progress["value"] = 0
                self.status.configure(
                    text=f"No {noun} found in the selected PDF(s)."
                )
                messagebox.showwarning(
                    "No Records Found",
                    f"No {noun} were found in the selected PDF(s).\n\n"
                    "No Excel file was created. Check that the correct "
                    "journal PDF(s) were selected for this mode, then try "
                    "again."
                )
                return

            output_file = self.build_output_path(label)

            self.output_folder = os.path.dirname(output_file)

            stage = "writing Excel"
            save_to_excel(records, output_file)

            # v6 (additive): keep the records in memory for Search / Explore.
            # This does not affect the Excel output above in any way.
            source_paths = {
                os.path.basename(p): p for p in self.selected_pdfs
            }
            self.dataset = Dataset.from_records(records, label, source_paths)

            self.progress["value"] = 100

            self.status.configure(
                text=f"Done! {len(records):,} {noun} extracted."
            )

            messagebox.showinfo(
                "Extraction Completed",
                "Extraction Completed\n\n"
                f"{noun.capitalize()} extracted : {len(records):,}\n\n"
                f"PDFs processed : {len(self.selected_pdfs)}\n\n"
                f"Output :\n{os.path.basename(output_file)}"
            )

        except Exception as e:
            self.status.configure(text="Extraction failed.")
            self.show_extraction_error(
                self._error_source_name(),
                e,
                stage,
            )

        finally:
            self.set_controls_state("normal")
            # Enable Search / Explore only when a dataset is loaded.
            self.search_btn.configure(
                state="normal" if self.dataset else "disabled"
            )

    # --------------------------------------------------

    def open_search(self):
        """Open the v6 discovery/search window for the loaded dataset.

        Imported lazily so any issue in the search layer can never affect the
        core extraction UI at startup.
        """

        if not self.dataset:
            messagebox.showwarning(
                "Warning",
                "Extract patents first, then Search / Explore."
            )
            return

        try:
            import search_ui
            search_ui.open_search_window(self.root, self.dataset)
        except Exception as e:
            messagebox.showerror(
                "Search unavailable",
                f"Could not open the search window:\n\n{e}"
            )

    # --------------------------------------------------

    def _error_source_name(self):
        """A short source description for the error dialog."""

        if len(self.selected_pdfs) == 1:
            return os.path.basename(self.selected_pdfs[0])
        return f"{len(self.selected_pdfs)} PDF(s)"

    # --------------------------------------------------

    def show_extraction_error(self, source_name, exc, stage):
        """Show a structured, actionable error instead of a raw dump.

        When the failure is a PatentExtractionError, the offending
        patent's title, application number and page are shown. For any
        other exception, the tracked stage and full traceback are shown.
        The raw exception message is truncated so a huge field value
        (e.g. an abstract) can never fill the dialog.
        """

        title = ""
        application = ""
        page = ""
        error_stage = stage

        if isinstance(exc, PatentExtractionError):
            title = exc.title or ""
            application = exc.application or ""
            page = "" if exc.page is None else exc.page
            error_stage = exc.stage or stage

        exc_message = str(exc).strip().replace("\n", " ")
        if len(exc_message) > 200:
            exc_message = exc_message[:200] + " ..."

        full_traceback = "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        )

        message = (
            f"PDF:\n{source_name}\n\n"
            f"Patent:\n{title}\n\n"
            f"Application:\n{application}\n\n"
            f"Page:\n{page}\n\n"
            f"Stage:\n{error_stage}\n\n"
            f"Exception:\n{type(exc).__name__}: {exc_message}\n\n"
            f"Full traceback:\n{full_traceback}"
        )

        messagebox.showerror("Extraction Error", message)

    # --------------------------------------------------

    def build_output_path(self, label):
        """Build a non-overwriting workbook path next to the first PDF.

        Named by the range of journals processed, e.g.
            Granted_Patents_29_to_32.xlsx
            Granted_Patents_29.xlsx                (single journal)
        Falls back to a timestamp when journal numbers can't be read:
            Granted_Patents_2026-08-17_11-54.xlsx
        On collision, append " (1)", " (2)", ... never overwriting.
        """

        folder = os.path.dirname(self.selected_pdfs[0])

        number_range = journal_number_range(self.selected_pdfs)

        if number_range:
            low, high = number_range
            suffix = f"{low}" if low == high else f"{low}_to_{high}"
        else:
            suffix = datetime.now().strftime("%Y-%m-%d_%H-%M")

        base_name = f"{label}_Patents_{suffix}"

        candidate = os.path.join(folder, f"{base_name}.xlsx")

        counter = 1
        while os.path.exists(candidate):
            candidate = os.path.join(
                folder,
                f"{base_name} ({counter}).xlsx"
            )
            counter += 1

        return candidate

    # --------------------------------------------------

    def open_output_folder(self):
        """Open the folder containing the generated workbook."""

        if not self.output_folder:
            messagebox.showwarning(
                "Warning",
                "Generate an Excel file first."
            )
            return

        os.startfile(self.output_folder)

    # --------------------------------------------------

    def run(self):

        self.root.mainloop()


# --------------------------------------------------

if __name__ == "__main__":

    app = PatentExtractorApp()

    app.run()
