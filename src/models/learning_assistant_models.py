"""
AI Learning Assistant Models
Pydantic models for Solve Homework and Grade & Tips features
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ============================================================================
# Shared types
# ============================================================================

SUBJECTS = [
    "math",
    "physics",
    "chemistry",
    "biology",
    "literature",
    "history",
    "english",
    "computer_science",
    "other",
]

GRADE_LEVELS = [
    "primary",  # Tiểu học
    "middle_school",  # Trung học cơ sở
    "high_school",  # Trung học phổ thông
    "university",  # Đại học / Cao đẳng
    "other",
]


# ============================================================================
# Feature 1: Solve Homework
# ============================================================================


class SolveHomeworkRequest(BaseModel):
    """Request to solve a homework question.

    The question can be provided as:
    - ``question_text``: typed text  (required if no image)
    - ``question_image``: base64-encoded image of the question (required if no text)

    At least one of ``question_text`` or ``question_image`` must be provided.
    Both can be provided together (e.g. typed context + photo).
    """

    # Question source — at least one required
    question_text: Optional[str] = Field(
        None,
        max_length=5000,
        description="Typed question text",
    )
    question_image: Optional[str] = Field(
        None,
        description="Base64-encoded image of the question (JPEG/PNG, max ~4MB decoded)",
    )
    image_mime_type: Optional[str] = Field(
        "image/jpeg",
        description="MIME type of question image: image/jpeg or image/png",
    )

    # Classification
    subject: str = Field(
        "other",
        description=f"Subject: {', '.join(SUBJECTS)}",
    )
    grade_level: str = Field(
        "other",
        description=f"Grade level: {', '.join(GRADE_LEVELS)}",
    )

    # Optional: language hint for response
    language: Optional[str] = Field(
        "vi",
        description="Response language hint: vi (Vietnamese) or en (English)",
    )

    class Config:
        json_schema_extra = {
            "examples": {
                "text_only": {
                    "summary": "Text question",
                    "value": {
                        "question_text": "Tính đạo hàm của hàm số f(x) = x^3 - 2x + 1",
                        "subject": "math",
                        "grade_level": "high_school",
                        "language": "vi",
                    },
                },
                "image_only": {
                    "summary": "Photo of question",
                    "value": {
                        "question_image": "<base64_encoded_jpeg>",
                        "image_mime_type": "image/jpeg",
                        "subject": "physics",
                        "grade_level": "high_school",
                        "language": "vi",
                    },
                },
                "image_and_text": {
                    "summary": "Photo + additional context",
                    "value": {
                        "question_image": "<base64_encoded_jpeg>",
                        "question_text": "Tìm x trong phương trình này",
                        "subject": "math",
                        "grade_level": "middle_school",
                        "language": "vi",
                    },
                },
            }
        }


class SolveHomeworkResponse(BaseModel):
    """Response from solve homework job"""

    success: bool
    job_id: str
    status: str  # pending / processing / completed / failed

    # Available when completed
    solution_steps: Optional[List[str]] = Field(
        None, description="Step-by-step solution walkthrough"
    )
    final_answer: Optional[str] = Field(
        None, description="The final answer / conclusion"
    )
    explanation: Optional[str] = Field(
        None, description="Why this approach is correct — conceptual explanation"
    )
    key_formulas: Optional[List[str]] = Field(
        None, description="Key formulas or rules used"
    )
    study_tips: Optional[List[str]] = Field(
        None, description="Tips to remember or avoid common mistakes"
    )

    # Token usage
    tokens: Optional[Dict[str, int]] = None

    # Points
    points_deducted: int = 2
    new_balance: Optional[int] = None

    # Error info
    error: Optional[str] = None
    message: Optional[str] = None


# ============================================================================
# Feature 2: Grade & Tips
# ============================================================================


class GradeRequest(BaseModel):
    """Request to grade student's work and provide improvement tips.

    Assignment (the question/test):
    - ``assignment_image``: photo of question/test paper (OR)
    - ``assignment_text``: typed question text

    Student's work (their answer):
    - ``student_work_image``: photo of student's answer sheet (OR)
    - ``student_answer_text``: typed student answer

    At least one assignment source AND one student work source are required.
    """

    # Assignment source — at least one required
    assignment_image: Optional[str] = Field(
        None,
        description="Base64-encoded image of the assignment/question paper",
    )
    assignment_image_mime_type: Optional[str] = Field(
        "image/jpeg",
        description="MIME type: image/jpeg or image/png",
    )
    assignment_text: Optional[str] = Field(
        None,
        max_length=5000,
        description="Typed assignment/question text",
    )

    # Student work source — at least one required
    student_work_image: Optional[str] = Field(
        None,
        description="Base64-encoded image of student's handwritten answer",
    )
    student_work_image_mime_type: Optional[str] = Field(
        "image/jpeg",
        description="MIME type: image/jpeg or image/png",
    )
    student_answer_text: Optional[str] = Field(
        None,
        max_length=10000,
        description="Typed student answer text",
    )

    # Classification
    subject: str = Field(
        "other",
        description=f"Subject: {', '.join(SUBJECTS)}",
    )
    grade_level: str = Field(
        "other",
        description=f"Grade level: {', '.join(GRADE_LEVELS)}",
    )

    # Optional
    language: Optional[str] = Field(
        "vi",
        description="Response language: vi or en",
    )

    class Config:
        json_schema_extra = {
            "examples": {
                "two_photos": {
                    "summary": "Photos of assignment + student work",
                    "value": {
                        "assignment_image": "<base64_jpeg_of_test_paper>",
                        "student_work_image": "<base64_jpeg_of_student_answer>",
                        "subject": "math",
                        "grade_level": "high_school",
                        "language": "vi",
                    },
                },
                "text_based": {
                    "summary": "Typed assignment + typed answer",
                    "value": {
                        "assignment_text": "Giải phương trình: x^2 - 5x + 6 = 0",
                        "student_answer_text": "x = 2 hoặc x = 3",
                        "subject": "math",
                        "grade_level": "high_school",
                        "language": "vi",
                    },
                },
                "mixed": {
                    "summary": "Photo of test + typed answer",
                    "value": {
                        "assignment_image": "<base64_jpeg>",
                        "student_answer_text": "Câu trả lời của học sinh...",
                        "subject": "literature",
                        "grade_level": "high_school",
                        "language": "vi",
                    },
                },
            }
        }


class StudyPlanItem(BaseModel):
    week: int
    focus: str
    activities: List[str]


class RecommendedMaterial(BaseModel):
    title: str
    type: str  # textbook / video / exercise / website
    description: Optional[str] = None
    url: Optional[str] = None


class GradeResponse(BaseModel):
    """Response from grade & tips job"""

    success: bool
    job_id: str
    status: str

    # Available when completed
    score: Optional[float] = Field(
        None, ge=0, le=10, description="Score on 10-point scale"
    )
    score_breakdown: Optional[Dict[str, Any]] = Field(
        None,
        description="Per-section scores, e.g. {'setup': 2, 'calculation': 5, 'conclusion': 1}",
    )
    overall_feedback: Optional[str] = Field(
        None, description="Overall assessment and grading rationale"
    )
    strengths: Optional[List[str]] = Field(
        None, description="What the student did well"
    )
    weaknesses: Optional[List[str]] = Field(
        None, description="Errors and knowledge gaps identified"
    )
    correct_solution: Optional[str] = Field(
        None, description="The correct solution for reference"
    )
    improvement_plan: Optional[List[str]] = Field(
        None, description="Specific steps for the student to improve"
    )
    study_plan: Optional[List[StudyPlanItem]] = Field(
        None, description="Personalised weekly study plan"
    )
    recommended_materials: Optional[List[RecommendedMaterial]] = Field(
        None, description="Recommended resources to study"
    )

    # Token usage
    tokens: Optional[Dict[str, int]] = None

    # Points
    points_deducted: int = 2
    new_balance: Optional[int] = None

    # Error info
    error: Optional[str] = None
    message: Optional[str] = None
