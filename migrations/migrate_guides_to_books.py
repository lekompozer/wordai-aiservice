#!/usr/bin/env python3
"""
Migration Script: Guide → Book Terminology
Renames collections and updates field names for Online Books system

Collections renamed:
- user_guides → online_books
- guide_chapters → book_chapters  
- guide_permissions → book_permissions

Field renames:
- guide_id → book_id (all collections)

New fields added:
- access_config to online_books
- community_config to online_books
- stats to online_books
- content_source to book_chapters
- document_id to book_chapters

Usage:
    python migrations/migrate_guides_to_books.py

Author: GitHub Copilot
Date: November 15, 2025
"""

import sys
import os
from pymongo import MongoClient
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config.config as config


def migrate_guides_to_books():
    """Execute Guide → Book migration"""
    
    print("=" * 80)
    print("🚀 MIGRATION: Guide → Book Terminology")
    print("=" * 80)
    print()
    
    # Connect to MongoDB
    try:
        mongo_uri = getattr(config, "MONGODB_URI_AUTH", None) or getattr(
            config, "MONGODB_URI", "mongodb://localhost:27017"
        )
        db_name = getattr(config, "MONGODB_NAME", "wordai_db")
        
        print(f"📡 Connecting to MongoDB: {db_name}")
        client = MongoClient(mongo_uri)
        db = client[db_name]
        
        # Test connection
        db.command("ping")
        print(f"✅ Connected to database: {db_name}\n")
        
    except Exception as e:
        print(f"❌ Failed to connect to MongoDB: {e}")
        return False
    
    # ============================================================
    # STEP 1: Rename Collections
    # ============================================================
    print("📦 STEP 1: Renaming Collections")
    print("-" * 80)
    
    collection_renames = [
        ("user_guides", "online_books"),
        ("guide_chapters", "book_chapters"),
        ("guide_permissions", "book_permissions")
    ]
    
    existing_collections = db.list_collection_names()
    
    for old_name, new_name in collection_renames:
        if old_name in existing_collections:
            if new_name in existing_collections:
                print(f"⚠️  {new_name} already exists, skipping rename of {old_name}")
            else:
                db[old_name].rename(new_name)
                print(f"✅ Renamed: {old_name} → {new_name}")
        else:
            if new_name in existing_collections:
                print(f"✅ {new_name} already exists (migration already done)")
            else:
                print(f"⚠️  {old_name} not found, skipping")
    
    print()
    
    # ============================================================
    # STEP 2: Update Field Names in online_books
    # ============================================================
    print("🔄 STEP 2: Updating Field Names in online_books")
    print("-" * 80)
    
    if "online_books" in db.list_collection_names():
        # Rename guide_id → book_id
        result = db.online_books.update_many(
            {"guide_id": {"$exists": True}},
            {"$rename": {"guide_id": "book_id"}}
        )
        print(f"✅ Renamed guide_id → book_id: {result.modified_count} documents")
        
        # Add new fields
        result = db.online_books.update_many(
            {"access_config": {"$exists": False}},
            {
                "$set": {
                    "access_config": {
                        "one_time_view_points": 0,
                        "forever_view_points": 0,
                        "download_pdf_points": 0,
                        "is_one_time_enabled": False,
                        "is_forever_enabled": False,
                        "is_download_enabled": False
                    },
                    "community_config": {
                        "is_public": False,
                        "category": None,
                        "tags": [],
                        "short_description": None,
                        "cover_image_url": None,
                        "difficulty_level": None,
                        "total_views": 0,
                        "total_downloads": 0,
                        "total_purchases": 0,
                        "average_rating": 0.0,
                        "rating_count": 0,
                        "version": "1.0.0",
                        "published_at": None
                    },
                    "stats": {
                        "total_revenue_points": 0,
                        "owner_reward_points": 0,
                        "system_fee_points": 0
                    }
                }
            }
        )
        print(f"✅ Added new fields (access_config, community_config, stats): {result.modified_count} documents")
    else:
        print("⚠️  online_books collection not found")
    
    print()
    
    # ============================================================
    # STEP 3: Update Field Names in book_chapters
    # ============================================================
    print("🔄 STEP 3: Updating Field Names in book_chapters")
    print("-" * 80)
    
    if "book_chapters" in db.list_collection_names():
        # Rename guide_id → book_id
        result = db.book_chapters.update_many(
            {"guide_id": {"$exists": True}},
            {"$rename": {"guide_id": "book_id"}}
        )
        print(f"✅ Renamed guide_id → book_id: {result.modified_count} documents")
        
        # Add new fields for document integration
        result = db.book_chapters.update_many(
            {"content_source": {"$exists": False}},
            {
                "$set": {
                    "content_source": "inline",  # All existing chapters are inline
                    "document_id": None
                }
            }
        )
        print(f"✅ Added new fields (content_source, document_id): {result.modified_count} documents")
    else:
        print("⚠️  book_chapters collection not found")
    
    print()
    
    # ============================================================
    # STEP 4: Update Field Names in book_permissions
    # ============================================================
    print("🔄 STEP 4: Updating Field Names in book_permissions")
    print("-" * 80)
    
    if "book_permissions" in db.list_collection_names():
        # Rename guide_id → book_id
        result = db.book_permissions.update_many(
            {"guide_id": {"$exists": True}},
            {"$rename": {"guide_id": "book_id"}}
        )
        print(f"✅ Renamed guide_id → book_id: {result.modified_count} documents")
    else:
        print("⚠️  book_permissions collection not found")
    
    print()
    
    # ============================================================
    # STEP 5: Create Indexes for New Collections
    # ============================================================
    print("🔍 STEP 5: Creating/Updating Indexes")
    print("-" * 80)
    
    if "online_books" in db.list_collection_names():
        # Create new indexes
        try:
            db.online_books.create_index("book_id", unique=True)
            print("✅ Created index: online_books.book_id (unique)")
        except Exception as e:
            print(f"⚠️  Index online_books.book_id already exists or error: {e}")
        
        try:
            db.online_books.create_index([("community_config.is_public", 1), ("community_config.published_at", -1)])
            print("✅ Created index: online_books.community_config.is_public + published_at")
        except Exception as e:
            print(f"⚠️  Community index already exists or error: {e}")
    
    if "book_chapters" in db.list_collection_names():
        try:
            db.book_chapters.create_index("document_id")
            print("✅ Created index: book_chapters.document_id")
        except Exception as e:
            print(f"⚠️  Index book_chapters.document_id already exists or error: {e}")
    
    print()
    
    # ============================================================
    # STEP 6: Verification
    # ============================================================
    print("✅ STEP 6: Verification")
    print("-" * 80)
    
    collections = db.list_collection_names()
    
    if "online_books" in collections:
        count = db.online_books.count_documents({})
        print(f"✅ online_books: {count} documents")
        
        # Check field migration
        with_book_id = db.online_books.count_documents({"book_id": {"$exists": True}})
        with_guide_id = db.online_books.count_documents({"guide_id": {"$exists": True}})
        print(f"   - book_id field: {with_book_id} documents")
        print(f"   - guide_id field (old): {with_guide_id} documents (should be 0)")
        
        with_access_config = db.online_books.count_documents({"access_config": {"$exists": True}})
        print(f"   - access_config: {with_access_config} documents")
    
    if "book_chapters" in collections:
        count = db.book_chapters.count_documents({})
        print(f"✅ book_chapters: {count} documents")
        
        with_book_id = db.book_chapters.count_documents({"book_id": {"$exists": True}})
        with_guide_id = db.book_chapters.count_documents({"guide_id": {"$exists": True}})
        print(f"   - book_id field: {with_book_id} documents")
        print(f"   - guide_id field (old): {with_guide_id} documents (should be 0)")
    
    if "book_permissions" in collections:
        count = db.book_permissions.count_documents({})
        print(f"✅ book_permissions: {count} documents")
        
        with_book_id = db.book_permissions.count_documents({"book_id": {"$exists": True}})
        with_guide_id = db.book_permissions.count_documents({"guide_id": {"$exists": True}})
        print(f"   - book_id field: {with_book_id} documents")
        print(f"   - guide_id field (old): {with_guide_id} documents (should be 0)")
    
    print()
    
    # Close connection
    client.close()
    
    print("=" * 80)
    print("✅ Migration Complete!")
    print("=" * 80)
    print()
    print("⚠️  NEXT STEPS:")
    print("   1. Update Python code (rename files & find/replace)")
    print("   2. Update API endpoints (/guides → /books)")
    print("   3. Update tests")
    print("   4. Deploy to production")
    print("   5. Notify frontend team of breaking changes")
    print()
    
    return True


if __name__ == "__main__":
    try:
        success = migrate_guides_to_books()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Migration failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
