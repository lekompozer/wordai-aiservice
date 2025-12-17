"""
Test Result AI Evaluation Routes
Uses Gemini 2.5 Flash to evaluate test performance and provide feedback
"""

from fastapi import APIRouter, Depends, HTTPException
import logging
import time
from datetime import datetime
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
    GetEvaluationHistoryResponse,
    EvaluationHistoryItem,
    GetUserEvaluationsResponse,
    TestOwnerEvaluationItem,
    GetTestEvaluationsResponse,
    SubmissionForGradingResponse,
    EssayQuestionForGrading,
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

        # Convert user answers to dict - handle ALL question types
        # Also extract media attachments for essay questions
        user_answers_dict = {}
        media_attachments_by_question = {}  # {question_id: [media_files]}

        for ans in user_answers_list:
            question_id = ans.get("question_id")
            question_type = ans.get("question_type", "mcq")

            if question_type == "mcq" or question_type == "mcq_multiple":
                # MCQ: use selected_answer_keys (array) or legacy selected_answer_key
                selected_answers = ans.get("selected_answer_keys", [])
                if not selected_answers and "selected_answer_key" in ans:
                    selected_answers = [ans.get("selected_answer_key")]
                user_answers_dict[question_id] = (
                    selected_answers[0]
                    if len(selected_answers) == 1
                    else selected_answers
                )

            elif question_type == "essay":
                # Essay: use essay_answer and extract media attachments
                user_answers_dict[question_id] = ans.get("essay_answer", "No answer")

                # Extract media attachments if present
                media_files = ans.get("media_attachments", [])
                if media_files:
                    media_attachments_by_question[question_id] = media_files
                    logger.info(
                        f"   📎 Question {question_id}: {len(media_files)} media file(s)"
                    )

            elif question_type == "matching":
                # Matching: use matches dict {left_key: right_key}
                user_answers_dict[question_id] = ans.get("matches", {})

            elif question_type == "completion":
                # Completion: use answers dict {blank_key: answer}
                user_answers_dict[question_id] = ans.get("answers", {})

            elif question_type == "sentence_completion":
                # Sentence completion: use answers dict {sentence_key: answer}
                user_answers_dict[question_id] = ans.get("answers", {})

            elif question_type == "short_answer":
                # Short answer: use answers dict {question_key: answer}
                user_answers_dict[question_id] = ans.get("answers", {})

            elif question_type == "true_false_multiple":
                # True/False Multiple: use user_answer dict {statement_key: true/false}
                user_answers_dict[question_id] = ans.get("user_answer", {})

        # Handle None values for essay tests pending grading
        score = submission.get("score")  # Can be None for essay tests
        score_percentage = submission.get("score_percentage") or 0  # 0 if None
        total_questions = submission.get("total_questions", len(questions))
        correct_answers = submission.get(
            "correct_answers"
        )  # Can be None for essay tests
        is_passed = submission.get("is_passed", False)

        # ===== STEP 7: Call AI evaluation service =====
        evaluation_service = get_gemini_evaluation_service()

        # Log media attachments summary
        if media_attachments_by_question:
            total_files = sum(
                len(files) for files in media_attachments_by_question.values()
            )
            logger.info(
                f"   📎 Total media attachments: {total_files} file(s) across {len(media_attachments_by_question)} question(s)"
            )

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
            media_attachments=media_attachments_by_question,  # NEW: Pass media files
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

        # ===== STEP 8.5: Save evaluation to history =====
        try:
            evaluations_collection = db["ai_evaluations"]
            evaluation_doc = {
                "submission_id": submission_id,
                "test_id": test_id,
                "user_id": user_id,
                "test_title": test_doc.get("title", "Untitled Test"),
                "test_category": test_doc.get("test_category", "academic"),
                "overall_evaluation": evaluation_result.get("overall_evaluation", {}),
                "question_evaluations": evaluation_result.get(
                    "question_evaluations", []
                ),
                "model": evaluation_result.get("model", "gemini-2.5-flash"),
                "generation_time_ms": generation_time_ms,
                "points_cost": points_cost,
                "language": request.language,
                "created_at": datetime.now(),
            }

            result = evaluations_collection.insert_one(evaluation_doc)
            logger.info(f"💾 Saved evaluation to history: {result.inserted_id}")
        except Exception as save_error:
            logger.error(f"❌ Failed to save evaluation to history: {save_error}")
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

            if q_type == "mcq" or q_type == "mcq_multiple":
                # Use correct_answers as primary field, fallback to old fields for backward compatibility
                correct_answer = (
                    q.get("correct_answers")
                    or q.get("correct_answer_keys")
                    or [q.get("correct_answer_key")]
                )
                is_correct = (
                    user_answer in correct_answer
                    if isinstance(user_answer, str)
                    else False
                )

                # Extract options
                options = []
                for opt in q.get("options", []):
                    options.append(
                        {
                            "key": opt.get("option_key") or opt.get("key"),
                            "text": opt.get("option_text") or opt.get("text"),
                        }
                    )

                question_evaluations.append(
                    QuestionEvaluation(
                        question_id=question_id,
                        question_type=q_type,
                        question_text=q["question_text"],
                        user_answer=user_answer,
                        correct_answer=(
                            correct_answer[0]
                            if len(correct_answer) == 1
                            else correct_answer
                        ),
                        is_correct=is_correct,
                        explanation=q.get("explanation"),
                        options=options,
                        max_points=q.get("max_points", 1),
                        ai_feedback=ai_feedbacks.get(
                            question_id, "No feedback available"
                        ),
                    )
                )

            elif q_type == "essay":
                question_evaluations.append(
                    QuestionEvaluation(
                        question_id=question_id,
                        question_type=q_type,
                        question_text=q["question_text"],
                        user_answer=user_answer,
                        correct_answer=None,
                        is_correct=None,
                        explanation=q.get("grading_rubric"),
                        max_points=q.get("max_points", 1),
                        ai_feedback=ai_feedbacks.get(
                            question_id, "No feedback available"
                        ),
                    )
                )

            # IELTS question types
            elif q_type in [
                "matching",
                "completion",
                "sentence_completion",
                "short_answer",
                "true_false_multiple",
            ]:
                # Format correct answer based on type
                if q_type == "matching":
                    # Use correct_answers as primary, fallback to correct_matches
                    matches = q.get("correct_answers") or q.get("correct_matches", [])
                    correct_answer = {m["left_key"]: m["right_key"] for m in matches}
                elif q_type == "completion":
                    # Handle both object format (correct) and string format (legacy)
                    correct_answers_list = q.get("correct_answers", [])
                    correct_answer = {}
                    for ca in correct_answers_list:
                        if isinstance(ca, dict):
                            # Correct format: object with blank_key and answers
                            correct_answer[ca["blank_key"]] = ca["answers"]
                        # Legacy format: ca is a string, skip it (can't map without blank_key)
                elif q_type == "sentence_completion":
                    correct_answer = {
                        s["key"]: s["correct_answers"] for s in q.get("sentences", [])
                    }
                elif q_type == "short_answer":
                    if "questions" in q:
                        correct_answer = {
                            sq["key"]: sq["correct_answers"]
                            for sq in q.get("questions", [])
                        }
                    else:
                        # Use correct_answers as primary, fallback to correct_answer_keys
                        correct_answer = q.get("correct_answers") or q.get(
                            "correct_answer_keys", []
                        )
                elif q_type == "true_false_multiple":
                    # True/False Multiple: format as {statement_key: correct_value}
                    statements = q.get("statements", [])
                    correct_answer = {
                        stmt["key"]: stmt["correct_value"] for stmt in statements
                    }

                question_evaluations.append(
                    QuestionEvaluation(
                        question_id=question_id,
                        question_type=q_type,
                        question_text=q["question_text"],
                        user_answer=user_answer,
                        correct_answer=correct_answer,
                        is_correct=None,  # Complex scoring, not simple true/false
                        explanation=q.get("explanation"),
                        max_points=q.get("max_points", 1),
                        ai_feedback=ai_feedbacks.get(
                            question_id, "No feedback available"
                        ),
                    )
                )

        # Build overall evaluation
        overall_eval_data = evaluation_result.get("overall_evaluation", {})
        overall_evaluation = OverallEvaluation(
            overall_rating=overall_eval_data.get("overall_rating"),
            strengths=overall_eval_data.get("strengths", []),
            weaknesses=overall_eval_data.get("weaknesses", []),
            recommendations=overall_eval_data.get("recommendations", []),
            study_plan=overall_eval_data.get("study_plan"),
            # IQ test fields
            iq_score=overall_eval_data.get("iq_score"),
            iq_category=overall_eval_data.get("iq_category"),
            # Diagnostic fields
            result_title=overall_eval_data.get("result_title"),
            result_description=overall_eval_data.get("result_description"),
            personality_traits=overall_eval_data.get("personality_traits"),
            advice=overall_eval_data.get("advice"),
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


@router.get(
    "/{submission_id}/evaluations",
    response_model=GetEvaluationHistoryResponse,
    summary="Get AI evaluation history for a submission",
)
async def get_submission_evaluations(
    submission_id: str,
    page: int = 1,
    limit: int = 10,
    user_info: dict = Depends(require_auth),
):
    """
    **Retrieve all AI evaluations for a specific submission**

    Returns list of all AI evaluations performed on this submission,
    sorted by most recent first. Useful when a student re-evaluates
    the same test multiple times.

    **Authentication:** Required

    **Path Parameters:**
    - `submission_id`: The submission ID

    **Query Parameters:**
    - `page`: Page number (default: 1)
    - `limit`: Items per page (default: 10, max: 50)

    **Response:**
    ```json
    {
      "success": true,
      "evaluations": [
        {
          "evaluation_id": "...",
          "submission_id": "...",
          "test_id": "...",
          "test_title": "Advanced JavaScript Test",
          "overall_evaluation": { ... },
          "question_evaluations": [ ... ],
          "model": "gemini-2.5-flash",
          "generation_time_ms": 48234,
          "points_cost": 1,
          "language": "vi",
          "created_at": "2024-01-15T10:30:00Z"
        }
      ],
      "total": 2,
      "page": 1,
      "limit": 10
    }
    ```

    **Error Responses:**
    - `404`: Submission not found
    - `403`: User doesn't own this submission
    """
    try:
        user_id = user_info["uid"]
        db = get_mongodb()

        # Validate submission ownership
        submission = db["test_submissions"].find_one({"_id": ObjectId(submission_id)})
        if not submission:
            raise HTTPException(status_code=404, detail="Submission not found")

        if submission.get("user_id") != user_id:
            raise HTTPException(
                status_code=403, detail="You don't have access to this submission"
            )

        # Paginate evaluations
        limit = min(limit, 50)  # Max 50 items per page
        skip = (page - 1) * limit

        evaluations_collection = db["ai_evaluations"]

        # Get total count
        total = evaluations_collection.count_documents({"submission_id": submission_id})

        # Get evaluations
        evaluations_cursor = (
            evaluations_collection.find({"submission_id": submission_id})
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )

        evaluations = []
        for eval_doc in evaluations_cursor:
            # Build question evaluations
            question_evals = []
            for qe in eval_doc.get("question_evaluations", []):
                question_evals.append(
                    QuestionEvaluation(
                        question_id=qe.get("question_id"),
                        question_text=qe.get("question_text", ""),
                        question_type=qe.get("question_type"),
                        user_answer=qe.get("user_answer"),
                        correct_answer=qe.get("correct_answer"),
                        is_correct=qe.get("is_correct"),
                        explanation=qe.get("explanation"),
                        options=qe.get("options"),
                        score_details=qe.get("score_details"),
                        points_earned=qe.get("points_earned"),
                        max_points=qe.get("max_points"),
                        ai_feedback=qe.get("ai_feedback", ""),
                    )
                )

            # Build overall evaluation
            overall_eval = eval_doc.get("overall_evaluation", {})
            overall_evaluation = OverallEvaluation(
                overall_rating=overall_eval.get("overall_rating"),
                strengths=overall_eval.get("strengths"),
                weaknesses=overall_eval.get("weaknesses"),
                recommendations=overall_eval.get("recommendations"),
                study_plan=overall_eval.get("study_plan"),
                iq_score=overall_eval.get("iq_score"),
                iq_category=overall_eval.get("iq_category"),
                result_title=overall_eval.get("result_title"),
                result_description=overall_eval.get("result_description"),
                personality_traits=overall_eval.get("personality_traits"),
                advice=overall_eval.get("advice"),
            )

            evaluations.append(
                EvaluationHistoryItem(
                    evaluation_id=str(eval_doc["_id"]),
                    submission_id=eval_doc.get("submission_id"),
                    test_id=eval_doc.get("test_id"),
                    test_title=eval_doc.get("test_title"),
                    test_category=eval_doc.get("test_category", "academic"),
                    overall_evaluation=overall_evaluation,
                    question_evaluations=question_evals,
                    model=eval_doc.get("model", "gemini-2.5-flash"),
                    generation_time_ms=eval_doc.get("generation_time_ms", 0),
                    points_cost=eval_doc.get("points_cost", 1),
                    language=eval_doc.get("language", "vi"),
                    created_at=(
                        eval_doc.get("created_at").isoformat()
                        if eval_doc.get("created_at")
                        else ""
                    ),
                )
            )

        return GetEvaluationHistoryResponse(
            success=True,
            evaluations=evaluations,
            total=total,
            page=page,
            limit=limit,
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"❌ Failed to get evaluation history: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "GET_HISTORY_FAILED",
                "message": "Không thể lấy lịch sử đánh giá. Vui lòng thử lại.",
                "technical_details": str(e),
            },
        )


