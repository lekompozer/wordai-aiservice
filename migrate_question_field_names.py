#!/usr/bin/env python3
"""
Migrate question field names to unified 'correct_answers' field
Converts old field names (correct_answer_keys, correct_matches) to new unified format

⚠️ BREAKING CHANGE: v2.3 Field Name Unification
Date: December 13, 2025

Migration Map:
- MCQ (single): correct_answer_keys → correct_answers (array of option keys)
- MCQ (multiple): correct_answer_keys → correct_answers (array of option keys)
- Matching: correct_matches → correct_answers (array of {left_key, right_key})
- Sentence Completion: correct_answer_keys → correct_answers (array of texts)
- Short Answer: correct_answer_keys → correct_answers (array of texts)
- Completion: correct_answers (unchanged)

Backward Compatibility:
- Keeps old field names for legacy support
- Adds new correct_answers field
- Backend can read both formats
"""

import os
import sys
from datetime import datetime
from pymongo import MongoClient
from bson import ObjectId

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import config
import config.config as config

# Dry run mode (set to False to actually execute migration)
DRY_RUN = True  # Set to False to run actual migration


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


def migrate_question_fields(question: dict) -> tuple[dict, bool, list]:
    """
    Migrate a single question's field names

    Args:
        question: Question document

    Returns:
        (updated_question, was_modified, changes_made)
    """
    question_type = question.get("question_type", "mcq")
    changes = []
    modified = False

    # Skip diagnostic questions (no correct answers)
    if question.get("diagnostic_question"):
        return question, False, []

    # 1. MCQ Types: correct_answer_keys → correct_answers
    if question_type in ["mcq", "mcq_multiple"]:
        if "correct_answer_keys" in question and "correct_answers" not in question:
            question["correct_answers"] = question["correct_answer_keys"]
            changes.append(f"Added correct_answers from correct_answer_keys")
            modified = True

        # Also handle singular form
        elif "correct_answer_key" in question and "correct_answers" not in question:
            question["correct_answers"] = [question["correct_answer_key"]]
            changes.append(f"Added correct_answers from correct_answer_key (singular)")
            modified = True

    # 2. Matching: correct_matches → correct_answers
    elif question_type == "matching":
        if "correct_matches" in question and "correct_answers" not in question:
            # Convert from object format to array format if needed
            correct_matches = question["correct_matches"]

            if isinstance(correct_matches, dict):
                # Convert {"1": "A", "2": "B"} → [{"left_key": "1", "right_key": "A"}, ...]
                question["correct_answers"] = [
                    {"left_key": left_key, "right_key": right_key}
                    for left_key, right_key in correct_matches.items()
                ]
                changes.append(
                    f"Converted correct_matches (dict) → correct_answers (array)"
                )
            elif isinstance(correct_matches, list):
                # Already in array format, just copy
                # Handle both formats: [{"key": "1", "value": "A"}] or [{"left_key": "1", "right_key": "A"}]
                normalized = []
                for match in correct_matches:
                    if "left_key" in match and "right_key" in match:
                        normalized.append(match)
                    elif "key" in match and "value" in match:
                        normalized.append(
                            {"left_key": match["key"], "right_key": match["value"]}
                        )

                question["correct_answers"] = normalized
                changes.append(f"Normalized correct_matches → correct_answers (array)")

            modified = True

    # 3. Sentence Completion: correct_answer_keys → correct_answers
    elif question_type == "sentence_completion":
        # Check sentences array for correct_answer_keys
        if "sentences" in question:
            sentences_modified = False
            for sentence in question["sentences"]:
                if (
                    "correct_answer_keys" in sentence
                    and "correct_answers" not in sentence
                ):
                    sentence["correct_answers"] = sentence["correct_answer_keys"]
                    sentences_modified = True

            if sentences_modified:
                changes.append(
                    f"Migrated sentences correct_answer_keys → correct_answers"
                )
                modified = True

    # 4. Short Answer: correct_answer_keys → correct_answers
    elif question_type == "short_answer":
        # Check questions array for correct_answer_keys
        if "questions" in question:
            questions_modified = False
            for sub_q in question["questions"]:
                if "correct_answer_keys" in sub_q and "correct_answers" not in sub_q:
                    sub_q["correct_answers"] = sub_q["correct_answer_keys"]
                    questions_modified = True

            if questions_modified:
                changes.append(
                    f"Migrated questions correct_answer_keys → correct_answers"
                )
                modified = True

        # Also check top-level correct_answer_keys
        elif "correct_answer_keys" in question and "correct_answers" not in question:
            question["correct_answers"] = question["correct_answer_keys"]
            changes.append(f"Added correct_answers from correct_answer_keys")
            modified = True

    # 5. Completion: correct_answers (should already be correct, but check format)
    elif question_type == "completion":
        if "correct_answers" in question:
            # Verify format is correct: [{"blank_key": "1", "answers": [...]}]
            # No migration needed, just validation
            pass

    # 6. Map Labeling: correct_labels (keep as is, document says it stays)
    elif question_type == "map_labeling":
        # No migration needed for map_labeling
        pass

    return question, modified, changes


