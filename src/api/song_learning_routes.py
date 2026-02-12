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
import json
import redis

from src.database.db_manager import DBManager
from src.models.song_models import (
    # Request models
    BrowseSongsRequest,
    StartSessionRequest,
    SubmitAnswersRequest,
    CreatePlaylistRequest,
    UpdatePlaylistRequest,
    AddSongToPlaylistRequest,
    AdminCreateSongRequest,
    AdminUpdateSongRequest,
    # Response models
    BrowseSongsResponse,
    SongDetailResponse,
    RandomSongResponse,
    StartSessionResponse,
    SubmitAnswersResponse,
    UserProgressResponse,
    PlaylistResponse,
    PlaylistListResponse,
    # Core models
    DifficultyLevel,
    SongLyrics,
    SongGaps,
    UserSongProgress,
    UserDailyFreeSongs,
    LearningAttempt,
    AttemptAnswer,
    SongListItem,
    UserPlaylist,
)
from src.middleware.firebase_auth import get_current_user


router = APIRouter(prefix="/api/v1/songs", tags=["Song Learning"])


# Dependency: Get database
def get_db():
    """Get database connection."""
    db_manager = DBManager()
    return db_manager.db


# Dependency: Get Redis client
def get_redis():
    """Get Redis client for caching."""
    return redis.Redis(host="redis-server", port=6379, db=0, decode_responses=True)


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
    search_query: Optional[str] = None,  # Support frontend's parameter name
    first_letter: Optional[str] = None,
    artist: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    db=Depends(get_db),
):
    """
    Browse songs with filters and pagination.

    Query params:
    - category: Filter by category name
    - search: Search in title or artist (alias: search_query)
    - search_query: Alternative name for search parameter
    - first_letter: Filter by first letter (A-Z) or # for numbers
    - artist: Filter by exact artist name
    - skip: Pagination offset
    - limit: Number of results (max 100)

    Returns: List of songs with metadata
    """
    # Validate limit
    limit = min(limit, 100)
    
    # Support both 'search' and 'search_query' parameter names
    search_term = search or search_query

    # Build query
    query = {}

    if category:
        query["category"] = {"$regex": category, "$options": "i"}

    if artist:
        query["artist"] = {"$regex": f"^{artist}$", "$options": "i"}

    if first_letter:
        if first_letter == "#":
            # Filter songs starting with numbers
            query["title"] = {"$regex": "^[0-9]", "$options": "i"}
        else:
            # Filter songs starting with specific letter
            query["title"] = {"$regex": f"^{first_letter}", "$options": "i"}

    # Get songs
    song_lyrics_col = db["song_lyrics"]
    song_gaps_col = db["song_gaps"]

    # Use text search if searching (MUCH faster than regex)
    if search_term:
        # Text search on title and artist (uses text index)
        query["$text"] = {"$search": search_term}

        # Get results with text score for relevance sorting
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
                    "score": {"$meta": "textScore"},  # Relevance score
                    "_id": 0,
                },
            )
            .sort([("score", {"$meta": "textScore"})])  # Sort by relevance
            .skip(skip)
            .limit(limit)
        )
    else:
        # Regular query (no search term)
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


