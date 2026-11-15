from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pymongo.errors import PyMongoError
from app.config import settings
from app.database import check_mongodb, close_mongodb, get_database
from app.schemas import AgentTestRequest, ProfileUpdate
from app.services.ollama_service import check_ollama
from app.agents import run_agent

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    close_mongodb()

app = FastAPI(
    title="ApplyAI API",
    description="Phase 1 foundation for a personal AI job-application agent.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "ApplyAI API"}

@app.get("/api/system/status")
async def system_status():
    mongo_ok, mongo_message = check_mongodb()
    ollama_ok, ollama_message = await check_ollama()
    return {
        "api": {"ok": True, "message": "FastAPI is running"},
        "mongodb": {"ok": mongo_ok, "message": mongo_message},
        "ollama": {"ok": ollama_ok, "message": ollama_message},
        "agent": {"ok": True, "message": "LangGraph workflow loaded"},
        "browser": {"ok": None, "message": "Chrome automation will be enabled in Phase 3"},
    }

@app.post("/api/agent/test")
async def agent_test(request: AgentTestRequest):
    try:
        answer = await run_agent(request.prompt)
        return {"answer": answer, "model": settings.ollama_model, "orchestrator": "LangGraph"}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Agent request failed: {exc.__class__.__name__}") from exc

@app.get("/api/profile")
async def get_profile():
    try:
        doc = get_database()["user_profiles"].find_one({"_id": "primary"})
        if not doc:
            return {"full_name": "", "email": "", "phone": "", "location": "", "target_role": ""}
        doc.pop("_id", None)
        return doc
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="Could not read profile from MongoDB Atlas") from exc

@app.put("/api/profile")
async def save_profile(profile: ProfileUpdate):
    payload = profile.model_dump()
    payload["updated_at"] = datetime.now(timezone.utc)
    try:
        get_database()["user_profiles"].update_one(
            {"_id": "primary"},
            {"$set": payload},
            upsert=True,
        )
        return {"saved": True, "profile": profile.model_dump()}
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="Could not save profile to MongoDB Atlas") from exc
