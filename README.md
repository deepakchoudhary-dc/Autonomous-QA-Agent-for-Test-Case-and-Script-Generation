# Autonomous QA Agent

An intelligent, autonomous QA agent capable of constructing a "testing brain" from project documentation and generating Selenium test scripts.

## Features

*   **Knowledge Base Ingestion**: Upload support docs (MD/TXT/JSON/PDF) *and* the checkout HTML (file upload or pasted text). Everything is parsed, chunked, and stored with metadata so snippets always cite their source file.
*   **Test Case + Viewpoint Generation**: Retrieval-Augmented Generation (RAG) produces structured QA viewpoints and grounded test cases; each case carries a `grounded_in` filename.
*   **Selenium Script Generation**: Select a test case and the agent retrieves both documentation and the stored HTML to craft an executable Python Selenium script with explicit waits and selectors that exist in `checkout.html`.

## Project Structure

*   `backend/`: FastAPI application handling the core logic, RAG engine, and LLM interactions.
*   `frontend/`: Streamlit application providing the user interface.
*   `assets/`: Sample project assets (`checkout.html`, `product_specs.md`, etc.).
*   `data/`: Directory for storing uploaded files and the Chroma vector database.
*   `scripts/`: Utility helpers (e.g., `list_models.py` for Gemini model discovery).

## Prerequisites

*   Python 3.10 (Verified)
*   A Google Gemini API Key.

## Setup Instructions

1.  **Clone or open the repo** and ensure you are on Python 3.10.
2.  **Install dependencies**:
    ```powershell
    C:/Users/mrrr7/AppData/Local/Programs/Python/Python310/python.exe -m pip install -r requirements.txt
    ```
3.  **Provide a Gemini API key** either via the UI sidebar or by exporting an env var:
    ```powershell
    $env:GOOGLE_API_KEY="AIza..."
    ```
4.  *(Optional)* Use the helper script to list enabled Gemini models for your key:
    ```powershell
    C:/Users/mrrr7/AppData/Local/Programs/Python/Python310/python.exe scripts/list_models.py
    ```

## How to Run

1.  **Start the Backend**:
    Open a terminal and run:
    ```powershell
    C:/Users/mrrr7/AppData/Local/Programs/Python/Python310/python.exe -m backend.app
    ```
    The API will start at `http://localhost:8000`.

2.  **Start the Frontend**:
    Open a new terminal and run:
    ```powershell
    C:/Users/mrrr7/AppData/Local/Programs/Python/Python310/python.exe -m streamlit run frontend/app.py
    ```
    The UI will open in your browser at `http://localhost:8501`.

## Deploy on Render

### FastAPI Backend (Web Service)
1.  Create a **Python Web Service** that points to this repo.
2.  **Build command** (Render fills this automatically):
    ```bash
    pip install -r requirements.txt
    ```
3.  **Start command** (requires `gunicorn`, already listed in `requirements.txt`):
    ```bash
    gunicorn -k uvicorn.workers.UvicornWorker backend.app:app --bind 0.0.0.0:$PORT --workers 2
    ```
4.  Set env vars under *Environment* → *Secret Files / Variables*:
    - `GOOGLE_API_KEY=<your key>`
    - (Optional) `CHROMA_PERSIST_DIR=/opt/render/project/.chroma`
5.  Choose a **Disk** (1–5 GB) if you want the vector store to persist between deploys. Otherwise it will rebuild per deploy.

### Streamlit Frontend (Second Web Service)
1.  Create another Python Web Service (or a Static Site that shells into Streamlit) referencing the same repo.
2.  **Build command**:
    ```bash
    pip install -r requirements.txt
    ```
3.  **Start command**:
    ```bash
    streamlit run frontend/app.py --server.port $PORT --server.address 0.0.0.0
    ```
4.  Under *Environment*, point `BACKEND_URL` to the backend Render URL (e.g., `https://qa-agent-backend.onrender.com`).

### Validation Checklist
* Confirm both services show an open port in the Render dashboard after deploy.
* Hit the backend `/health` endpoint (or `/docs`) to verify FastAPI is responding before hooking the UI.
* If deploy fails, inspect the **Logs** tab—most issues stem from missing packages or incorrect start commands.

