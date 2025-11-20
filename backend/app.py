import os
import shutil
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, Header
from backend.rag_engine import RAGEngine
from backend.models import TestCaseRequest, TestPlan, SeleniumScriptRequest, SeleniumScriptResponse

app = FastAPI(title="Autonomous QA Agent API")

UPLOAD_DIR = "data/uploads"
HTML_EXTENSIONS = (".html", ".htm")
os.makedirs(UPLOAD_DIR, exist_ok=True)

rag_engine = RAGEngine()

@app.post("/upload-documents")
async def upload_documents(files: List[UploadFile] = File(...)):
    saved_paths = []
    # Clear old uploads to keep it clean for the demo
    # In a real app, we might manage sessions
    for filename in os.listdir(UPLOAD_DIR):
        file_path = os.path.join(UPLOAD_DIR, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
        except Exception as e:
            print(f'Failed to delete {file_path}. Reason: {e}')

    for file in files:
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        saved_paths.append(file_path)
    
    return {"message": f"Successfully uploaded {len(saved_paths)} files", "filenames": [f.filename for f in files]}

@app.post("/build-knowledge-base")
async def build_knowledge_base():
    files = [os.path.join(UPLOAD_DIR, f) for f in os.listdir(UPLOAD_DIR)]

    if not files:
        raise HTTPException(status_code=400, detail="Upload at least one support document and checkout.html before building the knowledge base.")

    html_files = [f for f in files if os.path.splitext(f)[1].lower() in HTML_EXTENSIONS]
    support_files = [f for f in files if os.path.splitext(f)[1].lower() not in HTML_EXTENSIONS]

    if not html_files:
        raise HTTPException(status_code=400, detail="checkout.html (or another HTML file) is required to build the knowledge base.")
    if not support_files:
        raise HTTPException(status_code=400, detail="At least one support document (MD, TXT, JSON, etc.) is required alongside the HTML file.")

    rag_engine.clear_database()
    num_chunks = rag_engine.ingest_documents(files)

    return {"message": "Knowledge Base Built Successfully", "chunks_processed": num_chunks}

@app.post("/generate-test-cases", response_model=TestPlan)
async def generate_test_cases(request: TestCaseRequest, x_api_key: Optional[str] = Header(None)):
    try:
        return rag_engine.generate_test_cases(request.query, api_key=x_api_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate-script", response_model=SeleniumScriptResponse)
async def generate_script(request: SeleniumScriptRequest, x_api_key: Optional[str] = Header(None)):
    try:
        script = rag_engine.generate_selenium_script(request.test_case, request.html_content, api_key=x_api_key)
        return SeleniumScriptResponse(script_code=script)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
