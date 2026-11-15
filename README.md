# ApplyAI — Integrated Job Application Agent
React + FastAPI + MongoDB + Ollama/Llama + Playwright + Python state machine.

## Run on Windows
Backend CMD:
```cmd
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```
Edit `.env` with your MongoDB Atlas URI and a long random SECRET_KEY. Then:
```cmd
python -m playwright install chromium
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
Frontend second CMD:
```cmd
cd frontend
copy .env.example .env
npm install
npm run dev
```
Open http://localhost:5173. Ensure Ollama is running and `ollama pull llama3.1:8b` has completed. API docs: http://127.0.0.1:8000/docs.

## Included end-to-end modules
JWT registration/login; PDF/DOCX resume parsing and Llama extraction; editable/confirmed candidate profile; user-scoped MongoDB knowledge; job URL validation; Playwright Chromium navigation and visible form inspection; conservative deterministic field mapping; user questions for unknown fields; memory persistence; pause state; review and explicit approval gate; submission attempt and application history.

## Important limitations
This is an integrated functional prototype, not universal ATS compatibility. It handles common visible text inputs/selects; complex widgets, multi-step ATS flows, file upload fields, CAPTCHA, MFA and login need manual handling. Never bypass anti-bot protections. Browser contexts live in backend memory; a backend restart requires reopening the URL. Scanned PDF OCR and semantic vector search are not included. Review every field before approving submission. Use HTTPS, restrict Atlas IP access, protect `.env`, and add production hardening before public deployment. The agent never submits without the separate approval endpoint.
