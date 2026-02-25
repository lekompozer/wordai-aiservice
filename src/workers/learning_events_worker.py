"""
Learning Events Worker
======================
Listens to Redis queue "learning_events" and handles all NEW gamification
side-effects introduced in Phase 1+:

  - gap_submitted  → update gap_completed / gap_best_score / gap_difficulty
                     check dual-part completion → set is_completed
  - test_submitted → update test_completed / test_best_score
                     check dual-part completion → set is_completed
                     award test XP + streak + achievements
  - song_completed → update l{n}_songs_completed in user_learning_profile (Phase 3)

NOTE: Existing synchronous XP/streak/achievements (from gap_submitted) are
still handled inside the API handler for backward compatibility. This worker
handles the NEW Phase 1 dual-part completion fields and test-side effects.
"""

import asyncio
import json
import logging
import signal
import uuid
from datetime import datetime, date, timedelta

from src.database.db_manager import DBManager
from src.queue.queue_manager import QueueManager
from src.workers.payment_events_worker import _handle_conversation_subscription_paid

logger = logging.getLogger(__name__)

QUEUE_NAME = "learning_events"
PAYMENT_QUEUE_NAME = "payment_events"
REDIS_URL = "redis://redis-server:6379"

# ── XP Tables (same formula as API handler) ──────────────────────────────────
XP_BASE_GAP = {"easy": 5, "medium": 10, "hard": 15}

# Test XP = round(gap_base * 3/7)  →  easy=2, medium=4, hard=6
XP_BASE_TEST = {k: round(v * 3 / 7) for k, v in XP_BASE_GAP.items()}

LEVEL_THRESHOLDS = [
    (0, 1, "Novice"),
    (50, 2, "Learner"),
    (150, 3, "Practitioner"),
    (300, 4, "Proficient"),
    (500, 5, "Advanced"),
    (800, 6, "Expert"),
    (1200, 7, "Master"),
    (2000, 8, "Legend"),
]

STREAK_CACHE_TTL = 3600


# ── XP helpers ────────────────────────────────────────────────────────────────


def _calc_xp(base: int, score: float, is_first_attempt: bool) -> int:
    """Deterministic XP formula used by both API (provisional) and worker (actual)."""
    if score < 80:
        return 0
    bonus = 0
    if score == 100:
        bonus += 10 + 2  # score bonus + perfect bonus
    elif score >= 90:
        bonus += 5
    elif score >= 80:
        bonus += 3
    if is_first_attempt:
        bonus += 2
    return base + bonus


# ─────────────────────────────────────────────────────────────────────────────
# DB helpers (pure sync — worker uses sync motor pattern like other workers)
# ─────────────────────────────────────────────────────────────────────────────


def _update_user_xp(
    db,
    user_id: str,
    xp_earned: int,
    reason: str,
    conversation_id: str,
    difficulty: str,
    score: float,
):
    """Upsert user_learning_xp and return level-up info."""
    if xp_earned <= 0:
        return None
    xp_col = db["user_learning_xp"]
    user_xp = xp_col.find_one({"user_id": user_id})
    old_xp = user_xp.get("total_xp", 0) if user_xp else 0
    old_level = user_xp.get("level", 1) if user_xp else 1
    new_xp = old_xp + xp_earned

    new_level, level_name = 1, "Novice"
    for threshold, lvl, name in LEVEL_THRESHOLDS:
        if new_xp >= threshold:
            new_level, level_name = lvl, name

    xp_col.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "total_xp": new_xp,
                "level": new_level,
                "level_name": level_name,
                "updated_at": datetime.utcnow(),
            },
            "$push": {
                "xp_history": {
                    "earned_xp": xp_earned,
                    "reason": reason,
                    "conversation_id": conversation_id,
                    "difficulty": difficulty,
                    "score": score,
                    "timestamp": datetime.utcnow(),
                }
            },
            "$setOnInsert": {
                "xp_id": str(uuid.uuid4()),
                "user_id": user_id,
                "created_at": datetime.utcnow(),
            },
        },
        upsert=True,
    )
    return {
        "xp_earned": xp_earned,
        "total_xp": new_xp,
        "level": new_level,
        "leveled_up": new_level > old_level,
    }


