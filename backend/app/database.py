from pymongo import MongoClient
from app.config import settings

_client = None

def get_client():
    global _client
    if _client is None:
        _client = MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)
    return _client

def get_database():
    return get_client()[settings.mongodb_database]

def check_mongodb():
    try:
        get_client().admin.command("ping")
        return True, "Connected to MongoDB Atlas"
    except Exception as exc:
        return False, f"MongoDB connection failed: {type(exc).__name__}"

def close_mongodb():
    global _client
    if _client is not None:
        _client.close()
        _client = None
