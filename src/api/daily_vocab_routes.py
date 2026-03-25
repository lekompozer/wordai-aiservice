"""
Daily Vocab API — "Daily Vocab by WordAI"

Free vocabulary learning app powered by WordAI's conversation & podcast content.

Endpoints:
  GET  /api/v1/daily-vocab/today           — Today's vocab cards (random, related by topic)
  GET  /api/v1/daily-vocab/random          — Random vocab card (optionally filter by topic/level)
  GET  /api/v1/daily-vocab/topics          — List all topics with word counts (no auth)
  GET  /api/v1/daily-vocab/grammar/today   — Today's grammar tip cards
  POST /api/v1/daily-vocab/save            — Save/unsave a word (requires auth)
  GET  /api/v1/daily-vocab/saved           — Get user's saved words (requires auth)
  DELETE /api/v1/daily-vocab/saved/{word}  — Remove saved word (requires auth)

Card structure returned per word:
  word, pos_tag, definition_en, definition_vi, ipa (generated server-side),
  example, source_type (conversation|podcast), source_id, source_title,
  topic_slug, topic_en, level, audio_url, start_sec, end_sec,
  image_url (Pixabay cached), related_words (same topic, different words)
"""

import hashlib
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
# CONSTANTS
# ---------------------------------------------------------------------------

CARDS_PER_DAY = 10  # words per daily set
GRAMMAR_PER_DAY = 3  # grammar points per daily set
REDIS_TTL_DAILY = 86400  # 24h cache for daily sets
REDIS_TTL_TOPICS = 3600  # 1h cache for topic list

# BBC podcast categories mapping to display labels
PODCAST_CATEGORY_LABELS = {
    "bbc_6min_english": "BBC 6 Minute English",
    "bbc_work_english": "BBC Work English",
    "bbc_news_english": "BBC News English",
}

# Topic → macro-category grouping (for filtering)
TOPIC_CATEGORIES = {
    "greetings_introductions": "Social",
    "family_relationships": "Social",
    "social_issues": "Social",
    "events_celebrations": "Social",
    "work_office": "Work & Career",
    "finance_money": "Work & Career",
    "technology_internet": "Technology",
    "science_research": "Science",
    "health_body": "Health & Wellness",
    "sports_fitness": "Health & Wellness",
    "food_drinks": "Lifestyle",
    "shopping": "Lifestyle",
    "travel_tourism": "Travel",
    "transportation": "Travel",
    "education_learning": "Education",
    "philosophy_ethics": "Culture & Ideas",
    "art_creativity": "Culture & Ideas",
    "entertainment_media": "Culture & Ideas",
    "politics_government": "Society",
    "home_accommodation": "Daily Life",
    "weather_seasons": "Daily Life",
    "hobbies_interests": "Hobbies",
    "emergency_safety": "Safety",
}


# ---------------------------------------------------------------------------
# DEPENDENCIES
# ---------------------------------------------------------------------------


def get_db():
    return DBManager().db


def get_redis_client():
    try:
        return redis.Redis(host="redis-server", port=6379, db=2, decode_responses=True)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------


def _day_seed() -> str:
    """Returns a date-based seed string (same for all users each day)."""
    return date.today().isoformat()


def _word_image_key(word: str) -> str:
    return f"vocab:img:{hashlib.md5(word.lower().encode()).hexdigest()[:8]}"


def _get_cached_image(r, word: str) -> Optional[str]:
    if not r:
        return None
    try:
        return r.get(_word_image_key(word))
    except Exception:
        return None


def _enrich_vocab_item(
    item: dict,
    source_type: str,
    source_id: str,
    source_title: str,
    topic_slug: str,
    topic_en: str,
    level: str,
    audio_url: Optional[str],
    start_sec: Optional[float],
    end_sec: Optional[float],
    image_url: Optional[str],
    related_words: list,
) -> dict:
    """Build a complete vocab card dict."""
    return {
        "word": item.get("word", ""),
        "pos_tag": item.get("pos_tag", ""),
        "definition_en": item.get("definition_en", ""),
        "definition_vi": item.get("definition_vi", ""),
        "example": item.get("example", ""),
        # IPA hints: generated lazily on frontend using Web Speech API or
        # a lightweight JS IPA library — not stored in DB today
        "ipa": None,
        # Source metadata for "Listen in context" button
        "source_type": source_type,  # "conversation" | "podcast"
        "source_id": source_id,
        "source_title": source_title,
        "topic_slug": topic_slug,
        "topic_en": topic_en,
        "topic_category": TOPIC_CATEGORIES.get(topic_slug, "General"),
        "level": level,
        # Audio context — frontend uses HTML5:
        #   const a = new Audio(audio_url); a.currentTime = start_sec - 1.5; a.play();
        "audio_url": audio_url,
        "start_sec": start_sec,
        "end_sec": end_sec,
        # Image (pre-fetched by Pixabay caching script, stored in DB)
        "image_url": image_url,
        # Related words in same topic (word + pos_tag only for chips)
        "related_words": related_words,
    }


