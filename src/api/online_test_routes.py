"""
Online Test API Routes - Phase 1, 2, 3
Endpoints for test generation, taking tests, submission, WebSocket auto-save, and test editing
"""

import logging
import os
from typing import Optional, Dict, Any
from datetime import datetime
from bson import ObjectId
from pymongo import MongoClient

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from src.middleware.auth import verify_firebase_token as require_auth
from src.services.test_generator_service import get_test_generator_service
from src.services.document_manager import document_manager
import config.config as config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tests", tags=["Online Tests - Phase 1-3"])

# MongoDB connection helper
_mongo_client = None


def get_mongodb_service():
    """Get MongoDB database instance (helper for compatibility)"""
    global _mongo_client
    if _mongo_client is None:
        mongo_uri = getattr(config, "MONGODB_URI_AUTH", None) or getattr(
            config, "MONGODB_URI", "mongodb://localhost:27017"
        )
        _mongo_client = MongoClient(mongo_uri)
    db_name = getattr(config, "MONGODB_NAME", "wordai_db")
    db = _mongo_client[db_name]

    # Return a simple object that mimics the service interface
    class MongoDBService:
        def __init__(self, database):
            self.db = database

    return MongoDBService(db)


def get_document_manager():
    """Get document manager instance"""
    return document_manager


# ========== Request/Response Models ==========


class GenerateTestRequest(BaseModel):
    """Request model for AI-generated test"""

    source_type: str = Field(..., description="Source type: 'document' or 'file'")
    source_id: str = Field(..., description="Document ID or R2 file key")
    title: str = Field(..., description="Test title", min_length=5, max_length=200)
    description: Optional[str] = Field(
        None,
        description="Test description for test takers (optional, user-facing)",
        max_length=1000,
    )
    user_query: str = Field(
        ...,
        description="Instructions to AI: what topics/concepts to test (e.g., 'Kiến thức về bất động sản', 'Python programming basics')",
        min_length=10,
        max_length=500,
    )
    language: str = Field(
        default="vi",
        description="Language for questions and answers: 'vi' (Vietnamese), 'en' (English), 'zh' (Chinese)",
    )
    num_questions: int = Field(..., description="Number of questions", ge=1, le=100)
    time_limit_minutes: int = Field(
        30, description="Time limit in minutes", ge=1, le=300
    )
    max_retries: int = Field(3, description="Maximum number of attempts", ge=1, le=10)
    num_options: int = Field(
        4,
        description="Number of answer options per question (e.g., 4 for A-D, 6 for A-F). Set to 0 or 'auto' to let AI decide.",
        ge=0,
        le=10,
    )
    num_correct_answers: int = Field(
        1,
        description="Number of correct answers per question. Set to 0 or 'auto' to let AI decide based on question complexity.",
        ge=0,
        le=10,
    )


class ManualTestQuestion(BaseModel):
    """Manual question model - flexible validation for user-created tests"""

    question_text: str = Field(..., min_length=1, max_length=1000)
    options: list = Field(
        ..., description="List of options with 'key' and 'text'", min_length=2
    )
    correct_answer_key: str = Field(
        ..., description="Correct answer key (A, B, C, D, etc.)"
    )
    explanation: Optional[str] = Field(
        None, description="Optional explanation", max_length=500
    )


class CreateManualTestRequest(BaseModel):
    """Request model for manual test creation"""

    title: str = Field(..., description="Test title", min_length=5, max_length=200)
    description: Optional[str] = Field(
        None, description="Test description (optional)", max_length=1000
    )
    language: str = Field(default="vi", description="Language: 'vi', 'en', or 'zh'")
    time_limit_minutes: int = Field(
        30, description="Time limit in minutes", ge=1, le=300
    )
    max_retries: int = Field(3, description="Maximum number of attempts", ge=1, le=10)
    questions: Optional[list[ManualTestQuestion]] = Field(
        default=[],
        description="List of questions (optional, can be empty to create draft test)",
    )


class DuplicateTestRequest(BaseModel):
    """Request model for duplicating a test"""

    new_title: Optional[str] = Field(
        None,
        description="New title for duplicated test (optional, will auto-generate if not provided)",
        max_length=200,
    )


class TestQuestionsResponse(BaseModel):
    """Response model for test questions (for taking)"""

    test_id: str
    status: str
    title: str
    description: Optional[str]
    time_limit_minutes: int
    num_questions: int
    questions: list


class TestStatusResponse(BaseModel):
    """Response model for test status polling"""

    test_id: str
    status: str  # pending, generating, ready, failed
    progress_percent: int
    message: str
    error_message: Optional[str] = None
    # Include these when ready
    title: Optional[str] = None
    description: Optional[str] = None
    num_questions: Optional[int] = None
    created_at: Optional[str] = None
    generated_at: Optional[str] = None


class SubmitTestRequest(BaseModel):
    """Request model for test submission"""

    user_answers: list = Field(
        ..., description="List of {question_id, selected_answer_key}"
    )


class TestResultResponse(BaseModel):
    """Response model for test results"""

    submission_id: str
    score: float
    total_questions: int
    correct_answers: int
    time_taken_seconds: int
    results: list


class TestSummary(BaseModel):
    """Summary of a test"""

    test_id: str
    title: str
    num_questions: int
    time_limit_minutes: int
    created_at: str
    attempts_count: int


# ========== Endpoints ==========


# ========== Background Job for AI Generation ==========


async def generate_test_background(
    test_id: str,
    content: str,
    title: str,
    user_query: str,
    language: str,
    num_questions: int,
    creator_id: str,
    source_type: str,
    source_id: str,
    time_limit_minutes: int,
    gemini_pdf_bytes: Optional[bytes],
    num_options: int = 4,
    num_correct_answers: int = 1,
):
    """
    Background job to generate test questions with AI
    Updates status: pending → generating → ready/failed
    """
    from pymongo import MongoClient
    import config.config as config

    mongo_uri = getattr(config, "MONGODB_URI_AUTH", None) or getattr(
        config, "MONGODB_URI", "mongodb://localhost:27017"
    )
    client = MongoClient(mongo_uri)
    db_name = getattr(config, "MONGODB_NAME", "wordai_db")
    db = client[db_name]
    collection = db["online_tests"]

    try:
        # Update status to generating
        collection.update_one(
            {"_id": ObjectId(test_id)},
            {
                "$set": {
                    "status": "generating",
                    "progress_percent": 10,
                    "updated_at": datetime.now(),
                }
            },
        )
        logger.info(f"🔄 Test {test_id}: Status updated to 'generating'")

        # Generate test with AI
        test_generator = get_test_generator_service()

        logger.info(f"🤖 Calling AI to generate {num_questions} questions...")
        questions = await test_generator._generate_questions_with_ai(
            content=content,
            user_query=user_query,
            language=language,
            num_questions=num_questions,
            gemini_pdf_bytes=gemini_pdf_bytes,
            num_options=num_options,
            num_correct_answers=num_correct_answers,
        )

        # Update progress
        collection.update_one(
            {"_id": ObjectId(test_id)},
            {"$set": {"progress_percent": 80, "updated_at": datetime.now()}},
        )

        # Save questions
        collection.update_one(
            {"_id": ObjectId(test_id)},
            {
                "$set": {
                    "questions": questions,
                    "status": "ready",
                    "progress_percent": 100,
                    "generated_at": datetime.now(),
                    "updated_at": datetime.now(),
                }
            },
        )

        logger.info(f"✅ Test {test_id}: Generation completed successfully")

    except Exception as e:
        logger.error(f"❌ Test {test_id}: Generation failed: {e}")
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