@router.get(
    "/evaluations/me",
    response_model=GetUserEvaluationsResponse,
    summary="Get all AI evaluations for current user",
)
async def get_user_evaluations(
    test_id: str = None,
    page: int = 1,
    limit: int = 20,
    user_info: dict = Depends(require_auth),
):
    """
    **Retrieve all AI evaluations for the current user**

    Returns list of all AI evaluations performed by this user across all tests,
    sorted by most recent first. Optionally filter by specific test.

    **Authentication:** Required

    **Query Parameters:**
    - `test_id`: Filter by specific test (optional)
    - `page`: Page number (default: 1)
    - `limit`: Items per page (default: 20, max: 50)

    **Response:**
    ```json
    {
      "success": true,
      "evaluations": [
        {
          "evaluation_id": "...",
          "submission_id": "...",
          "test_id": "...",
          "test_title": "Advanced JavaScript Test",
          "test_category": "academic",
          "overall_evaluation": { ... },
          "question_evaluations": [ ... ],
          "model": "gemini-2.5-flash",
          "generation_time_ms": 48234,
          "points_cost": 1,
          "language": "vi",
          "created_at": "2024-01-15T10:30:00Z"
        }
      ],
      "total": 15,
      "page": 1,
      "limit": 20
    }
    ```

    **Use Cases:**
    - Student reviewing all their AI evaluation history
    - Tracking improvement over time
    - Finding specific evaluation from past
    """
    try:
        user_id = user_info["uid"]
        db = get_mongodb()

        # Build query filter
        query_filter = {"user_id": user_id}
        if test_id:
            query_filter["test_id"] = test_id

        # Paginate evaluations
        limit = min(limit, 50)  # Max 50 items per page
        skip = (page - 1) * limit

        evaluations_collection = db["ai_evaluations"]

        # Get total count
        total = evaluations_collection.count_documents(query_filter)

        # Get evaluations
        evaluations_cursor = (
            evaluations_collection.find(query_filter)
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )

        evaluations = []
        for eval_doc in evaluations_cursor:
            # Build question evaluations
            question_evals = []
            for qe in eval_doc.get("question_evaluations", []):
                question_evals.append(
                    QuestionEvaluation(
                        question_id=qe.get("question_id"),
                        question_text=qe.get("question_text", ""),
                        question_type=qe.get("question_type"),
                        user_answer=qe.get("user_answer"),
                        correct_answer=qe.get("correct_answer"),
                        is_correct=qe.get("is_correct"),
                        explanation=qe.get("explanation"),
                        options=qe.get("options"),
                        score_details=qe.get("score_details"),
                        points_earned=qe.get("points_earned"),
                        max_points=qe.get("max_points"),
                        ai_feedback=qe.get("ai_feedback", ""),
                    )
                )

            # Build overall evaluation
            overall_eval = eval_doc.get("overall_evaluation", {})
            overall_evaluation = OverallEvaluation(
                overall_rating=overall_eval.get("overall_rating"),
                strengths=overall_eval.get("strengths"),
                weaknesses=overall_eval.get("weaknesses"),
                recommendations=overall_eval.get("recommendations"),
                study_plan=overall_eval.get("study_plan"),
                iq_score=overall_eval.get("iq_score"),
                iq_category=overall_eval.get("iq_category"),
                result_title=overall_eval.get("result_title"),
                result_description=overall_eval.get("result_description"),
                personality_traits=overall_eval.get("personality_traits"),
                advice=overall_eval.get("advice"),
            )

            evaluations.append(
                EvaluationHistoryItem(
                    evaluation_id=str(eval_doc["_id"]),
                    submission_id=eval_doc.get("submission_id"),
                    test_id=eval_doc.get("test_id"),
                    test_title=eval_doc.get("test_title"),
                    test_category=eval_doc.get("test_category", "academic"),
                    overall_evaluation=overall_evaluation,
                    question_evaluations=question_evals,
                    model=eval_doc.get("model", "gemini-2.5-flash"),
                    generation_time_ms=eval_doc.get("generation_time_ms", 0),
                    points_cost=eval_doc.get("points_cost", 1),
                    language=eval_doc.get("language", "vi"),
                    created_at=(
                        eval_doc.get("created_at").isoformat()
                        if eval_doc.get("created_at")
                        else ""
                    ),
                )
            )

        return GetUserEvaluationsResponse(
            success=True,
            evaluations=evaluations,
            total=total,
            page=page,
            limit=limit,
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"❌ Failed to get user evaluations: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "GET_USER_EVALUATIONS_FAILED",
                "message": "Không thể lấy lịch sử đánh giá. Vui lòng thử lại.",
                "technical_details": str(e),
            },
        )


