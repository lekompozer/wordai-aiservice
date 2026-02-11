"""
Song Learning API Routes - Core Learning Features

Phase 5: Core Learning APIs (6 endpoints)
1. GET /api/v1/songs - Browse songs with filters
2. GET /api/v1/songs/{song_id} - Get song details
3. GET /api/v1/songs/random - Get random song
4. POST /api/v1/songs/{song_id}/start - Start learning session
5. POST /api/v1/songs/{song_id}/submit - Submit answers
6. GET /api/v1/users/me/progress - Get user progress

Business rules:
- Free users: 5 songs/day limit
- Premium users: Unlimited
- Completion threshold: ≥80% correct answers
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional
from datetime import datetime, date
import uuid
import random

from src.database.db_manager import DBManager
from src.models.song_models import (
    # Request models
    BrowseSongsRequest,
    StartSessionRequest,
    SubmitAnswersRequest,
    # Response models
    BrowseSongsResponse,
    SongDetailResponse,
    RandomSongResponse,
    StartSessionResponse,
    SubmitAnswersResponse,
    UserProgressResponse,
    # Core models
    DifficultyLevel,
    SongLyrics,
    SongGaps,
    UserSongProgress,
    UserDailyFreeSongs,
    LearningAttempt,
    AttemptAnswer,
    SongListItem,
)
from src.middleware.firebase_auth import get_current_user


router = APIRouter(prefix="/api/v1/songs", tags=["Song Learning"])


# Dependency: Get database
def get_db():
    """Get database connection."""
    db_manager = DBManager()
    return db_manager.db


# Dependency: Check premium status
async def check_user_premium(user_id: str, db) -> bool:
    """
    Check if user has active premium subscription.

    Returns: True if user is premium, False otherwise
    """
    subscription_col = db["user_song_subscription"]

    subscription = subscription_col.find_one(
        {"user_id": user_id, "is_active": True, "end_date": {"$gte": datetime.utcnow()}}
    )

    return subscription is not None


# Dependency: Check daily limit
async def check_daily_limit(user_id: str, db) -> dict:
    """
    Check user's daily free song limit.

    Returns: Dict with is_premium, songs_played_today, remaining_free
    """
    is_premium = await check_user_premium(user_id, db)

    if is_premium:
        return {
            "is_premium": True,
            "songs_played_today": 0,
            "remaining_free": -1,  # Unlimited
            "can_play": True,
        }

    # Check daily free songs
    daily_col = db["user_daily_free_songs"]
    today = date.today().isoformat()

    daily_record = daily_col.find_one({"user_id": user_id, "date": today})

    songs_played = len(daily_record["songs_played"]) if daily_record else 0
    remaining = max(0, 5 - songs_played)

    return {
        "is_premium": False,
        "songs_played_today": songs_played,
        "remaining_free": remaining,
        "can_play": remaining > 0,
    }


@router.get("/", response_model=BrowseSongsResponse)
async def browse_songs(
    category: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    db=Depends(get_db),
):
    """
    Browse songs with filters and pagination.

    Query params:
    - category: Filter by category name
    - search: Search in title or artist
    - skip: Pagination offset
    - limit: Number of results (max 100)

    Returns: List of songs with metadata
    """
    # Validate limit
    limit = min(limit, 100)

    # Build query
    query = {}

    if category:
        query["category"] = {"$regex": category, "$options": "i"}

    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"artist": {"$regex": search, "$options": "i"}},
        ]

    # Get songs
    song_lyrics_col = db["song_lyrics"]
    song_gaps_col = db["song_gaps"]

    total = song_lyrics_col.count_documents(query)
    songs_raw = list(
        song_lyrics_col.find(
            query,
            {
                "song_id": 1,
                "title": 1,
                "artist": 1,
                "category": 1,
                "youtube_id": 1,
                "view_count": 1,
                "word_count": 1,
                "_id": 0,
            },
        )
        .skip(skip)
        .limit(limit)
    )

    # Add difficulties_available for each song
    songs = []
    for song in songs_raw:
        # Get available difficulties from song_gaps
        difficulties = song_gaps_col.distinct(
            "difficulty", {"song_id": song["song_id"]}
        )
        song["difficulties_available"] = difficulties if difficulties else []
        songs.append(song)

    page = (skip // limit) + 1 if limit > 0 else 1

    return BrowseSongsResponse(songs=songs, total=total, page=page, limit=limit)


@router.get("/{song_id}", response_model=SongDetailResponse)
async def get_song_detail(song_id: str, db=Depends(get_db)):
    """
    Get detailed information about a song.

    Returns: Song lyrics and metadata (no gaps - those come from /start)
    """
    song_lyrics_col = db["song_lyrics"]

    song = song_lyrics_col.find_one({"song_id": song_id}, {"_id": 0})

    if not song:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Song {song_id} not found"
        )

    # Check if gaps exist for this song
    song_gaps_col = db["song_gaps"]
    has_gaps = song_gaps_col.count_documents({"song_id": song_id}) > 0

    return SongDetailResponse(**song, has_gaps=has_gaps)


@router.get("/random/pick", response_model=RandomSongResponse)
async def get_random_song(
    difficulty: Optional[DifficultyLevel] = None,
    category: Optional[str] = None,
    db=Depends(get_db),
):
    """
    Get a random song for learning.

    Query params:
    - difficulty: Filter by difficulty level (easy/medium/hard)
    - category: Filter by category name

    Returns: Random song with specified filters
    """
    # Build query
    query = {}

    if category:
        query["category"] = {"$regex": category, "$options": "i"}

    # Get random song
    song_lyrics_col = db["song_lyrics"]

    # Use MongoDB aggregation for random selection
    pipeline = []

    if query:
        pipeline.append({"$match": query})

    # If difficulty specified, filter songs that have gaps for that difficulty
    if difficulty:
        song_gaps_col = db["song_gaps"]

        # Get song_ids that have this difficulty
        gap_docs = song_gaps_col.find({"difficulty": difficulty.value}, {"song_id": 1})
        song_ids_with_difficulty = [doc["song_id"] for doc in gap_docs]

        if not song_ids_with_difficulty:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No songs found with {difficulty.value} difficulty",
            )

        pipeline.append({"$match": {"song_id": {"$in": song_ids_with_difficulty}}})

    # Random sample
    pipeline.append({"$sample": {"size": 1}})

    # Project fields
    pipeline.append(
        {
            "$project": {
                "song_id": 1,
                "title": 1,
                "artist": 1,
                "category": 1,
                "youtube_id": 1,
                "word_count": 1,
                "_id": 0,
            }
        }
    )

    result = list(song_lyrics_col.aggregate(pipeline))

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No songs found matching criteria",
        )

    song = result[0]

    # Construct youtube_url from youtube_id
    youtube_url = f"https://www.youtube.com/watch?v={song['youtube_id']}"

    # Use requested difficulty or default to easy
    selected_difficulty = difficulty if difficulty else DifficultyLevel.EASY

    return RandomSongResponse(
        **song, youtube_url=youtube_url, difficulty=selected_difficulty
    )


@router.post("/{song_id}/start", response_model=StartSessionResponse)
async def start_learning_session(
    song_id: str,
    request: StartSessionRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Start a learning session for a song.

    Request body:
    - difficulty: Difficulty level (easy/medium/hard)

    Returns: Song gaps (exercise) and session info

    Business rules:
    - Free users: Max 5 songs/day
    - Premium users: Unlimited
    - Updates user_daily_free_songs collection
    """
    user_id = current_user["user_id"]

    # Check daily limit
    limit_info = await check_daily_limit(user_id, db)

    if not limit_info["can_play"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Daily limit reached. You've played {limit_info['songs_played_today']}/5 free songs today. Subscribe for unlimited access!",
        )

    # Get song
    song_lyrics_col = db["song_lyrics"]
    song = song_lyrics_col.find_one({"song_id": song_id})

    if not song:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Song {song_id} not found"
        )

    # Get gaps for specified difficulty
    song_gaps_col = db["song_gaps"]
    gaps_doc = song_gaps_col.find_one(
        {"song_id": song_id, "difficulty": request.difficulty.value}, {"_id": 0}
    )

    if not gaps_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No {request.difficulty.value} difficulty gaps found for song {song_id}",
        )

    # Update daily free songs (if not premium)
    if not limit_info["is_premium"]:
        daily_col = db["user_daily_free_songs"]
        today = date.today().isoformat()

        # Upsert: Add song_id to songs_played array
        daily_col.update_one(
            {"user_id": user_id, "date": today},
            {
                "$setOnInsert": {
                    "record_id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "date": today,
                    "created_at": datetime.utcnow(),
                },
                "$addToSet": {  # Only add if not already present
                    "songs_played": song_id
                },
            },
            upsert=True,
        )

        # Recalculate remaining
        remaining_free = limit_info["remaining_free"] - 1
    else:
        remaining_free = -1  # Unlimited

    # Return session data
    return StartSessionResponse(
        session_id=str(uuid.uuid4()),  # Generate session ID for tracking
        song_id=song_id,
        title=song["title"],
        artist=song["artist"],
        difficulty=request.difficulty,
        gaps=gaps_doc["gaps"],
        lyrics_with_gaps=gaps_doc["lyrics_with_gaps"],
        gap_count=gaps_doc["gap_count"],
        youtube_url=song.get("youtube_url"),
        is_premium=limit_info["is_premium"],
        remaining_free_songs=remaining_free,
    )


