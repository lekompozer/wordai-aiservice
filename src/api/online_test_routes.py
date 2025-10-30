"""
Online Test API Routes - Phase 1
Endpoints for test generation, taking tests, and submission
"""

import logging
from typing import Optional
from datetime import datetime
from bson import ObjectId

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from src.utils.auth import require_auth
from src.services.test_generator_service import get_test_generator_service
from src.services.mongodb_service import get_mongodb_service
from src.services.document_manager import get_document_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tests", tags=["Online Tests - Phase 1"])


# ========== Request/Response Models ==========


class GenerateTestRequest(BaseModel):
    """Request model for test generation"""

    source_type: str = Field(..., description="Source type: 'document' or 'file'")
    source_id: str = Field(..., description="Document ID or R2 file key")
    user_query: str = Field(
        ..., description="Description of what to test", min_length=10, max_length=500
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
        logger.info(f"   Query: {request.user_query}")
        logger.info(
            f"   Questions: {request.num_questions}, Time: {request.time_limit_minutes}min"
        )

        # Get content based on source type
        if request.source_type == "document":
            # Get document from MongoDB
            doc_manager = get_document_manager()
            try:
                doc = doc_manager.get_document(request.source_id, user_info["uid"])
                content = doc.get("content_html", "")

                if not content:
                    raise HTTPException(
                        status_code=400, detail="Document has no content"
                    )

                # Strip HTML tags to get plain text
                import re

                content = re.sub(r"<[^>]+>", " ", content)
                content = re.sub(r"\s+", " ", content).strip()

            except Exception as e:
                logger.error(f"❌ Failed to get document: {e}")
                raise HTTPException(
                    status_code=404,
                    detail=f"Document not found or access denied: {str(e)}",
                )

        elif request.source_type == "file":
            # Get file from R2
            # TODO: Implement R2 file fetching
            # For now, return error
            raise HTTPException(
                status_code=501,
                detail="File source not yet implemented. Use 'document' source type.",
            )

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid source_type: {request.source_type}. Must be 'document' or 'file'",
            )

        # Generate test
        test_generator = get_test_generator_service()

        test_id, metadata = await test_generator.generate_test_from_content(
            content=content,
            user_query=request.user_query,
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