@router.get(
    "/tests/{test_id}/evaluations",
    response_model=GetTestEvaluationsResponse,
    summary="Get all AI evaluations for a test (Test Owner)",
)
async def get_test_evaluations(
    test_id: str,
    page: int = 1,
    limit: int = 20,
    user_info: dict = Depends(require_auth),
):
    """
    **Retrieve all AI evaluations for a test (Test Owner Only)**

    Returns list of all AI evaluations performed by students who took this test.
    Only the test owner can access this endpoint.

    **Authentication:** Required (must be test owner)

    **Path Parameters:**
    - `test_id`: The test ID

    **Query Parameters:**
    - `page`: Page number (default: 1)
    - `limit`: Items per page (default: 20, max: 50)

    **Response:**
    ```json
    {
      "success": true,
      "test_id": "...",
      "test_title": "Advanced JavaScript Test",
      "evaluations": [
        {
          "evaluation_id": "...",
          "submission_id": "...",
          "user_id": "student_123",
          "user_name": "John Doe",
          "user_email": "john@example.com",
          "overall_evaluation": { ... },
          "question_evaluations": [ ... ],
          "model": "gemini-2.5-flash",
          "generation_time_ms": 48234,
          "points_cost": 1,
          "language": "vi",
          "created_at": "2024-01-15T10:30:00Z"
        }
      ],
      "total": 25,
      "page": 1,
      "limit": 20
    }
    ```

    **Use Cases:**
    - Teacher reviewing how students performed (AI perspective)
    - Analyzing common mistakes across all students
    - Tracking which students requested AI evaluation
    - Comparing AI evaluations with manual grading

    **Error Responses:**
    - `404`: Test not found
    - `403`: User is not the test owner
    """
    try:
        user_id = user_info["uid"]
        db = get_mongodb()

        # Verify test exists and user is owner
        test_doc = db["online_tests"].find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        if test_doc.get("creator_id") != user_id:
            raise HTTPException(
                status_code=403, detail="Only test owner can view all evaluations"
            )

        # Paginate evaluations
        limit = min(limit, 50)  # Max 50 items per page
        skip = (page - 1) * limit

        evaluations_collection = db["ai_evaluations"]

        # Get total count
        total = evaluations_collection.count_documents({"test_id": test_id})

        # Get evaluations
        evaluations_cursor = (
            evaluations_collection.find({"test_id": test_id})
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )

        evaluations = []
        users_collection = db["users"]

        for eval_doc in evaluations_cursor:
            # Get student info
            student_user_id = eval_doc.get("user_id")
            student = users_collection.find_one({"firebase_uid": student_user_id})
            student_name = None
            student_email = None
            if student:
                student_name = (
                    student.get("display_name")
                    or student.get("name")
                    or student.get("email")
                )
                student_email = student.get("email")

            # Build question evaluations
            question_evals = []
            for qe in eval_doc.get("question_evaluations", []):
                question_evals.append(
                    QuestionEvaluation(
                        question_id=qe.get("question_id"),
                        question_text=qe.get("question_text", ""),
                        question_type=qe.get("question_type"),
                        user_answer=qe.get("user_answer"),
                        correct_answer=qe.get("correct_answer"),
                        is_correct=qe.get("is_correct"),
                        explanation=qe.get("explanation"),
                        options=qe.get("options"),
                        score_details=qe.get("score_details"),
                        points_earned=qe.get("points_earned"),
                        max_points=qe.get("max_points"),
                        ai_feedback=qe.get("ai_feedback", ""),
                    )
                )

            # Build overall evaluation
            overall_eval = eval_doc.get("overall_evaluation", {})
            overall_evaluation = OverallEvaluation(
                overall_rating=overall_eval.get("overall_rating"),
                strengths=overall_eval.get("strengths"),
                weaknesses=overall_eval.get("weaknesses"),
                recommendations=overall_eval.get("recommendations"),
                study_plan=overall_eval.get("study_plan"),
                iq_score=overall_eval.get("iq_score"),
                iq_category=overall_eval.get("iq_category"),
                result_title=overall_eval.get("result_title"),
                result_description=overall_eval.get("result_description"),
                personality_traits=overall_eval.get("personality_traits"),
                advice=overall_eval.get("advice"),
            )

            evaluations.append(
                TestOwnerEvaluationItem(
                    evaluation_id=str(eval_doc["_id"]),
                    submission_id=eval_doc.get("submission_id"),
                    user_id=student_user_id,
                    user_name=student_name,
                    user_email=student_email,
                    overall_evaluation=overall_evaluation,
                    question_evaluations=question_evals,
                    model=eval_doc.get("model", "gemini-2.5-flash"),
                    generation_time_ms=eval_doc.get("generation_time_ms", 0),
                    points_cost=eval_doc.get("points_cost", 1),
                    language=eval_doc.get("language", "vi"),
                    created_at=(
                        eval_doc.get("created_at").isoformat()
                        if eval_doc.get("created_at")
                        else ""
                    ),
                )
            )

        return GetTestEvaluationsResponse(
            success=True,
            test_id=test_id,
            test_title=test_doc.get("title", "Untitled Test"),
            evaluations=evaluations,
            total=total,
            page=page,
            limit=limit,
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"❌ Failed to get test evaluations: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "GET_TEST_EVALUATIONS_FAILED",
                "message": "Không thể lấy danh sách đánh giá. Vui lòng thử lại.",
                "technical_details": str(e),
            },
        )


