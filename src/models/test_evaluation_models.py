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
    user_answer: Optional[str] = Field(
        None, description="User's answer (MCQ: A/B/C/D, Essay: text)"
    )
    correct_answer: Optional[str] = Field(
        None, description="Correct answer (only for MCQ)"
    )
    is_correct: Optional[bool] = Field(
        None, description="Whether user answered correctly (only for MCQ)"
    )
    explanation: Optional[str] = Field(
        None, description="Question explanation or grading rubric"
    )
    ai_feedback: str = Field(
        ...,
        description="AI feedback on this specific question (why wrong, how to improve, or essay commentary)",
    )


class OverallEvaluation(BaseModel):
    """Overall AI evaluation of test performance"""

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
    score: float = Field(..., description="Test score (0-10)")
    score_percentage: float = Field(..., description="Test score percentage (0-100)")
    total_questions: int = Field(..., description="Total questions in test")
    correct_answers: int = Field(..., description="Number of correct answers")
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
