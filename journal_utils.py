import fitz
import re


def get_journal_metadata(pdf_path):
    """
    Extracts Journal Issue Number and Publication Date
    from the first page of an Indian Patent Journal PDF.
    """

    try:
        doc = fitz.open(pdf_path)

        # Read only the first page
        first_page = doc[0].get_text()

        doc.close()

        # -----------------------------
        # Extract Issue Number
        # Example:
        # ISSUE NO. 27/2026
        # -----------------------------
        issue_match = re.search(
            r"ISSUE\s*NO\.\s*(\d+/\d+)",
            first_page,
            re.IGNORECASE
        )

        # -----------------------------
        # Extract Publication Date
        # Example:
        # DATE: 03/07/2026
        # -----------------------------
        date_match = re.search(
            r"DATE:\s*(\d{2}/\d{2}/\d{4})",
            first_page,
            re.IGNORECASE
        )

        metadata = {
            "issue": issue_match.group(1) if issue_match else "Not Found",
            "date": date_match.group(1) if date_match else "Not Found"
        }

        return metadata

    except Exception as e:
        print(f"Error: {e}")
        return None


# --------------------------------------------------------
# Test
# --------------------------------------------------------

if __name__ == "__main__":

    pdf_path = r"C:\Users\91630\OneDrive\Desktop\Patent extractor\input\July 3(1).pdf"

    metadata = get_journal_metadata(pdf_path)

    print("\nJournal Metadata")
    print("------------------------")
    print("Issue :", metadata["issue"])
    print("Date  :", metadata["date"])