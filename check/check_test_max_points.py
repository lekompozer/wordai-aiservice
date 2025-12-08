#!/usr/bin/env python3
"""
Check if test has max_points field in questions
"""

import os
import sys
from pymongo import MongoClient
from bson import ObjectId

# Load .env
from dotenv import load_dotenv

load_dotenv()


def check_test(test_id):
    print(f"🔍 Checking test: {test_id}")

    # Connect to MongoDB
    mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
    db_name = os.getenv("MONGODB_NAME", "wordai_db")
    client = MongoClient(mongo_uri)
    db = client[db_name]

    try:
        test = db.online_tests.find_one({"_id": ObjectId(test_id)})

        if not test:
            print(f"❌ Test not found: {test_id}")
            return

        print(f"✅ Found test: {test.get('title')}")
        print(f"   Category: {test.get('test_category')}")
        print(f"   Status: {test.get('status')}")
        print(f"   Questions count: {len(test.get('questions', []))}")

        # Check questions for max_points
        questions = test.get("questions", [])
        if not questions:
            print("   ⚠️ No questions found")
            return

        with_points = sum(1 for q in questions if "max_points" in q)
        without_points = len(questions) - with_points

        print(f"\n📊 Max Points Summary:")
        print(f"   Total questions: {len(questions)}")
        print(f"   With max_points: {with_points}")
        print(f"   Without max_points: {without_points}")

        if with_points > 0:
            points_values = [
                q.get("max_points") for q in questions if "max_points" in q
            ]
            print(f"   Points range: {min(points_values)} - {max(points_values)}")
            print(f"   Total possible points: {sum(points_values)}")

        # Show first 3 questions
        print(f"\n📋 First 3 Questions:")
        for i, q in enumerate(questions[:3], 1):
            print(f"\n   Q{i}: {q.get('question_text', '')[:60]}...")
            print(f"      - question_id: {q.get('question_id', 'N/A')}")
            print(f"      - max_points: {q.get('max_points', '❌ MISSING')}")
            print(f"      - correct_answer_key: {q.get('correct_answer_key', 'N/A')}")

        if without_points > 0:
            print(f"\n   ⚠️ WARNING: {without_points} questions missing 'max_points'!")
            print(f"   ⚠️ This may cause incorrect scoring calculation.")
        else:
            print(f"\n   ✅ All questions have 'max_points' field!")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_id = sys.argv[1] if len(sys.argv) > 1 else "692c0ce9eabefddaa798357c"
    check_test(test_id)
