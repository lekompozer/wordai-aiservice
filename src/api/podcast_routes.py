"""
BBC 6 Minute English Podcast API Routes

Endpoints:
  GET  /api/v1/podcasts                              — List episodes (public)
  GET  /api/v1/podcasts/{podcast_id}                 — Episode detail (public) — includes vocabulary_raw + transcript_vi preview
  GET  /api/v1/podcasts/{podcast_id}/vocabulary      — Enriched vocab + transcript_vi (public, no auth)
                                                       + grammar_points (only when authenticated)
  GET  /api/v1/podcasts/{podcast_id}/gaps            — All gap difficulties (public)
  GET  /api/v1/podcasts/{podcast_id}/gaps/{diff}     — Gap exercise (auth, premium OR 3/day free)
  POST /api/v1/podcasts/{podcast_id}/gaps/{diff}/submit — Submit answers (auth, premium OR 3/day free)

Access model:
  PUBLIC (no auth):
    - Episode metadata, audio player, image
    - vocabulary_raw (6 BBC vocab words, English only)
    - transcript_vi (4000-char DeepSeek preview translation) — for SEO pages
    - Enriched vocabulary definitions (definition_vi) via /vocabulary endpoint

  AUTH ONLY (logged-in users):
    - grammar_points (returned in /vocabulary when Authorization header present)

  PREMIUM (Song or Conversation subscription):
    - Gap exercises (3/day free for non-premium)
    - Grammar practice
    - Speak with AI

Collections: bbc_podcasts, podcast_vocabulary, podcast_gaps, user_daily_submits
"""

import os
import re
import json
import logging
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException, Depends, Query

from src.database.db_manager import DBManager
from src.middleware.firebase_auth import get_current_user, get_current_user_optional

logger = logging.getLogger("chatbot")

router = APIRouter(prefix="/api/v1/podcasts", tags=["BBC Podcast Learning"])


def get_db():
    db_manager = DBManager()
    return db_manager.db


# ---------------------------------------------------------------------------
# Access-control helpers  (mirrors conversation_learning_routes pattern)
# ---------------------------------------------------------------------------


async def check_user_premium(user_id: str, db) -> bool:
    """Return True when user has an active Song or Conversation subscription."""
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


async def check_podcast_daily_limit(user_id: str, db) -> dict:
    """
    Return the free-user daily podcast limit status.
    Free users may access 3 unique podcast gap exercises per day (UTC reset).
    Returns: {is_premium, daily_used, remaining_free}
    """
    is_premium = await check_user_premium(user_id, db)
    if is_premium:
        return {"is_premium": True, "daily_used": 0, "remaining_free": -1}

    from datetime import date

    today = date.today().isoformat()
    record = db["user_daily_submits"].find_one({"user_id": user_id, "date": today})
    used = len(record.get("podcast_ids", [])) if record else 0
    return {
        "is_premium": False,
        "daily_used": used,
        "remaining_free": max(0, 3 - used),
    }


async def is_podcast_accessed_today(user_id: str, podcast_id: str, db) -> bool:
    """Return True if this podcast was already accessed for gaps today."""
    from datetime import date

    today = date.today().isoformat()
    record = db["user_daily_submits"].find_one({"user_id": user_id, "date": today})
    if not record:
        return False
    return podcast_id in record.get("podcast_ids", [])


async def increment_podcast_daily(user_id: str, podcast_id: str, db):
    """Record free-user gap access for a podcast today (idempotent via $addToSet)."""
    is_premium = await check_user_premium(user_id, db)
    if is_premium:
        return

    from datetime import date

    today = date.today().isoformat()
    db["user_daily_submits"].update_one(
        {"user_id": user_id, "date": today},
        {
            "$addToSet": {"podcast_ids": podcast_id},
            "$set": {"updated_at": datetime.utcnow()},
            "$setOnInsert": {"created_at": datetime.utcnow()},
        },
        upsert=True,
    )


# ---------------------------------------------------------------------------
# DeepSeek prompt for podcast vocabulary enrichment
# ---------------------------------------------------------------------------

