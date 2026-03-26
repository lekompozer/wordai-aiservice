"""
Daily Vocab Feed API — "Daily Vocab by WordAI"

Architecture:
- 500 pre-built daily sets in Redis (build_daily_sets.py, runs every 30d)
- Each set: 6 cards × 3 related words embedded = 0 MongoDB queries per /feed/today
- Infinite scroll pool: Redis List per topic/level, refilled from MongoDB $sample 1×/hour
- Like/Save: Redis Set per user (O(1)), async persist to MongoDB in background

Endpoints (public unless noted):
  GET    /api/v1/daily-vocab/feed/today            — 6 cards + 18 related (set assigned by uid+date)
  GET    /api/v1/daily-vocab/feed/next             — 5 cards infinite scroll
  GET    /api/v1/daily-vocab/feed/stats/{word_key} — like/save counts (public)
  POST   /api/v1/daily-vocab/like                  — Toggle like (auth required)
  POST   /api/v1/daily-vocab/save                  — Toggle save (auth required, persists to DB)
  GET    /api/v1/daily-vocab/saved                 — User saved list (auth required)
  DELETE /api/v1/daily-vocab/saved/{word}          — Remove saved word (auth required)
  GET    /api/v1/daily-vocab/topics                — All topics with word counts
  GET    /api/v1/daily-vocab/topic-audio/{slug}    — Background music pool
  GET    /api/v1/daily-vocab/grammar/today         — 3 grammar tip cards
  GET    /api/v1/daily-vocab/words/{word}          — Single word detail with related

Note for unauthenticated users:
  Like/Save requires auth. Frontend should store anon user saves in IndexedDB
  (browser local storage) and sync to server after the user logs in.
"""

import hashlib
import json
import logging
import random
import uuid
from datetime import datetime, date, timedelta
from typing import Optional

import redis
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel

from src.database.db_manager import DBManager
from src.middleware.firebase_auth import get_current_user, get_current_user_optional

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/daily-vocab", tags=["Daily Vocab"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NUM_SETS = 500  # pre-built daily sets in Redis
CARDS_PER_DAY = 6  # cards per daily set
RELATED_PER_CARD = 3  # related words embedded per card
SCROLL_BATCH = 5  # cards per /feed/next response
SCROLL_POOL_SIZE = 50  # cards in Redis scroll pool per topic/level

# ---------------------------------------------------------------------------
# Topic slug → music pool slug mapping + in-memory URL cache
# Maps each card's topic_slug to the corresponding vocab_topic_audio slug, then
# picks a random hosted_url from that pool to embed directly in the card response.
# Cache is loaded lazily from MongoDB on first call (no DB hit per card after that).
# ---------------------------------------------------------------------------
_MUSIC_URL_CACHE: dict[str, list[str]] = {}  # music_slug → list of hosted_url strings
_MUSIC_CACHE_LOADED = False

_TOPIC_SLUG_TO_MUSIC: dict[str, str] = {
    # 1:1 exact matches (already correct)
    "education_learning": "education_learning",
    "environment_nature": "environment_nature",
    "family_relationships": "family_relationships",
    "food_drinks": "food_drinks",
    "greetings_introductions": "greetings_introductions",
    "hobbies_interests": "hobbies_interests",
    "law_justice": "law_justice",
    "philosophy_ethics": "philosophy_ethics",
    "politics_government": "politics_government",
    "science_research": "science_research",
    "social_issues": "social_issues",
    "sports_fitness": "sports_fitness",
    "technology_internet": "technology_internet",
    "transportation": "transportation",
    "travel_tourism": "travel_tourism",
    "weather_seasons": "weather_seasons",
    # remapped slugs
    "art_creativity": "arts_culture",
    "business_entrepreneurship": "business_economics",
    "daily_routines": "daily_life_routines",
    "emergency_safety": "social_issues",
    "entertainment_media": "music_entertainment",
    "events_celebrations": "holidays_celebrations",
    "finance_money": "money_finance",
    "future_innovation": "science_research",
    "health_body": "health_medicine",
    "history_culture": "history_heritage",
    "home_accommodation": "housing_real_estate",
    "medicine_healthcare": "health_medicine",
    "podcast_bbc": "education_learning",
    "podcast_bbc_6min_english": "education_learning",
    "podcast_bbc_news_english": "politics_government",
    "podcast_bbc_work_english": "work_careers",
    "shopping": "shopping_consumer",
    "work_office": "work_careers",
}


