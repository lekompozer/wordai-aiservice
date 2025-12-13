#!/usr/bin/env python3
"""
Check how many questions in database need field name migration
Analyzes online_tests collection for questions using old field names

Date: December 13, 2025
Author: System Migration Script
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


def connect_db():
    """Connect to MongoDB using application config"""
    # Use authenticated URI if available (production), fallback to basic URI (development)
    mongo_uri = getattr(config, "MONGODB_URI_AUTH", None) or getattr(
        config, "MONGODB_URI", "mongodb://localhost:27017"
    )
    db_name = getattr(config, "MONGODB_NAME", "ai_service_db")

    print(f"🔗 Connecting to MongoDB...")
    print(f"   URI: {mongo_uri[:50]}...")
    print(f"   Database: {db_name}")
    print()

    client = MongoClient(mongo_uri)
    db = client[db_name]
    return db


def analyze_questions():
    """Analyze questions that need migration"""
    db = connect_db()
    collection = db["online_tests"]

    print("=" * 80)
    print("🔍 FIELD NAME MIGRATION ANALYSIS")
    print("=" * 80)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Collection: online_tests")
    print()

    # Get all tests
    total_tests = collection.count_documents({})
    print(f"📊 Total tests in database: {total_tests}")
    print()

    # Statistics
    tests_need_migration = 0
    questions_need_migration = 0

    # Field usage statistics
    field_stats = {
        "correct_answer_keys": {"tests": 0, "questions": 0, "types": []},
        "correct_answer_key": {"tests": 0, "questions": 0, "types": []},
        "correct_matches": {"tests": 0, "questions": 0, "types": []},
        "correct_answers": {"tests": 0, "questions": 0, "types": []},  # Already correct
    }

    # Question type breakdown
    type_breakdown = {}

    # Analyze each test
    for test in collection.find({}):
        test_id = str(test["_id"])
        test_has_old_fields = False

        questions = test.get("questions", [])
        if not questions:
            continue

        for q in questions:
            question_type = q.get("question_type", "mcq")

            # Track question types
            if question_type not in type_breakdown:
                type_breakdown[question_type] = {
                    "total": 0,
                    "need_migration": 0,
                    "old_fields_used": [],
                }
            type_breakdown[question_type]["total"] += 1

            # Check for old field names
            needs_migration = False

            # Check correct_answer_keys (MCQ types should use correct_answers)
            if "correct_answer_keys" in q:
                field_stats["correct_answer_keys"]["questions"] += 1
                if question_type not in field_stats["correct_answer_keys"]["types"]:
                    field_stats["correct_answer_keys"]["types"].append(question_type)
                needs_migration = True
                test_has_old_fields = True
                if (
                    "correct_answer_keys"
                    not in type_breakdown[question_type]["old_fields_used"]
                ):
                    type_breakdown[question_type]["old_fields_used"].append(
                        "correct_answer_keys"
                    )

            # Check correct_answer_key (singular, legacy)
            if "correct_answer_key" in q:
                field_stats["correct_answer_key"]["questions"] += 1
                if question_type not in field_stats["correct_answer_key"]["types"]:
                    field_stats["correct_answer_key"]["types"].append(question_type)
                needs_migration = True
                test_has_old_fields = True
                if (
                    "correct_answer_key"
                    not in type_breakdown[question_type]["old_fields_used"]
                ):
                    type_breakdown[question_type]["old_fields_used"].append(
                        "correct_answer_key"
                    )

            # Check correct_matches (matching type should use correct_answers)
            if "correct_matches" in q:
                field_stats["correct_matches"]["questions"] += 1
                if question_type not in field_stats["correct_matches"]["types"]:
                    field_stats["correct_matches"]["types"].append(question_type)
                needs_migration = True
                test_has_old_fields = True
                if (
                    "correct_matches"
                    not in type_breakdown[question_type]["old_fields_used"]
                ):
                    type_breakdown[question_type]["old_fields_used"].append(
                        "correct_matches"
                    )

            # Check if already using correct_answers (good!)
            if "correct_answers" in q:
                field_stats["correct_answers"]["questions"] += 1
                if question_type not in field_stats["correct_answers"]["types"]:
                    field_stats["correct_answers"]["types"].append(question_type)

            if needs_migration:
                questions_need_migration += 1
                type_breakdown[question_type]["need_migration"] += 1

        if test_has_old_fields:
            tests_need_migration += 1
            field_stats["correct_answer_keys"]["tests"] += (
                1 if any("correct_answer_keys" in q for q in questions) else 0
            )
            field_stats["correct_answer_key"]["tests"] += (
                1 if any("correct_answer_key" in q for q in questions) else 0
            )
            field_stats["correct_matches"]["tests"] += (
                1 if any("correct_matches" in q for q in questions) else 0
            )

    # Print summary
    print("📊 MIGRATION SUMMARY")
    print("-" * 80)
    print(f"✅ Tests with correct field names: {total_tests - tests_need_migration}")
    print(f"⚠️  Tests need migration: {tests_need_migration}")
    print(f"⚠️  Questions need migration: {questions_need_migration}")
    print()

    print("📋 FIELD USAGE BREAKDOWN")
    print("-" * 80)
    for field_name, stats in field_stats.items():
        if stats["questions"] > 0:
            status = "✅ CORRECT" if field_name == "correct_answers" else "⚠️  OLD"
            print(f"{status} {field_name}:")
            print(f"   - Tests using: {stats['tests']}")
            print(f"   - Questions using: {stats['questions']}")
            print(
                f"   - Question types: {', '.join(stats['types']) if stats['types'] else 'N/A'}"
            )
            print()

    print("📊 QUESTION TYPE BREAKDOWN")
    print("-" * 80)
    for q_type, stats in sorted(type_breakdown.items()):
        print(f"{q_type}:")
        print(f"   - Total questions: {stats['total']}")
        print(f"   - Need migration: {stats['need_migration']}")
        if stats["old_fields_used"]:
            print(f"   - Old fields used: {', '.join(stats['old_fields_used'])}")
        print()

    # Migration impact assessment
    print("⚡ MIGRATION IMPACT")
    print("-" * 80)
    migration_percentage = (
        (tests_need_migration / total_tests * 100) if total_tests > 0 else 0
    )
    print(f"Migration scope: {migration_percentage:.1f}% of tests")
    print(f"Estimated time: ~{tests_need_migration * 0.5:.1f} seconds")
    print()

    # Risk assessment
    print("🔍 RISK ASSESSMENT")
    print("-" * 80)
    if questions_need_migration == 0:
        print("✅ No migration needed - all questions use correct field names!")
    elif questions_need_migration < 100:
        print("🟢 LOW RISK - Small number of questions affected")
    elif questions_need_migration < 1000:
        print("🟡 MEDIUM RISK - Moderate migration scope")
    else:
        print("🔴 HIGH RISK - Large migration scope, recommend backup first")
    print()

    # Next steps
    print("📝 NEXT STEPS")
    print("-" * 80)
    if questions_need_migration > 0:
        print("1. Review migration script: migrate_question_field_names.py")
        print("2. Backup database: mongodump --db wordai --out /backup/pre-migration")
        print("3. Run migration in test mode first (dry-run)")
        print("4. Execute migration: python migrate_question_field_names.py")
        print("5. Verify results: python check_questions_need_migration.py")
    else:
        print("✅ No action needed - database is already up to date!")
    print()

    return {
        "total_tests": total_tests,
        "tests_need_migration": tests_need_migration,
        "questions_need_migration": questions_need_migration,
        "field_stats": field_stats,
        "type_breakdown": type_breakdown,
    }


if __name__ == "__main__":
    try:
        results = analyze_questions()
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
