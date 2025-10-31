"""
Online Test API Routes - Phase 1, 2, 3
Endpoints for test generation, taking tests, submission, WebSocket auto-save, and test editing
"""

import logging
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


router = APIRouter(prefix="/api/v1/tests", tags=["Online Tests - Phase 1"])


# ========== Request/Response Models ==========


class GenerateTestRequest(BaseModel):
    """Request model for test generation"""

    source_type: str = Field(..., description="Source type: 'document' or 'file'")
    source_id: str = Field(..., description="Document ID or R2 file key")
    title: str = Field(..., description="Test title", min_length=5, max_length=200)
    user_query: str = Field(
        ...,
        description="What topics/concepts to test (e.g., 'Kiến thức về bất động sản', 'Python programming basics')",
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


class TestQuestionsResponse(BaseModel):
    """Response model for test questions (for taking)"""

    test_id: str
    title: str
    time_limit_minutes: int
    num_questions: int
    questions: list


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


@router.post("/generate")
async def generate_test(
    request: GenerateTestRequest,
    background_tasks: BackgroundTasks,
    user_info: dict = Depends(require_auth),
):
    """
    Generate a new test from document or file

    **Phase 1 Feature**

    Uses Gemini 2.5 Pro with JSON Mode to generate multiple-choice questions.
    """
    try:
        logger.info(f"📝 Test generation request from user {user_info['uid']}")
        logger.info(f"   Source: {request.source_type}/{request.source_id}")
        logger.info(f"   Title: {request.title}")
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
            
            user_manager = get_user_manager()
            file_info = user_manager.get_file_by_id(request.source_id, user_info["uid"])
            
            if not file_info:
                raise HTTPException(
                    status_code=404,
                    detail=f"File not found: {request.source_id}"
                )
            
            # Check if file is PDF (required for Gemini File API)
            file_type = file_info.get("file_type", "").lower()
            if file_type != ".pdf":
                raise HTTPException(
                    status_code=400,
                    detail=f"Only PDF files are supported for direct file processing. Your file is {file_type}. Please convert to document first."
                )
            
            # TODO: Implement R2 PDF file fetching for Gemini
            # Gemini can directly process PDF files via File API
            raise HTTPException(
                status_code=501,
                detail="PDF file processing not yet implemented. Use 'document' source type for now."
            )

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid source_type: {request.source_type}. Must be 'document' or 'file'",
            )

        # Generate test with language parameter
        test_generator = get_test_generator_service()

        test_id, metadata = await test_generator.generate_test_from_content(
            content=content,
            title=request.title,
            user_query=request.user_query,
            language=request.language,
            num_questions=request.num_questions,
            creator_id=user_info["uid"],
            source_type=request.source_type,
            source_id=request.source_id,
            time_limit_minutes=request.time_limit_minutes,
        )

        logger.info(f"✅ Test generated: {test_id}")

        return {
            "success": True,
            "test_id": test_id,
            "message": "Test generated successfully",
            **metadata,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Test generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{test_id}")
async def get_test(
    test_id: str,
    user_info: dict = Depends(require_auth),
):
    """
    Get test details for taking (questions without correct answers)

    **Phase 1 Feature**

    Returns test questions for the user to answer. Does NOT include correct answers.
    """
    try:
        logger.info(f"📖 Get test request: {test_id} from user {user_info['uid']}")

        # Get test
        test_generator = get_test_generator_service()
        test_data = await test_generator.get_test_for_taking(test_id, user_info["uid"])

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

        max_retries = test_doc.get("max_retries", 1)

        # Count user's attempts
        attempts_count = submissions_collection.count_documents(
            {
                "test_id": test_id,
                "user_id": user_info["uid"],
            }
        )

        if max_retries != "unlimited" and attempts_count >= max_retries:
            raise HTTPException(
                status_code=429, detail=f"Maximum attempts ({max_retries}) exceeded"
            )

        # Create session in test_progress (Phase 2 feature, but prepare now)
        import uuid

        session_id = str(uuid.uuid4())

        progress_collection = mongo_service.db["test_progress"]
        progress_collection.insert_one(
            {
                "session_id": session_id,
                "test_id": test_id,
                "user_id": user_info["uid"],
                "current_answers": [],
                "started_at": datetime.now(),
                "last_saved_at": datetime.now(),
                "time_remaining_seconds": test_data["time_limit_minutes"] * 60,
                "is_completed": False,
            }
        )

        logger.info(f"   ✅ Session created: {session_id}")

        return {
            "success": True,
            "session_id": session_id,
            "test": test_data,
            "attempts_used": attempts_count,
            "attempts_remaining": (
                max_retries - attempts_count
                if max_retries != "unlimited"
                else "unlimited"
            ),
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

        # Calculate score
        score = (correct_count / total_questions * 100) if total_questions > 0 else 0

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
            "score": score,
            "total_questions": total_questions,
            "correct_answers": correct_count,
            "time_taken_seconds": 0,  # TODO: Calculate from session start time (Phase 2)
            "attempt_number": attempt_number,
            "is_passed": score >= 70,  # 70% pass threshold
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

        logger.info(f"✅ Test submitted: score={score:.1f}%, attempt={attempt_number}")

        return {
            "success": True,
            "submission_id": submission_id,
            "score": score,
            "total_questions": total_questions,
            "correct_answers": correct_count,
            "attempt_number": attempt_number,
            "is_passed": score >= 70,
            "results": results,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Test submission failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/me/tests")
async def get_my_tests(
    user_info: dict = Depends(require_auth),
):
    """
    Get list of tests created by the current user

    **Phase 1 Feature**
    """
    try:
        logger.info(f"📋 Get my tests for user {user_info['uid']}")

        mongo_service = get_mongodb_service()
        test_collection = mongo_service.db["online_tests"]
        submissions_collection = mongo_service.db["test_submissions"]

        # Get user's created tests
        tests = list(
            test_collection.find(
                {"creator_id": user_info["uid"]}, sort=[("created_at", -1)]
            )
        )

        # Add attempt counts
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
                    "num_questions": len(test["questions"]),
                    "time_limit_minutes": test["time_limit_minutes"],
                    "created_at": test["created_at"].isoformat(),
                    "total_submissions": attempts_count,
                }
            )

        return {"tests": result}

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
        submissions_collection = mongo_service.db["online_tests"]

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
            "score": submission["score"],
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
        user_id = user_info["user_id"]
        mongo = get_mongodb_service()

        # Verify test exists
        test_doc = await mongo.online_tests.find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        # Verify session exists and belongs to user
        session = await mongo.test_progress.find_one({"session_id": request.session_id})

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

        result = await mongo.test_progress.update_one(
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
        user_id = user_info["user_id"]
        mongo = get_mongodb_service()

        # Verify test exists
        test_doc = await mongo.online_tests.find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        # Get session progress
        session = await mongo.test_progress.find_one({"session_id": session_id})

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
        user_id = user_info["user_id"]
        mongo = get_mongodb_service()

        # Verify test exists
        test_doc = await mongo.online_tests.find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        # Find most recent incomplete session for this user and test
        session = await mongo.test_progress.find_one(
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
            await mongo.test_progress.update_one(
                {"_id": session["_id"]}, {"$set": {"is_completed": True}}
            )
            raise HTTPException(
                status_code=410,
                detail="Session expired due to time limit. Please start a new test.",
            )

        # Update time remaining in database
        await mongo.test_progress.update_one(
            {"_id": session["_id"]},
            {"$set": {"time_remaining_seconds": time_remaining}},
        )

        return {
            "session_id": session["session_id"],
            "current_answers": session.get("current_answers", {}),
            "time_remaining_seconds": time_remaining,
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
    Update test configuration (max_retries, time_limit, status, title)
    Only the test creator can update configuration
    """
    try:
        user_id = user_info["user_id"]
        mongo = get_mongodb_service()

        # Verify test exists and user is creator
        test_doc = await mongo.online_tests.find_one({"_id": ObjectId(test_id)})
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

        # Update in database
        result = await mongo.online_tests.update_one(
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
        user_id = user_info["user_id"]
        mongo = get_mongodb_service()

        # Verify test exists and user is creator
        test_doc = await mongo.online_tests.find_one({"_id": ObjectId(test_id)})
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

            if not q.get("correct_answer_key"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Question {idx + 1}: correct_answer_key is required",
                )

            # Validate correct_answer_key exists in options
            option_keys = [opt.get("key") for opt in q["options"]]
            if q["correct_answer_key"] not in option_keys:
                raise HTTPException(
                    status_code=400,
                    detail=f"Question {idx + 1}: correct_answer_key '{q['correct_answer_key']}' "
                    f"not found in options {option_keys}",
                )

            # Ensure question_id exists (generate if missing)
            if not q.get("question_id"):
                q["question_id"] = str(ObjectId())

        # Update questions in database
        result = await mongo.online_tests.update_one(
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
        user_id = user_info["user_id"]
        mongo = get_mongodb_service()

        # Get test document
        test_doc = await mongo.online_tests.find_one({"_id": ObjectId(test_id)})
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
        user_id = user_info["user_id"]
        mongo = get_mongodb_service()

        # Verify test exists and user is creator
        test_doc = await mongo.online_tests.find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        if test_doc["creator_id"] != user_id:
            raise HTTPException(
                status_code=403, detail="Only the test creator can delete"
            )

        # Soft delete by setting is_active=false
        result = await mongo.online_tests.update_one(
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
    Shows how many times attempted and remaining attempts
    """
    try:
        user_id = user_info["user_id"]
        mongo = get_mongodb_service()

        # Verify test exists
        test_doc = await mongo.online_tests.find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        # Count submissions for this user and test
        submissions = (
            await mongo.test_submissions.find(
                {"test_id": ObjectId(test_id), "user_id": user_id}
            )
            .sort("submitted_at", -1)
            .to_list(length=None)
        )

        attempts_used = len(submissions)
        max_retries = test_doc.get("max_retries", 3)
        attempts_remaining = max(0, max_retries - attempts_used)

        # Get best score
        best_score = 0
        if submissions:
            best_score = max(sub.get("score", 0) for sub in submissions)

        return {
            "test_id": test_id,
            "test_title": test_doc["title"],
            "max_retries": max_retries,
            "attempts_used": attempts_used,
            "attempts_remaining": attempts_remaining,
            "best_score": best_score,
            "can_retake": attempts_remaining > 0,
            "submissions": [
                {
                    "submission_id": str(sub["_id"]),
                    "score": sub.get("score", 0),
                    "is_passed": sub.get("is_passed", False),
                    "attempt_number": sub.get("attempt_number", 0),
                    "submitted_at": sub["submitted_at"].isoformat(),
                }
                for sub in submissions
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get attempts: {e}")
        raise HTTPException(status_code=500, detail=str(e))
