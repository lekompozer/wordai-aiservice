"""
Daily Vocab API — "Daily Vocab by WordAI"

Reads from the denormalized `vocab_cards` collection (built by build_vocab_cards.py)
instead of joining conversation/podcast collections on every request.

Endpoints (public unless noted):
  GET  /api/v1/daily-vocab/topics               — All topics with word counts
  GET  /api/v1/daily-vocab/today                — Today's 10-card set (deterministic)
  GET  /api/v1/daily-vocab/random               — One random card
  GET  /api/v1/daily-vocab/words/{word}         — Single word detail
  GET  /api/v1/daily-vocab/topic-audio/{slug}   — Background music pool for a topic
  GET  /api/v1/daily-vocab/grammar/today        — Today's 3 grammar tip cards
  POST /api/v1/daily-vocab/save                 — Toggle save (requires auth)
  GET  /api/v1/daily-vocab/saved                — User's saved words (requires auth)
  DELETE /api/v1/daily-vocab/saved/{word}       — Remove saved word (requires auth)
"""

import hashlib
import json
import logging
import random
import uuid
from datetime import datetime, date, timedelta
from typing import Optional

import redis
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.database.db_manager import DBManager
from src.middleware.firebase_auth import get_current_user, get_current_user_optional

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/daily-vocab", tags=["Daily Vocab"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CARDS_PER_DAY   = 10
GRAMMAR_PER_DAY = 3
REDIS_TTL_DAILY  = 86400        # 24h
REDIS_TTL_TOPICS = 3600         # 1h
REDIS_TTL_AUDIO  = 86400 * 30  # 30 days


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


def _day_seed() -> str:
    """Returns a date-based seed string (same for all users each day)."""
    return date.today().isoformat()


def _cards_query(
    topic_slug: Optional[str],
    level: Optional[str],
    exclude_words: set,
    limit: int,
    db,
    seed: Optional[str] = None,
) -> list:
    """
    Pull cards directly from vocab_cards (denormalized read model).
    seed=None  → truly random via $sample
    seed=str   → deterministic shuffle (same cards same day)
    """
    query: dict = {}
    if topic_slug:
        query["topic_slug"] = topic_slug
    if level:
        query["level"] = level

    proj = {
        "_id": 0,
        "word": 1, "word_key": 1, "pos_tag": 1,
        "definition_en": 1, "definition_vi": 1, "example": 1,
        "topic_slug": 1, "topic_en": 1, "topic_category": 1, "level": 1,
        "image_url": 1, "context_audio_url": 1,
        "context_start_sec": 1, "context_end_sec": 1,
        "sources": 1, "related_words": 1,
        "like_count": 1, "save_count": 1,
    }

    if seed is not None:
        pool = list(db.vocab_cards.find(query, proj).limit(limit * 5))
        if not pool:
            return []
        rng = random.Random(seed + (topic_slug or "") + (level or ""))
        rng.shuffle(pool)
        filtered = [c for c in pool if c.get("word_key", c.get("word", "")).lower() not in exclude_words]
        return filtered[:limit]
    else:
        pipeline: list = []
        if query:
            pipeline.append({"$match": query})
        if exclude_words:
            pipeline.append({"$match": {"word_key": {"$nin": list(exclude_words)}}})
        pipeline += [
            {"$sample": {"size": limit}},
            {"$project": proj},
        ]
        return list(db.vocab_cards.aggregate(pipeline))


# ---------------------------------------------------------------------------
# Endpoints — static paths BEFORE parametric /{word} routes
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
        {"$group": {
            "_id": {
                "topic_slug":     "$topic_slug",
                "topic_en":       "$topic_en",
                "topic_category": "$topic_category",
            },
            "total_words": {"$sum": 1},
            "levels":      {"$addToSet": "$level"},
        }},
        {"$sort": {"total_words": -1}},
    ]
    raw = list(db.vocab_cards.aggregate(pipeline))

    result = [
        {
            "topic_slug":    r_["_id"]["topic_slug"],
            "topic_en":      r_["_id"]["topic_en"],
            "topic_category": r_["_id"]["topic_category"],
            "total_words":   r_["total_words"],
            "levels":        sorted(r_["levels"]),
        }
        for r_ in raw if r_["_id"].get("topic_slug")
    ]

    if r:
        try:
            r.setex(cache_key, REDIS_TTL_TOPICS, json.dumps(result))
        except Exception:
            pass

    return result


