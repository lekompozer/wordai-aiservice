"""
Conversation Detail & Practice Routes

Handles per-conversation endpoints (detail, vocabulary, gaps, submit, history,
save/unsave) plus user XP, achievements, limits, and practice tracking.

These routes share the same router object (prefix='/api/v1/conversations')
defined in conversation_learning_routes.py. This module is imported in
app.py AFTER registering conversation_learning_router so all the routes
below are registered on the same router instance.
"""

from fastapi import APIRouter, HTTPException, Depends, status, Request
from typing import Optional, Dict, Any, List
from datetime import datetime, date, timedelta
import uuid
import json
import logging
import asyncio
import base64
import re as _re

from src.database.db_manager import DBManager
from src.middleware.firebase_auth import get_current_user, get_current_user_optional

# ── Shared router & helpers from conversation_learning_routes ────────────────
from src.api.conversation_learning_routes import (
    router,
    get_db,
    get_redis,
    STREAK_CACHE_TTL,
    FREE_LIFETIME_LIMITS,
    check_user_premium,
    check_daily_limit,
    increment_daily_submit,
    is_conversation_accessed_today,
    _get_free_limits,
    _can_unlock,
    _increment_lifetime_unlock,
    calculate_xp_earned,
    update_user_xp,
    update_daily_streak,
    check_and_award_achievements,
)

logger = logging.getLogger(__name__)


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
# ENDPOINT: AI Sentence Check (Practice)
# POST /practice/check-sentence
# MUST stay above /{conversation_id} catch-all route
# ============================================================================

_AI_CHECK_DAILY_LIMIT_FREE = 10  # free users max per day


async def _get_ai_check_count_today(user_id: str, db) -> int:
    """Return how many AI checks this user has done today (UTC day)."""
    xp_col = db["user_learning_xp"]
    today = datetime.utcnow().date().isoformat()
    doc = xp_col.find_one(
        {"user_id": user_id}, {"ai_checks_date": 1, "ai_checks_today": 1, "_id": 0}
    )
    if not doc:
        return 0
    if doc.get("ai_checks_date", "") != today:
        return 0  # New day, counter not yet reset
    return doc.get("ai_checks_today", 0)


async def _increment_ai_check_count(user_id: str, db):
    """Increment the daily AI check counter (reset if new UTC day)."""
    xp_col = db["user_learning_xp"]
    today = datetime.utcnow().date().isoformat()
    xp_col.update_one(
        {"user_id": user_id},
        [
            {
                "$set": {
                    "ai_checks_today": {
                        "$cond": {
                            "if": {"$eq": ["$ai_checks_date", today]},
                            "then": {"$add": [{"$ifNull": ["$ai_checks_today", 0]}, 1]},
                            "else": 1,
                        }
                    },
                    "ai_checks_date": today,
                }
            }
        ],
        upsert=True,
    )


@router.post("/practice/check-sentence")
async def practice_check_sentence(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    AI-powered sentence check for grammar/vocabulary practice (Tự đặt câu).

    Request Body:
    - sentence (str, required): The sentence written or dictated by the user
    - mode (str, required): "text" → DeepSeek (1 XP) | "audio" → Gemini (2 XP)
    - pattern (str): Grammar pattern being practiced (one of pattern/word required)
    - word (str): Vocabulary word being practiced (one of pattern/word required)
    - conversation_id (str, optional): Source conversation for context tagging
    - audio_base64 (str): Required if mode="audio" — base64-encoded audio
    - audio_mime_type (str): Required if mode="audio" — e.g. "audio/webm"

    XP: text correct +1, audio correct +2, wrong -1 (floor at 0)
    Rate limit: free users 10 checks/day, premium unlimited
    """
    import asyncio
    import base64

    user_id = current_user["uid"]
    body = await request.json()

    sentence = body.get("sentence", "").strip()
    mode = body.get("mode", "text").strip().lower()
    pattern = body.get("pattern", "").strip()
    word = body.get("word", "").strip()
    conversation_id = body.get("conversation_id", "")
    audio_base64 = body.get("audio_base64", "")
    audio_mime_type = body.get("audio_mime_type", "audio/webm")

    if not sentence:
        raise HTTPException(status_code=400, detail="sentence is required")
    if not pattern and not word:
        raise HTTPException(status_code=400, detail="pattern or word is required")
    if mode not in ("text", "audio"):
        raise HTTPException(status_code=400, detail="mode must be 'text' or 'audio'")
    if mode == "audio" and not audio_base64:
        raise HTTPException(
            status_code=400, detail="audio_base64 is required when mode='audio'"
        )

    # ── Rate limiting (free users only) ─────────────────────────────────────
    is_premium = await check_user_premium(user_id, db)
    if not is_premium:
        checks_today = await _get_ai_check_count_today(user_id, db)
        if checks_today >= _AI_CHECK_DAILY_LIMIT_FREE:
            raise HTTPException(
                status_code=429,
                detail=f"AI check daily limit reached ({_AI_CHECK_DAILY_LIMIT_FREE}/day for free users). Upgrade to Premium for unlimited checks.",
            )

    # ── Build context label ──────────────────────────────────────────────────
    target_label = (
        f'grammar pattern "{pattern}"' if pattern else f'vocabulary word "{word}"'
    )

    is_correct = False
    feedback_vi = ""
    corrected_sentence = None
    transcribed_text = None

    if mode == "text":
        # ── DeepSeek text evaluation ─────────────────────────────────────────
        try:
            from openai import OpenAI as _OpenAI
            import os as _os

            _deepseek_key = _os.getenv("DEEPSEEK_API_KEY", "")
            if not _deepseek_key:
                raise HTTPException(
                    status_code=503, detail="DeepSeek API not configured"
                )

            system_prompt = (
                "You are an English teacher. Check if the user's sentence correctly uses "
                "the given pattern or word. Return ONLY valid JSON, no markdown."
            )
            user_prompt = (
                f'Pattern/Word: "{pattern or word}"\n'
                f'User sentence: "{sentence}"\n\n'
                "Return JSON:\n"
                '{"is_correct": true/false, "feedback_vi": "1-2 câu tiếng Việt", '
                '"corrected_sentence": null_or_corrected_string}'
            )

            def _call_deepseek():
                _client = _OpenAI(
                    api_key=_deepseek_key, base_url="https://api.deepseek.com/v1"
                )
                resp = _client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.3,
                    max_tokens=256,
                )
                return resp.choices[0].message.content.strip()

            raw = await asyncio.to_thread(_call_deepseek)

            # Parse JSON (strip markdown fences if present)
            import re as _re

            raw_clean = _re.sub(
                r"^```[a-z]*\n?|```$", "", raw.strip(), flags=_re.MULTILINE
            ).strip()
            result_json = json.loads(raw_clean)

            is_correct = bool(result_json.get("is_correct", False))
            feedback_vi = result_json.get("feedback_vi", "")
            corrected_sentence = result_json.get("corrected_sentence") or None

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"DeepSeek sentence check error: {e}")
            raise HTTPException(
                status_code=503, detail="AI service temporarily unavailable"
            )

    else:
        # ── Gemini audio evaluation ───────────────────────────────────────────
        try:
            import google.generativeai as genai_mod
            import os as _os

            _gemini_key = _os.getenv("GEMINI_API_KEY", "")
            if not _gemini_key:
                raise HTTPException(status_code=503, detail="Gemini API not configured")

            genai_mod.configure(api_key=_gemini_key)

            # Decode base64 audio
            try:
                audio_bytes = base64.b64decode(audio_base64)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid base64 audio data")

            prompt = (
                f"The learner is practicing the {target_label}.\n"
                f"1. Transcribe exactly what was said in the audio.\n"
                f"2. Check if the transcribed sentence correctly uses {target_label}.\n"
                f"3. Return ONLY valid JSON (no markdown):\n"
                '{"transcribed_text": "...", "is_correct": true/false, '
                '"feedback_vi": "1-2 câu tiếng Việt", "corrected_sentence": null_or_corrected_string}'
            )

            def _call_gemini():
                _model = genai_mod.GenerativeModel("gemini-2.5-flash")
                response = _model.generate_content(
                    [
                        {"mime_type": audio_mime_type, "data": audio_bytes},
                        prompt,
                    ]
                )
                return response.text.strip()

            raw = await asyncio.to_thread(_call_gemini)

            import re as _re

            raw_clean = _re.sub(
                r"^```[a-z]*\n?|```$", "", raw.strip(), flags=_re.MULTILINE
            ).strip()
            result_json = json.loads(raw_clean)

            is_correct = bool(result_json.get("is_correct", False))
            feedback_vi = result_json.get("feedback_vi", "")
            corrected_sentence = result_json.get("corrected_sentence") or None
            transcribed_text = result_json.get("transcribed_text") or sentence

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Gemini audio sentence check error: {e}")
            raise HTTPException(
                status_code=503, detail="AI service temporarily unavailable"
            )

    # ── XP change ────────────────────────────────────────────────────────────
    if is_correct:
        xp_delta = 2 if mode == "audio" else 1
    else:
        xp_delta = -1  # update_user_xp floors at 0

    xp_result = await update_user_xp(
        user_id=user_id,
        xp_earned=xp_delta,
        reason=f"practice_{'audio' if mode == 'audio' else 'text'}_{'correct' if is_correct else 'wrong'}",
        conversation_id=conversation_id or "",
        difficulty="practice",
        score=100.0 if is_correct else 0.0,
        db=db,
    )

    # ── Increment daily counter ───────────────────────────────────────────────
    await _increment_ai_check_count(user_id, db)

    response_data: Dict[str, Any] = {
        "is_correct": is_correct,
        "feedback_vi": feedback_vi,
        "corrected_sentence": corrected_sentence,
        "xp_change": xp_result.get("xp_earned", xp_delta),
        "new_total_xp": xp_result.get("total_xp", 0),
        "mode": mode,
    }
    if transcribed_text:
        response_data["transcribed_text"] = transcribed_text

    return response_data


# ============================================================================
# ENDPOINT: Vocabulary Practice Result
# POST /practice/vocabulary/result
# MUST stay above /{conversation_id} catch-all route
# ============================================================================


@router.post("/practice/vocabulary/result")
async def practice_vocabulary_result(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Submit the result of a vocabulary practice session.

    Request Body:
    - conversation_id (str, required): Source conversation
    - score_percent (number, required): Score 0-100
    - total_words (number, optional): Total words in the exercise
    - correct_words (number, optional): Words answered correctly

    XP: >=80% → +3, 50-79% → +1, <50% → 0

    Returns: {xp_change, new_total_xp, practice_type, score_percent, result_id}
    """
    user_id = current_user["uid"]
    body = await request.json()

    conversation_id = body.get("conversation_id", "").strip()
    score_percent = body.get("score_percent")
    total_words = body.get("total_words", 0)
    correct_words = body.get("correct_words", 0)

    if not conversation_id:
        raise HTTPException(status_code=400, detail="conversation_id is required")
    if score_percent is None:
        raise HTTPException(status_code=400, detail="score_percent is required")
    try:
        score_percent = float(score_percent)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="score_percent must be a number")
    score_percent = max(0.0, min(100.0, score_percent))

    # ── XP tiers ─────────────────────────────────────────────────────────────
    if score_percent >= 80:
        xp_delta = 3
    elif score_percent >= 50:
        xp_delta = 1
    else:
        xp_delta = 0

    result_id = str(uuid.uuid4())
    now = datetime.utcnow()

    # Log practice result
    db["user_practice_results"].insert_one(
        {
            "result_id": result_id,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "practice_type": "vocabulary",
            "score_percent": score_percent,
            "total_questions": total_words,
            "correct_answers": correct_words,
            "xp_earned": xp_delta,
            "completed_at": now,
        }
    )

    xp_result: Dict[str, Any] = {}
    if xp_delta > 0:
        xp_result = await update_user_xp(
            user_id=user_id,
            xp_earned=xp_delta,
            reason="vocabulary_practice",
            conversation_id=conversation_id,
            difficulty="practice",
            score=score_percent,
            db=db,
        )

    return {
        "xp_change": xp_delta,
        "new_total_xp": xp_result.get("total_xp", 0),
        "practice_type": "vocabulary",
        "score_percent": score_percent,
        "result_id": result_id,
    }


