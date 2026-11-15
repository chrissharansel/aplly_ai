# ApplyAI Phase 2 — Resume Intelligence

Runnable starter: React/Vite + FastAPI + MongoDB Atlas + Ollama. It uploads PDF/DOCX, extracts text, asks Ollama for structured candidate data, lets the user review/edit it, and saves only explicitly confirmed information.

## Requirements
Python 3.12+, Node.js 20+, MongoDB Atlas, Ollama. Run `ollama pull llama3.1:8b`.

## Backend (Windows CMD)
```cmd
cd backend
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
copy .env.example .env
```
Edit `.env` with your MongoDB Atlas URI (keep it private), then:
```cmd
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
API docs: http://127.0.0.1:8000/docs

## Frontend (second terminal)
```cmd
cd frontend
npm install
copy .env.example .env
npm run dev
```
Open the Vite URL (usually http://localhost:5173).

## Notes
This is a local single-user prototype (`local-user`). Extracted facts are unverified until confirmed. It does not automate browser applications or submit applications. OCR, authentication, multi-user isolation, malware scanning, and production encryption are not included yet. Restrict Atlas network access to your IP; never commit `.env` or resume files.
