import streamlit as st
import docx
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import fitz  # PyMuPDF for PDF
import docx2txt
import pdfplumber
import re
import os

st.title("Resume Formatter")

uploaded_file = st.file_uploader("Upload Resume", type=['pdf', 'doc', 'docx', 'txt'])

if uploaded_file:
    # Extract text (handle formats)
    if uploaded_file.name.endswith('.pdf'):
        with pdfplumber.open(uploaded_file) as pdf:
            text = '\n'.join(page.extract_text() for page in pdf.pages)
    else:
        text = docx2txt.process(uploaded_file)

    # Parse sections (regex-based; customize per your needs for Summary, Skills, etc.)
    name = re.search(r'([A-Z][a-z]+ [A-Z][a-z]+)', text[:200]).group(0)  # Extract name
    first, last = name.split()
    name_formatted = f"{first.capitalize()} {last.capitalize()}"

    # Create DOCX
    doc = Document()
    doc.styles['Normal'].font.name = 'Times New Roman'

    # Name (Req 3)
    p = doc.add_paragraph(name_formatted)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.runs
    run.bold = True
    run.font.size = Pt(11)

    doc.add_paragraph()  # Space

    # Summary (Req 4)
    summary_match = re.search(r'Summary(.*?)Technical Skills', text, re.DOTALL | re.I)
    if summary_match:
        summary = [line.strip() for line in summary_match.group(1).split('\n') if line.strip()]
        p = doc.add_paragraph('Summary')
        p.runs.bold = True
        p.runs.font.size = Pt(10)
        for item in summary:
            p = doc.add_paragraph(f"-  {item}")
            p.paragraph_format.space_before = 0
            p.paragraph_format.space_after = 0
            run = p.runs
            run.font.size = Pt(10)
            run.font.name = 'Times New Roman'

    # Add other sections similarly: Technical Skills (Req 5), Education/Cert/Training (Req 6), Experience (Req 7)
    # Parse with regex, format bullets/spacing/tabs per specs. Example for Experience:
    # exp_match = re.search(r'Professional Experience(.*)', text, re.DOTALL | re.I)
    # Split into projects, format Company/Location/Duration, Role, bullets.

    # Global: Zero spacing, TNR font everywhere
    for para in doc.paragraphs:
        para.paragraph_format.space_before = 0
        para.paragraph_format.space_after = 0

    # Save & Download (Req 2)
    filename = f"{first.capitalize()} {last.capitalize()}.docx"
    doc.save(filename)
    with open(filename, 'rb') as f:
        st.download_button("Download Formatted Resume", f.read(), file_name=filename)
    os.remove(filename)
