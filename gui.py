from patent_extractor import extract_patents
from excel_writer import save_to_excel
from tkinter import messagebox, filedialog
from tkinter import ttk
import customtkinter as ctk
import os
import subprocess

# -------------------- Appearance --------------------
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# -------------------- Window --------------------
app = ctk.CTk()
app.title("Indian Patent Journal Extractor")
app.geometry("750x500")

selected_pdf = ""
output_folder = ""

# -------------------- Title --------------------
title = ctk.CTkLabel(
    app,
    text="Indian Patent Journal Extractor",
    font=("Arial", 24, "bold")
)
title.pack(pady=20)

# -------------------- Selected PDF --------------------
selected_label = ctk.CTkLabel(
    app,
    text="Selected PDF:"
)
selected_label.pack(pady=(5, 5))

pdf_entry = ctk.CTkEntry(
    app,
    width=550
)
pdf_entry.pack(pady=(0, 15))
pdf_entry.configure(state="readonly")


# -------------------- Browse PDF --------------------
def browse_pdf():
    global selected_pdf

    selected_pdf = filedialog.askopenfilename(
        title="Select Patent Journal PDF",
        filetypes=[("PDF Files", "*.pdf")]
    )

    if selected_pdf:
        pdf_entry.configure(state="normal")
        pdf_entry.delete(0, "end")
        pdf_entry.insert(0, selected_pdf)
        pdf_entry.configure(state="readonly")

        status.configure(text="PDF selected.")


# -------------------- Progress --------------------
def update_progress(current, total):
    percentage = (current / total) * 100
    progress["value"] = percentage
    status.configure(text=f"Processing page {current} of {total}...")
    app.update_idletasks()


# -------------------- Generate Excel --------------------
def generate_excel():
    global selected_pdf, output_folder

    if not selected_pdf:
        messagebox.showerror(
            "Error",
            "Please select a Patent Journal PDF first."
        )
        return

    try:
        browse_btn.configure(state="disabled")
        generate_btn.configure(state="disabled")
        open_folder_btn.configure(state="disabled")
        progress["value"] = 0

        status.configure(text="Extracting patents...")
        app.update()

        patents = extract_patents(
            selected_pdf,
            progress_callback=update_progress
        )

        pdf_name = os.path.splitext(os.path.basename(selected_pdf))[0]

        output_file = os.path.join(
         os.path.dirname(selected_pdf),
         f"{pdf_name}.xlsx"
)

        output_folder = os.path.dirname(output_file)

        save_to_excel(patents, output_file)

        progress["value"] = 100

        status.configure(
            text=f"Done! {len(patents)} patents extracted."
        )

        messagebox.showinfo(
            "Success",
            f"Excel saved successfully!\n\n{output_file}"
        )

    except Exception as e:
        messagebox.showerror(
            "Error",
             str(e)
        )

    finally:
        browse_btn.configure(state="normal")
        generate_btn.configure(state="normal")
        open_folder_btn.configure(state="normal")


# -------------------- Open Output Folder --------------------
def open_output_folder():
    global output_folder

    if not output_folder:
        messagebox.showwarning(
            "Warning",
            "Generate an Excel file first."
        )
        return

    os.startfile(output_folder)


# -------------------- Buttons --------------------
browse_btn = ctk.CTkButton(
    app,
    text="Browse Patent Journal PDF",
    command=browse_pdf
)
browse_btn.pack(pady=(10, 8))

generate_btn = ctk.CTkButton(
    app,
    text="Generate Excel",
    command=generate_excel
)
generate_btn.pack(pady=(8, 8))

open_folder_btn = ctk.CTkButton(
    app,
    text="📂 Open Output Folder",
    command=open_output_folder
)
open_folder_btn.pack(pady=(8, 15))

# -------------------- Progress Bar --------------------
progress = ttk.Progressbar(
    app,
    orient="horizontal",
    length=550,
    mode="determinate"
)
progress.pack(pady=10)

# -------------------- Status --------------------
status = ctk.CTkLabel(
    app,
    text="Status: Waiting..."
)
status.pack(pady=15)

# -------------------- Run --------------------
app.mainloop()