def _fetch_vocab_from_conversations(
    db, topic_slug: str, level: Optional[str], exclude_words: set, limit: int
) -> list:
    """
    Pull vocabulary items from conversation_vocabulary + conversation_library.
    Returns list of enriched card dicts.
    """
    # Find conversation IDs for this topic+level
    conv_query: dict = {"topic_slug": topic_slug}
    if level:
        conv_query["level"] = level

    conv_ids = [
        c["conversation_id"]
        for c in db.conversation_library.find(
            conv_query,
            {
                "conversation_id": 1,
                "title": 1,
                "topic_slug": 1,
                "level": 1,
                "audio_info": 1,
            },
        ).limit(50)
    ]

    if not conv_ids:
        return []

    # Build a lookup of conv metadata
    conv_meta = {
        c["conversation_id"]: c
        for c in db.conversation_library.find(
            {"conversation_id": {"$in": conv_ids}},
            {
                "conversation_id": 1,
                "title": 1,
                "topic_slug": 1,
                "level": 1,
                "audio_info": 1,
            },
        )
    }

    # Get vocabulary docs for those conversations
    vocab_docs = list(
        db.conversation_vocabulary.find(
            {"conversation_id": {"$in": conv_ids}},
            {"conversation_id": 1, "vocabulary": 1},
        )
    )

    cards = []
    for vdoc in vocab_docs:
        cid = vdoc.get("conversation_id", "")
        meta = conv_meta.get(cid, {})
        title_obj = meta.get("title", {})
        source_title = (
            title_obj.get("en", cid) if isinstance(title_obj, dict) else str(title_obj)
        )
        conv_level = meta.get("level", "intermediate")
        audio_info = meta.get("audio_info", {})
        audio_url = audio_info.get("r2_url") if audio_info else None

        for item in vdoc.get("vocabulary", []):
            word = item.get("word", "").strip()
            if not word or word.lower() in exclude_words:
                continue
            cards.append(
                _enrich_vocab_item(
                    item=item,
                    source_type="conversation",
                    source_id=cid,
                    source_title=source_title,
                    topic_slug=topic_slug,
                    topic_en=topic_slug.replace("_", " ").title(),
                    level=conv_level,
                    audio_url=audio_url,
                    start_sec=None,  # conversations don't have per-word timestamps
                    end_sec=None,
                    image_url=None,  # filled by caller from Redis cache
                    related_words=[],  # filled by caller
                )
            )
            if len(cards) >= limit * 3:  # over-fetch to allow shuffling
                break
        if len(cards) >= limit * 3:
            break

    return cards


