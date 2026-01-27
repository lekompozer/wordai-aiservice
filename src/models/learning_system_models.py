"""
Learning System Models
Models for Code Editor learning categories, topics, knowledge articles, and community features
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from enum import Enum


# ==================== ENUMS ====================


class ContentSourceType(str, Enum):
    """Source type for content"""

    WORDAI_TEAM = "wordai_team"
    COMMUNITY = "community"


class TopicLevel(str, Enum):
    """Learning level for topics"""

    STUDENT = "student"  # For students (Grade 10, 11, 12)
    PROFESSIONAL = "professional"  # For real-world practice


class GradeLevel(str, Enum):
    """Grade levels for student topics"""

    GRADE_10 = "10"
    GRADE_11 = "11"
    GRADE_12 = "12"


class ContentDifficulty(str, Enum):
    """Content difficulty levels"""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class GradingType(str, Enum):
    """Exercise grading types"""

    TEST_CASES = "test_cases"  # Run test cases
    AI_GRADING = "ai_grading"  # AI evaluates code + sample solution
    MANUAL = "manual"  # Manual review by instructor


class SubmissionStatus(str, Enum):
    """Exercise submission status"""

    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    PENDING_REVIEW = "pending_review"


# ==================== LEARNING CATEGORIES ====================


class LearningCategoryCreate(BaseModel):
    """Create learning category request"""

    id: str = Field(..., min_length=1, max_length=50, description="Category ID (slug)")
    name: str = Field(..., min_length=1, max_length=100, description="Category name")
    description: Optional[str] = Field(
        None, max_length=500, description="Category description"
    )
    icon: Optional[str] = Field(None, max_length=10, description="Category icon emoji")
    order: int = Field(default=0, description="Display order")


class LearningCategoryUpdate(BaseModel):
    """Update learning category request"""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    icon: Optional[str] = Field(None, max_length=10)
    order: Optional[int] = None
    is_active: Optional[bool] = None


class LearningCategoryResponse(BaseModel):
    """Learning category response"""

    id: str
    name: str
    description: Optional[str]
    icon: Optional[str]
    order: int
    is_active: bool
    topic_count: int = 0
    created_at: datetime
    updated_at: datetime


# ==================== LEARNING TOPICS ====================


class LearningTopicCreate(BaseModel):
    """Create learning topic request"""

    id: str = Field(..., min_length=1, max_length=100, description="Topic ID (slug)")
    category_id: str = Field(..., description="Parent category ID")
    name: str = Field(..., min_length=1, max_length=200, description="Topic name")
    description: Optional[str] = Field(None, max_length=1000)
    level: TopicLevel = Field(..., description="Learning level")
    grade: Optional[GradeLevel] = Field(
        None, description="Grade level (for student topics)"
    )
    order: int = Field(default=0, description="Display order within category")


class LearningTopicUpdate(BaseModel):
    """Update learning topic request"""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    level: Optional[TopicLevel] = None
    grade: Optional[GradeLevel] = None
    order: Optional[int] = None
    is_active: Optional[bool] = None


class LearningTopicResponse(BaseModel):
    """Learning topic response"""

    id: str
    category_id: str
    name: str
    description: Optional[str]
    level: TopicLevel
    grade: Optional[GradeLevel]
    order: int
    is_active: bool
    knowledge_count: int = 0
    template_count: int = 0
    exercise_count: int = 0
    created_at: datetime
    updated_at: datetime


# ==================== KNOWLEDGE ARTICLES ====================


class KnowledgeArticleCreate(BaseModel):
    """Create knowledge article request"""

    topic_id: str = Field(..., description="Parent topic ID")
    title: str = Field(..., min_length=1, max_length=300, description="Article title")
    content: str = Field(..., min_length=1, description="Article content (Markdown)")
    excerpt: Optional[str] = Field(None, max_length=500, description="Short summary")
    difficulty: Optional[ContentDifficulty] = Field(
        ContentDifficulty.BEGINNER, description="Difficulty level"
    )
    tags: List[str] = Field(default_factory=list, description="Article tags")
    is_published: bool = Field(default=True, description="Publish immediately")


class KnowledgeArticleUpdate(BaseModel):
    """Update knowledge article request"""

    title: Optional[str] = Field(None, min_length=1, max_length=300)
    content: Optional[str] = Field(None, min_length=1)
    excerpt: Optional[str] = Field(None, max_length=500)
    difficulty: Optional[ContentDifficulty] = None
    tags: Optional[List[str]] = None
    is_published: Optional[bool] = None
    is_featured: Optional[bool] = None


class KnowledgeArticleResponse(BaseModel):
    """Knowledge article response"""

    id: str
    topic_id: str
    category_id: str
    title: str
    content: str
    excerpt: Optional[str]
    source_type: ContentSourceType
    created_by: str
    author_name: str
    difficulty: ContentDifficulty
    tags: List[str]
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    is_published: bool
    is_featured: bool
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime]


class KnowledgeArticleListItem(BaseModel):
    """Knowledge article list item (without full content)"""

    id: str
    topic_id: str
    category_id: str
    title: str
    excerpt: Optional[str]
    source_type: ContentSourceType
    author_name: str
    difficulty: ContentDifficulty
    tags: List[str]
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    is_featured: bool
    created_at: datetime


# ==================== UPDATED TEMPLATE MODELS ====================


class TemplateCreate(BaseModel):
    """Create code template request (updated with learning system)"""

    topic_id: str = Field(..., description="Parent topic ID")
    title: str = Field(..., min_length=1, max_length=200)
    programming_language: str = Field(..., description="Programming language")
    code: str = Field(..., min_length=1, description="Template code")
    description: Optional[str] = Field(None, max_length=1000)
    difficulty: Optional[ContentDifficulty] = Field(ContentDifficulty.BEGINNER)
    tags: List[str] = Field(default_factory=list)
    is_published: bool = Field(default=True)


class TemplateUpdate(BaseModel):
    """Update code template request"""

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    code: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = Field(None, max_length=1000)
    difficulty: Optional[ContentDifficulty] = None
    tags: Optional[List[str]] = None
    is_published: Optional[bool] = None
    is_featured: Optional[bool] = None


# ==================== UPDATED EXERCISE MODELS ====================


class ExerciseCreate(BaseModel):
    """Create code exercise request (updated with AI grading)"""

    topic_id: str = Field(..., description="Parent topic ID")
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, description="Exercise description")
    programming_language: str = Field(..., description="Programming language")
    difficulty: ContentDifficulty = Field(ContentDifficulty.BEGINNER)
    points: int = Field(default=10, ge=1, le=100, description="Exercise points")

    # Grading configuration
    grading_type: GradingType = Field(
        GradingType.TEST_CASES, description="Grading method"
    )
    sample_solution: Optional[str] = Field(
        None, description="Sample solution for AI grading"
    )
    test_cases: Optional[List[Dict[str, Any]]] = Field(
        default_factory=list, description="Test cases"
    )

    # Additional fields
    starter_code: Optional[str] = Field(None, description="Initial code template")
    hints: List[str] = Field(default_factory=list, description="Exercise hints")
    tags: List[str] = Field(default_factory=list)
    is_published: bool = Field(default=True)


class ExerciseUpdate(BaseModel):
    """Update code exercise request"""

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, min_length=1)
    difficulty: Optional[ContentDifficulty] = None
    points: Optional[int] = Field(None, ge=1, le=100)
    grading_type: Optional[GradingType] = None
    sample_solution: Optional[str] = None
    test_cases: Optional[List[Dict[str, Any]]] = None
    starter_code: Optional[str] = None
    hints: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    is_published: Optional[bool] = None
    is_featured: Optional[bool] = None


class ExerciseSubmitRequest(BaseModel):
    """Submit exercise solution request"""

    code: str = Field(..., min_length=1, description="Student code")


class AIGradingResult(BaseModel):
    """AI grading result"""

    overall_score: int = Field(..., ge=0, le=100, description="Overall score 0-100")
    feedback: str = Field(..., description="AI feedback")
    suggestions: List[str] = Field(
        default_factory=list, description="Improvement suggestions"
    )
    model_used: str = Field(default="claude-sonnet-4.5", description="AI model used")


class ExerciseSubmissionResponse(BaseModel):
    """Exercise submission response"""

    id: str
    exercise_id: str
    user_id: str
    code: str
    grading_type: GradingType
    status: SubmissionStatus
    score: int
    max_score: int

    # Test case results (if applicable)
    test_results: Optional[List[Dict[str, Any]]] = None

    # AI grading results (if applicable)
    ai_grading_result: Optional[AIGradingResult] = None

    execution_time_ms: Optional[int] = None
    submitted_at: datetime
    graded_at: Optional[datetime]


# ==================== LIKE & COMMENT SYSTEM ====================


class ContentType(str, Enum):
    """Content types that support likes/comments"""

    KNOWLEDGE = "knowledge"
    TEMPLATE = "template"
    EXERCISE = "exercise"


class LikeRequest(BaseModel):
    """Like/unlike content request"""

    content_type: ContentType = Field(..., description="Type of content")
    content_id: str = Field(..., description="Content ID")


class CommentCreate(BaseModel):
    """Create comment request"""

    content_type: ContentType = Field(..., description="Type of content")
    content_id: str = Field(..., description="Content ID")
    comment: str = Field(..., min_length=1, max_length=2000, description="Comment text")
    parent_comment_id: Optional[str] = Field(
        None, description="Parent comment ID for replies"
    )


class CommentUpdate(BaseModel):
    """Update comment request"""

    comment: str = Field(..., min_length=1, max_length=2000)


class CommentResponse(BaseModel):
    """Comment response"""

    id: str
    content_type: ContentType
    content_id: str
    user_id: str
    user_name: str
    comment: str
    parent_comment_id: Optional[str]
    like_count: int = 0
    is_edited: bool = False
    created_at: datetime
    updated_at: datetime


# ==================== ADMIN MODELS ====================


class ContentModerationAction(str, Enum):
    """Content moderation actions"""

    DELETE = "delete"
    FEATURE = "feature"
    UNFEATURE = "unfeature"
    UNPUBLISH = "unpublish"


class ModerationRequest(BaseModel):
    """Content moderation request (admin only)"""

    content_type: ContentType = Field(..., description="Type of content")
    content_id: str = Field(..., description="Content ID")
    action: ContentModerationAction = Field(..., description="Moderation action")
    reason: Optional[str] = Field(None, max_length=500, description="Reason for action")
