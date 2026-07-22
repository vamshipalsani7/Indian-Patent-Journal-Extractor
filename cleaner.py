def clean(text):
    if not text:
        return ""

    text = text.replace("\n", " ")
    text = text.replace("\r", " ")
    text = " ".join(text.split())

    if text.startswith(":"):
        text = text[1:].strip()

    return text