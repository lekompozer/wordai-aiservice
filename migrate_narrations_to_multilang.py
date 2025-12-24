"""
Migration Script: Slide Narrations to Multi-Language System
Converts existing slide_narrations collection to new multi-language architecture
"""

import sys
import os
from datetime import datetime
from bson import ObjectId
from pymongo import MongoClient

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import config
import config.config as config

# Dry run mode
DRY_RUN = False  # Set to True to preview changes without executing


def connect_db():
    """Connect to MongoDB using application config"""
    # Use authenticated URI if available (production), fallback to basic URI (development)
    mongo_uri = getattr(config, "MONGODB_URI_AUTH", None) or getattr(
        config, "MONGODB_URI", "mongodb://localhost:27017"
    )
    db_name = getattr(config, "MONGODB_NAME", "ai_service_db")

    client = MongoClient(mongo_uri)
    db = client[db_name]
    return db


def migrate_narrations_to_multilang():
    """
    Migrate existing slide_narrations to multi-language structure

    Collections created:
    - presentation_subtitles
    - presentation_audio
    - presentation_sharing_config
    """

    print("=" * 80)
    print("MIGRATION: Slide Narrations → Multi-Language System")
    print("=" * 80)

    if DRY_RUN:
        print("\n⚠️  DRY RUN MODE - No changes will be made")
        print("Set DRY_RUN = False to execute migration\n")

    db = connect_db()

    # Collections
    slide_narrations = db.slide_narrations
    presentation_subtitles = db.presentation_subtitles
    presentation_audio = db.presentation_audio
    presentation_sharing_config = db.presentation_sharing_config

    # Statistics
    stats = {
        "total_narrations": 0,
        "subtitles_created": 0,
        "audio_files_created": 0,
        "sharing_configs_created": 0,
        "errors": 0,
    }

    # Get all slide narrations
    narrations = list(slide_narrations.find({}))
    stats["total_narrations"] = len(narrations)

    print(f"\nFound {stats['total_narrations']} narrations to migrate\n")

    for narration in narrations:
        try:
            narration_id = str(narration["_id"])
            presentation_id = narration["presentation_id"]
            user_id = narration["user_id"]
            language = narration.get("language", "vi")  # Default to Vietnamese
            version = narration.get("version", 1)
            mode = narration.get("mode", "presentation")

            print(f"Migrating narration {narration_id}...")
            print(f"  Presentation: {presentation_id}")
            print(f"  Language: {language}, Version: {version}")

            # ============================================================
            # 1. Create presentation_subtitles document
            # ============================================================

            subtitle_doc = {
                "presentation_id": presentation_id,
                "user_id": user_id,
                "language": language,
                "version": version,
                "mode": mode,
                "slides": [],  # Will populate below
                "status": narration.get("status", "completed"),
                "created_at": narration.get("created_at", datetime.utcnow()),
                "updated_at": narration.get("updated_at", datetime.utcnow()),
                "metadata": {
                    "total_slides": 0,
                    "word_count": 0,
                    "migrated_from": narration_id,
                },
            }

            # Convert slides format
            old_slides = narration.get("slides", [])
            new_slides = []
            total_words = 0

            for slide in old_slides:
                slide_index = slide.get("slide_index", 0)
                subtitles = slide.get("subtitles", [])

                # Convert subtitle format
                new_subtitles = []
                for subtitle in subtitles:
                    new_subtitle = {
                        "text": subtitle.get("text", ""),
                        "element_references": subtitle.get("element_references", ""),
                        "timestamp": subtitle.get("start_time"),  # Optional
                    }
                    new_subtitles.append(new_subtitle)
                    total_words += len(new_subtitle["text"].split())

                new_slides.append(
                    {
                        "slide_index": slide_index,
                        "subtitles": new_subtitles,
                    }
                )

            subtitle_doc["slides"] = new_slides
            subtitle_doc["metadata"]["total_slides"] = len(new_slides)
            subtitle_doc["metadata"]["word_count"] = total_words

            # Insert subtitle document
            if not DRY_RUN:
                result = presentation_subtitles.insert_one(subtitle_doc)
                subtitle_id = str(result.inserted_id)
            else:
                subtitle_id = "dry_run_id"

            stats["subtitles_created"] += 1

            print(f"  ✅ Created subtitle document: {subtitle_id}")

            # ============================================================
            # 2. Create presentation_audio documents
            # ============================================================

            audio_files = narration.get("audio_files", [])

            for audio_file in audio_files:
                slide_index = audio_file.get("slide_index", 0)
                audio_url = audio_file.get("audio_url", "")

                if not audio_url:
                    continue

                audio_doc = {
                    "presentation_id": presentation_id,
                    "subtitle_id": subtitle_id,
                    "user_id": user_id,
                    "language": language,
                    "version": version,
                    "slide_index": slide_index,
                    "audio_url": audio_url,
                    "audio_metadata": {
                        "duration_seconds": audio_file.get("duration", 0),
                        "file_size_bytes": audio_file.get("file_size", 0),
                        "format": audio_file.get("format", "mp3"),
                        "sample_rate": 44100,
                    },
                    "generation_method": "ai_generated",  # Assume AI generated
                    "voice_config": narration.get("voice_config"),
                    "status": "ready",
                    "created_at": narration.get("created_at", datetime.utcnow()),
                    "updated_at": narration.get("updated_at", datetime.utcnow()),
                }

                if not DRY_RUN:
                    result = presentation_audio.insert_one(audio_doc)
                stats["audio_files_created"] += 1

                print(f"  ✅ Created audio document for slide {slide_index}")

            # ============================================================
            # 3. Create presentation_sharing_config (if not exists)
            # ============================================================

            existing_config = presentation_sharing_config.find_one(
                {"presentation_id": presentation_id}
            )

            if not existing_config:
                sharing_config = {
                    "presentation_id": presentation_id,
                    "user_id": user_id,
                    "is_public": False,  # Default to private
                    "public_token": None,
                    "sharing_settings": {
                        "include_content": True,
                        "include_subtitles": True,
                        "include_audio": True,
                        "allowed_languages": [],  # All languages
                        "default_language": language,
                        "require_attribution": True,
                    },
                    "shared_with_users": [],
                    "access_stats": {
                        "total_views": 0,
                        "unique_visitors": 0,
                        "last_accessed": None,
                    },
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                    "expires_at": None,
                }

                if not DRY_RUN:
                    result = presentation_sharing_config.insert_one(sharing_config)
                stats["sharing_configs_created"] += 1

                print(f"  ✅ Created sharing config")
            else:
                print(f"  ℹ️  Sharing config already exists")

            # ============================================================
            # 4. Mark old narration as migrated (don't delete yet)
            # ============================================================

            if not DRY_RUN:
                slide_narrations.update_one(
                    {"_id": narration["_id"]},
                    {
                        "$set": {
                            "migrated": True,
                            "migrated_at": datetime.utcnow(),
                            "migrated_to_subtitle_id": subtitle_id,
                        }
                    },
                )

            print(f"  ✅ Marked narration as migrated\n")

        except Exception as e:
            print(f"  ❌ ERROR: {e}\n")
            stats["errors"] += 1
            continue

    # ============================================================
    # VERIFICATION
    # ============================================================

    print("\n" + "=" * 80)
    print("MIGRATION SUMMARY")
    print("=" * 80)
    print(f"Total narrations processed: {stats['total_narrations']}")
    print(f"Subtitles created: {stats['subtitles_created']}")
    print(f"Audio files created: {stats['audio_files_created']}")
    print(f"Sharing configs created: {stats['sharing_configs_created']}")
    print(f"Errors: {stats['errors']}")

    # Verify counts
    print("\n" + "=" * 80)
    print("VERIFICATION")
    print("=" * 80)

    old_count = slide_narrations.count_documents({})
    migrated_count = slide_narrations.count_documents({"migrated": True})
    subtitle_count = presentation_subtitles.count_documents({})
    audio_count = presentation_audio.count_documents({})
    sharing_count = presentation_sharing_config.count_documents({})

    print(f"Old narrations: {old_count}")
    print(f"Migrated: {migrated_count}")
    print(f"New subtitles: {subtitle_count}")
    print(f"New audio files: {audio_count}")
    print(f"Sharing configs: {sharing_count}")

    # Check for data loss
    if subtitle_count < migrated_count:
        print("\n⚠️  WARNING: Subtitle count less than migrated count!")
    else:
        print("\n✅ All narrations successfully migrated!")

    print("\n" + "=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print("1. Verify migrated data in new collections")
    print("2. Test new API endpoints with migrated data")
    print("3. Update frontend to use new API endpoints")
    print("4. After confirming everything works:")
    print("   - Keep old slide_narrations for rollback (1-2 weeks)")
    print("   - Then delete with: db.slide_narrations.deleteMany({migrated: true})")
    print("=" * 80)


if __name__ == "__main__":
    print("\nStarting migration...")
    print("This will:")
    print("  1. Create presentation_subtitles documents")
    print("  2. Create presentation_audio documents")
    print("  3. Create presentation_sharing_config documents")
    print("  4. Mark old narrations as migrated (NOT deleted)")
    print()

    confirm = input("Continue? (yes/no): ")

    if confirm.lower() == "yes":
        migrate_narrations_to_multilang()
    else:
        print("Migration cancelled")
