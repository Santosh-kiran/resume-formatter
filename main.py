from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
import shutil
import os
from parser import extract_text
from formatter import generate_docx

app = FastAPI()

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

@app.post("/upload")
async def upload_resume(file: UploadFile = File(...)):
    file_path = f"{UPLOAD_DIR}/{file.filename}"
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    extracted_text = extract_text(file_path)
    
    output_file, output_name = generate_docx(extracted_text)
    
    return FileResponse(
        path=output_file,
        filename=output_name,
        media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )