"""Check test status in production database"""

from pymongo import MongoClient
from bson import ObjectId
import json

client = MongoClient("mongodb://admin:ai_admin_2025_secure_password@mongodb:27017/")
db = client["ai_service_db"]

test_id = "693836cf2ff90bfa69b28d9c"
test = db.online_tests.find_one({"_id": ObjectId(test_id)})

if test:
    print(f"Status: {test.get('status')}")
    print(f"Generation Status: {test.get('generation_status')}")
    print(f"Num Questions Setting: {test.get('num_questions')}")
    print(f"Actual Questions: {len(test.get('questions', []))}")
    print(f"Audio Sections: {len(test.get('audio_sections', []))}")

    if test.get("questions"):
        print("\n=== QUESTIONS ===")
        for i, q in enumerate(test["questions"], 1):
            print(f"Q{i}: {q.get('question_type')} - {q.get('question_text', '')[:60]}")

    error_msg = test.get("error_message")
    if error_msg:
        print(f"\nError: {error_msg}")
else:
    print("Test not found")
