patterns = {
    "Application No": r"\(21\)\s*Application No\.([^\n]+)",
    "Filing Date": r"\(22\)\s*Date of filing of Application\s*:([^\n]+)",
    "Publication Date": r"\(43\)\s*Publication Date\s*:([^\n]+)",
    "Title": r"\(54\).*?:\s*(.*?)\n\s*\(51\)",
    "IPC": r"\(51\)\s*International classification\s*(.*?)\n\s*\(31\)",

    "Priority Document No": r"\(31\)\s*Priority Document No\s*:([^\n]+)",
    "Priority Date": r"\(32\)\s*Priority Date\s*:([^\n]+)",
    "Priority Country": r"\(33\)\s*Name of priority country\s*:([^\n]+)",

    "International Application No": r"\(86\)\s*International Application No\s*.*?:\s*(.*?)\n",
    "International Publication No": r"\(87\)\s*International Publication No\s*:([^\n]+)",

    "Patent of Addition": r"\(61\)\s*Patent of Addition to Application Number\s*:([^\n]+)",
    "Divisional Application": r"\(62\)\s*Divisional to Application Number\s*:([^\n]+)",

    "Applicant": r"\(71\)Name of Applicant\s*:\s*(.*?)\n\s*\(72\)",
    "Inventor": r"\(72\)Name of Inventor\s*:\s*(.*?)\n\s*\(57\)",
    "Abstract": r"\(57\)\s*Abstract\s*:\s*(.*?)No\. of Pages"
}