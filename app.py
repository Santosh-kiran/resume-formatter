from flask import Flask, render_template_string, request, send_file, flash
import os
import tempfile
import re
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import docx2txt
import pdfplumber

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "cloud-secret")


# =========================
# BRFv1.0 STRICT SETTINGS
# =========================
FONT_NAME = "Times New Roman"
FONT_SIZE = 10

SUMMARY_HEADING = "Summary :"
TECH_HEADING = "Technical Skills :"
EDU_HEADING = "Education :"
EXP_HEADING = "Professional Experience :"


# =========================
# TEXT EXTRACTION
# =========================
def extract_text(path):
    ext = os.path.splitext(path)[1].lower()
    text = ""

    if ext == ".pdf":
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
    elif ext == ".docx":
        text = docx2txt.process(path)

    return text


# =========================
# REMOVE ALL ORIGINAL BULLETS
# =========================
def remove_original_bullets(line):
    return re.sub(
        r'^\s*[\-\•\●\▪\◦\▪\■\□\*\–\—\→\►\➤\➔\➢\✓\✔\·]+\s*',
        '',
        line
    )


# =========================
# APPLY GLOBAL FORMATTING
# =========================
def apply_global_formatting(doc):
    style = doc.styles["Normal"]
    style.font.name = FONT_NAME
    style.font.size = Pt(FONT_SIZE)

    for p in doc.paragraphs:
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = 1


# =========================
# STRICT SECTION PARSER
# =========================
def parse_sections(text):

    lines = [l.rstrip() for l in text.split("\n")]

    name = lines[0].strip()
    first = name.split()[0]
    last = " ".join(name.split()[1:]) if len(name.split()) > 1 else ""

    sections = {
        "summary": [],
        "technical": [],
        "education": [],
        "experience": []
    }

    current = None

    for line in lines[1:]:
        lower = line.lower()

        if "summary" in lower:
            current = "summary"
            continue
        elif "technical" in lower:
            current = "technical"
            continue
        elif "education" in lower:
            current = "education"
            continue
        elif "experience" in lower:
            current = "experience"
            continue

        if current:
            sections[current].append(line)

    return name, first, last, sections


# =========================
# CREATE STRICT BRF DOC
# =========================
def create_brf_document(name, first, last, sections):

    doc = Document()

    # NAME CENTERED
    p = doc.add_paragraph(name)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # ================= SUMMARY =================
    p = doc.add_paragraph(SUMMARY_HEADING)
    p.runs[0].bold = True

    for line in sections["summary"]:
        cleaned = remove_original_bullets(line).strip()
        if cleaned:
            doc.add_paragraph("• " + cleaned)

    doc.add_paragraph()  # one blank line after Summary


    # ================= TECHNICAL SKILLS =================
    p = doc.add_paragraph(TECH_HEADING)
    p.runs[0].bold = True

    for line in sections["technical"]:
        cleaned = remove_original_bullets(line).strip()
        if cleaned:
            doc.add_paragraph(cleaned)


    # ================= EDUCATION =================
    p = doc.add_paragraph(EDU_HEADING)
    p.runs[0].bold = True

    for line in sections["education"]:
        cleaned = remove_original_bullets(line).strip()
        if cleaned:
            doc.add_paragraph(cleaned)

    doc.add_paragraph()  # one blank line after Education


    # ================= PROFESSIONAL EXPERIENCE =================
    p = doc.add_paragraph(EXP_HEADING)
    p.runs[0].bold = True

    exp_lines = [
        remove_original_bullets(l).strip()
        for l in sections["experience"]
        if l.strip()
    ]

    i = 0
    while i < len(exp_lines):

        # Line 1: Company, Location, Duration
        doc.add_paragraph(exp_lines[i])
        i += 1

        # Line 2: Role
        if i < len(exp_lines):
            doc.add_paragraph(exp_lines[i])
            i += 1

        # Remaining lines as BRF bullets
        while i < len(exp_lines) and not exp_lines[i].endswith(":"):
            doc.add_paragraph("• " + exp_lines[i])
            i += 1

        doc.add_paragraph()  # one blank line after each project


    apply_global_formatting(doc)

    filename = f"{first} {last}.docx"
    path = f"/tmp/{filename}"
    doc.save(path)

    return path, filename


# =========================
# ROUTE
# =========================
@app.route("/", methods=["GET", "POST"])
def index():

    if request.method == "POST":
        file = request.files.get("resume")

        if not file or not file.filename:
            flash("Please upload a resume file")
            return render_template_string("<h1>Error</h1>")

        if not file.filename.lower().endswith((".pdf", ".docx")):
            flash("Only PDF and DOCX supported")
            return render_template_string("<h1>Error</h1>")

        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            file.save(tmp.name)
            text = extract_text(tmp.name)
            os.unlink(tmp.name)

        name, first, last, sections = parse_sections(text)

        path, filename = create_brf_document(
            name, first, last, sections
        )

        return send_file(
            path,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

    return "<h2>BRFv1.0 Strict Formatter Running</h2>"


if __name__ == "__main__":
    app.run()
