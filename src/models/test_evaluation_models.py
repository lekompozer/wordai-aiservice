"""
Pydantic Models for Test Result AI Evaluation
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class EvaluateTestResultRequest(BaseModel):
    """Request to evaluate test result using AI"""

    submission_id: str = Field(
        ...,
        description="Submission ID to evaluate",
        examples=["507f1f77bcf86cd799439011"],
    )
    language: str = Field(
        default="vi",
        description="Language for AI feedback (e.g., 'vi', 'en', 'fr')",
        examples=["vi"],
    )


class QuestionEvaluation(BaseModel):
    """AI evaluation for a single question"""

    question_id: str = Field(..., description="Question ID")
    question_text: str = Field(..., description="Question text")
    question_type: Optional[str] = Field(
        None, description="Question type (mcq, essay, matching, etc.)"
    )

    # MCQ/Essay fields
    user_answer: Optional[Any] = Field(
        None, description="User's answer (MCQ: string, IELTS: dict, Essay: text)"
    )
    correct_answer: Optional[Any] = Field(
        None, description="Correct answer (MCQ: string, IELTS: varies by type)"
    )
    is_correct: Optional[bool] = Field(
        None, description="Whether user answered correctly (only for MCQ)"
    )
    explanation: Optional[str] = Field(
        None, description="Question explanation or grading rubric"
    )
    options: Optional[List[Dict[str, Any]]] = Field(
        None, description="List of options for MCQ questions (key, text)"
    )

    # IELTS specific fields
    score_details: Optional[str] = Field(
        None, description="Score breakdown for IELTS questions (e.g., '2/3 correct')"
    )
    points_earned: Optional[float] = Field(
        None, description="Points earned for this question (for partial credit)"
    )
    max_points: Optional[float] = Field(
        None, description="Maximum points for this question"
    )

    ai_feedback: str = Field(
        ...,
        description="AI feedback on this specific question (why wrong, how to improve, or essay commentary)",
    )


class OverallEvaluation(BaseModel):
    """Overall AI evaluation of test performance"""

    overall_rating: Optional[float] = Field(
        None,
        description="Overall rating score (0-10) based on performance or result type",
        ge=0,
        le=10,
    )

    # Academic Fields (for Knowledge Tests)
    strengths: Optional[List[str]] = Field(
        default=None,
        description="Areas where user performed well (Academic)",
        examples=[["Good understanding of basic concepts", "Fast response time"]],
    )
    weaknesses: Optional[List[str]] = Field(
        default=None,
        description="Areas that need improvement (Academic)",
        examples=[["Struggled with advanced topics", "Careless mistakes"]],
    )
    recommendations: Optional[List[str]] = Field(
        default=None,
        description="Specific recommendations for improvement (Academic)",
        examples=[
            [
                "Review chapter 3 on algorithms",
                "Practice more coding exercises",
            ]
        ],
    )
    study_plan: Optional[str] = Field(
        None,
        description="Suggested study plan based on performance (Academic)",
    )

    # IQ Test Fields (for IQ Tests)
    iq_score: Optional[int] = Field(
        None,
        description="Estimated IQ score (e.g., 85, 100, 115, 138) for IQ tests",
        ge=50,
        le=200,
    )
    iq_category: Optional[str] = Field(
        None,
        description="IQ category (e.g., Average, Above Average, Superior, Gifted)",
    )

    # Personality Fields (for Personality/Diagnostic Tests)
    result_title: Optional[str] = Field(
        None,
        description="Title of the personality result (e.g., 'The Commander', 'Introvert')",
    )
    result_description: Optional[str] = Field(
        None,
        description="Detailed description of the personality type or result",
    )
    personality_traits: Optional[List[str]] = Field(
        None,
        description="Key personality traits identified",
    )
    advice: Optional[List[str]] = Field(
        None,
        description="Advice or insights for this personality type",
    )


class EvaluateTestResultResponse(BaseModel):
    """Response from AI test result evaluation"""

    success: bool = Field(..., description="Evaluation success status")
    submission_id: str = Field(..., description="Submission ID evaluated")
    test_title: str = Field(..., description="Test title")
    score: Optional[float] = Field(
        None, description="Test score (0-10), None if essay grading pending"
    )
    score_percentage: float = Field(
        ..., description="Test score percentage (0-100), 0 if pending"
    )
    total_questions: int = Field(..., description="Total questions in test")
    correct_answers: Optional[int] = Field(
        None, description="Number of correct answers, None if essay grading pending"
    )
    is_passed: bool = Field(..., description="Whether user passed the test")

    # AI Evaluation
    overall_evaluation: OverallEvaluation = Field(
        ..., description="Overall performance evaluation"
    )
    question_evaluations: List[QuestionEvaluation] = Field(
        ..., description="Detailed evaluation for each question"
    )

    # Evaluation metadata
    evaluation_criteria: Optional[str] = Field(
        None, description="Evaluation criteria used by AI (from test creator)"
    )
    model: str = Field(..., description="AI model used for evaluation")
    generation_time_ms: int = Field(
        ..., description="Time taken to generate evaluation (milliseconds)"
    )
    timestamp: str = Field(..., description="Evaluation timestamp (ISO 8601)")


class EvaluationHistoryItem(BaseModel):
    """Single evaluation history item"""

    evaluation_id: str = Field(..., description="Unique evaluation ID")
    submission_id: str = Field(..., description="Submission ID")
    test_id: str = Field(..., description="Test ID")
    test_title: str = Field(..., description="Test title")
    test_category: str = Field(
        ..., description="Test category (academic, iq_test, diagnostic)"
    )

    overall_evaluation: OverallEvaluation = Field(
        ..., description="Overall evaluation result"
    )
    question_evaluations: List[QuestionEvaluation] = Field(
        ..., description="Question-level evaluations"
    )

    model: str = Field(..., description="AI model used")
    generation_time_ms: int = Field(..., description="Generation time in milliseconds")
    points_cost: int = Field(..., description="Points deducted for this evaluation")
    language: str = Field(..., description="Evaluation language (vi, en, etc.)")
    created_at: str = Field(..., description="Evaluation timestamp (ISO 8601)")


class GetEvaluationHistoryResponse(BaseModel):
    """Response for evaluation history retrieval"""

    success: bool = Field(..., description="Request success status")
    evaluations: List[EvaluationHistoryItem] = Field(
        ..., description="List of evaluations"
    )
    total: int = Field(..., description="Total number of evaluations")
    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Items per page")


class GetUserEvaluationsResponse(BaseModel):
    """Response for user's all evaluations"""

    success: bool = Field(..., description="Request success status")
    evaluations: List[EvaluationHistoryItem] = Field(
        ..., description="List of evaluations"
    )
    total: int = Field(..., description="Total number of evaluations")
    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Items per page")


