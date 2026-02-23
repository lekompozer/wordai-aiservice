"""
Conversation Learning API Routes - Core Learning Features

Endpoints:
1. GET /api/v1/conversations/browse - Browse conversations with filters
2. GET /api/v1/conversations/topics - Get topics list
3. GET /api/v1/conversations/limits - Get free-user limits status (auth required)
4. GET /api/v1/conversations/{conversation_id} - Get conversation details
5. GET /api/v1/conversations/{conversation_id}/vocabulary - Get vocabulary & grammar
6. GET /api/v1/conversations/{conversation_id}/gaps - Get all gap exercises (3 levels)
7. GET /api/v1/conversations/{conversation_id}/gaps/{difficulty} - Get single difficulty gap
8. POST /api/v1/conversations/{conversation_id}/gaps/{difficulty}/submit - Submit answers
9. GET /api/v1/conversations/progress - Get user progress
10. GET /api/v1/conversations/{conversation_id}/history - Get single conversation history
11. GET /api/v1/conversations/history - Get all learning history

Free user limits:
- Lifetime: 20 conversations via Learning Path, 15 Beginner / 5 Intermediate / 5 Advanced via Browse
- Daily: 3 gap-fill submissions/day (reset at 00:00 UTC)
- Audio: disabled on locked (over-limit) conversations
- Online Tests: not accessible (Premium only — no points deduction)
Premium (Song OR Conversation subscription):
- Unlimited submissions, full audio, Online Tests free of points
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional, Dict, Any
from datetime import datetime, date
import uuid
import json
import logging
import redis

from src.database.db_manager import DBManager
from src.middleware.firebase_auth import get_current_user, get_current_user_optional

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/v1/conversations", tags=["Conversation Learning"])


# ============================================================================
# DEPENDENCIES
# ============================================================================


def get_db():
    """Get database connection."""
    db_manager = DBManager()
    return db_manager.db


def get_redis():
    """Get Redis client for caching."""
    return redis.Redis(host="redis-server", port=6379, db=0, decode_responses=True)


# Redis TTL constants
STREAK_CACHE_TTL = 3600  # 1 hour - refresh after 1 hour or on each submit


async def check_user_premium(user_id: str, db) -> bool:
    """
    Check if user has active premium subscription.
    Returns True for active Song subscription OR Conversation Learning subscription.
    A Conversation Learning subscription also unlocks Song Learning.
    """
    now = datetime.utcnow()
    if db["user_song_subscription"].find_one(
        {"user_id": user_id, "is_active": True, "end_date": {"$gte": now}}
    ):
        return True
    if db["user_conversation_subscription"].find_one(
        {"user_id": user_id, "is_active": True, "end_date": {"$gte": now}}
    ):
        return True
    return False


async def check_daily_limit(user_id: str, db) -> dict:
    """
    Check user's daily free interaction limit (3 unique conversations/day for free users).
    'Interaction' means playing audio OR submitting gap-fill for a NEW conversation.
    Re-interacting with an already-accessed conversation today is free.

    Returns: Dict with is_premium, daily_used, remaining_free
    """
    is_premium = await check_user_premium(user_id, db)

    if is_premium:
        return {
            "is_premium": True,
            "daily_submits_used": 0,
            "remaining_free": -1,  # Unlimited
        }

    today = date.today().isoformat()
    daily_col = db["user_daily_submits"]

    record = daily_col.find_one({"user_id": user_id, "date": today})
    # New set-based: count unique conversation_ids; fallback to old submit_count for legacy records
    if record and "conversation_ids" in record:
        used = len(record["conversation_ids"])
    else:
        used = record.get("submit_count", 0) if record else 0
    remaining = max(0, 3 - used)

    return {
        "is_premium": False,
        "daily_submits_used": used,
        "remaining_free": remaining,
    }


async def is_conversation_accessed_today(
    user_id: str, conversation_id: str, db
) -> bool:
    """Return True if this conversation was already played/submitted today."""
    today = date.today().isoformat()
    record = db["user_daily_submits"].find_one({"user_id": user_id, "date": today})
    if not record:
        return False
    return conversation_id in record.get("conversation_ids", [])


async def increment_daily_submit(user_id: str, db, conversation_id: str = None):
    """
    Record a free-user interaction with a conversation today.
    Uses $addToSet so play + submit on same conversation only count once.
    """
    is_premium = await check_user_premium(user_id, db)
    if is_premium:
        return

    today = date.today().isoformat()
    daily_col = db["user_daily_submits"]

    update = {
        "$setOnInsert": {"created_at": datetime.utcnow()},
        "$set": {"updated_at": datetime.utcnow()},
    }
    if conversation_id:
        update["$addToSet"] = {"conversation_ids": conversation_id}
    else:
        # Legacy fallback: just increment counter
        update["$inc"] = {"submit_count": 1}

    daily_col.update_one(
        {"user_id": user_id, "date": today},
        update,
        upsert=True,
    )


# Free user lifetime conversation unlock limits per context
FREE_LIFETIME_LIMITS = {
    "learning_path": 20,
    "beginner": 15,
    "intermediate": 5,
    "advanced": 5,
}


async def _get_free_limits(user_id: str, db) -> dict:
    """Return current free_limits counters from user_learning_profile."""
    defaults = {
        "learning_path_unlocked": 0,
        "beginner_unlocked": 0,
        "intermediate_unlocked": 0,
        "advanced_unlocked": 0,
    }
    profile = db["user_learning_profile"].find_one(
        {"user_id": user_id}, {"free_limits": 1}
    )
    if not profile:
        return defaults
    return {**defaults, **profile.get("free_limits", {})}


async def _can_unlock(user_id: str, context: str, db) -> bool:
    """
    Check if a free user can still unlock a new conversation in the given context.
    context: 'learning_path' | 'beginner' | 'intermediate' | 'advanced'
    """
    limits = await _get_free_limits(user_id, db)
    max_allowed = FREE_LIFETIME_LIMITS.get(context, 0)
    current = limits.get(f"{context}_unlocked", 0)
    return current < max_allowed


async def _increment_lifetime_unlock(user_id: str, context: str, db):
    """Increment the lifetime unlock counter for this context (called on first submit)."""
    db["user_learning_profile"].update_one(
        {"user_id": user_id},
        {"$inc": {f"free_limits.{context}_unlocked": 1}},
        upsert=True,
    )


async def update_daily_streak(
    user_id: str,
    score: float,
    activity_type: str,
    activity_id: str,
    db,
    redis_client=None,
):
    """
    Update user's daily learning streak.

    Rules:
        - Count any completed activity regardless of score
        - One learning activity per day maintains streak
        - Multiple activities in same day don't increase streak
        - Streak resets to 1 if previous day was missed
        - Writes to MongoDB + invalidates Redis cache
    """
    from datetime import timedelta

    streak_col = db["user_learning_streak"]
    today = date.today()
    today_str = today.isoformat()
    new_activity = {
        "type": activity_type,
        "id": activity_id,
        "score": score,
        "completed_at": datetime.utcnow(),
    }

    # Check if user already learned today
    existing_today = streak_col.find_one({"user_id": user_id, "date": today_str})

    if existing_today:
        # Already learned today - add activity, update cache
        streak_col.update_one(
            {"user_id": user_id, "date": today_str},
            {
                "$addToSet": {"activities": new_activity},
                "$set": {"updated_at": datetime.utcnow()},
            },
        )
        # Update Redis cache: append the new activity
        if redis_client:
            try:
                cache_key = f"streak:{user_id}"
                cached = redis_client.get(cache_key)
                if cached:
                    data = json.loads(cached)
                    act = dict(new_activity)
                    act["completed_at"] = act["completed_at"].isoformat()
                    data["today_activities"].append(act)
                    data["today_learned"] = True
                    redis_client.setex(cache_key, STREAK_CACHE_TTL, json.dumps(data))
            except Exception:
                pass
        return

    # First activity today - calculate streak
    yesterday_str = (today - timedelta(days=1)).isoformat()

    # Single query: get yesterday + latest in one aggregation
    pipeline = [
        {"$match": {"user_id": user_id, "date": {"$in": [yesterday_str]}}},
        {"$sort": {"date": -1}},
        {"$limit": 1},
    ]
    yesterday_record = streak_col.find_one({"user_id": user_id, "date": yesterday_str})

    if yesterday_record:
        current_streak = yesterday_record.get("current_streak", 1) + 1
        longest_streak = max(yesterday_record.get("longest_streak", 1), current_streak)
    else:
        latest_record = streak_col.find_one({"user_id": user_id}, sort=[("date", -1)])
        current_streak = 1
        longest_streak = latest_record.get("longest_streak", 1) if latest_record else 1

    streak_doc = {
        "streak_id": str(uuid.uuid4()),
        "user_id": user_id,
        "date": today_str,
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "activities": [new_activity],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    streak_col.insert_one(streak_doc)

    # Write new cache
    if redis_client:
        try:
            cache_key = f"streak:{user_id}"
            cache_data = {
                "current_streak": current_streak,
                "longest_streak": longest_streak,
                "today_learned": True,
                "today_activities": [
                    {
                        "type": activity_type,
                        "id": activity_id,
                        "score": score,
                        "completed_at": datetime.utcnow().isoformat(),
                    }
                ],
                "cached_at": today_str,
            }
            redis_client.setex(cache_key, STREAK_CACHE_TTL, json.dumps(cache_data))
        except Exception:
            pass


async def calculate_xp_earned(
    difficulty: str, score: float, is_first_attempt: bool, is_perfect_score: bool
) -> int:
    """
    Calculate XP earned for completing a conversation.

    Base XP:
    - Easy: 5 XP
    - Medium: 10 XP
    - Hard: 15 XP

    Bonuses:
    - Score >= 80%: +3 XP
    - Score >= 90%: +5 XP
    - Score = 100%: +10 XP
    - First attempt pass: +2 XP
    - Daily streak: +2 XP (added separately)
    """
    base_xp = {"easy": 5, "medium": 10, "hard": 15}.get(difficulty, 5)
    bonus_xp = 0

    # Score bonuses
    if is_perfect_score:
        bonus_xp += 10
    elif score >= 90:
        bonus_xp += 5
    elif score >= 80:
        bonus_xp += 3

    # First attempt bonus
    if is_first_attempt and score >= 80:
        bonus_xp += 2

    return base_xp + bonus_xp


async def update_user_xp(
    user_id: str,
    xp_earned: int,
    reason: str,
    conversation_id: str,
    difficulty: str,
    score: float,
    db,
):
    """
    Update user's XP and check for level up.

    Returns: dict with xp info and level up status
    """
    xp_col = db["user_learning_xp"]

    # Get or create user XP record
    user_xp = xp_col.find_one({"user_id": user_id})

    if not user_xp:
        # Create new XP record
        user_xp = {
            "xp_id": str(uuid.uuid4()),
            "user_id": user_id,
            "total_xp": 0,
            "level": 1,
            "level_name": "Novice",
            "xp_history": [],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

    # Add XP
    old_xp = user_xp.get("total_xp", 0)
    new_xp = old_xp + xp_earned
    old_level = user_xp.get("level", 1)

    # Determine new level
    level_thresholds = [
        (0, 1, "Novice"),
        (50, 2, "Learner"),
        (150, 3, "Practitioner"),
        (300, 4, "Proficient"),
        (500, 5, "Advanced"),
        (800, 6, "Expert"),
        (1200, 7, "Master"),
        (2000, 8, "Legend"),
    ]

    new_level = 1
    level_name = "Novice"
    for threshold, level, name in level_thresholds:
        if new_xp >= threshold:
            new_level = level
            level_name = name

    # Add to history
    xp_history_entry = {
        "earned_xp": xp_earned,
        "reason": reason,
        "conversation_id": conversation_id,
        "difficulty": difficulty,
        "score": score,
        "timestamp": datetime.utcnow(),
    }

    # Update database
    xp_col.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "total_xp": new_xp,
                "level": new_level,
                "level_name": level_name,
                "updated_at": datetime.utcnow(),
            },
            "$push": {"xp_history": xp_history_entry},
            "$setOnInsert": {
                "xp_id": str(uuid.uuid4()),
                "user_id": user_id,
                "created_at": datetime.utcnow(),
            },
        },
        upsert=True,
    )

    leveled_up = new_level > old_level

    return {
        "xp_earned": xp_earned,
        "total_xp": new_xp,
        "level": new_level,
        "level_name": level_name,
        "leveled_up": leveled_up,
        "old_level": old_level,
    }


async def check_and_award_achievements(
    user_id: str,
    conversation_id: str,
    score: float,
    difficulty: str,
    db,
):
    """
    Check for new achievements and award them.

    Returns: List of newly earned achievements
    """
    achievements_col = db["user_learning_achievements"]
    progress_col = db["user_conversation_progress"]
    conv_col = db["conversation_library"]

    newly_earned = []

    # Get user's stats
    total_completed = progress_col.count_documents(
        {"user_id": user_id, "is_completed": True}
    )

    # Check completion milestones
    completion_achievements = [
        (1, "first_steps", "First Steps", "completion", 1),
        (5, "getting_started", "Getting Started", "completion", 10),
        (20, "dedicated_learner", "Dedicated Learner", "completion", 25),
        (50, "consistent_practice", "Consistent Practice", "completion", 50),
        (100, "century_club", "Century Club", "completion", 100),
    ]

    for threshold, ach_id, ach_name, ach_type, xp_bonus in completion_achievements:
        if total_completed == threshold:
            # Check if not already earned
            existing = achievements_col.find_one(
                {"user_id": user_id, "achievement_id": ach_id}
            )

            if not existing:
                achievement_doc = {
                    "user_achievement_id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "achievement_id": ach_id,
                    "achievement_name": ach_name,
                    "achievement_type": ach_type,
                    "xp_bonus": xp_bonus,
                    "earned_at": datetime.utcnow(),
                }
                achievements_col.insert_one(achievement_doc)
                newly_earned.append(achievement_doc)

                # Award bonus XP
                await update_user_xp(
                    user_id,
                    xp_bonus,
                    f"Achievement: {ach_name}",
                    conversation_id,
                    difficulty,
                    score,
                    db,
                )

    # Check for perfect score achievement
    if score == 100:
        existing = achievements_col.find_one(
            {"user_id": user_id, "achievement_id": "perfect_score"}
        )

        if not existing:
            achievement_doc = {
                "user_achievement_id": str(uuid.uuid4()),
                "user_id": user_id,
                "achievement_id": "perfect_score",
                "achievement_name": "Perfect Score",
                "achievement_type": "performance",
                "xp_bonus": 20,
                "earned_at": datetime.utcnow(),
            }
            achievements_col.insert_one(achievement_doc)
            newly_earned.append(achievement_doc)

            await update_user_xp(
                user_id,
                20,
                "Achievement: Perfect Score",
                conversation_id,
                difficulty,
                score,
                db,
            )

    # Check for topic mastery
    conv = conv_col.find_one({"conversation_id": conversation_id})
    if conv:
        topic_number = conv["topic_number"]
        level = conv["level"]

        # Get all conversations in this topic
        topic_convs = list(
            conv_col.find(
                {"topic_number": topic_number, "level": level}, {"conversation_id": 1}
            )
        )

        topic_conv_ids = [c["conversation_id"] for c in topic_convs]

        # Check if all completed
        completed_in_topic = progress_col.count_documents(
            {
                "user_id": user_id,
                "conversation_id": {"$in": topic_conv_ids},
                "is_completed": True,
            }
        )

        if completed_in_topic == len(topic_conv_ids):
            ach_id = f"topic_{level}_{topic_number}_master"
            existing = achievements_col.find_one(
                {"user_id": user_id, "achievement_id": ach_id}
            )

            if not existing:
                topic_name = conv["topic"]["en"]
                achievement_doc = {
                    "user_achievement_id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "achievement_id": ach_id,
                    "achievement_name": f"{topic_name} Master",
                    "achievement_type": "topic_mastery",
                    "xp_bonus": 50,
                    "metadata": {
                        "topic_number": topic_number,
                        "level": level,
                        "conversations_completed": len(topic_conv_ids),
                    },
                    "earned_at": datetime.utcnow(),
                }
                achievements_col.insert_one(achievement_doc)
                newly_earned.append(achievement_doc)

                await update_user_xp(
                    user_id,
                    50,
                    f"Achievement: {topic_name} Master",
                    conversation_id,
                    difficulty,
                    score,
                    db,
                )

    return newly_earned


# ============================================================================
# ENDPOINT 1: Browse Conversations
# ============================================================================


@router.get("/browse")
async def browse_conversations(
    level: Optional[str] = None,
    topic: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    current_user: Optional[dict] = Depends(get_current_user_optional),
    db=Depends(get_db),
):
    """
    Browse conversations with filters (PUBLIC - auth optional for premium unlock).

    Query Parameters:
    - level: "beginner" | "intermediate" | "advanced"
    - topic: Topic slug (e.g., "work_office")
    - search: Search term matched against title.en and title.vi (case-insensitive, bilingual)
    - page: Page number (default: 1)
    - page_size: Items per page (default: 20, max: 100)

    Returns: List of conversations with metadata and can_play_audio per item
    """
    # Validate page_size
    if page_size > 100:
        page_size = 100

    # Convert page to skip
    skip = (page - 1) * page_size
    limit = page_size

    # Build filter
    filter_query = {}
    if level:
        if level not in ["beginner", "intermediate", "advanced"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid level. Must be: beginner, intermediate, or advanced",
            )
        filter_query["level"] = level

    if topic:
        filter_query["topic_slug"] = topic

    if search and search.strip():
        regex = {"$regex": search.strip(), "$options": "i"}
        filter_query["$or"] = [
            {"title.en": regex},
            {"title.vi": regex},
        ]

    # Get conversations
    conv_col = db["conversation_library"]

    # Get total count
    total = conv_col.count_documents(filter_query)

    # Get paginated results
    conversations = list(
        conv_col.find(
            filter_query, {"dialogue": 0, "full_text_en": 0, "full_text_vi": 0}
        )
        .sort("conversation_id", 1)
        .skip(skip)
        .limit(limit)
    )

    # Check premium once for all items (avoid N+1 queries)
    is_premium = False
    gap_completed_ids = set()
    if current_user:
        uid = current_user["uid"]
        is_premium = await check_user_premium(uid, db)

        # Batch-fetch which conversations this user has attempted gap exercises for
        # Any progress document = user has done the gap (gap_completed field may be absent
        # for low-score attempts, so we check existence only)
        page_conv_ids = [c["conversation_id"] for c in conversations]
        if page_conv_ids:
            progress_col = db["user_conversation_progress"]
            attempted_docs = progress_col.find(
                {
                    "user_id": uid,
                    "conversation_id": {"$in": page_conv_ids},
                },
                {"conversation_id": 1, "_id": 0},
            )
            gap_completed_ids = {d["conversation_id"] for d in attempted_docs}

    # Format response
    conversation_list = []
    for conv in conversations:
        conv_id = conv["conversation_id"]
        item = {
            "conversation_id": conv_id,
            "level": conv["level"],
            "topic_number": conv["topic_number"],
            "topic_slug": conv["topic_slug"],
            "topic": conv["topic"],
            "title": conv["title"],
            "situation": conv["situation"],
            "turn_count": conv["turn_count"],
            "word_count": conv["word_count"],
            "difficulty_score": conv.get("difficulty_score", 5),
            "has_audio": conv.get("has_audio", False),
            "audio_url": conv.get("audio_url") if is_premium else None,
            "can_play_audio": is_premium,
            "gap_completed": conv_id in gap_completed_ids,
            "difficulties_available": [
                "easy",
                "medium",
                "hard",
            ],  # All have 3 levels
        }
        conversation_list.append(item)

    return {
        "conversations": conversation_list,
        "total": total,
        "page": skip // limit + 1,
        "limit": limit,
    }


# ============================================================================
# ENDPOINT 2: Get Topics List
# ============================================================================


@router.get("/topics")
async def get_topics_list(
    db=Depends(get_db),
):
    """
    Get list of all topics grouped by level with conversation counts (PUBLIC - No authentication required).

    Returns: Topics grouped by beginner/intermediate/advanced
    """
    conv_col = db["conversation_library"]

    # Aggregate topics by level
    pipeline = [
        {
            "$group": {
                "_id": {
                    "level": "$level",
                    "topic_number": "$topic_number",
                    "topic_slug": "$topic_slug",
                    "topic_en": "$topic.en",
                    "topic_vi": "$topic.vi",
                },
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"_id.topic_number": 1}},
    ]

    results = list(conv_col.aggregate(pipeline))

    # Group by level
    levels = {
        "beginner": {"level_number": 1, "topics": []},
        "intermediate": {"level_number": 2, "topics": []},
        "advanced": {"level_number": 3, "topics": []},
    }

    for result in results:
        level = result["_id"]["level"]
        topic_data = {
            "topic_number": result["_id"]["topic_number"],
            "topic_slug": result["_id"]["topic_slug"],
            "topic_en": result["_id"]["topic_en"],
            "topic_vi": result["_id"]["topic_vi"],
            "conversation_count": result["count"],
        }
        levels[level]["topics"].append(topic_data)

    # Calculate counts
    for level_key in levels:
        levels[level_key]["topic_count"] = len(levels[level_key]["topics"])
        levels[level_key]["conversation_count"] = sum(
            t["conversation_count"] for t in levels[level_key]["topics"]
        )

    total_topics = sum(len(v["topics"]) for v in levels.values())

    return {"total_topics": total_topics, "levels": levels}


# ============================================================================
# ENDPOINT 3: Get All Learning History (MUST BE BEFORE /{conversation_id})
# ============================================================================


@router.get("/history")
async def get_all_learning_history(
    level: Optional[str] = None,
    topic: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Get all conversations user has attempted with detailed stats.

    Query Parameters:
    - level: Filter by level
    - topic: Filter by topic
    - page: Page number (1-based)
    - page_size: Items per page (max: 100)

    Returns: Complete learning history with analytics
    """
    user_id = current_user["uid"]

    if page_size > 100:
        page_size = 100

    skip = (page - 1) * page_size

    # Get user's progress records
    progress_col = db["user_conversation_progress"]
    conv_col = db["conversation_library"]

    # Build filter
    progress_filter = {"user_id": user_id}

    # Get all progress records
    all_progress = list(progress_col.find(progress_filter))

    # Get conversation details and filter
    history = []
    for prog in all_progress:
        conv = conv_col.find_one({"conversation_id": prog["conversation_id"]})
        if not conv:
            continue

        # Apply level/topic filters
        if level and conv["level"] != level:
            continue
        if topic and conv["topic_slug"] != topic:
            continue

        # Calculate stats
        best_scores = prog.get("best_scores", {})
        highest_score = 0
        completed_difficulties = []

        for diff in ["easy", "medium", "hard"]:
            if diff in best_scores:
                score = best_scores[diff]["score"]
                if score > highest_score:
                    highest_score = score
                if score >= 80:
                    completed_difficulties.append(diff)

        history.append(
            {
                "conversation_id": prog["conversation_id"],
                "title": conv["title"],
                "level": conv["level"],
                "topic": conv["topic"],
                "topic_slug": conv["topic_slug"],
                "total_attempts": prog.get("total_attempts", 0),
                "total_time_spent": prog.get("total_time_spent", 0),
                "best_scores": best_scores,
                "highest_score": highest_score,
                "completed_difficulties": completed_difficulties,
                "is_completed": prog.get("is_completed", False),
                "first_attempt_at": (
                    prog.get("first_attempt_at").isoformat()
                    if prog.get("first_attempt_at")
                    else None
                ),
                "last_attempt_at": (
                    prog.get("last_attempt_at").isoformat()
                    if prog.get("last_attempt_at")
                    else None
                ),
            }
        )

    # Sort by last attempt (most recent first)
    history.sort(key=lambda x: x["last_attempt_at"] or "", reverse=True)

    # Paginate
    total = len(history)
    paginated = history[skip : skip + page_size]

    return {
        "history": paginated,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ============================================================================
# ENDPOINT 7: Get User Progress
# ============================================================================


@router.get("/progress")
async def get_user_progress(
    level: Optional[str] = None,
    topic: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Get user's conversation learning progress.

    Query Parameters:
    - level: Filter by level
    - topic: Filter by topic

    Returns: Progress statistics, recent attempts, best scores
    """
    user_id = current_user["uid"]

    # Get total conversations
    conv_col = db["conversation_library"]
    total_conversations = conv_col.count_documents({})

    # Get user progress
    progress_col = db["user_conversation_progress"]
    completed = progress_col.count_documents({"user_id": user_id, "is_completed": True})

    completion_rate = (
        round((completed / total_conversations) * 100, 1)
        if total_conversations > 0
        else 0
    )

    # Daily usage
    limit_info = await check_daily_limit(user_id, db)

    # Progress by level
    by_level = {}
    for level_name in ["beginner", "intermediate", "advanced"]:
        level_total = conv_col.count_documents({"level": level_name})
        level_completed = 0
        level_scores = []

        # Get completed conversations for this level
        level_convs = list(conv_col.find({"level": level_name}, {"conversation_id": 1}))
        conv_ids = [c["conversation_id"] for c in level_convs]

        if conv_ids:
            completed_progress = list(
                progress_col.find(
                    {
                        "user_id": user_id,
                        "conversation_id": {"$in": conv_ids},
                        "is_completed": True,
                    }
                )
            )
            level_completed = len(completed_progress)

            # Get average score
            for prog in completed_progress:
                best_scores = prog.get("best_scores", {})
                for difficulty in ["easy", "medium", "hard"]:
                    if difficulty in best_scores:
                        level_scores.append(best_scores[difficulty]["score"])

        avg_score = (
            round(sum(level_scores) / len(level_scores), 1) if level_scores else 0
        )

        by_level[level_name] = {
            "total": level_total,
            "completed": level_completed,
            "completion_rate": (
                round((level_completed / level_total) * 100, 1)
                if level_total > 0
                else 0
            ),
            "avg_score": avg_score,
        }

    # Recent attempts
    attempts_col = db["conversation_attempts"]
    recent_attempts_docs = list(
        attempts_col.find({"user_id": user_id}).sort("completed_at", -1).limit(10)
    )

    recent_attempts = []
    for attempt in recent_attempts_docs:
        # Get conversation details
        conv = conv_col.find_one({"conversation_id": attempt["conversation_id"]})
        if conv:
            recent_attempts.append(
                {
                    "conversation_id": attempt["conversation_id"],
                    "title": conv["title"],
                    "difficulty": attempt["difficulty"],
                    "score": attempt["score"],
                    "time_spent": attempt["time_spent"],
                    "completed_at": attempt["completed_at"].isoformat(),
                    "is_passed": attempt["is_passed"],
                }
            )

    # Best scores
    best_scores_docs = list(
        progress_col.find({"user_id": user_id, "is_completed": True})
        .sort("best_scores.easy.score", -1)
        .limit(10)
    )

    best_scores = []
    for prog in best_scores_docs:
        conv = conv_col.find_one({"conversation_id": prog["conversation_id"]})
        if conv:
            # Find highest score across all difficulties
            all_scores = []
            best_difficulty = None
            best_score_value = 0

            for difficulty in ["easy", "medium", "hard"]:
                if difficulty in prog.get("best_scores", {}):
                    score_data = prog["best_scores"][difficulty]
                    if score_data["score"] > best_score_value:
                        best_score_value = score_data["score"]
                        best_difficulty = difficulty
                        completed_at = score_data["completed_at"]

            if best_difficulty:
                best_scores.append(
                    {
                        "conversation_id": prog["conversation_id"],
                        "title": conv["title"],
                        "difficulty": best_difficulty,
                        "score": best_score_value,
                        "completed_at": completed_at.isoformat(),
                    }
                )

    # Phase 1: dual-part completion stats
    gap_only_completed = progress_col.count_documents(
        {"user_id": user_id, "gap_completed": True, "test_completed": {"$ne": True}}
    )
    fully_completed = progress_col.count_documents(
        {"user_id": user_id, "gap_completed": True, "test_completed": True}
    )
    # Completion by gap difficulty (only passed gaps)
    completion_by_difficulty = {}
    for diff in ["easy", "medium", "hard"]:
        completion_by_difficulty[diff] = progress_col.count_documents(
            {"user_id": user_id, "gap_completed": True, "gap_difficulty": diff}
        )

    # Phase 3: progression level data
    _progression_names = {1: "Initiate", 2: "Scholar", 3: "Addict"}
    _profile = db["user_learning_profile"].find_one({"user_id": user_id})
    if _profile:
        _prog_level = _profile.get("progression_level", 1)
        progression_block = {
            "level": _prog_level,
            "level_name": _progression_names.get(_prog_level, "Initiate"),
            "l1_completed": _profile.get("l1_completed", 0),
            "l1_songs_completed": _profile.get("l1_songs_completed", 0),
            "l2_completed": _profile.get("l2_completed", 0),
            "l2_songs_completed": _profile.get("l2_songs_completed", 0),
            "l3_completed": _profile.get("l3_completed", 0),
            "l3_songs_completed": _profile.get("l3_songs_completed", 0),
        }
    else:
        progression_block = None

    return {
        "total_conversations": total_conversations,
        "total_completed": completed,
        "completion_rate": completion_rate,
        "daily_limit": (
            limit_info.get("remaining_free", -1) if not limit_info["is_premium"] else -1
        ),
        "used_today": limit_info.get("conversations_played_today", 0),
        "remaining_today": limit_info.get("remaining_free", -1),
        "reset_at": datetime.combine(date.today(), datetime.min.time()).isoformat()
        + "Z",
        "by_level": by_level,
        "recent_attempts": recent_attempts,
        "best_scores": best_scores,
        # Phase 1 dual-part stats
        "dual_part": {
            "fully_completed": fully_completed,  # gap + test both done
            "gap_only_completed": gap_only_completed,  # gap done, test pending
            "completion_by_difficulty": completion_by_difficulty,
        },
        # Phase 3 progression stats
        "progression": progression_block,
    }


# ============================================================================
# ENDPOINT 10: Get Saved Conversations
# ============================================================================


@router.get("/saved")
async def get_saved_conversations(
    level: Optional[str] = None,
    topic: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Get user's bookmarked/saved conversations.

    Query Parameters:
    - level: Filter by level
    - topic: Filter by topic
    - skip: Pagination offset
    - limit: Page size (max: 100)

    Returns: List of saved conversations
    """
    user_id = current_user["uid"]

    if limit > 100:
        limit = 100

    # Get saved conversations
    saved_col = db["user_conversation_saved"]
    conv_col = db["conversation_library"]

    # Build filter
    saved_filter = {"user_id": user_id}

    # Get all saved records
    saved_docs = list(saved_col.find(saved_filter).sort("saved_at", -1))

    # Get conversation details
    saved_list = []
    for saved in saved_docs:
        conv = conv_col.find_one({"conversation_id": saved["conversation_id"]})
        if not conv:
            continue

        # Apply filters
        if level and conv["level"] != level:
            continue
        if topic and conv["topic_slug"] != topic:
            continue

        saved_list.append(
            {
                "conversation_id": saved["conversation_id"],
                "title": conv["title"],
                "level": conv["level"],
                "topic": conv["topic"],
                "topic_slug": conv["topic_slug"],
                "situation": conv["situation"],
                "turn_count": conv["turn_count"],
                "word_count": conv["word_count"],
                "saved_at": saved["saved_at"].isoformat(),
                "notes": saved.get("notes"),
                "tags": saved.get("tags", []),
            }
        )

    # Paginate
    total = len(saved_list)
    paginated = saved_list[skip : skip + limit]

    return {
        "saved": paginated,
        "total": total,
        "page": skip // limit + 1,
        "limit": limit,
    }


# ============================================================================
# ENDPOINT 13: Get Topic Analytics
# ============================================================================


@router.get("/analytics/topics")
async def get_topic_analytics(
    level: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Get analytics grouped by topics.

    Query Parameters:
    - level: Filter by level (optional)

    Returns: Detailed stats for each topic
    """
    user_id = current_user["uid"]

    conv_col = db["conversation_library"]
    progress_col = db["user_conversation_progress"]
    attempts_col = db["conversation_attempts"]

    # Get all topics
    pipeline = [
        {
            "$group": {
                "_id": {
                    "topic_number": "$topic_number",
                    "topic_slug": "$topic_slug",
                    "topic_en": "$topic.en",
                    "topic_vi": "$topic.vi",
                    "level": "$level",
                },
                "total_conversations": {"$sum": 1},
            }
        },
        {"$sort": {"_id.topic_number": 1}},
    ]

    if level:
        pipeline.insert(0, {"$match": {"level": level}})

    topics = list(conv_col.aggregate(pipeline))

    # Calculate stats for each topic
    topic_stats = []

    for topic in topics:
        topic_info = topic["_id"]
        total_convs = topic["total_conversations"]

        # Get conversations in this topic
        topic_convs = list(
            conv_col.find(
                {
                    "topic_number": topic_info["topic_number"],
                    "level": topic_info["level"],
                },
                {"conversation_id": 1},
            )
        )

        conv_ids = [c["conversation_id"] for c in topic_convs]

        # Get user's progress for this topic
        topic_progress = list(
            progress_col.find(
                {"user_id": user_id, "conversation_id": {"$in": conv_ids}}
            )
        )

        completed = sum(1 for p in topic_progress if p.get("is_completed", False))

        # Get all attempts for this topic
        topic_attempts = list(
            attempts_col.find(
                {"user_id": user_id, "conversation_id": {"$in": conv_ids}}
            )
        )

        total_attempts = len(topic_attempts)
        avg_score = (
            sum(a["score"] for a in topic_attempts) / total_attempts
            if total_attempts > 0
            else 0
        )
        total_time = sum(p.get("total_time_spent", 0) for p in topic_progress)

        # Best conversation in this topic
        best_conv = None
        best_score = 0

        for prog in topic_progress:
            for diff in ["easy", "medium", "hard"]:
                if diff in prog.get("best_scores", {}):
                    score = prog["best_scores"][diff]["score"]
                    if score > best_score:
                        best_score = score
                        conv = conv_col.find_one(
                            {"conversation_id": prog["conversation_id"]}
                        )
                        if conv:
                            best_conv = {
                                "conversation_id": prog["conversation_id"],
                                "title": conv["title"],
                                "score": score,
                                "difficulty": diff,
                            }

        topic_stats.append(
            {
                "topic_number": topic_info["topic_number"],
                "topic_slug": topic_info["topic_slug"],
                "topic": {"en": topic_info["topic_en"], "vi": topic_info["topic_vi"]},
                "level": topic_info["level"],
                "total_conversations": total_convs,
                "completed": completed,
                "completion_rate": (
                    round((completed / total_convs) * 100, 1) if total_convs > 0 else 0
                ),
                "total_attempts": total_attempts,
                "avg_score": round(avg_score, 1),
                "total_time_spent": total_time,
                "best_conversation": best_conv,
            }
        )

    return {"topics": topic_stats, "total_topics": len(topic_stats)}


# ============================================================================
# ENDPOINT 14: Get Overall Analytics
# ============================================================================


@router.get("/analytics/overview")
async def get_overall_analytics(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Get overall learning analytics including XP, streaks, achievements.

    Returns: Comprehensive analytics dashboard data
    """
    user_id = current_user["uid"]

    conv_col = db["conversation_library"]
    progress_col = db["user_conversation_progress"]
    attempts_col = db["conversation_attempts"]

    # Overall stats
    total_conversations = conv_col.count_documents({})
    user_progress = list(progress_col.find({"user_id": user_id}))
    total_completed = sum(1 for p in user_progress if p.get("is_completed", False))

    # All attempts
    all_attempts = list(attempts_col.find({"user_id": user_id}))
    total_attempts = len(all_attempts)
    total_time_spent = sum(p.get("total_time_spent", 0) for p in user_progress)

    # Average score
    avg_score = (
        sum(a["score"] for a in all_attempts) / total_attempts
        if total_attempts > 0
        else 0
    )

    # Stats by difficulty
    difficulty_stats = {
        "easy": {"completed": 0, "attempts": 0, "avg_score": 0, "scores": []},
        "medium": {"completed": 0, "attempts": 0, "avg_score": 0, "scores": []},
        "hard": {"completed": 0, "attempts": 0, "avg_score": 0, "scores": []},
    }

    for attempt in all_attempts:
        diff = attempt["difficulty"]
        difficulty_stats[diff]["attempts"] += 1
        difficulty_stats[diff]["scores"].append(attempt["score"])
        if attempt["is_passed"]:
            difficulty_stats[diff]["completed"] += 1

    for diff in ["easy", "medium", "hard"]:
        scores = difficulty_stats[diff]["scores"]
        if scores:
            difficulty_stats[diff]["avg_score"] = round(sum(scores) / len(scores), 1)

    # Stats by level
    level_stats = {}
    for level_name in ["beginner", "intermediate", "advanced"]:
        level_total = conv_col.count_documents({"level": level_name})
        level_convs = list(conv_col.find({"level": level_name}, {"conversation_id": 1}))
        level_conv_ids = [c["conversation_id"] for c in level_convs]

        level_progress = [
            p for p in user_progress if p["conversation_id"] in level_conv_ids
        ]
        level_completed = sum(1 for p in level_progress if p.get("is_completed", False))

        level_attempts = [
            a for a in all_attempts if a["conversation_id"] in level_conv_ids
        ]
        level_avg_score = (
            sum(a["score"] for a in level_attempts) / len(level_attempts)
            if level_attempts
            else 0
        )

        level_stats[level_name] = {
            "total": level_total,
            "completed": level_completed,
            "completion_rate": (
                round((level_completed / level_total) * 100, 1)
                if level_total > 0
                else 0
            ),
            "attempts": len(level_attempts),
            "avg_score": round(level_avg_score, 1),
        }

    # Weak areas (POS with low accuracy)
    pos_stats = {}
    for attempt in all_attempts:
        for gap_result in attempt.get("gap_results", []):
            pos = gap_result["pos_tag"]
            if pos not in pos_stats:
                pos_stats[pos] = {"correct": 0, "total": 0}
            pos_stats[pos]["total"] += 1
            if gap_result["is_correct"]:
                pos_stats[pos]["correct"] += 1

    weak_areas = []
    for pos, stats in pos_stats.items():
        accuracy = (
            (stats["correct"] / stats["total"]) * 100 if stats["total"] > 0 else 0
        )
        if accuracy < 70 and stats["total"] >= 10:  # At least 10 attempts
            weak_areas.append(
                {
                    "pos_tag": pos,
                    "accuracy": round(accuracy, 1),
                    "total_attempts": stats["total"],
                    "correct": stats["correct"],
                }
            )

    weak_areas.sort(key=lambda x: x["accuracy"])

    # Recent activity (last 7 days)
    from datetime import timedelta

    seven_days_ago = datetime.utcnow() - timedelta(days=7)

    recent_attempts = [a for a in all_attempts if a["completed_at"] >= seven_days_ago]
    recent_by_day = {}

    for attempt in recent_attempts:
        day = attempt["completed_at"].date().isoformat()
        if day not in recent_by_day:
            recent_by_day[day] = {"count": 0, "avg_score": 0, "scores": []}
        recent_by_day[day]["count"] += 1
        recent_by_day[day]["scores"].append(attempt["score"])

    for day in recent_by_day:
        scores = recent_by_day[day]["scores"]
        recent_by_day[day]["avg_score"] = round(sum(scores) / len(scores), 1)
        del recent_by_day[day]["scores"]

    # Performance trend
    trend = "stable"
    if len(recent_by_day) >= 2:
        days_sorted = sorted(recent_by_day.keys())
        first_half = days_sorted[: len(days_sorted) // 2]
        second_half = days_sorted[len(days_sorted) // 2 :]

        first_avg = sum(recent_by_day[d]["avg_score"] for d in first_half) / len(
            first_half
        )
        second_avg = sum(recent_by_day[d]["avg_score"] for d in second_half) / len(
            second_half
        )

        if second_avg > first_avg + 5:
            trend = "improving"
        elif second_avg < first_avg - 5:
            trend = "declining"

    # Daily limit info
    limit_info = await check_daily_limit(user_id, db)

    return {
        "overall": {
            "total_conversations": total_conversations,
            "total_completed": total_completed,
            "completion_rate": (
                round((total_completed / total_conversations) * 100, 1)
                if total_conversations > 0
                else 0
            ),
            "total_attempts": total_attempts,
            "total_time_spent": total_time_spent,
            "avg_score": round(avg_score, 1),
            "is_premium": limit_info["is_premium"],
            "daily_limit": (
                limit_info.get("remaining_free", -1)
                if not limit_info["is_premium"]
                else -1
            ),
        },
        "by_level": level_stats,
        "by_difficulty": {
            diff: {
                "completed": stats["completed"],
                "attempts": stats["attempts"],
                "avg_score": stats["avg_score"],
            }
            for diff, stats in difficulty_stats.items()
        },
        "weak_areas": weak_areas,
        "recent_activity": {"days": recent_by_day, "trend": trend},
    }


# ============================================================================
# ENDPOINT 15: Get Learning Path Recommendation
# ============================================================================


@router.get("/learning-path")
async def get_learning_path(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Get recommended next conversation based on user progress.

    Algorithm:
    1. Start with Beginner Topic 1 if no progress
    2. Continue current topic until 80% complete
    3. Move to next topic in sequence
    4. Suggest Easy → Medium → Hard progression

    Returns: Recommended conversation with reasoning
    """
    user_id = current_user["uid"]

    # Phase 3: if user has a smart learning path, redirect to /learning-path/today
    _lp_profile = db["user_learning_profile"].find_one(
        {"user_id": user_id}, projection={"active_path_id": 1}
    )
    if _lp_profile and _lp_profile.get("active_path_id"):
        return {
            "has_smart_path": True,
            "redirect_to": "/api/v1/learning-path/today",
            "message": (
                "You have a personalized learning path. "
                "Use /api/v1/learning-path/today for your daily assignments."
            ),
        }

    conv_col = db["conversation_library"]
    progress_col = db["user_conversation_progress"]

    # Get user's progress
    user_progress = list(progress_col.find({"user_id": user_id}))

    # If no progress, start with Topic 1, Easy
    if not user_progress:
        first_conv = conv_col.find_one(
            {"level": "beginner", "topic_number": 1}, sort=[("conversation_id", 1)]
        )

        if first_conv:
            return {
                "recommendation": {
                    "conversation_id": first_conv["conversation_id"],
                    "title": first_conv["title"],
                    "level": first_conv["level"],
                    "topic": first_conv["topic"],
                    "topic_number": first_conv["topic_number"],
                    "difficulty": "easy",
                    "reason": "Start your learning journey with greetings and introductions!",
                },
                "progress_context": {
                    "current_level": "beginner",
                    "current_topic": 1,
                    "completed_conversations": 0,
                    "recommended_difficulty": "easy",
                },
            }

    # Find current level and topic
    completed_by_level = {"beginner": 0, "intermediate": 0, "advanced": 0}

    for prog in user_progress:
        conv = conv_col.find_one({"conversation_id": prog["conversation_id"]})
        if conv and prog.get("is_completed", False):
            completed_by_level[conv["level"]] += 1

    # Determine current level
    current_level = "beginner"
    if completed_by_level["beginner"] >= 150:  # 62% of 242
        current_level = "intermediate"
    if completed_by_level["intermediate"] >= 180:  # 58% of 310
        current_level = "advanced"

    # Find incomplete conversations in current level
    all_convs_in_level = list(
        conv_col.find({"level": current_level})
        .sort("topic_number", 1)
        .sort("conversation_id", 1)
    )

    completed_ids = {
        p["conversation_id"] for p in user_progress if p.get("is_completed", False)
    }

    # Find next conversation
    for conv in all_convs_in_level:
        if conv["conversation_id"] not in completed_ids:
            # Determine recommended difficulty
            conv_progress = next(
                (
                    p
                    for p in user_progress
                    if p["conversation_id"] == conv["conversation_id"]
                ),
                None,
            )

            recommended_diff = "easy"
            reason = f"Continue with {conv['topic']['en']} topic"

            if conv_progress:
                best_scores = conv_progress.get("best_scores", {})
                if "easy" in best_scores and best_scores["easy"]["score"] >= 80:
                    recommended_diff = "medium"
                    reason = "You passed Easy, try Medium difficulty!"
                if "medium" in best_scores and best_scores["medium"]["score"] >= 80:
                    recommended_diff = "hard"
                    reason = "Challenge yourself with Hard difficulty!"

            return {
                "recommendation": {
                    "conversation_id": conv["conversation_id"],
                    "title": conv["title"],
                    "level": conv["level"],
                    "topic": conv["topic"],
                    "topic_number": conv["topic_number"],
                    "difficulty": recommended_diff,
                    "reason": reason,
                },
                "progress_context": {
                    "current_level": current_level,
                    "current_topic": conv["topic_number"],
                    "completed_conversations": len(completed_ids),
                    "recommended_difficulty": recommended_diff,
                    "level_completion": {
                        "beginner": f"{completed_by_level['beginner']}/242",
                        "intermediate": f"{completed_by_level['intermediate']}/310",
                        "advanced": f"{completed_by_level['advanced']}/24",
                    },
                },
            }

    # All conversations completed!
    return {
        "recommendation": None,
        "message": "🎉 Congratulations! You have completed all conversations!",
        "progress_context": {
            "current_level": "completed",
            "completed_conversations": len(completed_ids),
            "level_completion": {
                "beginner": f"{completed_by_level['beginner']}/242",
                "intermediate": f"{completed_by_level['intermediate']}/310",
                "advanced": f"{completed_by_level['advanced']}/24",
            },
        },
    }


# ============================================================================
# ENDPOINT: Get Daily Streak
# ============================================================================


@router.get("/streak")
async def get_daily_streak(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
    redis_client=Depends(get_redis),
):
    """
    Get user's daily learning streak information.
    Uses Redis cache (TTL 1h). Falls back to MongoDB if cache miss.
    Cache is invalidated/updated on every submit.
    """
    from datetime import timedelta

    user_id = current_user["uid"]
    streak_col = db["user_learning_streak"]
    today = date.today()
    today_str = today.isoformat()

    current_streak = 0
    longest_streak = 0
    today_learned = False
    today_activities = []

    # ── 1. Try Redis cache first ──────────────────────────────────────────
    cache_key = f"streak:{user_id}"
    try:
        cached = redis_client.get(cache_key)
        if cached:
            data = json.loads(cached)
            # Cache is valid only if it was built today
            if data.get("cached_at") == today_str:
                current_streak = data.get("current_streak", 0)
                longest_streak = data.get("longest_streak", 0)
                today_learned = data.get("today_learned", False)
                today_activities = data.get("today_activities", [])
            else:
                # Stale cache from a previous day - discard
                redis_client.delete(cache_key)
                cached = None
    except Exception:
        cached = None

    # ── 2. Cache miss → query MongoDB ────────────────────────────────────
    if not cached:
        today_record = streak_col.find_one({"user_id": user_id, "date": today_str})
        latest_record = (
            streak_col.find_one({"user_id": user_id}, sort=[("date", -1)])
            if not today_record
            else None
        )

        if today_record:
            current_streak = today_record.get("current_streak", 1)
            longest_streak = today_record.get("longest_streak", 1)
            today_learned = True
            raw_activities = today_record.get("activities", [])
            today_activities = [
                {
                    **a,
                    "completed_at": (
                        a["completed_at"].isoformat()
                        if isinstance(a.get("completed_at"), datetime)
                        else a.get("completed_at")
                    ),
                }
                for a in raw_activities
            ]
        elif latest_record:
            latest_date = latest_record.get("date")
            yesterday = (today - timedelta(days=1)).isoformat()
            current_streak = (
                latest_record.get("current_streak", 1)
                if latest_date == yesterday
                else 0
            )
            longest_streak = latest_record.get("longest_streak", 1)

        # Write to cache
        try:
            cache_data = {
                "current_streak": current_streak,
                "longest_streak": longest_streak,
                "today_learned": today_learned,
                "today_activities": today_activities,
                "cached_at": today_str,
            }
            redis_client.setex(cache_key, STREAK_CACHE_TTL, json.dumps(cache_data))
        except Exception:
            pass

    # ── 3. Build last_7_days from MongoDB (single query) ─────────────────
    seven_days_ago = (today - timedelta(days=6)).isoformat()
    records_7d = {
        r["date"]: r
        for r in streak_col.find(
            {"user_id": user_id, "date": {"$gte": seven_days_ago}},
            {"date": 1, "activities": 1},
        )
    }

    last_7_days = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_str = day.isoformat()
        rec = records_7d.get(day_str)
        last_7_days.append(
            {
                "date": day_str,
                "day_of_week": day.strftime("%A"),
                "learned": rec is not None,
                "activity_count": len(rec.get("activities", [])) if rec else 0,
            }
        )

    # ── 4. Streak badge ──────────────────────────────────────────────────
    streak_status = {
        "title": "New Learner",
        "emoji": "",
        "description": "Complete your first day of learning!",
    }
    if current_streak >= 100:
        streak_status = {
            "title": "Legend",
            "emoji": "🔥🔥🔥🔥🔥🔥🔥",
            "description": "100 day streak! You're unstoppable!",
        }
    elif current_streak >= 60:
        streak_status = {
            "title": "Unstoppable",
            "emoji": "🔥🔥🔥🔥🔥🔥",
            "description": "60 day streak! You're on fire!",
        }
    elif current_streak >= 30:
        streak_status = {
            "title": "Monthly Master",
            "emoji": "🔥🔥🔥🔥🔥",
            "description": "30 day streak!",
        }
    elif current_streak >= 14:
        streak_status = {
            "title": "Fortnight Champion",
            "emoji": "🔥🔥🔥🔥",
            "description": "14 day streak!",
        }
    elif current_streak >= 7:
        streak_status = {
            "title": "Week Warrior",
            "emoji": "🔥🔥🔥",
            "description": "7 day streak! Keep it up!",
        }
    elif current_streak >= 3:
        streak_status = {
            "title": "Building Momentum",
            "emoji": "🔥🔥",
            "description": "3 day streak!",
        }
    elif current_streak >= 1:
        streak_status = {
            "title": "Getting Started",
            "emoji": "🔥",
            "description": "Great start! Come back tomorrow!",
        }

    return {
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "today_learned": today_learned,
        "today_activities": today_activities,
        "streak_status": streak_status,
        "last_7_days": last_7_days,
        "note": "Complete at least 1 learning activity per day to maintain streak",
    }


# ============================================================================
# ENDPOINT: Get User XP
# ============================================================================


@router.get("/xp")
async def get_user_xp(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Get user's XP (Experience Points) information.

    Returns:
    - total_xp: Total XP earned
    - level: Current level (1-8)
    - level_name: Level name (Novice, Learner, ... Legend)
    - xp_to_next_level: XP needed to reach next level
    - xp_progress_percentage: Progress to next level (%)
    - recent_xp_history: Last 10 XP earnings
    """
    user_id = current_user["uid"]
    xp_col = db["user_learning_xp"]

    user_xp = xp_col.find_one({"user_id": user_id})

    if not user_xp:
        # New user - return default
        return {
            "total_xp": 0,
            "level": 1,
            "level_name": "Novice",
            "xp_to_next_level": 50,
            "xp_progress_percentage": 0,
            "level_thresholds": [
                {"level": 1, "name": "Novice", "min_xp": 0},
                {"level": 2, "name": "Learner", "min_xp": 50},
                {"level": 3, "name": "Practitioner", "min_xp": 150},
                {"level": 4, "name": "Proficient", "min_xp": 300},
                {"level": 5, "name": "Advanced", "min_xp": 500},
                {"level": 6, "name": "Expert", "min_xp": 800},
                {"level": 7, "name": "Master", "min_xp": 1200},
                {"level": 8, "name": "Legend", "min_xp": 2000},
            ],
            "recent_xp_history": [],
        }

    total_xp = user_xp.get("total_xp", 0)
    level = user_xp.get("level", 1)
    level_name = user_xp.get("level_name", "Novice")

    # Calculate XP to next level
    level_thresholds = [
        (0, 1, "Novice"),
        (50, 2, "Learner"),
        (150, 3, "Practitioner"),
        (300, 4, "Proficient"),
        (500, 5, "Advanced"),
        (800, 6, "Expert"),
        (1200, 7, "Master"),
        (2000, 8, "Legend"),
    ]

    current_level_xp = 0
    next_level_xp = None

    for i, (threshold, lvl, name) in enumerate(level_thresholds):
        if lvl == level:
            current_level_xp = threshold
            if i + 1 < len(level_thresholds):
                next_level_xp = level_thresholds[i + 1][0]
            break

    if next_level_xp:
        xp_to_next = next_level_xp - total_xp
        xp_progress = total_xp - current_level_xp
        xp_needed = next_level_xp - current_level_xp
        progress_percentage = round((xp_progress / xp_needed) * 100, 1)
    else:
        # Max level
        xp_to_next = 0
        progress_percentage = 100

    # Get recent XP history (last 10)
    xp_history = user_xp.get("xp_history", [])
    recent_history = sorted(
        xp_history, key=lambda x: x.get("timestamp", datetime.min), reverse=True
    )[:10]

    # Format history for response
    formatted_history = []
    for entry in recent_history:
        formatted_history.append(
            {
                "earned_xp": entry.get("earned_xp", 0),
                "reason": entry.get("reason", ""),
                "conversation_id": entry.get("conversation_id"),
                "timestamp": (
                    entry.get("timestamp").isoformat()
                    if entry.get("timestamp")
                    else None
                ),
            }
        )

    # Phase 3: progression level data
    _prog_names = {1: "Initiate", 2: "Scholar", 3: "Addict"}
    _profile = db["user_learning_profile"].find_one({"user_id": user_id})
    if _profile:
        _prog_level = _profile.get("progression_level", 1)
        _lk = f"l{_prog_level}"
        _convs_done = _profile.get(f"{_lk}_completed", 0)
        _songs_done = _profile.get(f"{_lk}_songs_completed", 0)
        progression_data = {
            "progression_level": _prog_level,
            "progression_level_name": _prog_names.get(_prog_level, "Initiate"),
            "progression_progress": {
                "conversations_completed": _convs_done,
                "conversations_required": 100,
                "conversations_remaining": max(0, 100 - _convs_done),
                "songs_completed": _songs_done,
                "songs_required": 10,
                "songs_remaining": max(0, 10 - _songs_done),
            },
        }
    else:
        progression_data = {
            "progression_level": None,
            "progression_level_name": None,
            "progression_progress": None,
        }

    return {
        "total_xp": total_xp,
        "level": level,
        "level_name": level_name,
        "xp_to_next_level": xp_to_next if next_level_xp else 0,
        "xp_progress_percentage": progress_percentage,
        "level_thresholds": [
            {"level": lvl, "name": name, "min_xp": threshold}
            for threshold, lvl, name in level_thresholds
        ],
        "recent_xp_history": formatted_history,
        **progression_data,
    }


# ============================================================================
# ENDPOINT: Get User Achievements
# ============================================================================


@router.get("/achievements")
async def get_user_achievements(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Get user's earned achievements and available achievements.

    Returns:
    - total_achievements: Total earned
    - total_xp_from_achievements: Total bonus XP from achievements
    - earned: List of earned achievements
    - progress: Progress toward unearned achievements
    """
    user_id = current_user["uid"]
    achievements_col = db["user_learning_achievements"]
    progress_col = db["user_conversation_progress"]
    conv_col = db["conversation_library"]

    # Get earned achievements
    earned_achievements = list(
        achievements_col.find({"user_id": user_id}).sort("earned_at", -1)
    )

    # Format earned achievements
    formatted_earned = []
    total_xp_bonus = 0

    for ach in earned_achievements:
        total_xp_bonus += ach.get("xp_bonus", 0)
        formatted_earned.append(
            {
                "achievement_id": ach["achievement_id"],
                "achievement_name": ach["achievement_name"],
                "achievement_type": ach["achievement_type"],
                "xp_bonus": ach.get("xp_bonus", 0),
                "earned_at": ach["earned_at"].isoformat(),
                "metadata": ach.get("metadata", {}),
            }
        )

    # Calculate progress toward unearned achievements
    total_completed = progress_col.count_documents(
        {"user_id": user_id, "is_completed": True}
    )

    # Completion achievements progress
    completion_achievements = [
        {"id": "first_steps", "name": "First Steps", "threshold": 1, "xp": 1},
        {"id": "getting_started", "name": "Getting Started", "threshold": 5, "xp": 10},
        {
            "id": "dedicated_learner",
            "name": "Dedicated Learner",
            "threshold": 20,
            "xp": 25,
        },
        {
            "id": "consistent_practice",
            "name": "Consistent Practice",
            "threshold": 50,
            "xp": 50,
        },
        {"id": "century_club", "name": "Century Club", "threshold": 100, "xp": 100},
    ]

    progress_info = []
    earned_ids = {ach["achievement_id"] for ach in earned_achievements}

    for ach_def in completion_achievements:
        if ach_def["id"] not in earned_ids:
            progress_info.append(
                {
                    "achievement_id": ach_def["id"],
                    "achievement_name": ach_def["name"],
                    "achievement_type": "completion",
                    "xp_bonus": ach_def["xp"],
                    "current": min(total_completed, ach_def["threshold"]),
                    "required": ach_def["threshold"],
                    "progress_percentage": min(
                        round((total_completed / ach_def["threshold"]) * 100, 1), 100
                    ),
                }
            )

    # Topic mastery progress
    # Get topics where user has some progress
    user_convs = list(progress_col.find({"user_id": user_id, "is_completed": True}))
    user_conv_ids = [p["conversation_id"] for p in user_convs]

    if user_conv_ids:
        # Group by topic
        topics_progress = {}
        for conv_id in user_conv_ids:
            conv = conv_col.find_one({"conversation_id": conv_id})
            if conv:
                key = f"{conv['level']}_{conv['topic_number']}"
                if key not in topics_progress:
                    topics_progress[key] = {
                        "level": conv["level"],
                        "topic_number": conv["topic_number"],
                        "topic_name": conv["topic"]["en"],
                        "completed": 0,
                        "total": 0,
                    }
                topics_progress[key]["completed"] += 1

        # Get totals for each topic
        for key, info in topics_progress.items():
            total_in_topic = conv_col.count_documents(
                {"level": info["level"], "topic_number": info["topic_number"]}
            )
            info["total"] = total_in_topic

            # Check if achievement earned
            ach_id = f"topic_{info['level']}_{info['topic_number']}_master"
            if ach_id not in earned_ids and info["completed"] < info["total"]:
                progress_info.append(
                    {
                        "achievement_id": ach_id,
                        "achievement_name": f"{info['topic_name']} Master",
                        "achievement_type": "topic_mastery",
                        "xp_bonus": 50,
                        "current": info["completed"],
                        "required": info["total"],
                        "progress_percentage": round(
                            (info["completed"] / info["total"]) * 100, 1
                        ),
                        "metadata": {
                            "topic_number": info["topic_number"],
                            "level": info["level"],
                        },
                    }
                )

    # Phase 3: progression achievements
    _prog_profile = db["user_learning_profile"].find_one({"user_id": user_id})
    if _prog_profile:
        _prog_achievements = [
            {
                "id": "level_1_initiate",
                "name": "Initiate",
                "convs_key": "l1_completed",
                "songs_key": "l1_songs_completed",
                "xp": 200,
            },
            {
                "id": "level_2_scholar",
                "name": "Scholar",
                "convs_key": "l2_completed",
                "songs_key": "l2_songs_completed",
                "xp": 500,
            },
            {
                "id": "level_3_addict",
                "name": "Addict",
                "convs_key": "l3_completed",
                "songs_key": "l3_songs_completed",
                "xp": 1000,
            },
        ]
        for pa in _prog_achievements:
            if pa["id"] not in earned_ids:
                _c = _prog_profile.get(pa["convs_key"], 0)
                _s = _prog_profile.get(pa["songs_key"], 0)
                _pct = round(min(_c / 100, 1.0) * 60 + min(_s / 10, 1.0) * 40, 1)
                progress_info.append(
                    {
                        "achievement_id": pa["id"],
                        "achievement_name": pa["name"],
                        "achievement_type": "progression",
                        "xp_bonus": pa["xp"],
                        "current_conversations": _c,
                        "required_conversations": 100,
                        "current_songs": _s,
                        "required_songs": 10,
                        "progress_percentage": _pct,
                    }
                )

    return {
        "total_achievements": len(earned_achievements),
        "total_xp_from_achievements": total_xp_bonus,
        "earned": formatted_earned,
        "in_progress": progress_info,
    }


# ============================================================================
# ENDPOINT: Get Free User Limits
# ============================================================================


@router.get("/limits")
async def get_user_limits(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Get current free-tier usage limits for the authenticated user.
    Premium users receive unlimited=True with no counters.

    Returns: Lifetime unlock counts, daily submit count, and reset time.
    """
    from datetime import timedelta

    user_id = current_user["uid"]
    is_premium = await check_user_premium(user_id, db)

    if is_premium:
        return {
            "is_premium": True,
            "unlimited": True,
        }

    free_limits = await _get_free_limits(user_id, db)
    today = date.today().isoformat()
    record = db["user_daily_submits"].find_one({"user_id": user_id, "date": today})
    # New set-based: count unique conversation_ids; fallback to submit_count for legacy
    if record and "conversation_ids" in record:
        daily_used = len(record["conversation_ids"])
    else:
        daily_used = record.get("submit_count", 0) if record else 0

    # Calculate UTC reset time (start of next day)
    from datetime import timezone as _tz

    tomorrow = date.today() + timedelta(days=1)
    resets_at = (
        datetime.combine(tomorrow, datetime.min.time())
        .replace(tzinfo=_tz.utc)
        .isoformat()
    )

    return {
        "is_premium": False,
        "unlimited": False,
        "lifetime": {
            "learning_path_unlocked": free_limits["learning_path_unlocked"],
            "learning_path_max": FREE_LIFETIME_LIMITS["learning_path"],
            "beginner_unlocked": free_limits["beginner_unlocked"],
            "beginner_max": FREE_LIFETIME_LIMITS["beginner"],
            "intermediate_unlocked": free_limits["intermediate_unlocked"],
            "intermediate_max": FREE_LIFETIME_LIMITS["intermediate"],
            "advanced_unlocked": free_limits["advanced_unlocked"],
            "advanced_max": FREE_LIFETIME_LIMITS["advanced"],
        },
        "daily_submits": {
            "used": daily_used,
            "max": 3,
            "remaining": max(0, 3 - daily_used),
            "resets_at": resets_at,
        },
    }


# ============================================================================
# ENDPOINT 4: Get Conversation Detail
# ============================================================================


@router.get("/{conversation_id}")
async def get_conversation_detail(
    conversation_id: str,
    db=Depends(get_db),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """
    Get full conversation details including dialogue (PUBLIC - No authentication required)
    Returns: Complete conversation with all dialogue turns.
    When authenticated, also returns `can_play_audio` reflecting the user's access level.
    """
    conv_col = db["conversation_library"]

    conversation = conv_col.find_one({"conversation_id": conversation_id})

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Remove MongoDB _id
    conversation.pop("_id", None)

    # Convert ObjectId fields to string for JSON serialization
    if conversation.get("online_test_id"):
        conversation["online_test_id"] = str(conversation["online_test_id"])

    # Format audio info - build R2 URL from r2_key
    if conversation.get("audio_info"):
        audio_info = conversation["audio_info"]
        audio_url = None

        # Build R2 URL from r2_key (new format)
        if audio_info.get("r2_key"):
            audio_url = f"https://static.wordai.pro/{audio_info['r2_key']}"
        # Fallback to r2_url or url (legacy formats)
        elif audio_info.get("r2_url"):
            audio_url = audio_info["r2_url"]
        elif audio_info.get("url"):
            audio_url = audio_info["url"]

        conversation["audio_url"] = audio_url
        conversation["has_audio"] = bool(audio_url)

    # Determine audio access for authenticated users
    if current_user:
        uid = current_user["uid"]
        is_premium = await check_user_premium(uid, db)

        # Check if user has ever attempted this conversation (for gap_completed flag)
        has_prior = db["user_conversation_progress"].find_one(
            {"user_id": uid, "conversation_id": conversation_id}
        )
        conversation["gap_completed"] = bool(has_prior)

        if is_premium:
            conversation["can_play_audio"] = True
        else:
            # Can play if already submitted (has progress record any day)
            if has_prior:
                conversation["can_play_audio"] = True
            else:
                # Or: already played/accessed this conversation today (in daily set)
                already_today = await is_conversation_accessed_today(
                    uid, conversation_id, db
                )
                if already_today:
                    conversation["can_play_audio"] = True
                else:
                    # New conversation — check BOTH lifetime AND daily limits
                    level = conversation.get("level", "beginner")
                    can_lifetime = await _can_unlock(uid, level, db)
                    daily_info = await check_daily_limit(uid, db)
                    conversation["can_play_audio"] = (
                        can_lifetime and daily_info["remaining_free"] > 0
                    )
    else:
        conversation["can_play_audio"] = False
        conversation["gap_completed"] = False

    # Enforce server-side: hide audio_url when user cannot play audio
    if not conversation.get("can_play_audio"):
        conversation["audio_url"] = None

    return conversation


# ============================================================================
# ENDPOINT 3b: Track Audio Play (increments daily counter for free users)
# ============================================================================


@router.post("/{conversation_id}/play")
async def track_audio_play(
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Track that a user played audio for a conversation.
    For free users: consumes 1 daily interaction slot (shared with gap-fill submits).
    No-op for premium users or already-attempted conversations.
    """
    user_id = current_user["uid"]
    is_premium = await check_user_premium(user_id, db)

    if is_premium:
        return {"ok": True, "premium": True}

    # If user already has a progress record, replay is free (already unlocked)
    has_prior = db["user_conversation_progress"].find_one(
        {"user_id": user_id, "conversation_id": conversation_id}
    )
    if has_prior:
        return {"ok": True, "already_unlocked": True}

    # If already played this conversation today, replay is free (slot already consumed)
    already_today = await is_conversation_accessed_today(user_id, conversation_id, db)
    if already_today:
        return {"ok": True, "already_accessed_today": True}

    # New conversation — check daily limit
    limit_info = await check_daily_limit(user_id, db)
    if limit_info["remaining_free"] == 0:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "daily_limit_reached",
                "message": "Bạn đã dùng hết 3 lượt miễn phí hôm nay. Nâng cấp Premium để nghe không giới hạn!",
                "remaining": 0,
            },
        )

    # Check lifetime limit for this level
    conv_meta = db["conversation_library"].find_one(
        {"conversation_id": conversation_id}, {"level": 1}
    )
    level = conv_meta.get("level", "beginner") if conv_meta else "beginner"
    if not await _can_unlock(user_id, level, db):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "lifetime_limit_reached",
                "message": f"Bạn đã đạt giới hạn số bài {level} miễn phí. Nâng cấp Premium để học không giới hạn!",
            },
        )

    # Increment daily counter (shared pool with submit)
    await increment_daily_submit(user_id, db, conversation_id=conversation_id)
    new_remaining = limit_info["remaining_free"] - 1
    return {"ok": True, "remaining_today": new_remaining}


# ============================================================================
# ENDPOINT 4: Get Vocabulary & Grammar
# ============================================================================


@router.get("/{conversation_id}/vocabulary")
async def get_vocabulary_grammar(
    conversation_id: str,
    db=Depends(get_db),
):
    """
    Get vocabulary and grammar points extracted from the conversation (PUBLIC - No authentication required).

    Returns: Vocabulary items and grammar patterns
    """
    vocab_col = db["conversation_vocabulary"]

    vocab_doc = vocab_col.find_one({"conversation_id": conversation_id})

    if not vocab_doc:
        raise HTTPException(
            status_code=404,
            detail=f"Vocabulary not found for conversation: {conversation_id}",
        )

    # Remove MongoDB _id
    vocab_doc.pop("_id", None)

    return vocab_doc


# ============================================================================
# ENDPOINT 5: Get Gap Exercise
# ============================================================================


@router.get("/{conversation_id}/gaps")
async def get_all_gap_exercises(
    conversation_id: str,
    db=Depends(get_db),
):
    """
    Get all gap-fill exercises (easy, medium, hard) for the conversation (PUBLIC - No authentication required).

    Returns: All 3 difficulty levels with gaps and gap definitions
    """
    # Check conversation exists
    conv_col = db["conversation_library"]
    conversation = conv_col.find_one({"conversation_id": conversation_id})

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get all gaps documents
    gaps_col = db["conversation_gaps"]
    gaps_docs = list(gaps_col.find({"conversation_id": conversation_id}))

    # Organize by difficulty
    result = {"conversation_id": conversation_id, "gaps": {}}

    for gaps_doc in gaps_docs:
        difficulty = gaps_doc.get("difficulty")
        gaps_doc.pop("_id", None)
        result["gaps"][difficulty] = gaps_doc

    # If no gaps found, return empty structure
    if not gaps_docs:
        result["gaps"] = {"easy": None, "medium": None, "hard": None}
        result["message"] = "Gaps not generated yet. Please generate gaps first."

    return result


@router.get("/{conversation_id}/gaps/{difficulty}")
async def get_gap_exercise(
    conversation_id: str,
    difficulty: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Get gap-fill exercise for the conversation at specified difficulty.

    Path Parameters:
    - difficulty: "easy" | "medium" | "hard"

    Returns: Dialogue with gaps and gap definitions
    """
    # Validate difficulty
    if difficulty not in ["easy", "medium", "hard"]:
        raise HTTPException(
            status_code=400, detail="Invalid difficulty. Must be: easy, medium, or hard"
        )

    # Check conversation exists
    conv_col = db["conversation_library"]
    conversation = conv_col.find_one({"conversation_id": conversation_id})

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get gaps document
    gaps_col = db["conversation_gaps"]
    gaps_doc = gaps_col.find_one(
        {"conversation_id": conversation_id, "difficulty": difficulty}
    )

    if not gaps_doc:
        raise HTTPException(
            status_code=404,
            detail=f"Gaps not found for {conversation_id} at {difficulty} level. Please generate gaps first.",
        )

    # Remove MongoDB _id
    gaps_doc.pop("_id", None)

    return gaps_doc


# ============================================================================
# ENDPOINT 6: Submit Gap Exercise
# ============================================================================


@router.post("/{conversation_id}/gaps/{difficulty}/submit")
async def submit_gap_exercise(
    conversation_id: str,
    difficulty: str,
    request: Dict[str, Any],
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
    redis_client=Depends(get_redis),
):
    """
    Submit gap exercise answers and get results.

    Request Body:
    {
        "answers": {"1": "morning", "2": "are", ...},
        "time_spent": 120  # seconds
    }

    Returns: Detailed results with score, accuracy, and feedback
    """
    user_id = current_user["uid"]

    # Validate difficulty
    if difficulty not in ["easy", "medium", "hard"]:
        raise HTTPException(
            status_code=400, detail="Invalid difficulty. Must be: easy, medium, or hard"
        )

    # Get request data
    answers = request.get("answers", {})
    time_spent = request.get("time_spent", 0)

    if not answers:
        raise HTTPException(status_code=400, detail="Missing required field: answers")

    # Get gaps document
    gaps_col = db["conversation_gaps"]
    gaps_doc = gaps_col.find_one(
        {"conversation_id": conversation_id, "difficulty": difficulty}
    )

    if not gaps_doc:
        raise HTTPException(
            status_code=404,
            detail=f"Gaps not found for {conversation_id} at {difficulty} level",
        )

    # Check daily submit limit (free users: 3 unique conversations/day)
    limit_info = await check_daily_limit(user_id, db)
    if not limit_info["is_premium"] and limit_info["remaining_free"] == 0:
        # Allow if this conversation was already accessed today (replay is free)
        already_today = await is_conversation_accessed_today(
            user_id, conversation_id, db
        )
        if not already_today:
            raise HTTPException(
                status_code=403,
                detail="Daily submit limit reached (3 submissions/day for free users). Upgrade to Premium for unlimited access.",
            )

    # Check lifetime limit for NEW conversations (free users)
    if not limit_info["is_premium"]:
        has_prior_check = db["user_conversation_progress"].find_one(
            {"user_id": user_id, "conversation_id": conversation_id}
        )
        if not has_prior_check:
            already_today_check = await is_conversation_accessed_today(
                user_id, conversation_id, db
            )
            if not already_today_check:
                conv_level_meta = db["conversation_library"].find_one(
                    {"conversation_id": conversation_id}, {"level": 1}
                )
                level_ctx = (
                    conv_level_meta.get("level", "beginner")
                    if conv_level_meta
                    else "beginner"
                )
                if not await _can_unlock(user_id, level_ctx, db):
                    raise HTTPException(
                        status_code=403,
                        detail=f"Lifetime limit reached for {level_ctx} conversations. Upgrade to Premium for unlimited access.",
                    )

    # Increment daily submit count (free users only)
    await increment_daily_submit(user_id, db, conversation_id=conversation_id)

    # On first-ever attempt for this conversation, increment lifetime unlock counter
    if not limit_info["is_premium"]:
        has_prior_attempt = db["user_conversation_progress"].find_one(
            {"user_id": user_id, "conversation_id": conversation_id}
        )
        if not has_prior_attempt:
            conv_meta = db["conversation_library"].find_one(
                {"conversation_id": conversation_id}, {"level": 1}
            )
            if conv_meta:
                await _increment_lifetime_unlock(user_id, conv_meta["level"], db)

    # Grade answers
    gap_definitions = gaps_doc["gap_definitions"]  # Use gap_definitions field
    total_gaps = len(gap_definitions)
    correct_count = 0
    incorrect_count = 0
    gap_results = []
    pos_stats = {}

    for gap in gap_definitions:
        gap_num = str(gap["gap_number"])
        correct_answer = gap["correct_answer"].lower().strip()
        user_answer = answers.get(gap_num, "").lower().strip()
        is_correct = user_answer == correct_answer

        if is_correct:
            correct_count += 1
        else:
            incorrect_count += 1

        gap_results.append(
            {
                "gap_number": gap["gap_number"],
                "correct_answer": gap["correct_answer"],
                "user_answer": answers.get(gap_num, ""),
                "is_correct": is_correct,
                "pos_tag": gap["pos_tag"],
            }
        )

        # POS statistics
        pos = gap["pos_tag"]
        if pos not in pos_stats:
            pos_stats[pos] = {"correct": 0, "total": 0}
        pos_stats[pos]["total"] += 1
        if is_correct:
            pos_stats[pos]["correct"] += 1

    # Calculate score
    score = round((correct_count / total_gaps) * 100, 1) if total_gaps > 0 else 0
    is_passed = score >= 80

    # Calculate POS accuracy
    pos_accuracy = {}
    for pos, stats in pos_stats.items():
        pos_accuracy[pos.lower()] = {
            "correct": stats["correct"],
            "total": stats["total"],
            "accuracy": round((stats["correct"] / stats["total"]) * 100, 1),
        }

    # Save attempt
    attempt_id = str(uuid.uuid4())
    attempt_doc = {
        "attempt_id": attempt_id,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "difficulty": difficulty,
        "answers": answers,
        "total_gaps": total_gaps,
        "correct_count": correct_count,
        "incorrect_count": incorrect_count,
        "score": score,
        "is_passed": is_passed,
        "gap_results": gap_results,
        "pos_accuracy": pos_accuracy,
        "time_spent": time_spent,
        "completed_at": datetime.utcnow(),
        "created_at": datetime.utcnow(),
    }

    attempts_col = db["conversation_attempts"]
    attempts_col.insert_one(attempt_doc)

    # Update user progress
    progress_col = db["user_conversation_progress"]

    # Check if this is best score for this difficulty
    existing_progress = progress_col.find_one(
        {"user_id": user_id, "conversation_id": conversation_id}
    )

    is_best_score = True
    if existing_progress and existing_progress.get("best_scores"):
        best_scores = existing_progress["best_scores"]
        if difficulty in best_scores:
            is_best_score = score > best_scores[difficulty]["score"]

    # Update progress
    update_data = {
        "$inc": {"total_attempts": 1, "total_time_spent": time_spent},
        "$set": {
            "last_attempt_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        },
        "$setOnInsert": {
            "user_id": user_id,
            "conversation_id": conversation_id,
            "first_attempt_at": datetime.utcnow(),
        },
    }

    # Update best score if needed
    if is_best_score:
        update_data["$set"][f"best_scores.{difficulty}"] = {
            "score": score,
            "attempt_id": attempt_id,
            "completed_at": datetime.utcnow(),
        }

    # Mark as completed if passed + update Phase 1 dual-part fields
    if is_passed:
        update_data["$set"]["is_completed"] = True  # kept for backward compat
        update_data["$addToSet"] = {"completed_difficulties": difficulty}
        # Phase 1: gap completion fields (worker will also check dual-part for is_completed)
        prev_gap_best = (existing_progress or {}).get("gap_best_score", 0)
        update_data["$set"]["gap_completed"] = True
        update_data["$set"]["gap_difficulty"] = difficulty
        if score > prev_gap_best:
            update_data["$set"]["gap_best_score"] = score

    progress_col.update_one(
        {"user_id": user_id, "conversation_id": conversation_id},
        update_data,
        upsert=True,
    )

    # Update daily streak (any completed activity counts)
    await update_daily_streak(
        user_id=user_id,
        score=score,
        activity_type="conversation",
        activity_id=conversation_id,
        db=db,
        redis_client=redis_client,
    )

    # Calculate and award XP (if passed)
    xp_info = None
    newly_earned_achievements = []

    if is_passed:
        # Calculate XP earned
        is_first_attempt = not existing_progress
        is_perfect_score = score == 100.0

        xp_earned = await calculate_xp_earned(
            difficulty, score, is_first_attempt, is_perfect_score
        )

        # Update user XP
        xp_info = await update_user_xp(
            user_id,
            xp_earned,
            f"Completed {difficulty} conversation",
            conversation_id,
            difficulty,
            score,
            db,
        )

        # Check and award achievements
        newly_earned_achievements = await check_and_award_achievements(
            user_id, conversation_id, score, difficulty, db
        )

    # Phase 1: push gamification event → learning_events_worker processes
    # new dual-part is_completed check + future Phase 2/3 path/progression updates
    try:
        event_payload = json.dumps(
            {
                "event_id": str(uuid.uuid4()),
                "event_type": "gap_submitted",
                "user_id": user_id,
                "conversation_id": conversation_id,
                "difficulty": difficulty,
                "score": score,
                "correct": correct_count,
                "total": total_gaps,
                "time_spent": time_spent,
                "is_first_attempt": not existing_progress,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
        redis_client.lpush("queue:learning_events", event_payload)
    except Exception as _e:
        # Non-critical: log but never fail the submit response
        logger.warning(f"learning_events push failed: {_e}")

    # Return results
    return {
        "total_gaps": total_gaps,
        "correct_count": correct_count,
        "incorrect_count": incorrect_count,
        "score": score,
        "is_passed": is_passed,
        "gap_results": gap_results,
        "pos_accuracy": pos_accuracy,
        "attempt_saved": {
            "attempt_id": attempt_id,
            "conversation_id": conversation_id,
            "difficulty": difficulty,
            "score": score,
            "time_spent": time_spent,
            "completed_at": datetime.utcnow().isoformat(),
            "is_best_score": is_best_score,
        },
        "xp_earned": xp_info if xp_info else None,
        "achievements_earned": [
            {
                "achievement_id": ach["achievement_id"],
                "achievement_name": ach["achievement_name"],
                "achievement_type": ach["achievement_type"],
                "xp_bonus": ach.get("xp_bonus", 0),
            }
            for ach in newly_earned_achievements
        ],
        "gamification": "synced",  # background worker also handling dual-part tracking
    }


# ============================================================================
# ENDPOINT 8: Get Conversation History
# ============================================================================


@router.get("/{conversation_id}/history")
async def get_conversation_history(
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Get all attempts for a specific conversation by current user.

    Returns: Attempt history and best scores
    """
    user_id = current_user["uid"]

    # Check conversation exists
    conv_col = db["conversation_library"]
    conversation = conv_col.find_one({"conversation_id": conversation_id})

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get all attempts
    attempts_col = db["conversation_attempts"]
    attempts_docs = list(
        attempts_col.find(
            {"user_id": user_id, "conversation_id": conversation_id}
        ).sort("completed_at", -1)
    )

    attempts = []
    for attempt in attempts_docs:
        attempts.append(
            {
                "attempt_id": attempt["attempt_id"],
                "difficulty": attempt["difficulty"],
                "score": attempt["score"],
                "correct_count": attempt["correct_count"],
                "total_gaps": attempt["total_gaps"],
                "time_spent": attempt["time_spent"],
                "is_passed": attempt["is_passed"],
                "completed_at": attempt["completed_at"].isoformat(),
            }
        )

    # Get best scores
    progress_col = db["user_conversation_progress"]
    progress = progress_col.find_one(
        {"user_id": user_id, "conversation_id": conversation_id}
    )

    best_scores = {"easy": None, "medium": None, "hard": None}
    total_time_spent = 0

    if progress:
        total_time_spent = progress.get("total_time_spent", 0)
        for difficulty in ["easy", "medium", "hard"]:
            if difficulty in progress.get("best_scores", {}):
                score_data = progress["best_scores"][difficulty]
                best_scores[difficulty] = {
                    "score": score_data["score"],
                    "attempt_id": score_data["attempt_id"],
                    "completed_at": score_data["completed_at"].isoformat(),
                }

    return {
        "conversation_id": conversation_id,
        "title": conversation["title"],
        "attempts": attempts,
        "best_scores": best_scores,
        "total_attempts": len(attempts),
        "total_time_spent": total_time_spent,
    }


# ============================================================================
# ENDPOINT 11: Save Conversation
# ============================================================================


@router.post("/{conversation_id}/save")
async def save_conversation(
    conversation_id: str,
    request: Dict[str, Any] = {},
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Bookmark/save a conversation for later practice.

    Request Body (all fields optional):
    {
        "notes": "Need to review this",  # Optional
        "tags": ["difficult", "review"]   # Optional
    }

    Returns: Success message
    """
    user_id = current_user["uid"]

    # Check conversation exists
    conv_col = db["conversation_library"]
    conversation = conv_col.find_one({"conversation_id": conversation_id})

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if already saved
    saved_col = db["user_conversation_saved"]
    existing = saved_col.find_one(
        {"user_id": user_id, "conversation_id": conversation_id}
    )

    if existing:
        # Update notes/tags if provided
        update_data = {"updated_at": datetime.utcnow()}
        if "notes" in request:
            update_data["notes"] = request["notes"]
        if "tags" in request:
            update_data["tags"] = request["tags"]

        saved_col.update_one(
            {"user_id": user_id, "conversation_id": conversation_id},
            {"$set": update_data},
        )

        return {
            "message": "Conversation updated in saved list",
            "conversation_id": conversation_id,
            "already_saved": True,
        }

    # Save new
    saved_doc = {
        "user_id": user_id,
        "conversation_id": conversation_id,
        "notes": request.get("notes"),
        "tags": request.get("tags", []),
        "saved_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

    saved_col.insert_one(saved_doc)

    return {
        "message": "Conversation saved successfully",
        "conversation_id": conversation_id,
        "saved_at": saved_doc["saved_at"].isoformat(),
    }


# ============================================================================
# ENDPOINT 12: Unsave Conversation
# ============================================================================


@router.delete("/{conversation_id}/save")
async def unsave_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Remove conversation from saved list.

    Returns: Success message
    """
    user_id = current_user["uid"]

    saved_col = db["user_conversation_saved"]

    result = saved_col.delete_one(
        {"user_id": user_id, "conversation_id": conversation_id}
    )

    if result.deleted_count == 0:
        raise HTTPException(
            status_code=404, detail="Conversation not found in saved list"
        )

    return {
        "message": "Conversation removed from saved list",
        "conversation_id": conversation_id,
    }
