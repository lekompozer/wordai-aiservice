#!/usr/bin/env python3
"""
List all files for a user (including deleted ones)
"""
import sys

sys.path.insert(0, "/app")

from config.config import get_mongodb

user_id = "17BeaeikPBQYk8OWeDUkqm0Ov8e2"

print(f"\n🔍 Listing ALL files for user {user_id}")
print("=" * 80)

db = get_mongodb()
user_files = db.user_files

# Get all files (including deleted)
files = user_files.find({"user_id": user_id}).sort("upload_time", -1).limit(20)

count = 0
for f in files:
    count += 1
    print(f"\n📄 File {count}:")
    print(f"   file_id: {f.get('file_id')}")
    print(f"   original_name: {f.get('original_name')}")
    print(f"   file_type: {f.get('file_type')}")
    print(f"   is_deleted: {f.get('is_deleted', False)}")
    print(f"   upload_time: {f.get('upload_time')}")
    print(f"   r2_key: {f.get('r2_key')}")

if count == 0:
    print(f"\n❌ No files found for user {user_id}")
    print(f"\n💡 This user needs to upload a file first!")
    print(f"   Use: POST /api/simple-file/upload")
    print(f"   Or:  POST /api/files/upload")
else:
    print(f"\n✅ Total: {count} file(s)")

print("\n" + "=" * 80)
