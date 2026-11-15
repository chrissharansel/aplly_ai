from datetime import datetime, timezone
from bson import ObjectId
from app.database import get_database

def save_confirmed_profile(profile: dict, resume_id: str):
    db = get_database()
    now = datetime.now(timezone.utc)
    db.candidate_profiles.update_one({"_id": "local-user"},
        {"$set": {"profile": profile, "verified": True, "resume_id": resume_id, "updated_at": now}}, upsert=True)
    docs = []
    for key in ("full_name", "email", "phone", "location", "headline", "summary"):
        if profile.get(key):
            docs.append({"user_id":"local-user","category":key,"question":f"Candidate {key.replace('_',' ')}",
                         "answer":profile[key],"source":"user_confirmed_resume","verified":True,"reusable":True,"updated_at":now})
    for skill in profile.get("skills", []):
        if skill:
            docs.append({"user_id":"local-user","category":"skill","question":"Candidate skill","answer":skill,
                         "source":"user_confirmed_resume","verified":True,"reusable":True,"updated_at":now})
    for d in docs:
        db.knowledge_base.update_one({k:d[k] for k in ("user_id","category","question","answer")},{"$set":d},upsert=True)
    return {"saved":True,"knowledge_items_saved":len(docs)}

def list_knowledge():
    items=list(get_database().knowledge_base.find({"user_id":"local-user","verified":True}).sort("updated_at",-1).limit(200))
    for x in items:
        x["id"]=str(x.pop("_id")); x.pop("user_id",None)
    return items

def add_knowledge(question, answer, category, reusable):
    d={"user_id":"local-user","question":question,"answer":answer,"category":category,"source":"user_entered",
       "verified":True,"reusable":reusable,"updated_at":datetime.now(timezone.utc)}
    return str(get_database().knowledge_base.insert_one(d).inserted_id)

def delete_knowledge(item_id):
    if not ObjectId.is_valid(item_id): return False
    return get_database().knowledge_base.delete_one({"_id":ObjectId(item_id),"user_id":"local-user"}).deleted_count > 0
