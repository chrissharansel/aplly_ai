from datetime import datetime,timedelta,timezone
from jose import jwt,JWTError
from passlib.context import CryptContext
from fastapi import Depends,HTTPException
from fastapi.security import HTTPBearer,HTTPAuthorizationCredentials
from app.config import settings
from app.db import db
pwd=CryptContext(schemes=['bcrypt'],deprecated='auto');bearer=HTTPBearer()
def hashpw(p):return pwd.hash(p)
def checkpw(p,h):return pwd.verify(p,h)
def token(uid):return jwt.encode({'sub':uid,'exp':datetime.now(timezone.utc)+timedelta(minutes=settings.access_token_minutes)},settings.secret_key,algorithm='HS256')
def user(c:HTTPAuthorizationCredentials=Depends(bearer)):
 try:uid=jwt.decode(c.credentials,settings.secret_key,algorithms=['HS256']).get('sub')
 except JWTError:uid=None
 u=db().users.find_one({'_id':uid},{'password_hash':0}) if uid else None
 if not u:raise HTTPException(401,'Invalid login session')
 u['id']=u.pop('_id');return u
