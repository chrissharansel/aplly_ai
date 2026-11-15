from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.config import settings
from app.database import get_database
from app.schemas import ConfirmProfileRequest, KnowledgeCreate
from app.services.resume_service import extract_resume_text
from app.services.ollama_service import analyze_resume
from app.services.knowledge_service import save_confirmed_profile, list_knowledge, add_knowledge, delete_knowledge

router=APIRouter(prefix="/api",tags=["Resume and Knowledge"])
STORAGE=Path(__file__).resolve().parents[2]/"storage"/"resumes"
ALLOWED={".pdf",".docx"}

@router.post("/resumes/analyze")
async def analyze(file: UploadFile=File(...)):
    filename=Path(file.filename or "resume").name
    ext=Path(filename).suffix.lower()
    if ext not in ALLOWED: raise HTTPException(400,"Upload a PDF or DOCX resume.")
    data=await file.read()
    if not data: raise HTTPException(400,"The uploaded file is empty.")
    if len(data)>settings.max_upload_mb*1024*1024: raise HTTPException(413,f"Maximum upload size is {settings.max_upload_mb} MB.")
    STORAGE.mkdir(parents=True,exist_ok=True)
    rid=str(uuid4()); path=STORAGE/f"{rid}{ext}"; path.write_bytes(data)
    try:
        raw=extract_resume_text(path,ext)
        candidate=await analyze_resume(raw)
    except ValueError as exc:
        path.unlink(missing_ok=True); raise HTTPException(422,str(exc)) from exc
    except Exception as exc:
        path.unlink(missing_ok=True); raise HTTPException(502,f"Analysis failed ({type(exc).__name__}). Check Ollama and the configured model.") from exc
    get_database().resumes.insert_one({"_id":rid,"user_id":"local-user","original_filename":filename,
        "stored_filename":path.name,"status":"pending_review","verified":False})
    return {"resume_id":rid,"filename":filename,"status":"pending_review",
            "extracted_profile":candidate.model_dump(),"notice":"Review and confirm; extracted data is not yet verified."}

@router.post("/profile/confirm")
def confirm(req: ConfirmProfileRequest):
    resume=get_database().resumes.find_one({"_id":req.resume_id,"user_id":"local-user"})
    if not resume: raise HTTPException(404,"Resume record not found.")
    result=save_confirmed_profile(req.profile.model_dump(),req.resume_id)
    get_database().resumes.update_one({"_id":req.resume_id},{"$set":{"status":"confirmed","verified":True}})
    return result

@router.get("/profile")
def profile():
    d=get_database().candidate_profiles.find_one({"_id":"local-user"})
    if not d: return {"profile":None,"verified":False}
    d.pop("_id",None); return d

@router.get("/knowledge")
def knowledge(): return {"items":list_knowledge()}

@router.post("/knowledge")
def create_knowledge(req:KnowledgeCreate):
    return {"saved":True,"id":add_knowledge(req.question,req.answer,req.category,req.reusable)}

@router.delete("/knowledge/{item_id}")
def remove_knowledge(item_id:str):
    if not delete_knowledge(item_id): raise HTTPException(404,"Knowledge item not found.")
    return {"deleted":True}
