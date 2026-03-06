"""
AI Learning Assistant Routes
Two features:
  POST /learning-assistant/solve        → Solve Homework (Gemini Flash)
  GET  /learning-assistant/solve/{id}/status
  POST /learning-assistant/grade        → Grade & Tips (Gemini Flash)
  GET  /learning-assistant/grade/{id}/status
"""

import json
import uuid
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from src.middleware.firebase_auth import get_current_user
from src.queue.queue_manager import QueueManager, set_job_status, get_job_status
from src.services.points_service import get_points_service
from src.models.learning_assistant_models import (
    SolveHomeworkRequest,
    SolveHomeworkResponse,
    GradeRequest,
    GradeResponse,
)

logger = logging.getLogger("chatbot")
router = APIRouter()

POINTS_COST = 2  # Gemini vision — same as analyze-architecture


# ============================================================================
# Feature 1: Solve Homework
# ============================================================================


@router.post("/solve", response_model=SolveHomeworkResponse)
async def start_solve_homework(
    request: SolveHomeworkRequest,
    user: dict = Depends(get_current_user),
):
    """
    Start AI homework solving job.

    Accepts a text question, an image of the question, or both.
    Returns a job_id for status polling.

    Cost: 2 points
    """
    # Validate: at least one source required
    if not request.question_text and not request.question_image:
        raise HTTPException(
            status_code=422,
            detail="Bạn phải cung cấp ít nhất một trong: question_text hoặc question_image",
        )

    user_id = user["uid"]
    points_service = get_points_service()

    # Check & deduct points up-front
    try:
        transaction = await points_service.deduct_points(
            user_id=user_id,
            amount=POINTS_COST,
            service="learning_assistant_solve",
            description=f"AI giải bài tập – môn {request.subject}, lớp {request.grade_level}",
        )
    except Exception as exc:
        if "Không đủ điểm" in str(exc) or "insufficient" in str(exc).lower():
            balance = await points_service.get_points_balance(user_id)
            raise HTTPException(
                status_code=403,
                detail=f"Không đủ điểm. Cần: {POINTS_COST}, Còn lại: {balance['points_remaining']}",
            )
        raise HTTPException(status_code=500, detail=str(exc))

    job_id = f"solve_{uuid.uuid4().hex[:12]}"
    queue = QueueManager(queue_name="learning_assistant_solve")
    await queue.connect()

    job_data = {
        "job_id": job_id,
        "user_id": user_id,
        "question_text": request.question_text,
        "question_image": request.question_image,
        "image_mime_type": request.image_mime_type or "image/jpeg",
        "subject": request.subject,
        "grade_level": request.grade_level,
        "language": request.language or "vi",
    }

    await set_job_status(
        redis_client=queue.redis_client,
        job_id=job_id,
        status="pending",
        user_id=user_id,
        created_at=datetime.utcnow().isoformat(),
    )

    await queue.redis_client.lpush(queue.task_queue_key, json.dumps(job_data))
    await queue.disconnect()

    return SolveHomeworkResponse(
        success=True,
        job_id=job_id,
        status="pending",
        points_deducted=POINTS_COST,
        new_balance=transaction.balance_after,
    )


@router.get("/solve/{job_id}/status", response_model=SolveHomeworkResponse)
async def get_solve_status(job_id: str, user: dict = Depends(get_current_user)):
    """Poll the status / result of a solve homework job."""
    queue = QueueManager(queue_name="learning_assistant_solve")
    await queue.connect()
    job = await get_job_status(queue.redis_client, job_id)
    await queue.disconnect()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("user_id") != user["uid"]:
        raise HTTPException(status_code=403, detail="Not authorised")

    return SolveHomeworkResponse(
        success=True,
        job_id=job_id,
        status=job.get("status", "unknown"),
        solution_steps=job.get("solution_steps"),
        final_answer=job.get("final_answer"),
        explanation=job.get("explanation"),
        key_formulas=job.get("key_formulas"),
        study_tips=job.get("study_tips"),
        tokens=job.get("tokens"),
        points_deducted=POINTS_COST,
        new_balance=job.get("new_balance"),
        error=job.get("error"),
    )


