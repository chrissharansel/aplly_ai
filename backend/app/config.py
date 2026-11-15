from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
 mongodb_uri:str
 mongodb_database:str='applyai'
 ollama_base_url:str='http://localhost:11434'
 ollama_model:str='llama3.1:8b'
 secret_key:str
 access_token_minutes:int=720
 frontend_origins:str='http://localhost:5173,http://127.0.0.1:5173'
 max_upload_mb:int=5
 browser_headless:bool=False
 model_config=SettingsConfigDict(env_file='.env',extra='ignore')
 @property
 def origins(self): return [x.strip() for x in self.frontend_origins.split(',') if x.strip()]
settings=Settings()
