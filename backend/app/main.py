from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import check_mongodb, close_mongodb
from app.api.resume import router

@asynccontextmanager
async def lifespan(app:FastAPI):
    yield
    close_mongodb()

app=FastAPI(title="ApplyAI — Resume Intelligence",version="0.2.0",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=settings.allowed_origins,allow_credentials=True,
                   allow_methods=["*"],allow_headers=["*"])
app.include_router(router)

@app.get("/api/health")
def health(): return {"status":"ok","service":"ApplyAI API"}

@app.get("/api/system/status")
def status():
    ok,msg=check_mongodb()
    return {"api":{"ok":True,"message":"FastAPI is running"},
            "mongodb":{"ok":ok,"message":msg},
            "ollama":{"ok":None,"message":f"Configured model: {settings.ollama_model}; checked during resume analysis"},
            "agent":{"ok":True,"message":"Python orchestrator/services ready"},
            "browser":{"ok":None,"message":"Browser automation planned for Phase 3"}}
