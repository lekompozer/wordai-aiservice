#!/usr/bin/env python3
"""Debug script for share_8165b18b26ff4862"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.mongodb_config import get_mongodb


def debug_share():
    """Debug the share and library file"""
    db = get_mongodb()

    share_id = "share_8165b18b26ff4862"

    print("=" * 80)
    print(f"🔍 DEBUG SHARE: {share_id}")
    print("=" * 80)

    # 1. Get share record
    print("\n📋 1. FILE_SHARES RECORD:")
    print("-" * 80)
    share = db["file_shares"].find_one({"share_id": share_id})
    if share:
        print(f"share_id: {share.get('share_id')}")
        print(f"file_id: {share.get('file_id')}")
        print(f"file_type: {share.get('file_type')}")
        print(f"owner_id: {share.get('owner_id')}")
        print(f"recipient_id: {share.get('recipient_id')}")
        print(f"permission: {share.get('permission')}")
        print(f"is_active: {share.get('is_active')}")
        print(f"is_encrypted: {share.get('is_encrypted')}")
        print(f"created_at: {share.get('created_at')}")
    else:
        print("❌ Share not found!")
        return

    # 2. Get library file
    file_id = share.get("file_id")
    recipient_id = share.get("recipient_id")

    print(f"\n📁 2. LIBRARY_FILES RECORD (file_id={file_id}):")
    print("-" * 80)
    library_file = db["library_files"].find_one({"library_id": file_id})
    if library_file:
        print(f"library_id: {library_file.get('library_id')}")
        print(f"filename: {library_file.get('filename')}")
        print(f"user_id: {library_file.get('user_id')}")
        print(f"is_encrypted: {library_file.get('is_encrypted')}")
        print(f"shared_with: {library_file.get('shared_with', [])}")

        encrypted_file_keys = library_file.get("encrypted_file_keys", {})
        print(f"\n🔑 encrypted_file_keys keys: {list(encrypted_file_keys.keys())}")

        if recipient_id:
            print(f"\n🎯 Looking for key: {recipient_id}")
            if recipient_id in encrypted_file_keys:
                key_value = encrypted_file_keys[recipient_id]
                print(f"✅ FOUND! Length: {len(key_value)} chars")
                print(f"Preview: {key_value[:50]}...")
            else:
                print(f"❌ NOT FOUND! recipient_id not in encrypted_file_keys")
                print(f"Available keys: {list(encrypted_file_keys.keys())}")
    else:
        print("❌ Library file not found!")
        return

    # 3. Get recipient user
    print(f"\n👤 3. RECIPIENT USER (recipient_id={recipient_id}):")
    print("-" * 80)
    user = db["users"].find_one({"uid": recipient_id})
    if user:
        print(f"uid: {user.get('uid')}")
        print(f"email: {user.get('email')}")
        print(f"display_name: {user.get('displayName')}")
        has_public_key = bool(user.get("publicKey"))
        print(f"has publicKey: {has_public_key}")
    else:
        print("❌ Recipient user not found!")

    print("\n" + "=" * 80)
    print("🎯 CONCLUSION:")
    print("=" * 80)
    if share and library_file:
        if recipient_id in encrypted_file_keys:
            print("✅ Everything looks correct!")
            print(f"   - share record exists with recipient_id={recipient_id}")
            print(f"   - encrypted_file_keys[{recipient_id}] exists")
            print("   - User should be able to access")
        else:
            print("❌ PROBLEM FOUND:")
            print(f"   - share record has recipient_id={recipient_id}")
            print(
                f"   - BUT encrypted_file_keys does NOT have key for {recipient_id}"
            )
            print(f"   - Available keys: {list(encrypted_file_keys.keys())}")
            print("\n💡 This is why user gets 403 error!")


if __name__ == "__main__":
    debug_share()
