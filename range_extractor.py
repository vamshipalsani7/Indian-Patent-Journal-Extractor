import os
from datetime import datetime

from patent_extractor import extract_patents
from journal_utils import get_journal_metadata


def extract_date_range(
    folder_path,
    from_date,
    to_date,
    progress_callback=None,
    status_callback=None,
):

    pdf_files = []

    # Search recursively inside all subfolders
    for root, dirs, files in os.walk(folder_path):

        for file in files:

            if file.lower().endswith(".pdf"):

                pdf_files.append(
                    os.path.join(root, file)
                )

    pdf_files.sort()

    if status_callback:
        status_callback(f"Found {len(pdf_files)} PDF(s).")

    all_patents = []

    matched = 0

    for pdf in pdf_files:

        metadata = get_journal_metadata(pdf)

        if metadata is None:
            continue

        if metadata["date"] == "Not Found":
            continue

        journal_date = datetime.strptime(
            metadata["date"],
            "%d/%m/%Y"
        ).date()

        if not (from_date <= journal_date <= to_date):
            continue

        matched += 1

        if status_callback:
            status_callback(
                f"Journal {matched}\n"
                f"Issue : {metadata['issue']}\n"
                f"Date  : {metadata['date']}"
            )

        patents = extract_patents(
            pdf,
            progress_callback=progress_callback
        )

        for patent in patents:

            patent["Journal Issue"] = metadata["issue"]
            patent["Journal Date"] = metadata["date"]
            patent["Source PDF"] = os.path.basename(pdf)

        all_patents.extend(patents)

    return all_patents


# ---------------------------------------------------
# TEST
# ---------------------------------------------------

if __name__ == "__main__":

    folder = r"C:\Users\91630\OneDrive\Desktop\Patent extractor\input"

    from_date = datetime.strptime(
        "03/07/2026",
        "%d/%m/%Y"
    ).date()

    to_date = datetime.strptime(
        "31/07/2026",
        "%d/%m/%Y"
    ).date()

    patents = extract_date_range(
        folder,
        from_date,
        to_date
    )

    print("\n--------------------------------------")
    print(f"Total patents extracted : {len(patents)}")
    print("--------------------------------------")

    if patents:

        print("\nFirst Patent\n")

        for key, value in patents[0].items():
            print(f"{key}: {value}")