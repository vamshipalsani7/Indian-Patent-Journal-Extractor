"""
Indian Patent Journal Extractor
Version 4.0

GUI Foundation
Sprint 1 - Part 1

Author:
Praveen Reddy Thumukuntla
"""

import customtkinter as ctk
from tkinter import ttk
from tkinter import filedialog
from tkinter import messagebox
from tkcalendar import DateEntry
import tkinter as tk
import os
import time

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

APP_VERSION = "Version 4.0"

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

        # ---------------- Variables ---------------- #

        self.mode = tk.StringVar(value="single")

# Remember selections separately
        self.selected_pdf = None
        self.selected_folder = None

        self.output_folder = None

        self.start_time = None
        self.build_ui()

    # --------------------------------------------------

    def build_ui(self):

        self.create_menu()

        self.create_title()

        self.create_mode_section()

        self.create_source_section()

        self.create_date_section()

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
            text="Extraction Mode",
            font=SECTION_FONT
        )

        heading.pack(
            anchor="w",
            padx=15,
            pady=(12, 8)
        )

        self.single_radio = ctk.CTkRadioButton(
            frame,
            text="Single Patent Journal",
            variable=self.mode,
            value="single",
            command=self.toggle_mode
        )

        self.single_radio.pack(
            anchor="w",
            padx=20,
            pady=4
        )

        self.range_radio = ctk.CTkRadioButton(
            frame,
            text="Date Range Extraction",
            variable=self.mode,
            value="range",
            command=self.toggle_mode
        )

        self.range_radio.pack(
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
            text="No source selected",
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
            text="Browse",
            width=150,
            command=self.browse_source
        )

        self.browse_btn.pack(
            pady=(8, 15)
        )

    # --------------------------------------------------

    def create_date_section(self):

        self.date_frame = ctk.CTkFrame(self.root)

        self.date_frame.pack(
            fill="x",
            padx=20,
            pady=10
        )

        heading = ctk.CTkLabel(
            self.date_frame,
            text="Date Range",
            font=SECTION_FONT
        )

        heading.pack(
            anchor="w",
            padx=15,
            pady=(12, 12)
        )

        row = ctk.CTkFrame(
            self.date_frame,
            fg_color="transparent"
        )

        row.pack(
            pady=(0, 15)
        )

        from_label = ctk.CTkLabel(
            row,
            text="From"
        )

        from_label.grid(
            row=0,
            column=0,
            padx=10
        )

        self.from_date = DateEntry(
            row,
            date_pattern="dd/mm/yyyy",
            width=14
        )

        self.from_date.grid(
            row=0,
            column=1,
            padx=10
        )

        to_label = ctk.CTkLabel(
            row,
            text="To"
        )

        to_label.grid(
            row=0,
            column=2,
            padx=10
        )

        self.to_date = DateEntry(
            row,
            date_pattern="dd/mm/yyyy",
            width=14
        )

        self.to_date.grid(
            row=0,
            column=3,
            padx=10
        )

    # --------------------------------------------------

    def create_action_section(self):

        frame = ctk.CTkFrame(self.root)

        frame.pack(
            fill="x",
            padx=20,
            pady=10
        )

        self.extract_btn = ctk.CTkButton(
            frame,
            text="Extract Patents",
            width=220,
            height=40
            # command added in Part 2
        )

        self.extract_btn.pack(
            pady=(15, 8)
        )

        self.open_btn = ctk.CTkButton(
            frame,
            text="📂 Open Output Folder",
            width=220,
            height=35
            # command added later
        )

        self.open_btn.pack(
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

    def toggle_mode(self):

     if self.mode.get() == "single":

        # Hide Date Range section
        self.date_frame.pack_forget()

        # Update placeholder
        if self.selected_pdf is None:
            self.source_label.configure(
                text="📄 No PDF selected"
            )
        else:
            self.source_label.configure(
                text=f"📄 {os.path.basename(self.selected_pdf)}"
            )

        self.status.configure(
            text="Single Patent Journal mode."
        )

     else:

        # Show Date Range section
        self.date_frame.pack(
            fill="x",
            padx=20,
            pady=10
        )

        # Update placeholder
        if self.selected_folder is None:
            self.source_label.configure(
                text="📁 No folder selected"
            )
        else:
            self.source_label.configure(
                text=f"📁 {os.path.basename(self.selected_folder)}"
            )

        self.status.configure(
            text="Date Range Extraction mode."
        )
    # --------------------------------------------------

    def browse_source(self):

     if self.mode.get() == "single":

        selected = filedialog.askopenfilename(
            title="Select Patent Journal PDF",
            filetypes=[("PDF Files", "*.pdf")]
        )

        if selected:

            self.selected_pdf = selected

            self.source_label.configure(
                text=f"📄 {os.path.basename(selected)}"
            )

            self.status.configure(
                text="Patent Journal selected."
            )

     else:

        selected = filedialog.askdirectory(
            title="Select Journal Folder"
        )

        if selected:

            self.selected_folder = selected

            self.source_label.configure(
                text=f"📁 {os.path.basename(selected)}"
            )

            self.status.configure(
                text="Journal folder selected."
            )
    # --------------------------------------------------

    def show_about(self):

        messagebox.showinfo(
            "About",
            "Indian Patent Journal Extractor\n\n"
            "Version 4.0\n\n"
            "Developed by\n"
            "Praveen Reddy Thumukuntla\n\n"
            "© 2026"
        )

    # --------------------------------------------------

    def run(self):

        self.root.mainloop()


# --------------------------------------------------

if __name__ == "__main__":

    app = PatentExtractorApp()

    app.run()