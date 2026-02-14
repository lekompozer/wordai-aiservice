#!/usr/bin/env python3
"""
Fix marketplace_config for 3 conversation tests
Add all missing fields to match production tests
"""

import sys
import os
from datetime import datetime

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
    level = test["conversation_level"]
    num_questions = len(test.get("questions", []))

    # Generate descriptions
    short_desc = f"Test your {level} English with {num_questions} questions on {title.replace('Vocabulary & Grammar Test: ', '')}"
    if len(short_desc) > 160:
        short_desc = short_desc[:157] + "..."

    meta_desc = f"{level.capitalize()} English test: {title.replace('Vocabulary & Grammar Test: ', '')}. {num_questions} IELTS-style questions. Free practice test."
    if len(meta_desc) > 160:
        meta_desc = meta_desc[:157] + "..."

    # Generate slug
    topic = test.get("conversation_topic", {})
    topic_text = topic.get("en", "unknown") if isinstance(topic, dict) else str(topic)
    conv_id = test["conversation_id"]
    slug = f"test-{level}-{topic_text.lower().replace(' ', '-').replace('&', 'and')}-{conv_id.split('_')[-1]}"

    # Update marketplace_config
    now = datetime.utcnow()
    update_result = db.online_tests.update_one(
        {"_id": test_id},
        {
            "$set": {
                # ✅ Root level fields (for endpoint compatibility)
                "slug": slug,
                "meta_description": meta_desc,
                # Marketplace config
                "marketplace_config.version": "v1",
                "marketplace_config.title": title,
                "marketplace_config.description": test.get("description", ""),
                "marketplace_config.short_description": short_desc,
                "marketplace_config.price_points": 1,  # ✅ 1 point per test
                "marketplace_config.difficulty_level": level,  # ✅ beginner/intermediate/advanced (NOT easy/medium/hard)
                "marketplace_config.tags": [
                    level,
                    "vocabulary",
                    "grammar",
                    "conversation",
                    "IELTS",
                    "test",
                ],
                "marketplace_config.published_at": test.get("created_at", now),
                "marketplace_config.total_participants": 0,
                "marketplace_config.total_earnings": 0,
                "marketplace_config.average_rating": 0,
                "marketplace_config.rating_count": 0,
                "marketplace_config.average_participant_score": 0,
                "marketplace_config.avg_rating": 0,
                "marketplace_config.slug": slug,
                "marketplace_config.meta_description": meta_desc,
                "marketplace_config.updated_at": now,
            }
        },
    )

    print(f"✅ Updated: {title[:60]}")
    print(f"   Slug: {slug}")
    print(f"   Level: {level}")
    print()

# Verify
print("\n=== VERIFICATION ===")
for test in db.online_tests.find({"source_type": "conversation"}):
    mc = test.get("marketplace_config", {})
    print(f"{test['title'][:50]}:")
    print(f"  - is_public: {mc.get('is_public')}")
    print(f"  - version: {mc.get('version')}")
    print(f"  - slug: {mc.get('slug')}")
    print(f"  - difficulty_level: {mc.get('difficulty_level')}")
    print(f"  - tags: {len(mc.get('tags', []))} tags")
    print()

print("✅ All conversation tests updated!")
