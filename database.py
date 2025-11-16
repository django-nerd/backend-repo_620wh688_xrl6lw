"""
Database Helper Functions

MongoDB helper functions ready to use in your backend code.
Import and use these functions in your API endpoints for database operations.
"""

from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime, timezone
import os
from dotenv import load_dotenv
from typing import Union, Optional, Dict, Any, List
from pydantic import BaseModel

# Load environment variables from .env file
load_dotenv()

_client = None
db = None

database_url = os.getenv("DATABASE_URL")
database_name = os.getenv("DATABASE_NAME")

if database_url and database_name:
    _client = MongoClient(database_url)
    db = _client[database_name]


def _ensure_db():
    if db is None:
        raise Exception("Database not available. Check DATABASE_URL and DATABASE_NAME environment variables.")


def _to_dict(data: Union[BaseModel, dict]) -> dict:
    if isinstance(data, BaseModel):
        return data.model_dump()
    return dict(data)


# CRUD helpers

def create_document(collection_name: str, data: Union[BaseModel, dict]) -> str:
    _ensure_db()
    payload = _to_dict(data)
    now = datetime.now(timezone.utc)
    payload['created_at'] = now
    payload['updated_at'] = now
    result = db[collection_name].insert_one(payload)
    return str(result.inserted_id)


def get_documents(collection_name: str, filter_dict: Optional[dict] = None, limit: Optional[int] = None, sort: Optional[list] = None) -> List[dict]:
    _ensure_db()
    cursor = db[collection_name].find(filter_dict or {})
    if sort:
        cursor = cursor.sort(sort)
    if limit:
        cursor = cursor.limit(int(limit))
    return [serialize_doc(doc) for doc in cursor]


def get_document_by_id(collection_name: str, _id: str) -> Optional[dict]:
    _ensure_db()
    try:
        doc = db[collection_name].find_one({"_id": ObjectId(_id)})
        return serialize_doc(doc) if doc else None
    except Exception:
        return None


def update_document(collection_name: str, _id: str, update_data: Dict[str, Any]) -> bool:
    _ensure_db()
    update = {"$set": _to_dict(update_data)}
    update["$set"]["updated_at"] = datetime.now(timezone.utc)
    result = db[collection_name].update_one({"_id": ObjectId(_id)}, update)
    return result.modified_count > 0


def delete_document(collection_name: str, _id: str) -> bool:
    _ensure_db()
    result = db[collection_name].delete_one({"_id": ObjectId(_id)})
    return result.deleted_count > 0


# Utility

def serialize_doc(doc: Optional[dict]) -> Optional[dict]:
    if not doc:
        return None
    d = dict(doc)
    if "_id" in d:
        d["_id"] = str(d["_id"])  # convert ObjectId to string
    return d
