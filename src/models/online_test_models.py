"""
Pydantic Models for Online Test System
Contains all request/response models for test creation, taking, and grading
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict, Any
from datetime import datetime


class GenerateTestRequest(BaseModel):
    """Request model for AI-generated test"""

    source_type: str = Field(..., description="Source type: 'document' or 'file'")
    source_id: str = Field(..., description="Document ID or R2 file key")
    title: str = Field(..., description="Test title", min_length=5, max_length=200)
    description: Optional[str] = Field(
        None,
        description="Test description for test takers (optional, user-facing)",
        max_length=1000,
    )
    creator_name: Optional[str] = Field(
        None, min_length=2, max_length=100, description="Custom creator display name"
    )
    user_query: Optional[str] = Field(
        None,
        description="Instructions to AI: what topics/concepts to test (optional for files, can be inferred from content)",
        min_length=10,
        max_length=2000,
    )
    language: str = Field(
        default="vi",
        description="Language for test content: specify any language (e.g., 'vi', 'en', 'zh', 'fr', 'es', etc.)",
    )
    difficulty: Optional[str] = Field(
        None,
        description="Question difficulty level: 'easy', 'medium', 'hard' (optional, AI can infer if not provided)",
    )

    # Test type configuration
    test_type: str = Field(
        default="mcq",
        description="Test type: 'mcq' (multiple choice only), 'essay' (essay only), 'mixed' (both MCQ and essay)",
    )

    # Question configuration - flexible based on test_type
    num_questions: Optional[int] = Field(
        None,
        description="Total number of questions (used for 'mcq' or 'essay' types). Max 100.",
        ge=1,
        le=100,
    )

    # Mixed test configuration (only for test_type='mixed')
    num_mcq_questions: Optional[int] = Field(
        None,
        description="Number of MCQ questions (for 'mixed' type). Max 100.",
        ge=0,
        le=100,
    )
    num_essay_questions: Optional[int] = Field(
        None,
        description="Number of essay questions (for 'mixed' type). Max 20.",
        ge=0,
        le=20,
    )
    mcq_points: Optional[int] = Field(
        None,
        description="Total points for MCQ section (for 'mixed' type)",
        ge=0,
        le=1000,
    )
    essay_points: Optional[int] = Field(
        None,
        description="Total points for essay section (for 'mixed' type)",
        ge=0,
        le=1000,
    )

    time_limit_minutes: int = Field(
        30,
        description="Time limit in minutes. Max 270 minutes (4.5 hours).",
        ge=1,
        le=270,
    )
    max_retries: int = Field(3, description="Maximum number of attempts", ge=1, le=10)
    passing_score: int = Field(
        70, description="Minimum score percentage to pass (0-100)", ge=0, le=100
    )
    deadline: Optional[datetime] = Field(
        None, description="Global deadline for all users (ISO 8601 format)"
    )
    show_answers_timing: str = Field(
        "immediate",
        description="When to show answers: 'immediate' (show after submit) or 'after_deadline' (show only after deadline passes)",
    )
    num_options: int = Field(
        4,
        description="Number of answer options per question (e.g., 4 for A-D, 6 for A-F). Set to 0 or 'auto' to let AI decide.",
        ge=0,
        le=10,
    )
    num_correct_answers: int = Field(
        1,
        description="Number of correct answers per question. Set to 0 or 'auto' to let AI decide based on question complexity.",
        ge=0,
        le=10,
    )
    test_category: str = Field(
        default="academic",
        description="Test category: 'academic' (knowledge-based with correct answers) or 'diagnostic' (personality/assessment without correct answers)",
    )

    @model_validator(mode="after")
    def validate_test_configuration(self):
        """Validate test type and question counts"""
        if self.test_type == "mixed":
            # For mixed tests, require MCQ and essay counts
            if not self.num_mcq_questions or not self.num_essay_questions:
                raise ValueError(
                    "num_mcq_questions and num_essay_questions are required for test_type='mixed'"
                )
            if self.num_mcq_questions + self.num_essay_questions > 100:
                raise ValueError("Total questions (MCQ + Essay) cannot exceed 100")
            # Ignore num_questions for mixed type
            self.num_questions = self.num_mcq_questions + self.num_essay_questions
        else:
            # For mcq or essay types, require num_questions
            if not self.num_questions:
                raise ValueError(
                    f"num_questions is required for test_type='{self.test_type}'"
                )
            # Set individual counts based on test_type
            if self.test_type == "mcq":
                self.num_mcq_questions = self.num_questions
                self.num_essay_questions = 0
            elif self.test_type == "essay":
                self.num_mcq_questions = 0
                self.num_essay_questions = self.num_questions

        return self


class ManualTestQuestion(BaseModel):
    """Manual question model - flexible validation for user-created tests

    Supports 8 question types:
    - "mcq": Multiple choice questions (default)
    - "essay": Essay questions requiring text answers
    - "matching": Match left items to right options (IELTS)
    - "map_labeling": Label positions on a map/diagram (IELTS)
    - "completion": Fill in blanks in form/note/table (IELTS)
    - "sentence_completion": Complete sentences (IELTS)
    - "short_answer": Short answer questions (IELTS)
    - "mixed": Combination of different types (determined by questions array)
    """

    question_type: str = Field(
        default="mcq",
        description="Question type: 'mcq', 'essay', 'matching', 'map_labeling', 'completion', 'sentence_completion', 'short_answer'",
    )
    question_text: str = Field(..., min_length=1, max_length=2000)
    instruction: Optional[str] = Field(
        None,
        description="Additional instruction for the question (e.g., 'Write NO MORE THAN TWO WORDS')",
        max_length=500,
    )

    # MCQ-specific fields (required only if question_type='mcq')
    options: Optional[list] = Field(
        default=None,
        description="List of options with 'key' and 'text' (required for MCQ, not needed for Essay)",
    )
    correct_answer_keys: Optional[List[str]] = Field(
        None,
        description="List of correct answer keys (e.g., ['A'], ['B', 'C'] for multi-answer). (Optional for Diagnostic tests)",
    )
    # Legacy field for backward compatibility
    correct_answer_key: Optional[str] = Field(
        None,
        description="DEPRECATED: Use correct_answer_keys instead. Single correct answer key (A, B, C, D, etc.)",
    )

    # Common fields
    explanation: Optional[str] = Field(
        None, description="Optional explanation or solution", max_length=5000
    )

    # Essay-specific fields
    max_points: Optional[int] = Field(
        default=1,
        description="Maximum points for this question (used for weighted scoring)",
        ge=1,
        le=100,
    )
    grading_rubric: Optional[str] = Field(
        None, description="Grading criteria/rubric for essay questions", max_length=2000
    )

    # Media fields (optional for all question types)
    media_type: Optional[str] = Field(
        None, description="Media type: 'image' or 'audio'"
    )
    media_url: Optional[str] = Field(None, description="Public URL to media file")
    media_description: Optional[str] = Field(
        None, description="Description of media content", max_length=1500
    )

    # ========== IELTS-specific fields ==========

    # Matching type fields
    left_items: Optional[List[Dict[str, str]]] = Field(
        None,
        description="Left items to match (matching type): [{'key': '1', 'text': 'Item 1'}, ...]",
    )
    right_options: Optional[List[Dict[str, str]]] = Field(
        None,
        description="Right options to choose from (matching type): [{'key': 'A', 'text': 'Option A'}, ...]",
    )
    correct_matches: Optional[Dict[str, str]] = Field(
        None, description="Correct matches (matching type): {'1': 'A', '2': 'C', ...}"
    )

    # Map/Diagram Labeling fields
    diagram_url: Optional[str] = Field(
        None,
        description="URL to diagram/map image (map_labeling type)",
        max_length=1000,
    )
    diagram_description: Optional[str] = Field(
        None,
        description="Description of the diagram (map_labeling type)",
        max_length=1000,
    )
    label_positions: Optional[List[Dict[str, str]]] = Field(
        None,
        description="Label positions (map_labeling): [{'key': '1', 'description': 'Position 1'}, ...]",
    )
    correct_labels: Optional[Dict[str, str]] = Field(
        None, description="Correct labels (map_labeling): {'1': 'A', '2': 'B', ...}"
    )

    # Completion fields (form/note/table)
    template: Optional[str] = Field(
        None,
        description="Template with blanks (completion type): 'Name: _____(1)_____, Age: _____(2)_____'",
        max_length=5000,
    )
    completion_subtype: Optional[str] = Field(
        None, description="Subtype for completion: 'form', 'note', 'table'"
    )
    blanks: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Blank definitions (completion): [{'key': '1', 'position': 'Name', 'word_limit': 2}, ...]",
    )
    correct_answers: Optional[Dict[str, List[str]]] = Field(
        None,
        description="Correct answers with alternatives (completion/sentence_completion/short_answer): {'1': ['answer1', 'answer2'], ...}",
    )

    # Sentence Completion fields
    sentences: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Sentences to complete: [{'key': '1', 'template': 'The library opens at _____.', 'word_limit': 2, 'correct_answers': ['8 AM']}, ...]",
    )

    # Short Answer fields
    questions: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Short answer questions: [{'key': '1', 'text': 'What is...?', 'word_limit': 3, 'correct_answers': ['answer']}, ...]",
    )

    # Common IELTS fields
    case_sensitive: Optional[bool] = Field(
        False,
        description="Whether answers are case-sensitive (for text-based IELTS types)",
    )
    audio_section: Optional[int] = Field(
        None, description="Audio section number (for listening tests)", ge=1, le=10
    )

    @field_validator("question_type")
    @classmethod
    def validate_question_type(cls, v):
        valid_types = [
            "mcq",
            "essay",
            "matching",
            "map_labeling",
            "completion",
            "sentence_completion",
            "short_answer",
        ]
        if v not in valid_types:
            raise ValueError(f"question_type must be one of: {', '.join(valid_types)}")
        return v

    @model_validator(mode="after")
    def validate_question_fields(self):
        """Validate that required fields are present based on question_type"""

        # ========== MCQ Validation ==========
        if self.question_type == "mcq":
            # MCQ requires options
            if not self.options or len(self.options) < 2:
                raise ValueError("MCQ questions must have at least 2 options")

            # Convert legacy correct_answer_key to correct_answer_keys
            if self.correct_answer_key and not self.correct_answer_keys:
                self.correct_answer_keys = [self.correct_answer_key]

            # NOTE: We allow correct_answer_keys to be None for Diagnostic/Survey tests
            # If it is provided, we validate all keys exist in options
            if self.correct_answer_keys:
                option_keys = [
                    opt.get("key") if isinstance(opt, dict) else opt
                    for opt in self.options
                ]
                for answer_key in self.correct_answer_keys:
                    if answer_key not in option_keys:
                        raise ValueError(
                            f"correct_answer_key '{answer_key}' not found in options"
                        )

        # ========== Essay Validation ==========
        elif self.question_type == "essay":
            # Essay should NOT have options or correct_answer_keys
            if self.options is not None and len(self.options) > 0:
                raise ValueError("Essay questions should not have options")
            if (
                self.correct_answer_keys is not None
                and len(self.correct_answer_keys) > 0
            ):
                raise ValueError("Essay questions should not have correct_answer_keys")
            if (
                self.correct_answer_key is not None
                and len(self.correct_answer_key.strip()) > 0
            ):
                raise ValueError("Essay questions should not have correct_answer_key")

        # ========== Matching Validation ==========
        elif self.question_type == "matching":
            if not self.left_items or len(self.left_items) < 2:
                raise ValueError("Matching questions must have at least 2 left_items")
            if not self.right_options or len(self.right_options) < 2:
                raise ValueError(
                    "Matching questions must have at least 2 right_options"
                )
            if not self.correct_matches:
                raise ValueError("Matching questions must have correct_matches")

            # Validate all left_items have corresponding matches
            left_keys = [item.get("key") for item in self.left_items]
            right_keys = [opt.get("key") for opt in self.right_options]

            for left_key in left_keys:
                if left_key not in self.correct_matches:
                    raise ValueError(f"Missing match for left_item key '{left_key}'")
                right_key = self.correct_matches[left_key]
                if right_key not in right_keys:
                    raise ValueError(
                        f"Invalid right_option key '{right_key}' in correct_matches"
                    )

        # ========== Map Labeling Validation ==========
        elif self.question_type == "map_labeling":
            if not self.diagram_url:
                raise ValueError("Map labeling questions must have diagram_url")
            if not self.label_positions or len(self.label_positions) < 1:
                raise ValueError(
                    "Map labeling questions must have at least 1 label_position"
                )
            if not self.options or len(self.options) < 2:
                raise ValueError("Map labeling questions must have at least 2 options")
            if not self.correct_labels:
                raise ValueError("Map labeling questions must have correct_labels")

            # Validate all positions have labels
            position_keys = [pos.get("key") for pos in self.label_positions]
            option_keys = [opt.get("key") for opt in self.options]

            for pos_key in position_keys:
                if pos_key not in self.correct_labels:
                    raise ValueError(f"Missing label for position '{pos_key}'")
                option_key = self.correct_labels[pos_key]
                if option_key not in option_keys:
                    raise ValueError(
                        f"Invalid option key '{option_key}' in correct_labels"
                    )

        # ========== Completion Validation ==========
        elif self.question_type == "completion":
            if not self.template:
                raise ValueError("Completion questions must have template")
            if not self.blanks or len(self.blanks) < 1:
                raise ValueError("Completion questions must have at least 1 blank")
            if not self.correct_answers:
                raise ValueError("Completion questions must have correct_answers")

            # Validate all blanks have answers
            blank_keys = [blank.get("key") for blank in self.blanks]
            for blank_key in blank_keys:
                if blank_key not in self.correct_answers:
                    raise ValueError(f"Missing answer for blank '{blank_key}'")
                if not isinstance(self.correct_answers[blank_key], list):
                    raise ValueError(
                        f"correct_answers['{blank_key}'] must be a list of acceptable answers"
                    )

        # ========== Sentence Completion Validation ==========
        elif self.question_type == "sentence_completion":
            if not self.sentences or len(self.sentences) < 1:
                raise ValueError(
                    "Sentence completion questions must have at least 1 sentence"
                )

            # Validate each sentence has required fields
            for i, sentence in enumerate(self.sentences):
                if "key" not in sentence:
                    raise ValueError(f"Sentence {i+1} missing 'key' field")
                if "template" not in sentence:
                    raise ValueError(f"Sentence {i+1} missing 'template' field")
                if "correct_answers" not in sentence or not isinstance(
                    sentence["correct_answers"], list
                ):
                    raise ValueError(
                        f"Sentence {i+1} must have 'correct_answers' as a list"
                    )

        # ========== Short Answer Validation ==========
        elif self.question_type == "short_answer":
            if not self.questions or len(self.questions) < 1:
                raise ValueError("Short answer questions must have at least 1 question")

            # Validate each question has required fields
            for i, q in enumerate(self.questions):
                if "key" not in q:
                    raise ValueError(f"Question {i+1} missing 'key' field")
                if "text" not in q:
                    raise ValueError(f"Question {i+1} missing 'text' field")
                if "correct_answers" not in q or not isinstance(
                    q["correct_answers"], list
                ):
                    raise ValueError(
                        f"Question {i+1} must have 'correct_answers' as a list"
                    )

        # Validate media fields
        if self.media_type:
            if self.media_type not in ["image", "audio"]:
                raise ValueError("media_type must be 'image' or 'audio'")
            if not self.media_url:
                raise ValueError("media_url is required when media_type is set")

        return self


class TestAttachment(BaseModel):
    """Test attachment model for reading comprehension materials"""

    title: str = Field(
        ...,
        description="Attachment title (e.g., 'Reading Passage', 'Reference Document')",
        min_length=1,
        max_length=200,
    )
    description: Optional[str] = Field(
        None, description="Optional description of the attachment", max_length=1500
    )
    file_url: str = Field(
        ...,
        description="URL to the PDF file (R2 storage URL or external URL)",
        max_length=1000,
    )
    file_size_mb: float = Field(
        ...,
        description="File size in MB (from presigned URL response)",
        ge=0,
        le=100,
    )


class PresignedURLRequest(BaseModel):
    """Request model for generating presigned URL for file upload"""

    filename: str = Field(
        ...,
        description="Original filename (e.g., 'passage1.pdf')",
        min_length=1,
        max_length=255,
    )
    file_size_mb: float = Field(
        ...,
        description="File size in MB (frontend must calculate before upload)",
        ge=0,
        le=100,  # Max 100MB per file
    )
    content_type: Optional[str] = Field(
        "application/pdf",
        description="MIME type of file (default: application/pdf)",
        max_length=100,
    )


class CreateManualTestRequest(BaseModel):
    """Request model for manual test creation"""

    title: str = Field(..., description="Test title", min_length=5, max_length=200)
    description: Optional[str] = Field(
        None, description="Test description (optional)", max_length=5000
    )
    creator_name: Optional[str] = Field(
        None, min_length=2, max_length=100, description="Custom creator display name"
    )
    test_category: str = Field(
        default="academic",
        description="Test category: 'academic' (default) or 'diagnostic'",
    )
    language: str = Field(
        default="vi",
        description="Language for test content: specify any language (e.g., 'vi', 'en', 'zh', 'fr', 'es', etc.)",
    )
    time_limit_minutes: int = Field(
        30, description="Time limit in minutes", ge=1, le=300
    )
    max_retries: int = Field(3, description="Maximum number of attempts", ge=1, le=10)
    passing_score: int = Field(
        70, description="Minimum score percentage to pass (0-100)", ge=0, le=100
    )
    deadline: Optional[datetime] = Field(
        None, description="Global deadline for all users (ISO 8601 format)"
    )
    show_answers_timing: str = Field(
        "immediate",
        description="When to show answers: 'immediate' (show after submit) or 'after_deadline' (show only after deadline passes)",
    )
    questions: Optional[List[ManualTestQuestion]] = Field(
        default=[],
        description="List of questions (optional, can be empty to create draft test)",
    )
    attachments: Optional[List[TestAttachment]] = Field(
        default=[],
        description="List of PDF attachments for reading comprehension (optional)",
    )
    grading_config: Optional[dict] = Field(
        default=None,
        description="""Grading configuration for mixed-format tests. Optional.
        {
            "mcq_weight": 0.6,  // MCQ portion weight (0-1)
            "essay_weight": 0.4,  // Essay portion weight (0-1)
            "auto_calculate_weights": true  // Auto-calculate from max_points
        }
        If not provided, weights calculated equally by question count.
        """,
    )

    @field_validator("test_category")
    @classmethod
    def validate_test_category(cls, v):
        if v not in ["academic", "diagnostic"]:
            raise ValueError("test_category must be 'academic' or 'diagnostic'")
        return v

    @model_validator(mode="after")
    def validate_academic_questions(self):
        """Ensure academic tests have correct answers for MCQs"""
        if self.test_category == "academic" and self.questions:
            for i, q in enumerate(self.questions):
                if q.question_type == "mcq" and not q.correct_answer_key:
                    raise ValueError(
                        f"Question {i+1} (MCQ) must have a correct answer for academic tests"
                    )
        return self


class DuplicateTestRequest(BaseModel):
    """Request model for duplicating a test"""

    new_title: Optional[str] = Field(
        None,
        description="New title for duplicated test (optional, will auto-generate if not provided)",
        max_length=200,
    )


class TestQuestionsResponse(BaseModel):
    """Response model for test questions (for taking)"""

    test_id: str
    status: str
    title: str
    description: Optional[str]
    time_limit_minutes: int
    num_questions: int
    questions: list


class TestStatusResponse(BaseModel):
    """Response model for test status polling"""

    test_id: str
    status: str  # pending, generating, ready, failed
    progress_percent: int
    message: str
    error_message: Optional[str] = None
    # Include these when ready
    title: Optional[str] = None
    description: Optional[str] = None
    num_questions: Optional[int] = None
    created_at: Optional[str] = None
    generated_at: Optional[str] = None


class SubmitTestRequest(BaseModel):
    """Request model for test submission

    Supports both MCQ and Essay answers:
    - MCQ (Multi-answer): {question_id, question_type: 'mcq', selected_answer_keys: ["A", "B"]}
    - MCQ (Legacy): {question_id, question_type: 'mcq', selected_answer_key: "A"}
    - Essay: {question_id, question_type: 'essay', essay_answer, media_attachments: [...]}

    Essay answers can include optional media attachments:
    - Images: JPG, PNG, GIF
    - Audio: MP3, WAV, M4A
    - Documents: PDF, DOCX

    Media attachment format:
    {
        "media_type": "image|audio|document",
        "media_url": "https://static.wordai.pro/answer-media/...",
        "filename": "diagram.png",
        "file_size_mb": 2.5,
        "description": "Optional description"
    }
    """

    user_answers: list = Field(
        ...,
        description="""List of answers with format:
        MCQ (Multi-answer): {"question_id": "q1", "question_type": "mcq", "selected_answer_keys": ["A", "B"]}
        MCQ (Legacy): {"question_id": "q1", "question_type": "mcq", "selected_answer_key": "A"}
        Essay: {
            "question_id": "q2",
            "question_type": "essay",
            "essay_answer": "text...",
            "media_attachments": [
                {
                    "media_type": "image",
                    "media_url": "https://...",
                    "filename": "diagram.png",
                    "file_size_mb": 2.5,
                    "description": "My diagram explaining..."
                }
            ]
        }
        """,
    )


class EssayGrade(BaseModel):
    """Model for essay question grade"""

    question_id: str = Field(..., description="ID of the essay question")
    points_awarded: float = Field(
        ..., ge=0, description="Points awarded (0 to max_points)"
    )
    max_points: int = Field(
        ..., ge=1, le=100, description="Maximum points for this question"
    )
    feedback: Optional[str] = Field(
        default=None, max_length=5000, description="Grader's feedback"
    )
    graded_by: str = Field(..., description="User ID of the grader")
    graded_at: str = Field(..., description="ISO timestamp when graded")


class GradingStatusEnum(str):
    """Enum for grading status"""

    AUTO_GRADED = "auto_graded"  # All MCQ, no manual grading needed
    PENDING_GRADING = "pending_grading"  # Contains essay questions, not graded yet
    PARTIALLY_GRADED = "partially_graded"  # Some essay questions graded
    FULLY_GRADED = "fully_graded"  # All questions graded


class TestResultResponse(BaseModel):
    """Response model for test results

    For auto-graded tests (MCQ only):
    - score and correct_answers are immediately available
    - grading_status: auto_graded

    For tests with essays:
    - score and correct_answers may be partial or None
    - grading_status: pending_grading, partially_graded, or fully_graded
    - essay_grades: list of graded essay questions
    """

    submission_id: str
    score: Optional[float] = Field(
        default=None, description="Final score (None if pending grading)"
    )
    total_questions: int
    correct_answers: Optional[int] = Field(
        default=None, description="Number correct (MCQ only)"
    )
    time_taken_seconds: int
    results: list
    grading_status: str = Field(
        default="auto_graded",
        description="auto_graded|pending_grading|partially_graded|fully_graded",
    )
    essay_grades: Optional[List[EssayGrade]] = Field(
        default=None, description="Grades for essay questions"
    )


class TestSummary(BaseModel):
    """Summary of a test"""

    test_id: str
    title: str
    num_questions: int
    time_limit_minutes: int
    created_at: str
    attempts_count: int


class GradingQueueItem(BaseModel):
    """Model for grading queue entries

    Represents a test submission waiting for manual grading
    """

    submission_id: str = Field(..., description="ID of the test submission")
    test_id: str = Field(..., description="ID of the test")
    test_title: str = Field(..., description="Title of the test")
    student_id: str = Field(..., description="User ID of the student")
    student_name: Optional[str] = Field(default=None, description="Name of the student")
    submitted_at: str = Field(..., description="ISO timestamp of submission")
    essay_question_count: int = Field(
        ..., ge=1, description="Number of essay questions to grade"
    )
    graded_count: int = Field(default=0, ge=0, description="Number already graded")
    assigned_to: Optional[str] = Field(
        default=None, description="User ID of assigned grader"
    )
    priority: int = Field(
        default=0, description="Priority level for grading (higher = more urgent)"
    )
    status: str = Field(default="pending", description="pending|in_progress|completed")


class TestProgressUpdate(BaseModel):
    """Model for updating test progress

    Used when tracking partial saves of essay answers during test
    """

    test_id: str = Field(..., description="ID of the test")
    user_id: str = Field(..., description="ID of the user taking the test")
    current_answers: list = Field(
        ..., description="Current state of answers (same format as SubmitTestRequest)"
    )
    last_updated: str = Field(..., description="ISO timestamp of last update")


class GradeEssayRequest(BaseModel):
    """Request model for grading essay questions"""

    question_id: str = Field(..., description="ID of the essay question to grade")
    points_awarded: float = Field(
        ..., ge=0, description="Points awarded (0 to max_points)"
    )
    feedback: Optional[str] = Field(
        default=None, max_length=5000, description="Grader's feedback (optional)"
    )


class GradeAllEssaysRequest(BaseModel):
    """Request model for grading all essay questions at once"""

    grades: list[GradeEssayRequest] = Field(
        ..., description="List of grades for all essay questions"
    )


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
    creator_name: Optional[str] = Field(
        None, min_length=2, max_length=100, description="Custom creator display name"
    )

    # Test settings
    max_retries: Optional[int] = Field(None, ge=1, le=20)
    time_limit_minutes: Optional[int] = Field(None, ge=1, le=300)
    passing_score: Optional[int] = Field(None, ge=0, le=100)
    deadline: Optional[datetime] = None
    show_answers_timing: Optional[str] = None

    # Questions
    questions: Optional[list] = None

    # Attachments
    attachments: Optional[list] = Field(
        None,
        description="List of PDF attachments for reading comprehension",
    )

    # Marketplace config (if published)
    marketplace_title: Optional[str] = Field(None, min_length=10, max_length=200)
    marketplace_description: Optional[str] = Field(None, min_length=50, max_length=2000)
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


class PaymentInfoRequest(BaseModel):
    """Request model for setting up payment information for earnings withdrawal"""

    account_holder_name: str = Field(
        ..., description="Tên chủ tài khoản", min_length=2, max_length=100
    )
    account_number: str = Field(
        ..., description="Số tài khoản ngân hàng", min_length=6, max_length=30
    )
    bank_name: str = Field(
        ..., description="Tên ngân hàng", min_length=2, max_length=100
    )
    bank_branch: Optional[str] = Field(
        None, description="Chi nhánh ngân hàng (optional)", max_length=100
    )


class WithdrawEarningsRequest(BaseModel):
    """Request model for withdrawing earnings to cash"""

    amount: int = Field(
        ..., description="Amount to withdraw in points (1 point = 1 VND)", ge=100000
    )
