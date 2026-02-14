#!/usr/bin/env python3
"""
Add question_id, question_number, and questions array to conversation test questions
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.db_manager import DBManager

db_manager = DBManager()
db = db_manager.db

# Get all conversation tests
tests = list(db.online_tests.find({"source_type": "conversation"}))

print(f"Found {len(tests)} conversation tests\n")

for test in tests:
    test_id = test["_id"]
    title = test["title"]
    questions = test.get("questions", [])
    
    updated = False
    
    for idx, q in enumerate(questions, 1):
        if "question_id" not in q:
            q["question_id"] = f"q{idx}"
            q["question_number"] = idx
            updated = True
        
        if "questions" not in q:
            q["questions"] = []
            updated = True
    
    if updated:
        db.online_tests.update_one(
            {"_id": test_id},
            {"$set": {"questions": questions}}
        )
        print(f"✅ Updated: {title} ({len(questions)} questions)")
    else:
        print(f"⏭️  Skipped: {title} (already has question_id)")

print("\n✅ Done!")
