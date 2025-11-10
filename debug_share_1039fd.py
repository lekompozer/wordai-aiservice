#!/usr/bin/env python3
"""Debug script for share_1039fda898e34b5d"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.config import get_mongodb


def debug_share():
    """Debug the share and library file"""
    db = get_mongodb()

    share_id = "share_1039fda898e34b5d"
    accessing_uid = "17BeaeikPBQYk8OWeDUkqm0Ov8e2"
    key_in_db = "KkAfCdSeUOduPYNCRfbv446rnR72"

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
        print(f"owner_id: {share.get('owner_id')}")
        print(f"recipient_id: {share.get('recipient_id')}")
        print(f"is_active: {share.get('is_active')}")
        print(f"created_at: {share.get('created_at')}")

        recipient_id = share.get("recipient_id")
    else:
        print("❌ Share not found!")
        return

    # 2. Check who is trying to access
    print(f"\n👤 2. USER TRYING TO ACCESS:")
    print("-" * 80)
    print(f"user_id from JWT: {accessing_uid}")
    print(f"recipient_id in share: {recipient_id}")
    if accessing_uid == recipient_id:
        print("✅ MATCH! User is the recipient")
    else:
        print("❌ MISMATCH! User is NOT the recipient!")

        # Get both users
        accessing_user = db["users"].find_one({"uid": accessing_uid})
        recipient_user = db["users"].find_one({"uid": recipient_id})

        print(f"\n👤 Accessing user (uid={accessing_uid}):")
        if accessing_user:
            print(f"   email: {accessing_user.get('email')}")
            print(f"   name: {accessing_user.get('displayName')}")
        else:
            print("   ❌ Not found!")

        print(f"\n👤 Recipient user (uid={recipient_id}):")
        if recipient_user:
            print(f"   email: {recipient_user.get('email')}")
            print(f"   name: {recipient_user.get('displayName')}")
        else:
            print("   ❌ Not found!")

    # 3. Check library file
    file_id = share.get("file_id")
    print(f"\n📁 3. LIBRARY_FILES RECORD (file_id={file_id}):")
    print("-" * 80)
    library_file = db["library_files"].find_one({"library_id": file_id})
    if library_file:
        print(f"library_id: {library_file.get('library_id')}")
        print(f"filename: {library_file.get('filename')}")
        print(f"owner_id (user_id): {library_file.get('user_id')}")

        encrypted_file_keys = library_file.get("encrypted_file_keys", {})
        print(f"\n🔑 encrypted_file_keys:")
        for uid, key_preview in encrypted_file_keys.items():
            print(f"   {uid}: {key_preview[:50]}...")

            # Check who this uid is
            user = db["users"].find_one({"uid": uid})
            if user:
                print(f"      → {user.get('email')} ({user.get('displayName')})")
            else:
                print(f"      → User not found!")
    else:
        print("❌ Library file not found!")
        return

    # 4. Conclusion
    print("\n" + "=" * 80)
    print("🎯 PROBLEM ANALYSIS:")
    print("=" * 80)

    if accessing_uid == recipient_id:
        if accessing_uid in encrypted_file_keys:
            print("✅ Everything is correct!")
            print("   - User is the recipient")
            print("   - Key exists for user")
        else:
            print("❌ PROBLEM: Key missing for recipient!")
            print(f"   - User is recipient (uid={recipient_id})")
            print(f"   - But key not in encrypted_file_keys")
            print(f"   - Available keys: {list(encrypted_file_keys.keys())}")
    else:
        print("❌ PROBLEM: Wrong user trying to access!")
        print(f"   - Accessing user: {accessing_uid}")
        print(f"   - Recipient should be: {recipient_id}")
        print("\n💡 POSSIBLE CAUSES:")
        print("   1. User logged in with wrong account")
        print("   2. Share was created for different user")
        print("   3. Frontend using wrong user session")


if __name__ == "__main__":
    debug_share()
