from pymongo import MongoClient,ASCENDING,DESCENDING
from app.config import settings
_client=None
def db():
 global _client
 if _client is None:_client=MongoClient(settings.mongodb_uri,serverSelectionTimeoutMS=6000)
 return _client[settings.mongodb_database]
def ping():
 try: db().command('ping');return True,'MongoDB connected'
 except Exception as e:return False,type(e).__name__
def init():
 d=db();d.users.create_index('email',unique=True);d.knowledge_base.create_index([('user_id',ASCENDING),('updated_at',DESCENDING)]);d.applications.create_index([('user_id',ASCENDING),('created_at',DESCENDING)])
 d.documents.create_index([('user_id',ASCENDING),('created_at',DESCENDING)])
 d.document_chunks.create_index([('user_id',ASCENDING),('document_id',ASCENDING),('chunk_index',ASCENDING)])
 d.document_qa.create_index([('user_id',ASCENDING),('document_id',ASCENDING),('created_at',DESCENDING)])
 d.document_summaries.create_index([('user_id',ASCENDING),('document_id',ASCENDING)])
def close():
 global _client
 if _client:_client.close();_client=None