@router.post("/{song_id}/submit", response_model=SubmitAnswersResponse)
async def submit_answers(
    song_id: str,
    request: SubmitAnswersRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Submit user's answers for gap-fill exercise.

    Request body:
    - session_id: Session ID from /start
    - difficulty: Difficulty level
    - answers: Dict of {gap_position: user_answer}

    Returns: Score, correct answers, is_completed status

    Business rules:
    - Score: Percentage of correct answers
    - Completed: Score ≥ 80%
    - Updates user_song_progress collection
    """
    user_id = current_user["user_id"]

    # Get gaps for validation
    song_gaps_col = db["song_gaps"]
    gaps_doc = song_gaps_col.find_one(
        {"song_id": song_id, "difficulty": request.difficulty.value}
    )

    if not gaps_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No {request.difficulty.value} difficulty gaps found for song {song_id}",
        )

    # Build correct answers map
    correct_answers = {
        gap["position"]: gap["correct_answer"] for gap in gaps_doc["gaps"]
    }

    # Grade answers - convert list to lookup
    user_answers_map = {ans.gap_index: ans.user_answer for ans in request.answers}

    total_gaps = len(correct_answers)
    correct_count = 0
    graded_answers = []

    for position, correct_answer in correct_answers.items():
        user_answer = user_answers_map.get(position, "").strip().lower()
        is_correct = user_answer == correct_answer.lower()

        if is_correct:
            correct_count += 1

        graded_answers.append(
            {
                "gap_index": position,
                "user_answer": user_answer,
                "correct_answer": correct_answer,
                "is_correct": is_correct,
            }
        )

    # Calculate score
    score = round((correct_count / total_gaps) * 100, 2)
    is_completed = score >= 80.0

    # Update user progress
    progress_col = db["user_song_progress"]

    # Create attempt record with graded answers
    attempt_answers = [
        AttemptAnswer(
            gap_index=ans["gap_index"],
            user_answer=ans["user_answer"],
            is_correct=ans["is_correct"],
        )
        for ans in graded_answers
    ]

    attempt = LearningAttempt(
        attempt_number=0,  # Will be updated below
        score=score,
        correct_count=correct_count,
        total_gaps=total_gaps,
        time_spent_seconds=request.time_spent_seconds,
        answers=attempt_answers,
        completed_at=datetime.utcnow(),
    )

    # Get existing progress
    existing_progress = progress_col.find_one(
        {"user_id": user_id, "song_id": song_id, "difficulty": request.difficulty.value}
    )

    if existing_progress:
        # Update existing progress
        attempt.attempt_number = len(existing_progress.get("attempts", [])) + 1

        best_score = max(existing_progress.get("best_score", 0), score)

        progress_col.update_one(
            {
                "user_id": user_id,
                "song_id": song_id,
                "difficulty": request.difficulty.value,
            },
            {
                "$push": {"attempts": attempt.model_dump()},
                "$set": {
                    "best_score": best_score,
                    "is_completed": is_completed
                    or existing_progress.get("is_completed", False),
                    "last_attempt_at": datetime.utcnow(),
                },
            },
        )
    else:
        # Create new progress
        attempt.attempt_number = 1

        new_progress = UserSongProgress(
            progress_id=str(uuid.uuid4()),
            user_id=user_id,
            song_id=song_id,
            difficulty=request.difficulty,
            attempts=[attempt],
            best_score=score,
            is_completed=is_completed,
            last_attempt_at=datetime.utcnow(),
        )

        progress_col.insert_one(new_progress.model_dump())

    return SubmitAnswersResponse(
        session_id=request.session_id,
        score=score,
        correct_count=correct_count,
        total_gaps=total_gaps,
        is_completed=is_completed,
        graded_answers=graded_answers,
        best_score=(
            max(existing_progress.get("best_score", 0), score)
            if existing_progress
            else score
        ),
    )


@router.get("/users/me/progress", response_model=UserProgressResponse)
async def get_user_progress(
    current_user: dict = Depends(get_current_user), db=Depends(get_db)
):
    """
    Get user's learning progress and statistics.

    Returns:
    - Total songs played
    - Completed songs (by difficulty)
    - Total attempts
    - Average score
    - Recent activity
    - Subscription status
    """
    user_id = current_user["user_id"]

    progress_col = db["user_song_progress"]

    # Get all user's progress
    all_progress = list(progress_col.find({"user_id": user_id}))

    # Calculate statistics
    total_songs = len({p["song_id"] for p in all_progress})
    total_attempts = sum(len(p.get("attempts", [])) for p in all_progress)

    completed_by_difficulty = {
        DifficultyLevel.EASY.value: 0,
        DifficultyLevel.MEDIUM.value: 0,
        DifficultyLevel.HARD.value: 0,
    }

    all_scores = []
    for progress in all_progress:
        if progress.get("is_completed"):
            difficulty = progress["difficulty"]
            completed_by_difficulty[difficulty] += 1

        all_scores.extend(
            attempt.get("score", 0) for attempt in progress.get("attempts", [])
        )

    average_score = round(sum(all_scores) / len(all_scores), 2) if all_scores else 0

    # Get recent activity (last 10)
    recent_progress = sorted(
        all_progress, key=lambda x: x.get("last_attempt_at", datetime.min), reverse=True
    )[:10]

    # Enrich with song info
    song_lyrics_col = db["song_lyrics"]
    recent_activity = []

    for progress in recent_progress:
        song = song_lyrics_col.find_one(
            {"song_id": progress["song_id"]}, {"title": 1, "artist": 1, "_id": 0}
        )

        if song:
            recent_activity.append(
                {
                    "song_id": progress["song_id"],
                    "title": song["title"],
                    "artist": song["artist"],
                    "difficulty": progress["difficulty"],
                    "best_score": progress.get("best_score", 0),
                    "is_completed": progress.get("is_completed", False),
                    "last_attempt_at": progress.get("last_attempt_at"),
                }
            )

    # Check subscription
    limit_info = await check_daily_limit(user_id, db)

    # Get subscription details if premium
    subscription_info = None
    if limit_info["is_premium"]:
        subscription_col = db["user_song_subscription"]
        subscription = subscription_col.find_one(
            {"user_id": user_id, "is_active": True}, {"_id": 0}
        )

        if subscription:
            subscription_info = {
                "plan_type": subscription["plan_type"],
                "start_date": subscription["start_date"],
                "end_date": subscription["end_date"],
                "price_paid": subscription.get("price_paid", 29000),
            }

    return UserProgressResponse(
        user_id=user_id,
        total_songs_played=total_songs,
        total_attempts=total_attempts,
        completed_songs=completed_by_difficulty,
        average_score=average_score,
        is_premium=limit_info["is_premium"],
        songs_played_today=limit_info["songs_played_today"],
        remaining_free_songs=limit_info["remaining_free"],
        subscription=subscription_info,
        recent_activity=recent_activity,
    )
