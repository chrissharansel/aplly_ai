# ApplyAI — Phase 1 (MongoDB Atlas + local Ollama)

Phase 1 gives you a working foundation:
- React + Vite dashboard
- Python + FastAPI API
- MongoDB Atlas connection
- Local Llama through Ollama
- A minimal LangGraph workflow
- Chrome selected for later Playwright automation
- Human-review-first submission policy

## Architecture

React (5173) → FastAPI (8000) → LangGraph → Ollama (11434)
                               ↘ MongoDB Atlas

The browser automation and actual job-form submission are intentionally not enabled in Phase 1. Phase 3 will add Playwright with your installed Google Chrome. The eventual workflow will stop for your review before submitting.

## Prerequisites

Install:
1. Python 3.11 or 3.12
2. Node.js 20+
3. Google Chrome
4. Ollama
5. A MongoDB Atlas account and a database user

## A. Configure MongoDB Atlas

1. Sign in at https://cloud.mongodb.com/
2. Create a free/shared cluster.
3. Under **Database Access**, create a database user and password.
4. Under **Network Access**, add your current public IP address.
   - For a short local test, you may use `0.0.0.0/0`, but this allows connections from any IP and is not recommended for ongoing use.
5. Select **Connect → Drivers → Python** and copy the connection string.
6. Replace `<password>` with the database user's password. URL-encode special characters in the password.
7. Put the URI in `backend/.env`. Never commit or share this file.

Example:
`mongodb+srv://applyai_user:YOUR_URL_ENCODED_PASSWORD@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0`

The app uses database name `applyai` by default. It creates collections when data is first written.

## B. Install and start Ollama

Install Ollama from https://ollama.com/download

In a terminal:
```bash
ollama pull llama3.1:8b
ollama run llama3.1:8b
```
Once the model is downloaded, exit the chat. Ollama should remain available at `http://localhost:11434`.

Verify:
```bash
curl http://localhost:11434/api/tags
```
Windows PowerShell:
```powershell
Invoke-RestMethod http://localhost:11434/api/tags
```

A 8B model can be memory-intensive on a 16 GB RAM laptop. Close memory-heavy applications if needed. If it is too slow, use a smaller Ollama model and update `OLLAMA_MODEL` in `.env`.

## C. Backend setup

Open terminal in `applyai_phase1_atlas/backend`.

### Windows PowerShell
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `backend/.env` and paste your Atlas URI into `MONGODB_URI`.

Run:
```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### macOS / Linux
```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```
Edit `backend/.env`, then:
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

API docs: http://127.0.0.1:8000/docs

## D. Frontend setup

Open a second terminal in `applyai_phase1_atlas/frontend`.

```bash
npm install
```

Windows PowerShell:
```powershell
Copy-Item .env.example .env
```
macOS/Linux:
```bash
cp .env.example .env
```

Then:
```bash
npm run dev
```

Open http://localhost:5173

## E. Verify Phase 1

1. Visit http://localhost:5173.
2. The dashboard should show API, Atlas and Ollama status.
3. If Atlas shows disconnected, check the URI, database username/password, IP access list and outbound network access.
4. If Ollama is unavailable, start Ollama and confirm the model is pulled.
5. Use the **Test Llama + LangGraph** box. The request runs through a one-node LangGraph workflow and asks your local model to respond.
6. Open http://127.0.0.1:8000/docs to inspect the API.

Useful endpoints:
- `GET /api/health`
- `GET /api/system/status`
- `POST /api/agent/test`
- `GET /api/profile`
- `PUT /api/profile`

## Environment variables

`backend/.env`:
```env
MONGODB_URI=mongodb+srv://...
MONGODB_DATABASE=applyai
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
FRONTEND_ORIGIN=http://localhost:5173
```

## Security notes

- Keep `.env` private. Do not paste Atlas credentials into chat or commit them to Git.
- Restrict Atlas Network Access to your IP rather than leaving `0.0.0.0/0` enabled.
- Use a dedicated least-privilege database user.
- Phase 1 does not store your resume or sensitive personal information yet.
- The future application agent will ask before saving new reusable answers and will require your explicit approval before the final Submit action.
- CAPTCHA, OTP and login verification will remain user-assisted; the agent will not bypass them.
