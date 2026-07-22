from excel_writer import save_to_excel

from patent_extractor import extract_patents

PDF_FILE = "input/Patent_Journal.pdf"
OUTPUT_FILE = "output/Patent_Journal_Output.xlsx"

patents = extract_patents(PDF_FILE)

save_to_excel(patents, OUTPUT_FILE)

print("=" * 60)
print("Extraction Completed Successfully!")
print(f"Total Patents Extracted: {len(patents)}")
print(f"Excel File Saved As: {OUTPUT_FILE}")
print("=" * 60)