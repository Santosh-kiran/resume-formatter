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
app.secret_key = os.environ.get('SECRET_KEY', 'cloud-brfv1-secret')

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>BRFv1.0 Resume Formatter</title>
    <style>
        *{margin:0;padding:0;box-sizing:border-box;}
        body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px;}
        .container{background:rgba(255,255,255,0.95);backdrop-filter:blur(20px);border-radius:24px;padding:3rem;max-width:550px;width:100%;box-shadow:0 25px 50px rgba(0,0,0,0.15);text-align:center;}
        h1{font-size:2.5rem;font-weight:800;background:linear-gradient(135deg,#667eea,#764ba2);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:0.5rem;}
        p{color:#64748b;font-size:1.1rem;margin-bottom:2rem;}
        .alert{padding:1rem 1.5rem;border-radius:12px;margin:0 0 2rem 0;background:#fef2f2;color:#dc2626;border:1px solid #fecaca;}
        .upload-zone{border:3px dashed #cbd5e1;border-radius:16px;padding:3rem 2rem;cursor:pointer;transition:all 0.3s;background:#f8fafc;position:relative;}
        .upload-zone:hover{border-color:#667eea;background:#eff6ff;}
        .upload-zone.highlight,.upload-zone.has-file{border-color:#10b981;background:#ecfdf5;}
        .upload-zone i{font-size:4rem;color:#94a3b8;margin-bottom:1rem;display:block;}
        .upload-zone p{color:#64748b;font-size:1.1rem;margin-bottom:1rem;}
        .upload-zone span{font-weight:600;color:#475569;}
        #fileInfo{margin-top:1.5rem;padding-top:1.5rem;border-top:1px solid #e2e8f0;}
        #fileName{display:block;font-weight:600;color:#1e293b;margin-bottom:0.25rem;}
        button{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:white;border:none;padding:1.25rem 3rem;border-radius:50px;font-size:1.1rem;font-weight:600;cursor:pointer;width:100%;transition:all 0.3s;margin-top:1.5rem;}
        button:hover{transform:translateY(-2px);box-shadow:0 20px 40px rgba(102,126,234,0.4);}
        .features-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:1.5rem;margin-top:3rem;padding-top:2rem;border-top:1px solid #e2e8f0;}
        .feature{text-align:center;padding:1.5rem;}
        .feature i{font-size:2.5rem;background:linear-gradient(135deg,#667eea,#764ba2);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:1rem;display:block;}
        .feature h4{color:#1e293b;margin-bottom:0.5rem;font-size:1.1rem;}
        input[type=file]{position:absolute;left:-9999px;}
    </style>
</head>
<body>
    <div class="container">
        <h1>BRFv1.0 Formatter</h1>
        <p>Upload PDF/DOCX → Get perfect Beeline Resume Format instantly</p>
        
        {% with messages=get_flashed_messages() %}
            {% if messages %}
                <div class="alert">{{ messages[0] }}</div>
            {% endif %}
        {% endwith %}
        
        <form method="POST" enctype="multipart/form-data">
            <div class="upload-zone" id="uploadZone">
                <i>📤</i>
                <p>Drop resume or <span>click to browse</span></p>
                <input type="file" id="resume" name="resume" accept=".pdf,.docx,.doc" required>
                <div id="fileInfo"><span id="fileName">No file selected</span></div>
            </div>
            <button type="submit">✨ Convert to BRFv1.0</button>
        </form>
        
        <div class="features-grid">
            <div class="feature"><i>📄</i><h4>Any Format</h4><p>PDF, DOCX, DOC</p></div>
            <div class="feature"><i>📐</i><h4>Perfect Format</h4><p>Times New Roman 10pt</p></div>
            <div class="feature"><i>✅</i><h4>BRFv1.0 Rules</h4><p>100% Spec Compliant</p></div>
        </div>
    </div>
    <script>
        const zone=document.getElementById('uploadZone'),fileInput=document.getElementById('resume'),fileName=document.getElementById('fileName');
        ['dragenter','dragover','dragleave','drop'].forEach(e=>zone.addEventListener(e,ev=>{ev.preventDefault();ev.stopPropagation();}));
        ['dragenter','dragover'].forEach(e=>zone.addEventListener(e,()=>zone.classList.add('highlight'),false));
        ['dragleave','drop'].forEach(e=>zone.addEventListener(e,()=>zone.classList.remove('highlight'),false));
        zone.addEventListener('drop',e=>{const files=e.dataTransfer.files;handleFiles(files);});
        zone.addEventListener('click',()=>fileInput.click());
        fileInput.onchange=e=>{const file=e.target.files[0];if(file){fileName.textContent=file.name;zone.classList.add('has-file');}};
        function handleFiles(files){if(files[0]){fileName.textContent=files[0].name;zone.classList.add('has-file');}}
    </script>
</body>
</html>
'''

def extract_text(file_path):
    """Extract raw text preserving exact wording"""
    ext = os.path.splitext(file_path)[1].lower()
    text = ""
    if ext == '.pdf' and pdfplumber:
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text: text += page_text + "\n"
        except: pass
    elif ext == '.docx':
        text = docx2txt.process(file_path)
    return text.strip()

def parse_resume(text):
    """Parse into BRFv1.0 structure - NO rewriting, exact content"""
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    # Extract name (first prominent line)
    name = lines[0] if lines else "Candidate Name"
    name_parts = name.split()
    first_name = name_parts[0] if name_parts else "First"
    last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else "Last"
    
    # Section detection (preserves ALL original content)
    sections = {'summary':[], 'technical_skills':[], 'education':[], 'projects':[]}
    current_section = None
    current_project = []
    
    keywords = {
        'summary': ['summary', 'profile', 'objective', 'overview'],
        'skills': ['skill', 'technical', 'technology', 'technologies', 'tools'],
        'education': ['education', 'degree', 'university', 'college', 'academic'],
        'experience': ['experience', 'work', 'professional', 'project', 'company']
    }
    
    for line in lines:
        line_lower = line.lower()
        
        # Detect section headers
        if any(kw in line_lower for kw in keywords['summary']): current_section = 'summary'
        elif any(kw in line_lower for kw in keywords['skills']): current_section = 'technical_skills'
        elif any(kw in line_lower for kw in keywords['education']): current_section = 'education'
        elif any(kw in line_lower for kw in keywords['experience']):
            if current_project: 
                sections['projects'].append(' '.join(current_project))
                current_project = []
            current_section = 'projects'
        
        if current_section and line:
            if current_section == 'projects':
                current_project.append(line)
            else:
                sections[current_section].append(line)
    
    # Add final project
    if current_project:
        sections['projects'].append(' '.join(current_project))
    
    return {
        'name': name,
        'first_name': first_name,
        'last_name': last_name,
        'summary': sections['summary'],
        'technical_skills': sections['technical_skills'],
        'education': sections['education'],
        'projects': sections['projects']
    }

def create_brfv1_doc(parsed_data):
    """Create EXACT BRFv1.0 .docx per all specifications"""
    doc = Document()
    
    # GLOBAL: Times New Roman 10pt
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Times New Roman'
    font.size = Pt(10)
    
    # 1. HEADER: Candidate Name (CENTERED)
    name_p = doc.add_paragraph(parsed_data['name'])
    name_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    name_p.paragraph_format.space_after = Pt(0)
    
    # 2. Summary header (BOLD)
    summary_title = doc.add_paragraph('Summary :')
    summary_title.runs[0].bold = True
    summary_title.paragraph_format.space_after = Pt(0)
    
    # 3. Summary bullets (BRF format • exact wording)
    for item in parsed_data['summary']:
        bullet_p = doc.add_paragraph(f"• {item}")
        bullet_p.paragraph_format.space_after = Pt(0)
        bullet_p.paragraph_format.space_before = Pt(0)
    
    doc.add_paragraph()  # REQUIRED: one line gap after Summary
    
    # 4. TECHNICAL SKILLS (paragraph format NO bullets)
    skills_title = doc.add_paragraph('Technical Skills :')
    skills_title.runs[0].bold = True
    for skill in parsed_data['technical_skills']:
        skills_p = doc.add_paragraph(skill)
        skills_p.paragraph_format.space_after = Pt(0)
    
    doc.add_paragraph()  # Gap
    
    # 5. EDUCATION (paragraph format NO bullets, includes certifications)
    edu_title = doc.add_paragraph('Education :')
    edu_title.runs[0].bold = True
    for edu_item in parsed_data['education']:
        edu_p = doc.add_paragraph(edu_item)
        edu_p.paragraph_format.space_after = Pt(0)
    
    doc.add_paragraph()  # REQUIRED: one line gap after Education
    
    # 6. PROFESSIONAL EXPERIENCE (STRICT FORMAT)
    exp_title = doc.add_paragraph('Professional Experience :')
    exp_title.runs[0].bold = True
    
    for project in parsed_data['projects']:
        # Line 1: Company Name, Location, Duration (first line of project)
        first_line = project.split('\n')[0] if '\n' in project else project
        project_header = doc.add_paragraph(first_line)
        project_header.paragraph_format.space_after = Pt(0)
        
        # Project bullets (BRF format • exact wording)
        project_lines = project.split('\n')[1:] if '\n' in project else []
        for line in project_lines:
            if line.strip():
                bullet_p = doc.add_paragraph(f"• {line.strip()}")
                bullet_p.paragraph_format.space_after = Pt(0)
        
        doc.add_paragraph()  # REQUIRED: one line gap after EACH project
    
    # FILENAME RULE: First Last.docx
    filename = f"{parsed_data['first_name']} {parsed_data['last_name']}.docx"
    path = f"/tmp/{filename}"
    doc.save(path)
    return path, filename

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        file = request.files.get('resume')
        if not file or not file.filename:
            flash('Please select a resume file')
            return render_template_string(HTML_TEMPLATE)
        
        if not file.filename.lower().endswith(('.pdf', '.docx', '.doc')):
            flash('Only PDF, DOCX, DOC supported')
            return render_template_string(HTML_TEMPLATE)
        
        try:
            # Save temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf' if file.filename.lower().endswith('.pdf') else '.docx') as tmp:
                file.save(tmp.name)
                file_path = tmp.name
            
            # Process EXACTLY per BRFv1.0
            raw_text = extract_text(file_path)
            parsed_data = parse_resume(raw_text)
            doc_path, filename = create_brfv1_doc(parsed_data)
            
            # Cleanup
            os.unlink(file_path)
            
            # Download
            return send_file(doc_path, 
                           as_attachment=True,
                           download_name=filename,
                           mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
            
        except Exception as e:
            if os.path.exists(file_path): os.unlink(file_path)
            flash(f'Processing error: {str(e)[:100]}')
    
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(debug=False)
