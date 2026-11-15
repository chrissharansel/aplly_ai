from contextlib import asynccontextmanager
import asyncio
from datetime import datetime,timezone
from uuid import uuid4
from pathlib import Path
from fastapi import FastAPI,HTTPException,Depends,UploadFile,File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel,EmailStr,Field
from app.config import settings
from app.db import db,ping,init,close
from app.security import user,hashpw,checkpw,token
from app.llm import resume_extract, ask
from app.document_intelligence.processor import extract_document
from app.document_intelligence.summarizer import summarize_chunks
from app.agents import answer_document_question
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

# Resume extraction jobs expose real backend stages to the React UI.
RESUME_JOBS: dict[str, dict] = {}


def _set_resume_job(job_id: str, **updates):
 job = RESUME_JOBS.get(job_id)
 if job is not None:
  job.update(updates)


async def _run_resume_job(job_id: str, raw: bytes, name: str, ext: str, content_type: str, user_id: str):
 try:
  _set_resume_job(job_id, status='running', stage='extracting', percent=8,
                  message='Reading your document and extracting text…',
                  steps=[{'label':'Upload received','status':'done'},
                         {'label':'Read PDF / Word content','status':'active'},
                         {'label':'Analyse resume with Ollama','status':'waiting'},
                         {'label':'Save document and profile to MongoDB','status':'waiting'}])
  extracted = await asyncio.to_thread(extract_document, raw, ext)
  if not extracted.get('text', '').strip():
   raise ValueError('No readable text could be extracted from this document.')

  _set_resume_job(job_id, stage='analysing', percent=25,
                  message=f"Extracted {len(extracted['text']):,} characters in {len(extracted['chunks'])} chunks. Analysing with {settings.ollama_model}…",
                  steps=[{'label':'Upload received','status':'done'},
                         {'label':'Read PDF / Word content','status':'done'},
                         {'label':'Analyse resume with Ollama','status':'active'},
                         {'label':'Save document and profile to MongoDB','status':'waiting'}],
                  document_stats={'pages':extracted['page_count'], 'characters':len(extracted['text']), 'chunks':len(extracted['chunks']), 'method':extracted['extraction_method']})

  async def report_chunk(index, total):
   # Reserve 25–82% for model extraction; this reflects actual completed chunks.
   percent = 25 + int((index / max(total, 1)) * 57)
   _set_resume_job(job_id, percent=percent, message=f'AI is analysing resume section {index} of {total}…',
                   current_chunk=index, total_chunks=total)

  data = await resume_extract(extracted['text'], progress_callback=report_chunk)
  _set_resume_job(job_id, stage='saving', percent=88,
                  message='AI extraction complete. Saving document, chunks and candidate profile to MongoDB…',
                  steps=[{'label':'Upload received','status':'done'},
                         {'label':'Read PDF / Word content','status':'done'},
                         {'label':'Analyse resume with Ollama','status':'done'},
                         {'label':'Save document and profile to MongoDB','status':'active'}])

  rid = str(uuid4())
  doc_id = str(uuid4())
  db().documents.insert_one({
   '_id':doc_id,'user_id':user_id,'resume_id':rid,'filename':name,
   'extension':ext,'mime_type':content_type,'document_type':'resume','file_data':raw,
   'page_count':extracted['page_count'],'title':extracted['title'],
   'extraction_method':extracted['extraction_method'],
   'character_count':len(extracted['text']),'chunk_count':len(extracted['chunks']),
   'summary':None,'profile_extraction':data,'verified':False,'created_at':now()
  })
  chunk_docs=[{'user_id':user_id,'document_id':doc_id,'chunk_index':i,'text':chunk,'created_at':now()} for i,chunk in enumerate(extracted['chunks'])]
  if chunk_docs:
   db().document_chunks.insert_many(chunk_docs)
  db().resumes.insert_one({'_id':rid,'user_id':user_id,'document_id':doc_id,'filename':name,
                           'verified':False,'status':'pending_review',
                           'extraction_method':extracted['extraction_method'],'created_at':now()})
  result={'resume_id':rid,'document_id':doc_id,'filename':name,'profile':data,'verified':False,
          'document':{'page_count':extracted['page_count'],'character_count':len(extracted['text']),
                      'chunk_count':len(extracted['chunks']),'extraction_method':extracted['extraction_method']},
          'notice':'Document stored. Review and confirm extracted candidate information before it becomes trusted knowledge.'}
  _set_resume_job(job_id, status='completed', stage='completed', percent=100,
                  message='Resume analysis and MongoDB storage completed. Review your extracted profile.',
                  steps=[{'label':'Upload received','status':'done'},
                         {'label':'Read PDF / Word content','status':'done'},
                         {'label':'Analyse resume with Ollama','status':'done'},
                         {'label':'Save document and profile to MongoDB','status':'done'}],
                  result=result, completed_at=now().isoformat())
 except Exception as exc:
  import logging
  logging.exception('Resume analysis job failed')
  _set_resume_job(job_id, status='failed', stage='failed', percent=100,
                  message=f'{type(exc).__name__}: {str(exc) or repr(exc)}', error=str(exc) or repr(exc))


