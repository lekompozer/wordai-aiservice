#!/usr/bin/env python3
"""
Setup system user and @sachonline author for book crawler
Usage: python setup_crawler_system_user.py
"""

from src.database.db_manager import DBManager
from datetime import datetime
import uuid


def setup_system_user():
    """Create system user and @sachonline author in database"""

    db_manager = DBManager()
    db = db_manager.db

    # System user ID (fixed)
    SYSTEM_USER_ID = "system_crawler_uid"
    AUTHOR_ID = "@sachonline"

    print("🔧 Setting up crawler system user and author...\n")

    # 1. Create @sachonline author
    print("1️⃣  Creating @sachonline author...")
    existing_author = db.authors.find_one({"author_id": AUTHOR_ID})

    if existing_author:
        print(f"   ⏭️  Skip: Author {AUTHOR_ID} already exists")
    else:
        author_doc = {
            "_id": str(uuid.uuid4()),
            "author_id": AUTHOR_ID,
            "name": "Sách Online",
            "bio": "Kho sách miễn phí từ nhiều nguồn - Tự động thu thập và chia sẻ",
            "avatar_url": "https://static.wordai.pro/authors/sachonline.jpg",
            # Social links
            "facebook_url": None,
            "website_url": "https://nhasachmienphi.com",
            # Stats (updated by crawler)
            "total_books": 0,
            "total_followers": 0,
            "total_views": 0,
            # Metadata
            "created_by": "system",
            "is_verified": True,
            "is_system_account": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        db.authors.insert_one(author_doc)
        print(f"   ✅ Created author: {AUTHOR_ID}")

    # 2. Create system root folder (for file storage)
    print("\n2️⃣  Creating system user root folder...")
    existing_folder = db.user_files.find_one(
        {"user_id": SYSTEM_USER_ID, "file_type": "folder", "filename": "root"}
    )

    if existing_folder:
        print(f"   ⏭️  Skip: Root folder already exists")
    else:
        folder_doc = {
            "file_id": f"folder_{uuid.uuid4().hex[:12]}",
            "user_id": SYSTEM_USER_ID,
            "filename": "root",
            "file_type": "folder",
            "parent_folder_id": None,
            "is_deleted": False,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        db.user_files.insert_one(folder_doc)
        print(f"   ✅ Created root folder for system user")

    # 3. Create default avatar (if not exists)
    print("\n3️⃣  Checking default avatar...")
    # Note: You need to manually upload avatar to R2 at:
    # https://static.wordai.pro/authors/sachonline.jpg
    print(f"   ⚠️  Manual step: Upload avatar to R2 storage")
    print(f"      Path: authors/sachonline.jpg")
    print(f"      URL: https://static.wordai.pro/authors/sachonline.jpg")

    print("\n✅ Setup completed!")
    print(f"\n📝 Summary:")
    print(f"   Author ID: {AUTHOR_ID}")
    print(f"   System User ID: {SYSTEM_USER_ID}")
    print(f"   Root Folder: Created")
    print(f"\n⚠️  Next steps:")
    print(f"   1. Upload avatar to R2 (optional)")
    print(f"   2. Create Firebase user with UID: {SYSTEM_USER_ID}")
    print(f"      Email: crawler@wordai.pro")
    print(f"      Password: [Generate secure password]")
    print(f"   3. Run: python seed_nhasachmienphi_categories.py")


if __name__ == "__main__":
    setup_system_user()
