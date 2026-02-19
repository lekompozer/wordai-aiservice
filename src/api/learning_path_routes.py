"""
Learning Path API Routes — Phase 2
===================================
Smart personalized 100-conversation learning path.

Endpoints:
  POST /api/v1/learning-path/setup    - Create/update profile + generate path
  GET  /api/v1/learning-path/today    - Today's assignments from active path
  GET  /api/v1/learning-path/progress - Path progress + progression level status
  GET  /api/v1/learning-path/profile  - Get/check existing profile
  DELETE /api/v1/learning-path/reset  - Reset path (regenerate)

Collections:
  user_learning_profile   – goals, interests, progression level, song counts
  user_learning_path      – 100-item ordered path with completion state
  user_conversation_progress – dual-part completion (gap + test)
  conversation_library    – source of truth for conversations
"""

import logging
import random
import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from src.database.db_manager import DBManager
from src.middleware.firebase_auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/learning-path", tags=["Learning Path"])


# ============================================================================
# Dependencies
# ============================================================================


def get_db():
    return DBManager().db


# ============================================================================
# Constants — Goal / Interest → topic_number mapping
# (topic_numbers 1-30 as used in conversation_library)
# Beginner: 1-10,  Intermediate: 11-20,  Advanced: 21-30
# ============================================================================

GOAL_TOPIC_MAP: Dict[str, List[int]] = {
    # Beginner-anchored goals
    "daily_life": [1, 2, 3, 4],  # Greetings, Routines, Family, Food & Dining
    "travel": [8, 12],  # Transportation (B) + Travel & Tourism (I)
    "health": [9, 24],  # Health & Body (B) + Medicine & Healthcare (A)
    "education": [10, 15],  # Education (B) + Academic Life (I)
    # Intermediate goals
    "business": [11, 18, 21],  # Work (I) + Finance (I) + Business (A)
    "technology": [14, 30],  # Technology (I) + Future & Innovation (A)
    "social": [13, 19],  # Social Issues (I) + Relationships (I)
    "culture": [16, 23],  # Culture & Arts (I) + History (A)
    "environment": [17, 25],  # Environment (I) + Climate (A)
    # Advanced goals
    "debate": [26, 27],  # Debate Topics (A) + Critical Thinking (A)
    "career": [22, 28],  # Career Development (A) + Leadership (A)
    "science": [20, 29],  # Science (I) + Research & Innovation (A)
}

INTEREST_TOPIC_MAP: Dict[str, List[int]] = {
    "sports": [5],  # Sports & Fitness (B)
    "shopping": [6],  # Shopping (B)
    "entertainment": [7, 16],  # Entertainment (B) + Culture & Arts (I)
    "music": [7],  # Entertainment/music (B)
    "food": [4],  # Food & Dining (B)
    "fashion": [6],  # Shopping/fashion
    "nature": [17, 25],  # Environment (I) + Climate (A)
    "history": [23],  # History & Heritage (A)
    "philosophy": [27],  # Critical Thinking (A)
    "humor": [1, 13],  # Greetings/small-talk + Social
}

# Foundation essentials — used for the final 10 "foundation" slots
FOUNDATION_TOPICS = [1, 2, 3, 4, 10]  # Greetings, Routines, Family, Food, Education

# Level → challenge level (one level up)
LEVEL_UP = {
    "beginner": "intermediate",
    "intermediate": "advanced",
    "advanced": "advanced",
}

# Progression thresholds
PROGRESSION_LEVELS = {
    1: {"name": "Initiate", "conversations": 100, "songs": 10},
    2: {"name": "Scholar", "conversations": 100, "songs": 10},
    3: {"name": "Addict", "conversations": 100, "songs": 10},
}


# ============================================================================
# Path Generation Logic
# ============================================================================


def _level_to_difficulty(level: str) -> str:
    lvl = (level or "").lower()
    if lvl == "advanced":
        return "hard"
    if lvl == "intermediate":
        return "medium"
    return "easy"


def _get_topic_convs(
    db, topic_numbers: List[int], level: str, exclude_ids: set
) -> List[dict]:
    """Fetch conversations from given topic numbers at a specific level."""
    return list(
        db["conversation_library"].find(
            {
                "topic_number": {"$in": topic_numbers},
                "level": level,
                "conversation_id": {"$nin": list(exclude_ids)},
            },
            projection={
                "conversation_id": 1,
                "topic": 1,
                "topic_number": 1,
                "level": 1,
                "online_test_id": 1,
                "_id": 0,
            },
        )
    )


