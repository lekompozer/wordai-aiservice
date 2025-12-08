"""
Debug script to check book structure
"""

import os
from pymongo import MongoClient
import json

MONGODB_URI = os.environ.get(
    "MONGODB_URI_AUTH",
    "mongodb://ai_service_user:wordai_secure_2024@localhost:27017/ai_service_db?authSource=ai_service_db",
)

client = MongoClient(MONGODB_URI)
db = client.ai_service_db

book = db.online_books.find_one(
    {"book_id": "guide_f1fa41574c92"},
    {"book_id": 1, "title": 1, "authors": 1, "community_config": 1, "_id": 0},
)

print(json.dumps(book, indent=2, default=str))

client.close()
