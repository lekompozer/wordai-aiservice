"""
Conversation Learning Models
Pydantic models for "Learn with Conversations" feature

Collections:
- conversation_library: Conversation content and metadata
- conversation_gaps: Gap-fill exercises (3 difficulty levels)
- conversation_vocabulary: Vocabulary and grammar from conversations
- user_conversation_progress: User learning progress
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum


# ============================================================================
# ENUMS
# ============================================================================


class ConversationLevel(str, Enum):
    """Conversation difficulty levels"""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class ConversationTopic(str, Enum):
    """Conversation topics"""

    DAILY_LIFE = "daily_life"
    RESTAURANT = "restaurant"
    SHOPPING = "shopping"
    TRAVEL = "travel"
    WORK_BUSINESS = "work_business"
    HEALTH_WELLNESS = "health_wellness"
    TECHNOLOGY = "technology"
    EDUCATION = "education"
    ENTERTAINMENT = "entertainment"
    SOCIAL_ISSUES = "social_issues"


class SpeakerGender(str, Enum):
    """Speaker gender for TTS"""

    MALE = "male"
    FEMALE = "female"


class GapDifficulty(str, Enum):
    """Gap exercise difficulty"""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


# ============================================================================
# COLLECTION: conversation_library
# ============================================================================


class DialogueTurn(BaseModel):
    """Single dialogue turn"""

    speaker: str = Field(..., description="A or B")
    gender: SpeakerGender
    text_en: str = Field(..., description="English text")
    text_vi: str = Field(..., description="Vietnamese translation")
    order: int = Field(..., description="Turn number (1-based)")


class TopicDisplay(BaseModel):
    """Topic display names"""

    en: str
    vi: str


class TitleDisplay(BaseModel):
    """Conversation title in both languages"""

    en: str
    vi: str


class AudioInfo(BaseModel):
    """Audio file information"""

    url: Optional[str] = None
    duration_seconds: Optional[int] = None
    speaker_a_voice: str = Field(default="en-US-Neural2-D", description="Male voice")
    speaker_b_voice: str = Field(default="en-US-Neural2-C", description="Female voice")


class ConversationLibrary(BaseModel):
    """
    Conversation data for learning

    Collection: conversation_library
    """

    conversation_id: str = Field(
        ..., description="Unique ID (e.g., conv_beginner_daily_001)"
    )
    level: ConversationLevel
    topic: str = Field(..., description="Topic slug")
    topic_display: TopicDisplay
    title: TitleDisplay
    situation: str = Field(..., description="Context description")

    # Dialogue content
    dialogue: List[DialogueTurn] = Field(
        ..., description="6-15 turns depending on level"
    )
    full_text_en: str = Field(..., description="Full conversation in English")
    full_text_vi: str = Field(..., description="Full conversation in Vietnamese")

    # Audio
    audio: AudioInfo = Field(default_factory=AudioInfo)

    # Metadata
    word_count: int
    turn_count: int
    difficulty_score: float = Field(..., ge=1.0, le=10.0)

    # Generation info
    generated_by: str = Field(default="deepseek-v3")
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    audio_generated_at: Optional[datetime] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# COLLECTION: conversation_vocabulary
# ============================================================================


class VocabularyItem(BaseModel):
    """Single vocabulary item"""

    word: str
    definition_en: str
    definition_vi: str
    example: str = Field(..., description="Example from conversation")
    pos_tag: str = Field(..., description="NOUN, VERB, ADJ, etc.")


class GrammarPoint(BaseModel):
    """Grammar pattern explanation"""

    pattern: str = Field(..., description="Grammar pattern (e.g., 'Can I + verb?')")
    explanation_en: str
    explanation_vi: str
    example: str = Field(..., description="Example from conversation")


class ConversationVocabulary(BaseModel):
    """
    Vocabulary and grammar from conversation

    Collection: conversation_vocabulary
    """

    vocab_id: str = Field(..., description="vocab_{conversation_id}")
    conversation_id: str

    vocabulary: List[VocabularyItem] = Field(..., description="8-15 words")
    grammar_points: List[GrammarPoint] = Field(..., description="3-6 grammar points")

    generated_by: str = Field(default="deepseek-v3")
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# COLLECTION: conversation_gaps
# ============================================================================


class GapItem(BaseModel):
    """Single gap in conversation"""

    position: int = Field(..., description="Gap index (0-based)")
    speaker: str = Field(..., description="A or B")
    turn_index: int = Field(..., description="Which turn in dialogue (0-based)")
    word_index: int = Field(..., description="Position in sentence")
    correct_answer: str
    hint_char_count: int
    pos_tag: str
    line_number: int = Field(..., description="Line number in full text")


class ConversationGaps(BaseModel):
    """
    Gap-fill exercise for conversation

    Collection: conversation_gaps
    """

    gap_id: str = Field(..., description="gap_{conversation_id}_{difficulty}")
    conversation_id: str
    difficulty: GapDifficulty

    gaps: List[GapItem]
    text_with_gaps: str = Field(..., description="Full text with ___ placeholders")
    gap_count: int

    created_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# COLLECTION: user_conversation_progress
# ============================================================================


class ConversationAnswer(BaseModel):
    """User's answer to a gap"""

    gap_index: int
    user_answer: str
    is_correct: bool


class ConversationAttempt(BaseModel):
    """Single learning attempt"""

    attempt_number: int
    score: float = Field(..., ge=0.0, le=100.0)
    correct_count: int
    total_gaps: int
    time_spent_seconds: int
    answers: List[ConversationAnswer]
    completed_at: datetime = Field(default_factory=datetime.utcnow)


class UserConversationProgress(BaseModel):
    """
    User's progress on a conversation

    Collection: user_conversation_progress
    """

    progress_id: str = Field(..., description="prog_{user_id}_{conversation_id}")
    user_id: str
    conversation_id: str
    difficulty: GapDifficulty

    attempts: List[ConversationAttempt] = Field(default=[])
    best_score: float = Field(default=0.0)
    is_completed: bool = Field(default=False, description="Score >= 80%")
    audio_listened: bool = Field(default=False)

    last_attempt_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# API REQUEST/RESPONSE MODELS
# ============================================================================


class GenerateConversationRequest(BaseModel):
    """Request to generate conversation"""

    level: ConversationLevel
    topic: str
    count: int = Field(
        default=1, ge=1, le=5, description="Number of conversations to generate"
    )


class ConversationResponse(BaseModel):
    """Conversation response"""

    conversation_id: str
    level: ConversationLevel
    topic: str
    title: TitleDisplay
    situation: str
    dialogue: List[DialogueTurn]
    word_count: int
    turn_count: int
    has_audio: bool
    has_vocabulary: bool
    has_gaps: bool