@router.get("/artists/list")
async def get_artists_list(db=Depends(get_db)):
    """
    Get list of all artists with song counts.

    Returns: List of artists sorted alphabetically with song counts
    """
    song_lyrics_col = db["song_lyrics"]

    # Aggregate to get unique artists with counts
    pipeline = [
        {"$group": {"_id": "$artist", "song_count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},  # Sort alphabetically
        {"$project": {"artist": "$_id", "song_count": 1, "_id": 0}},
    ]

    artists = list(song_lyrics_col.aggregate(pipeline))

    # Group by first letter
    artists_by_letter = {}
    for artist_doc in artists:
        artist = artist_doc["artist"]
        first_char = artist[0].upper() if artist else "#"

        # If starts with number, group under #
        if first_char.isdigit():
            first_char = "#"
        elif not first_char.isalpha():
            first_char = "#"

        if first_char not in artists_by_letter:
            artists_by_letter[first_char] = []

        artists_by_letter[first_char].append(artist_doc)

    return {
        "total_artists": len(artists),
        "artists": artists,
        "artists_by_letter": artists_by_letter,
    }


@router.get("/artists/{artist_name}/songs", response_model=BrowseSongsResponse)
async def get_songs_by_artist(
    artist_name: str,
    skip: int = 0,
    limit: int = 20,
    db=Depends(get_db),
):
    """
    Get all songs by a specific artist.

    Perfect for artist detail page showing all their songs.

    Args:
        artist_name: Artist name (case-insensitive)
        skip: Pagination offset
        limit: Number of results (max 100)

    Returns: List of songs by the artist
    """
    # Validate limit
    limit = min(limit, 100)

    song_lyrics_col = db["song_lyrics"]
    song_gaps_col = db["song_gaps"]

    # Case-insensitive exact match on artist
    query = {"artist": {"$regex": f"^{artist_name}$", "$options": "i"}}

    total = song_lyrics_col.count_documents(query)

    if total == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artist '{artist_name}' not found",
        )

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
        .sort([("view_count", -1)])  # Sort by popularity
        .skip(skip)
        .limit(limit)
    )

    # Add difficulties_available for each song
    songs = []
    for song in songs_raw:
        difficulties = song_gaps_col.distinct(
            "difficulty", {"song_id": song["song_id"]}
        )
        song["difficulties_available"] = difficulties if difficulties else []
        songs.append(song)

    page = (skip // limit) + 1 if limit > 0 else 1

    return BrowseSongsResponse(songs=songs, total=total, page=page, limit=limit)


@router.get("/hot/trending", response_model=BrowseSongsResponse)
async def get_hot_songs(
    skip: int = 0,
    limit: int = 20,
    db=Depends(get_db),
    redis_client=Depends(get_redis),
):
    """
    Get trending songs sorted by view count (most played).

    Perfect for "Hot Songs" section showing most popular songs.
    Supports pagination for infinite scroll.
    **Cached for 30 minutes** for better performance.

    - **skip**: Number of songs to skip (default: 0)
    - **limit**: Number of songs to return (default: 20, max: 100)

    Returns: Songs sorted by view_count DESC
    """
    if limit > 100:
        limit = 100

    # Try cache first (key includes skip/limit for pagination)
    cache_key = f"hot_songs:{skip}:{limit}"
    try:
        cached = redis_client.get(cache_key)
        if cached:
            data = json.loads(cached)
            return BrowseSongsResponse(**data)
    except Exception as e:
        print(f"Cache read error: {e}")

    song_lyrics_col = db["song_lyrics"]
    song_gaps_col = db["song_gaps"]

    # Get hot songs sorted by view count
    cursor = (
        song_lyrics_col.find(
            {}, {"_id": 0, "english_lyrics": 0, "vietnamese_lyrics": 0}
        )
        .sort("view_count", -1)
        .skip(skip)
        .limit(limit)
    )

    songs = []
    for song in cursor:
        # Get available difficulties
        difficulties = song_gaps_col.distinct(
            "difficulty", {"song_id": song["song_id"]}
        )

        songs.append(
            SongListItem(
                song_id=song["song_id"],
                title=song.get("title", "Unknown"),
                artist=song.get("artist", "Unknown"),
                category=song.get("category", "Unknown"),
                youtube_id=song.get("youtube_id", ""),
                difficulties_available=difficulties,
                word_count=song.get("word_count", 0),
                view_count=song.get("view_count", 0),
            )
        )

    # Get total count
    total = song_lyrics_col.count_documents({})

    response = BrowseSongsResponse(
        songs=songs,
        total=total,
        page=(skip // limit) + 1,
        limit=limit,
    )

    # Cache for 30 minutes (1800 seconds)
    try:
        redis_client.setex(cache_key, 1800, json.dumps(response.model_dump()))
    except Exception as e:
        print(f"Cache write error: {e}")

    return response


@router.get("/recent/played", response_model=BrowseSongsResponse)
async def get_recent_songs(
    skip: int = 0,
    limit: int = 20,
    db=Depends(get_db),
    redis_client=Depends(get_redis),
):
    """
    Get recently played songs sorted by last update time.

    Perfect for "Recently Played" section showing newest activity.
    Supports pagination for infinite scroll.
    **Cached for 5 minutes** for better performance.

    - **skip**: Number of songs to skip (default: 0)
    - **limit**: Number of songs to return (default: 20, max: 100)

    Returns: Songs sorted by updated_at DESC (most recently played first)
    """
    if limit > 100:
        limit = 100

    # Try cache first (key includes skip/limit for pagination)
    cache_key = f"recent_songs:{skip}:{limit}"
    try:
        cached = redis_client.get(cache_key)
        if cached:
            data = json.loads(cached)
            return BrowseSongsResponse(**data)
    except Exception as e:
        print(f"Cache read error: {e}")

    song_lyrics_col = db["song_lyrics"]
    song_gaps_col = db["song_gaps"]

    # Get recent songs sorted by updated_at
    cursor = (
        song_lyrics_col.find(
            {}, {"_id": 0, "english_lyrics": 0, "vietnamese_lyrics": 0}
        )
        .sort("updated_at", -1)
        .skip(skip)
        .limit(limit)
    )

    songs = []
    for song in cursor:
        # Get available difficulties
        difficulties = song_gaps_col.distinct(
            "difficulty", {"song_id": song["song_id"]}
        )

        songs.append(
            SongListItem(
                song_id=song["song_id"],
                title=song.get("title", "Unknown"),
                artist=song.get("artist", "Unknown"),
                category=song.get("category", "Unknown"),
                youtube_id=song.get("youtube_id", ""),
                difficulties_available=difficulties,
                word_count=song.get("word_count", 0),
                view_count=song.get("view_count", 0),
            )
        )

    # Get total count
    total = song_lyrics_col.count_documents({})

    response = BrowseSongsResponse(
        songs=songs,
        total=total,
        page=(skip // limit) + 1,
        limit=limit,
    )

    # Cache for 5 minutes (300 seconds) - shorter than hot songs since it updates more frequently
    try:
        redis_client.setex(cache_key, 300, json.dumps(response.model_dump()))
    except Exception as e:
        print(f"Cache write error: {e}")

    return response


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

    # Get available difficulties and check if gaps exist
    song_gaps_col = db["song_gaps"]
    difficulties = song_gaps_col.distinct("difficulty", {"song_id": song_id})
    has_gaps = len(difficulties) > 0

    return SongDetailResponse(
        **song,
        difficulties_available=difficulties if difficulties else [],
        has_gaps=has_gaps,
    )


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
    db=Depends(get_db),
):
    """
    Start a learning session for a song.

    Request body:
    - difficulty: Difficulty level (easy/medium/hard)

    Returns: Song gaps (exercise) and session info

    Business rules:
    - NO AUTH REQUIRED - Free to preview/start
    - Daily limit only checked on SUBMIT, not on start
    - Users can start unlimited times to see gaps
    """
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

    # Return session data (NO limit check, NO database update)
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
        is_premium=False,  # Will be checked on submit
        remaining_free_songs=-1,  # Will be calculated on submit
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
    user_id = current_user["uid"]

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

    # Build correct answers map - use original_word as correct answer
    # Gap index is 0-based position in gaps array
    correct_answers = {
        i: gap["original_word"] for i, gap in enumerate(gaps_doc["gaps"])
    }

    # Grade answers - convert list to lookup
    user_answers_map = {ans.gap_index: ans.user_answer for ans in request.answers}

    total_gaps = len(correct_answers)
    correct_count = 0
    graded_answers = []

    for gap_index, correct_answer in correct_answers.items():
        user_answer = user_answers_map.get(gap_index, "").strip().lower()
        is_correct = user_answer == correct_answer.lower()

        if is_correct:
            correct_count += 1

        graded_answers.append(
            {
                "gap_index": gap_index,
                "user_answer": user_answer,
                "correct_answer": correct_answer,
                "is_correct": is_correct,
            }
        )

    # Calculate score
    score = round((correct_count / total_gaps) * 100, 2)
    is_completed = score >= 80.0

    # Check if this is first attempt for this song (for daily limit)
    progress_col = db["user_song_progress"]
    existing_progress = progress_col.find_one(
        {"user_id": user_id, "song_id": song_id, "difficulty": request.difficulty.value}
    )

    is_first_attempt = existing_progress is None

    # If first attempt, check and update daily limit
    if is_first_attempt:
        limit_info = await check_daily_limit(user_id, db)

        if not limit_info["can_play"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Daily limit reached. You've played {limit_info['songs_played_today']}/5 free songs today. Subscribe for unlimited access!",
            )

        # Update daily free songs if not premium
        if not limit_info["is_premium"]:
            daily_col = db["user_daily_free_songs"]
            today = date.today().isoformat()

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

    # Create attempt record with graded answers
    attempt_answers = [
        AttemptAnswer(
            gap_index=ans["gap_index"],
            user_answer=ans["user_answer"],
            correct_answer=ans["correct_answer"],  # NEW: Include correct answer
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

    # Update or create progress (existing_progress already fetched above)
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

    # Update song statistics (view_count and updated_at)
    song_lyrics_col = db["song_lyrics"]
    song_lyrics_col.update_one(
        {"song_id": song_id},
        {
            "$inc": {"view_count": 1},  # Increment view count
            "$set": {"updated_at": datetime.utcnow()},  # Update timestamp
        },
    )

    return SubmitAnswersResponse(
        session_id=request.session_id,
        score=score,
        correct_count=correct_count,
        total_gaps=total_gaps,
        is_completed=is_completed,
        answers=attempt_answers,  # NEW: Return detailed answers
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
    user_id = current_user["uid"]

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


# ============================================================================
# PLAYLIST MANAGEMENT ENDPOINTS
# ============================================================================


@router.get("/playlists", response_model=List[PlaylistListResponse])
async def get_user_playlists(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Get all playlists for current user.

    Returns: List of user's playlists with song counts
    """
    user_id = current_user["uid"]
    playlists_col = db["user_song_playlists"]

    playlists = list(
        playlists_col.find({"user_id": user_id}, {"_id": 0}).sort(
            "created_at", -1
        )
    )

    # Transform to response format with song counts
    result = []
    for playlist in playlists:
        result.append(
            PlaylistListResponse(
                playlist_id=playlist["playlist_id"],
                name=playlist["name"],
                description=playlist.get("description"),
                song_count=len(playlist.get("song_ids", [])),
                is_public=playlist.get("is_public", False),
                created_at=playlist["created_at"],
                updated_at=playlist["updated_at"],
            )
        )

    return result


@router.post("/playlists", response_model=PlaylistResponse, status_code=201)
async def create_playlist(
    request: CreatePlaylistRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Create new playlist for current user.

    Request body:
    - name: Playlist name (required, 1-100 chars)
    - description: Optional description (max 500 chars)
    - is_public: Make playlist public? (default: false)

    Returns: Created playlist
    """
    user_id = current_user["uid"]
    playlists_col = db["user_song_playlists"]

    # Create playlist
    playlist_id = str(uuid.uuid4())
    now = datetime.utcnow()

    new_playlist = UserPlaylist(
        playlist_id=playlist_id,
        user_id=user_id,
        name=request.name,
        description=request.description,
        song_ids=[],
        is_public=request.is_public,
        created_at=now,
        updated_at=now,
    )

    playlists_col.insert_one(new_playlist.model_dump())

    return PlaylistResponse(
        playlist_id=playlist_id,
        user_id=user_id,
        name=request.name,
        description=request.description,
        songs=[],
        song_count=0,
        is_public=request.is_public,
        created_at=now,
        updated_at=now,
    )


@router.get("/playlists/{playlist_id}", response_model=PlaylistResponse)
async def get_playlist(
    playlist_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Get playlist details with full song information.

    Returns: Playlist with complete song details
    """
    user_id = current_user["uid"]
    playlists_col = db["user_song_playlists"]
    song_lyrics_col = db["song_lyrics"]
    song_gaps_col = db["song_gaps"]

    # Get playlist
    playlist = playlists_col.find_one(
        {"playlist_id": playlist_id}, {"_id": 0}
    )

    if not playlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Playlist not found",
        )

    # Check ownership (or public)
    if playlist["user_id"] != user_id and not playlist.get("is_public", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view this playlist",
        )

    # Get song details
    song_ids = playlist.get("song_ids", [])
    songs = []

    if song_ids:
        songs_raw = list(
            song_lyrics_col.find(
                {"song_id": {"$in": song_ids}},
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
        )

        # Add difficulties for each song
        for song in songs_raw:
            difficulties = song_gaps_col.distinct(
                "difficulty", {"song_id": song["song_id"]}
            )
            song["difficulties_available"] = difficulties if difficulties else []
            songs.append(SongListItem(**song))

    return PlaylistResponse(
        playlist_id=playlist["playlist_id"],
        user_id=playlist["user_id"],
        name=playlist["name"],
        description=playlist.get("description"),
        songs=songs,
        song_count=len(songs),
        is_public=playlist.get("is_public", False),
        created_at=playlist["created_at"],
        updated_at=playlist["updated_at"],
    )


@router.put("/playlists/{playlist_id}", response_model=PlaylistResponse)
async def update_playlist(
    playlist_id: str,
    request: UpdatePlaylistRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Update playlist name, description, or visibility.

    Request body:
    - name: New playlist name (optional)
    - description: New description (optional)
    - is_public: Change visibility (optional)

    Returns: Updated playlist
    """
    user_id = current_user["uid"]
    playlists_col = db["user_song_playlists"]

    # Get playlist
    playlist = playlists_col.find_one(
        {"playlist_id": playlist_id, "user_id": user_id}, {"_id": 0}
    )

    if not playlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Playlist not found",
        )

    # Build update fields
    update_fields = {"updated_at": datetime.utcnow()}

    if request.name is not None:
        update_fields["name"] = request.name
    if request.description is not None:
        update_fields["description"] = request.description
    if request.is_public is not None:
        update_fields["is_public"] = request.is_public

    # Update playlist
    playlists_col.update_one(
        {"playlist_id": playlist_id}, {"$set": update_fields}
    )

    # Get updated playlist (with song details)
    return await get_playlist(playlist_id, current_user, db)


@router.delete("/playlists/{playlist_id}", status_code=204)
async def delete_playlist(
    playlist_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Delete playlist.

    Returns: 204 No Content
    """
    user_id = current_user["uid"]
    playlists_col = db["user_song_playlists"]

    result = playlists_col.delete_one(
        {"playlist_id": playlist_id, "user_id": user_id}
    )

    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Playlist not found",
        )

    return None


@router.post("/playlists/{playlist_id}/songs", response_model=PlaylistResponse)
async def add_song_to_playlist(
    playlist_id: str,
    request: AddSongToPlaylistRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Add song to playlist.

    Request body:
    - song_id: Song ID to add

    Returns: Updated playlist
    """
    user_id = current_user["uid"]
    playlists_col = db["user_song_playlists"]
    song_lyrics_col = db["song_lyrics"]

    # Check if song exists
    song = song_lyrics_col.find_one({"song_id": request.song_id})
    if not song:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Song {request.song_id} not found",
        )

    # Get playlist
    playlist = playlists_col.find_one(
        {"playlist_id": playlist_id, "user_id": user_id}, {"_id": 0}
    )

    if not playlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Playlist not found",
        )

    # Check if song already in playlist
    song_ids = playlist.get("song_ids", [])
    if request.song_id in song_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Song already in playlist",
        )

    # Add song to playlist
    playlists_col.update_one(
        {"playlist_id": playlist_id},
        {
            "$push": {"song_ids": request.song_id},
            "$set": {"updated_at": datetime.utcnow()},
        },
    )

    # Return updated playlist
    return await get_playlist(playlist_id, current_user, db)


@router.delete(
    "/playlists/{playlist_id}/songs/{song_id}", response_model=PlaylistResponse
)
async def remove_song_from_playlist(
    playlist_id: str,
    song_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Remove song from playlist.

    Returns: Updated playlist
    """
    user_id = current_user["uid"]
    playlists_col = db["user_song_playlists"]

    # Get playlist
    playlist = playlists_col.find_one(
        {"playlist_id": playlist_id, "user_id": user_id}, {"_id": 0}
    )

    if not playlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Playlist not found",
        )

    # Remove song from playlist
    playlists_col.update_one(
        {"playlist_id": playlist_id},
        {
            "$pull": {"song_ids": song_id},
            "$set": {"updated_at": datetime.utcnow()},
        },
    )

    # Return updated playlist
    return await get_playlist(playlist_id, current_user, db)


# ============================================================================
# ADMIN SONG MANAGEMENT ENDPOINTS
# ============================================================================


# Admin check dependency
async def verify_admin(current_user: dict = Depends(get_current_user)):
    """
    Verify user is admin (tienhoi.lh@gmail.com).
    
    Raises 403 if not admin.
    """
    admin_email = "tienhoi.lh@gmail.com"
    user_email = current_user.get("email", "")
    
    if user_email != admin_email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    
    return current_user


@router.post("/admin/songs", response_model=SongDetailResponse, status_code=201)
async def admin_create_song(
    request: AdminCreateSongRequest,
    current_user: dict = Depends(verify_admin),
    db=Depends(get_db),
):
    """
    [ADMIN ONLY] Create new song in database.
    
    Admin: tienhoi.lh@gmail.com
    
    Request body: Full song information (see AdminCreateSongRequest schema)
    
    Returns: Created song details
    """
    song_lyrics_col = db["song_lyrics"]
    
    # Check if song_id already exists
    existing = song_lyrics_col.find_one({"song_id": request.song_id})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Song with ID {request.song_id} already exists",
        )
    
    # Create song
    now = datetime.utcnow()
    new_song = SongLyrics(
        song_id=request.song_id,
        title=request.title,
        artist=request.artist,
        category=request.category,
        english_lyrics=request.english_lyrics,
        vietnamese_lyrics=request.vietnamese_lyrics,
        youtube_url=request.youtube_url,
        youtube_id=request.youtube_id,
        view_count=request.view_count,
        source_url=request.source_url,
        word_count=request.word_count,
        has_profanity=request.has_profanity,
        is_processed=False,  # Gaps not generated yet
        crawled_at=now,
        created_at=now,
        updated_at=now,
    )
    
    song_lyrics_col.insert_one(new_song.model_dump())
    
    return SongDetailResponse(
        **new_song.model_dump(),
        difficulties_available=[],
        has_gaps=False,
    )


@router.get("/admin/songs/{song_id}", response_model=SongDetailResponse)
async def admin_get_song(
    song_id: str,
    current_user: dict = Depends(verify_admin),
    db=Depends(get_db),
):
    """
    [ADMIN ONLY] Get full song details including all fields.
    
    Admin: tienhoi.lh@gmail.com
    
    Returns: Complete song information for editing
    """
    song_lyrics_col = db["song_lyrics"]
    song_gaps_col = db["song_gaps"]
    
    song = song_lyrics_col.find_one({"song_id": song_id}, {"_id": 0})
    
    if not song:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Song {song_id} not found",
        )
    
    # Get available difficulties
    difficulties = song_gaps_col.distinct("difficulty", {"song_id": song_id})
    has_gaps = len(difficulties) > 0
    
    return SongDetailResponse(
        **song,
        difficulties_available=difficulties if difficulties else [],
        has_gaps=has_gaps,
    )


@router.put("/admin/songs/{song_id}", response_model=SongDetailResponse)
async def admin_update_song(
    song_id: str,
    request: AdminUpdateSongRequest,
    current_user: dict = Depends(verify_admin),
    db=Depends(get_db),
):
    """
    [ADMIN ONLY] Update song information.
    
    Admin: tienhoi.lh@gmail.com
    
    Request body: Fields to update (all optional)
    
    Returns: Updated song details
    """
    song_lyrics_col = db["song_lyrics"]
    
    # Check if song exists
    song = song_lyrics_col.find_one({"song_id": song_id})
    if not song:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Song {song_id} not found",
        )
    
    # Build update fields
    update_fields = {"updated_at": datetime.utcnow()}
    
    if request.title is not None:
        update_fields["title"] = request.title
    if request.artist is not None:
        update_fields["artist"] = request.artist
    if request.category is not None:
        update_fields["category"] = request.category
    if request.english_lyrics is not None:
        update_fields["english_lyrics"] = request.english_lyrics
    if request.vietnamese_lyrics is not None:
        update_fields["vietnamese_lyrics"] = request.vietnamese_lyrics
    if request.youtube_url is not None:
        update_fields["youtube_url"] = request.youtube_url
    if request.youtube_id is not None:
        update_fields["youtube_id"] = request.youtube_id
    if request.view_count is not None:
        update_fields["view_count"] = request.view_count
    if request.source_url is not None:
        update_fields["source_url"] = request.source_url
    if request.word_count is not None:
        update_fields["word_count"] = request.word_count
    if request.has_profanity is not None:
        update_fields["has_profanity"] = request.has_profanity
    
    # Update song
    song_lyrics_col.update_one(
        {"song_id": song_id},
        {"$set": update_fields}
    )
    
    # Return updated song
    return await admin_get_song(song_id, current_user, db)


@router.delete("/admin/songs/{song_id}", status_code=204)
async def admin_delete_song(
    song_id: str,
    current_user: dict = Depends(verify_admin),
    db=Depends(get_db),
):
    """
    [ADMIN ONLY] Delete song from database.
    
    Admin: tienhoi.lh@gmail.com
    
    Also deletes:
    - All gap exercises for this song
    - User progress for this song
    - Song from all playlists
    
    Returns: 204 No Content
    """
    song_lyrics_col = db["song_lyrics"]
    song_gaps_col = db["song_gaps"]
    progress_col = db["user_song_progress"]
    playlists_col = db["user_song_playlists"]
    
    # Delete song
    result = song_lyrics_col.delete_one({"song_id": song_id})
    
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Song {song_id} not found",
        )
    
    # Delete related data
    song_gaps_col.delete_many({"song_id": song_id})
    progress_col.delete_many({"song_id": song_id})
    
    # Remove from all playlists
    playlists_col.update_many(
        {"song_ids": song_id},
        {"$pull": {"song_ids": song_id}}
    )
    
    return None