@app.post('/api/resumes/analyze')
async def upload(file:UploadFile=File(...),u=Depends(user)):
 name=Path(file.filename or 'resume').name
 ext=Path(name).suffix.lower()
 if ext not in ('.pdf','.docx'):
  raise HTTPException(400,'PDF or DOCX only')
 raw=await file.read()
 if not raw or len(raw)>settings.max_upload_mb*1024*1024:
  raise HTTPException(413,'Empty file or upload size limit exceeded')
 job_id=str(uuid4())
 RESUME_JOBS[job_id]={'job_id':job_id,'user_id':u['id'],'status':'queued','stage':'queued','percent':2,
                      'message':'Upload received. Waiting for document processing…',
                      'steps':[{'label':'Upload received','status':'done'},
                               {'label':'Read PDF / Word content','status':'waiting'},
                               {'label':'Analyse resume with Ollama','status':'waiting'},
                               {'label':'Save document and profile to MongoDB','status':'waiting'}]}
 asyncio.create_task(_run_resume_job(job_id,raw,name,ext,file.content_type or '',u['id']))
 return {'job_id':job_id,'status':'queued','message':'Resume processing started.'}


@app.get('/api/resumes/analyze/{job_id}')
def resume_job_status(job_id:str,u=Depends(user)):
 job=RESUME_JOBS.get(job_id)
 if not job or job.get('user_id') != u['id']:
  raise HTTPException(404,'Resume processing job not found.')
 return {k:v for k,v in job.items() if k != 'user_id'}



@app.post('/api/documents/upload')
async def upload_reference_document(file:UploadFile=File(...),u=Depends(user)):
 name=Path(file.filename or 'document').name
 ext=Path(name).suffix.lower()
 if ext not in ('.pdf','.docx'):
  raise HTTPException(400,'Only PDF and DOCX documents are supported.')
 raw=await file.read()
 if not raw or len(raw)>settings.max_upload_mb*1024*1024:
  raise HTTPException(413,'Empty file or upload size limit exceeded.')
 try:
  extracted=extract_document(raw,ext)
 except ValueError as e:
  raise HTTPException(422,str(e))
 doc_id=str(uuid4())
 db().documents.insert_one({
  '_id':doc_id,'user_id':u['id'],'filename':name,'extension':ext,
  'mime_type':file.content_type or '','file_data':raw,
  'page_count':extracted['page_count'],'title':extracted['title'],
  'extraction_method':extracted['extraction_method'],
  'character_count':len(extracted['text']),'chunk_count':len(extracted['chunks']),
  'document_type':'reference','summary':None,'verified':False,'created_at':now()
 })
 chunk_docs=[{
  'user_id':u['id'],'document_id':doc_id,'chunk_index':i,
  'text':chunk,'created_at':now()
 } for i,chunk in enumerate(extracted['chunks'])]
 if chunk_docs:db().document_chunks.insert_many(chunk_docs)
 return {
  'document_id':doc_id,'filename':name,
  'document':{'page_count':extracted['page_count'],
              'character_count':len(extracted['text']),
              'chunk_count':len(extracted['chunks']),
              'extraction_method':extracted['extraction_method']},
  'stored':True
}

@app.get('/api/documents')
def list_documents(u=Depends(user)):
 items=list(db().documents.find(
  {'user_id':u['id']},
  {'file_data':0,'profile_extraction':0}
 ).sort('created_at',-1).limit(100))
 for item in items:
  item['id']=item.pop('_id')
 return {'items':items}

@app.get('/api/documents/{document_id}')
def get_document(document_id:str,u=Depends(user)):
 item=db().documents.find_one({'_id':document_id,'user_id':u['id']},{
  'file_data':0
 })
 if not item:raise HTTPException(404,'Document not found')
 item['id']=item.pop('_id')
 return item