def _get_background_music_url(music_slug: str) -> str:
    """Return a random hosted_url for the given music_slug from the in-memory cache.
    Falls back to empty string if cache not yet loaded or slug has no tracks.
    The cache is populated once by _ensure_music_cache_loaded() at startup.
    """
    urls = _MUSIC_URL_CACHE.get(music_slug, [])
    return random.choice(urls) if urls else ""


def _ensure_music_cache_loaded(db) -> None:
    """Load all vocab_topic_audio pools into _MUSIC_URL_CACHE (runs once per process)."""
    global _MUSIC_URL_CACHE, _MUSIC_CACHE_LOADED
    if _MUSIC_CACHE_LOADED:
        return
    try:
        cache: dict[str, list[str]] = {}
        for doc in db["vocab_topic_audio"].find(
            {}, {"topic_slug": 1, "pool.hosted_url": 1, "_id": 0}
        ):
            slug = doc.get("topic_slug", "")
            urls = [t["hosted_url"] for t in doc.get("pool", []) if t.get("hosted_url")]
            if slug and urls:
                cache[slug] = urls
        _MUSIC_URL_CACHE = cache
        _MUSIC_CACHE_LOADED = True
        logger.info(
            f"✅ Music URL cache loaded: {len(cache)} topics, {sum(len(v) for v in cache.values())} tracks"
        )
    except Exception as e:
        logger.warning(f"Music cache load failed (non-fatal): {e}")


GRAMMAR_PER_DAY = 3
REDIS_TTL_DAILY = 86400  # 24h
REDIS_TTL_TOPICS = 3600  # 1h
REDIS_TTL_AUDIO = 86400 * 30  # 30 days
REDIS_TTL_SCROLL = 3600  # 1h scroll pool
REDIS_TTL_SETS = 86400 * 30  # 30 days pre-built sets

EPOCH = date(2026, 1, 1)  # day-number reference


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def get_db():
    return DBManager().db


def get_redis_client():
    try:
        return redis.Redis(host="redis-server", port=6379, db=2, decode_responses=True)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _day_number() -> int:
    """Days since epoch (2026-01-01). Monotonically increases each day."""
    return (date.today() - EPOCH).days


def _day_seed() -> str:
    return date.today().isoformat()


def _assign_set_idx(uid: Optional[str]) -> int:
    """
    Deterministic set assignment — no DB lookup.
    - Same user → same set all day, different set next day
    - Different users → different sets on same day
    - Anon users → day-based rotating set (same for all anon that day)
    """
    day_n = _day_number()
    if uid:
        uid_hash = int(hashlib.md5(uid.encode()).hexdigest()[:8], 16)
        return (uid_hash + day_n * 7) % NUM_SETS
    return (day_n * 13 + 37) % NUM_SETS


def _card_proj() -> dict:
    return {
        "_id": 0,
        "word": 1,
        "word_key": 1,
        "pos_tag": 1,
        "definition_en": 1,
        "definition_vi": 1,
        "example": 1,
        "topic_slug": 1,
        "topic_en": 1,
        "topic_category": 1,
        "level": 1,
        "image_url": 1,
        "context_audio_url": 1,
        "sources": 1,
        "related_words": 1,
        "like_count": 1,
        "save_count": 1,
    }


def _format_card(raw: dict) -> dict:
    """Normalize card fields for API response. `example` = how to use the word."""
    topic_slug = raw.get("topic_slug", "")
    music_slug = _TOPIC_SLUG_TO_MUSIC.get(topic_slug, "daily_life_routines")
    background_music_url = _get_background_music_url(music_slug)
    return {
        "word": raw.get("word", ""),
        "word_key": raw.get("word_key", raw.get("word", "")),
        "pos_tag": raw.get("pos_tag", ""),
        "definition_en": raw.get("definition_en", ""),
        "definition_vi": raw.get("definition_vi", ""),
        "example": raw.get("example", ""),  # how_to_use — shown publicly
        "topic_slug": topic_slug,
        "topic_en": raw.get("topic_en", ""),
        "topic_category": raw.get("topic_category", ""),
        "level": raw.get("level", "intermediate"),
        "image_url": raw.get("image_url", ""),
        "audio_url": raw.get("context_audio_url", ""),
        "background_music_url": background_music_url,  # random track from topic pool
        "sources": raw.get("sources", []),
        "like_count": raw.get("like_count", 0),
        "save_count": raw.get("save_count", 0),
    }


