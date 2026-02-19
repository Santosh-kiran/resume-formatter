from flask import Flask, render_template_string, request, send_file, flash
import os
import tempfile
import re
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import docx2txt
try:
    import pdfplumber
except:
    pdfplumber = None

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'cloud-secret')

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>BRFv1.0 Cloud Formatter</title>
    <style>
        *{margin:0;padding:0;box-sizing:border-box;}
        body{font-family:Arial,sans-serif;background:linear-gradient(135deg,#667eea,#764ba2);min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px;}
        .container{background:white;border-radius:20px;padding:3rem;max-width:500px;width:100%;box-shadow:0 25px 50px rgba(0,0,0,0.2);text-align:center;}
        h1{font-size:2.5rem;background:linear-gradient(135deg,#667eea,#764ba2);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:1rem;}
        .upload-zone{border:3px dashed #667eea;border-radius:15px;padding:3rem 2rem;cursor:pointer;transition:all 0.3s;background:#f8f9ff;margin:2rem 0;}
        .upload-zone:hover{background:#e3f2fd;border-color:#5a67d8;}
        .upload-zone.has-file{border-color:#10b981;background:#f0fff4;}
        button{background:linear-gradient(135deg,#667eea,#764ba2);color:white;border:none;padding:1.5rem 3rem;border-radius:50px;font-size:1.1rem;cursor:pointer;width:100%;margin-top:1rem;}
        button:hover{transform:translateY(-3px);box-shadow:0 15px 30px rgba(102,126,234,0.4);}
        .features{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:1rem;margin-top:2rem;}
        .feature{padding:1rem;text-align:center;}
        .feature i{font-size:2rem;color:#667eea;margin-bottom:0.5rem;}
        #fileInfo{margin-top:1rem;padding-top:1rem;border-top:1px solid #eee;}
        .alert{padding:1rem;border-radius:8px;margin:1rem 0;background:#fee;color:#c33;}
    </style>
</head>
<body>
    <div class="container">
        <h1>BRFv1.0 Formatter</h1>
        <p>Upload resume → Get formatted .docx instantly</p>
        
        {% with messages=get_flashed_messages() %}
            {% if messages %}
                <div class="alert">{{ messages[0] }}</div>
            {% endif %}
        {% endwith %}
        
        <form method="POST" enctype="multipart/form-data">
            <div class="upload-zone" id="uploadZone">
                <div>📄 Drop resume here or click</div>
                <input type="file" name="resume" id="fileInput" accept=".pdf,.docx,.doc" required style="display:none;">
                <div id="fileInfo">No file selected</div>
            </div>
            <button type="submit">✨ Convert to BRFv1.0</button>
        </form>
        
        <div class="features">
            <div class="feature"><div>📎</div><div>PDF/DOCX</div></div>
            <div class="feature"><div>📏</div><div>10pt TNR</div></div>
            <div class="feature"><div>✅</div><div>BRFv1.0</div></div>
        </div>
    </div>
    <script>
        const zone=document.getElementById('uploadZone'),input=document.getElementById('fileInput'),info=document.getElementById('fileInfo');
        zone.onclick=()=>input.click();
        input.onchange=e=>{info.textContent=e.target.files[0]?.name||'No file';zone.classList.toggle('has-file',e.target.files[0]);};
    </script>
</body>
</html>
'''

def extract_text(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    text = ""
    if ext == '.pdf' and pdfplumber:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages: text += page.extract_text() or ""
    elif ext == '.docx': text = docx2txt.process(file_path)
    return text.strip()

def parse_resume(text):
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    name = lines[0] if lines else "Candidate"
    first, last = (name.split()[0], " ".join(name.split()[1:])) if " " in name else ("First", "Last")
    
    sections = {'summary':[], 'skills':[], 'education':[], 'projects':[]}
    current, project = None, []
    
    for line in lines:
        lw = line.lower()
        if any(k in lw for k in ['summary','profile','objective']):
            current = 'summary'
        elif any(k in lw for k in ['skill','tech','technology']):
            current = 'skills'
        elif any(k in lw for k in ['education','degree','university']):
            current = 'education'
        elif any(k in lw for k in ['experience','project','work']):
            if project: sections['projects'].append(" ".join(project)); project=[]
            current = 'projects'
        
        if current and line:
            if current == 'projects': project.append(line)
            else: sections[current].append(line)
    
    if project: sections['projects'].append(" ".join(project))
    return {'name':name, 'first_name':first, 'last_name':last, 'summary':sections['summary'], 'technical_skills':sections['skills'], 'education':sections['education'], 'projects':sections['projects']}

def create_docx(data):
    doc = Document()
    
    # Set Times New Roman 10pt globally
    style = doc.styles['Normal']
    style.font.name = 'Times New Roman'
    style.font.size = Pt(10)
    
    # NAME (Centered)
    p = doc.add_paragraph(data['name'])
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # SUMMARY :
    p = doc.add_paragraph('Summary :')
    p.runs[0].bold = True
    for item in data['summary']:
        doc.add_paragraph(f"• {item}")
    doc.add_paragraph()
    
    # TECHNICAL SKILLS :
    p = doc.add_paragraph('Technical Skills :')
    p.runs[0].bold = True
    for skill in data['technical_skills']:
        doc.add_paragraph(skill)
    doc.add_paragraph()
    
    # EDUCATION :
    p = doc.add_paragraph('Education :')
    p.runs[0].bold = True
    for edu in data['education']:
        doc.add_paragraph(edu)
    doc.add_paragraph()
    
    # PROFESSIONAL EXPERIENCE :
    p = doc.add_paragraph('Professional Experience :')
    p.runs[0].bold = True
    for proj in data['projects']:
        doc.add_paragraph(proj[:150])
        for line in proj.split('.'):
            if line.strip(): doc.add_paragraph(f"• {line.strip()}")
        doc.add_paragraph()
    
    filename = f"{data['first_name']} {data['last_name']}.docx"
    path = f"/tmp/{filename}"
    doc.save(path)
    return path, filename

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        file = request.files.get('resume')
        if not file or not file.filename:
            flash('Please select a file')
            return render_template_string(HTML_TEMPLATE)
        
        if not file.filename.lower().endswith(('.pdf','.docx')):
            flash('Only PDF/DOCX supported')
            return render_template_string(HTML_TEMPLATE)
        
        try:
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                file.save(tmp.name)
                text = extract_text(tmp.name)
                os.unlink(tmp.name)
            
            data = parse_resume(text)
            doc_path, filename = create_docx(data)
            
            return send_file(doc_path, as_attachment=True, download_name=filename,
                           mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        except Exception as e:
            flash(f'Error: {str(e)}')
    
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run()