### CORS / Frontend Integration
Set `BACKEND_ALLOWED_ORIGINS` on your backend service to control which origins can access the API. For a Streamlit frontend hosted on Render, set this to the Streamlit service domain (for example `https://my-streamlit-app.onrender.com`). For quick testing you can set `*`, but it's not recommended for production.

Example env var value for Render:
```
BACKEND_ALLOWED_ORIGINS=https://my-streamlit-app.onrender.com
```

The backend exposes a `/health` endpoint for quick verification after deploy.

## Push to GitHub (Repo: https://github.com/deepakchoudhary-dc/Autonomous-QA-Agent-for-Test-Case-and-Script-Generation)

If you want to upload your local code to that GitHub repo, use one of the methods below. Replace <USERNAME> and <TOKEN> accordingly.

Option A — HTTPS (recommended with a token):
```powershell
git init
git add .
git commit -m "Initial commit: Autonomous QA Agent"
git branch -M main
git remote add origin https://github.com/deepakchoudhary-dc/Autonomous-QA-Agent-for-Test-Case-and-Script-Generation.git
# Push — will prompt for credentials unless you embed PAT (NOT recommended). To use PAT:
# git push https://<USERNAME>:<TOKEN>@github.com/deepakchoudhary-dc/Autonomous-QA-Agent-for-Test-Case-and-Script-Generation.git main
git push -u origin main
```

Option B — SSH (recommended if you use an SSH key):
```powershell
git init
git add .
git commit -m "Initial commit: Autonomous QA Agent"
git remote add origin git@github.com:deepakchoudhary-dc/Autonomous-QA-Agent-for-Test-Case-and-Script-Generation.git
git branch -M main
git push -u origin main
```

Option C — Create/Push using the GitHub CLI (gh):
```powershell
gh auth login
gh repo set-default deepakchoudhary-dc/Autonomous-QA-Agent-for-Test-Case-and-Script-Generation
git init
git add .
git commit -m "Initial commit: Autonomous QA Agent"
git branch -M main
git remote add origin https://github.com/deepakchoudhary-dc/Autonomous-QA-Agent-for-Test-Case-and-Script-Generation.git
gh repo sync
git push -u origin main
```

Note: if the remote repo already contains content, you can either pull first or force push (not recommended for collaborative repos). Use:
```powershell
# Quick pull path to merge
git pull origin main --allow-unrelated-histories
git push origin main
```

## Usage Guide

### Phase 1: Build Knowledge Base
1.  Open the **Knowledge Base** tab.
2.  Upload 3–5 support docs (examples live in `assets/`).
3.  Upload `checkout.html` **or** paste its contents in the provided textarea.
4.  Click **Build Knowledge Base**. The backend verifies that both support docs and HTML are present before chunking/ingesting.

### Phase 2: Generate Test Cases & Viewpoints
1.  Switch to **Test Case Generation**.
2.  Provide a request such as `Generate all positive and negative test cases for the discount code feature.`
3.  Click **Generate Test Cases**.
4.  Review the resulting **Test Viewpoints** list (coverage perspectives) and the structured table of grounded test cases. Use the JSON expander for raw output.

### Phase 3: Generate Selenium Script
1.  Visit **Script Generation**.
2.  Pick any of the previously generated cases.
3.  Click **Generate Script** to receive a runnable Selenium script (Chrome driver, explicit waits, selectors tied to the uploaded HTML).
4.  Download or copy the script for your test suite.

## Included Support Documents

*   **`assets/checkout.html`** – canonical E-Shop checkout UI used by Selenium scripts.
*   **`assets/product_specs.md`** – discount codes, shipping policies, payment rules.
*   **`assets/ui_ux_guide.txt`** – UX color, validation, and layout requirements.
*   **`assets/api_endpoints.json`** – example backend interfaces for coupons/orders.

Feel free to replace these with your own documents before rebuilding the knowledge base.


## Troubleshooting

*   **Model errors** – run `scripts/list_models.py` to confirm which Gemini models your key can access, then update `backend/rag_engine.py` if needed.
*   **HTML not found** – ensure you uploaded/pasted `checkout.html` before building the knowledge base; the backend will reject ingestion otherwise.
*   **Selectors failing** – re-run Phase 1 after changing the HTML so the vector store stays in sync with the UI markup.