class TestOwnerEvaluationItem(BaseModel):
    """Evaluation item for test owner view"""

    evaluation_id: str = Field(..., description="Unique evaluation ID")
    submission_id: str = Field(..., description="Submission ID")
    user_id: str = Field(..., description="Student user ID")
    user_name: Optional[str] = Field(None, description="Student name")
    user_email: Optional[str] = Field(None, description="Student email")

    overall_evaluation: OverallEvaluation = Field(
        ..., description="Overall evaluation result"
    )
    question_evaluations: List[QuestionEvaluation] = Field(
        ..., description="Question-level evaluations"
    )

    model: str = Field(..., description="AI model used")
    generation_time_ms: int = Field(..., description="Generation time in milliseconds")
    points_cost: int = Field(..., description="Points deducted for this evaluation")
    language: str = Field(..., description="Evaluation language (vi, en, etc.)")
    created_at: str = Field(..., description="Evaluation timestamp (ISO 8601)")


class GetTestEvaluationsResponse(BaseModel):
    """Response for test owner viewing all evaluations of their test"""

    success: bool = Field(..., description="Request success status")
    test_id: str = Field(..., description="Test ID")
    test_title: str = Field(..., description="Test title")
    evaluations: List[TestOwnerEvaluationItem] = Field(
        ..., description="List of evaluations from all students"
    )
    total: int = Field(..., description="Total number of evaluations")
    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Items per page")


class EssayQuestionForGrading(BaseModel):
    """Essay question details for grading interface"""

    question_id: str = Field(..., description="Question ID")
    question_text: str = Field(..., description="Question text")
    question_type: str = Field(..., description="Question type (essay)")
    max_points: float = Field(..., description="Maximum points for this question")
    grading_rubric: Optional[str] = Field(None, description="Grading rubric/criteria")
    sample_answer: Optional[str] = Field(None, description="Sample correct answer")
    student_answer: str = Field(..., description="Student's text answer")
    media_attachments: Optional[list] = Field(
        None,
        description="Media files attached to answer (images, audio, documents)",
    )
    points_earned: Optional[float] = Field(
        None, description="Points earned (if already graded)"
    )
    feedback: Optional[str] = Field(None, description="Grading feedback (if any)")
    is_correct: Optional[bool] = Field(None, description="Whether answer is correct")


class SubmissionForGradingResponse(BaseModel):
    """Response for getting submission details for teacher grading"""

    success: bool = Field(..., description="Request success status")
    submission_id: str = Field(..., description="Submission ID")
    test_id: str = Field(..., description="Test ID")
    test_title: str = Field(..., description="Test title")

    # Student info
    user_id: str = Field(..., description="Student user ID")
    user_name: Optional[str] = Field(None, description="Student name")
    user_email: Optional[str] = Field(None, description="Student email")
    submitted_at: str = Field(..., description="Submission timestamp")

    # Score info
    mcq_score: Optional[float] = Field(None, description="MCQ score (if any)")
    mcq_correct_count: Optional[int] = Field(None, description="MCQ correct count")
    essay_graded_count: int = Field(..., description="Number of essays graded")
    essay_question_count: int = Field(..., description="Total essay questions")
    grading_status: str = Field(
        ..., description="Status: auto_graded, pending_grading, partially_graded"
    )

    # Questions for grading
    essay_questions: List[EssayQuestionForGrading] = Field(
        ..., description="Essay questions with student answers"
    )
