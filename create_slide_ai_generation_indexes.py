"""
Create database indexes for slide AI generation system.

This script creates the necessary MongoDB indexes for the slide_analyses collection
to support efficient queries for the AI slide generation feature.
"""

import sys
import os
from pymongo import ASCENDING, DESCENDING

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config.database import get_database


def create_slide_ai_generation_indexes():
    """Create indexes for slide_analyses collection."""
    db = get_database()
    collection = db.slide_analyses

    print("Creating indexes for slide_analyses collection...")

    # Index 1: User queries (for listing user's analyses)
    # Used in: GET /api/slides/ai-generate/analyses?user_id=xxx
    collection.create_index(
        [("user_id", ASCENDING), ("created_at", DESCENDING)], name="user_analyses_idx"
    )
    print("✅ Created index: user_analyses_idx (user_id + created_at)")

    # Index 2: Analysis lookup for Step 2
    # Used in: POST /api/slides/ai-generate/create (needs to verify analysis_id belongs to user)
    collection.create_index(
        [("_id", ASCENDING), ("user_id", ASCENDING)], name="analysis_user_lookup_idx"
    )
    print("✅ Created index: analysis_user_lookup_idx (_id + user_id)")

    # Index 3: Recent analyses by slide type (for analytics/recommendations)
    collection.create_index(
        [("slide_type", ASCENDING), ("created_at", DESCENDING)], name="type_recent_idx"
    )
    print("✅ Created index: type_recent_idx (slide_type + created_at)")

    # List all indexes
    print("\n📋 All indexes in slide_analyses collection:")
    for index in collection.list_indexes():
        print(f"  - {index['name']}: {index['key']}")

    print("\n✅ All indexes created successfully!")


if __name__ == "__main__":
    create_slide_ai_generation_indexes()
