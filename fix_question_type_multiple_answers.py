#!/usr/bin/env python3
"""
Migration Script: Fix question_type for multiple-answer MCQ questions

PROBLEM: Existing tests in database have questions with multiple correct answers
but question_type='mcq' instead of 'mcq_multiple', causing frontend to display
radio buttons (single choice) when it should be checkboxes (multiple choice).

SOLUTION: Scan all tests and auto-correct question_type based on correct_answer_keys length.

Usage:
    python fix_question_type_multiple_answers.py --dry-run  # Preview changes
    python fix_question_type_multiple_answers.py            # Apply changes
    
    # In Docker production:
    docker exec -it ai-chatbot-rag python fix_question_type_multiple_answers.py --dry-run
    docker exec -it ai-chatbot-rag python fix_question_type_multiple_answers.py
"""

import sys
import os
from datetime import datetime
from bson import ObjectId
import argparse
import pymongo
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_mongodb_connection():
    """
    Try multiple MongoDB connection methods for Docker environment
    
    Returns:
        (client, db) or (None, None) if all methods fail
    """
    db_name = os.getenv("MONGODB_NAME", "ai_service_db")
    mongo_user = os.getenv("MONGODB_APP_USERNAME")
    mongo_pass = os.getenv("MONGODB_APP_PASSWORD")
    
    print(f"📊 Database: {db_name}")
    print(f"👤 User: {mongo_user}")
    print()
    
    # Try different connection methods
    connection_methods = [
        {
            "name": "Container name (mongodb)",
            "uri": f"mongodb://{mongo_user}:{mongo_pass}@mongodb:27017/{db_name}?authSource=admin",
        },
        {
            "name": "host.docker.internal",
            "uri": f"mongodb://{mongo_user}:{mongo_pass}@host.docker.internal:27017/{db_name}?authSource=admin",
        },
        {
            "name": "localhost",
            "uri": f"mongodb://{mongo_user}:{mongo_pass}@localhost:27017/{db_name}?authSource=admin",
        },
    ]
    
    for method in connection_methods:
        try:
            print(f"🔍 Trying: {method['name']}")
            client = pymongo.MongoClient(method["uri"], serverSelectionTimeoutMS=5000)
            # Test connection
            client.admin.command("ping")
            db = client[db_name]
            print(f"✅ Connected via {method['name']}")
            print()
            return client, db
        except Exception as e:
            print(f"   ❌ Failed: {e}")
            continue
    
    print()
    print("❌ All connection methods failed")
    return None, None

def fix_question_types(dry_run=True):
    """
    Fix question_type for all MCQ questions in database
    
    Args:
        dry_run: If True, only preview changes without updating database
    """
    
    print("=" * 80)
    print("🔍 QUESTION TYPE MIGRATION SCRIPT")
    print("=" * 80)
    print(f"Mode: {'DRY RUN (Preview Only)' if dry_run else 'LIVE UPDATE'}")
    print(f"Started at: {datetime.now().isoformat()}")
    print()
    
    # Connect to MongoDB
    client, db = get_mongodb_connection()
    if client is None or db is None:
        print("❌ Failed to connect to MongoDB")
        sys.exit(1)
    
    collection = db["online_tests"]
    
    # Find all active tests
    tests = list(collection.find({"is_active": {"$ne": False}}))
    
    print(f"📊 Found {len(tests)} active tests to scan")
    print()
    
    stats = {
        "tests_scanned": 0,
        "tests_updated": 0,
        "questions_fixed": 0,
        "mcq_to_multiple": 0,
        "multiple_to_mcq": 0,
    }
    
    updates_to_apply = []
    
    for test in tests:
        stats["tests_scanned"] += 1
        test_id = str(test["_id"])
        test_title = test.get("title", "Untitled")
        questions = test.get("questions", [])
        
        if not questions:
            continue
        
        test_modified = False
        fixed_questions = []
        
        for idx, q in enumerate(questions):
            question_type = q.get("question_type", "mcq")
            correct_answer_keys = q.get("correct_answer_keys", [])
            
            # Only process MCQ questions
            if question_type not in ["mcq", "mcq_multiple"]:
                fixed_questions.append(q)
                continue
            
            # Count correct answers
            if isinstance(correct_answer_keys, str):
                # Convert string to array
                correct_answer_keys = [correct_answer_keys]
                q["correct_answer_keys"] = correct_answer_keys
            
            num_correct = len(correct_answer_keys)
            
            # Determine correct question_type
            correct_type = "mcq" if num_correct == 1 else "mcq_multiple"
            
            if question_type != correct_type:
                # Need to fix
                old_type = question_type
                q["question_type"] = correct_type
                test_modified = True
                stats["questions_fixed"] += 1
                
                if correct_type == "mcq_multiple":
                    stats["mcq_to_multiple"] += 1
                else:
                    stats["multiple_to_mcq"] += 1
                
                print(f"   ⚠️  Question {idx + 1}: {q.get('question_text', '')[:60]}...")
                print(f"      Old type: {old_type}, Correct answers: {num_correct}")
                print(f"      New type: {correct_type}")
                print(f"      Answers: {correct_answer_keys}")
                print()
            
            fixed_questions.append(q)
        
        if test_modified:
            stats["tests_updated"] += 1
            print(f"✏️  Test: {test_title} (ID: {test_id})")
            print(f"   Fixed {sum(1 for q in fixed_questions if q.get('question_type') in ['mcq', 'mcq_multiple'])} questions")
            print()
            
            updates_to_apply.append({
                "test_id": test_id,
                "test_title": test_title,
                "questions": fixed_questions,
            })
    
    print()
    print("=" * 80)
    print("📊 MIGRATION SUMMARY")
    print("=" * 80)
    print(f"Tests scanned:        {stats['tests_scanned']}")
    print(f"Tests to update:      {stats['tests_updated']}")
    print(f"Questions fixed:      {stats['questions_fixed']}")
    print(f"  mcq → mcq_multiple: {stats['mcq_to_multiple']}")
    print(f"  mcq_multiple → mcq: {stats['multiple_to_mcq']}")
    print()
    
    if dry_run:
        print("⚠️  DRY RUN MODE - No changes applied to database")
        print("   Run without --dry-run to apply changes")
    else:
        print("💾 Applying updates to database...")
        
        for update in updates_to_apply:
            result = collection.update_one(
                {"_id": ObjectId(update["test_id"])},
                {
                    "$set": {
                        "questions": update["questions"],
                        "updated_at": datetime.now(),
                    }
                }
            )
            
            if result.modified_count > 0:
                print(f"   ✅ Updated: {update['test_title']}")
            else:
                print(f"   ❌ Failed: {update['test_title']}")
        
        print()
        print("✅ Migration completed successfully!")
    
    print()
    print(f"Finished at: {datetime.now().isoformat()}")
    print("=" * 80)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fix question_type for multiple-answer MCQ questions"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without updating database (default: False)",
    )
    
    args = parser.parse_args()
    
    try:
        fix_question_types(dry_run=args.dry_run)
    except KeyboardInterrupt:
        print("\n\n⚠️  Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