@router.get("/today")
async def get_today_vocab(
    topic_slug: Optional[str] = Query(None, description="Filter by topic slug"),
    level: Optional[str] = Query(None, description="beginner|intermediate|advanced"),
    db=Depends(get_db),
    r=Depends(get_redis_client),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """
    Return today's vocabulary card set (10 words).
    Same cards for same topic/level/day (deterministic seed).
    No auth required — free feature.
    """
    seed      = _day_seed()
    cache_key = f"vocab:daily:v2:{hashlib.md5(f'{seed}:{topic_slug}:{level}'.encode()).hexdigest()[:12]}"

    if r:
        try:
            cached = r.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

    cards = _cards_query(
        topic_slug=topic_slug, level=level, exclude_words=set(),
        limit=CARDS_PER_DAY, db=db, seed=seed,
    )

    if not cards:
        # Fallback: any topic
        cards = _cards_query(
            topic_slug=None, level=level, exclude_words=set(),
            limit=CARDS_PER_DAY, db=db, seed=seed,
        )

    if not cards:
        raise HTTPException(status_code=404, detail="No vocabulary found for this filter")

    response = {
        "date":       seed,
        "topic_slug": topic_slug,
        "level":      level,
        "total":      len(cards),
        "cards":      cards,
    }

    if r:
        try:
            r.setex(cache_key, REDIS_TTL_DAILY, json.dumps(response))
        except Exception:
            pass

    return response


@router.get("/random")
async def get_random_vocab(
    topic_slug: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    exclude: Optional[str] = Query(None, description="Comma-separated words to exclude"),
    db=Depends(get_db),
):
    """
    Return a single random vocabulary card.
    Used when user swipes to next card (truly random each call).
    No auth required.
    """
    exclude_words = {w.strip().lower() for w in (exclude or "").split(",") if w.strip()}

    cards = _cards_query(
        topic_slug=topic_slug, level=level,
        exclude_words=exclude_words, limit=1, db=db, seed=None,
    )

    if not cards:
        raise HTTPException(status_code=404, detail="No vocabulary found")

    return cards[0]


@router.get("/grammar/today")
async def get_today_grammar(
    topic_slug: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    db=Depends(get_db),
    r=Depends(get_redis_client),
):
    """
    Return today's grammar tip cards (3 patterns).
    Each card has: pattern, explanation_en, explanation_vi, example, source link.
    No auth required.
    """
    seed      = _day_seed()
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

    for vdoc in db.conversation_vocabulary.find(conv_query, {"conversation_id": 1, "grammar_points": 1}).limit(50):
        for gp in vdoc.get("grammar_points", []):
            grammar_items.append({**gp, "source_type": "conversation", "source_id": vdoc.get("conversation_id", "")})

    for vdoc in db.podcast_vocabulary.find({"grammar_points.0": {"$exists": True}}, {"podcast_id": 1, "grammar_points": 1}).limit(50):
        for gp in vdoc.get("grammar_points", []):
            grammar_items.append({**gp, "source_type": "podcast", "source_id": vdoc.get("podcast_id", "")})

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
    Frontend shuffles and loops through the pool.
    No auth required.
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
# Saved words — requires auth
# ---------------------------------------------------------------------------


class SaveVocabRequest(BaseModel):
    word: str
    pos_tag: str = ""
    definition_en: str
    definition_vi: str = ""
    example: str = ""
    source_type: str = "conversation"  # conversation | podcast
    source_id: str = ""
    topic_slug: str = ""
    topic_en: str = ""
    level: str = "intermediate"


@router.post("/save")
async def save_vocabulary_word(
    body: SaveVocabRequest,
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Save a vocabulary word to user's personal list. Toggle: saves or removes."""
    user_id = current_user["uid"]
    word_lower = body.word.strip().lower()

    existing = db.user_saved_vocabulary.find_one(
        {"user_id": user_id, "word": {"$regex": f"^{word_lower}$", "$options": "i"}}
    )
    if existing:
        db.user_saved_vocabulary.delete_one({"_id": existing["_id"]})
        return {"saved": False, "word": body.word}

    doc = {
        "save_id": str(uuid.uuid4()),
        "user_id": user_id,
        "word": body.word.strip(),
        "pos_tag": body.pos_tag,
        "definition_en": body.definition_en,
        "definition_vi": body.definition_vi,
        "example": body.example,
        "source_type": body.source_type,
        "conversation_id": (
            body.source_id if body.source_type == "conversation" else None
        ),
        "podcast_id": body.source_id if body.source_type == "podcast" else None,
        "topic_slug": body.topic_slug,
        "topic_en": body.topic_en,
        "level": body.level,
        "review_count": 0,
        "correct_count": 0,
        "next_review_date": (datetime.utcnow() + timedelta(days=1)).isoformat(),
        "saved_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    db.user_saved_vocabulary.insert_one(doc)
    doc.pop("_id", None)
    return {"saved": True, "word": body.word, "doc": doc}


@router.get("/saved")
async def get_saved_vocabulary(
    topic_slug: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get user's saved vocabulary list with optional filters."""
    user_id = current_user["uid"]
    query: dict = {"user_id": user_id}
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

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "words": docs,
    }


@router.delete("/saved/{word}")
async def delete_saved_word(
    word: str,
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Remove a word from user's saved list."""
    user_id = current_user["uid"]
    result = db.user_saved_vocabulary.delete_one(
        {"user_id": user_id, "word": {"$regex": f"^{word}$", "$options": "i"}}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Word not in saved list")
    return {"deleted": True, "word": word}


# ---------------------------------------------------------------------------
# Word detail — MUST be last (parametric, catches any slug)
# ---------------------------------------------------------------------------

@router.get("/words/{word}")
async def get_word_detail(
    word: str,
    db=Depends(get_db),
    r=Depends(get_redis_client),
):
    """
    Full detail for a single word including all sources.
    No auth required.
    """
    cache_key = f"vocab:word:{word.lower()}"
    if r:
        try:
            cached = r.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

    doc = db.vocab_cards.find_one({"word_key": word.lower()}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Word '{word}' not found")

    if r:
        try:
            r.setex(cache_key, REDIS_TTL_DAILY, json.dumps(doc, default=str))
        except Exception:
            pass

    return doc
