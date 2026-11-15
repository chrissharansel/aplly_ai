from contextlib import asynccontextmanager
from datetime import datetime,timezone
from uuid import uuid4
from pathlib import Path
from fastapi import FastAPI,HTTPException,Depends,UploadFile,File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel,EmailStr,Field
from app.config import settings
from app.db import db,ping,init,close
from app.security import user,hashpw,checkpw,token
from app.llm import resume_extract
from app.browser import inspect,fill,enter_answer,submit,validate
from pypdf import PdfReader
from docx import Document
from bson import ObjectId

@asynccontextmanager
async def lifespan(app):
 try:init()
 except Exception:pass
 yield;close()
app=FastAPI(title='ApplyAI Autonomous Job Application Agent',version='1.0',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=settings.origins,allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
def now():return datetime.now(timezone.utc)
class Register(BaseModel):email:EmailStr;password:str=Field(min_length=8);full_name:str
class Login(BaseModel):email:EmailStr;password:str
class ProfileSave(BaseModel):profile:dict;resume_id:str|None=None
class Knowledge(BaseModel):question:str;answer:str;category:str='general';reusable:bool=True
class Job(BaseModel):url:str
class Answer(BaseModel):answer:str;save_for_future:bool=True;reusable:bool=True
class Approval(BaseModel):approved:bool
@app.get('/api/health')
def health():return {'status':'ok'}
@app.get('/api/system/status')
def status():
 ok,msg=ping();return {'api':{'ok':True,'message':'FastAPI running'},'mongodb':{'ok':ok,'message':msg},'ollama':{'ok':None,'message':settings.ollama_model+' configured'},'browser':{'ok':None,'message':'Playwright Chromium required'}}
@app.post('/api/auth/register')
def register(x:Register):
 email=x.email.lower()
 if db().users.find_one({'email':email}):raise HTTPException(409,'Email already registered')
 uid=str(uuid4());db().users.insert_one({'_id':uid,'email':email,'full_name':x.full_name,'password_hash':hashpw(x.password),'created_at':now()})
 return {'access_token':token(uid),'user':{'id':uid,'email':email,'full_name':x.full_name}}
@app.post('/api/auth/login')
def login(x:Login):
 u=db().users.find_one({'email':x.email.lower()})
 if not u or not checkpw(x.password,u['password_hash']):raise HTTPException(401,'Incorrect email or password')
 return {'access_token':token(u['_id']),'user':{'id':u['_id'],'email':u['email'],'full_name':u['full_name']}}
@app.post('/api/resumes/analyze')
async def upload(file:UploadFile=File(...),u=Depends(user)):
 name=Path(file.filename or 'resume').name;ext=Path(name).suffix.lower()
 if ext not in ('.pdf','.docx'):raise HTTPException(400,'PDF or DOCX only')
 raw=await file.read()
 if not raw or len(raw)>settings.max_upload_mb*1024*1024:raise HTTPException(413,'Empty file or upload size limit exceeded')
 folder=Path(__file__).resolve().parents[1]/'storage'/'resumes';folder.mkdir(parents=True,exist_ok=True);rid=str(uuid4());path=folder/(u['id']+'_'+rid+ext);path.write_bytes(raw)
 try:
  if ext=='.pdf':text='\n'.join(p.extract_text() or '' for p in PdfReader(str(path)).pages)
  else:
   doc=Document(str(path));text='\n'.join([p.text for p in doc.paragraphs]+[' | '.join(c.text for c in r.cells) for t in doc.tables for r in t.rows])
  if not text.strip():raise ValueError('No readable text; scanned PDF OCR is not included')
  data=await resume_extract(text)
 except Exception as e:
  path.unlink(missing_ok=True);raise HTTPException(422,'Resume analysis failed: '+str(e))
 db().resumes.insert_one({'_id':rid,'user_id':u['id'],'filename':name,'path':str(path),'verified':False,'status':'pending_review','created_at':now()})
 return {'resume_id':rid,'profile':data,'verified':False}
@app.get('/api/profile')
def get_profile(u=Depends(user)):
 d=db().candidate_profiles.find_one({'user_id':u['id']});return {'profile':d.get('profile') if d else None,'verified':bool(d and d.get('verified'))}
@app.put('/api/profile')
def save_profile(x:ProfileSave,u=Depends(user)):
 if x.resume_id and not db().resumes.find_one({'_id':x.resume_id,'user_id':u['id']}):raise HTTPException(404,'Resume not found')
 db().candidate_profiles.update_one({'user_id':u['id']},{'$set':{'profile':x.profile,'verified':True,'updated_at':now()}},upsert=True)
 if x.resume_id:db().resumes.update_one({'_id':x.resume_id},{'$set':{'verified':True,'status':'confirmed'}})
 return {'saved':True,'verified':True}
@app.get('/api/knowledge')
def list_knowledge(u=Depends(user)):
 a=list(db().knowledge_base.find({'user_id':u['id']}).sort('updated_at',-1).limit(300))
 for x in a:x['id']=str(x.pop('_id'));x.pop('user_id',None)
 return {'items':a}
@app.post('/api/knowledge')
def add_knowledge(x:Knowledge,u=Depends(user)):
 d=x.model_dump();d.update({'user_id':u['id'],'verified':True,'source':'user','updated_at':now()});r=db().knowledge_base.insert_one(d);return {'saved':True,'id':str(r.inserted_id)}
@app.delete('/api/knowledge/{iid}')
def del_knowledge(iid:str,u=Depends(user)):
 if not ObjectId.is_valid(iid) or not db().knowledge_base.delete_one({'_id':ObjectId(iid),'user_id':u['id']}).deleted_count:raise HTTPException(404,'Knowledge item not found')
 return {'deleted':True}
def profile(uid):
 d=db().candidate_profiles.find_one({'user_id':uid,'verified':True});return d.get('profile',{}) if d else {}
def value_for(label,p,uid):
 q=label.lower();full=p.get('full_name','')
 pairs=[(('first name','given name'),full.split()[0] if full else ''),(('last name','surname'),full.split()[-1] if full else ''),(('full name','your name'),full),(('email',),p.get('email','')),(('phone','mobile'),p.get('phone','')),(('city','location'),p.get('location',''))]
 for keys,v in pairs:
  if v and any(k in q for k in keys):return v
 for k in db().knowledge_base.find({'user_id':uid,'verified':True,'reusable':True}):
  if q.strip() and (q in k.get('question','').lower() or k.get('question','').lower() in q):return k.get('answer','')
 return ''
@app.post('/api/applications/start')
async def start(x:Job,u=Depends(user)):
 try:validate(x.url)
 except Exception as e:raise HTTPException(400,str(e))
 sid=str(uuid4());db().agent_sessions.insert_one({'_id':sid,'user_id':u['id'],'url':x.url,'status':'starting','created_at':now(),'updated_at':now(),'pending_questions':[]})
 try:obs=await inspect(sid,x.url)
 except Exception as e:db().agent_sessions.update_one({'_id':sid},{'$set':{'status':'failed','error':str(e)}});raise HTTPException(502,'Browser inspection failed: '+str(e))
 p=profile(u['id']);tofill=[];pending=[]
 for f in obs['fields']:
  label=f.get('label') or f.get('name') or f.get('placeholder') or ''
  if f['tag']=='button' or f.get('type') in ('submit','button','file','checkbox','radio','password'):continue
  v=value_for(label,p,u['id'])
  if v:tofill.append({'index':f['index'],'value':v})
  elif f.get('required') or label:pending.append({'id':str(uuid4()),'field_index':f['index'],'question':label or 'Please provide a value','status':'waiting'})
 result=await fill(sid,tofill) if tofill else [];app_id=str(uuid4());status='waiting_for_user' if pending else 'ready_for_review'
 db().applications.insert_one({'_id':app_id,'user_id':u['id'],'session_id':sid,'url':x.url,'job_title':obs['title'],'status':'In Progress','created_at':now()})
 db().agent_sessions.update_one({'_id':sid},{'$set':{'status':status,'application_id':app_id,'job':obs,'observed_fields':obs['fields'],'filled_fields':result,'pending_questions':pending,'updated_at':now()}})
 return session_data(u['id'],sid)
def session_data(uid,sid):
 d=db().agent_sessions.find_one({'_id':sid,'user_id':uid})
 if not d:raise HTTPException(404,'Session not found')
 d['id']=d.pop('_id');return d
@app.get('/api/agent/sessions/{sid}')
def get_session(sid:str,u=Depends(user)):return session_data(u['id'],sid)
@app.post('/api/agent/sessions/{sid}/answer/{qid}')
async def answer(sid:str,qid:str,x:Answer,u=Depends(user)):
 d=db().agent_sessions.find_one({'_id':sid,'user_id':u['id']});q=next((a for a in d.get('pending_questions',[]) if a['id']==qid),None) if d else None
 if not q:raise HTTPException(404,'Pending question not found')
 try:await enter_answer(sid,q['field_index'],x.answer)
 except Exception as e:raise HTTPException(409,'Could not enter answer; manual intervention required: '+str(e))
 db().agent_sessions.update_one({'_id':sid,'pending_questions.id':qid},{'$set':{'pending_questions.$.status':'answered','pending_questions.$.answer':x.answer,'updated_at':now()}})
 if x.save_for_future:db().knowledge_base.insert_one({'user_id':u['id'],'question':q['question'],'answer':x.answer,'category':'application_question','verified':True,'reusable':x.reusable,'source':'user','updated_at':now()})
 fresh=db().agent_sessions.find_one({'_id':sid});remaining=any(a['status']=='waiting' for a in fresh['pending_questions']);st='waiting_for_user' if remaining else 'ready_for_review'
 db().agent_sessions.update_one({'_id':sid},{'$set':{'status':st,'updated_at':now()}});db().applications.update_one({'_id':d['application_id']},{'$set':{'status':'Waiting for User Input' if remaining else 'Ready for Review'}})
 return session_data(u['id'],sid)
@app.post('/api/agent/sessions/{sid}/approve-submit')
async def approve(sid:str,x:Approval,u=Depends(user)):
 d=db().agent_sessions.find_one({'_id':sid,'user_id':u['id']})
 if not d:raise HTTPException(404,'Session not found')
 if not x.approved:raise HTTPException(400,'Explicit approval required')
 if d['status']!='ready_for_review':raise HTTPException(409,'Resolve pending questions before approval')
 try:res=await submit(sid);st='Submitted'
 except Exception as e:
  db().agent_sessions.update_one({'_id':sid},{'$set':{'status':'requires_manual_intervention','error':str(e)}});db().applications.update_one({'_id':d['application_id']},{'$set':{'status':'Requires Manual Intervention','error':str(e)}});raise HTTPException(409,str(e))
 db().agent_sessions.update_one({'_id':sid},{'$set':{'status':'submitted','submission_result':res,'updated_at':now()}});db().applications.update_one({'_id':d['application_id']},{'$set':{'status':st,'submission_result':res,'updated_at':now()}});return session_data(u['id'],sid)
@app.get('/api/applications')
def history(u=Depends(user)):
 a=list(db().applications.find({'user_id':u['id']}).sort('created_at',-1).limit(200))
 for x in a:x['id']=x.pop('_id')
 return {'items':a}