_PODCAST_VOCAB_PROMPT = """You are an English language teacher for Vietnamese learners.

Given a BBC 6 Minute English episode, provide:
1. Vietnamese definitions and example sentences for each vocabulary word
2. 4-5 grammar patterns found in the transcript
3. Vietnamese translation of the transcript (speaker by speaker, line by line)

Return ONLY valid JSON, no markdown fences:
{{
  "vocabulary": [
    {{
      "word": "word or phrase",
      "definition_en": "English definition from BBC",
      "definition_vi": "Định nghĩa bằng tiếng Việt",
      "example": "exact sentence from transcript using this word",
      "pos_tag": "NOUN|VERB|ADJ|ADV|PHRASE|IDIOM|PREP"
    }}
  ],
  "grammar_points": [
    {{
      "pattern": "Grammar pattern name",
      "explanation_en": "Explanation in English",
      "explanation_vi": "Giải thích bằng tiếng Việt",
      "example": "Exact example from transcript"
    }}
  ],
  "transcript_vi": "Phil: Xin chào, đây là chương trình...\\nSam: ..."
}}

Episode title: "{title}"

Vocabulary (6 words from BBC):
{vocab_json}

Transcript (first 2500 characters):
{transcript_excerpt}
"""


# ---------------------------------------------------------------------------
# Gap generation helpers
# ---------------------------------------------------------------------------


def _generate_gaps_from_vocabulary(
    transcript_turns: list, vocabulary_raw: list, difficulty: str
) -> dict:
    """
    Generate gap-fill exercise from vocabulary words in transcript.

    Easy:   6 gaps — the 6 BBC vocabulary words
    Medium: min(10, 6+extra) gaps — 6 vocab + up to 4 common content words
    Hard:   min(15, 6+extra) gaps — 6 vocab + up to 9 key content words
    """
    gaps = []
    used_turns = set()  # (turn_index, word) to avoid double-gapping

    target_vocab_words = vocabulary_raw[:6]

    # Step 1: Find vocabulary words in transcript turns
    for vocab_item in target_vocab_words:
        word = vocab_item["word"]
        # Normalize: strip trailing parenthetical like "(something)"
        word_clean = re.sub(r"\s*\(.*?\)", "", word).strip()
        # Also try the full original word
        candidates = list({word, word_clean})

        found = False
        for turn_idx, turn in enumerate(transcript_turns):
            text = turn.get("text", "")
            for candidate in candidates:
                pattern = re.compile(re.escape(candidate), re.IGNORECASE)
                m = pattern.search(text)
                if m and (turn_idx, word) not in used_turns:
                    start = m.start()
                    end = m.end()
                    context_before = text[max(0, start - 60) : start]
                    context_after = text[end : end + 60]
                    word_found = text[start:end]

                    gaps.append(
                        {
                            "position": len(gaps),
                            "turn_index": turn_idx,
                            "speaker": turn.get("speaker", ""),
                            "correct_answer": word_found,
                            "context_before": context_before,
                            "context_after": context_after,
                        }
                    )
                    used_turns.add((turn_idx, word))
                    found = True
                    break
            if found:
                break

    # Step 2: For medium/hard — find additional content words
    if difficulty in ("medium", "hard"):
        extra_target = 4 if difficulty == "medium" else 9

        # Collect candidate extra words: adjectives/adverbs ending in -ly, -ful, -less
        # or past participles, or notable verbs (length > 5, not common stopwords)
        STOPWORDS = {
            "about",
            "after",
            "again",
            "also",
            "although",
            "always",
            "another",
            "because",
            "been",
            "before",
            "being",
            "between",
            "both",
            "could",
            "does",
            "during",
            "each",
            "even",
            "every",
            "first",
            "from",
            "have",
            "here",
            "however",
            "into",
            "just",
            "know",
            "like",
            "little",
            "look",
            "made",
            "make",
            "many",
            "might",
            "more",
            "most",
            "much",
            "must",
            "never",
            "next",
            "often",
            "only",
            "other",
            "over",
            "same",
            "says",
            "should",
            "since",
            "some",
            "still",
            "such",
            "than",
            "that",
            "their",
            "them",
            "then",
            "there",
            "these",
            "they",
            "thing",
            "think",
            "this",
            "those",
            "time",
            "very",
            "want",
            "well",
            "were",
            "what",
            "when",
            "where",
            "which",
            "while",
            "will",
            "with",
            "would",
            "your",
        }

        extra_words = []
        already_used_words = {g["correct_answer"].lower() for g in gaps}

        for turn_idx, turn in enumerate(transcript_turns):
            text = turn.get("text", "")
            words = re.findall(r"\b[a-zA-Z]{6,}\b", text)
            for w in words:
                wl = w.lower()
                if (
                    wl not in STOPWORDS
                    and wl not in already_used_words
                    and not any(wl in g["correct_answer"].lower() for g in gaps)
                    and (turn_idx, w) not in used_turns
                ):
                    # Check it's actually a content-ish word (simple heuristic)
                    if (
                        wl.endswith(
                            (
                                "tion",
                                "ness",
                                "ment",
                                "ful",
                                "less",
                                "ity",
                                "ive",
                                "ous",
                                "ing",
                                "ed",
                            )
                        )
                        or len(wl) >= 8
                    ):
                        extra_words.append((turn_idx, turn, w))
                        already_used_words.add(wl)
                        used_turns.add((turn_idx, w))
                        if len(extra_words) >= extra_target:
                            break
            if len(extra_words) >= extra_target:
                break

        for turn_idx, turn, w in extra_words:
            text = turn.get("text", "")
            pattern = re.compile(r"\b" + re.escape(w) + r"\b", re.IGNORECASE)
            m = pattern.search(text)
            if m:
                start, end = m.start(), m.end()
                gaps.append(
                    {
                        "position": len(gaps),
                        "turn_index": turn_idx,
                        "speaker": turn.get("speaker", ""),
                        "correct_answer": text[start:end],
                        "context_before": text[max(0, start - 60) : start],
                        "context_after": text[end : end + 60],
                    }
                )

    # Step 3: Build transcript_with_gaps
    # Clone the turns and apply gaps
    gapped_turns = [dict(t) for t in transcript_turns]
    for gap in sorted(gaps, key=lambda g: (g["turn_index"], -g["turn_index"])):
        ti = gap["turn_index"]
        answer = gap["correct_answer"]
        gapped_turns[ti]["text"] = re.sub(
            re.escape(answer),
            "___",
            gapped_turns[ti]["text"],
            count=1,
            flags=re.IGNORECASE,
        )

    transcript_with_gaps = "\n\n".join(
        f"{t.get('speaker', '')}\n{t.get('text', '')}" for t in gapped_turns
    )

    return {
        "gaps": gaps,
        "gap_count": len(gaps),
        "transcript_with_gaps": transcript_with_gaps,
    }


