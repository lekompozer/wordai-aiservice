"""
Song Learning Models
Pydantic models for "Learn English With Songs" feature

Collections:
- song_lyrics: Raw song data from loidichvn.com
- song_gaps: Gap-fill exercises (3 difficulty levels)
- user_song_progress: User learning progress
- user_song_subscription: Premium subscriptions
- user_daily_free_songs: Daily free song tracking
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum


# ============================================================================
# ENUMS
# ============================================================================


class DifficultyLevel(str, Enum):
    """Difficulty levels for gap exercises"""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class POSTag(str, Enum):
    """Part of Speech tags"""

    NOUN = "NOUN"
    VERB = "VERB"
    ADJ = "ADJ"
    ADV = "ADV"
    PROPN = "PROPN"  # Proper noun (names, places)


class SubscriptionPlan(str, Enum):
    """Subscription plan types"""

    MONTHLY = "monthly"
    SIX_MONTHS = "6months"
    YEARLY = "yearly"


class PaymentMethod(str, Enum):
    """Payment methods"""

    MOMO = "momo"
    VNPAY = "vnpay"
    BANK_TRANSFER = "bank_transfer"


# ============================================================================
# COLLECTION: song_lyrics
# ============================================================================


class SongLyrics(BaseModel):
    """
    Song data crawled from loidichvn.com

    Collection: song_lyrics
    """

    song_id: str = Field(..., description="Unique ID from loidichvn")
    title: str = Field(..., description="Song title")
    artist: str = Field(..., description="Artist name")
    category: str = Field(..., description="Music category/genre")

    # Lyrics data
    english_lyrics: str = Field(..., description="English lyrics (raw)")
    vietnamese_lyrics: str = Field(..., description="Vietnamese lyrics (raw)")

    # Media
    youtube_url: str = Field(..., description="YouTube URL")
    youtube_id: str = Field(..., description="YouTube video ID")

    # Metadata
    view_count: int = Field(default=0, description="View count from loidichvn")
    source_url: str = Field(..., description="Original URL from loidichvn")

    # Processing status
    is_processed: bool = Field(default=False, description="Has gaps been generated?")
    has_profanity: bool = Field(default=False, description="Contains profanity?")
    word_count: int = Field(default=0, description="Total word count")

    # Timestamps
    crawled_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "song_id": "yesterday-beatles-123",
                "title": "Yesterday",
                "artist": "The Beatles",
                "category": "Pop",
                "english_lyrics": "Yesterday, all my troubles seemed so far away...",
                "vietnamese_lyrics": "Ngày hôm qua, mọi phiền muộn như xa vời...",
                "youtube_url": "https://www.youtube.com/watch?v=wXTJBr9tt8Q",
                "youtube_id": "wXTJBr9tt8Q",
                "view_count": 15000,
                "source_url": "https://loidichvn.com/yesterday-beatles",
                "word_count": 120,
            }
        }


# ============================================================================
# COLLECTION: song_gaps
# ============================================================================


class GapItem(BaseModel):
    """Single gap in a song"""

    line_number: int = Field(..., description="Line number (0-indexed)")
    word_index: int = Field(..., description="Word index in line (0-indexed)")
    original_word: str = Field(..., description="Original word (lowercase)")
    lemma: str = Field(..., description="Lemma form")
    pos_tag: str = Field(..., description="POS tag: NOUN/VERB/ADJ")
    difficulty_score: float = Field(..., description="Zipf frequency score (0-8)")
    char_count: int = Field(..., description="Character count")
    is_end_of_line: bool = Field(default=False, description="Is last word in line?")

    class Config:
        json_schema_extra = {
            "example": {
                "line_number": 0,
                "word_index": 5,
                "original_word": "believe",
                "lemma": "believe",
                "pos_tag": "VERB",
                "difficulty_score": 4.2,
                "char_count": 7,
                "is_end_of_line": False,
            }
        }


class SongGaps(BaseModel):
    """
    Gap-fill exercise for a song at specific difficulty

    Collection: song_gaps
    """

    gap_id: str = Field(..., description="UUID for this gap version")
    song_id: str = Field(..., description="Reference to song_lyrics")
    difficulty: DifficultyLevel = Field(..., description="Difficulty level")

    # Gap data
    gaps: List[GapItem] = Field(..., max_length=20, description="Max 20 gaps")

    # Display data
    lyrics_with_gaps: str = Field(..., description="Lyrics with ___ placeholders")
    gap_count: int = Field(..., ge=1, le=20, description="Number of gaps (max 20)")

    # Statistics
    avg_difficulty_score: float = Field(default=0.0, description="Average difficulty")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "gap_id": "uuid-123",
                "song_id": "yesterday-beatles-123",
                "difficulty": "easy",
                "gap_count": 8,
                "avg_difficulty_score": 5.2,
                "lyrics_with_gaps": "___, all my troubles seemed so ___ away...",
            }
        }


# ============================================================================
# COLLECTION: user_song_progress
# ============================================================================


class AttemptAnswer(BaseModel):
    """Single answer in an attempt"""

    gap_index: int = Field(..., description="Gap index (0-based)")
    user_answer: str = Field(..., description="User's answer")
    is_correct: bool = Field(..., description="Is answer correct?")


class LearningAttempt(BaseModel):
    """Single learning attempt"""

    attempt_number: int = Field(..., description="Attempt number")
    score: float = Field(..., ge=0, le=100, description="Score (0-100)")
    correct_count: int = Field(..., description="Number correct")
    total_gaps: int = Field(..., description="Total gaps")
    time_spent_seconds: int = Field(..., description="Time spent")
    answers: List[AttemptAnswer] = Field(..., description="User answers")
    completed_at: datetime = Field(default_factory=datetime.utcnow)


class UserSongProgress(BaseModel):
    """
    User's learning progress for a specific song

    Collection: user_song_progress
    """

    progress_id: str = Field(..., description="UUID")
    user_id: str = Field(..., description="Firebase UID")
    song_id: str = Field(..., description="Reference to song_lyrics")
    difficulty: DifficultyLevel = Field(..., description="Difficulty chosen")

    # Learning data
    attempts: List[LearningAttempt] = Field(default=[], description="All attempts")

    # Status
    is_completed: bool = Field(default=False, description="Completed (>= 80% score)?")
    best_score: float = Field(default=0.0, description="Best score achieved")
    total_attempts: int = Field(default=0, description="Total attempts")

    # Timestamps
    first_attempt_at: Optional[datetime] = None
    last_attempt_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# COLLECTION: user_song_subscription
# ============================================================================


class UserSongSubscription(BaseModel):
    """
    Premium subscription for unlimited songs

    Collection: user_song_subscription
    """

    subscription_id: str = Field(..., description="UUID")
    user_id: str = Field(..., description="Firebase UID")

    # Plan details
    plan_type: SubscriptionPlan = Field(..., description="Subscription plan")
    price_paid: int = Field(..., description="Amount paid (VND)")

    # Subscription period
    start_date: datetime = Field(..., description="Subscription start")
    end_date: datetime = Field(..., description="Subscription end")
    is_active: bool = Field(default=True, description="Is subscription active?")

    # Payment info
    payment_method: PaymentMethod = Field(..., description="Payment method used")
    transaction_id: str = Field(..., description="Payment transaction ID")

    # Auto-renewal
    auto_renew: bool = Field(default=False, description="Auto-renew enabled?")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    cancelled_at: Optional[datetime] = None

    class Config:
        json_schema_extra = {
            "example": {
                "subscription_id": "sub-uuid-123",
                "user_id": "firebase-uid-abc",
                "plan_type": "monthly",
                "price_paid": 29000,
                "payment_method": "momo",
            }
        }


# ============================================================================
# COLLECTION: user_daily_free_songs
# ============================================================================


class DailySongPlay(BaseModel):
    """Single song played today"""

    song_id: str = Field(..., description="Song ID")
    difficulty: DifficultyLevel = Field(..., description="Difficulty played")
    played_at: datetime = Field(default_factory=datetime.utcnow)


class UserDailyFreeSongs(BaseModel):
    """
    Daily free song tracking (5 songs/day limit)

    Collection: user_daily_free_songs
    """

    record_id: str = Field(..., description="UUID")
    user_id: str = Field(..., description="Firebase UID")
    date: datetime = Field(..., description="Date (ISO, day only)")

    # Free songs today
    songs_played: List[DailySongPlay] = Field(
        default=[], max_length=5, description="Songs played today (max 5)"
    )
    songs_count: int = Field(default=0, ge=0, le=5, description="Count (max 5)")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# API REQUEST/RESPONSE MODELS
# ============================================================================


class SongListItem(BaseModel):
    """Song item in list response"""

    song_id: str
    title: str
    artist: str
    category: str
    youtube_id: str
    difficulties_available: List[DifficultyLevel]
    word_count: int
    view_count: int


class SongDetailResponse(BaseModel):
    """Song detail response"""

    song_id: str
    title: str
    artist: str
    category: str
    english_lyrics: str
    vietnamese_lyrics: str
    youtube_url: str
    youtube_id: str
    view_count: int
    word_count: int
    difficulties_available: List[DifficultyLevel]
    has_gaps: bool  # Whether gaps have been generated for this song


class StartSessionRequest(BaseModel):
    """Request to start learning session"""

    difficulty: DifficultyLevel


class SubmitAnswersRequest(BaseModel):
    """Request to submit answers"""

    session_id: str
    difficulty: DifficultyLevel
    answers: List[AttemptAnswer]
    time_spent_seconds: int


class CreateSubscriptionRequest(BaseModel):
    """Request to create subscription"""

    plan_type: SubscriptionPlan


# ============================================================================
# API RESPONSE MODELS
# ============================================================================


class BrowseSongsRequest(BaseModel):
    """Request model for browsing songs"""

    category: Optional[str] = None
    search_query: Optional[str] = None
    skip: int = 0
    limit: int = 20


class BrowseSongsResponse(BaseModel):
    """Response model for browsing songs"""

    songs: List[SongListItem]
    total: int
    page: int
    limit: int


class RandomSongRequest(BaseModel):
    """Request model for random song"""

    difficulty: Optional[DifficultyLevel] = None
    category: Optional[str] = None


class RandomSongResponse(BaseModel):
    """Response model for random song"""

    song_id: str
    title: str
    artist: str
    category: str
    youtube_id: str
    youtube_url: str
    word_count: int
    difficulty: DifficultyLevel


class StartSessionResponse(BaseModel):
    """Response model for starting session"""

    session_id: str
    song_id: str
    title: str
    artist: str
    difficulty: DifficultyLevel
    gaps: List[GapItem]
    lyrics_with_gaps: str
    gap_count: int
    youtube_url: Optional[str] = None
    is_premium: bool
    remaining_free_songs: int  # -1 for unlimited


class SubmitAnswersResponse(BaseModel):
    """Response model for submitting answers"""

    session_id: str
    score: float
    correct_count: int
    total_gaps: int
    is_completed: bool
    best_score: float
    graded_answers: List[
        dict
    ]  # List of {gap_id, correct_answer, user_answer, is_correct}


class RecentActivity(BaseModel):
    """Recent learning activity"""

    song_id: str
    title: str
    artist: str
    difficulty: DifficultyLevel
    best_score: float
    is_completed: bool
    last_attempt_at: datetime


class UserProgressResponse(BaseModel):
    """User progress response"""

    user_id: str
    total_songs_played: int
    total_attempts: int
    completed_songs: dict  # {difficulty: count}
    average_score: float
    is_premium: bool
    songs_played_today: int
    remaining_free_songs: int
    subscription: Optional[dict] = None  # Subscription details if premium
    recent_activity: List[RecentActivity]