def _enrich_related(cards: list, db) -> list:
    """
    Attach full related word data to each card.
    Strategy:
      1. Try curated related_words lookup (1 batch MongoDB query).
      2. Fill remaining slots with same topic+level $sample cards (1 query per unique
         topic+level pair with < 3 related — usually 1-2 extra queries at most).
    """
    all_keys = list(
        {
            rw.get("word", "")
            for c in cards
            for rw in c.get("related_words", [])[:RELATED_PER_CARD]
            if rw.get("word")
        }
    )
    lookup: dict = {}
    if all_keys:
        for rdoc in db.vocab_cards.find(
            {"word_key": {"$in": all_keys}},
            {
                "_id": 0,
                "word_key": 1,
                "word": 1,
                "pos_tag": 1,
                "definition_en": 1,
                "definition_vi": 1,
                "example": 1,
                "image_url": 1,
                "context_audio_url": 1,
            },
        ):
            lookup[rdoc["word_key"]] = rdoc

    cards_needing_fill = []
    for c in cards:
        c["related"] = []
        existing_keys = {c.get("word_key", c.get("word", ""))}
        for rw in c.get("related_words", [])[:RELATED_PER_CARD]:
            rk = rw.get("word", "")
            rd = lookup.get(rk, {})
            if rd and rd.get("definition_en") and rk not in existing_keys:
                c["related"].append(
                    {
                        "word_key": rd["word_key"],
                        "word": rd["word"],
                        "pos_tag": rw.get("pos_tag", rd.get("pos_tag", "")),
                        "definition_en": rd.get("definition_en", ""),
                        "definition_vi": rd.get("definition_vi", ""),
                        "example": rd.get("example", ""),
                        "image_url": rd.get("image_url", ""),
                        "audio_url": rd.get("context_audio_url", ""),
                    }
                )
                existing_keys.add(rk)
        if len(c["related"]) < RELATED_PER_CARD:
            cards_needing_fill.append(c)

    # Fill missing related via $sample fallback.
    # Strategy: try same topic+level first (diverse words from same theme);
    # if topic is a "podcast" meta-slug (small pool) or still not enough → fall back
    # to same level across ALL topics for maximum variety.
    # Also exclude all word_keys already visible in the current feed.
    PODCAST_SLUGS = {
        "podcast_bbc",
        "podcast_bbc_6min_english",
        "podcast_bbc_news_english",
        "podcast_bbc_work_english",
    }
    all_feed_keys = {c.get("word_key", c.get("word", "")) for c in cards}

    if cards_needing_fill:
        sample_size = max(30, RELATED_PER_CARD * len(cards_needing_fill) * 3)
        proj = {
            "$project": {
                "_id": 0,
                "word_key": 1,
                "word": 1,
                "pos_tag": 1,
                "definition_en": 1,
                "definition_vi": 1,
                "example": 1,
                "image_url": 1,
                "context_audio_url": 1,
            }
        }

        # Build pool per (effective_slug, level) — podcast slugs use level-only pool
        tl_pool: dict = {}
        unique_pairs = {
            (c.get("topic_slug", ""), c.get("level", "intermediate"))
            for c in cards_needing_fill
        }
        for tslug, tlevel in unique_pairs:
            use_slug = None if tslug in PODCAST_SLUGS else tslug
            match: dict = {"definition_en": {"$exists": True, "$ne": ""}}
            if use_slug:
                match["topic_slug"] = use_slug
            if tlevel:
                match["level"] = tlevel
            pool = list(
                db.vocab_cards.aggregate(
                    [
                        {"$match": match},
                        {"$sample": {"size": sample_size}},
                        proj,
                    ]
                )
            )
            # If same-topic pool is tiny (< 10), supplement with cross-topic same-level
            if len(pool) < 10:
                cross_match: dict = {"definition_en": {"$exists": True, "$ne": ""}}
                if tlevel:
                    cross_match["level"] = tlevel
                extra = list(
                    db.vocab_cards.aggregate(
                        [
                            {"$match": cross_match},
                            {"$sample": {"size": sample_size}},
                            proj,
                        ]
                    )
                )
                seen = {d["word_key"] for d in pool}
                pool += [d for d in extra if d.get("word_key") not in seen]
            tl_pool[(tslug, tlevel)] = pool

        for c in cards_needing_fill:
            key = (c.get("topic_slug", ""), c.get("level", "intermediate"))
            pool = tl_pool.get(key, [])
            existing_keys = all_feed_keys | {r["word_key"] for r in c["related"]}
            for candidate in pool:
                if len(c["related"]) >= RELATED_PER_CARD:
                    break
                ck = candidate.get("word_key", "")
                if ck and ck not in existing_keys and candidate.get("definition_en"):
                    c["related"].append(
                        {
                            "word_key": ck,
                            "word": candidate["word"],
                            "pos_tag": candidate.get("pos_tag", ""),
                            "definition_en": candidate.get("definition_en", ""),
                            "definition_vi": candidate.get("definition_vi", ""),
                            "example": candidate.get("example", ""),
                            "image_url": candidate.get("image_url", ""),
                            "audio_url": candidate.get("context_audio_url", ""),
                        }
                    )
                    existing_keys.add(ck)

    return cards


