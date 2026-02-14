#!/usr/bin/env python3
"""
Generate Cover Images for Conversation Tests

Uses Gemini 3 Pro Image to generate 16:9 test covers from cover_image_prompt field
Uploads to R2 and updates marketplace_config.cover_image_url

RUN LOCALLY (requires env vars):
    python crawler/generate_conversation_test_covers.py

RUN ON PRODUCTION:
    ssh root@104.248.147.155 "docker cp /home/hoile/wordai/crawler/generate_conversation_test_covers.py ai-chatbot-rag:/app/crawler/ && docker exec ai-chatbot-rag python crawler/generate_conversation_test_covers.py"
"""

import os
import sys
import asyncio
import base64
from datetime import datetime
from typing import Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.db_manager import DBManager
from src.services.gemini_test_cover_service import get_gemini_test_cover_service


async def generate_and_upload_cover(
    test_id: str,
    title: str,
    cover_prompt: str,
    gemini_service,
) -> Optional[Dict]:
    """
    Generate cover image and upload to R2

    Returns:
        Dict with cover_url and file_id, or None if failed
    """
    try:
        print(f"\n🎨 Generating cover for: {title}")
        print(f"   Prompt: {cover_prompt[:80]}...")

        # Generate cover using Gemini 3 Pro Image
        result = await gemini_service.generate_test_cover(
            title=title,
            description=cover_prompt,
            style="minimal, modern, educational",
        )

        print(f"✅ Generated image ({len(result['image_base64'])} bytes)")

        # Decode base64
        image_bytes = base64.b64decode(result["image_base64"])

        # Upload to R2
        filename = f"test_{test_id}_cover_v1.png"
        upload_result = await gemini_service.upload_cover_to_r2(
            image_bytes=image_bytes,
            test_id=test_id,
            filename=filename,
        )

        print(f"☁️  Uploaded to R2: {upload_result['cover_url']}")

        return {
            "cover_url": upload_result["cover_url"],
            "file_id": upload_result.get("file_id"),
        }

    except Exception as e:
        print(f"❌ Failed to generate cover: {e}")
        import traceback

        traceback.print_exc()
        return None


async def main():
    """Main function"""

    print("\n" + "=" * 80)
    print("🎨 GENERATE COVER IMAGES FOR CONVERSATION TESTS")
    print("=" * 80)

    db_manager = DBManager()
    db = db_manager.db

    # Get Gemini service
    try:
        gemini_service = get_gemini_test_cover_service()
    except Exception as e:
        print(f"❌ Failed to initialize Gemini service: {e}")
        print("Make sure GEMINI_API_KEY and R2 credentials are set in environment")
        return

    # Find conversation tests without cover images
    query = {
        "source_type": "conversation",
        "$or": [
            {"marketplace_config.cover_image_url": None},
            {"marketplace_config.cover_image_url": {"$exists": False}},
        ],
    }

    tests = list(db.online_tests.find(query))
    print(f"\nFound {len(tests)} conversation tests without cover images")

    if len(tests) == 0:
        print("✅ All tests already have cover images!")
        return

    results = []

    for test in tests:
        test_id = str(test["_id"])
        title = test.get("title", "Untitled Test")
        cover_prompt = test.get("cover_image_prompt")

        if not cover_prompt:
            print(f"\n⚠️  Test {test_id} has no cover_image_prompt, skipping")
            continue

        # Generate and upload
        result = await generate_and_upload_cover(
            test_id=test_id,
            title=title,
            cover_prompt=cover_prompt,
            gemini_service=gemini_service,
        )

        if result:
            # Update database
            db.online_tests.update_one(
                {"_id": test["_id"]},
                {
                    "$set": {
                        "marketplace_config.cover_image_url": result["cover_url"],
                        "marketplace_config.updated_at": datetime.utcnow(),
                    }
                },
            )

            print(f"✅ Updated test {test_id} with cover image")

            results.append(
                {
                    "test_id": test_id,
                    "title": title,
                    "cover_url": result["cover_url"],
                }
            )

        # Small delay to avoid rate limits
        await asyncio.sleep(2)

    # Summary
    print("\n\n" + "=" * 80)
    print("📊 GENERATION SUMMARY")
    print("=" * 80)

    for result in results:
        print(f"\n✅ {result['title']}")
        print(f"   Test ID: {result['test_id']}")
        print(f"   Cover: {result['cover_url']}")

    print(f"\n\n✅ Generated {len(results)} cover images!")


if __name__ == "__main__":
    asyncio.run(main())
