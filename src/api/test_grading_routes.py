"""
Online Test Grading Routes
Endpoints for grading queue, dashboard, and manual essay grading
"""

import logging
import os
import uuid
from typing import Optional, Dict, Any
from datetime import datetime
from bson import ObjectId

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    BackgroundTasks,
    UploadFile,
    File,
    Form,
    Query,
)

from src.middleware.auth import verify_firebase_token as require_auth
from src.models.online_test_models import *
from src.services.online_test_utils import *

logger = logging.getLogger("chatbot")

router = APIRouter(prefix="/api/v1/tests", tags=["Test Grading"])


@router.get("/{test_id}/grading-queue", tags=["Phase 4 - Grading"])
async def get_grading_queue(
    test_id: str,
    status: Optional[str] = None,
    user_info: dict = Depends(require_auth),
):
    """
    Get list of submissions pending grading for a specific test

    **Access:** Only test owner can view grading queue

    **Query Params:**
    - status: Filter by status (pending, in_progress, completed)

    **Returns:**
    - List of submissions with essay questions needing grading
    - Sorted by submission time (oldest first)
    """
    try:
        mongo_service = get_mongodb_service()

        # Verify test exists and user is owner
        test_doc = mongo_service.db["online_tests"].find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        if test_doc["creator_id"] != user_info["uid"]:
            raise HTTPException(
                status_code=403, detail="Only test owner can view grading queue"
            )

        # Query grading queue
        grading_queue = mongo_service.db["grading_queue"]

        query = {"test_id": test_id}
        if status:
            if status not in ["pending", "in_progress", "completed"]:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid status. Must be: pending, in_progress, or completed",
                )
            query["status"] = status

        queue_items = list(grading_queue.find(query).sort("submitted_at", 1))

        # Format response
        results = []
        for item in queue_items:
            results.append(
                {
                    "submission_id": item["submission_id"],
                    "student_id": item["student_id"],
                    "student_name": item.get("student_name"),
                    "submitted_at": item["submitted_at"],
                    "essay_question_count": item["essay_question_count"],
                    "graded_count": item["graded_count"],
                    "assigned_to": item.get("assigned_to"),
                    "priority": item.get("priority", 0),
                    "status": item["status"],
                }
            )

        logger.info(
            f"📋 Grading queue for test {test_id}: {len(results)} items (status={status or 'all'})"
        )

        return {
            "success": True,
            "test_id": test_id,
            "test_title": test_doc.get("title"),
            "total_count": len(results),
            "queue": results,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get grading queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/submissions/{submission_id}/grading-view", tags=["Phase 4 - Grading"])
async def get_submission_for_grading(
    submission_id: str,
    user_info: dict = Depends(require_auth),
):
    """
    Get submission details for grading interface

    **Access:** Only test owner can view submissions for grading

    **Returns:**
    - Student's essay answers
    - Grading rubrics for each question
    - Current grades (if any)
    - MCQ results (for context)
    """
    try:
        mongo_service = get_mongodb_service()

        # Get submission
        submission = mongo_service.db["test_submissions"].find_one(
            {"_id": ObjectId(submission_id)}
        )
        if not submission:
            raise HTTPException(status_code=404, detail="Submission not found")

        # Get test and verify owner
        test_doc = mongo_service.db["online_tests"].find_one(
            {"_id": ObjectId(submission["test_id"])}
        )
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        if test_doc["creator_id"] != user_info["uid"]:
            raise HTTPException(
                status_code=403, detail="Only test owner can grade submissions"
            )

        # Get student info
        student = mongo_service.db.users.find_one(
            {"firebase_uid": submission["user_id"]}
        )
        student_name = (
            student.get("name") or student.get("display_name") if student else "Unknown"
        )
        student_email = student.get("email") if student else None

        # Build essay questions for grading
        essay_questions = []
        user_answers_map = {}

        for ans in submission["user_answers"]:
            q_id = ans.get("question_id")
            ans_type = ans.get("question_type", "mcq")
            if ans_type == "essay":
                user_answers_map[q_id] = ans.get("essay_answer", "")

        # Get existing grades
        essay_grades_map = {}
        if submission.get("essay_grades"):
            for grade in submission["essay_grades"]:
                essay_grades_map[grade["question_id"]] = grade

        for q in test_doc["questions"]:
            if q.get("question_type") == "essay":
                question_id = q["question_id"]
                existing_grade = essay_grades_map.get(question_id)

                essay_questions.append(
                    {
                        "question_id": question_id,
                        "question_text": q["question_text"],
                        "max_points": q.get("max_points", 1),
                        "grading_rubric": q.get("grading_rubric"),
                        "student_answer": user_answers_map.get(question_id, ""),
                        "current_grade": (
                            {
                                "points_awarded": existing_grade.get("points_awarded"),
                                "feedback": existing_grade.get("feedback"),
                                "graded_by": existing_grade.get("graded_by"),
                                "graded_at": existing_grade.get("graded_at"),
                            }
                            if existing_grade
                            else None
                        ),
                    }
                )

        # MCQ summary for context
        mcq_summary = {
            "mcq_score": submission.get("mcq_score"),
            "mcq_correct_count": submission.get("mcq_correct_count"),
        }

        logger.info(
            f"📝 Grading view for submission {submission_id}: {len(essay_questions)} essays"
        )

        return {
            "success": True,
            "submission_id": submission_id,
            "test_id": submission["test_id"],
            "test_title": test_doc.get("title"),
            "student_id": submission["user_id"],
            "student_name": student_name,
            "student_email": student_email,
            "submitted_at": submission["submitted_at"].isoformat(),
            "time_taken_seconds": submission.get("time_taken_seconds", 0),
            "grading_status": submission.get("grading_status", "pending_grading"),
            "mcq_summary": mcq_summary,
            "essay_questions": essay_questions,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get submission for grading: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/submissions/{submission_id}/grade-essay", tags=["Phase 4 - Grading"])
async def grade_single_essay(
    submission_id: str,
    request: GradeEssayRequest,
    user_info: dict = Depends(require_auth),
):
    """
    Grade a single essay question in a submission

    **Access:** Only test owner can grade

    **Updates:**
    - Adds/updates grade for specific essay question
    - Updates grading_status (partially_graded or fully_graded)
    - Recalculates final score if all essays are graded
    - Updates grading queue
    """
    try:
        mongo_service = get_mongodb_service()

        # Get submission
        submission = mongo_service.db["test_submissions"].find_one(
            {"_id": ObjectId(submission_id)}
        )
        if not submission:
            raise HTTPException(status_code=404, detail="Submission not found")

        # Get test and verify owner
        test_doc = mongo_service.db["online_tests"].find_one(
            {"_id": ObjectId(submission["test_id"])}
        )
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        if test_doc["creator_id"] != user_info["uid"]:
            raise HTTPException(
                status_code=403, detail="Only test owner can grade submissions"
            )

        # Verify question exists and is essay type
        question = None
        for q in test_doc["questions"]:
            if q["question_id"] == request.question_id:
                question = q
                break

        if not question:
            raise HTTPException(status_code=404, detail="Question not found")

        if question.get("question_type") != "essay":
            raise HTTPException(
                status_code=400, detail="Can only grade essay questions"
            )

        # Validate points_awarded
        max_points = question.get("max_points", 1)
        if request.points_awarded > max_points:
            raise HTTPException(
                status_code=400,
                detail=f"Points awarded ({request.points_awarded}) cannot exceed max_points ({max_points})",
            )

        # Create/update grade
        new_grade = {
            "question_id": request.question_id,
            "points_awarded": request.points_awarded,
            "max_points": max_points,
            "feedback": request.feedback,
            "graded_by": user_info["uid"],
            "graded_at": datetime.now().isoformat(),
        }

        # Update or add grade
        essay_grades = submission.get("essay_grades", [])
        grade_updated = False

        for i, grade in enumerate(essay_grades):
            if grade["question_id"] == request.question_id:
                essay_grades[i] = new_grade
                grade_updated = True
                break

        if not grade_updated:
            essay_grades.append(new_grade)

        # Count essay questions
        essay_questions = [
            q for q in test_doc["questions"] if q.get("question_type") == "essay"
        ]
        total_essays = len(essay_questions)
        graded_essays = len(essay_grades)

        # Determine new grading status
        if graded_essays == total_essays:
            new_status = "fully_graded"
            # Calculate final score
            final_score = calculate_final_score(submission, test_doc, essay_grades)
        elif graded_essays > 0:
            new_status = "partially_graded"
            final_score = None  # Don't calculate until all graded
        else:
            new_status = "pending_grading"
            final_score = None

        # Update submission
        update_data = {
            "essay_grades": essay_grades,
            "grading_status": new_status,
        }

        if final_score is not None:
            update_data["score"] = final_score["score"]
            update_data["score_percentage"] = final_score["score_percentage"]
            update_data["is_passed"] = final_score["is_passed"]

        mongo_service.db["test_submissions"].update_one(
            {"_id": ObjectId(submission_id)}, {"$set": update_data}
        )

        # Update grading queue
        mongo_service.db["grading_queue"].update_one(
            {"submission_id": submission_id},
            {
                "$set": {
                    "graded_count": graded_essays,
                    "status": (
                        "completed" if new_status == "fully_graded" else "in_progress"
                    ),
                }
            },
        )

        logger.info(
            f"✅ Graded essay {request.question_id} in submission {submission_id}: "
            f"{request.points_awarded}/{max_points} points, status={new_status}"
        )

        return {
            "success": True,
            "submission_id": submission_id,
            "question_id": request.question_id,
            "points_awarded": request.points_awarded,
            "max_points": max_points,
            "grading_status": new_status,
            "graded_essays": graded_essays,
            "total_essays": total_essays,
            "final_score": final_score,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to grade essay: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def calculate_final_score(submission: dict, test_doc: dict, essay_grades: list) -> dict:
    """
    Calculate final score when all questions are graded

    Returns:
        dict with score, score_percentage, is_passed
    """
    # Get MCQ score (handle None case)
    mcq_score = submission.get("mcq_score") or 0

    # Calculate essay score (handle None points_awarded)
    essay_score = sum(grade.get("points_awarded") or 0 for grade in essay_grades)

    # Calculate total
    total_score = mcq_score + essay_score

    # Calculate max possible score
    mcq_questions = [
        q for q in test_doc["questions"] if q.get("question_type", "mcq") == "mcq"
    ]
    essay_questions = [
        q for q in test_doc["questions"] if q.get("question_type") == "essay"
    ]

    max_mcq = sum(q.get("max_points", 1) for q in mcq_questions)
    max_essay = sum(q.get("max_points", 1) for q in essay_questions)
    max_total = max_mcq + max_essay

    # Calculate percentage and score out of 10
    score_percentage = round(total_score / max_total * 100, 2) if max_total > 0 else 0
    score_out_of_10 = round(total_score / max_total * 10, 2) if max_total > 0 else 0

    # Check if passed
    passing_score = test_doc.get("passing_score", 70)
    is_passed = score_percentage >= passing_score

    return {
        "score": score_out_of_10,
        "score_percentage": score_percentage,
        "is_passed": is_passed,
        "total_score": total_score,
        "max_total": max_total,
    }


@router.post(
    "/submissions/{submission_id}/grade-all-essays", tags=["Phase 4 - Grading"]
)
async def grade_all_essays(
    submission_id: str,
    request: GradeAllEssaysRequest,
    background_tasks: BackgroundTasks,
    user_info: dict = Depends(require_auth),
):
    """
    Grade all essay questions in a submission at once

    **Access:** Only test owner can grade

    **Updates:**
    - Adds grades for all essay questions
    - Sets grading_status to fully_graded
    - Calculates final score
    - Sends notification email to student
    """
    try:
        mongo_service = get_mongodb_service()

        # Get submission
        submission = mongo_service.db["test_submissions"].find_one(
            {"_id": ObjectId(submission_id)}
        )
        if not submission:
            raise HTTPException(status_code=404, detail="Submission not found")

        # Get test and verify owner
        test_doc = mongo_service.db["online_tests"].find_one(
            {"_id": ObjectId(submission["test_id"])}
        )
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        if test_doc["creator_id"] != user_info["uid"]:
            raise HTTPException(
                status_code=403, detail="Only test owner can grade submissions"
            )

        # Validate all grades
        essay_questions_map = {
            q["question_id"]: q
            for q in test_doc["questions"]
            if q.get("question_type") == "essay"
        }

        essay_grades = []
        for grade_req in request.grades:
            if grade_req.question_id not in essay_questions_map:
                raise HTTPException(
                    status_code=400,
                    detail=f"Question {grade_req.question_id} not found or not an essay question",
                )

            question = essay_questions_map[grade_req.question_id]
            max_points = question.get("max_points", 1)

            if grade_req.points_awarded > max_points:
                raise HTTPException(
                    status_code=400,
                    detail=f"Points for {grade_req.question_id} ({grade_req.points_awarded}) exceed max ({max_points})",
                )

            essay_grades.append(
                {
                    "question_id": grade_req.question_id,
                    "points_awarded": grade_req.points_awarded,
                    "max_points": max_points,
                    "feedback": grade_req.feedback,
                    "graded_by": user_info["uid"],
                    "graded_at": datetime.now().isoformat(),
                }
            )

        # Calculate final score
        final_score = calculate_final_score(submission, test_doc, essay_grades)

        # Update submission
        mongo_service.db["test_submissions"].update_one(
            {"_id": ObjectId(submission_id)},
            {
                "$set": {
                    "essay_grades": essay_grades,
                    "grading_status": "fully_graded",
                    "score": final_score["score"],
                    "score_percentage": final_score["score_percentage"],
                    "is_passed": final_score["is_passed"],
                }
            },
        )

        # Update grading queue
        mongo_service.db["grading_queue"].update_one(
            {"submission_id": submission_id},
            {
                "$set": {
                    "graded_count": len(essay_grades),
                    "status": "completed",
                }
            },
        )

        # Send notification email to student (Phase 5) + InApp notification
        async def send_grading_complete_notification():
            try:
                from src.services.brevo_email_service import get_brevo_service
                from src.services.notification_manager import NotificationManager

                student = mongo_service.db.users.find_one(
                    {"firebase_uid": submission["user_id"]}
                )
                if student:
                    # Send email notification
                    if student.get("email"):
                        brevo = get_brevo_service()
                        await asyncio.to_thread(
                            brevo.send_grading_complete_notification,
                            to_email=student["email"],
                            student_name=student.get("name")
                            or student.get("display_name")
                            or "Student",
                            test_title=test_doc["title"],
                            score=final_score["score"],
                            is_passed=final_score["is_passed"],
                        )
                        logger.info(
                            f"   📧 Sent grading complete email to {student['email']}"
                        )

                    # Create InApp notification
                    notification_manager = NotificationManager(db=mongo_service.db)
                    notification_manager.create_test_grading_notification(
                        student_id=submission["user_id"],
                        test_id=submission["test_id"],
                        test_title=test_doc["title"],
                        submission_id=submission_id,
                        score=final_score["score"],
                        score_percentage=final_score["score_percentage"],
                        is_passed=final_score["is_passed"],
                    )
                    logger.info(
                        f"   🔔 Created InApp notification for user {submission['user_id']}"
                    )

            except Exception as e:
                logger.error(f"   ⚠️ Failed to send grading notification: {e}")

        background_tasks.add_task(send_grading_complete_notification)

        logger.info(
            f"✅ Graded all essays in submission {submission_id}: "
            f"{len(essay_grades)} essays, final_score={final_score['score']}/10"
        )

        return {
            "success": True,
            "submission_id": submission_id,
            "grading_status": "fully_graded",
            "graded_essays": len(essay_grades),
            "final_score": final_score,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to grade all essays: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/me/grading-dashboard", tags=["Phase 4 - Grading"])
async def get_grading_dashboard(
    user_info: dict = Depends(require_auth),
):
    """
    Get grading dashboard for test owner

    **Returns:**
    - Summary of all tests with pending grading
    - Total pending submissions across all tests
    - Recently graded submissions
    """
    try:
        mongo_service = get_mongodb_service()

        # Get all tests owned by user
        owned_tests = list(
            mongo_service.db["online_tests"].find({"creator_id": user_info["uid"]})
        )

        test_ids = [str(test["_id"]) for test in owned_tests]

        # Get grading queue for all owned tests
        grading_queue = mongo_service.db["grading_queue"]

        pending_items = list(
            grading_queue.find(
                {
                    "test_id": {"$in": test_ids},
                    "status": {"$in": ["pending", "in_progress"]},
                }
            ).sort("submitted_at", 1)
        )

        # Group by test
        tests_summary = {}
        for item in pending_items:
            test_id = item["test_id"]
            if test_id not in tests_summary:
                test = next((t for t in owned_tests if str(t["_id"]) == test_id), None)
                tests_summary[test_id] = {
                    "test_id": test_id,
                    "test_title": test.get("title") if test else "Unknown",
                    "pending_count": 0,
                    "oldest_submission": None,
                }

            tests_summary[test_id]["pending_count"] += 1
            if tests_summary[test_id]["oldest_submission"] is None:
                tests_summary[test_id]["oldest_submission"] = item["submitted_at"]

        # Get recently graded (last 10)
        recently_graded = list(
            grading_queue.find({"test_id": {"$in": test_ids}, "status": "completed"})
            .sort("submitted_at", -1)
            .limit(10)
        )

        recent_summary = []
        for item in recently_graded:
            test = next(
                (t for t in owned_tests if str(t["_id"]) == item["test_id"]), None
            )
            recent_summary.append(
                {
                    "submission_id": item["submission_id"],
                    "test_title": test.get("title") if test else "Unknown",
                    "student_name": item.get("student_name"),
                    "submitted_at": item["submitted_at"],
                    "graded_count": item["graded_count"],
                    "essay_question_count": item["essay_question_count"],
                }
            )

        total_pending = sum(t["pending_count"] for t in tests_summary.values())

        logger.info(
            f"📊 Grading dashboard for {user_info['uid']}: {total_pending} pending"
        )

        return {
            "success": True,
            "total_pending": total_pending,
            "tests_with_pending": list(tests_summary.values()),
            "recently_graded": recent_summary,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get grading dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch(
    "/submissions/{submission_id}/update-essay-grade", tags=["Phase 4 - Grading"]
)
async def update_essay_grade(
    submission_id: str,
    request: GradeEssayRequest,
    background_tasks: BackgroundTasks,
    user_info: dict = Depends(require_auth),
):
    """
    Update an existing essay grade (edit previously graded essay)

    **Access:** Only test owner can update grades

    **Updates:**
    - Updates grade for specific essay question
    - Recalculates final score
    - Sends update notification email to student
    """
    try:
        mongo_service = get_mongodb_service()

        # Get submission
        submission = mongo_service.db["test_submissions"].find_one(
            {"_id": ObjectId(submission_id)}
        )
        if not submission:
            raise HTTPException(status_code=404, detail="Submission not found")

        # Get test and verify owner
        test_doc = mongo_service.db["online_tests"].find_one(
            {"_id": ObjectId(submission["test_id"])}
        )
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        if test_doc["creator_id"] != user_info["uid"]:
            raise HTTPException(
                status_code=403, detail="Only test owner can update grades"
            )

        # Find existing grade
        essay_grades = submission.get("essay_grades", [])
        grade_found = False

        for i, grade in enumerate(essay_grades):
            if grade["question_id"] == request.question_id:
                # Update grade
                question = next(
                    (
                        q
                        for q in test_doc["questions"]
                        if q["question_id"] == request.question_id
                    ),
                    None,
                )
                if not question:
                    raise HTTPException(status_code=404, detail="Question not found")

                max_points = question.get("max_points", 1)
                if request.points_awarded > max_points:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Points awarded ({request.points_awarded}) cannot exceed max_points ({max_points})",
                    )

                essay_grades[i] = {
                    "question_id": request.question_id,
                    "points_awarded": request.points_awarded,
                    "max_points": max_points,
                    "feedback": request.feedback,
                    "graded_by": user_info["uid"],
                    "graded_at": datetime.now().isoformat(),
                }
                grade_found = True
                break

        if not grade_found:
            raise HTTPException(
                status_code=404,
                detail="Grade not found. Use /grade-essay to create a new grade.",
            )

        # Recalculate final score
        final_score = calculate_final_score(submission, test_doc, essay_grades)

        # Update submission
        mongo_service.db["test_submissions"].update_one(
            {"_id": ObjectId(submission_id)},
            {
                "$set": {
                    "essay_grades": essay_grades,
                    "score": final_score["score"],
                    "score_percentage": final_score["score_percentage"],
                    "is_passed": final_score["is_passed"],
                }
            },
        )

        # Send update notification email
        async def send_grade_updated_notification():
            try:
                from src.services.brevo_email_service import get_brevo_service

                student = mongo_service.db.users.find_one(
                    {"firebase_uid": submission["user_id"]}
                )
                if student and student.get("email"):
                    brevo = get_brevo_service()
                    await asyncio.to_thread(
                        brevo.send_grade_updated_notification,
                        to_email=student["email"],
                        student_name=student.get("name")
                        or student.get("display_name")
                        or "Student",
                        test_title=test_doc["title"],
                        score=final_score["score"],
                        is_passed=final_score["is_passed"],
                    )
                    logger.info(f"   📧 Sent grade update email to {student['email']}")
            except Exception as e:
                logger.error(f"   ⚠️ Failed to send grade update notification: {e}")

        background_tasks.add_task(send_grade_updated_notification)

        logger.info(
            f"✅ Updated essay grade for {request.question_id} in submission {submission_id}: "
            f"{request.points_awarded} points, new_score={final_score['score']}/10"
        )

        return {
            "success": True,
            "submission_id": submission_id,
            "question_id": request.question_id,
            "points_awarded": request.points_awarded,
            "final_score": final_score,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update essay grade: {e}")
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
    passing_score: Optional[int] = Field(
        None, description="Minimum score percentage to pass (0-100)", ge=0, le=100
    )
    deadline: Optional[datetime] = Field(
        None, description="Global deadline for all users (ISO 8601 format)"
    )
    show_answers_timing: Optional[str] = Field(
        None,
        description="When to show answers: 'immediate' or 'after_deadline'",
    )
    is_active: Optional[bool] = Field(None, description="Active status")
    title: Optional[str] = Field(None, description="Test title", max_length=200)
    description: Optional[str] = Field(
        None, description="Test description", max_length=5000
    )
    evaluation_criteria: Optional[str] = Field(
        None,
        description="AI evaluation criteria for test results (max 5000 chars)",
        max_length=5000,
    )


class UpdateTestQuestionsRequest(BaseModel):
    """Request model for updating test questions"""

    questions: list = Field(..., description="Updated questions array")


class UpdateMarketplaceConfigRequest(BaseModel):
    """Request model for updating marketplace configuration"""

    title: Optional[str] = Field(
        None, description="Marketplace title", min_length=10, max_length=200
    )
    description: Optional[str] = Field(
        None, description="Full description", min_length=50, max_length=2000
    )
    short_description: Optional[str] = Field(
        None, description="Short description for cards", max_length=150
    )
    price_points: Optional[int] = Field(None, description="Price in points", ge=0)
    category: Optional[str] = Field(None, description="Test category")
    tags: Optional[str] = Field(None, description="Comma-separated tags")
    difficulty_level: Optional[str] = Field(None, description="Difficulty level")
    is_public: Optional[bool] = Field(
        None, description="Public status (unpublish if False)"
    )


class FullTestEditRequest(BaseModel):
    """Request model for comprehensive test editing (owner only)"""

    # Basic config
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=5000)
    is_active: Optional[bool] = None

    # Test settings
    max_retries: Optional[int] = Field(None, ge=1, le=20)
    time_limit_minutes: Optional[int] = Field(None, ge=1, le=300)
    passing_score: Optional[int] = Field(None, ge=0, le=100)
    deadline: Optional[datetime] = None
    show_answers_timing: Optional[str] = None

    # Questions
    questions: Optional[list] = None

    # Attachments (NEW)
    attachments: Optional[list[TestAttachment]] = Field(
        None,
        description="List of PDF attachments for reading comprehension",
    )

    # ========== PHASE 7 & 8: Listening test source fields ==========
    user_transcript: Optional[str] = Field(
        None,
        max_length=5000,
        description="User-provided transcript text for listening test (Phase 7)",
    )
    youtube_url: Optional[str] = Field(
        None,
        max_length=500,
        description="YouTube URL for listening test audio source (Phase 8)",
    )

    # Marketplace config (if published)
    marketplace_title: Optional[str] = Field(None, min_length=10, max_length=200)
    marketplace_description: Optional[str] = Field(None, min_length=50, max_length=5000)
    short_description: Optional[str] = Field(None, max_length=200)
    price_points: Optional[int] = Field(None, ge=0)
    category: Optional[str] = None
    tags: Optional[str] = None
    difficulty_level: Optional[str] = None
    evaluation_criteria: Optional[str] = Field(
        None,
        description="AI evaluation criteria for test results (max 5000 chars)",
        max_length=5000,
    )


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
