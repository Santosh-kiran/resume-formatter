import pdfplumber
from docx import Document
from striprtf.striprtf import rtf_to_text
from odf.opendocument import load
from odf import text as odf_text

def extract_text(file_path):
    ext = file_path.split('.')[-1].lower()

    if ext == "pdf":
        with pdfplumber.open(file_path) as pdf:
            return "\n".join(
                page.extract_text() for page in pdf.pages if page.extract_text()
            )

    elif ext == "docx":
        doc = Document(file_path)
        return "\n".join(p.text for p in doc.paragraphs)

    elif ext == "rtf":
        with open(file_path, "r", errors="ignore") as f:
            return rtf_to_text(f.read())

    elif ext == "odt":
        doc = load(file_path)
        paragraphs = doc.getElementsByType(odf_text.P)
        return "\n".join(str(p) for p in paragraphs)

    else:
        with open(file_path, "r", errors="ignore") as f:
            return f.read()
