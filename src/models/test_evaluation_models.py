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
    score: Optional[float] = Field(None, description="Test score (0-10), None if essay grading pending")
    score_percentage: float = Field(..., description="Test score percentage (0-100), 0 if pending")
    total_questions: int = Field(..., description="Total questions in test")
    correct_answers: Optional[int] = Field(None, description="Number of correct answers, None if essay grading pending")
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
