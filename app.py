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
app.secret_key = os.environ.get('SECRET_KEY', 'cloud-secret')


# ==============================
# BRFv1.0 STRICT CONFIG
# ==============================

BRF = {
    "font_name": "Times New Roman",
    "font_size": 10,
    "space_before": 0,
    "space_after": 0,
    "line_spacing": 1,
    "summary_heading": "Summary :",
    "technical_heading": "Technical Skills :",
    "education_heading": "Education :",
    "experience_heading": "Professional Experience :"
}


# ==============================
# UTILITIES
# ==============================

def extract_text(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    text = ""

    if ext == ".pdf":
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
    elif ext == ".docx":
        text = docx2txt.process(file_path)

    return text


def clean_line(line):
    """Remove ALL original bullet symbols without changing wording"""
    return re.sub(r'^[\-\•\●\▪\*\–]+\s*', '', line.strip())


def apply_global_formatting(doc):
    style = doc.styles['Normal']
    style.font.name = BRF["font_name"]
    style.font.size = Pt(BRF["font_size"])

    for p in doc.paragraphs:
        p.paragraph_format.space_before = Pt(BRF["space_before"])
        p.paragraph_format.space_after = Pt(BRF["space_after"])
        p.paragraph_format.line_spacing = BRF["line_spacing"]


# ==============================
# STRICT SECTION PARSER
# ==============================

def strict_parse(text):
    """
    DOES NOT MODIFY CONTENT.
    ONLY SPLITS BASED ON HEADINGS.
    """

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

    return {
        "name": name,
        "first": first,
        "last": last,
        "sections": sections
    }


# ==============================
# STRICT DOC CREATION
# ==============================

def create_brf_doc(data):
    doc = Document()

    # NAME CENTERED
    name_para = doc.add_paragraph(data["name"])
    name_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

    sections = data["sections"]

    # ================= SUMMARY =================
    p = doc.add_paragraph(BRF["summary_heading"])
    p.runs[0].bold = True

    for line in sections["summary"]:
        line = clean_line(line)
        if line.strip():
            doc.add_paragraph(f"• {line}")

    doc.add_paragraph()  # one line gap after summary


    # ================= TECHNICAL SKILLS =================
    p = doc.add_paragraph(BRF["technical_heading"])
    p.runs[0].bold = True

    for line in sections["technical"]:
        line = clean_line(line)
        if line.strip():
            doc.add_paragraph(line)

    doc.add_paragraph()  # one line gap after education


    # ================= EDUCATION =================
    p = doc.add_paragraph(BRF["education_heading"])
    p.runs[0].bold = True

    for line in sections["education"]:
        line = clean_line(line)
        if line.strip():
            doc.add_paragraph(line)

    doc.add_paragraph()


    # ================= EXPERIENCE =================
    p = doc.add_paragraph(BRF["experience_heading"])
    p.runs[0].bold = True

    buffer = []

    for line in sections["experience"]:
        line = clean_line(line)

        if line.strip() == "":
            continue

        buffer.append(line)

        # Detect new project when line looks like company header
        if "," in line and len(buffer) > 1:
            pass

    # STRICT RULE:
    # We do NOT restructure.
    # We only apply bullet formatting AFTER first 2 lines of each block.

    project_lines = []
    for line in sections["experience"]:
        line = clean_line(line)
        if line.strip():
            project_lines.append(line)

    i = 0
    while i < len(project_lines):

        # Line 1: Company, Location, Duration
        doc.add_paragraph(project_lines[i])
        i += 1

        # Line 2: Role
        if i < len(project_lines):
            doc.add_paragraph(project_lines[i])
            i += 1

        # Remaining lines as bullets until next header pattern
        while i < len(project_lines) and "," not in project_lines[i]:
            doc.add_paragraph(f"• {project_lines[i]}")
            i += 1

        doc.add_paragraph()  # one blank line after project

    apply_global_formatting(doc)

    filename = f"{data['first']} {data['last']}.docx"
    path = f"/tmp/{filename}"
    doc.save(path)

    return path, filename


# ==============================
# ROUTE
# ==============================

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        file = request.files.get("resume")

        if not file:
            flash("Upload a resume file")
            return render_template_string("<h1>Error</h1>")

        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            file.save(tmp.name)
            text = extract_text(tmp.name)
            os.unlink(tmp.name)

        data = strict_parse(text)
        path, filename = create_brf_doc(data)

        return send_file(path,
                         as_attachment=True,
                         download_name=filename,
                         mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    return "<h1>BRFv1.0 Strict Engine Running</h1>"


if __name__ == "__main__":
    app.run()
