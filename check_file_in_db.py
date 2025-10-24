#!/usr/bin/env python3
"""
Debug script to check if file exists in user_files collection
"""
import sys

sys.path.insert(0, "/app")

from config.config import get_mongodb
from src.services.user_manager import UserManager

# File and user from logs
file_id = "file_66e18e975d12"
user_id = "17BeaeikPBQYk8OWeDUkqm0Ov8e2"

print(f"\n🔍 Checking file in database:")
print(f"   File ID: {file_id}")
print(f"   User ID: {user_id}")
print("-" * 60)

db = get_mongodb()
user_manager = UserManager(db)

# Try to get file
file_info = user_manager.get_file_by_id(file_id, user_id)

if file_info:
    print(f"\n✅ File FOUND in database!")
    print(f"\nFile Info:")
    for key, value in file_info.items():
        if key == "_id":
            continue
        print(f"   {key}: {value}")
else:
    print(f"\n❌ File NOT FOUND in database!")

    # Check if file exists for any user
    print(f"\n🔍 Checking if file exists for ANY user...")
    all_files = user_manager.user_files.find({"file_id": file_id})
    count = 0
    for f in all_files:
        count += 1
        print(f"\n   Found file for user: {f.get('user_id')}")
        print(f"   is_deleted: {f.get('is_deleted')}")
        print(f"   original_name: {f.get('original_name')}")
        print(f"   r2_key: {f.get('r2_key')}")

    if count == 0:
        print(f"   ❌ No files found with file_id={file_id}")

    # Check files for this user
    print(f"\n🔍 Checking ALL files for user {user_id}...")
    user_files = user_manager.user_files.find(
        {"user_id": user_id, "is_deleted": False}
    ).limit(5)
    count = 0
    for f in user_files:
        count += 1
        print(f"\n   File {count}:")
        print(f"      file_id: {f.get('file_id')}")
        print(f"      original_name: {f.get('original_name')}")
        print(f"      file_type: {f.get('file_type')}")

    if count == 0:
        print(f"   ❌ No files found for user {user_id}")

print("\n" + "=" * 60)