def _generate_path_items(
    db,
    level: str,
    goals: List[str],
    interests: List[str],
) -> List[dict]:
    """
    Generate ordered 100-item path:
      - 60 from goal topics at user's level
      - 20 from interest topics at user's level
      - 10 from challenge level (one level up)
      -  10 from foundation topics (beginner, any)

    Items are shuffled within each bucket, then concatenated in order.
    Deduplication is maintained across buckets.
    """
    difficulty = _level_to_difficulty(level)
    challenge_level = LEVEL_UP.get(level, level)
    challenge_diff = _level_to_difficulty(challenge_level)
    used_ids: set = set()

    def _pick(
        convs: List[dict], n: int, source: str, diff_override: str = difficulty
    ) -> List[dict]:
        """Shuffle and pick up to n convs, tag with source + difficulty."""
        random.shuffle(convs)
        picked = []
        for c in convs:
            cid = c["conversation_id"]
            if cid not in used_ids:
                used_ids.add(cid)
                picked.append(
                    {**c, "source": source, "difficulty_suggestion": diff_override}
                )
            if len(picked) >= n:
                break
        return picked

    # ── Goal bucket (60 slots) ──────────────────────────────────────────────
    goal_topic_nums = list({tn for g in goals for tn in GOAL_TOPIC_MAP.get(g, [])})
    goal_convs = _get_topic_convs(
        db, goal_topic_nums or list(range(1, 11)), level, used_ids
    )
    goal_items = _pick(goal_convs, 60, "goal")

    # ── Interest bucket (20 slots) ──────────────────────────────────────────
    interest_topic_nums = list(
        {tn for i in interests for tn in INTEREST_TOPIC_MAP.get(i, [])}
    )
    interest_convs = _get_topic_convs(
        db, interest_topic_nums or list(range(1, 11)), level, used_ids
    )
    interest_items = _pick(interest_convs, 20, "interest")

    # ── Challenge bucket (10 slots, one level up) ──────────────────────────
    challenge_topic_nums = goal_topic_nums or list(range(1, 11))
    challenge_convs = _get_topic_convs(
        db, challenge_topic_nums, challenge_level, used_ids
    )
    challenge_items = _pick(challenge_convs, 10, "challenge", challenge_diff)

    # ── Foundation bucket (10 slots) ───────────────────────────────────────
    foundation_convs = _get_topic_convs(db, FOUNDATION_TOPICS, "beginner", used_ids)
    foundation_items = _pick(foundation_convs, 10, "foundation", "easy")

    # Merge and assign positions
    all_items = goal_items + interest_items + challenge_items + foundation_items
    path_items = []
    for pos, item in enumerate(all_items, start=1):
        path_items.append(
            {
                "conversation_id": item["conversation_id"],
                "topic": item.get("topic", {}).get("en", ""),
                "topic_number": item.get("topic_number", 0),
                "level": item.get("level", level),
                "position": pos,
                "source": item["source"],
                "difficulty_suggestion": item["difficulty_suggestion"],
                "online_test_id": (
                    str(item["online_test_id"]) if item.get("online_test_id") else None
                ),
                "completed": False,
                "completed_at": None,
            }
        )

    return path_items


# ============================================================================
# ENDPOINT 1: POST /setup
# ============================================================================


