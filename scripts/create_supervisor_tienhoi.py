"""
One-off script to create supervisor account for tienhoi.lh@gmail.com.

Looks up Firebase UID by email, then creates supervisor document in MongoDB.

Run on production:
    docker cp create_supervisor_tienhoi.py ai-chatbot-rag:/app/
    docker exec ai-chatbot-rag python3 /app/create_supervisor_tienhoi.py
"""

from datetime import datetime
from src.database.db_manager import DBManager
from src.config.firebase_config import FirebaseConfig

# ── Config ────────────────────────────────────────────────────────────────────
EMAIL = "tienhoi.lh@gmail.com"
SUPERVISOR_CODE = "SUP_TIENHOI"
SUPERVISOR_NAME = "Supervisor - Tiến Hội"
NOTES = "Tài khoản Supervisor được tạo bởi Admin"
# ─────────────────────────────────────────────────────────────────────────────

db_manager = DBManager()
db = db_manager.db

# 1. Look up Firebase UID by email
print(f"🔍 Looking up Firebase user: {EMAIL}")
try:
    from firebase_admin import auth as firebase_auth

    FirebaseConfig()  # ensure initialized
    user = firebase_auth.get_user_by_email(EMAIL)
    user_id = user.uid
    print(
        f"  ✅ Found: uid={user_id}, email={user.email}, display_name={user.display_name}"
    )
except Exception as e:
    print(f"  ⚠️  Firebase lookup failed: {e}")
    print("  → Creating supervisor without user_id (can be linked later via admin API)")
    user_id = None

# 2. Check if supervisor with this code already exists
existing = db["supervisors"].find_one({"code": SUPERVISOR_CODE})
if existing:
    print(f"\n⚠️  Supervisor '{SUPERVISOR_CODE}' already exists!")
    print(f"   ID: {existing['_id']}, user_id: {existing.get('user_id')}")
    if user_id and not existing.get("user_id"):
        # Link Firebase UID to existing record
        db["supervisors"].update_one(
            {"code": SUPERVISOR_CODE},
            {"$set": {"user_id": user_id, "updated_at": datetime.utcnow()}},
        )
        print(f"  ✅ Linked user_id={user_id} to existing supervisor")
    else:
        print("  → No changes needed")
else:
    # 3. Create supervisor document
    now = datetime.utcnow()
    doc = {
        "code": SUPERVISOR_CODE,
        "name": SUPERVISOR_NAME,
        "is_active": True,
        "user_id": user_id,
        "notes": NOTES,
        "bank_info": None,
        "pending_balance": 0,
        "available_balance": 0,
        "total_earned": 0,
        "total_managed_affiliates": 0,
        "created_at": now,
        "updated_at": now,
    }
    result = db["supervisors"].insert_one(doc)
    print(f"\n✅ Supervisor created!")
    print(f"   _id      : {result.inserted_id}")
    print(f"   code     : {SUPERVISOR_CODE}")
    print(f"   name     : {SUPERVISOR_NAME}")
    print(f"   user_id  : {user_id}")
    print(f"   email    : {EMAIL}")
    print(f"\n💡 To login as supervisor, use Firebase Auth with email: {EMAIL}")
    print(f"   Portal endpoint: GET /api/v1/supervisors/me")
