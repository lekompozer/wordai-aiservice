"""
Test Translation Routes
Translate existing tests to different languages using Gemini 2.5 Flash
"""

import logging
import time
from datetime import datetime
from bson import ObjectId
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from src.middleware.auth import verify_firebase_token as require_auth
from src.services.online_test_utils import get_mongodb_service

logger = logging.getLogger("chatbot")

router = APIRouter(prefix="/api/v1/tests", tags=["Test Translation"])


# ========== Request/Response Models ==========


class TranslateTestRequest(BaseModel):
    """Request model for translating a test to another language"""

    target_language: str = Field(
        ...,
        description="Target language code (e.g., 'en', 'vi', 'zh-CN', 'ja', 'ko', etc.)",
        min_length=2,
        max_length=10,
    )
    new_title: Optional[str] = Field(
        None,
        description="Optional new title for translated test (if not provided, will translate original title)",
        max_length=200,
    )


class TranslateTestResponse(BaseModel):
    """Response model for test translation"""

    success: bool
    test_id: str
    status: str  # 'pending' -> 'translating' -> 'ready'
    original_test_id: str
    target_language: str
    message: str
    created_at: str


# ========== Background Translation Job ==========


async def translate_test_background(
    test_id: str,
    original_test_id: str,
    target_language: str,
    original_test_doc: dict,
):
    """
    Background job to translate test content using Gemini 2.5 Flash
    Updates status: pending → translating → ready/failed
    """
    from pymongo import MongoClient
    from src.core.config import config

    mongo_uri = getattr(config, "MONGODB_URI_AUTH", None) or getattr(
        config, "MONGODB_URI", "mongodb://localhost:27017"
    )
    client = MongoClient(mongo_uri)
    db_name = getattr(config, "MONGODB_NAME", "wordai_db")
    db = client[db_name]
    collection = db["online_tests"]

    try:
        # Update status to translating
        collection.update_one(
            {"_id": ObjectId(test_id)},
            {
                "$set": {
                    "status": "translating",
                    "progress_percent": 10,
                    "updated_at": datetime.now(),
                }
            },
        )
        logger.info(f"🔄 Test {test_id}: Status updated to 'translating'")

        # Import Gemini service
        from src.services.gemini_service import get_gemini_service

        gemini_service = get_gemini_service()

        # Prepare content for translation
        questions = original_test_doc.get("questions", [])
        test_category = original_test_doc.get("test_category", "academic")

        logger.info(
            f"🌍 Translating test to {target_language}: {len(questions)} questions"
        )

        # Build translation prompt
        questions_json = []
        for q in questions:
            q_data = {
                "question_id": q.get("question_id"),
                "question_type": q.get("question_type", "mcq"),
                "question_text": q.get("question_text"),
            }

            if q.get("question_type") == "mcq":
                q_data["options"] = [
                    {
                        "key": opt.get("option_key") or opt.get("key"),
                        "text": opt.get("option_text") or opt.get("text"),
                    }
                    for opt in q.get("options", [])
                ]
                q_data["correct_answer_key"] = q.get("correct_answer_key")

            if q.get("explanation"):
                q_data["explanation"] = q.get("explanation")

            if q.get("grading_rubric"):
                q_data["grading_rubric"] = q.get("grading_rubric")

            questions_json.append(q_data)

        import json

        prompt = f"""You are a professional translator. Translate the following test content to {target_language}.

**IMPORTANT RULES:**
1. Translate ALL text content accurately while preserving meaning
2. Keep question_id, question_type, option keys (A, B, C, D) unchanged
3. Keep correct_answer_key unchanged
4. Maintain the same JSON structure
5. Translate: question_text, option text, explanation, grading_rubric
6. Use natural, fluent language appropriate for educational content
7. For technical terms, use commonly accepted translations in target language

**Original Test:**
Title: {original_test_doc.get('title', 'Untitled')}
Description: {original_test_doc.get('description', 'No description')}
Category: {test_category}
Language: {original_test_doc.get('test_language', 'unknown')}

**Questions to Translate:**
{json.dumps(questions_json, ensure_ascii=False, indent=2)}

**Output Format:**
Return a JSON object with this exact structure:
{{
  "title": "translated title",
  "description": "translated description",
  "questions": [
    {{
      "question_id": "keep original",
      "question_type": "keep original",
      "question_text": "translated text",
      "options": [
        {{"key": "A", "text": "translated option"}},
        {{"key": "B", "text": "translated option"}}
      ],
      "correct_answer_key": "keep original",
      "explanation": "translated explanation",
      "grading_rubric": "translated rubric (if exists)"
    }}
  ]
}}

Return ONLY valid JSON, no markdown, no code blocks."""

        # Call Gemini 2.5 Flash
        collection.update_one(
            {"_id": ObjectId(test_id)},
            {"$set": {"progress_percent": 30, "updated_at": datetime.now()}},
        )

        result = await gemini_service.generate_content(
            prompt=prompt,
            model_name="gemini-2.0-flash-exp",  # Use Flash for translation
            response_format="json",
        )

        # Parse response
        import json

        try:
            translated_data = json.loads(result)
        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse Gemini response: {e}")
            logger.error(f"Response: {result[:500]}")
            raise Exception(f"Invalid JSON response from AI: {str(e)}")

        # Update progress
        collection.update_one(
            {"_id": ObjectId(test_id)},
            {"$set": {"progress_percent": 80, "updated_at": datetime.now()}},
        )

        # Merge translated content with original structure
        translated_questions = []
        original_questions_dict = {
            q["question_id"]: q for q in original_test_doc.get("questions", [])
        }

        for trans_q in translated_data.get("questions", []):
            q_id = trans_q.get("question_id")
            orig_q = original_questions_dict.get(q_id, {})

            merged_q = {
                "question_id": q_id,
                "question_type": orig_q.get("question_type", "mcq"),
                "question_text": trans_q.get("question_text"),
            }

            # Merge MCQ fields
            if merged_q["question_type"] == "mcq":
                # Translate options while preserving keys
                translated_options = []
                for trans_opt in trans_q.get("options", []):
                    translated_options.append(
                        {
                            "option_key": trans_opt.get("key"),
                            "option_text": trans_opt.get("text"),
                        }
                    )
                merged_q["options"] = translated_options
                merged_q["correct_answer_key"] = orig_q.get("correct_answer_key")

            # Add optional fields
            if trans_q.get("explanation"):
                merged_q["explanation"] = trans_q.get("explanation")

            if merged_q["question_type"] == "essay":
                merged_q["max_points"] = orig_q.get("max_points", 1)
                if trans_q.get("grading_rubric"):
                    merged_q["grading_rubric"] = trans_q.get("grading_rubric")

            # Copy media fields if exist
            if orig_q.get("media_type"):
                merged_q["media_type"] = orig_q.get("media_type")
                merged_q["media_url"] = orig_q.get("media_url")
                merged_q["media_description"] = orig_q.get("media_description")

            translated_questions.append(merged_q)

        # Update test with translated content
        update_fields = {
            "title": translated_data.get("title", original_test_doc.get("title")),
            "description": translated_data.get(
                "description", original_test_doc.get("description")
            ),
            "test_language": target_language,
            "questions": translated_questions,
            "status": "ready",
            "progress_percent": 100,
            "translated_at": datetime.now(),
            "updated_at": datetime.now(),
        }

        collection.update_one(
            {"_id": ObjectId(test_id)},
            {"$set": update_fields},
        )

        logger.info(
            f"✅ Test {test_id}: Translation completed successfully to {target_language}"
        )

    except Exception as e:
        logger.error(f"❌ Test {test_id}: Translation failed: {e}", exc_info=True)
        collection.update_one(
            {"_id": ObjectId(test_id)},
            {
                "$set": {
                    "status": "failed",
                    "error_message": str(e),
                    "progress_percent": 0,
                    "updated_at": datetime.now(),
                }
            },
        )

    finally:
        client.close()