@router.post("/setup")
async def setup_learning_path(
    request: Dict[str, Any],
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Create or update user learning profile and generate a personalized
    100-conversation path.

    Request body:
    {
        "level": "beginner" | "intermediate" | "advanced",
        "goals": ["daily_life", "travel", "business", ...],
        "interests": ["sports", "music", "food", ...],
        "daily_commitment": 1-5
    }

    Goals map to 60 conversations, interests to 20, challenge to 10, foundation to 10.
    """
    user_id = current_user["uid"]

    level = request.get("level", "beginner").lower()
    if level not in ("beginner", "intermediate", "advanced"):
        raise HTTPException(
            status_code=400, detail="level must be beginner|intermediate|advanced"
        )

    goals: List[str] = request.get("goals", [])
    interests: List[str] = request.get("interests", [])
    daily_commitment = int(request.get("daily_commitment", 2))
    daily_commitment = max(1, min(5, daily_commitment))

    now = datetime.utcnow()

    # ── Upsert user_learning_profile ───────────────────────────────────────
    profile_col = db["user_learning_profile"]
    existing_profile = profile_col.find_one({"user_id": user_id})

    profile_update = {
        "level": level,
        "goals": goals,
        "interests": interests,
        "daily_commitment": daily_commitment,
        "updated_at": now,
    }

    if not existing_profile:
        profile_update.update(
            {
                "user_id": user_id,
                "progression_level": 1,
                "l1_completed": 0,
                "l2_completed": 0,
                "l3_completed": 0,
                "l1_songs_completed": 0,
                "l2_songs_completed": 0,
                "l3_songs_completed": 0,
                "created_at": now,
            }
        )

    profile_col.update_one(
        {"user_id": user_id},
        {"$set": profile_update, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )

    # ── Deactivate any existing active path ────────────────────────────────
    path_col = db["user_learning_path"]
    path_col.update_many(
        {"user_id": user_id, "is_active": True},
        {"$set": {"is_active": False, "updated_at": now}},
    )

    # ── Generate new path ──────────────────────────────────────────────────
    path_items = _generate_path_items(db, level, goals, interests)
    path_id = f"lp_{uuid.uuid4().hex[:12]}"

    path_doc = {
        "path_id": path_id,
        "user_id": user_id,
        "level": level,
        "goals": goals,
        "interests": interests,
        "daily_commitment": daily_commitment,
        "path_items": path_items,
        "total_items": len(path_items),
        "completed_count": 0,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    path_col.insert_one(path_doc)

    # ── Link path to profile ───────────────────────────────────────────────
    profile_col.update_one(
        {"user_id": user_id},
        {"$set": {"active_path_id": path_id, "updated_at": now}},
    )

    logger.info(
        f"[learning_path] setup user={user_id} level={level} "
        f"path={path_id} items={len(path_items)}"
    )

    return {
        "path_id": path_id,
        "level": level,
        "goals": goals,
        "interests": interests,
        "daily_commitment": daily_commitment,
        "total_conversations": len(path_items),
        "breakdown": {
            "goals": sum(1 for i in path_items if i["source"] == "goal"),
            "interests": sum(1 for i in path_items if i["source"] == "interest"),
            "challenge": sum(1 for i in path_items if i["source"] == "challenge"),
            "foundation": sum(1 for i in path_items if i["source"] == "foundation"),
        },
        "message": "Learning path generated! Use GET /today to see today's assignments.",
    }


# ============================================================================
# ENDPOINT 2: GET /today
# ============================================================================


@router.get("/today")
async def get_today_plan(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Get today's learning assignments based on:
    - daily_commitment (from profile)
    - Next N unfinished items from active path
    - +1 review item (incomplete or gap_score < 80%)

    Returns list of assignments with dual-part completion status.
    """
    user_id = current_user["uid"]

    # Load profile + active path
    profile_col = db["user_learning_profile"]
    path_col = db["user_learning_path"]
    progress_col = db["user_conversation_progress"]
    conv_col = db["conversation_library"]

    profile = profile_col.find_one({"user_id": user_id})
    if not profile:
        raise HTTPException(
            status_code=404,
            detail="No learning profile found. Please call POST /learning-path/setup first.",
        )

    path = path_col.find_one({"user_id": user_id, "is_active": True})
    if not path:
        raise HTTPException(
            status_code=404,
            detail="No active learning path. Please call POST /learning-path/setup to generate one.",
        )

    daily_goal = profile.get("daily_commitment", 2)

    # Get all progress for path conversations (one query)
    path_conv_ids = [item["conversation_id"] for item in path["path_items"]]
    progress_docs = {
        p["conversation_id"]: p
        for p in progress_col.find(
            {"user_id": user_id, "conversation_id": {"$in": path_conv_ids}},
            projection={
                "conversation_id": 1,
                "gap_completed": 1,
                "gap_best_score": 1,
                "test_completed": 1,
                "test_best_score": 1,
                "is_completed": 1,
                "_id": 0,
            },
        )
    }

    # Get today's completed units count
    today_str = date.today().isoformat()
    # Count items completed today (is_completed that were completed today)
    # We approximate by checking progress_docs — exact "today" count requires
    # reading streak data; use the streak collection for that.
    streak_col = db["user_learning_streak"]
    streak_today = streak_col.find_one({"user_id": user_id, "date": today_str})
    progress_today = len((streak_today or {}).get("activities", []))

    # ── Pick new assignments ────────────────────────────────────────────────
    assignments = []
    review_candidate = None

    for item in path["path_items"]:
        cid = item["conversation_id"]
        prog = progress_docs.get(cid, {})
        gap_done = prog.get("gap_completed", False)
        test_done = prog.get("test_completed", False)
        is_fully_done = prog.get("is_completed", False)

        if is_fully_done:
            continue  # Skip fully done items

        if len(assignments) < daily_goal:
            assignments.append(
                {
                    "position": item["position"],
                    "type": "new" if not gap_done else "continue",
                    "conversation_id": cid,
                    "topic": item.get("topic", ""),
                    "topic_number": item.get("topic_number", 0),
                    "level": item.get("level", ""),
                    "source": item["source"],
                    "suggested_difficulty": item["difficulty_suggestion"],
                    "parts": {
                        "gap_fill": {
                            "completed": gap_done,
                            "best_score": prog.get("gap_best_score"),
                        },
                        "online_test": {
                            "completed": test_done,
                            "test_id": item.get("online_test_id"),
                            "best_score": prog.get("test_best_score"),
                        },
                    },
                }
            )
        elif review_candidate is None and gap_done and not test_done:
            # Review candidate: gap done but test not done, or low gap score
            review_candidate = {
                "position": item["position"],
                "type": "review",
                "conversation_id": cid,
                "topic": item.get("topic", ""),
                "topic_number": item.get("topic_number", 0),
                "level": item.get("level", ""),
                "source": item["source"],
                "suggested_difficulty": item["difficulty_suggestion"],
                "review_reason": "test_pending",
                "parts": {
                    "gap_fill": {
                        "completed": gap_done,
                        "best_score": prog.get("gap_best_score"),
                    },
                    "online_test": {
                        "completed": test_done,
                        "test_id": item.get("online_test_id"),
                        "best_score": prog.get("test_best_score"),
                    },
                },
            }
        elif (
            review_candidate is None
            and gap_done
            and (prog.get("gap_best_score", 100) < 80)
        ):
            review_candidate = {
                "position": item["position"],
                "type": "review",
                "conversation_id": cid,
                "topic": item.get("topic", ""),
                "topic_number": item.get("topic_number", 0),
                "level": item.get("level", ""),
                "source": item["source"],
                "suggested_difficulty": item["difficulty_suggestion"],
                "review_reason": "gap_score_low",
                "parts": {
                    "gap_fill": {
                        "completed": gap_done,
                        "best_score": prog.get("gap_best_score"),
                    },
                    "online_test": {
                        "completed": test_done,
                        "test_id": item.get("online_test_id"),
                        "best_score": prog.get("test_best_score"),
                    },
                },
            }

    if review_candidate:
        assignments.append(review_candidate)

    # ── Streak info ─────────────────────────────────────────────────────────
    streak_col = db["user_learning_streak"]
    streak_record = streak_col.find_one({"user_id": user_id}, sort=[("date", -1)])
    current_streak = 0
    today_completed_streak = False
    if streak_record:
        current_streak = streak_record.get("current_streak", 0)
        today_completed_streak = streak_record.get("date") == today_str

    return {
        "date": today_str,
        "daily_goal": daily_goal,
        "progress_today": progress_today,
        "daily_goal_met": progress_today >= daily_goal,
        "path_id": path["path_id"],
        "assignments": assignments,
        "streak_info": {
            "current_streak": current_streak,
            "today_completed": today_completed_streak,
        },
    }


# ============================================================================
# ENDPOINT 3: GET /progress
# ============================================================================


@router.get("/progress")
async def get_path_progress(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Summary of active path + progression level status.
    """
    user_id = current_user["uid"]

    profile_col = db["user_learning_profile"]
    path_col = db["user_learning_path"]
    progress_col = db["user_conversation_progress"]

    profile = profile_col.find_one({"user_id": user_id})
    if not profile:
        raise HTTPException(
            status_code=404,
            detail="No learning profile found. Please call POST /learning-path/setup first.",
        )

    path = path_col.find_one({"user_id": user_id, "is_active": True})

    if not path:
        # Return profile info even without a path
        return {
            "path_id": None,
            "level": profile.get("level"),
            "overall_percent": 0.0,
            "completed": 0,
            "total": 0,
            "breakdown": {"goals": 0, "interests": 0, "challenge": 0, "foundation": 0},
            "progression": _build_progression_info(profile),
            "message": "No active path. Call POST /learning-path/setup to generate one.",
        }

    # Get all progress in one query
    path_conv_ids = [i["conversation_id"] for i in path["path_items"]]
    completed_ids = set(
        p["conversation_id"]
        for p in progress_col.find(
            {
                "user_id": user_id,
                "conversation_id": {"$in": path_conv_ids},
                "is_completed": True,
            },
            projection={"conversation_id": 1, "_id": 0},
        )
    )

    # Breakdown by source
    breakdown = {
        "goals": {"completed": 0, "total": 0},
        "interests": {"completed": 0, "total": 0},
        "challenge": {"completed": 0, "total": 0},
        "foundation": {"completed": 0, "total": 0},
    }

    for item in path["path_items"]:
        src = item.get("source", "goals")
        key = {
            "goal": "goals",
            "interest": "interests",
            "challenge": "challenge",
            "foundation": "foundation",
        }.get(src, "goals")
        breakdown[key]["total"] += 1
        if item["conversation_id"] in completed_ids:
            breakdown[key]["completed"] += 1

    total = path["total_items"]
    completed_count = len(completed_ids)
    overall_percent = round(completed_count / total * 100, 1) if total > 0 else 0.0

    return {
        "path_id": path["path_id"],
        "level": path["level"],
        "overall_percent": overall_percent,
        "completed": completed_count,
        "total": total,
        "breakdown": breakdown,
        "progression": _build_progression_info(profile),
    }


# ============================================================================
# ENDPOINT 4: GET /profile
# ============================================================================


@router.get("/profile")
async def get_learning_profile(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Get user's current learning profile.
    Returns 404 if no profile has been setup yet.
    """
    user_id = current_user["uid"]
    profile = db["user_learning_profile"].find_one(
        {"user_id": user_id},
        projection={"_id": 0},
    )
    if not profile:
        raise HTTPException(
            status_code=404,
            detail="No learning profile. Call POST /learning-path/setup first.",
        )
    # Convert ObjectId if any
    profile.pop("_id", None)
    return profile


# ============================================================================
# ENDPOINT 5: DELETE /reset
# ============================================================================


@router.delete("/reset")
async def reset_learning_path(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Deactivate current path. User must call POST /setup again to get a new path.
    Preserves profile (goals, interests, progression level) and progress data.
    """
    user_id = current_user["uid"]
    now = datetime.utcnow()

    result = db["user_learning_path"].update_many(
        {"user_id": user_id, "is_active": True},
        {"$set": {"is_active": False, "updated_at": now}},
    )

    db["user_learning_profile"].update_one(
        {"user_id": user_id},
        {"$unset": {"active_path_id": ""}, "$set": {"updated_at": now}},
    )

    return {
        "reset": True,
        "paths_deactivated": result.modified_count,
        "message": "Path reset. Call POST /learning-path/setup to generate a new path.",
    }


# ============================================================================
# Helpers
# ============================================================================


def _build_progression_info(profile: dict) -> dict:
    """Build the progression level response block from a profile document."""
    prog_level = profile.get("progression_level", 1)
    level_info = PROGRESSION_LEVELS.get(prog_level, PROGRESSION_LEVELS[1])
    next_level_info = PROGRESSION_LEVELS.get(prog_level + 1)

    # Count conversations toward current progression level
    if prog_level == 1:
        convs_done = profile.get("l1_completed", 0)
        songs_done = profile.get("l1_songs_completed", 0)
    elif prog_level == 2:
        convs_done = profile.get("l2_completed", 0)
        songs_done = profile.get("l2_songs_completed", 0)
    else:
        convs_done = profile.get("l3_completed", 0)
        songs_done = profile.get("l3_songs_completed", 0)

    required_convs = level_info["conversations"]
    required_songs = level_info["songs"]

    info = {
        "level": prog_level,
        "level_name": level_info["name"],
        f"l{prog_level}_progress": {
            "conversations": convs_done,
            "required": required_convs,
            "songs": songs_done,
            "songs_required": required_songs,
        },
        "unlocked": convs_done >= required_convs and songs_done >= required_songs,
        "unlock_requirements": {
            "conversations_remaining": max(0, required_convs - convs_done),
            "songs_remaining": max(0, required_songs - songs_done),
        },
    }

    if next_level_info:
        info["next_level"] = next_level_info["name"]
    else:
        info["next_level"] = None
        info["max_level_reached"] = True

    return info