@app.post('/api/documents/{document_id}/ask')
async def ask_document(document_id:str,x:dict,u=Depends(user)):
 question=str(x.get('question','')).strip()
 if not question or len(question)>2000:
  raise HTTPException(400,'Enter a question (maximum 2,000 characters).')
 try:
  result=await answer_document_question(u['id'],document_id,question)
  db().document_qa.insert_one({
   'user_id':u['id'],'document_id':document_id,'question':question,
   'answer':result['answer'],'tools_used':result['tools_used'],'created_at':now()
  })
  return result
 except ValueError as e:
  raise HTTPException(404,str(e))
 except Exception as e:
  import logging
  logging.exception("Document Q&A failed")
  raise HTTPException(502,f"Document Q&A failed ({type(e).__name__}): {str(e) or repr(e)}")


@app.get('/api/documents/{document_id}/history')
def document_history(document_id:str,u=Depends(user)):
 if not db().documents.find_one({'_id':document_id,'user_id':u['id']},{'_id':1}):
  raise HTTPException(404,'Document not found')
 items=list(db().document_qa.find(
  {'user_id':u['id'],'document_id':document_id},
  {'_id':0,'question':1,'answer':1,'tools_used':1,'created_at':1}
 ).sort('created_at',1).limit(100))
 return {'items':items}

@app.post('/api/documents/{document_id}/summary')
async def summarize_document(document_id:str,u=Depends(user)):
 doc=db().documents.find_one({'_id':document_id,'user_id':u['id']})
 if not doc:raise HTTPException(404,'Document not found')
 if doc.get('summary'):
  return {'summary':doc['summary'],'cached':True}
 chunks=list(db().document_chunks.find(
  {'user_id':u['id'],'document_id':document_id},
  {'_id':0,'text':1}
 ).sort('chunk_index',1))
 text='\n\n'.join(item['text'] for item in chunks)
 try:
  summary=await summarize_chunks([item['text'] for item in chunks])
  db().documents.update_one({'_id':document_id,'user_id':u['id']},{'$set':{'summary':summary,'summary_created_at':now()}})
  db().document_summaries.insert_one({'user_id':u['id'],'document_id':document_id,'summary':summary,'created_at':now()})
  return {'summary':summary,'cached':False}
 except Exception as e:
  import logging
  logging.exception("Document summary failed")
  raise HTTPException(502,f"Summary generation failed ({type(e).__name__}): {str(e) or repr(e)}")

@app.delete('/api/documents/{document_id}')
def delete_document(document_id:str,u=Depends(user)):
 doc=db().documents.find_one({'_id':document_id,'user_id':u['id']})
 if not doc:raise HTTPException(404,'Document not found')
 db().document_chunks.delete_many({'user_id':u['id'],'document_id':document_id})
 db().document_qa.delete_many({'user_id':u['id'],'document_id':document_id})
 db().document_summaries.delete_many({'user_id':u['id'],'document_id':document_id})
 db().resumes.delete_many({'user_id':u['id'],'document_id':document_id})
 db().documents.delete_one({'_id':document_id,'user_id':u['id']})
 return {'deleted':True}

@app.get('/api/profile')
def get_profile(u=Depends(user)):
 d=db().candidate_profiles.find_one({'user_id':u['id']});return {'profile':d.get('profile') if d else None,'verified':bool(d and d.get('verified'))}
@app.put('/api/profile')
def save_profile(x:ProfileSave,u=Depends(user)):
 if x.resume_id and not db().resumes.find_one({'_id':x.resume_id,'user_id':u['id']}):raise HTTPException(404,'Resume not found')
 db().candidate_profiles.update_one({'user_id':u['id']},{'$set':{'profile':x.profile,'verified':True,'updated_at':now()}},upsert=True)
 if x.resume_id:db().resumes.update_one({'_id':x.resume_id,'user_id':u['id']},{'$set':{'verified':True,'status':'confirmed'}})
 # Only user-confirmed profile facts enter the reusable knowledge base.
 reusable_fields=('full_name','email','phone','location','headline','summary','total_experience','skills','education','experience','certifications','projects','links')
 for key in reusable_fields:
  value=x.profile.get(key)
  if value not in (None,'',[],{}):
   question='Candidate '+key.replace('_',' ')
   answer_text=value if isinstance(value,str) else __import__('json').dumps(value,ensure_ascii=False)
   db().knowledge_base.update_one(
    {'user_id':u['id'],'category':'confirmed_profile','question':question},
    {'$set':{'answer':answer_text,'verified':True,'reusable':True,'source':'user_confirmed_profile','updated_at':now()}},
    upsert=True
   )
 if x.resume_id:
  resume=db().resumes.find_one({'_id':x.resume_id,'user_id':u['id']})
  if resume and resume.get('document_id'):
   db().documents.update_one({'_id':resume['document_id'],'user_id':u['id']},{'$set':{'verified':True,'confirmed_at':now()}})
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