@router.get(
    "/{submission_id}/grading-details",
    response_model=SubmissionForGradingResponse,
    summary="Get submission details for teacher grading",
)
async def get_submission_for_grading(
    submission_id: str,
    user_info: dict = Depends(require_auth),
):
    """
    **Get submission details for teacher grading interface**

    Returns complete submission data including essay questions with grading rubrics,
    sample answers, and student responses. Only test owner can access.

    **Authentication:** Required (must be test owner)

    **Path Parameters:**
    - `submission_id`: The submission ID

    **Response:**
    ```json
    {
      "success": true,
      "submission_id": "...",
      "test_id": "...",
      "test_title": "Advanced JavaScript Test",
      "user_id": "student_123",
      "user_name": "John Doe",
      "user_email": "john@example.com",
      "submitted_at": "2024-01-15T10:30:00Z",
      "mcq_score": 7.5,
      "mcq_correct_count": 15,
      "essay_graded_count": 2,
      "essay_question_count": 4,
      "grading_status": "partially_graded",
      "essay_questions": [
        {
          "question_id": "q1_essay",
          "question_text": "Explain closures in JavaScript",
          "question_type": "essay",
          "max_points": 10,
          "grading_rubric": "Must explain scope, function, and variable access",
          "sample_answer": "A closure is...",
          "student_answer": "Closures are functions that...",
          "points_earned": 8.5,
          "feedback": "Good explanation, missing edge cases",
          "is_correct": true
        }
      ]
    }
    ```

    **Use Cases:**
    - Teacher opens grading interface to grade essays
    - View student answers alongside grading criteria
    - See MCQ performance for context
    - Check grading progress (which essays are done)

    **Error Responses:**
    - `404`: Submission or test not found
    - `403`: User is not the test owner
    """
    try:
        user_id = user_info["uid"]
        db = get_mongodb()

        # Get submission
        submission = db["test_submissions"].find_one({"_id": ObjectId(submission_id)})
        if not submission:
            raise HTTPException(status_code=404, detail="Submission not found")

        # Get test and verify owner
        test_doc = db["online_tests"].find_one({"_id": ObjectId(submission["test_id"])})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        if test_doc.get("creator_id") != user_id:
            raise HTTPException(
                status_code=403, detail="Only test owner can view submission details"
            )

        # Get student info
        student = db["users"].find_one({"firebase_uid": submission["user_id"]})
        student_name = None
        student_email = None
        if student:
            student_name = (
                student.get("display_name")
                or student.get("name")
                or student.get("email")
            )
            student_email = student.get("email")

        # Build essay questions for grading
        essay_questions = []
        user_answers_map = {}

        # Map user answers
        for ans in submission.get("user_answers", []):
            q_id = ans.get("question_id")
            user_answers_map[q_id] = ans

        # Get existing grades
        essay_grades_map = {}
        if submission.get("essay_grades"):
            for grade in submission.get("essay_grades", []):
                essay_grades_map[grade["question_id"]] = grade

        # Build essay questions list
        for q in test_doc.get("questions", []):
            if q.get("question_type") == "essay":
                question_id = q["question_id"]
                user_ans = user_answers_map.get(question_id, {})
                existing_grade = essay_grades_map.get(question_id)

                essay_questions.append(
                    EssayQuestionForGrading(
                        question_id=question_id,
                        question_text=q.get("question_text", ""),
                        question_type="essay",
                        max_points=q.get("max_points", 1),
                        grading_rubric=q.get("grading_rubric"),
                        sample_answer=q.get("sample_answer"),
                        student_answer=user_ans.get("essay_answer", ""),
                        points_earned=(
                            existing_grade.get("points_awarded")
                            if existing_grade
                            else None
                        ),
                        feedback=(
                            existing_grade.get("feedback") if existing_grade else None
                        ),
                        is_correct=(
                            existing_grade.get("is_correct") if existing_grade else None
                        ),
                    )
                )

        # Count graded essays
        essay_graded_count = len(essay_grades_map)
        essay_question_count = len(essay_questions)

        return SubmissionForGradingResponse(
            success=True,
            submission_id=submission_id,
            test_id=submission["test_id"],
            test_title=test_doc.get("title", "Untitled Test"),
            user_id=submission["user_id"],
            user_name=student_name,
            user_email=student_email,
            submitted_at=(
                submission.get("submitted_at").isoformat()
                if submission.get("submitted_at")
                else ""
            ),
            mcq_score=submission.get("mcq_score"),
            mcq_correct_count=submission.get("mcq_correct_count"),
            essay_graded_count=essay_graded_count,
            essay_question_count=essay_question_count,
            grading_status=submission.get("grading_status", "pending_grading"),
            essay_questions=essay_questions,
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"❌ Failed to get submission for grading: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "GET_SUBMISSION_GRADING_FAILED",
                "message": "Không thể lấy thông tin submission. Vui lòng thử lại.",
                "technical_details": str(e),
            },
        )
