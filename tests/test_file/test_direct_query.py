#!/usr/bin/env python3
"""
Direct MongoDB query test
"""
import sys

sys.path.insert(0, "/app")

from config.config import get_mongodb

file_id = "file_66e18e975d12"
user_id = "17BeaeikPBQYk8OWeDUkqm0Ov8e2"

print(f"\n🔍 Testing MongoDB query")
print("=" * 80)

db = get_mongodb()
user_files = db.user_files

# Test exact query from get_file_by_id
query = {"file_id": file_id, "user_id": user_id, "is_deleted": False}
print(f"\nQuery: {query}")

file_doc = user_files.find_one(query)

if file_doc:
    print(f"\n✅ File FOUND!")
    print(f"\nFile Info:")
    for key, value in file_doc.items():
        if key == "_id":
            continue
        print(f"   {key}: {value}")
else:
    print(f"\n❌ File NOT FOUND with this query!")

    # Try without is_deleted filter
    print(f"\n🔍 Trying without is_deleted filter...")
    query2 = {"file_id": file_id, "user_id": user_id}
    file_doc2 = user_files.find_one(query2)

    if file_doc2:
        print(f"\n✅ File FOUND without is_deleted filter!")
        print(f"   is_deleted value: {file_doc2.get('is_deleted')}")
        print(f"   is_deleted type: {type(file_doc2.get('is_deleted'))}")
    else:
        print(f"\n❌ Still not found!")

print("\n" + "=" * 80)