# ============================================================================
# Feature 2: Grade & Tips
# ============================================================================


@router.post("/grade", response_model=GradeResponse)
async def start_grade_and_tips(
    request: GradeRequest,
    user: dict = Depends(get_current_user),
):
    """
    Start AI grading + personalised study plan job.

    Accepts assignment (image or text) and student work (image or text).
    Returns job_id for status polling.

    Cost: 2 points
    """
    # Validate assignment
    if not request.assignment_image and not request.assignment_text:
        raise HTTPException(
            status_code=422,
            detail="Bạn phải cung cấp ít nhất một trong: assignment_image hoặc assignment_text",
        )
    # Validate student work
    if not request.student_work_image and not request.student_answer_text:
        raise HTTPException(
            status_code=422,
            detail="Bạn phải cung cấp ít nhất một trong: student_work_image hoặc student_answer_text",
        )

    user_id = user["uid"]
    points_service = get_points_service()

    # Check & deduct points up-front
    try:
        transaction = await points_service.deduct_points(
            user_id=user_id,
            amount=POINTS_COST,
            service="learning_assistant_grade",
            description=f"AI chấm bài – môn {request.subject}, lớp {request.grade_level}",
        )
    except Exception as exc:
        if "Không đủ điểm" in str(exc) or "insufficient" in str(exc).lower():
            balance = await points_service.get_points_balance(user_id)
            raise HTTPException(
                status_code=403,
                detail=f"Không đủ điểm. Cần: {POINTS_COST}, Còn lại: {balance['points_remaining']}",
            )
        raise HTTPException(status_code=500, detail=str(exc))

    job_id = f"grade_{uuid.uuid4().hex[:12]}"
    queue = QueueManager(queue_name="learning_assistant_grade")
    await queue.connect()

    job_data = {
        "job_id": job_id,
        "user_id": user_id,
        "assignment_image": request.assignment_image,
        "assignment_image_mime_type": request.assignment_image_mime_type or "image/jpeg",
        "assignment_text": request.assignment_text,
        "student_work_image": request.student_work_image,
        "student_work_image_mime_type": request.student_work_image_mime_type or "image/jpeg",
        "student_answer_text": request.student_answer_text,
        "subject": request.subject,
        "grade_level": request.grade_level,
        "language": request.language or "vi",
    }

    await set_job_status(
        redis_client=queue.redis_client,
        job_id=job_id,
        status="pending",
        user_id=user_id,
        created_at=datetime.utcnow().isoformat(),
    )

    await queue.redis_client.lpush(queue.task_queue_key, json.dumps(job_data))
    await queue.disconnect()

    return GradeResponse(
        success=True,
        job_id=job_id,
        status="pending",
        points_deducted=POINTS_COST,
        new_balance=transaction.balance_after,
    )


@router.get("/grade/{job_id}/status", response_model=GradeResponse)
async def get_grade_status(job_id: str, user: dict = Depends(get_current_user)):
    """Poll the status / result of a grade & tips job."""
    queue = QueueManager(queue_name="learning_assistant_grade")
    await queue.connect()
    job = await get_job_status(queue.redis_client, job_id)
    await queue.disconnect()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("user_id") != user["uid"]:
        raise HTTPException(status_code=403, detail="Not authorised")

    return GradeResponse(
        success=True,
        job_id=job_id,
        status=job.get("status", "unknown"),
        score=job.get("score"),
        score_breakdown=job.get("score_breakdown"),
        overall_feedback=job.get("overall_feedback"),
        strengths=job.get("strengths"),
        weaknesses=job.get("weaknesses"),
        correct_solution=job.get("correct_solution"),
        improvement_plan=job.get("improvement_plan"),
        study_plan=job.get("study_plan"),
        recommended_materials=job.get("recommended_materials"),
        tokens=job.get("tokens"),
        points_deducted=POINTS_COST,
        new_balance=job.get("new_balance"),
        error=job.get("error"),
    )