def _attach_user_status(cards: list, uid: Optional[str], r) -> list:
    """
    Attach user_liked / user_saved flags to each card.
    Uses a single Redis pipeline — O(1) per card regardless of count.
    Always sets user_liked=False, user_saved=False for anon users.
    """
    if not uid:
        for c in cards:
            c["user_liked"] = False
            c["user_saved"] = False
        return cards
    if not r:
        for c in cards:
            c["user_liked"] = False
            c["user_saved"] = False
        return cards
    try:
        pipe = r.pipeline()
        for c in cards:
            wk = c.get("word_key", c.get("word", ""))
            pipe.sismember(f"vocab:liked:{uid}", wk)
            pipe.sismember(f"vocab:saved:{uid}", wk)
        results = pipe.execute()
        for i, c in enumerate(cards):
            c["user_liked"] = bool(results[i * 2])
            c["user_saved"] = bool(results[i * 2 + 1])
    except Exception:
        for c in cards:
            c["user_liked"] = False
            c["user_saved"] = False
    return cards


def _refill_scroll_pool(
    pool_key: str, topic_slug: Optional[str], level: Optional[str], db, r
):
    """
    Background task: query MongoDB $sample → enrich related → push to Redis List.
    Triggered when pool falls below 10 cards. ~1 MongoDB call per topic per hour.
    """
    try:
        query: dict = {}
        if topic_slug:
            query["topic_slug"] = topic_slug
        if level:
            query["level"] = level
        pipeline = []
        if query:
            pipeline.append({"$match": query})
        pipeline += [
            {"$sample": {"size": SCROLL_POOL_SIZE}},
            {"$project": _card_proj()},
        ]
        raw_cards = list(db.vocab_cards.aggregate(pipeline))
        if not raw_cards:
            return
        formatted = [_format_card(c) for c in raw_cards]
        # Merge related_words back for _enrich_related
        for i, fc in enumerate(formatted):
            fc["related_words"] = raw_cards[i].get("related_words", [])
        _enrich_related(formatted, db)
        for fc in formatted:
            fc.pop("related_words", None)
        pipe = r.pipeline(transaction=False)
        for item in formatted:
            pipe.lpush(pool_key, json.dumps(item))
        pipe.expire(pool_key, REDIS_TTL_SCROLL)
        pipe.execute()
    except Exception as e:
        logger.error(f"_refill_scroll_pool error: {e}")


# ---------------------------------------------------------------------------
# Topics — static info, cached 1h
# ---------------------------------------------------------------------------


@router.get("/topics")
async def get_vocab_topics(db=Depends(get_db), r=Depends(get_redis_client)):
    """
    List all available topics with vocabulary counts.
    Public endpoint — no auth required.
    """
    cache_key = "vocab:topics:v2"
    if r:
        try:
            cached = r.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

    pipeline = [
        {
            "$group": {
                "_id": {
                    "topic_slug": "$topic_slug",
                    "topic_en": "$topic_en",
                    "topic_category": "$topic_category",
                },
                "total_words": {"$sum": 1},
                "levels": {"$addToSet": "$level"},
            }
        },
        {"$sort": {"total_words": -1}},
    ]
    raw = list(db.vocab_cards.aggregate(pipeline))

    result = [
        {
            "topic_slug": r_["_id"]["topic_slug"],
            "topic_en": r_["_id"]["topic_en"],
            "topic_category": r_["_id"]["topic_category"],
            "total_words": r_["total_words"],
            "levels": sorted(r_["levels"]),
        }
        for r_ in raw
        if r_["_id"].get("topic_slug")
    ]

    if r:
        try:
            r.setex(cache_key, REDIS_TTL_TOPICS, json.dumps(result))
        except Exception:
            pass

    return result


# ---------------------------------------------------------------------------
# NEW FEED ENDPOINTS
# ---------------------------------------------------------------------------