# ---------------------------------------------------------------------------
# ENDPOINT 1: List Podcasts
# ---------------------------------------------------------------------------


@router.get("")
async def list_podcasts(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=50),
    level: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    db=Depends(get_db),
):
    """
    List BBC 6 Minute English podcast episodes.
    Public — no authentication required.
    """
    query: Dict[str, Any] = {"category": "bbc_6min_english"}

    if level and level in ("beginner", "intermediate", "advanced"):
        query["level"] = level

    if search:
        safe = re.escape(search.strip())[:100]
        query["$or"] = [
            {"title": {"$regex": safe, "$options": "i"}},
            {"description": {"$regex": safe, "$options": "i"}},
        ]

    col = db["bbc_podcasts"]
    total = col.count_documents(query)
    skip = (page - 1) * limit

    docs = list(
        col.find(
            query,
            {
                "_id": 0,
                "podcast_id": 1,
                "title": 1,
                "description": 1,
                "image_url": 1,
                "published_date": 1,
                "level": 1,
                "audio_url": 1,
                "vocabulary_raw": 1,
                "transcript_turns": 1,
            },
        )
        .sort("published_date", -1)
        .skip(skip)
        .limit(limit)
    )

    podcasts = []
    for doc in docs:
        podcasts.append(
            {
                "podcast_id": doc.get("podcast_id"),
                "title": doc.get("title"),
                "description": doc.get("description"),
                "image_url": doc.get("image_url"),
                "published_date": doc.get("published_date"),
                "level": doc.get("level", "intermediate"),
                "audio_url": doc.get("audio_url"),
                "vocabulary_count": len(doc.get("vocabulary_raw") or []),
                "transcript_turns_count": len(doc.get("transcript_turns") or []),
            }
        )

    return {
        "podcasts": podcasts,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": max(1, (total + limit - 1) // limit),
    }


# ---------------------------------------------------------------------------
# ENDPOINT 2: Episode Detail
# ---------------------------------------------------------------------------


