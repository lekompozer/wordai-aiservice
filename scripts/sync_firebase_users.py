#!/usr/bin/env python3
"""
Create firebase_users record for logged-in user
This script creates the missing firebase_users record with bonus points
"""
import sys

sys.path.insert(0, "/app/src")

from src.config.database import get_database
from datetime import datetime, timezone
import firebase_admin
from firebase_admin import credentials, auth
from pathlib import Path

# Initialize Firebase Admin
cred_path = Path("/app/firebase-credentials.json")
if not cred_path.exists():
    print("❌ Firebase credentials not found!")
    sys.exit(1)

if not firebase_admin._apps:
    cred = credentials.Certificate(str(cred_path))
    firebase_admin.initialize_app(cred)
    print("✅ Firebase Admin initialized\n")

db = get_database()

print("🔍 Fetching all users from Firebase Auth...")
print("=" * 80)

# Get all users from Firebase Auth
try:
    page = auth.list_users()
    users = page.users

    print(f"✅ Found {len(users)} users in Firebase Auth\n")

    for user in users:
        email = user.email
        uid = user.uid

        print(f"👤 User: {email}")
        print(f"   UID: {uid}")

        # Check if exists in firebase_users
        existing = db.firebase_users.find_one({"uid": uid})

        if existing:
            print(f"   ✅ Already in firebase_users")
            print(f"      points_remaining: {existing.get('points_remaining', 0)}")
        else:
            print(f"   ❌ NOT in firebase_users - Creating record...")

            # Create firebase_users record with bonus points
            user_doc = {
                "uid": uid,
                "email": email,
                "display_name": user.display_name,
                "photo_url": user.photo_url,
                "points_remaining": 10,  # 10 bonus points
                "points_total": 10,
                "earnings_points": 0,
                "bonus_points": 10,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }

            result = db.firebase_users.insert_one(user_doc)

            if result.inserted_id:
                print(f"   ✅ Created firebase_users record!")
                print(f"      Bonus points: 10")
            else:
                print(f"   ❌ Failed to create record")

        print()

    print("=" * 80)
    print(f"\n📊 Summary:")
    total = db.firebase_users.count_documents({})
    print(f"   Total users in firebase_users: {total}")

    # Check specific user
    target_user = db.firebase_users.find_one({"email": "tienhoi.lh@gmail.com"})
    if target_user:
        print(f"\n✅ Target user tienhoi.lh@gmail.com:")
        print(f"   uid: {target_user.get('uid')}")
        print(f"   points_remaining: {target_user.get('points_remaining')}")
        print(f"\n🎉 User can now purchase books!")
    else:
        print(f"\n⚠️ Target user tienhoi.lh@gmail.com not found in Firebase Auth")
        print(f"   User may need to login first")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback

    traceback.print_exc()