def _update_streak(
    db, redis_client, user_id: str, score: float, activity_type: str, activity_id: str
):
    """Replicate streak logic from API handler (sync version for worker)."""
    streak_col = db["user_learning_streak"]
    today = date.today()
    today_str = today.isoformat()
    new_activity = {
        "type": activity_type,
        "id": activity_id,
        "score": score,
        "completed_at": datetime.utcnow(),
    }

    existing_today = streak_col.find_one({"user_id": user_id, "date": today_str})
    if existing_today:
        streak_col.update_one(
            {"user_id": user_id, "date": today_str},
            {
                "$addToSet": {"activities": new_activity},
                "$set": {"updated_at": datetime.utcnow()},
            },
        )
        return

    yesterday_str = (today - timedelta(days=1)).isoformat()
    yesterday_record = streak_col.find_one({"user_id": user_id, "date": yesterday_str})

    if yesterday_record:
        current_streak = yesterday_record.get("current_streak", 1) + 1
        longest_streak = max(yesterday_record.get("longest_streak", 1), current_streak)
    else:
        latest = streak_col.find_one({"user_id": user_id}, sort=[("date", -1)])
        current_streak = 1
        longest_streak = latest.get("longest_streak", 1) if latest else 1

    streak_col.insert_one(
        {
            "streak_id": str(uuid.uuid4()),
            "user_id": user_id,
            "date": today_str,
            "current_streak": current_streak,
            "longest_streak": longest_streak,
            "activities": [new_activity],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
    )

    # Invalidate Redis streak cache
    if redis_client:
        try:
            cache_key = f"streak:{user_id}"
            redis_client.delete(cache_key)
        except Exception:
            pass


def _award_achievements(
    db, user_id: str, conversation_id: str, score: float, difficulty: str, source: str
):
    """Check and award achievements. Called for test submissions."""
    achievements_col = db["user_learning_achievements"]
    progress_col = db["user_conversation_progress"]
    conv_col = db["conversation_library"]
    newly_earned = []

    total_completed = progress_col.count_documents(
        {"user_id": user_id, "is_completed": True}
    )

    completion_achievements = [
        (1, "first_steps", "First Steps", "completion", 1),
        (5, "getting_started", "Getting Started", "completion", 10),
        (20, "dedicated_learner", "Dedicated Learner", "completion", 25),
        (50, "consistent_practice", "Consistent Practice", "completion", 50),
        (100, "century_club", "Century Club", "completion", 100),
    ]

    for threshold, ach_id, ach_name, ach_type, xp_bonus in completion_achievements:
        if total_completed >= threshold:
            if not achievements_col.find_one(
                {"user_id": user_id, "achievement_id": ach_id}
            ):
                doc = {
                    "user_achievement_id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "achievement_id": ach_id,
                    "achievement_name": ach_name,
                    "achievement_type": ach_type,
                    "xp_bonus": xp_bonus,
                    "earned_at": datetime.utcnow(),
                }
                achievements_col.insert_one(doc)
                newly_earned.append(doc)
                _update_user_xp(
                    db,
                    user_id,
                    xp_bonus,
                    f"Achievement: {ach_name}",
                    conversation_id,
                    difficulty,
                    score,
                )

    if score == 100 and not achievements_col.find_one(
        {"user_id": user_id, "achievement_id": "perfect_score"}
    ):
        doc = {
            "user_achievement_id": str(uuid.uuid4()),
            "user_id": user_id,
            "achievement_id": "perfect_score",
            "achievement_name": "Perfect Score",
            "achievement_type": "performance",
            "xp_bonus": 20,
            "earned_at": datetime.utcnow(),
        }
        achievements_col.insert_one(doc)
        newly_earned.append(doc)
        _update_user_xp(
            db,
            user_id,
            20,
            "Achievement: Perfect Score",
            conversation_id,
            difficulty,
            score,
        )

    # Topic mastery check
    conv = conv_col.find_one({"conversation_id": conversation_id})
    if conv:
        topic_number = conv["topic_number"]
        level = conv["level"]
        topic_convs = list(
            conv_col.find(
                {"topic_number": topic_number, "level": level}, {"conversation_id": 1}
            )
        )
        topic_conv_ids = [c["conversation_id"] for c in topic_convs]
        completed_in_topic = progress_col.count_documents(
            {
                "user_id": user_id,
                "conversation_id": {"$in": topic_conv_ids},
                "is_completed": True,
            }
        )
        if completed_in_topic == len(topic_conv_ids):
            ach_id = f"topic_{level}_{topic_number}_master"
            if not achievements_col.find_one(
                {"user_id": user_id, "achievement_id": ach_id}
            ):
                topic_name = conv["topic"]["en"]
                doc = {
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
                achievements_col.insert_one(doc)
                newly_earned.append(doc)
                _update_user_xp(
                    db,
                    user_id,
                    50,
                    f"Achievement: {topic_name} Master",
                    conversation_id,
                    difficulty,
                    score,
                )

    return newly_earned


def _award_progression_achievement(
    db,
    user_id: str,
    ach_id: str,
    ach_name: str,
    xp_bonus: int,
    conversation_id: str,
    difficulty: str,
):
    """Insert a progression achievement and award XP if not already earned."""
    achievements_col = db["user_learning_achievements"]
    if achievements_col.find_one({"user_id": user_id, "achievement_id": ach_id}):
        return  # Already earned
    doc = {
        "user_achievement_id": str(uuid.uuid4()),
        "user_id": user_id,
        "achievement_id": ach_id,
        "achievement_name": ach_name,
        "achievement_type": "progression",
        "xp_bonus": xp_bonus,
        "earned_at": datetime.utcnow(),
    }
    achievements_col.insert_one(doc)
    _update_user_xp(
        db,
        user_id,
        xp_bonus,
        f"Achievement: {ach_name}",
        conversation_id,
        difficulty,
        0,
    )
    logger.info(f"[progression_achievement] user={user_id} ach={ach_id} xp={xp_bonus}")


def _check_progression_level_up(
    db, user_id: str, profile: dict, conversation_id: str, difficulty: str
):
    """
    Check if the user qualifies for a progression level-up and award
    the corresponding achievement.  Called after any progression counter update.
    """
    level = profile.get("progression_level", 1)

    if level >= 3:
        # Max level — only check for Addict achievement
        if (
            profile.get("l3_completed", 0) >= 100
            and profile.get("l3_songs_completed", 0) >= 10
        ):
            _award_progression_achievement(
                db,
                user_id,
                "level_3_addict",
                "Addict",
                1000,
                conversation_id,
                difficulty,
            )
        return

    lk = f"l{level}"
    convs_done = profile.get(f"{lk}_completed", 0)
    songs_done = profile.get(f"{lk}_songs_completed", 0)

    if convs_done >= 100 and songs_done >= 10:
        new_level = level + 1
        ach_map = {
            1: ("level_1_initiate", "Initiate", 200),
            2: ("level_2_scholar", "Scholar", 500),
        }
        ach_id, ach_name, ach_xp = ach_map[level]

        # Promote user to next level
        db["user_learning_profile"].update_one(
            {"user_id": user_id},
            {"$set": {"progression_level": new_level, "updated_at": datetime.utcnow()}},
        )
        logger.info(f"[progression_levelup] user={user_id} level {level}→{new_level}")

        _award_progression_achievement(
            db, user_id, ach_id, ach_name, ach_xp, conversation_id, difficulty
        )


def _update_progression_counter(
    db, user_id: str, conversation_id: str, difficulty: str
):
    """
    Phase 3: Level-gated progression counter.

    Triggered by: first successful gap fill (score ≥ 80) per conversation.
    Deduped via l{n}_counted_convs list — each conversation counts once.

    Level rules:
      l1 (level 1) — any difficulty counts
      l2 (level 2) — medium or hard only
      l3 (level 3) — hard only

    After incrementing, checks for level-up (100 convos + 10 songs).
    Also marks the path item as completed.
    """
    profile_col = db["user_learning_profile"]
    path_col = db["user_learning_path"]

    profile = profile_col.find_one({"user_id": user_id})
    if not profile:
        return  # User hasn't set up Phase 2 profile yet — skip silently

    level = profile.get("progression_level", 1)
    counted_key = f"l{level}_counted_convs"

    # Dedup: each conversation counts once per progression level
    counted = profile.get(counted_key, [])
    if conversation_id in counted:
        logger.info(
            f"[progression] user={user_id} conv={conversation_id} already counted — skip"
        )
        return

    now = datetime.utcnow()
    inc = {}

    if level == 1:
        # L1: any difficulty qualifies
        inc["l1_completed"] = 1
    elif level == 2:
        # L2: only medium or hard
        if difficulty in ("medium", "hard"):
            inc["l2_completed"] = 1
    elif level == 3:
        # L3: hard only
        if difficulty == "hard":
            inc["l3_completed"] = 1

    if inc:
        profile_col.update_one(
            {"user_id": user_id},
            {
                "$inc": inc,
                "$push": {counted_key: conversation_id},
                "$set": {"updated_at": now},
            },
        )
        # Re-read to check level-up with latest counters
        updated_profile = profile_col.find_one({"user_id": user_id})
        if updated_profile:
            _check_progression_level_up(
                db, user_id, updated_profile, conversation_id, difficulty
            )
    else:
        # Difficulty doesn't qualify for this level — still record as seen to avoid re-processing
        profile_col.update_one(
            {"user_id": user_id},
            {"$push": {counted_key: conversation_id}, "$set": {"updated_at": now}},
        )

    # Mark path item as completed in active path
    path_col.update_one(
        {
            "user_id": user_id,
            "is_active": True,
            "path_items.conversation_id": conversation_id,
        },
        {
            "$set": {
                "path_items.$.completed": True,
                "path_items.$.completed_at": now,
                "updated_at": now,
            },
            "$inc": {"completed_count": 1},
        },
    )

    logger.info(
        f"[progression] user={user_id} conv={conversation_id} "
        f"level={level} difficulty={difficulty} inc={inc}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Event Handlers
# ─────────────────────────────────────────────────────────────────────────────


def _handle_gap_submitted(db, redis_client, event: dict):
    """
    Worker side-effects for gap_submitted event.

    The API handler already:
      - saved the attempt doc
      - updated best_scores / total_attempts (progress)
      - ran XP + streak + achievements (synchronous, for backward compat)

    Worker handles NEW Phase 1 fields:
      - gap_completed, gap_best_score, gap_difficulty
      - is_completed dual-part check (gap + test both done)
      - completion_count increment
    """
    user_id = event["user_id"]
    conversation_id = event["conversation_id"]
    difficulty = event["difficulty"]
    score = event["score"]
    is_passed = score >= 80.0

    if not is_passed:
        return  # No gamification side-effects on fail

    progress_col = db["user_conversation_progress"]

    existing = progress_col.find_one(
        {"user_id": user_id, "conversation_id": conversation_id},
        projection={
            "gap_completed": 1,
            "gap_best_score": 1,
            "test_completed": 1,
            "completion_count": 1,
        },
    )

    # Update gap completion fields
    gap_update = {"$set": {}}
    already_gap_completed = existing.get("gap_completed", False) if existing else False

    if not already_gap_completed or score > (existing or {}).get("gap_best_score", 0):
        gap_update["$set"]["gap_completed"] = True
        gap_update["$set"]["gap_best_score"] = score
        gap_update["$set"]["gap_difficulty"] = difficulty

    test_done = existing.get("test_completed", False) if existing else False
    new_gap_done = True  # we just passed

    if new_gap_done and test_done:
        # Both parts complete → mark unit as fully_completed
        gap_update["$set"]["is_completed"] = True
        gap_update["$inc"] = {"completion_count": 1}

    if gap_update["$set"]:
        progress_col.update_one(
            {"user_id": user_id, "conversation_id": conversation_id},
            gap_update,
        )
        logger.info(
            f"[gap_submitted] user={user_id} conv={conversation_id} "
            f"gap_completed=True already_was={already_gap_completed}"
        )
        # Progression: triggered by first successful gap pass per conversation
        if not already_gap_completed:
            _update_progression_counter(db, user_id, conversation_id, difficulty)


def _handle_test_submitted(db, redis_client, event: dict):
    """
    Worker side-effects for test_submitted event.

    The test submit endpoint is NEW (Phase 1), so there is no existing
    synchronous handler. Worker does everything:
      - update test_completed / test_best_score
      - dual-part completion check → is_completed
      - award test XP
      - update streak
      - check achievements
    """
    user_id = event["user_id"]
    conversation_id = event["conversation_id"]
    test_id = event.get("test_id", "")
    score = event["score"]
    is_passed = score >= 80.0
    is_first_attempt = event.get("is_first_attempt", False)
    time_spent = event.get("time_spent", 0)

    progress_col = db["user_conversation_progress"]
    existing = progress_col.find_one(
        {"user_id": user_id, "conversation_id": conversation_id},
        projection={
            "gap_completed": 1,
            "gap_difficulty": 1,
            "test_completed": 1,
            "test_best_score": 1,
            "completion_count": 1,
        },
    )

    gap_done = existing.get("gap_completed", False) if existing else False
    gap_difficulty = existing.get("gap_difficulty", "easy") if existing else "easy"
    prev_test_best = existing.get("test_best_score", 0) if existing else 0
    is_best = score > prev_test_best

    # Always update attempt count + time
    test_update: dict = {
        "$inc": {
            "total_attempts": 1,
            "total_time_spent": time_spent,
        },
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

    if is_passed:
        test_update["$set"]["test_completed"] = True
        if is_best:
            test_update["$set"]["test_best_score"] = score
            test_update["$set"]["test_id"] = test_id

        if gap_done:
            test_update["$set"]["is_completed"] = True
            if "$inc" not in test_update:
                test_update["$inc"] = {}
            test_update["$inc"]["completion_count"] = 1

    progress_col.update_one(
        {"user_id": user_id, "conversation_id": conversation_id},
        test_update,
        upsert=True,
    )

    # Streak update (any activity)
    _update_streak(
        db, redis_client, user_id, score, "conversation_test", conversation_id
    )

    if not is_passed:
        return

    # Award test XP
    test_base = XP_BASE_TEST.get(gap_difficulty, 2)
    xp_earned = _calc_xp(test_base, score, is_first_attempt)
    _update_user_xp(
        db,
        user_id,
        xp_earned,
        f"Online test: {gap_difficulty} conversation",
        conversation_id,
        gap_difficulty,
        score,
    )

    # Achievements (check after is_completed may have been set)
    _award_achievements(db, user_id, conversation_id, score, gap_difficulty, "test")

    # Note: progression already counted on gap_submitted (first gap pass)
    # No double-count needed here — _update_progression_counter deduplicates

    logger.info(
        f"[test_submitted] user={user_id} conv={conversation_id} "
        f"score={score} xp={xp_earned} gap_done={gap_done} "
        f"unit_completed={gap_done and is_passed}"
    )


def _handle_song_completed(db, redis_client, event: dict):
    """
    Phase 3 hook: update l{n}_songs_completed in user_learning_profile.
    Skipped if user has no profile yet (profile setup is Phase 2).
    """
    user_id = event["user_id"]
    song_id = event.get("song_id", "")

    profile_col = db["user_learning_profile"]
    profile = profile_col.find_one({"user_id": user_id})
    if not profile:
        return

    level = profile.get("progression_level", 1)
    counted_key = f"l{level}_counted_songs"
    counted = profile.get(counted_key, [])

    if song_id not in counted:
        profile_col.update_one(
            {"user_id": user_id},
            {
                "$inc": {f"l{level}_songs_completed": 1},
                "$push": {counted_key: song_id},
                "$set": {"updated_at": datetime.utcnow()},
            },
        )
        logger.info(
            f"[song_completed] user={user_id} song={song_id} "
            f"progression_level={level}"
        )
        # Check level-up after song count update
        updated_profile = profile_col.find_one({"user_id": user_id})
        if updated_profile:
            _check_progression_level_up(db, user_id, updated_profile, "", "")


# ─────────────────────────────────────────────────────────────────────────────
# Worker Class
# ─────────────────────────────────────────────────────────────────────────────


class LearningEventsWorker:
    def __init__(
        self,
        worker_id: str = "learning-events-worker",
        redis_url: str = REDIS_URL,
    ):
        self.worker_id = worker_id
        self.redis_url = redis_url
        self.running = False
        self.queue = QueueManager(redis_url=redis_url, queue_name=QUEUE_NAME)
        self.payment_queue_key = f"queue:{PAYMENT_QUEUE_NAME}"
        self.db_manager = DBManager()
        logger.info(
            f"🎮 LearningEventsWorker [{worker_id}] initialized (also handles payment_events)"
        )

    async def initialize(self):
        await self.queue.connect()
        logger.info(
            f"✅ Worker [{self.worker_id}] connected to Redis queue '{QUEUE_NAME}'"
        )

    def _get_redis_sync(self):
        """Sync Redis client for streak cache invalidation."""
        import redis as redis_sync

        return redis_sync.Redis(
            host="redis-server", port=6379, db=0, decode_responses=True
        )

    async def start(self):
        self.running = True
        logger.info(
            f"🚀 Worker [{self.worker_id}] listening on queue '{QUEUE_NAME}' ..."
        )

        redis_sync = self._get_redis_sync()
        db = self.db_manager.db

        while self.running:
            try:
                # BRPOP blocks up to 1s on BOTH queues — learning_events + payment_events
                raw = await self.queue.redis_client.brpop(
                    [self.queue.task_queue_key, self.payment_queue_key], timeout=1
                )
                if not raw:
                    continue

                queue_key, raw_payload = raw
                event = json.loads(raw_payload)
                event_type = event.get("event_type", "")
                event_id = event.get("event_id", event.get("order_invoice_number", "?"))

                logger.info(
                    f"📥 [{self.worker_id}] queue={queue_key} event={event_type} id={event_id}"
                )

                if event_type == "gap_submitted":
                    _handle_gap_submitted(db, redis_sync, event)
                elif event_type == "test_submitted":
                    _handle_test_submitted(db, redis_sync, event)
                elif event_type == "song_completed":
                    _handle_song_completed(db, redis_sync, event)
                elif event_type == "conversation_subscription_paid":
                    _handle_conversation_subscription_paid(db, event)
                else:
                    logger.warning(
                        f"[{self.worker_id}] Unknown event_type: {event_type}"
                    )

            except json.JSONDecodeError as e:
                logger.error(f"[{self.worker_id}] JSON parse error: {e}")
            except Exception as e:
                logger.error(
                    f"[{self.worker_id}] Error processing event: {e}", exc_info=True
                )
                await asyncio.sleep(1)  # brief pause on error

    def stop(self):
        self.running = False
        logger.info(f"🛑 Worker [{self.worker_id}] stopping...")


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    worker = LearningEventsWorker()
    await worker.initialize()

    loop = asyncio.get_running_loop()

    def _shutdown(*_):
        worker.stop()

    loop.add_signal_handler(signal.SIGINT, _shutdown)
    loop.add_signal_handler(signal.SIGTERM, _shutdown)

    await worker.start()


if __name__ == "__main__":
    asyncio.run(main())