@router.get("/{podcast_id}")
async def get_podcast_detail(
    podcast_id: str,
    db=Depends(get_db),
):
    """
    Get full episode details: metadata, embed, introduction, vocabulary_raw, transcript_vi preview.
    Public — no authentication required.

    Includes:
    - vocabulary_raw: 6 BBC vocab words (English only) for SEO
    - transcript_vi: partial Vietnamese translation (~4000-char DeepSeek preview)
    Grammar points are NOT included — require auth via /vocabulary endpoint.
    """
    col = db["bbc_podcasts"]
    doc = col.find_one({"podcast_id": podcast_id}, {"_id": 0})

    if not doc:
        raise HTTPException(status_code=404, detail="Podcast episode not found")

    # Don't expose the raw transcript text blob — only structured turns
    doc.pop("transcript", None)

    # Summarise transcript_turns count (don't expose full turns on public endpoint)
    turns = doc.get("transcript_turns") or []
    doc["transcript_turns_count"] = len(turns)
    doc.pop("transcript_turns", None)

    # Attach transcript_vi preview from vocabulary collection (no auth needed)
    vocab_doc = db["podcast_vocabulary"].find_one(
        {"podcast_id": podcast_id},
        {"_id": 0, "transcript_vi": 1},
    )
    doc["transcript_vi"] = (vocab_doc or {}).get("transcript_vi", "")

    return doc


# ---------------------------------------------------------------------------
# ENDPOINT 3: Vocabulary & Grammar
# ---------------------------------------------------------------------------


@router.get("/{podcast_id}/vocabulary")
async def get_podcast_vocabulary(
    podcast_id: str,
    current_user: dict = Depends(get_current_user_optional),
    db=Depends(get_db),
):
    """
    Get enriched vocabulary (with Vietnamese definitions) and transcript_vi preview.

    Public (no auth): vocabulary (enriched with definition_vi) + transcript_vi
    Authenticated: above + grammar_points

    Content is pre-generated by bulk enrich script; falls back to on-demand DeepSeek.
    """
    user_id = current_user["uid"] if current_user else None
    is_authenticated = user_id is not None

    # ── 1. Return from cache if vocabulary is already enriched ──────────
    existing = db["podcast_vocabulary"].find_one(
        {"podcast_id": podcast_id},
        {
            "_id": 0,
            "vocabulary": 1,
            "grammar_points": 1,
            "transcript_vi": 1,
            "generated_by": 1,
        },
    )
    vocab_is_enriched = (
        existing is not None
        and existing.get("vocabulary")
        and existing["vocabulary"][0].get("definition_vi")
    )
    if vocab_is_enriched:
        resp = {
            "podcast_id": podcast_id,
            "vocabulary": existing.get("vocabulary", []),
            "transcript_vi": existing.get("transcript_vi", ""),
            "generated_by": existing.get("generated_by", "deepseek-chat"),
        }
        # grammar_points + full transcript_turns only for authenticated users
        if is_authenticated:
            resp["grammar_points"] = existing.get("grammar_points", [])
            podcast_for_turns = db["bbc_podcasts"].find_one(
                {"podcast_id": podcast_id},
                {"_id": 0, "transcript_turns": 1},
            )
            resp["transcript_turns"] = (podcast_for_turns or {}).get(
                "transcript_turns", []
            )
        return resp

    # ── 2. Fetch podcast data ────────────────────────────────────────────
    podcast = db["bbc_podcasts"].find_one(
        {"podcast_id": podcast_id},
        {"_id": 0, "title": 1, "vocabulary_raw": 1, "transcript_turns": 1},
    )
    if not podcast:
        raise HTTPException(status_code=404, detail="Podcast episode not found")

    vocabulary_raw = podcast.get("vocabulary_raw") or []
    transcript_turns = podcast.get("transcript_turns") or []

    transcript_text = "\n".join(
        f"{t.get('speaker', '')}: {t.get('text', '')}" for t in transcript_turns
    )

    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not deepseek_key:
        resp = {
            "podcast_id": podcast_id,
            "vocabulary": vocabulary_raw,
            "transcript_vi": "",
            "generated_by": "raw",
        }
        if is_authenticated:
            resp["grammar_points"] = []
        return resp

    # ── 3. Generate via DeepSeek (on-demand fallback) ────────────────────
    try:
        from openai import OpenAI as _OpenAI

        vocab_json = json.dumps(
            [
                {"word": v["word"], "definition_en": v.get("definition_en", "")}
                for v in vocabulary_raw
            ],
            ensure_ascii=False,
            indent=2,
        )
        prompt = _PODCAST_VOCAB_PROMPT.format(
            title=podcast.get("title", ""),
            vocab_json=vocab_json,
            transcript_excerpt=transcript_text[:2500],
        )

        def _call():
            client = _OpenAI(
                api_key=deepseek_key, base_url="https://api.deepseek.com/v1"
            )
            resp = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=3000,
            )
            return resp.choices[0].message.content.strip()

        raw_response = await asyncio.to_thread(_call)
        raw_response = re.sub(
            r"^```[a-z]*\n?|```$", "", raw_response.strip(), flags=re.MULTILINE
        ).strip()
        result = json.loads(raw_response)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[podcast/{podcast_id}/vocabulary] DeepSeek error: {e}")
        raise HTTPException(
            status_code=503, detail="AI service temporarily unavailable"
        )

    vocabulary = result.get("vocabulary") or vocabulary_raw
    grammar_points = result.get("grammar_points") or []
    transcript_vi = result.get("transcript_vi") or ""

    # ── 4. Cache in DB ────────────────────────────────────────────────────
    now = datetime.utcnow()
    db["podcast_vocabulary"].update_one(
        {"podcast_id": podcast_id},
        {
            "$set": {
                "podcast_id": podcast_id,
                "vocabulary": vocabulary,
                "grammar_points": grammar_points,
                "transcript_vi": transcript_vi,
                "generated_by": "deepseek-chat",
                "first_generated_by": user_id,
                "generated_at": now,
                "updated_at": now,
            }
        },
        upsert=True,
    )

    resp = {
        "podcast_id": podcast_id,
        "vocabulary": vocabulary,
        "transcript_vi": transcript_vi,
        "generated_by": "deepseek-chat",
    }
    if is_authenticated:
        resp["grammar_points"] = grammar_points
        resp["transcript_turns"] = transcript_turns
    return resp


