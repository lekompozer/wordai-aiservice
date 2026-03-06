"""
Create MongoDB indexes for pdf_chapter_jobs collection

Optimizes job status queries and auto-cleanup of old jobs.

Run:
    python create_pdf_chapter_jobs_indexes.py
"""

import os
from dotenv import load_dotenv
from src.database.db_manager import DBManager

# Load environment
load_dotenv()


def create_indexes():
    """Create indexes for pdf_chapter_jobs collection"""
    db_manager = DBManager()
    db = db_manager.db

    collection = db.pdf_chapter_jobs

    print("\n🔧 Creating indexes for pdf_chapter_jobs collection...")

    # 1. Job ID index (unique) - for job status queries
    collection.create_index("job_id", unique=True)
    print("✅ Created unique index on: job_id")

    # 2. User ID + Status index - for user's job list
    collection.create_index([("user_id", 1), ("status", 1)])
    print("✅ Created index on: user_id + status")

    # 3. Created timestamp (TTL) - auto-delete jobs after 7 days
    collection.create_index("created_at", expireAfterSeconds=604800)  # 7 days
    print("✅ Created TTL index on: created_at (7 days)")

    # 4. Updated timestamp - for sorting recent jobs
    collection.create_index("updated_at")
    print("✅ Created index on: updated_at")

    print("\n✅ All indexes created successfully!")
    print("\n📊 Collection stats:")
    stats = db.command("collStats", "pdf_chapter_jobs")
    print(f"   Documents: {stats.get('count', 0)}")
    print(f"   Size: {stats.get('size', 0) / 1024:.2f} KB")
    print(f"   Indexes: {stats.get('nindexes', 0)}")


if __name__ == "__main__":
    create_indexes()
