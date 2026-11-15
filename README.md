# ApplyAI — Document-aware Job Application Agent

React + FastAPI + MongoDB Atlas + Ollama + Python tool-calling orchestrator + Playwright.
The workflow uses ordinary Python orchestration; it does not require LangGraph.

## Windows setup

### Backend
```cmd
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```
Edit `backend/.env` with your MongoDB Atlas URI and a long random `SECRET_KEY`.
Then install the Playwright browser:
```cmd
python -m playwright install chromium
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend
Open another terminal:
```cmd
cd frontend
copy .env.example .env
npm install
npm run dev
```
Open http://localhost:5173. Ollama must already be running and the model in `.env` must be installed, for example `ollama pull llama3.1:8b`.

## Document intelligence included

- PDF and DOCX reference-document uploads from the Documents & AI tab, separate from candidate resume confirmation.
- PDF text extraction using PyPDF.
- DOCX paragraph and table extraction using python-docx.
- Scanned PDF OCR using PyMuPDF + Tesseract, automatically detected in PATH and common Windows install folders.
- Text chunking with overlap and lexical retrieval of relevant sections.
- Llama structured resume extraction with JSON mode and long read timeout.
- Original uploaded file, extracted chunks, document metadata, pending profile extraction, summaries and Q&A history stored in MongoDB, scoped to the authenticated user.
- On-demand document summary, cached in MongoDB.
- Document Q&A with actual Ollama function/tool calls. The Python tool dispatcher exposes `search_document`, `get_candidate_profile` and `search_knowledge_base`. Tool outputs are bounded and user-scoped.
- Facts extracted from a resume are not trusted until the user reviews and confirms the profile. Only confirmed profile data is promoted to reusable knowledge.
- Uploaded documents can be deleted with their chunks, summaries and Q&A records.

## OCR note

PyMuPDF, pytesseract and Pillow are installed through `requirements.txt`. Tesseract OCR is a separate Windows application. If a scanned PDF is uploaded, install Tesseract OCR and ensure `tesseract.exe` is in PATH or one of the common Windows installation folders. Normal text PDFs and DOCX files do not require Tesseract.

## Job application agent

JWT registration/login; user-scoped profile and knowledge; URL validation; Playwright Chromium inspection; conservative field mapping; pending user questions; reusable answer storage only after the user supplies the answer; explicit final approval before the submit action; application history.

Login, CAPTCHA, MFA, anti-bot checks, unsupported widgets and multi-step ATS flows may require manual intervention. Do not bypass anti-bot controls. Browser sessions are held in backend memory; a backend restart requires opening the job URL again.

## MongoDB collections

`users`, `resumes`, `documents`, `document_chunks`, `document_qa`, `document_summaries`, `candidate_profiles`, `knowledge_base`, `agent_sessions`, and `applications`.

## API
FastAPI docs: http://127.0.0.1:8000/docs

Important endpoints:
- `POST /api/resumes/analyze`
- `POST /api/documents/upload`
- `GET /api/documents`
- `POST /api/documents/{document_id}/ask`
- `GET /api/documents/{document_id}/history`
- `POST /api/documents/{document_id}/summary`
- `DELETE /api/documents/{document_id}`
- `PUT /api/profile`
- `GET/POST /api/knowledge`
- `POST /api/applications/start`
- `POST /api/agent/sessions/{session_id}/approve-submit`

## Prototype and security limitations

This is a local functional prototype, not universal ATS compatibility or a production deployment. Keep Atlas network access restricted to your own IP, protect `.env`, review all extracted and generated information, and do not allow the agent to answer legal, immigration, demographic or other sensitive declarations without explicit user input. Use HTTPS, rate limits, secure file scanning, encryption-at-rest controls and deployment hardening before exposing it publicly.


### Resume extraction progress
Resume uploads run as background jobs. The profile page polls the authenticated job-status endpoint and displays live backend stages: document extraction, Ollama chunk analysis, and MongoDB persistence. Progress percentages advance as actual resume chunks finish; OCR is reported within the document-reading stage. Job progress is held in backend memory, so an API process restart will stop in-flight jobs.
