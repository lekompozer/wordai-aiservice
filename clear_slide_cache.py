#!/usr/bin/env python3
"""
Delete cached slide documents to force re-parse
"""
import sys

sys.path.insert(0, "/app")

from config.config import get_mongodb

file_id = "file_66e18e975d12"
user_id = "17BeaeikPBQYk8OWeDUkqm0Ov8e2"

db = get_mongodb()
documents = db.documents

# Delete all documents for this file
result = documents.delete_many({"file_id": file_id, "user_id": user_id})

print(f"\n🗑️  Deleted {result.deleted_count} cached document(s)")
print(f"✅ File {file_id} cache cleared!")
print(f"\n📝 Next parse will use fresh Gemini API call with current prompt")
