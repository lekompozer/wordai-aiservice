#!/usr/bin/env python3
"""
Initialize MongoDB indexes for Slide Template System
Run this once to set up the database
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.db_manager import DBManager

def main():
    """Create indexes for slide_templates collection"""
    print("🔧 Initializing Slide Template System indexes...")
    
    db_manager = DBManager()
    db = db_manager.db
    collection = db["slide_templates"]
    
    # Drop existing indexes (except _id)
    print("📋 Dropping existing indexes...")
    try:
        indexes = collection.index_information()
        for index_name in indexes:
            if index_name != "_id_":
                collection.drop_index(index_name)
                print(f"   Dropped: {index_name}")
    except Exception as e:
        print(f"   Warning: {e}")
    
    # Create indexes
    print("\n📊 Creating new indexes...")
    
    # 1. User templates sorted by creation date
    collection.create_index([("user_id", 1), ("created_at", -1)])
    print("   ✅ Index: user_id + created_at (for listing)")
    
    # 2. Unique template_id
    collection.create_index("template_id", unique=True)
    print("   ✅ Index: template_id (unique)")
    
    # 3. Filter by category
    collection.create_index([("user_id", 1), ("category", 1)])
    print("   ✅ Index: user_id + category (for filtering)")
    
    # 4. Search by tags
    collection.create_index([("user_id", 1), ("tags", 1)])
    print("   ✅ Index: user_id + tags (for filtering)")
    
    # List all indexes
    print("\n📄 Current indexes:")
    for index_name, index_info in collection.index_information().items():
        print(f"   - {index_name}: {index_info['key']}")
    
    print("\n✅ Slide Template System indexes initialized successfully!")

if __name__ == "__main__":
    main()