@router.post("/generate")
async def generate_test(
    request: GenerateTestRequest,
    background_tasks: BackgroundTasks,
    user_info: dict = Depends(require_auth),
):
    """
    Generate a new test from document or file (AI-powered)

    **NEW Async Pattern**: Returns immediately with test_id and status='pending'.
    Background job generates questions. Frontend polls /tests/{test_id}/status.

    **Flow:**
    1. Create test record with status='pending'
    2. Return test_id immediately (< 500ms)
    3. Start background AI generation
    4. Frontend polls status endpoint
    5. When ready, frontend renders questions

    **Benefits:**
    - Fast response time
    - User can close browser, come back later
    - No data loss on network errors
    """
    try:
        logger.info(f"📝 Test generation request from user {user_info['uid']}")
        logger.info(f"   Source: {request.source_type}/{request.source_id}")
        logger.info(f"   Title: {request.title}")
        logger.info(f"   Description: {request.description or '(none)'}")
        logger.info(f"   Query: {request.user_query}")
        logger.info(f"   Language: {request.language}")
        logger.info(
            f"   Questions: {request.num_questions}, Time: {request.time_limit_minutes}min"
        )

        # Validate language
        supported_languages = {"vi", "en", "zh"}
        if request.language not in supported_languages:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid language: {request.language}. Must be one of: {supported_languages}",
            )

        # Initialize variables
        content = ""
        gemini_pdf_bytes = None  # For PDF files

        # Get content based on source type
        if request.source_type == "document":
            # Get document from MongoDB
            doc_manager = get_document_manager()
            try:
                doc = doc_manager.get_document(request.source_id, user_info["uid"])
                content_html = doc.get("content_html", "")

                if not content_html:
                    raise HTTPException(
                        status_code=400, detail="Document has no content"
                    )

                # Parse HTML to plain text (remove tags but preserve structure)
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(content_html, "html.parser")

                # Remove script and style tags completely
                for script in soup(["script", "style"]):
                    script.decompose()

                # Get text with some structure preserved
                content = soup.get_text(separator=" ", strip=True)

                # Clean up excessive whitespace
                import re

                content = re.sub(r"\s+", " ", content).strip()

                logger.info(f"📄 Parsed HTML document: {len(content)} characters")

            except Exception as e:
                logger.error(f"❌ Failed to get document: {e}")
                raise HTTPException(
                    status_code=404,
                    detail=f"Document not found or access denied: {str(e)}",
                )

        elif request.source_type == "file":
            # Get file metadata from MongoDB to check file type
            from src.services.user_manager import get_user_manager
            from src.services.file_download_service import FileDownloadService
            import google.generativeai as genai

            user_manager = get_user_manager()
            file_info = user_manager.get_file_by_id(request.source_id, user_info["uid"])

            if not file_info:
                raise HTTPException(
                    status_code=404, detail=f"File not found: {request.source_id}"
                )

            # Check if file is PDF (required for Gemini File API)
            file_type = file_info.get("file_type", "").lower()
            if file_type != ".pdf":
                raise HTTPException(
                    status_code=400,
                    detail=f"Only PDF files are supported for direct file processing. Your file is {file_type}. Please convert to document first.",
                )

            # Download PDF from R2
            r2_key = file_info.get("r2_key")
            if not r2_key:
                raise HTTPException(
                    status_code=500, detail="File R2 key not found in database"
                )

            logger.info(f"📥 Downloading PDF from R2 for Gemini File API: {r2_key}")

            # Download PDF to temp file (ONLY download, no need to parse)
            # Gemini File API will handle PDF directly
            temp_pdf_path = await FileDownloadService._download_file_from_r2_with_boto3(
                r2_key=r2_key, file_type="pdf"
            )

            if not temp_pdf_path:
                raise HTTPException(
                    status_code=500, detail="Failed to download PDF from R2"
                )

            logger.info(f"✅ PDF downloaded to: {temp_pdf_path}")

            # Read PDF content as bytes (NEW API approach)
            logger.info(f"� Reading PDF content for Gemini...")

            try:
                with open(temp_pdf_path, "rb") as f:
                    pdf_content = f.read()

                logger.info(f"✅ PDF content read: {len(pdf_content)} bytes")

                # Store PDF bytes for Gemini (will be passed directly to model)
                gemini_pdf_bytes = pdf_content

                # Use placeholder content
                content = f"[PDF file ready for Gemini: {len(pdf_content)} bytes]"

            except Exception as e:
                logger.error(f"❌ Failed to read PDF: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to process PDF: {str(e)}",
                )

            finally:
                # Cleanup temp file
                if temp_pdf_path and os.path.exists(temp_pdf_path):
                    try:
                        os.unlink(temp_pdf_path)
                        logger.info(f"🗑️ Cleaned up temp file: {temp_pdf_path}")
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to cleanup temp file: {e}")

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid source_type: {request.source_type}. Must be 'document' or 'file'",
            )

        # ========== NEW: Create test record immediately with status='pending' ==========
        mongo_service = get_mongodb_service()
        collection = mongo_service.db["online_tests"]

        test_doc = {
            "title": request.title,
            "description": request.description,
            "user_query": request.user_query,
            "language": request.language,
            "source_type": request.source_type,
            "source_document_id": (
                request.source_id if request.source_type == "document" else None
            ),
            "source_file_r2_key": (
                request.source_id if request.source_type == "file" else None
            ),
            "creator_id": user_info["uid"],
            "time_limit_minutes": request.time_limit_minutes,
            "num_questions": request.num_questions,
            "max_retries": request.max_retries,
            "creation_type": "ai_generated",
            "status": "pending",
            "progress_percent": 0,
            "questions": [],  # Will be populated by background job
            "is_active": True,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

        result = collection.insert_one(test_doc)
        test_id = str(result.inserted_id)

        logger.info(f"✅ Test record created: {test_id} with status='pending'")

        # ========== Start background job for AI generation ==========
        background_tasks.add_task(
            generate_test_background,
            test_id=test_id,
            content=content,
            title=request.title,
            user_query=request.user_query,
            language=request.language,
            num_questions=request.num_questions,
            creator_id=user_info["uid"],
            source_type=request.source_type,
            source_id=request.source_id,
            time_limit_minutes=request.time_limit_minutes,
            gemini_pdf_bytes=(
                gemini_pdf_bytes if request.source_type == "file" else None
            ),
            num_options=request.num_options if request.num_options > 0 else 4,
            num_correct_answers=(
                request.num_correct_answers if request.num_correct_answers > 0 else 1
            ),
        )

        logger.info(f"🚀 Background job queued for test {test_id}")

        # ========== Return immediately ==========
        return {
            "success": True,
            "test_id": test_id,
            "status": "pending",
            "title": request.title,
            "description": request.description,
            "num_questions": request.num_questions,
            "time_limit_minutes": request.time_limit_minutes,
            "created_at": test_doc["created_at"].isoformat(),
            "message": "Test created successfully. AI is generating questions...",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Test generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== NEW: Manual Test Creation Endpoint ==========


@router.post("/manual")
async def create_manual_test(
    request: CreateManualTestRequest,
    user_info: dict = Depends(require_auth),
):
    """
    Create a test with manually entered questions

    **UPDATED**: Questions are now optional - can create empty draft test

    User can:
    1. Create empty test with just title → Add questions later
    2. Create test with initial questions → Continue editing
    3. Duplicate existing test → Modify copy

    Test is immediately set to status='ready' (no AI generation needed).

    **Use Cases:**
    - Teacher creates draft quiz, adds questions gradually
    - Import questions from existing material
    - Quick test without AI
    """
    try:
        logger.info(f"📝 Manual test creation from user {user_info['uid']}")
        logger.info(f"   Title: {request.title}")
        logger.info(f"   Questions: {len(request.questions or [])}")

        # Validate questions if provided
        if request.questions:
            for idx, q in enumerate(request.questions):
                if len(q.options) < 2:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Question {idx+1}: Must have at least 2 options",
                    )

                # Validate correct_answer_key exists in options
                option_keys = [opt["key"] for opt in q.options]
                if q.correct_answer_key not in option_keys:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Question {idx+1}: correct_answer_key '{q.correct_answer_key}' not found in options",
                    )

        # Create test record
        mongo_service = get_mongodb_service()
        collection = mongo_service.db["online_tests"]

        # Format questions with question_id
        import uuid

        formatted_questions = []
        if request.questions:
            for q in request.questions:
                formatted_questions.append(
                    {
                        "question_id": str(uuid.uuid4())[:8],
                        "question_text": q.question_text,
                        "options": q.options,
                        "correct_answer_key": q.correct_answer_key,
                        "explanation": q.explanation,
                    }
                )

        # Determine status based on whether test has questions
        status = "ready" if len(formatted_questions) > 0 else "draft"

        test_doc = {
            "title": request.title,
            "description": request.description,
            "user_query": None,  # N/A for manual tests
            "language": request.language,
            "source_type": "manual",
            "source_document_id": None,
            "source_file_r2_key": None,
            "creator_id": user_info["uid"],
            "time_limit_minutes": request.time_limit_minutes,
            "num_questions": len(formatted_questions),
            "max_retries": request.max_retries,
            "creation_type": "manual",
            "status": status,  # "draft" if no questions, "ready" if has questions
            "progress_percent": 100 if len(formatted_questions) > 0 else 0,
            "questions": formatted_questions,
            "is_active": True,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

        result = collection.insert_one(test_doc)
        test_id = str(result.inserted_id)

        logger.info(f"✅ Manual test created: {test_id} (status: {status})")

        message = (
            "Manual test created successfully!"
            if status == "ready"
            else "Draft test created. Add questions to make it ready."
        )

        return {
            "success": True,
            "test_id": test_id,
            "status": status,
            "title": request.title,
            "description": request.description,
            "num_questions": len(formatted_questions),
            "time_limit_minutes": request.time_limit_minutes,
            "created_at": test_doc["created_at"].isoformat(),
            "message": message,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Manual test creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Duplicate Test Endpoint ==========


@router.post("/{test_id}/duplicate")
async def duplicate_test(
    test_id: str,
    request: DuplicateTestRequest,
    user_info: dict = Depends(require_auth),
):
    """
    Duplicate an existing test

    **NEW Endpoint**

    Creates a copy of existing test with auto-generated title suffix:
    - "Test ABC" → "Test ABC copy1"
    - "Test ABC copy1" → "Test ABC copy2"
    - etc.

    **Use Cases:**
    - Create variations of same test
    - Modify copy without affecting original
    - Template-based test creation

    **Response:**
    - Returns new test_id with duplicated content
    - Questions are deep-copied with new question_ids
    - Status = "ready" (or "draft" if original was draft)
    """
    try:
        logger.info(
            f"📋 Duplicate test request: {test_id} from user {user_info['uid']}"
        )

        # Get original test
        mongo_service = get_mongodb_service()
        collection = mongo_service.db["online_tests"]

        original_test = collection.find_one({"_id": ObjectId(test_id)})

        if not original_test:
            raise HTTPException(status_code=404, detail="Test not found")

        # Only creator can duplicate
        if original_test.get("creator_id") != user_info["uid"]:
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to duplicate this test",
            )

        # Generate new title with copy suffix
        import re

        original_title = original_test.get("title", "Untitled Test")

        if request.new_title:
            new_title = request.new_title
        else:
            # Check for existing copies
            match = re.search(r" copy(\d+)$", original_title)
            if match:
                # Increment copy number
                copy_num = int(match.group(1)) + 1
                base_title = original_title[: match.start()]
                new_title = f"{base_title} copy{copy_num}"
            else:
                # First copy
                new_title = f"{original_title} copy1"

        # Deep copy questions with new question_ids
        import uuid

        new_questions = []
        for q in original_test.get("questions", []):
            new_q = q.copy()
            new_q["question_id"] = str(uuid.uuid4())[:8]
            new_questions.append(new_q)

        # Create duplicated test document
        duplicated_doc = {
            "title": new_title,
            "description": original_test.get("description"),
            "user_query": original_test.get("user_query"),
            "language": original_test.get("language", "vi"),
            "source_type": original_test.get("source_type", "manual"),
            "source_document_id": original_test.get("source_document_id"),
            "source_file_r2_key": original_test.get("source_file_r2_key"),
            "creator_id": user_info["uid"],
            "time_limit_minutes": original_test.get("time_limit_minutes", 30),
            "num_questions": len(new_questions),
            "max_retries": original_test.get("max_retries", 3),
            "creation_type": original_test.get("creation_type", "manual"),
            "status": original_test.get("status", "ready"),
            "progress_percent": original_test.get("progress_percent", 100),
            "questions": new_questions,
            "is_active": True,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            # Add metadata to track duplication
            "duplicated_from": test_id,
            "is_duplicate": True,
        }

        result = collection.insert_one(duplicated_doc)
        new_test_id = str(result.inserted_id)

        logger.info(f"✅ Test duplicated: {test_id} → {new_test_id}")

        return {
            "success": True,
            "test_id": new_test_id,
            "original_test_id": test_id,
            "title": new_title,
            "description": duplicated_doc["description"],
            "num_questions": len(new_questions),
            "status": duplicated_doc["status"],
            "created_at": duplicated_doc["created_at"].isoformat(),
            "message": f"Test duplicated successfully as '{new_title}'",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Test duplication failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{test_id}/status")
async def get_test_status(
    test_id: str,
    user_info: dict = Depends(require_auth),
):
    """
    Get test generation status (for polling)

    **NEW Endpoint for async pattern**

    Frontend polls this endpoint every 3 seconds to check if AI generation is complete.

    **Status Values:**
    - `pending`: Test queued, AI generation not started
    - `generating`: AI is generating questions
    - `ready`: Questions generated, test ready to take
    - `failed`: AI generation failed

    **Usage:**
    ```javascript
    const interval = setInterval(async () => {
      const status = await fetch(`/api/v1/tests/${testId}/status`);
      if (status.status === 'ready') {
        clearInterval(interval);
        loadQuestions();
      }
    }, 3000);
    ```
    """
    try:
        mongo_service = get_mongodb_service()
        collection = mongo_service.db["online_tests"]

        test = collection.find_one({"_id": ObjectId(test_id)})

        if not test:
            raise HTTPException(status_code=404, detail="Test not found")

        # Only creator can check status
        if test.get("creator_id") != user_info["uid"]:
            raise HTTPException(
                status_code=403, detail="You don't have permission to view this test"
            )

        status = test.get("status", "pending")
        progress = test.get("progress_percent", 0)

        response = {
            "test_id": test_id,
            "status": status,
            "progress_percent": progress,
        }

        if status == "pending":
            response["message"] = "Test is queued for generation..."
        elif status == "generating":
            response["message"] = f"AI is generating questions... ({progress}%)"
        elif status == "ready":
            response.update(
                {
                    "message": "Test is ready to take!",
                    "title": test.get("title"),
                    "description": test.get("description"),
                    "num_questions": test.get("num_questions"),
                    "time_limit_minutes": test.get("time_limit_minutes"),
                    "created_at": test.get("created_at").isoformat(),
                    "generated_at": (
                        test.get("generated_at").isoformat()
                        if test.get("generated_at")
                        else None
                    ),
                }
            )
        elif status == "failed":
            response.update(
                {
                    "message": "Test generation failed. Please try again.",
                    "error_message": test.get("error_message"),
                }
            )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get test status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{test_id}")
async def get_test(
    test_id: str,
    user_info: dict = Depends(require_auth),
):
    """
    Get test details for taking (questions without correct answers)

    **UPDATED**: Now checks if test is ready before returning questions

    **Status Check:**
    - If status != 'ready': Returns error with current status
    - If status = 'ready': Returns questions (without correct answers)
    """
    try:
        logger.info(f"📖 Get test request: {test_id} from user {user_info['uid']}")

        # Get test
        mongo_service = get_mongodb_service()
        test = mongo_service.db["online_tests"].find_one({"_id": ObjectId(test_id)})

        if not test:
            raise HTTPException(status_code=404, detail="Test not found")

        if not test.get("is_active", False):
            raise HTTPException(status_code=403, detail="Test is not active")

        # ========== NEW: Check if test is ready ==========
        status = test.get("status", "ready")
        if status != "ready":
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "TEST_NOT_READY",
                    "message": f"Test is not ready yet. Current status: {status}",
                    "current_status": status,
                    "progress_percent": test.get("progress_percent", 0),
                    "tip": f"Poll GET /api/v1/tests/{test_id}/status to check when ready",
                },
            )

        # Test is ready, return questions
        test_generator = get_test_generator_service()
        test_data = await test_generator.get_test_for_taking(test_id, user_info["uid"])

        # Add status to response
        test_data["status"] = "ready"
        test_data["description"] = test.get("description")

        return test_data

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Failed to get test: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{test_id}/start")
async def start_test(
    test_id: str,
    user_info: dict = Depends(require_auth),
):
    """
    Start a new test session

    **Phase 1 Feature**

    Creates a session record and returns test questions.
    Phase 2 will add WebSocket support for real-time progress.
    """
    try:
        logger.info(f"🚀 Start test: {test_id} for user {user_info['uid']}")

        # Get test to verify it exists
        test_generator = get_test_generator_service()
        test_data = await test_generator.get_test_for_taking(test_id, user_info["uid"])

        # Check if user has already exceeded max attempts
        mongo_service = get_mongodb_service()
        test_collection = mongo_service.db["online_tests"]
        submissions_collection = mongo_service.db["test_submissions"]

        test_doc = test_collection.find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        # Check if user is the creator/owner
        is_creator = test_doc.get("creator_id") == user_info["uid"]

        if is_creator:
            logger.info(f"   👤 User is test creator - unlimited attempts allowed")

        max_retries = test_doc.get("max_retries", 1)

        # Count user's attempts from BOTH submissions AND active sessions
        # This prevents users from starting multiple sessions to bypass retry limit
        progress_collection = mongo_service.db["test_progress"]

        # Count completed submissions
        completed_submissions = submissions_collection.count_documents(
            {
                "test_id": test_id,
                "user_id": user_info["uid"],
            }
        )

        # Count existing sessions (completed or not)
        existing_sessions = progress_collection.count_documents(
            {
                "test_id": test_id,
                "user_id": user_info["uid"],
            }
        )

        # Total attempts = max of submissions or sessions
        # (in case of orphaned sessions without submissions)
        attempts_used = max(completed_submissions, existing_sessions)

        # Current attempt number (this new session)
        current_attempt = attempts_used + 1

        # Check if exceeds limit BEFORE creating new session
        # BUT skip check if user is the creator (owner has unlimited attempts)
        if (
            not is_creator
            and max_retries != "unlimited"
            and current_attempt > max_retries
        ):
            raise HTTPException(
                status_code=429,
                detail=f"Maximum attempts ({max_retries}) exceeded. You have used {attempts_used} attempts.",
            )

        # Create session in test_progress (Phase 2 feature, but prepare now)
        import uuid

        session_id = str(uuid.uuid4())

        progress_collection.insert_one(
            {
                "session_id": session_id,
                "test_id": test_id,
                "user_id": user_info["uid"],
                "current_answers": {},  # ✅ Dict/object, not array
                "started_at": datetime.now(),
                "last_saved_at": datetime.now(),
                "time_remaining_seconds": test_data["time_limit_minutes"] * 60,
                "is_completed": False,
                "attempt_number": current_attempt,  # Track which attempt this is
            }
        )

        logger.info(
            f"   ✅ Session created: {session_id} (Attempt {current_attempt}/{max_retries if not is_creator else 'unlimited'})"
        )

        # Calculate time values for frontend
        time_limit_seconds = test_data["time_limit_minutes"] * 60
        time_remaining_seconds = time_limit_seconds  # Full time at start

        return {
            "success": True,
            "session_id": session_id,
            "test": test_data,
            # Attempt tracking
            "current_attempt": current_attempt,  # Lần thử hiện tại (1, 2, 3...)
            "max_attempts": (
                "unlimited" if is_creator else max_retries
            ),  # Creator = unlimited
            "attempts_remaining": (
                "unlimited"
                if is_creator
                else (
                    max_retries - current_attempt
                    if max_retries != "unlimited"
                    else "unlimited"
                )
            ),
            "is_creator": is_creator,  # NEW: Frontend biết user có phải creator
            # Time tracking
            "time_limit_seconds": time_limit_seconds,
            "time_remaining_seconds": time_remaining_seconds,
            "is_completed": False,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to start test: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{test_id}/submit")
async def submit_test(
    test_id: str,
    request: SubmitTestRequest,
    user_info: dict = Depends(require_auth),
):
    """
    Submit test answers and get results

    **Phase 1 Feature**

    Scores the test and returns detailed results with explanations.
    """
    try:
        logger.info(f"📤 Submit test: {test_id} from user {user_info['uid']}")
        logger.info(f"   Answers: {len(request.user_answers)} questions")

        # Get test with correct answers
        mongo_service = get_mongodb_service()
        test_collection = mongo_service.db["online_tests"]

        test_doc = test_collection.find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        if not test_doc.get("is_active", False):
            raise HTTPException(status_code=410, detail="Test is no longer active")

        # Score the test
        questions = test_doc["questions"]
        total_questions = len(questions)
        correct_count = 0
        results = []

        # Create answer map for quick lookup
        user_answers_map = {
            ans["question_id"]: ans["selected_answer_key"]
            for ans in request.user_answers
        }

        for q in questions:
            question_id = q["question_id"]
            correct_answer = q["correct_answer_key"]
            user_answer = user_answers_map.get(question_id, None)

            is_correct = user_answer == correct_answer
            if is_correct:
                correct_count += 1

            results.append(
                {
                    "question_id": question_id,
                    "question_text": q["question_text"],
                    "your_answer": user_answer,
                    "correct_answer": correct_answer,
                    "is_correct": is_correct,
                    "explanation": q["explanation"],
                }
            )

        # Calculate score (thang điểm 10)
        score_percentage = (
            (correct_count / total_questions * 100) if total_questions > 0 else 0
        )
        score_out_of_10 = (
            round(correct_count / total_questions * 10, 2) if total_questions > 0 else 0
        )

        # Count attempt number
        submissions_collection = mongo_service.db["test_submissions"]
        attempt_number = (
            submissions_collection.count_documents(
                {
                    "test_id": test_id,
                    "user_id": user_info["uid"],
                }
            )
            + 1
        )

        # Save submission
        submission_doc = {
            "test_id": test_id,
            "user_id": user_info["uid"],
            "user_answers": request.user_answers,
            "score": score_out_of_10,  # Thang điểm 10
            "score_percentage": score_percentage,  # Phần trăm (for reference)
            "total_questions": total_questions,
            "correct_answers": correct_count,
            "time_taken_seconds": 0,  # TODO: Calculate from session start time (Phase 2)
            "attempt_number": attempt_number,
            "is_passed": score_out_of_10 >= 5.0,  # Pass threshold: 5/10
            "submitted_at": datetime.now(),
        }

        result = submissions_collection.insert_one(submission_doc)
        submission_id = str(result.inserted_id)

        # Mark session as completed (if exists)
        progress_collection = mongo_service.db["test_progress"]
        progress_collection.update_many(
            {"test_id": test_id, "user_id": user_info["uid"], "is_completed": False},
            {"$set": {"is_completed": True, "last_saved_at": datetime.now()}},
        )

        logger.info(
            f"✅ Test submitted: score={score_out_of_10:.2f}/10 "
            f"({score_percentage:.1f}%), attempt={attempt_number}"
        )

        return {
            "success": True,
            "submission_id": submission_id,
            "score": score_out_of_10,  # Thang điểm 10
            "score_percentage": score_percentage,  # Phần trăm
            "total_questions": total_questions,
            "correct_answers": correct_count,
            "attempt_number": attempt_number,
            "is_passed": score_out_of_10 >= 5.0,  # Pass: >= 5/10
            "results": results,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Test submission failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/me/tests")
async def get_my_tests(
    limit: int = 10,
    offset: int = 0,
    user_info: dict = Depends(require_auth),
):
    """
    Get paginated list of tests created by the current user

    **IMPORTANT:** With router prefix, this becomes /api/v1/tests/me/tests
    But documentation says it should be /api/v1/me/tests
    Use the user_router version below for correct path.

    **Phase 1 Feature**

    Args:
        limit: Number of tests to return (default 10, max 100)
        offset: Number of tests to skip (default 0)
    """
    try:
        logger.info(
            f"📋 Get my tests for user {user_info['uid']} (limit={limit}, offset={offset})"
        )

        # Validate pagination params
        if limit > 100:
            limit = 100
        if offset < 0:
            offset = 0

        mongo_service = get_mongodb_service()
        test_collection = mongo_service.db["online_tests"]
        submissions_collection = mongo_service.db["test_submissions"]

        # Get total count
        total_count = test_collection.count_documents({"creator_id": user_info["uid"]})

        # Get user's created tests with pagination, sorted by updated_at (latest first)
        tests = list(
            test_collection.find({"creator_id": user_info["uid"]})
            .sort(
                [("updated_at", -1), ("created_at", -1)]
            )  # Latest edited/created first
            .skip(offset)
            .limit(limit)
        )

        # Build result with minimal info for list view
        result = []
        for test in tests:
            test_id = str(test["_id"])
            attempts_count = submissions_collection.count_documents(
                {"test_id": test_id}
            )

            result.append(
                {
                    "test_id": test_id,
                    "title": test["title"],
                    "description": test.get("description"),  # Optional field
                    "num_questions": len(test.get("questions", [])),
                    "time_limit_minutes": test["time_limit_minutes"],
                    "status": test.get(
                        "status", "ready"
                    ),  # pending, generating, ready, failed, draft
                    "is_active": test.get("is_active", True),
                    "created_at": test["created_at"].isoformat(),
                    "updated_at": test.get(
                        "updated_at", test["created_at"]
                    ).isoformat(),
                    "total_submissions": attempts_count,
                }
            )

        return {
            "tests": result,
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total_count,
        }

    except Exception as e:
        logger.error(f"❌ Failed to get tests: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/me/submissions")
async def get_my_submissions(
    user_info: dict = Depends(require_auth),
):
    """
    Get list of test submissions by the current user

    **Phase 1 Feature**
    """
    try:
        logger.info(f"📊 Get my submissions for user {user_info['uid']}")

        mongo_service = get_mongodb_service()
        submissions_collection = mongo_service.db["test_submissions"]
        test_collection = mongo_service.db["online_tests"]

        # Get user's submissions
        submissions = list(
            submissions_collection.find(
                {"user_id": user_info["uid"]}, sort=[("submitted_at", -1)]
            )
        )

        # Enrich with test details
        result = []
        for sub in submissions:
            test_id = sub["test_id"]
            test_doc = test_collection.find_one({"_id": ObjectId(test_id)})

            if test_doc:
                result.append(
                    {
                        "submission_id": str(sub["_id"]),
                        "test_id": test_id,
                        "test_title": test_doc["title"],
                        "score": sub["score"],
                        "correct_answers": sub["correct_answers"],
                        "total_questions": sub["total_questions"],
                        "is_passed": sub.get("is_passed", False),
                        "attempt_number": sub["attempt_number"],
                        "submitted_at": sub["submitted_at"].isoformat(),
                    }
                )

        return {"submissions": result}

    except Exception as e:
        logger.error(f"❌ Failed to get submissions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/me/submissions/{submission_id}")
async def get_submission_detail(
    submission_id: str,
    user_info: dict = Depends(require_auth),
):
    """
    Get detailed results of a specific submission

    **Phase 1 Feature**
    """
    try:
        logger.info(f"🔍 Get submission detail: {submission_id}")

        mongo_service = get_mongodb_service()
        submissions_collection = mongo_service.db[
            "test_submissions"
        ]  # ✅ Correct collection

        submission = submissions_collection.find_one({"_id": ObjectId(submission_id)})

        if not submission:
            raise HTTPException(status_code=404, detail="Submission not found")

        if submission["user_id"] != user_info["uid"]:
            raise HTTPException(status_code=403, detail="Access denied")

        # Get test for question details
        test_collection = mongo_service.db["online_tests"]
        test_doc = test_collection.find_one({"_id": ObjectId(submission["test_id"])})

        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        # Build results with explanations
        results = []
        user_answers_map = {
            ans["question_id"]: ans["selected_answer_key"]
            for ans in submission["user_answers"]
        }

        for q in test_doc["questions"]:
            question_id = q["question_id"]
            user_answer = user_answers_map.get(question_id)
            is_correct = user_answer == q["correct_answer_key"]

            results.append(
                {
                    "question_id": question_id,
                    "question_text": q["question_text"],
                    "options": q["options"],
                    "your_answer": user_answer,
                    "correct_answer": q["correct_answer_key"],
                    "is_correct": is_correct,
                    "explanation": q["explanation"],
                }
            )

        return {
            "submission_id": submission_id,
            "test_title": test_doc["title"],
            "score": submission["score"],  # Thang điểm 10
            "score_percentage": submission.get(
                "score_percentage", submission["score"] * 10
            ),  # Fallback for old data
            "total_questions": submission["total_questions"],
            "correct_answers": submission["correct_answers"],
            "time_taken_seconds": submission.get("time_taken_seconds", 0),
            "attempt_number": submission["attempt_number"],
            "is_passed": submission.get("is_passed", False),
            "submitted_at": submission["submitted_at"].isoformat(),
            "results": results,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get submission detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Phase 2: HTTP Fallback Endpoints for Real-time Progress ==========


class SaveProgressRequest(BaseModel):
    """Request model for saving progress (HTTP fallback)"""

    session_id: str = Field(..., description="Session ID from /start endpoint")
    answers: dict = Field(
        ..., description="Current answers dict (question_id -> answer_key)"
    )
    time_remaining_seconds: Optional[int] = Field(
        None, description="Time remaining in seconds"
    )


class ProgressResponse(BaseModel):
    """Response model for progress retrieval"""

    session_id: str
    current_answers: dict
    time_remaining_seconds: Optional[int]
    started_at: str
    last_saved_at: str
    is_completed: bool


@router.post(
    "/{test_id}/progress/save", response_model=dict, tags=["Phase 2 - Auto-save"]
)
async def save_test_progress(
    test_id: str,
    request: SaveProgressRequest,
    user_info: dict = Depends(require_auth),
):
    """
    HTTP fallback for saving test progress (for clients without WebSocket)
    Saves current answers and time remaining to database
    """
    try:
        user_id = user_info["uid"]
        mongo_service = get_mongodb_service()

        # Verify test exists
        test_doc = mongo_service.db["online_tests"].find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        # Verify session exists and belongs to user
        session = mongo_service.db["test_progress"].find_one(
            {"session_id": request.session_id}
        )

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        if session["user_id"] != user_id:
            raise HTTPException(
                status_code=403, detail="Session does not belong to user"
            )

        if str(session["test_id"]) != test_id:
            raise HTTPException(
                status_code=400, detail="Session does not belong to this test"
            )

        if session.get("is_completed"):
            raise HTTPException(status_code=409, detail="Session already completed")

        # Update progress in database
        update_data = {
            "current_answers": request.answers,
            "last_saved_at": datetime.utcnow(),
        }

        if request.time_remaining_seconds is not None:
            update_data["time_remaining_seconds"] = request.time_remaining_seconds

        result = mongo_service.db["test_progress"].update_one(
            {"session_id": request.session_id}, {"$set": update_data}
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=500, detail="Failed to save progress")

        logger.info(
            f"💾 Saved progress for session {request.session_id}: "
            f"{len(request.answers)} answers"
        )

        return {
            "success": True,
            "session_id": request.session_id,
            "saved_at": datetime.utcnow().isoformat(),
            "answers_count": len(request.answers),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to save progress: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{test_id}/progress", response_model=ProgressResponse, tags=["Phase 2 - Auto-save"]
)
async def get_test_progress(
    test_id: str,
    session_id: str,
    user_info: dict = Depends(require_auth),
):
    """
    Get current test progress (HTTP fallback)
    Useful for resuming tests after reconnection or page refresh
    """
    try:
        user_id = user_info["uid"]
        mongo_service = get_mongodb_service()

        # Verify test exists
        test_doc = mongo_service.db["online_tests"].find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        # Get session progress
        session = mongo_service.db["test_progress"].find_one({"session_id": session_id})

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        if session["user_id"] != user_id:
            raise HTTPException(
                status_code=403, detail="Session does not belong to user"
            )

        if str(session["test_id"]) != test_id:
            raise HTTPException(
                status_code=400, detail="Session does not belong to this test"
            )

        return ProgressResponse(
            session_id=session["session_id"],
            current_answers=session.get("current_answers", {}),
            time_remaining_seconds=session.get("time_remaining_seconds"),
            started_at=session["started_at"].isoformat(),
            last_saved_at=session.get(
                "last_saved_at", session["started_at"]
            ).isoformat(),
            is_completed=session.get("is_completed", False),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get progress: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{test_id}/resume", response_model=dict, tags=["Phase 2 - Auto-save"])
async def resume_test_session(
    test_id: str,
    user_info: dict = Depends(require_auth),
):
    """
    Resume an incomplete test session
    Returns the most recent session if one exists
    """
    try:
        user_id = user_info["uid"]
        mongo_service = get_mongodb_service()

        # Verify test exists
        test_doc = mongo_service.db["online_tests"].find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        # Find most recent incomplete session for this user and test
        session = mongo_service.db["test_progress"].find_one(
            {"user_id": user_id, "test_id": ObjectId(test_id), "is_completed": False},
            sort=[("started_at", -1)],
        )

        if not session:
            raise HTTPException(
                status_code=404,
                detail="No incomplete session found. Please start a new test.",
            )

        # Calculate elapsed time
        elapsed_seconds = int(
            (datetime.utcnow() - session["started_at"]).total_seconds()
        )
        time_limit_seconds = test_doc["time_limit_minutes"] * 60
        time_remaining = max(0, time_limit_seconds - elapsed_seconds)

        # If time ran out, mark session as completed and return error
        if time_remaining == 0:
            mongo_service.db["test_progress"].update_one(
                {"_id": session["_id"]}, {"$set": {"is_completed": True}}
            )
            raise HTTPException(
                status_code=410,
                detail="Session expired due to time limit. Please start a new test.",
            )

        # Update time remaining in database
        mongo_service.db["test_progress"].update_one(
            {"_id": session["_id"]},
            {"$set": {"time_remaining_seconds": time_remaining}},
        )

        return {
            "session_id": session["session_id"],
            "current_answers": session.get("current_answers", {}),
            "time_limit_seconds": time_limit_seconds,
            "time_remaining_seconds": time_remaining,
            "is_completed": False,
            "started_at": session["started_at"].isoformat(),
            "last_saved_at": session.get(
                "last_saved_at", session["started_at"]
            ).isoformat(),
            "message": "Session resumed successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to resume session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Phase 3: Test Configuration & Editing ==========


class UpdateTestConfigRequest(BaseModel):
    """Request model for updating test configuration"""

    max_retries: Optional[int] = Field(
        None, description="Max retry attempts", ge=1, le=20
    )
    time_limit_minutes: Optional[int] = Field(
        None, description="Time limit in minutes", ge=1, le=300
    )
    is_active: Optional[bool] = Field(None, description="Active status")
    title: Optional[str] = Field(None, description="Test title", max_length=200)
    description: Optional[str] = Field(
        None, description="Test description", max_length=1000
    )


class UpdateTestQuestionsRequest(BaseModel):
    """Request model for updating test questions"""

    questions: list = Field(..., description="Updated questions array")


class TestPreviewResponse(BaseModel):
    """Response model for test preview (including correct answers)"""

    test_id: str
    title: str
    time_limit_minutes: int
    max_retries: int
    is_active: bool
    total_questions: int
    questions: list
    created_at: str
    updated_at: str


@router.patch("/{test_id}/config", response_model=dict, tags=["Phase 3 - Editing"])
async def update_test_config(
    test_id: str,
    request: UpdateTestConfigRequest,
    user_info: dict = Depends(require_auth),
):
    """
    Update test configuration (max_retries, time_limit, status, title, description)
    Only the test creator can update configuration
    """
    try:
        user_id = user_info["uid"]
        mongo_service = get_mongodb_service()

        # Verify test exists and user is creator
        test_doc = mongo_service.db["online_tests"].find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        if test_doc["creator_id"] != user_id:
            raise HTTPException(
                status_code=403,
                detail="Only the test creator can update configuration",
            )

        # Build update data
        update_data = {"updated_at": datetime.utcnow()}

        if request.max_retries is not None:
            update_data["max_retries"] = request.max_retries

        if request.time_limit_minutes is not None:
            update_data["time_limit_minutes"] = request.time_limit_minutes

        if request.is_active is not None:
            update_data["is_active"] = request.is_active

        if request.title is not None:
            update_data["title"] = request.title

        if request.description is not None:
            update_data["description"] = request.description

        # Update in database
        result = mongo_service.db["online_tests"].update_one(
            {"_id": ObjectId(test_id)}, {"$set": update_data}
        )

        if result.modified_count == 0:
            raise HTTPException(
                status_code=500, detail="Failed to update configuration"
            )

        logger.info(f"✅ Updated configuration for test {test_id}")

        return {
            "success": True,
            "test_id": test_id,
            "updated_fields": list(update_data.keys()),
            "updated_at": update_data["updated_at"].isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update test config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{test_id}/questions", response_model=dict, tags=["Phase 3 - Editing"])
async def update_test_questions(
    test_id: str,
    request: UpdateTestQuestionsRequest,
    user_info: dict = Depends(require_auth),
):
    """
    Update test questions and answers
    Only the test creator can edit questions
    Validates question structure before saving
    """
    try:
        user_id = user_info["uid"]
        mongo_service = get_mongodb_service()

        # Verify test exists and user is creator
        test_doc = mongo_service.db["online_tests"].find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        if test_doc["creator_id"] != user_id:
            raise HTTPException(
                status_code=403, detail="Only the test creator can edit questions"
            )

        # Validate questions structure
        if not request.questions or len(request.questions) == 0:
            raise HTTPException(
                status_code=400, detail="At least one question is required"
            )

        if len(request.questions) > 100:
            raise HTTPException(status_code=400, detail="Maximum 100 questions allowed")

        for idx, q in enumerate(request.questions):
            # Validate required fields
            if not q.get("question_text"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Question {idx + 1}: question_text is required",
                )

            if not q.get("options") or len(q["options"]) < 2:
                raise HTTPException(
                    status_code=400,
                    detail=f"Question {idx + 1}: At least 2 options are required",
                )

            # Support both correct_answer_key (string) and correct_answer_keys (array)
            has_correct_answer_key = q.get("correct_answer_key")
            has_correct_answer_keys = q.get("correct_answer_keys")

            if not has_correct_answer_key and not has_correct_answer_keys:
                raise HTTPException(
                    status_code=400,
                    detail=f"Question {idx + 1}: correct_answer_key or correct_answer_keys is required",
                )

            # Get option keys for validation
            option_keys = [opt.get("key") for opt in q["options"]]

            # Normalize to correct_answer_keys array format
            if has_correct_answer_keys:
                # Ensure it's an array
                if isinstance(q["correct_answer_keys"], str):
                    q["correct_answer_keys"] = [q["correct_answer_keys"]]

                # Validate all correct answers exist in options
                for ans in q["correct_answer_keys"]:
                    if ans not in option_keys:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Question {idx + 1}: correct answer '{ans}' not found in options {option_keys}",
                        )

                # Also set correct_answer_key for backwards compatibility (first correct answer)
                q["correct_answer_key"] = q["correct_answer_keys"][0]

            elif has_correct_answer_key:
                # Old format: single correct answer
                if q["correct_answer_key"] not in option_keys:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Question {idx + 1}: correct_answer_key '{q['correct_answer_key']}' "
                        f"not found in options {option_keys}",
                    )

                # Convert to new format
                q["correct_answer_keys"] = [q["correct_answer_key"]]

            # Ensure question_id exists (generate if missing)
            if not q.get("question_id"):
                q["question_id"] = str(ObjectId())

        # Update questions in database
        result = mongo_service.db["online_tests"].update_one(
            {"_id": ObjectId(test_id)},
            {"$set": {"questions": request.questions, "updated_at": datetime.utcnow()}},
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=500, detail="Failed to update questions")

        logger.info(f"✅ Updated {len(request.questions)} questions for test {test_id}")

        return {
            "success": True,
            "test_id": test_id,
            "questions_updated": len(request.questions),
            "updated_at": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update questions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{test_id}/preview", response_model=TestPreviewResponse, tags=["Phase 3 - Editing"]
)
async def preview_test(
    test_id: str,
    user_info: dict = Depends(require_auth),
):
    """
    Preview test with all details including correct answers
    Only the test creator can preview with answers
    """
    try:
        user_id = user_info["uid"]
        mongo_service = get_mongodb_service()

        # Get test document
        test_doc = mongo_service.db["online_tests"].find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        if test_doc["creator_id"] != user_id:
            raise HTTPException(
                status_code=403, detail="Only the test creator can preview with answers"
            )

        return TestPreviewResponse(
            test_id=str(test_doc["_id"]),
            title=test_doc["title"],
            time_limit_minutes=test_doc["time_limit_minutes"],
            max_retries=test_doc["max_retries"],
            is_active=test_doc.get("is_active", True),
            total_questions=len(test_doc["questions"]),
            questions=test_doc["questions"],  # Includes correct_answer_key
            created_at=test_doc["created_at"].isoformat(),
            updated_at=test_doc.get("updated_at", test_doc["created_at"]).isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to preview test: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{test_id}", response_model=dict, tags=["Phase 3 - Editing"])
async def delete_test(
    test_id: str,
    user_info: dict = Depends(require_auth),
):
    """
    Delete a test (soft delete by setting is_active=false)
    Only the test creator can delete
    """
    try:
        user_id = user_info["uid"]
        mongo_service = get_mongodb_service()

        # Verify test exists and user is creator
        test_doc = mongo_service.db["online_tests"].find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        if test_doc["creator_id"] != user_id:
            raise HTTPException(
                status_code=403, detail="Only the test creator can delete"
            )

        # Soft delete by setting is_active=false
        result = mongo_service.db["online_tests"].update_one(
            {"_id": ObjectId(test_id)},
            {"$set": {"is_active": False, "updated_at": datetime.utcnow()}},
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=500, detail="Failed to delete test")

        logger.info(f"🗑️ Soft deleted test {test_id}")

        return {
            "success": True,
            "test_id": test_id,
            "message": "Test deactivated successfully",
            "deleted_at": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete test: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{test_id}/attempts", response_model=dict, tags=["Phase 3 - Editing"])
async def get_test_attempts(
    test_id: str,
    user_info: dict = Depends(require_auth),
):
    """
    Get user's attempt history for a specific test

    Returns:
    - Summary: total attempts, remaining attempts, best score
    - List of all submissions with basic info
    - Click on submission_id to get full details via GET /me/submissions/{submission_id}

    **Example:**
    User A làm test XX 3 lần:
    - Attempt 1: score 5.0/10 (50%) - PASS
    - Attempt 2: score 7.0/10 (70%) - PASS
    - Attempt 3: score 8.0/10 (80%) - PASS
    """
    try:
        user_id = user_info["uid"]
        mongo_service = get_mongodb_service()

        # Verify test exists
        test_doc = mongo_service.db["online_tests"].find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        # Check if user is creator (unlimited attempts)
        is_creator = test_doc.get("creator_id") == user_id

        # Get all submissions for this user and test (sorted newest first)
        submissions = list(
            mongo_service.db["test_submissions"]
            .find({"test_id": test_id, "user_id": user_id})
            .sort("submitted_at", -1)
        )

        attempts_used = len(submissions)
        max_retries = test_doc.get("max_retries", 3)

        # Creator has unlimited attempts
        if is_creator:
            attempts_remaining = float("inf")  # Unlimited
            can_retake = True
        else:
            attempts_remaining = max(0, max_retries - attempts_used)
            can_retake = attempts_remaining > 0

        # Get best score
        best_score = 0
        if submissions:
            best_score = max(sub.get("score", 0) for sub in submissions)

        # Build submission list with more details
        submission_list = []
        for sub in submissions:
            submission_list.append(
                {
                    "submission_id": str(sub["_id"]),
                    "score": sub.get("score", 0),  # Thang điểm 10
                    "score_percentage": sub.get(
                        "score_percentage", sub.get("score", 0) * 10
                    ),
                    "correct_answers": sub.get("correct_answers", 0),
                    "total_questions": sub.get("total_questions", 0),
                    "is_passed": sub.get("is_passed", False),
                    "attempt_number": sub.get("attempt_number", 0),
                    "time_taken_seconds": sub.get("time_taken_seconds", 0),
                    "submitted_at": sub["submitted_at"].isoformat(),
                }
            )

        logger.info(
            f"📊 Get attempts for test {test_id}: user={user_id}, "
            f"attempts={attempts_used}/{max_retries}, best_score={best_score}/10"
        )

        return {
            "test_id": test_id,
            "test_title": test_doc["title"],
            "is_creator": is_creator,
            "max_retries": max_retries if not is_creator else None,  # None = unlimited
            "attempts_used": attempts_used,
            "attempts_remaining": "unlimited" if is_creator else attempts_remaining,
            "best_score": best_score,
            "can_retake": can_retake,
            "submissions": submission_list,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get attempts: {e}")
        raise HTTPException(status_code=500, detail=str(e))