def _fetch_vocab_from_podcasts(
    db, exclude_words: set, limit: int, category: Optional[str] = None
) -> list:
    """
    Pull vocabulary items from podcast_vocabulary + bbc_podcasts (with timestamps).
    Returns list of enriched card dicts.
    """
    podcast_query: dict = {"vocabulary.0": {"$exists": True}}
    if category:
        # Filter by podcast category via joining on podcast_id
        podcast_ids = [
            p["podcast_id"]
            for p in db.bbc_podcasts.find(
                {"category": category, "whisper_aligned": True}, {"podcast_id": 1}
            ).limit(100)
        ]
        if podcast_ids:
            podcast_query["podcast_id"] = {"$in": podcast_ids}

    vocab_docs = list(
        db.podcast_vocabulary.find(
            podcast_query, {"podcast_id": 1, "vocabulary": 1}
        ).limit(100)
    )
    if not vocab_docs:
        return []

    # Build podcast metadata lookup with transcript_turns for timestamps
    podcast_ids = [d["podcast_id"] for d in vocab_docs]
    podcasts = {
        p["podcast_id"]: p
        for p in db.bbc_podcasts.find(
            {"podcast_id": {"$in": podcast_ids}},
            {
                "podcast_id": 1,
                "title": 1,
                "category": 1,
                "level": 1,
                "audio_url": 1,
                "transcript_turns": 1,
            },
        )
    }

    cards = []
    for vdoc in vocab_docs:
        pid = vdoc.get("podcast_id", "")
        podcast = podcasts.get(pid, {})
        podcast_cat = podcast.get("category", "")
        source_title = PODCAST_CATEGORY_LABELS.get(podcast_cat, "BBC Podcast")
        podcast_title = podcast.get("title", "")
        if podcast_title:
            source_title = f"{source_title} — {podcast_title}"
        level = podcast.get("level", "intermediate")
        audio_url = podcast.get("audio_url")
        turns = podcast.get("transcript_turns", [])

        # Build word → (start_sec, end_sec) from transcript_turns
        # Match example sentence to nearest turn
        def find_turn_for_example(example_text: str):
            if not turns or not example_text:
                return None, None
            ex_lower = example_text.lower()
            best_turn = None
            for t in turns:
                if any(w in t.get("text", "").lower() for w in ex_lower.split()[:4]):
                    best_turn = t
                    break
            if best_turn:
                # DB stores timestamps as milliseconds
                start_ms = best_turn.get("start_ms")
                end_ms = best_turn.get("end_ms")
                start_s = round(start_ms / 1000, 2) if start_ms is not None else None
                end_s = round(end_ms / 1000, 2) if end_ms is not None else None
                return start_s, end_s
            return None, None

        # Topic mapping for podcasts
        topic_slug_short = podcast_cat.replace("bbc_", "").replace("_english", "")
        topic_en_map = {
            "6min": "BBC 6 Minute English",
            "work": "Work & Office",
            "news": "News & Current Affairs",
        }
        topic_en = topic_en_map.get(topic_slug_short, "BBC English")

        for item in vdoc.get("vocabulary", []):
            word = item.get("word", "").strip()
            if not word or word.lower() in exclude_words:
                continue
            start_sec, end_sec = find_turn_for_example(item.get("example", ""))
            cards.append(
                _enrich_vocab_item(
                    item=item,
                    source_type="podcast",
                    source_id=pid,
                    source_title=source_title,
                    topic_slug=podcast_cat,
                    topic_en=topic_en,
                    level=level,
                    audio_url=audio_url,
                    start_sec=start_sec,
                    end_sec=end_sec,
                    image_url=None,
                    related_words=[],
                )
            )
            if len(cards) >= limit * 3:
                break
        if len(cards) >= limit * 3:
            break

    return cards


def _attach_images_and_related(
    r, cards: list, db, topic_slug: str, source_type: str
) -> list:
    """Fill image_url from Redis and build related_words chips."""
    # Build a pool of same-topic words for related chips
    same_topic_words = [{"word": c["word"], "pos_tag": c["pos_tag"]} for c in cards]

    for card in cards:
        # Image from Redis cache
        card["image_url"] = _get_cached_image(r, card["word"])

        # Related words: 5 different words from same topic
        related = [
            w for w in same_topic_words if w["word"].lower() != card["word"].lower()
        ]
        random.shuffle(related)
        card["related_words"] = related[:5]

    return cards


# ---------------------------------------------------------------------------
# ENDPOINTS
# ---------------------------------------------------------------------------


@router.get("/topics")
async def get_vocab_topics(db=Depends(get_db), r=Depends(get_redis_client)):
    """
    List all available topics with vocabulary counts.
    Public endpoint — no auth required.
    """
    cache_key = "vocab:topics:v1"
    if r:
        try:
            cached = r.get(cache_key)
            if cached:
                import json

                return json.loads(cached)
        except Exception:
            pass

    # Group conversation_vocabulary by topic_slug via conversation_library
    pipeline = [
        {
            "$lookup": {
                "from": "conversation_library",
                "localField": "conversation_id",
                "foreignField": "conversation_id",
                "as": "conv",
            }
        },
        {"$unwind": "$conv"},
        {"$unwind": "$vocabulary"},
        {
            "$group": {
                "_id": {
                    "topic_slug": "$conv.topic_slug",
                    "topic_en": {
                        "$arrayElemAt": [{"$objectToArray": "$conv.topic"}, 0]
                    },
                    "level": "$conv.level",
                },
                "word_count": {"$sum": 1},
            }
        },
        {"$sort": {"word_count": -1}},
    ]

    raw = list(db.conversation_vocabulary.aggregate(pipeline))

    topics: dict = {}
    for r_item in raw:
        slug = r_item["_id"].get("topic_slug", "")
        level = r_item["_id"].get("level", "intermediate")
        count = r_item["word_count"]
        if slug not in topics:
            topics[slug] = {
                "topic_slug": slug,
                "topic_en": slug.replace("_", " ").title(),
                "topic_category": TOPIC_CATEGORIES.get(slug, "General"),
                "levels": {},
                "total_words": 0,
            }
        topics[slug]["levels"][level] = topics[slug]["levels"].get(level, 0) + count
        topics[slug]["total_words"] += count

    # Add BBC podcast topics
    podcast_counts = list(
        db.podcast_vocabulary.aggregate(
            [
                {"$unwind": "$vocabulary"},
                {
                    "$lookup": {
                        "from": "bbc_podcasts",
                        "localField": "podcast_id",
                        "foreignField": "podcast_id",
                        "as": "p",
                    }
                },
                {"$unwind": "$p"},
                {"$group": {"_id": "$p.category", "word_count": {"$sum": 1}}},
            ]
        )
    )
    for pc in podcast_counts:
        cat = pc["_id"] or ""
        label = PODCAST_CATEGORY_LABELS.get(cat, cat)
        slug = f"podcast_{cat}"
        topics[slug] = {
            "topic_slug": slug,
            "topic_en": label,
            "topic_category": "BBC Podcast",
            "levels": {"intermediate": pc["word_count"]},
            "total_words": pc["word_count"],
        }

    result = sorted(topics.values(), key=lambda x: -x["total_words"])

    if r:
        try:
            import json

            r.setex(cache_key, REDIS_TTL_TOPICS, json.dumps(result))
        except Exception:
            pass

    return result