@router.get("/feed/today")
async def get_feed_today(
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
    r=Depends(get_redis_client),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """
    Return today's 6-card set with 3 related words per card (18 related total).

    - Authenticated users get a unique set per day (uid + date deterministic hash, no DB)
    - Anon users get the day's rotating set (same for all anon that day)
    - Pre-built sets in Redis (build_daily_sets.py) → 0 MongoDB queries when cache warm
    - `example` = how to use the word in a real sentence (public)
    - `audio_url` = context audio clip URL (may be empty)
    - `related[*].example` = how to use each related word
    - `user_liked` / `user_saved` = requires auth (always false for anon)
    """
    _ensure_music_cache_loaded(db)
    uid = current_user["uid"] if current_user else None
    set_idx = _assign_set_idx(uid)
    set_key = f"vocab:set:{set_idx}"

    cards = None
    if r:
        try:
            raw = r.get(set_key)
            if raw:
                cards = json.loads(raw)
                # Backfill background_music_url for cards cached before this field existed
                for c in cards:
                    if "background_music_url" not in c:
                        music_slug = _TOPIC_SLUG_TO_MUSIC.get(
                            c.get("topic_slug", ""), "daily_life_routines"
                        )
                        c["background_music_url"] = _get_background_music_url(
                            music_slug
                        )
        except Exception:
            pass

    if cards is None:
        # Slow path — build on-the-fly if build_daily_sets.py hasn't run yet
        logger.warning(f"Set {set_idx} not in Redis — building on-the-fly")
        seed = _day_seed() + str(set_idx)
        pool = list(db.vocab_cards.find({}, _card_proj()).limit(CARDS_PER_DAY * 15))
        rng = random.Random(seed)
        rng.shuffle(pool)
        selected = pool[:CARDS_PER_DAY]
        formatted = [_format_card(c) for c in selected]
        for i, fc in enumerate(formatted):
            fc["related_words"] = selected[i].get("related_words", [])
        _enrich_related(formatted, db)
        for fc in formatted:
            fc.pop("related_words", None)
        cards = formatted
        if r:
            try:
                r.setex(set_key, REDIS_TTL_SETS, json.dumps(cards))
            except Exception:
                pass

    _attach_user_status(cards, uid, r)

    return {
        "date": _day_seed(),
        "set_idx": set_idx,
        "total": len(cards),
        "cards": cards,
    }


@router.get("/feed/next")
async def get_feed_next(
    background_tasks: BackgroundTasks,
    topic_slug: Optional[str] = Query(None, description="Filter by topic slug"),
    level: Optional[str] = Query(None, description="beginner|intermediate|advanced"),
    limit: int = Query(SCROLL_BATCH, ge=1, le=20),
    db=Depends(get_db),
    r=Depends(get_redis_client),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """
    Return next batch of cards for infinite scroll (TikTok-style).

    - Each card has 3 related words embedded with full data
    - Redis List pool per topic/level, refilled from MongoDB $sample once per hour
    - When pool < 10 cards remaining, refill triggered in background (no latency)
    - `example` = how to use the word
    - Filter by topic_slug (e.g. technology_internet) or level (beginner/intermediate/advanced)
    - `user_liked` / `user_saved` requires auth
    """
    _ensure_music_cache_loaded(db)
    uid = current_user["uid"] if current_user else None
    pool_key = f"vocab:scroll_pool:{topic_slug or 'all'}:{level or 'all'}"
    cards = []

    if r:
        try:
            pool_len = r.llen(pool_key)
            if pool_len > 0:
                raw_cards = r.lrange(pool_key, 0, limit - 1)
                r.ltrim(pool_key, limit, -1)
                cards = [json.loads(c) for c in raw_cards]
                # Backfill background_music_url for cards cached before this field existed
                for c in cards:
                    if "background_music_url" not in c:
                        music_slug = _TOPIC_SLUG_TO_MUSIC.get(
                            c.get("topic_slug", ""), "daily_life_routines"
                        )
                        c["background_music_url"] = _get_background_music_url(
                            music_slug
                        )
                if pool_len - limit < 10:
                    background_tasks.add_task(
                        _refill_scroll_pool, pool_key, topic_slug, level, db, r
                    )
        except Exception:
            pass

    if len(cards) < limit:
        # Direct MongoDB fallback
        needed = limit - len(cards)
        query: dict = {}
        if topic_slug:
            query["topic_slug"] = topic_slug
        if level:
            query["level"] = level
        pipeline = []
        if query:
            pipeline.append({"$match": query})
        pipeline += [{"$sample": {"size": needed}}, {"$project": _card_proj()}]
        raw = list(db.vocab_cards.aggregate(pipeline))
        formatted = [_format_card(c) for c in raw]
        for i, fc in enumerate(formatted):
            fc["related_words"] = raw[i].get("related_words", [])
        _enrich_related(formatted, db)
        for fc in formatted:
            fc.pop("related_words", None)
        cards.extend(formatted)
        background_tasks.add_task(
            _refill_scroll_pool, pool_key, topic_slug, level, db, r
        )

    _attach_user_status(cards, uid, r)
    return {"total": len(cards), "cards": cards}


@router.get("/feed/stats/{word_key}")
async def get_word_stats(
    word_key: str,
    db=Depends(get_db),
    r=Depends(get_redis_client),
):
    """
    Return realtime like_count and save_count for a word.
    Public — no auth required. Used for live counter updates on the card UI.
    Reads from Redis first (updated on every like/save), falls back to MongoDB.
    """
    if r:
        try:
            stats = r.hgetall(f"vocab:card_stats:{word_key}")
            if stats:
                return {
                    "word_key": word_key,
                    "like_count": int(stats.get("like_count", 0)),
                    "save_count": int(stats.get("save_count", 0)),
                }
        except Exception:
            pass
    doc = db.vocab_cards.find_one(
        {"word_key": word_key}, {"_id": 0, "like_count": 1, "save_count": 1}
    )
    return {
        "word_key": word_key,
        "like_count": doc.get("like_count", 0) if doc else 0,
        "save_count": doc.get("save_count", 0) if doc else 0,
    }


@router.post("/like")
async def toggle_like(
    body: dict,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
    r=Depends(get_redis_client),
    current_user: dict = Depends(get_current_user),
):
    """
    Toggle like on a vocabulary word (auth required).

    - O(1) Redis SADD/SREM on `vocab:liked:{uid}`
    - Increments/decrements global counter in `vocab:card_stats:{word_key}`
    - Persists to MongoDB vocab_cards.like_count in background (no latency impact)

    Body: `{"word_key": "innovation"}`
    Returns: `{"liked": true, "like_count": 43}`
    """
    uid = current_user["uid"]
    word_key = (body.get("word_key") or "").strip().lower()
    if not word_key:
        raise HTTPException(status_code=400, detail="word_key required")
    if not r:
        raise HTTPException(status_code=503, detail="Cache unavailable")

    liked_key = f"vocab:liked:{uid}"
    stats_key = f"vocab:card_stats:{word_key}"

    try:
        if r.sismember(liked_key, word_key):
            r.srem(liked_key, word_key)
            new_count = max(0, int(r.hget(stats_key, "like_count") or 0) - 1)
            r.hset(stats_key, "like_count", new_count)
            liked = False
        else:
            r.sadd(liked_key, word_key)
            new_count = int(r.hget(stats_key, "like_count") or 0) + 1
            r.hset(stats_key, "like_count", new_count)
            liked = True

        def _persist(wk, delta):
            try:
                DBManager().db.vocab_cards.update_one(
                    {"word_key": wk}, {"$inc": {"like_count": delta}}
                )
            except Exception as e:
                logger.error(f"like persist error: {e}")

        background_tasks.add_task(_persist, word_key, 1 if liked else -1)
        return {"liked": liked, "like_count": new_count}
    except Exception as e:
        logger.error(f"toggle_like error: {e}")
        raise HTTPException(status_code=500, detail="Internal error")


# ---------------------------------------------------------------------------
# Save — auth required, persists to MongoDB
# ---------------------------------------------------------------------------


class SaveVocabRequest(BaseModel):
    word_key: str
    word: str
    pos_tag: str = ""
    definition_en: str = ""
    definition_vi: str = ""
    example: str = ""
    topic_slug: str = ""
    topic_en: str = ""
    level: str = "intermediate"
    image_url: str = ""
    audio_url: str = ""


@router.post("/save")
async def toggle_save(
    body: SaveVocabRequest,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
    r=Depends(get_redis_client),
    current_user: dict = Depends(get_current_user),
):
    """
    Toggle save on a vocabulary word (auth required).

    - O(1) Redis SADD/SREM on `vocab:saved:{uid}` for instant UI response
    - Full word data persisted to `user_saved_vocabulary` collection in background
    - Unauthenticated users: frontend should store saves in browser IndexedDB
      and sync to server after login

    Returns: `{"saved": true, "save_count": 19}`
    """
    uid = current_user["uid"]
    word_key = body.word_key.strip().lower()
    saved_key = f"vocab:saved:{uid}"
    stats_key = f"vocab:card_stats:{word_key}"

    currently_saved = False
    if r:
        try:
            currently_saved = bool(r.sismember(saved_key, word_key))
        except Exception:
            pass
    if not r:
        currently_saved = bool(
            db.user_saved_vocabulary.find_one(
                {"user_id": uid, "word_key": word_key}, {"_id": 1}
            )
        )

    if currently_saved:
        if r:
            try:
                r.srem(saved_key, word_key)
                new_count = max(0, int(r.hget(stats_key, "save_count") or 0) - 1)
                r.hset(stats_key, "save_count", new_count)
            except Exception:
                new_count = 0
        else:
            new_count = 0

        def _unsave(wk, user_id):
            try:
                dbc = DBManager().db
                dbc.user_saved_vocabulary.delete_one(
                    {"user_id": user_id, "word_key": wk}
                )
                dbc.vocab_cards.update_one(
                    {"word_key": wk}, {"$inc": {"save_count": -1}}
                )
            except Exception as e:
                logger.error(f"unsave persist error: {e}")

        background_tasks.add_task(_unsave, word_key, uid)
        return {"saved": False, "save_count": new_count}

    else:
        if r:
            try:
                r.sadd(saved_key, word_key)
                new_count = int(r.hget(stats_key, "save_count") or 0) + 1
                r.hset(stats_key, "save_count", new_count)
            except Exception:
                new_count = 0
        else:
            new_count = 0

        def _save(b, user_id):
            try:
                dbc = DBManager().db
                doc = {
                    "save_id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "word_key": b.word_key.strip().lower(),
                    "word": b.word.strip(),
                    "pos_tag": b.pos_tag,
                    "definition_en": b.definition_en,
                    "definition_vi": b.definition_vi,
                    "example": b.example,
                    "topic_slug": b.topic_slug,
                    "topic_en": b.topic_en,
                    "level": b.level,
                    "image_url": b.image_url,
                    "audio_url": b.audio_url,
                    "review_count": 0,
                    "correct_count": 0,
                    "next_review_date": (
                        datetime.utcnow() + timedelta(days=1)
                    ).isoformat(),
                    "saved_at": datetime.utcnow().isoformat(),
                }
                dbc.user_saved_vocabulary.update_one(
                    {"user_id": user_id, "word_key": b.word_key.strip().lower()},
                    {"$setOnInsert": doc},
                    upsert=True,
                )
                dbc.vocab_cards.update_one(
                    {"word_key": b.word_key.strip().lower()},
                    {"$inc": {"save_count": 1}},
                )
            except Exception as e:
                logger.error(f"save persist error: {e}")

        background_tasks.add_task(_save, body, uid)
        return {"saved": True, "save_count": new_count}


@router.get("/saved")
async def get_saved_vocabulary(
    topic_slug: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Get authenticated user's saved vocabulary list.

    Note: Unauthenticated users' saves are stored in browser IndexedDB
    (managed entirely by frontend — no server-side storage for anon users).
    """
    uid = current_user["uid"]
    query: dict = {"user_id": uid}
    if topic_slug:
        query["topic_slug"] = topic_slug
    if level:
        query["level"] = level
    skip = (page - 1) * limit
    total = db.user_saved_vocabulary.count_documents(query)
    docs = list(
        db.user_saved_vocabulary.find(query, {"_id": 0})
        .sort("saved_at", -1)
        .skip(skip)
        .limit(limit)
    )
    return {"total": total, "page": page, "limit": limit, "words": docs}


@router.delete("/saved/{word}")
async def delete_saved_word(
    word: str,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
    r=Depends(get_redis_client),
    current_user: dict = Depends(get_current_user),
):
    """Remove a word from user's saved list (auth required)."""
    uid = current_user["uid"]
    word_lower = word.strip().lower()
    if r:
        try:
            r.srem(f"vocab:saved:{uid}", word_lower)
        except Exception:
            pass
    result = db.user_saved_vocabulary.delete_one(
        {"user_id": uid, "word_key": word_lower}
    )
    if result.deleted_count == 0:
        result = db.user_saved_vocabulary.delete_one(
            {"user_id": uid, "word": {"$regex": f"^{word_lower}$", "$options": "i"}}
        )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Word not in saved list")
    return {"deleted": True, "word": word}


# ---------------------------------------------------------------------------
# Static info endpoints
# ---------------------------------------------------------------------------


@router.get("/grammar/today")
async def get_today_grammar(
    topic_slug: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    db=Depends(get_db),
    r=Depends(get_redis_client),
):
    """
    Return today's 3 grammar tip cards.
    Each card: pattern, explanation_en, explanation_vi, example, source link.
    No auth required. Cached 24h.
    """
    seed = _day_seed()
    cache_key = f"vocab:grammar:v2:{hashlib.md5(f'{seed}:{topic_slug}:{level}'.encode()).hexdigest()[:12]}"
    if r:
        try:
            cached = r.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

    grammar_items: list = []
    conv_query: dict = {"grammar_points.0": {"$exists": True}}
    if topic_slug:
        conv_ids = [
            c["conversation_id"]
            for c in db.conversation_library.find(
                {"topic_slug": topic_slug, **({"level": level} if level else {})},
                {"conversation_id": 1},
            ).limit(30)
        ]
        conv_query["conversation_id"] = {"$in": conv_ids}

    for vdoc in db.conversation_vocabulary.find(
        conv_query, {"conversation_id": 1, "grammar_points": 1}
    ).limit(50):
        for gp in vdoc.get("grammar_points", []):
            grammar_items.append(
                {
                    **gp,
                    "source_type": "conversation",
                    "source_id": vdoc.get("conversation_id", ""),
                }
            )

    for vdoc in db.podcast_vocabulary.find(
        {"grammar_points.0": {"$exists": True}}, {"podcast_id": 1, "grammar_points": 1}
    ).limit(50):
        for gp in vdoc.get("grammar_points", []):
            grammar_items.append(
                {
                    **gp,
                    "source_type": "podcast",
                    "source_id": vdoc.get("podcast_id", ""),
                }
            )

    if not grammar_items:
        raise HTTPException(status_code=404, detail="No grammar data found")

    rng = random.Random(seed + (topic_slug or "") + (level or ""))
    rng.shuffle(grammar_items)
    selected = grammar_items[:GRAMMAR_PER_DAY]
    response = {"date": seed, "total": len(selected), "grammar": selected}

    if r:
        try:
            r.setex(cache_key, REDIS_TTL_DAILY, json.dumps(response))
        except Exception:
            pass
    return response


@router.get("/topic-audio/{slug}")
async def get_topic_audio(
    slug: str,
    db=Depends(get_db),
    r=Depends(get_redis_client),
):
    """
    Return background music pool for a topic (hosted on static.aivungtau.com).
    Frontend shuffles and loops through the pool. No auth required.
    """
    redis_key = f"vocab:topic_audio_pool:{slug}"
    if r:
        try:
            cached = r.get(redis_key)
            if cached:
                return {"topic_slug": slug, "pool": json.loads(cached)}
        except Exception:
            pass
    doc = db.vocab_topic_audio.find_one({"topic_slug": slug}, {"_id": 0, "pool": 1})
    if not doc or not doc.get("pool"):
        raise HTTPException(status_code=404, detail=f"No audio pool for topic '{slug}'")
    pool = doc["pool"]
    if r:
        try:
            r.setex(redis_key, REDIS_TTL_AUDIO, json.dumps(pool))
        except Exception:
            pass
    return {"topic_slug": slug, "pool": pool}


# ---------------------------------------------------------------------------
# Word detail — LAST (parametric route, catches any /{word})
# ---------------------------------------------------------------------------


@router.get("/words/{word}")
async def get_word_detail(
    word: str,
    db=Depends(get_db),
    r=Depends(get_redis_client),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """
    Full detail for a single vocabulary word.

    - `example` = how to use the word in a real sentence (public)
    - `sources` = conversation/podcast/song context clips with links
    - `related` = up to 3 related words with full data including example
    - `user_liked` / `user_saved` — requires auth (false for anon)
    - Cached in Redis 24h (user status attached after cache hit, not stored in cache)
    """
    word_lower = word.strip().lower()
    cache_key = f"vocab:word:{word_lower}"
    uid = current_user["uid"] if current_user else None

    if r:
        try:
            cached = r.get(cache_key)
            if cached:
                doc = json.loads(cached)
                _attach_user_status([doc], uid, r)
                return doc
        except Exception:
            pass

    raw = db.vocab_cards.find_one({"word_key": word_lower}, _card_proj())
    if not raw:
        raise HTTPException(status_code=404, detail=f"Word '{word}' not found")

    doc = _format_card(raw)
    doc["related_words"] = raw.get("related_words", [])
    _enrich_related([doc], db)
    doc.pop("related_words", None)

    if r:
        try:
            r.setex(cache_key, REDIS_TTL_DAILY, json.dumps(doc))
        except Exception:
            pass

    _attach_user_status([doc], uid, r)
    return doc
