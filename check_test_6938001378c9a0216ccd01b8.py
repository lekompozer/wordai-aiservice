"""Check test data in production database"""

from pymongo import MongoClient
from bson import ObjectId
import json

# Connect with authentication
client = MongoClient("mongodb://admin:ai_admin_2025_secure_password@mongodb:27017/")
db = client["ai_service_db"]

test_id = "6938001378c9a0216ccd01b8"
test = db.online_tests.find_one({"_id": ObjectId(test_id)})

if test:
    print("=== TEST METADATA ===")
    print(f"Title: {test.get('title')}")
    print(f"Num Questions: {test.get('num_questions')}")
    print(f"Test Type: {test.get('test_type')}")
    print(f"User Query: {test.get('user_query')}")
    print(f"\n=== QUESTIONS ({len(test.get('questions', []))}) ===")

    for idx, q in enumerate(test.get("questions", []), 1):
        print(f"\n--- Question {idx} ---")
        print(f"Question ID: {q.get('question_id')}")
        print(f"Type: {q.get('question_type')}")
        print(f"Text: {q.get('question_text')}")
        print(f"Instruction: {q.get('instruction')}")
        print(f"Audio Section: {q.get('audio_section')}")

        # Print type-specific fields
        if q.get("question_type") == "completion":
            print(f"Template: {q.get('template')}")
            print(
                f"Blanks: {json.dumps(q.get('blanks'), ensure_ascii=False, indent=2)}"
            )
            print(
                f"Correct Answers: {json.dumps(q.get('correct_answers'), ensure_ascii=False, indent=2)}"
            )
        elif q.get("question_type") == "matching":
            print(
                f"Left Items: {json.dumps(q.get('left_items'), ensure_ascii=False, indent=2)}"
            )
            print(
                f"Right Options: {json.dumps(q.get('right_options'), ensure_ascii=False, indent=2)}"
            )
            print(
                f"Correct Matches: {json.dumps(q.get('correct_matches'), ensure_ascii=False, indent=2)}"
            )
        elif q.get("question_type") == "mcq":
            print(
                f"Options: {json.dumps(q.get('options'), ensure_ascii=False, indent=2)}"
            )
            print(f"Correct Answer Keys: {q.get('correct_answer_keys')}")
        elif q.get("question_type") == "short_answer":
            print(
                f"Questions: {json.dumps(q.get('questions'), ensure_ascii=False, indent=2)}"
            )
        elif q.get("question_type") == "sentence_completion":
            print(
                f"Sentences: {json.dumps(q.get('sentences'), ensure_ascii=False, indent=2)}"
            )

    print(f"\n=== AUDIO SECTIONS ({len(test.get('audio_sections', []))}) ===")
    for section in test.get("audio_sections", []):
        print(
            f"\nSection {section.get('section_number')}: {section.get('section_title')}"
        )
        print(f"Audio URL: {section.get('audio_url')}")
        print(f"Duration: {section.get('duration_seconds')}s")
        print(f"Questions in section: {len(section.get('questions', []))}")

        # Print questions in audio_sections
        for q_idx, q in enumerate(section.get("questions", []), 1):
            print(f"\n  Audio Section Question {q_idx}:")
            print(f"  Type: {q.get('question_type')}")
            print(f"  Text: {q.get('question_text')[:100]}...")
else:
    print("Test not found")