@router.get("/today")
async def get_today_vocab(
    topic_slug: Optional[str] = Query(None, description="Filter by topic slug"),
    level: Optional[str] = Query(None, description="beginner|intermediate|advanced"),
    source: Optional[str] = Query(None, description="conversation|podcast"),
    db=Depends(get_db),
    r=Depends(get_redis_client),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """
    Return today's vocabulary card set (10 words).
    Same cards for same topic/level/day (deterministic seed).
    No auth required — free feature.
    """
    seed_key = f"{_day_seed()}:{topic_slug or 'all'}:{level or 'all'}:{source or 'all'}"
    cache_key = f"vocab:daily:{hashlib.md5(seed_key.encode()).hexdigest()[:12]}"

    if r:
        try:
            cached = r.get(cache_key)
            if cached:
                import json

                return json.loads(cached)
        except Exception:
            pass

    exclude_words: set = set()
    cards: list = []

    # Determine sources to pull from
    use_conv = source in (None, "conversation")
    use_podcast = source in (None, "podcast")

    if use_conv:
        if topic_slug:
            cards += _fetch_vocab_from_conversations(
                db, topic_slug, level, exclude_words, CARDS_PER_DAY
            )
        else:
            # Pick random topic for today using day seed
            rng = random.Random(_day_seed())
            topics_available = [
                t["topic_slug"]
                for t in db.conversation_library.aggregate(
                    [
                        {"$group": {"_id": "$topic_slug"}},
                    ]
                )
            ]
            if topics_available:
                chosen_topic = rng.choice(topics_available)
                cards += _fetch_vocab_from_conversations(
                    db, chosen_topic, level, exclude_words, CARDS_PER_DAY
                )

    if use_podcast and len(cards) < CARDS_PER_DAY:
        remaining = CARDS_PER_DAY - len(cards)
        podcast_cat = None
        if topic_slug and topic_slug.startswith("podcast_"):
            podcast_cat = topic_slug.replace("podcast_", "")
        cards += _fetch_vocab_from_podcasts(db, exclude_words, remaining, podcast_cat)

    if not cards:
        raise HTTPException(
            status_code=404, detail="No vocabulary found for this filter"
        )

    # Deduplicate by word
    seen: set = set()
    unique_cards: list = []
    for c in cards:
        w = c["word"].lower()
        if w not in seen:
            seen.add(w)
            unique_cards.append(c)

    # Shuffle deterministically by day seed
    rng = random.Random(_day_seed() + (topic_slug or "") + (level or ""))
    rng.shuffle(unique_cards)
    result_cards = unique_cards[:CARDS_PER_DAY]

    # Fill images and related words
    result_cards = _attach_images_and_related(
        r, result_cards, db, topic_slug or "", source or "conversation"
    )

    response = {
        "date": _day_seed(),
        "topic_slug": topic_slug,
        "level": level,
        "total": len(result_cards),
        "cards": result_cards,
    }

    if r:
        try:
            import json

            r.setex(cache_key, REDIS_TTL_DAILY, json.dumps(response))
        except Exception:
            pass

    return response


@router.get("/random")
async def get_random_vocab(
    topic_slug: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    source: Optional[str] = Query(None, description="conversation|podcast"),
    exclude: Optional[str] = Query(
        None, description="Comma-separated words to exclude"
    ),
    db=Depends(get_db),
    r=Depends(get_redis_client),
):
    """
    Return a single random vocabulary card.
    Used when user swipes to next card (truly random each call).
    No auth required.
    """
    exclude_words = {w.strip().lower() for w in (exclude or "").split(",") if w.strip()}

    cards: list = []
    use_conv = source in (None, "conversation")
    use_podcast = source in (None, "podcast")

    if use_conv and topic_slug and not topic_slug.startswith("podcast_"):
        cards += _fetch_vocab_from_conversations(
            db, topic_slug, level, exclude_words, 5
        )

    if use_podcast and (not cards or topic_slug and topic_slug.startswith("podcast_")):
        podcast_cat = None
        if topic_slug and topic_slug.startswith("podcast_"):
            podcast_cat = topic_slug.replace("podcast_", "")
        cards += _fetch_vocab_from_podcasts(db, exclude_words, 5, podcast_cat)

    if not cards:
        # Fallback: any topic
        cards += _fetch_vocab_from_conversations(
            db, "technology_internet", level, exclude_words, 10
        )

    if not cards:
        raise HTTPException(status_code=404, detail="No vocabulary found")

    card = random.choice(cards)
    card["image_url"] = _get_cached_image(r, card["word"])

    # Related words
    same_words = [
        {"word": c["word"], "pos_tag": c["pos_tag"]}
        for c in cards
        if c["word"] != card["word"]
    ]
    random.shuffle(same_words)
    card["related_words"] = same_words[:5]

    return card


@router.get("/grammar/today")
async def get_today_grammar(
    topic_slug: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    source: Optional[str] = Query(None, description="conversation|podcast"),
    db=Depends(get_db),
    r=Depends(get_redis_client),
):
    """
    Return today's grammar tip cards (3 patterns).
    Each card has: pattern, explanation_en, explanation_vi, example, source link.
    No auth required.
    """
    seed_key = f"grammar:{_day_seed()}:{topic_slug or 'all'}:{level or 'all'}"
    cache_key = f"vocab:grammar:{hashlib.md5(seed_key.encode()).hexdigest()[:12]}"

    if r:
        try:
            cached = r.get(cache_key)
            if cached:
                import json

                return json.loads(cached)
        except Exception:
            pass

    grammar_items: list = []

    # Pull from conversation_vocabulary
    conv_query: dict = {}
    if topic_slug and not topic_slug.startswith("podcast_"):
        conv_ids = [
            c["conversation_id"]
            for c in db.conversation_library.find(
                {"topic_slug": topic_slug, **({"level": level} if level else {})},
                {"conversation_id": 1},
            ).limit(30)
        ]
        conv_query["conversation_id"] = {"$in": conv_ids}

    conv_vocab_docs = list(
        db.conversation_vocabulary.find(
            {"grammar_points.0": {"$exists": True}, **conv_query},
            {"conversation_id": 1, "grammar_points": 1},
        ).limit(50)
    )

    for vdoc in conv_vocab_docs:
        cid = vdoc.get("conversation_id", "")
        for gp in vdoc.get("grammar_points", []):
            grammar_items.append(
                {
                    **gp,
                    "source_type": "conversation",
                    "source_id": cid,
                }
            )

    # Pull from podcast_vocabulary
    podcast_grammar_docs = list(
        db.podcast_vocabulary.find(
            {"grammar_points.0": {"$exists": True}},
            {"podcast_id": 1, "grammar_points": 1},
        ).limit(50)
    )
    for vdoc in podcast_grammar_docs:
        pid = vdoc.get("podcast_id", "")
        for gp in vdoc.get("grammar_points", []):
            grammar_items.append(
                {
                    **gp,
                    "source_type": "podcast",
                    "source_id": pid,
                }
            )

    if not grammar_items:
        raise HTTPException(status_code=404, detail="No grammar data found")

    # Deterministic shuffle by day
    rng = random.Random(_day_seed() + (topic_slug or "") + (level or ""))
    rng.shuffle(grammar_items)
    selected = grammar_items[:GRAMMAR_PER_DAY]

    response = {
        "date": _day_seed(),
        "total": len(selected),
        "grammar": selected,
    }

    if r:
        try:
            import json

            r.setex(cache_key, REDIS_TTL_DAILY, json.dumps(response))
        except Exception:
            pass

    return response


# ---------------------------------------------------------------------------
# SAVED WORDS (requires auth)
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
