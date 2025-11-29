"""
Test Result AI Evaluation Routes
Uses Gemini 2.5 Flash to evaluate test performance and provide feedback
"""

from fastapi import APIRouter, Depends, HTTPException
import logging
import time
from bson import ObjectId

# Authentication
from src.middleware.auth import verify_firebase_token as require_auth

# Database
from config.config import get_mongodb

# Models
from src.models.test_evaluation_models import (
    EvaluateTestResultRequest,
    EvaluateTestResultResponse,
    OverallEvaluation,
    QuestionEvaluation,
)

# Services
from src.services.gemini_test_evaluation_service import get_gemini_evaluation_service
from src.services.points_service import get_points_service

logger = logging.getLogger("chatbot")

router = APIRouter(
    prefix="/api/v1/tests/submissions", tags=["Test Result AI Evaluation"]
)


@router.post(
    "/evaluate",
    response_model=EvaluateTestResultResponse,
    summary="Evaluate test result using AI",
)
async def evaluate_test_result(
    request: EvaluateTestResultRequest,
    user_info: dict = Depends(require_auth),
):
    """
    **AI-powered evaluation of test performance using Gemini 2.5 Flash**

    Provides detailed feedback on test results including:
    - Overall performance evaluation (strengths, weaknesses, recommendations)
    - Question-by-question analysis with AI feedback
    - Personalized study plan
    - Evaluation based on test creator's criteria (if provided)

    **Features:**
    - Uses Gemini 2.5 Flash for comprehensive analysis
    - Considers evaluation criteria from test creator
    - Provides actionable recommendations
    - Specific feedback for each question
    - Costs 1 point per evaluation

    **Authentication:** Required

    **Request Body:**
    ```json
    {
      "submission_id": "507f1f77bcf86cd799439011"
    }
    ```

    **Response:**
    - Overall evaluation with strengths, weaknesses, recommendations
    - Detailed feedback for each question
    - Personalized study plan
    - Evaluation criteria used (if available from test creator)

    **Use Cases:**
    - Student wants detailed feedback after completing a test
    - Teacher wants AI analysis of student performance
    - Automated feedback for self-study tests

    **Error Responses:**
    - `404`: Submission not found
    - `403`: User doesn't own this submission
    - `500`: AI evaluation failed
    """
    start_time = time.time()

    try:
        user_id = user_info["uid"]
        submission_id = request.submission_id

        logger.info(f"🤖 User {user_id} requesting AI evaluation for {submission_id}")

        db = get_mongodb()

        # ===== STEP 1: Get submission =====
        submission = db["test_submissions"].find_one({"_id": ObjectId(submission_id)})

        if not submission:
            raise HTTPException(status_code=404, detail="Submission not found")

        # ===== STEP 2: Verify ownership =====
        if submission.get("user_id") != user_id:
            raise HTTPException(
                status_code=403,
                detail="You can only evaluate your own submissions",
            )

        # ===== STEP 3: Check and deduct points (1 point) =====
        points_service = get_points_service()
        points_cost = 1  # 1 point for AI evaluation

        # Check sufficient points
        check_result = await points_service.check_sufficient_points(
            user_id=user_id,
            points_needed=points_cost,
            service="ai_test_evaluation",
        )

        if not check_result["has_points"]:
            logger.warning(
                f"💰 Insufficient points for test evaluation - User: {user_id}, Need: {points_cost}, Have: {check_result['points_available']}"
            )
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "INSUFFICIENT_POINTS",
                    "message": f"Không đủ điểm để đánh giá kết quả bằng AI. Cần: {points_cost}, Còn: {check_result['points_available']}",
                    "points_needed": points_cost,
                    "points_available": check_result["points_available"],
                    "service": "ai_test_evaluation",
                    "action_required": "purchase_points",
                    "purchase_url": "/pricing",
                },
            )

        logger.info(
            f"💰 Points check passed - User: {user_id}, Cost: {points_cost} point"
        )

        # ===== STEP 4: Get test details =====
        test_id = submission.get("test_id")
        test_doc = db["online_tests"].find_one({"_id": ObjectId(test_id)})

        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        # ===== STEP 5: Get evaluation criteria (if available) =====
        marketplace_config = test_doc.get("marketplace_config", {})
        evaluation_criteria = marketplace_config.get("evaluation_criteria")

        logger.info(
            f"   Test: {test_doc.get('title')} ({len(test_doc.get('questions', []))} questions)"
        )
        logger.info(
            f"   Evaluation criteria: {'Provided' if evaluation_criteria else 'Not provided'}"
        )

        # ===== STEP 6: Prepare data for AI evaluation =====
        questions = test_doc.get("questions", [])
        user_answers_list = submission.get("user_answers", [])

        # Convert user answers to dict - handle both MCQ and Essay
        user_answers_dict = {}
        for ans in user_answers_list:
            question_id = ans.get("question_id")
            question_type = ans.get("question_type", "mcq")

            if question_type == "mcq":
                # MCQ: use selected_answer_key
                user_answers_dict[question_id] = ans.get(
                    "selected_answer_key", "No answer"
                )
            elif question_type == "essay":
                # Essay: use essay_answer
                user_answers_dict[question_id] = ans.get("essay_answer", "No answer")

        score = submission.get("score", 0)
        score_percentage = submission.get("score_percentage") or 0  # Handle None for pending grading
        total_questions = submission.get("total_questions", len(questions))
        correct_answers = submission.get("correct_answers") or 0  # Handle None case
        is_passed = submission.get("is_passed", False)

        # ===== STEP 7: Call AI evaluation service =====
        evaluation_service = get_gemini_evaluation_service()

        evaluation_result = await evaluation_service.evaluate_test_result(
            test_title=test_doc.get("title", "Untitled Test"),
            test_description=test_doc.get("description", "No description"),
            questions=questions,
            user_answers=user_answers_dict,
            score_percentage=score_percentage,
            is_passed=is_passed,
            evaluation_criteria=evaluation_criteria,
            language=request.language,
            test_category=test_doc.get("test_category", "academic"),
        )

        generation_time_ms = int((time.time() - start_time) * 1000)

        logger.info(f"✅ AI evaluation completed in {generation_time_ms}ms")

        # ===== STEP 8: Deduct points after success =====
        try:
            await points_service.deduct_points(
                user_id=user_id,
                amount=points_cost,
                service="ai_test_evaluation",
                resource_id=submission_id,
                description=f"AI evaluation for test: {test_doc.get('title', 'Untitled')}",
            )
            logger.info(f"💸 Deducted {points_cost} point for AI evaluation")
        except Exception as points_error:
            logger.error(f"❌ Error deducting points: {points_error}")
            # Don't fail the request, just log the error

        # ===== STEP 9: Build response =====
        # Map question evaluations to include full question data
        question_evaluations = []
        ai_feedbacks = {
            qe["question_id"]: qe["ai_feedback"]
            for qe in evaluation_result.get("question_evaluations", [])
        }

        for q in questions:
            question_id = q["question_id"]
            q_type = q.get("question_type", "mcq")
            user_answer = user_answers_dict.get(question_id)

            if q_type == "mcq":
                correct_answer = q.get("correct_answer_key")
                is_correct = user_answer == correct_answer

                question_evaluations.append(
                    QuestionEvaluation(
                        question_id=question_id,
                        question_text=q["question_text"],
                        user_answer=user_answer,
                        correct_answer=correct_answer,
                        is_correct=is_correct,
                        explanation=q.get("explanation"),
                        ai_feedback=ai_feedbacks.get(
                            question_id, "No feedback available for this question"
                        ),
                    )
                )
            elif q_type == "essay":
                # For essay questions, we don't have correct_answer or is_correct
                question_evaluations.append(
                    QuestionEvaluation(
                        question_id=question_id,
                        question_text=q["question_text"],
                        user_answer=user_answer,
                        correct_answer=None,  # Essays don't have a single correct answer
                        is_correct=None,  # Not applicable for essays
                        explanation=q.get("grading_rubric"),
                        ai_feedback=ai_feedbacks.get(
                            question_id, "No feedback available for this question"
                        ),
                    )
                )

        # Build overall evaluation
        overall_eval_data = evaluation_result.get("overall_evaluation", {})
        overall_evaluation = OverallEvaluation(
            strengths=overall_eval_data.get("strengths", []),
            weaknesses=overall_eval_data.get("weaknesses", []),
            recommendations=overall_eval_data.get("recommendations", []),
            study_plan=overall_eval_data.get("study_plan"),
        )

        return EvaluateTestResultResponse(
            success=True,
            submission_id=submission_id,
            test_title=test_doc.get("title", "Untitled Test"),
            score=score,
            score_percentage=score_percentage,
            total_questions=total_questions,
            correct_answers=correct_answers,
            is_passed=is_passed,
            overall_evaluation=overall_evaluation,
            question_evaluations=question_evaluations,
            evaluation_criteria=evaluation_criteria,
            model=evaluation_result.get("model", "gemini-2.5-flash"),
            generation_time_ms=generation_time_ms,
            timestamp=evaluation_result.get("timestamp", ""),
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"❌ AI evaluation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "EVALUATION_FAILED",
                "message": "Không thể đánh giá kết quả bằng AI. Vui lòng thử lại.",
                "technical_details": str(e),
            },
        )
