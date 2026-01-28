#!/usr/bin/env python3
"""
Create MongoDB indexes for Software Lab collections
Run: python create_software_lab_indexes.py
"""

from src.database.db_manager import DBManager
from datetime import datetime


def create_software_lab_indexes():
    """Create all indexes for Software Lab collections"""

    db_manager = DBManager()
    db = db_manager.db

    print("🔧 Creating Software Lab MongoDB Indexes...")

    # ========================================
    # 1. software_lab_projects
    # ========================================
    print("\n1️⃣ Creating indexes for software_lab_projects...")

    # User's projects sorted by updated_at
    db.software_lab_projects.create_index(
        [("user_id", 1), ("updated_at", -1)], name="user_projects_by_updated"
    )
    print("   ✅ user_projects_by_updated")

    # Filter by template
    db.software_lab_projects.create_index(
        [("template", 1)], name="projects_by_template"
    )
    print("   ✅ projects_by_template")

    # Public projects
    db.software_lab_projects.create_index(
        [("is_public", 1), ("created_at", -1)], name="public_projects"
    )
    print("   ✅ public_projects")

    # Unique project ID
    db.software_lab_projects.create_index(
        [("id", 1)], unique=True, name="unique_project_id"
    )
    print("   ✅ unique_project_id")

    # ========================================
    # 2. software_lab_files
    # ========================================
    print("\n2️⃣ Creating indexes for software_lab_files...")

    # Unique file path per project
    db.software_lab_files.create_index(
        [("project_id", 1), ("path", 1)], unique=True, name="unique_file_path"
    )
    print("   ✅ unique_file_path")

    # Files by language (for analytics)
    db.software_lab_files.create_index(
        [("project_id", 1), ("language", 1)], name="files_by_language"
    )
    print("   ✅ files_by_language")

    # Unique file ID
    db.software_lab_files.create_index([("id", 1)], unique=True, name="unique_file_id")
    print("   ✅ unique_file_id")

    # ========================================
    # 3. software_lab_templates
    # ========================================
    print("\n3️⃣ Creating indexes for software_lab_templates...")

    # Filter by category and difficulty
    db.software_lab_templates.create_index(
        [("category", 1), ("difficulty", 1)], name="templates_by_category_difficulty"
    )
    print("   ✅ templates_by_category_difficulty")

    # Active templates only
    db.software_lab_templates.create_index([("is_active", 1)], name="active_templates")
    print("   ✅ active_templates")

    # Unique template ID
    db.software_lab_templates.create_index(
        [("id", 1)], unique=True, name="unique_template_id"
    )
    print("   ✅ unique_template_id")

    # ========================================
    # 4. software_lab_template_files
    # ========================================
    print("\n4️⃣ Creating indexes for software_lab_template_files...")

    # Unique file path per template
    db.software_lab_template_files.create_index(
        [("template_id", 1), ("path", 1)], unique=True, name="unique_template_file_path"
    )
    print("   ✅ unique_template_file_path")

    # Unique template file ID
    db.software_lab_template_files.create_index(
        [("id", 1)], unique=True, name="unique_template_file_id"
    )
    print("   ✅ unique_template_file_id")

    # ========================================
    # 5. software_lab_snapshots
    # ========================================
    print("\n5️⃣ Creating indexes for software_lab_snapshots...")

    # Snapshots by project, sorted by created_at
    db.software_lab_snapshots.create_index(
        [("project_id", 1), ("created_at", -1)], name="snapshots_by_project"
    )
    print("   ✅ snapshots_by_project")

    # Unique snapshot ID
    db.software_lab_snapshots.create_index(
        [("id", 1)], unique=True, name="unique_snapshot_id"
    )
    print("   ✅ unique_snapshot_id")

    # ========================================
    # 6. software_lab_progress
    # ========================================
    print("\n6️⃣ Creating indexes for software_lab_progress...")

    # Unique progress per user-project
    db.software_lab_progress.create_index(
        [("user_id", 1), ("project_id", 1)],
        unique=True,
        name="unique_user_project_progress",
    )
    print("   ✅ unique_user_project_progress")

    # Recent projects by user
    db.software_lab_progress.create_index(
        [("user_id", 1), ("last_accessed_at", -1)], name="recent_user_projects"
    )
    print("   ✅ recent_user_projects")

    # Unique progress ID
    db.software_lab_progress.create_index(
        [("id", 1)], unique=True, name="unique_progress_id"
    )
    print("   ✅ unique_progress_id")

    print("\n✅ All Software Lab indexes created successfully!")
    print("\n📊 Collection Statistics:")

    # Show collection stats
    collections = [
        "software_lab_projects",
        "software_lab_files",
        "software_lab_templates",
        "software_lab_template_files",
        "software_lab_snapshots",
        "software_lab_progress",
    ]

    for collection_name in collections:
        count = db[collection_name].count_documents({})
        print(f"   {collection_name}: {count} documents")


if __name__ == "__main__":
    create_software_lab_indexes()