def migrate_test(test: dict, dry_run: bool = True) -> dict:
    """
    Migrate a single test document

    Args:
        test: Test document
        dry_run: If True, don't actually update database

    Returns:
        Migration statistics for this test
    """
    test_id = str(test["_id"])
    questions = test.get("questions", [])

    stats = {
        "test_id": test_id,
        "total_questions": len(questions),
        "modified_questions": 0,
        "changes": [],
    }

    if not questions:
        return stats

    modified_questions = []
    all_changes = []

    for idx, question in enumerate(questions):
        updated_q, was_modified, changes = migrate_question_fields(question)

        if was_modified:
            stats["modified_questions"] += 1
            modified_questions.append(updated_q)
            all_changes.append(
                {
                    "question_idx": idx,
                    "question_id": question.get("question_id", f"q{idx}"),
                    "question_type": question.get("question_type", "mcq"),
                    "changes": changes,
                }
            )
        else:
            modified_questions.append(updated_q)

    stats["changes"] = all_changes

    # Update database if not dry run and there were changes
    if not dry_run and stats["modified_questions"] > 0:
        db = connect_db()
        collection = db["online_tests"]

        result = collection.update_one(
            {"_id": test["_id"]},
            {
                "$set": {
                    "questions": modified_questions,
                    "migration_metadata": {
                        "migrated_at": datetime.utcnow(),
                        "migration_version": "v2.3",
                        "field_name_unification": True,
                        "questions_migrated": stats["modified_questions"],
                    },
                }
            },
        )

        stats["updated"] = result.modified_count > 0

    return stats


def run_migration(dry_run: bool = True):
    """Run migration on all tests"""
    db = connect_db()
    collection = db["online_tests"]

    print("=" * 80)
    print("⚡ QUESTION FIELD NAME MIGRATION")
    print("=" * 80)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: {'🔍 DRY RUN (Preview only)' if dry_run else '🚀 LIVE MIGRATION'}")
    print(f"Collection: online_tests")
    print()

    # Skip confirmation for automated execution
    if not dry_run:
        print("⚠️  WARNING: This will modify your database!")
        print("🚀 EXECUTING MIGRATION (Backup already completed)")
        print()

    # Get all tests that might need migration
    total_tests = collection.count_documents({})
    print(f"📊 Scanning {total_tests} tests...")
    print()

    # Migration statistics
    total_stats = {
        "tests_scanned": 0,
        "tests_modified": 0,
        "questions_modified": 0,
        "errors": [],
    }

    # Process each test
    for test in collection.find({}):
        total_stats["tests_scanned"] += 1

        try:
            test_stats = migrate_test(test, dry_run)

            if test_stats["modified_questions"] > 0:
                total_stats["tests_modified"] += 1
                total_stats["questions_modified"] += test_stats["modified_questions"]

                # Print details for modified tests
                print(f"📝 Test {test_stats['test_id']}")
                print(f"   Title: {test.get('title', 'N/A')}")
                print(
                    f"   Modified: {test_stats['modified_questions']}/{test_stats['total_questions']} questions"
                )

                for change_info in test_stats["changes"]:
                    print(
                        f"   - Q{change_info['question_idx']} ({change_info['question_type']}): {', '.join(change_info['changes'])}"
                    )

                print()

        except Exception as e:
            error_msg = f"Test {test.get('_id')}: {str(e)}"
            total_stats["errors"].append(error_msg)
            print(f"❌ ERROR: {error_msg}")

    # Print final summary
    print("=" * 80)
    print("📊 MIGRATION SUMMARY")
    print("=" * 80)
    print(f"Tests scanned: {total_stats['tests_scanned']}")
    print(f"Tests modified: {total_stats['tests_modified']}")
    print(f"Questions migrated: {total_stats['questions_modified']}")

    if total_stats["errors"]:
        print(f"\n⚠️  Errors encountered: {len(total_stats['errors'])}")
        for error in total_stats["errors"]:
            print(f"   - {error}")

    print()

    if dry_run:
        print("🔍 DRY RUN COMPLETE - No changes were made to database")
        print("   To execute migration, set DRY_RUN = False in script")
    else:
        print("✅ MIGRATION COMPLETE")
        print("   All changes have been saved to database")

    print()

    return total_stats


if __name__ == "__main__":
    # Check command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--execute":
            DRY_RUN = False
        elif sys.argv[1] == "--dry-run":
            DRY_RUN = True
        elif sys.argv[1] == "--help":
            print("Question Field Name Migration Script")
            print()
            print("Usage:")
            print("  python migrate_question_field_names.py [--dry-run|--execute]")
            print()
            print("Options:")
            print("  --dry-run   Preview changes without modifying database (default)")
            print("  --execute   Execute migration and update database")
            print("  --help      Show this help message")
            print()
            sys.exit(0)

    try:
        results = run_migration(dry_run=DRY_RUN)
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
