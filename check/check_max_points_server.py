import os
from pymongo import MongoClient
from bson import ObjectId
import sys

test_id = sys.argv[1] if len(sys.argv) > 1 else "692c0ce9eabefddaa798357c"
mongo_uri = os.getenv("MONGODB_URI_AUTH", "mongodb://localhost:27017/")
db_name = os.getenv("MONGODB_NAME", "ai_service_db")

client = MongoClient(mongo_uri)
db = client[db_name]

test = db.online_tests.find_one({"_id": ObjectId(test_id)})

if test:
    questions = test.get("questions", [])
    with_points = sum(1 for q in questions if "max_points" in q)
    without_points = len(questions) - with_points

    print(f"Test: {test.get('title')}")
    print(f"Category: {test.get('test_category')}")
    print(f"Total questions: {len(questions)}")
    print(f"With max_points: {with_points}")
    print(f"Without max_points: {without_points}")

    if questions:
        print("\nFirst 3 questions:")
        for i, q in enumerate(questions[:3], 1):
            mp = q.get("max_points", "MISSING")
            print(f"  Q{i}: max_points={mp}, text={q.get('question_text', '')[:40]}...")

    if without_points > 0:
        print(f"\nWARNING: {without_points} questions missing max_points!")
    else:
        print("\nAll questions have max_points!")
else:
    print("Test not found")