# ============================================================================
# ENDPOINT: Grammar Quick Challenge Result
# POST /practice/grammar/result
# MUST stay above /{conversation_id} catch-all route
# ============================================================================


@router.post("/practice/grammar/result")
async def practice_grammar_result(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Submit the result of a grammar quick challenge session.

    Practice types:
    - unscramble: Click-to-place words in correct order
    - match: Match grammar patterns to their explanations
    - fill_blank: Multiple-choice gap fill from example sentence

    Request Body:
    - conversation_id (str, required): Source conversation
    - practice_type (str, required): "unscramble" | "match" | "fill_blank"
    - score_percent (number, required): Score 0-100
    - total_questions (number, optional): Total questions
    - correct_answers (number, optional): Correct answers count

    XP: >=80% → +3, 50-79% → +1, <50% → 0

    Returns: {xp_change, new_total_xp, practice_type, score_percent, result_id}
    """
    user_id = current_user["uid"]
    body = await request.json()

    conversation_id = body.get("conversation_id", "").strip()
    practice_type = body.get("practice_type", "").strip().lower()
    score_percent = body.get("score_percent")
    total_questions = body.get("total_questions", 0)
    correct_answers = body.get("correct_answers", 0)

    if not conversation_id:
        raise HTTPException(status_code=400, detail="conversation_id is required")
    if practice_type not in ("unscramble", "match", "fill_blank"):
        raise HTTPException(
            status_code=400,
            detail="practice_type must be 'unscramble', 'match', or 'fill_blank'",
        )
    if score_percent is None:
        raise HTTPException(status_code=400, detail="score_percent is required")
    try:
        score_percent = float(score_percent)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="score_percent must be a number")
    score_percent = max(0.0, min(100.0, score_percent))

    # ── XP tiers ─────────────────────────────────────────────────────────────
    if score_percent >= 80:
        xp_delta = 3
    elif score_percent >= 50:
        xp_delta = 1
    else:
        xp_delta = 0

    result_id = str(uuid.uuid4())
    now = datetime.utcnow()

    db["user_practice_results"].insert_one(
        {
            "result_id": result_id,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "practice_type": f"grammar_{practice_type}",
            "score_percent": score_percent,
            "total_questions": total_questions,
            "correct_answers": correct_answers,
            "xp_earned": xp_delta,
            "completed_at": now,
        }
    )

    xp_result: Dict[str, Any] = {}
    if xp_delta > 0:
        xp_result = await update_user_xp(
            user_id=user_id,
            xp_earned=xp_delta,
            reason=f"grammar_practice_{practice_type}",
            conversation_id=conversation_id,
            difficulty="practice",
            score=score_percent,
            db=db,
        )

    return {
        "xp_change": xp_delta,
        "new_total_xp": xp_result.get("total_xp", 0),
        "practice_type": practice_type,
        "score_percent": score_percent,
        "result_id": result_id,
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
    For free users:
    - First time playing a NEW conversation: checks daily + lifetime limits, increments both counters
    - Replaying same conversation: FREE (unlimited replays of unlocked conversations)
    """
    user_id = current_user["uid"]
    is_premium = await check_user_premium(user_id, db)

    if is_premium:
        return {"ok": True, "premium": True}

    # CRITICAL: If user already has a progress record, conversation is UNLOCKED → replay is FREE
    # This allows unlimited play/submit of same conversation after first unlock
    has_prior = db["user_conversation_progress"].find_one(
        {"user_id": user_id, "conversation_id": conversation_id}
    )
    if has_prior:
        return {"ok": True, "already_unlocked": True}

    # New conversation — check daily limit (3 unique conversations/day)
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

    # Check lifetime limit for this level (15 beginner, 5 intermediate, 5 advanced)
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

    # CRITICAL: Increment lifetime counter when unlocking NEW conversation
    await _increment_lifetime_unlock(user_id, level, db)

    # Create progress record to mark conversation as UNLOCKED
    # This prevents double-counting when user submits later
    db["user_conversation_progress"].update_one(
        {"user_id": user_id, "conversation_id": conversation_id},
        {
            "$setOnInsert": {
                "user_id": user_id,
                "conversation_id": conversation_id,
                "first_attempt_at": datetime.utcnow(),
                "created_at": datetime.utcnow(),
                "total_attempts": 0,
                "total_time_spent": 0,
            },
            "$set": {
                "updated_at": datetime.utcnow(),
            },
        },
        upsert=True,
    )

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
    # IMPORTANT: Query progress record ONCE and reuse to avoid race condition
    has_prior_progress = None
    conv_level = None

    if not limit_info["is_premium"]:
        # Single query for progress record - store result for reuse
        has_prior_progress = db["user_conversation_progress"].find_one(
            {"user_id": user_id, "conversation_id": conversation_id}
        )

        # CRITICAL: Check lifetime limit for NEW conversations (no progress record yet)
        # If progress record exists, conversation was already unlocked (by play or previous submit) → no need to check/increment
        if not has_prior_progress:
            # Get conversation level once
            conv_meta = db["conversation_library"].find_one(
                {"conversation_id": conversation_id}, {"level": 1}
            )
            conv_level = conv_meta.get("level", "beginner") if conv_meta else "beginner"

            # ALWAYS check lifetime limit for new conversations
            if not await _can_unlock(user_id, conv_level, db):
                raise HTTPException(
                    status_code=403,
                    detail=f"Lifetime limit reached for {conv_level} conversations. Upgrade to Premium for unlimited access.",
                )

    # Increment daily submit count (free users only)
    await increment_daily_submit(user_id, db, conversation_id=conversation_id)

    # On first-ever attempt for this conversation, increment lifetime unlock counter
    # CRITICAL FIX: Reuse has_prior_progress from above - DO NOT query again!
    if not limit_info["is_premium"] and not has_prior_progress:
        # Reuse conv_level from above if available, otherwise fetch
        if conv_level is None:
            conv_meta = db["conversation_library"].find_one(
                {"conversation_id": conversation_id}, {"level": 1}
            )
            conv_level = conv_meta.get("level", "beginner") if conv_meta else "beginner"

        await _increment_lifetime_unlock(user_id, conv_level, db)

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


# ============================================================================
# ENDPOINT: Save Vocabulary Word
# ============================================================================


@router.post("/{conversation_id}/vocabulary/save")
async def save_vocabulary(
    conversation_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Save a vocabulary word from a specific conversation.

    Request Body:
    - word (str, required): The word to save
    - pos_tag (str, required): Part-of-speech tag (e.g. "ADJ", "NOUN")
    - definition_en (str, required): English definition
    - definition_vi (str, required): Vietnamese definition
    - example (str, required): Example sentence
    - definition_zh (str, optional): Chinese definition
    - definition_ja (str, optional): Japanese definition
    - definition_ko (str, optional): Korean definition

    Returns:
    - {saved: true, save_id, next_review_date} on first save
    - {already_saved: true, save_id, next_review_date} if already saved
    """
    user_id = current_user["uid"]
    body = await request.json()

    word = body.get("word", "").strip()
    if not word:
        raise HTTPException(status_code=400, detail="word is required")

    pos_tag = body.get("pos_tag", "").strip()
    definition_en = body.get("definition_en", "").strip()
    definition_vi = body.get("definition_vi", "").strip()
    example = body.get("example", "").strip()

    if not definition_en or not definition_vi or not example:
        raise HTTPException(
            status_code=400,
            detail="definition_en, definition_vi, and example are required",
        )

    col = db["user_saved_vocabulary"]

    # Check if already saved
    existing = col.find_one(
        {"user_id": user_id, "word": word},
        {"_id": 0, "save_id": 1, "next_review_date": 1},
    )
    if existing:
        next_review = existing.get("next_review_date")
        next_review_str = (
            next_review.date().isoformat()
            if isinstance(next_review, datetime)
            else str(next_review)
        )
        return {
            "already_saved": True,
            "save_id": existing["save_id"],
            "word": word,
            "next_review_date": next_review_str,
        }

    # Fetch conversation metadata for denormalization
    conv = db["conversation_library"].find_one(
        {"conversation_id": conversation_id},
        {"_id": 0, "topic_slug": 1, "topic": 1, "level": 1},
    )
    topic_slug = conv.get("topic_slug", "") if conv else ""
    topic_en = (conv.get("topic") or {}).get("en", "") if conv else ""
    level = conv.get("level", "") if conv else ""

    now = datetime.utcnow()
    next_review_date = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    save_id = str(uuid.uuid4())

    doc = {
        "save_id": save_id,
        "user_id": user_id,
        "word": word,
        "pos_tag": pos_tag,
        "definition_en": definition_en,
        "definition_vi": definition_vi,
        "definition_zh": body.get("definition_zh"),
        "definition_ja": body.get("definition_ja"),
        "definition_ko": body.get("definition_ko"),
        "example": example,
        "conversation_id": conversation_id,
        "topic_slug": topic_slug,
        "topic_en": topic_en,
        "level": level,
        "review_count": 0,
        "correct_count": 0,
        "next_review_date": next_review_date,
        "saved_at": now,
        "updated_at": now,
    }

    try:
        col.insert_one(doc)
    except Exception:
        # Race condition: another request saved first
        existing = col.find_one(
            {"user_id": user_id, "word": word},
            {"_id": 0, "save_id": 1, "next_review_date": 1},
        )
        if existing:
            next_review = existing.get("next_review_date")
            next_review_str = (
                next_review.date().isoformat()
                if isinstance(next_review, datetime)
                else str(next_review)
            )
            return {
                "already_saved": True,
                "save_id": existing["save_id"],
                "word": word,
                "next_review_date": next_review_str,
            }
        raise HTTPException(status_code=500, detail="Failed to save vocabulary")

    return {
        "saved": True,
        "save_id": save_id,
        "word": word,
        "next_review_date": next_review_date.date().isoformat(),
    }


# ============================================================================
# ENDPOINT: Unsave Vocabulary Word
# ============================================================================


@router.delete("/{conversation_id}/vocabulary/{word}/save")
async def unsave_vocabulary(
    conversation_id: str,
    word: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Remove a saved vocabulary word.

    Path Parameters:
    - conversation_id: The conversation the word came from
    - word: The word to unsave (URL-encoded)

    Returns: {message, word}
    """
    user_id = current_user["uid"]

    col = db["user_saved_vocabulary"]
    result = col.delete_one({"user_id": user_id, "word": word})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Saved vocabulary not found")

    return {
        "message": "Vocabulary removed from saved list",
        "word": word,
    }


# ============================================================================
# ENDPOINT: Save Grammar Pattern
# ============================================================================


@router.post("/{conversation_id}/grammar/save")
async def save_grammar(
    conversation_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Save a grammar pattern from a specific conversation.

    Request Body:
    - pattern (str, required): Grammar pattern (e.g. "I feel like + clause")
    - explanation_en (str, required): English explanation
    - explanation_vi (str, required): Vietnamese explanation
    - example (str, required): Example sentence
    - explanation_zh (str, optional): Chinese explanation
    - explanation_ja (str, optional): Japanese explanation
    - explanation_ko (str, optional): Korean explanation

    Returns:
    - {saved: true, save_id, next_review_date} on first save
    - {already_saved: true, save_id, next_review_date} if already saved
    """
    user_id = current_user["uid"]
    body = await request.json()

    pattern = body.get("pattern", "").strip()
    if not pattern:
        raise HTTPException(status_code=400, detail="pattern is required")

    explanation_en = body.get("explanation_en", "").strip()
    explanation_vi = body.get("explanation_vi", "").strip()
    example = body.get("example", "").strip()

    if not explanation_en or not explanation_vi or not example:
        raise HTTPException(
            status_code=400,
            detail="explanation_en, explanation_vi, and example are required",
        )

    col = db["user_saved_grammar"]

    existing = col.find_one(
        {"user_id": user_id, "pattern": pattern},
        {"_id": 0, "save_id": 1, "next_review_date": 1},
    )
    if existing:
        next_review = existing.get("next_review_date")
        next_review_str = (
            next_review.date().isoformat()
            if isinstance(next_review, datetime)
            else str(next_review)
        )
        return {
            "already_saved": True,
            "save_id": existing["save_id"],
            "pattern": pattern,
            "next_review_date": next_review_str,
        }

    # Fetch conversation metadata for denormalization
    conv = db["conversation_library"].find_one(
        {"conversation_id": conversation_id},
        {"_id": 0, "topic_slug": 1, "topic": 1, "level": 1},
    )
    topic_slug = conv.get("topic_slug", "") if conv else ""
    topic_en = (conv.get("topic") or {}).get("en", "") if conv else ""
    level = conv.get("level", "") if conv else ""

    now = datetime.utcnow()
    next_review_date = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    save_id = str(uuid.uuid4())

    doc = {
        "save_id": save_id,
        "user_id": user_id,
        "pattern": pattern,
        "explanation_en": explanation_en,
        "explanation_vi": explanation_vi,
        "explanation_zh": body.get("explanation_zh"),
        "explanation_ja": body.get("explanation_ja"),
        "explanation_ko": body.get("explanation_ko"),
        "example": example,
        "conversation_id": conversation_id,
        "topic_slug": topic_slug,
        "topic_en": topic_en,
        "level": level,
        "review_count": 0,
        "correct_count": 0,
        "next_review_date": next_review_date,
        "saved_at": now,
        "updated_at": now,
    }

    try:
        col.insert_one(doc)
    except Exception:
        existing = col.find_one(
            {"user_id": user_id, "pattern": pattern},
            {"_id": 0, "save_id": 1, "next_review_date": 1},
        )
        if existing:
            next_review = existing.get("next_review_date")
            next_review_str = (
                next_review.date().isoformat()
                if isinstance(next_review, datetime)
                else str(next_review)
            )
            return {
                "already_saved": True,
                "save_id": existing["save_id"],
                "pattern": pattern,
                "next_review_date": next_review_str,
            }
        raise HTTPException(status_code=500, detail="Failed to save grammar")

    return {
        "saved": True,
        "save_id": save_id,
        "pattern": pattern,
        "next_review_date": next_review_date.date().isoformat(),
    }


# ============================================================================
# ENDPOINT: Unsave Grammar Pattern
# ============================================================================


@router.delete("/{conversation_id}/grammar/save")
async def unsave_grammar(
    conversation_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Remove a saved grammar pattern.

    Request Body:
    - pattern (str, required): The grammar pattern to unsave

    Returns: {message, pattern}
    """
    user_id = current_user["uid"]
    body = await request.json()

    pattern = body.get("pattern", "").strip()
    if not pattern:
        raise HTTPException(
            status_code=400, detail="pattern is required in request body"
        )

    col = db["user_saved_grammar"]
    result = col.delete_one({"user_id": user_id, "pattern": pattern})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Saved grammar not found")

    return {
        "message": "Grammar pattern removed from saved list",
        "pattern": pattern,
    }
