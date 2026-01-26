#!/usr/bin/env python3
"""
Create MongoDB indexes for Code Editor collections

Run this script to set up database indexes for optimal query performance.

Usage:
    python create_code_editor_indexes.py
"""

from src.database.db_manager import DBManager


def create_code_editor_indexes():
    """Create all indexes for Code Editor collections"""
    db_manager = DBManager()
    db = db_manager.db

    print("🔧 Creating Code Editor indexes...")

    # ==================== CODE FILES ====================
    print("\n📁 Creating code_files indexes...")

    # User's files query
    db.code_files.create_index([("user_id", 1), ("deleted_at", 1)])
    print("  ✅ user_id + deleted_at")

    # Folder filtering
    db.code_files.create_index([("user_id", 1), ("folder_id", 1)])
    print("  ✅ user_id + folder_id")

    # Language filtering
    db.code_files.create_index([("user_id", 1), ("language", 1)])
    print("  ✅ user_id + language")

    # Tags search
    db.code_files.create_index([("tags", 1)])
    print("  ✅ tags")

    # Public files discovery
    db.code_files.create_index([("is_public", 1), ("created_at", -1)])
    print("  ✅ is_public + created_at")

    # Sorting by updated_at
    db.code_files.create_index([("user_id", 1), ("updated_at", -1)])
    print("  ✅ user_id + updated_at")

    # Sorting by run_count
    db.code_files.create_index([("user_id", 1), ("metadata.run_count", -1)])
    print("  ✅ user_id + run_count")

    # Text search on name and description
    db.code_files.create_index([("name", "text"), ("description", "text")])
    print("  ✅ text search (name, description)")

    # ==================== CODE FOLDERS ====================
    print("\n📂 Creating code_folders indexes...")

    # User's folders
    db.code_folders.create_index([("user_id", 1)])
    print("  ✅ user_id")

    # Nested folders
    db.code_folders.create_index([("user_id", 1), ("parent_id", 1)])
    print("  ✅ user_id + parent_id")

    # Language filter
    db.code_folders.create_index([("user_id", 1), ("language_filter", 1)])
    print("  ✅ user_id + language_filter")

    # ==================== CODE TEMPLATES (Phase 2) ====================
    print("\n📋 Creating code_templates indexes...")

    # Language + category filtering
    db.code_templates.create_index([("programming_language", 1), ("category", 1)])
    print("  ✅ programming_language + category")

    # Difficulty filtering
    db.code_templates.create_index([("difficulty", 1)])
    print("  ✅ difficulty")

    # Featured templates
    db.code_templates.create_index([("is_featured", 1), ("metadata.usage_count", -1)])
    print("  ✅ is_featured + usage_count")

    # Tags search
    db.code_templates.create_index([("tags", 1)])
    print("  ✅ tags")

    # Active templates
    db.code_templates.create_index([("is_active", 1)])
    print("  ✅ is_active")

    # Text search
    db.code_templates.create_index([("title", "text"), ("description", "text")])
    print("  ✅ text search (title, description)")

    # ==================== CODE TEMPLATE CATEGORIES ====================
    print("\n📚 Creating code_template_categories indexes...")

    # Language categories
    db.code_template_categories.create_index([("language", 1), ("order", 1)])
    print("  ✅ language + order")

    # Active categories
    db.code_template_categories.create_index([("is_active", 1)])
    print("  ✅ is_active")

    # ==================== CODE EXERCISES (Phase 4) ====================
    print("\n🎯 Creating code_exercises indexes...")

    # Language + difficulty
    db.code_exercises.create_index([("language", 1), ("difficulty", 1)])
    print("  ✅ language + difficulty")

    # Category filtering
    db.code_exercises.create_index([("category", 1)])
    print("  ✅ category")

    # Published exercises
    db.code_exercises.create_index([("is_published", 1), ("created_at", -1)])
    print("  ✅ is_published + created_at")

    # Text search
    db.code_exercises.create_index([("title", "text"), ("description", "text")])
    print("  ✅ text search (title, description)")

    # ==================== CODE SUBMISSIONS ====================
    print("\n📝 Creating code_submissions indexes...")

    # User submissions
    db.code_submissions.create_index([("user_id", 1), ("submitted_at", -1)])
    print("  ✅ user_id + submitted_at")

    # Exercise submissions
    db.code_submissions.create_index([("exercise_id", 1), ("submitted_at", -1)])
    print("  ✅ exercise_id + submitted_at")

    # User + exercise (for progress tracking)
    db.code_submissions.create_index([("user_id", 1), ("exercise_id", 1)])
    print("  ✅ user_id + exercise_id")

    # Status filtering
    db.code_submissions.create_index([("status", 1)])
    print("  ✅ status")

    # ==================== EXERCISE PROGRESS ====================
    print("\n📈 Creating exercise_progress indexes...")

    # User progress
    db.exercise_progress.create_index([("user_id", 1), ("exercise_id", 1)], unique=True)
    print("  ✅ user_id + exercise_id (UNIQUE)")

    # User stats
    db.exercise_progress.create_index([("user_id", 1), ("status", 1)])
    print("  ✅ user_id + status")

    # Exercise completion rate
    db.exercise_progress.create_index([("exercise_id", 1), ("status", 1)])
    print("  ✅ exercise_id + status")

    # ==================== CODE SHARES (Phase 5) ====================
    print("\n🔗 Creating code_shares indexes...")

    # Share code lookup
    db.code_shares.create_index([("share_code", 1)], unique=True)
    print("  ✅ share_code (UNIQUE)")

    # User's shared files
    db.code_shares.create_index([("user_id", 1), ("created_at", -1)])
    print("  ✅ user_id + created_at")

    # File shares
    db.code_shares.create_index([("file_id", 1)])
    print("  ✅ file_id")

    # Active shares (not expired)
    db.code_shares.create_index([("expires_at", 1), ("is_active", 1)])
    print("  ✅ expires_at + is_active")

    # ==================== CODE ANALYTICS (Phase 6) ====================
    print("\n📊 Creating code_analytics indexes...")

    # User analytics
    db.code_analytics.create_index([("user_id", 1), ("date", -1)])
    print("  ✅ user_id + date")

    # File analytics
    db.code_analytics.create_index([("file_id", 1), ("date", -1)])
    print("  ✅ file_id + date")

    # Event type
    db.code_analytics.create_index([("event_type", 1), ("created_at", -1)])
    print("  ✅ event_type + created_at")

    # ==================== USER ACHIEVEMENTS (Phase 6) ====================
    print("\n🏆 Creating user_achievements indexes...")

    # User achievements
    db.user_achievements.create_index([("user_id", 1), ("earned_at", -1)])
    print("  ✅ user_id + earned_at")

    # Achievement type
    db.user_achievements.create_index([("achievement_type", 1)])
    print("  ✅ achievement_type")

    # User + achievement (no duplicates)
    db.user_achievements.create_index(
        [("user_id", 1), ("achievement_type", 1)], unique=True
    )
    print("  ✅ user_id + achievement_type (UNIQUE)")

    print("\n✅ All Code Editor indexes created successfully!")
    print("\n📋 Summary:")
    print("  - code_files: 8 indexes")
    print("  - code_folders: 3 indexes")
    print("  - code_templates: 6 indexes")
    print("  - code_template_categories: 2 indexes")
    print("  - code_exercises: 4 indexes")
    print("  - code_submissions: 4 indexes")
    print("  - exercise_progress: 3 indexes")
    print("  - code_shares: 4 indexes")
    print("  - code_analytics: 3 indexes")
    print("  - user_achievements: 3 indexes")
    print("  Total: 40 indexes\n")


if __name__ == "__main__":
    create_code_editor_indexes()
