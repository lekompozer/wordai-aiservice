"""
BBC 6 Minute English Podcast API Routes

Endpoints:
  GET  /api/v1/podcasts                              — List episodes (public)
  GET  /api/v1/podcasts/{podcast_id}                 — Episode detail (public)
  GET  /api/v1/podcasts/{podcast_id}/vocabulary      — Vocab + grammar (auth, 1 pt first use)
  GET  /api/v1/podcasts/{podcast_id}/gaps            — All gap difficulties (public)
  GET  /api/v1/podcasts/{podcast_id}/gaps/{diff}     — Gap exercise (auth)
  POST /api/v1/podcasts/{podcast_id}/gaps/{diff}/submit — Submit answers (auth)

Collections: bbc_podcasts, podcast_vocabulary, podcast_gaps
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
from src.middleware.firebase_auth import get_current_user

logger = logging.getLogger("chatbot")

router = APIRouter(prefix="/api/v1/podcasts", tags=["BBC Podcast Learning"])

POINTS_COST_PODCAST_VOCAB = 1  # 1 point per vocabulary access (first time)


def get_db():
    db_manager = DBManager()
    return db_manager.db


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
    Get full episode details: metadata, embed, introduction, transcript turns.
    Public — no authentication required.
    """
    col = db["bbc_podcasts"]
    doc = col.find_one({"podcast_id": podcast_id}, {"_id": 0})

    if not doc:
        raise HTTPException(status_code=404, detail="Podcast episode not found")

    # Don't expose the raw transcript text blob — only structured turns
    doc.pop("transcript", None)

    # Summarise transcript_turns count
    turns = doc.get("transcript_turns") or []
    doc["transcript_turns_count"] = len(turns)

    return doc


# ---------------------------------------------------------------------------
# ENDPOINT 3: Vocabulary & Grammar (auth, 1 pt first time)
# ---------------------------------------------------------------------------


@router.get("/{podcast_id}/vocabulary")
async def get_podcast_vocabulary(
    podcast_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Get enriched vocabulary (with Vietnamese definitions) and grammar points.

    Points rules:
    - AI Bundle → always free
    - User already paid → free (user_id already in paid_user_ids[])
    - First time → deduct 1 point, generate via DeepSeek if not cached
    """
    from src.services.points_service import get_points_service
    from src.middleware.ai_bundle_quota import check_ai_bundle_quota

    user_id = current_user["uid"]
    has_bundle = await check_ai_bundle_quota(user_id, db)

    # ── 1. Check paid status ────────────────────────────────────────────
    existing = db["podcast_vocabulary"].find_one(
        {"podcast_id": podcast_id},
        {
            "_id": 0,
            "vocabulary": 1,
            "grammar_points": 1,
            "transcript_vi": 1,
            "generated_by": 1,
            "paid_user_ids": 1,
        },
    )
    already_paid = has_bundle or (
        existing is not None and user_id in (existing.get("paid_user_ids") or [])
    )

    # ── 2. Deduct 1 point if first time ─────────────────────────────────
    new_balance = None
    if not already_paid:
        podcast_meta = db["bbc_podcasts"].find_one(
            {"podcast_id": podcast_id}, {"_id": 0, "title": 1}
        )
        if not podcast_meta:
            raise HTTPException(status_code=404, detail="Podcast episode not found")

        points_service = get_points_service()
        try:
            transaction = await points_service.deduct_points(
                user_id=user_id,
                amount=POINTS_COST_PODCAST_VOCAB,
                service="podcast_vocabulary",
                description=f"Xem từ vựng podcast: {podcast_meta.get('title', podcast_id)[:60]}",
            )
            new_balance = transaction.balance_after
        except Exception as e:
            if "Không đủ điểm" in str(e) or "insufficient" in str(e).lower():
                balance = await get_points_service().get_points_balance(user_id)
                raise HTTPException(
                    status_code=403,
                    detail=f"Không đủ điểm. Cần: {POINTS_COST_PODCAST_VOCAB}, Còn lại: {balance['points_remaining']}",
                )
            raise HTTPException(status_code=500, detail=str(e))

    points_deducted = 0 if (has_bundle or already_paid) else POINTS_COST_PODCAST_VOCAB

    # ── 3. Return from cache if vocabulary data is complete ─────────────
    vocab_is_enriched = (
        existing is not None
        and existing.get("vocabulary")
        and existing["vocabulary"][0].get("definition_vi")
    )
    if vocab_is_enriched:
        if not has_bundle and not already_paid:
            db["podcast_vocabulary"].update_one(
                {"podcast_id": podcast_id},
                {"$addToSet": {"paid_user_ids": user_id}},
            )
        return {
            "podcast_id": podcast_id,
            "vocabulary": existing.get("vocabulary", []),
            "grammar_points": existing.get("grammar_points", []),
            "transcript_vi": existing.get("transcript_vi", ""),
            "generated_by": existing.get("generated_by", "deepseek-chat"),
            "points_deducted": points_deducted,
            "new_balance": new_balance,
        }

    # ── 4. Fetch podcast data for DeepSeek ──────────────────────────────
    podcast = db["bbc_podcasts"].find_one(
        {"podcast_id": podcast_id},
        {"_id": 0, "title": 1, "vocabulary_raw": 1, "transcript_turns": 1},
    )
    if not podcast:
        raise HTTPException(status_code=404, detail="Podcast episode not found")

    vocabulary_raw = podcast.get("vocabulary_raw") or []
    transcript_turns = podcast.get("transcript_turns") or []

    # Build transcript excerpt for DeepSeek
    transcript_text = "\n".join(
        f"{t.get('speaker', '')}: {t.get('text', '')}" for t in transcript_turns
    )

    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not deepseek_key:
        # Return raw vocabulary without enrichment
        if not has_bundle and not already_paid:
            db["podcast_vocabulary"].update_one(
                {"podcast_id": podcast_id},
                {"$addToSet": {"paid_user_ids": user_id}},
                upsert=True,
            )
        return {
            "podcast_id": podcast_id,
            "vocabulary": vocabulary_raw,
            "grammar_points": [],
            "transcript_vi": "",
            "generated_by": "raw",
            "points_deducted": points_deducted,
            "new_balance": new_balance,
        }

    # ── 5. Call DeepSeek ─────────────────────────────────────────────────
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

    # ── 6. Cache in DB ───────────────────────────────────────────────────
    now = datetime.utcnow()
    save_update: dict = {
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
    }
    if not has_bundle:
        save_update["$addToSet"] = {"paid_user_ids": user_id}
    db["podcast_vocabulary"].update_one(
        {"podcast_id": podcast_id}, save_update, upsert=True
    )

    return {
        "podcast_id": podcast_id,
        "vocabulary": vocabulary,
        "grammar_points": grammar_points,
        "transcript_vi": transcript_vi,
        "generated_by": "deepseek-chat",
        "points_deducted": points_deducted,
        "new_balance": new_balance,
    }


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
# ENDPOINT 5: Get Gap Exercise (auth)
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
    Generates and caches gaps on first request.

    difficulty: easy | medium | hard
    """
    if difficulty not in ("easy", "medium", "hard"):
        raise HTTPException(
            status_code=400, detail="Invalid difficulty. Must be: easy, medium, or hard"
        )

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
# ENDPOINT 6: Submit Gap Answers (auth)
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

    answers: Dict[str, str] = request.get("answers") or {}
    time_spent: int = int(request.get("time_spent") or 0)

    if not answers:
        raise HTTPException(status_code=400, detail="Missing required field: answers")

    # Load gaps doc
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
