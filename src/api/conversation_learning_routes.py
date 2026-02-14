"""
Conversation Learning API Routes - Core Learning Features

Endpoints:
1. GET /api/v1/conversations - Browse conversations with filters
2. GET /api/v1/conversations/topics - Get topics list
3. GET /api/v1/conversations/{conversation_id} - Get conversation details
4. GET /api/v1/conversations/{conversation_id}/vocabulary - Get vocabulary & grammar
5. GET /api/v1/conversations/{conversation_id}/gaps/{difficulty} - Get gap exercise
6. POST /api/v1/conversations/{conversation_id}/gaps/{difficulty}/submit - Submit answers
7. GET /api/v1/conversations/progress - Get user progress
8. GET /api/v1/conversations/{conversation_id}/history - Get conversation history

Business rules:
- Free users: 5 conversations/day limit
- Premium users: Unlimited (shared with Song Learning)
- Completion threshold: ≥80% correct answers
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional, Dict, Any
from datetime import datetime, date
import uuid

from src.database.db_manager import DBManager
from src.middleware.firebase_auth import get_current_user


router = APIRouter(prefix="/api/v1/conversations", tags=["Conversation Learning"])


# ============================================================================
# DEPENDENCIES
# ============================================================================


def get_db():
    """Get database connection."""
    db_manager = DBManager()
    return db_manager.db


async def check_user_premium(user_id: str, db) -> bool:
    """
    Check if user has active premium subscription.
    Shared with Song Learning subscription.

    Returns: True if user is premium, False otherwise
    """
    subscription_col = db["user_song_subscription"]

    subscription = subscription_col.find_one(
        {"user_id": user_id, "is_active": True, "end_date": {"$gte": datetime.utcnow()}}
    )

    return subscription is not None


async def check_daily_limit(user_id: str, db) -> dict:
    """
    Check user's daily free conversation limit.

    Returns: Dict with is_premium, conversations_played_today, remaining_free
    """
    is_premium = await check_user_premium(user_id, db)

    if is_premium:
        return {
            "is_premium": True,
            "conversations_played_today": 0,
            "remaining_free": -1,  # Unlimited
        }

    # Check free usage today
    today = date.today()
    daily_col = db["user_daily_free_conversations"]

    daily_record = daily_col.find_one(
        {"user_id": user_id, "date": datetime.combine(today, datetime.min.time())}
    )

    if not daily_record:
        return {
            "is_premium": False,
            "conversations_played_today": 0,
            "remaining_free": 5,
        }

    conversations_played = len(daily_record.get("conversation_ids", []))
    remaining = max(0, 5 - conversations_played)

    return {
        "is_premium": False,
        "conversations_played_today": conversations_played,
        "remaining_free": remaining,
    }


async def increment_daily_usage(user_id: str, conversation_id: str, db):
    """
    Increment user's daily conversation usage.
    Only for free users.
    """
    is_premium = await check_user_premium(user_id, db)
    if is_premium:
        return  # Premium users don't have limits

    today = date.today()
    daily_col = db["user_daily_free_conversations"]

    daily_col.update_one(
        {"user_id": user_id, "date": datetime.combine(today, datetime.min.time())},
        {
            "$addToSet": {"conversation_ids": conversation_id},
            "$setOnInsert": {"created_at": datetime.utcnow()},
            "$set": {"updated_at": datetime.utcnow()},
        },
        upsert=True,
    )


# ============================================================================
# ENDPOINT 1: Browse Conversations
# ============================================================================


@router.get("/browse")
async def browse_conversations(
    level: Optional[str] = None,
    topic: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db=Depends(get_db),
):
    """
    Browse conversations with filters (PUBLIC - No authentication required).

    Query Parameters:
    - level: "beginner" | "intermediate" | "advanced"
    - topic: Topic slug (e.g., "work_office")
    - page: Page number (default: 1)
    - page_size: Items per page (default: 20, max: 100)

    Returns: List of conversations with metadata
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

    # Format response
    conversation_list = []
    for conv in conversations:
        conversation_list.append(
            {
                "conversation_id": conv["conversation_id"],
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
                "audio_url": conv.get("audio_url"),
                "difficulties_available": [
                    "easy",
                    "medium",
                    "hard",
                ],  # All have 3 levels
            }
        )

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
# ENDPOINT 3: Get Conversation Detail
# ============================================================================


@router.get("/{conversation_id}")
async def get_conversation_detail(
    conversation_id: str,
    db=Depends(get_db),
):
    """
    Get full conversation details including dialogue (PUBLIC - No authentication required)
    Returns: Complete conversation with all dialogue turns
    """
    conv_col = db["conversation_library"]

    conversation = conv_col.find_one({"conversation_id": conversation_id})

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Remove MongoDB _id
    conversation.pop("_id", None)

    # Format audio info - check both r2_url and url fields
    if conversation.get("audio_info"):
        audio_info = conversation["audio_info"]
        # Try r2_url first (new format), then url (old format)
        audio_url = audio_info.get("r2_url") or audio_info.get("url")
        conversation["audio_url"] = audio_url
        conversation["has_audio"] = bool(audio_url)

    return conversation


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

    # Check daily limit
    limit_info = await check_daily_limit(user_id, db)
    if not limit_info["is_premium"] and limit_info["remaining_free"] == 0:
        raise HTTPException(
            status_code=403,
            detail="Daily limit reached (5 conversations/day for free users). Upgrade to premium for unlimited access.",
        )

    # Increment daily usage
    await increment_daily_usage(user_id, conversation_id, db)

    # Grade answers
    gaps = gaps_doc["gaps"]
    total_gaps = len(gaps)
    correct_count = 0
    incorrect_count = 0
    gap_results = []
    pos_stats = {}

    for gap in gaps:
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

    # Mark as completed if passed
    if is_passed:
        update_data["$set"]["is_completed"] = True
        update_data["$addToSet"] = {"completed_difficulties": difficulty}

    progress_col.update_one(
        {"user_id": user_id, "conversation_id": conversation_id},
        update_data,
        upsert=True,
    )

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
# ENDPOINT 9: Get All Learning History
# ============================================================================


@router.get("/history/all")
async def get_all_learning_history(
    level: Optional[str] = None,
    topic: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Get all conversations user has attempted with detailed stats.

    Query Parameters:
    - level: Filter by level
    - topic: Filter by topic
    - skip: Pagination offset
    - limit: Page size (max: 100)

    Returns: Complete learning history with analytics
    """
    user_id = current_user["uid"]

    if limit > 100:
        limit = 100

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
    paginated = history[skip : skip + limit]

    return {
        "history": paginated,
        "total": total,
        "page": skip // limit + 1,
        "limit": limit,
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
# ENDPOINT 11: Save Conversation
# ============================================================================


@router.post("/{conversation_id}/save")
async def save_conversation(
    conversation_id: str,
    request: Dict[str, Any],
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Bookmark/save a conversation for later practice.

    Request Body:
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
