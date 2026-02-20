from flask import Flask, request, send_file, render_template_string
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from PyPDF2 import PdfReader
import docx2txt
from io import BytesIO

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        file = request.files['file']
        text = ""
        
        # Convert to text
        if file.filename.endswith('.pdf'):
            reader = PdfReader(file)
            text = "\n".join(page.extract_text() for page in reader.pages)
        else:
            text = docx2txt.process(file)
        
        # Simple parsing
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        name = lines[0].title() if lines else "John Doe"
        
        # Create formatted doc
        doc = Document()
        
        # Name (Centered, 11pt bold)
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(name)
        run.bold = True
        run.font.size = Pt(11)
        run.font.name = 'Times New Roman'
        
        # Sections with exact formatting
        sections = {
            'Summary': lines[1:5], 'Technical Skills': lines[5:12],
            'Education, Certification & Training': lines[12:20],
            'Professional Experience': lines[20:35]
        }
        
        for title, content in sections.items():
            doc.add_paragraph()
            h = doc.add_paragraph(title)
            h.runs[0].bold = True
            h.runs[0].font.size = Pt(10)
            h.runs[0].font.name = 'Times New Roman'
            
            for line in content[:8]:
                if line:
                    bullet = '• ' if title != 'Technical Skills' else ''
                    p = doc.add_paragraph(f'  {bullet}{line}')
                    p.runs[0].font.size = Pt(10)
                    p.runs[0].font.name = 'Times New Roman'
        
        # Save with exact filename
        bio = BytesIO()
        doc.save(bio)
        bio.seek(0)
        
        filename = f"{name.split()[0]} {name.split()[-1]}.docx"
        return send_file(bio, as_attachment=True, download_name=filename)
    
    return '''
    <!DOCTYPE html>
    <html><body style="text-align:center;padding:50px;font-family:Arial;">
    <h1>📄 Resume Formatter</h1>
    <p>Upload PDF/DOCX → Get Perfect Formatted Resume</p>
    <form method=post enctype=multipart/form-data style="max-width:400px;margin:auto;">
        <input type=file name=file accept=".pdf,.docx" style="width:100%;padding:10px;margin:10px;">
        <button type=submit style="width:100%;padding:15px;font-size:18px;background:#007bff;color:white;border:none;border-radius:5px;">Format Resume</button>
    </form>
    </body></html>
    '''

if __name__ == '__main__':
    from waitress import serve
    serve(app, host='0.0.0.0', port=8080)