# ---------------------------------------------------------------------------
# ENDPOINT 4: All Gap Difficulties (public overview)
# ---------------------------------------------------------------------------


@router.get("/{podcast_id}/gaps")
async def get_all_gaps(
    podcast_id: str,
    db=Depends(get_db),
):
    """
    Get available gap-fill exercise levels for an episode.
    Public — no authentication required.
    """
    col = db["bbc_podcasts"]
    if not col.find_one({"podcast_id": podcast_id}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Podcast episode not found")

    gaps_col = db["podcast_gaps"]
    docs = list(
        gaps_col.find(
            {"podcast_id": podcast_id},
            {"_id": 0, "podcast_id": 1, "difficulty": 1, "gap_count": 1},
        )
    )

    result: Dict[str, Any] = {"podcast_id": podcast_id, "gaps": {}}
    for doc in docs:
        result["gaps"][doc["difficulty"]] = {
            "difficulty": doc["difficulty"],
            "gap_count": doc["gap_count"],
        }

    for diff in ("easy", "medium", "hard"):
        if diff not in result["gaps"]:
            result["gaps"][diff] = None

    return result


# ---------------------------------------------------------------------------
# ENDPOINT 5: Get Gap Exercise (auth, premium OR 3/day free)
# ---------------------------------------------------------------------------


@router.get("/{podcast_id}/gaps/{difficulty}")
async def get_gap_exercise(
    podcast_id: str,
    difficulty: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Get gap-fill exercise for specified difficulty.

    Access rules:
    - Premium users (Song or Conversation subscription) → unlimited
    - Free users → 3 unique podcasts per day; re-accessing same podcast today is free

    difficulty: easy | medium | hard
    """
    if difficulty not in ("easy", "medium", "hard"):
        raise HTTPException(
            status_code=400, detail="Invalid difficulty. Must be: easy, medium, or hard"
        )

    user_id = current_user["uid"]

    # ── Access control ──────────────────────────────────────────────────
    is_premium = await check_user_premium(user_id, db)
    if not is_premium:
        already_today = await is_podcast_accessed_today(user_id, podcast_id, db)
        if not already_today:
            limit = await check_podcast_daily_limit(user_id, db)
            if limit["remaining_free"] == 0:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "daily_limit_reached",
                        "message": "Bạn đã dùng hết 3 lượt miễn phí hôm nay. Nâng cấp Premium để luyện tập không giới hạn!",
                        "remaining": 0,
                    },
                )
            await increment_podcast_daily(user_id, podcast_id, db)

    # Check episode exists
    podcast = db["bbc_podcasts"].find_one(
        {"podcast_id": podcast_id},
        {"_id": 0, "vocabulary_raw": 1, "transcript_turns": 1, "title": 1},
    )
    if not podcast:
        raise HTTPException(status_code=404, detail="Podcast episode not found")

    # Return cached gaps if available
    gaps_col = db["podcast_gaps"]
    cached = gaps_col.find_one(
        {"podcast_id": podcast_id, "difficulty": difficulty}, {"_id": 0}
    )
    if cached:
        return cached

    # Generate gaps on the fly
    vocabulary_raw = podcast.get("vocabulary_raw") or []
    transcript_turns = podcast.get("transcript_turns") or []

    if not transcript_turns:
        raise HTTPException(
            status_code=422,
            detail="Episode has no transcript turns to generate gaps from",
        )
    if not vocabulary_raw:
        raise HTTPException(
            status_code=422,
            detail="Episode has no vocabulary to generate gaps from",
        )

    generated = _generate_gaps_from_vocabulary(
        transcript_turns, vocabulary_raw, difficulty
    )

    gaps_doc = {
        "podcast_id": podcast_id,
        "difficulty": difficulty,
        "gap_count": generated["gap_count"],
        "gaps": generated["gaps"],
        "transcript_with_gaps": generated["transcript_with_gaps"],
        "created_at": datetime.utcnow(),
    }

    gaps_col.update_one(
        {"podcast_id": podcast_id, "difficulty": difficulty},
        {"$set": gaps_doc},
        upsert=True,
    )

    return gaps_doc


# ---------------------------------------------------------------------------
# ENDPOINT 6: Submit Gap Answers (auth, premium OR 3/day free)
# ---------------------------------------------------------------------------


@router.post("/{podcast_id}/gaps/{difficulty}/submit")
async def submit_gap_answers(
    podcast_id: str,
    difficulty: str,
    request: Dict[str, Any],
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Submit gap-fill answers and receive score + per-gap feedback.

    Access rules: same as GET gaps/{difficulty} — premium unlimited, free 3 unique/day.

    Request body:
    {
      "answers": {"0": "first and foremost", "1": "tolerant", ...},
      "time_spent": 93
    }
    """
    if difficulty not in ("easy", "medium", "hard"):
        raise HTTPException(
            status_code=400, detail="Invalid difficulty. Must be: easy, medium, or hard"
        )

    user_id = current_user["uid"]

    # ── Access control (same as GET) ────────────────────────────────────
    is_premium = await check_user_premium(user_id, db)
    if not is_premium:
        already_today = await is_podcast_accessed_today(user_id, podcast_id, db)
        if not already_today:
            limit = await check_podcast_daily_limit(user_id, db)
            if limit["remaining_free"] == 0:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "daily_limit_reached",
                        "message": "Bạn đã dùng hết 3 lượt miễn phí hôm nay. Nâng cấp Premium để luyện tập không giới hạn!",
                        "remaining": 0,
                    },
                )
            await increment_podcast_daily(user_id, podcast_id, db)

    answers: Dict[str, str] = request.get("answers") or {}
    time_spent: int = int(request.get("time_spent") or 0)

    if not answers:
        raise HTTPException(status_code=400, detail="Missing required field: answers")

    # Load gaps doc  (user_id already resolved above for access control)
    gaps_col = db["podcast_gaps"]
    gaps_doc = gaps_col.find_one(
        {"podcast_id": podcast_id, "difficulty": difficulty}, {"_id": 0}
    )

    if not gaps_doc:
        # Try to auto-generate if missing
        raise HTTPException(
            status_code=404,
            detail=f"Gaps not found for {podcast_id} [{difficulty}]. Call GET /gaps/{difficulty} first.",
        )

    gaps: List[Dict] = gaps_doc.get("gaps") or []
    total_gaps = len(gaps)

    if total_gaps == 0:
        raise HTTPException(status_code=422, detail="No gaps found in this exercise")

    # Evaluate answers
    results = []
    correct_count = 0

    for gap in gaps:
        pos = str(gap["position"])
        user_answer = (answers.get(pos) or "").strip().lower()
        correct_answer = gap["correct_answer"].strip().lower()

        # Accept minor whitespace differences
        is_correct = user_answer == correct_answer

        if is_correct:
            correct_count += 1

        results.append(
            {
                "position": gap["position"],
                "user_answer": answers.get(pos, ""),
                "correct_answer": gap["correct_answer"],
                "is_correct": is_correct,
            }
        )

    score = round((correct_count / total_gaps) * 100, 1) if total_gaps else 0.0

    return {
        "podcast_id": podcast_id,
        "difficulty": difficulty,
        "score": score,
        "correct_count": correct_count,
        "total_gaps": total_gaps,
        "time_spent": time_spent,
        "results": results,
    }
