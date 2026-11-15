from pymongo import MongoClient
from pymongo.errors import PyMongoError
from app.config import settings

_client: MongoClient | None = None

def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
        )
    return _client

def get_database():
    return get_client()[settings.mongodb_database]

def check_mongodb() -> tuple[bool, str]:
    try:
        get_client().admin.command("ping")
        return True, "Connected to MongoDB Atlas"
    except PyMongoError as exc:
        return False, f"MongoDB connection failed: {exc.__class__.__name__}"

def close_mongodb() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