# ========== Endpoints ==========


@router.post("/{test_id}/translate", response_model=TranslateTestResponse)
async def translate_test(
    test_id: str,
    request: TranslateTestRequest,
    background_tasks: BackgroundTasks,
    user_info: dict = Depends(require_auth),
):
    """
    Translate an existing test to a different language using Gemini 2.5 Flash

    **Features:**
    - Translates title, description, questions, options, explanations
    - Preserves test structure and correct answers
    - Creates a new test copy in target language
    - Async translation with status polling

    **Supported Languages:**
    - English (en), Vietnamese (vi)
    - Chinese Simplified (zh-CN), Traditional (zh-TW)
    - Japanese (ja), Korean (ko)
    - Thai (th), Indonesian (id), Malay (ms)
    - Khmer (km), Lao (lo), Hindi (hi)
    - Portuguese (pt), Russian (ru), French (fr), German (de), Spanish (es)

    **Process:**
    1. Creates new test record with status='pending'
    2. Returns test_id immediately
    3. Background job translates content using Gemini 2.5 Flash
    4. Frontend polls /tests/{test_id}/status for completion

    **What Gets Translated:**
    - Test title and description
    - All question texts
    - MCQ option texts
    - Answer explanations
    - Essay grading rubrics

    **What Stays the Same:**
    - Question structure and IDs
    - Option keys (A, B, C, D)
    - Correct answer keys
    - Media attachments
    - Time limits and settings

    **Authentication:** Required (must own original test)

    **Response:**
    - new test_id for translated version
    - status='pending' (poll for completion)
    """
    try:
        user_id = user_info["uid"]

        logger.info(
            f"🌍 User {user_id} requesting translation of test {test_id} to {request.target_language}"
        )

        # Get original test
        mongo_service = get_mongodb_service()
        collection = mongo_service.db["online_tests"]

        original_test = collection.find_one({"_id": ObjectId(test_id)})

        if not original_test:
            raise HTTPException(status_code=404, detail="Test not found")

        # Check ownership
        if original_test.get("creator_id") != user_id:
            raise HTTPException(
                status_code=403,
                detail="Only test owner can translate test",
            )

        # Check if test has questions
        if not original_test.get("questions"):
            raise HTTPException(
                status_code=400,
                detail="Cannot translate test without questions",
            )

        # Validate target language
        supported_languages = [
            "en",
            "vi",
            "zh-CN",
            "zh-TW",
            "ja",
            "ko",
            "th",
            "id",
            "km",
            "lo",
            "hi",
            "ms",
            "pt",
            "ru",
            "fr",
            "de",
            "es",
        ]

        if request.target_language not in supported_languages:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported language: {request.target_language}. Supported: {', '.join(supported_languages)}",
            )

        # Check if translating to same language
        current_language = original_test.get("test_language", "vi")
        if request.target_language == current_language:
            raise HTTPException(
                status_code=400,
                detail=f"Test is already in {request.target_language}",
            )

        # Generate new title
        original_title = original_test.get("title", "Untitled Test")
        new_title = request.new_title or f"{original_title} ({request.target_language})"

        # Create new test record for translation
        new_test_doc = {
            "title": new_title,
            "description": original_test.get("description"),
            "creator_name": original_test.get("creator_name"),
            "test_category": original_test.get("test_category", "academic"),
            "user_query": original_test.get("user_query"),
            "test_language": request.target_language,  # New language
            "source_type": "translation",  # Mark as translated
            "original_test_id": test_id,  # Reference to original
            "creator_id": user_id,
            "time_limit_minutes": original_test.get("time_limit_minutes", 30),
            "num_questions": original_test.get("num_questions", 0),
            "max_retries": original_test.get("max_retries", 3),
            "passing_score": original_test.get("passing_score", 70),
            "deadline": original_test.get("deadline"),
            "show_answers_timing": original_test.get(
                "show_answers_timing", "immediate"
            ),
            "creation_type": "translated",
            "status": "pending",
            "progress_percent": 0,
            "questions": [],  # Will be populated by background job
            "attachments": original_test.get(
                "attachments", []
            ),  # Copy attachments (PDFs don't need translation)
            "grading_config": original_test.get("grading_config"),
            "is_active": True,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

        result = collection.insert_one(new_test_doc)
        new_test_id = str(result.inserted_id)

        logger.info(
            f"✅ Translation test record created: {new_test_id} with status='pending'"
        )

        # Start background translation job
        background_tasks.add_task(
            translate_test_background,
            test_id=new_test_id,
            original_test_id=test_id,
            target_language=request.target_language,
            original_test_doc=original_test,
        )

        logger.info(f"🚀 Background translation job queued for test {new_test_id}")

        return TranslateTestResponse(
            success=True,
            test_id=new_test_id,
            status="pending",
            original_test_id=test_id,
            target_language=request.target_language,
            message=f"Test translation to {request.target_language} started. Poll /tests/{new_test_id}/status for progress.",
            created_at=new_test_doc["created_at"].isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Test translation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
