"""
Pronunciation API Routes

POST /api/v1/pronunciation/transcribe
  - Audio → English transcript using faster-whisper
  - Input:  {audio_base64, audio_mime_type?}
  - Cost:   FREE — 10 uses/day per user
  - Auth:   required (Firebase login)

POST /api/v1/pronunciation/score
  - Audio + expected_text → phoneme-level pronunciation score
  - Works for word / phrase / full sentence
  - Input:  {audio_base64, expected_text, audio_mime_type?}
  - Cost:   FREE — 10 uses/day per user
  - Auth:   required (Firebase login)

Model loading:
  - Models are lazy-loaded on first request (NOT at startup)
  - faster-whisper tiny: ~75 MB, already cached from alignment batch
  - Wav2Vec2 lv-60-espeak: ~370 MB, downloaded on first score request
"""

import base64
import logging
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from src.database.db_manager import DBManager
from src.middleware.firebase_auth import get_current_user

logger = logging.getLogger("chatbot")

router = APIRouter(prefix="/api/v1/pronunciation", tags=["Pronunciation Assessment"])

# Daily limit per endpoint per user (free, no points required)
DAILY_LIMIT = 10


def get_db():
    return DBManager().db


def _decode_audio(body: dict) -> bytes:
    """Decode audio_base64 from request body. Raises 400 if missing/invalid."""
    raw = body.get("audio_base64", "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="audio_base64 is required")
    try:
        return base64.b64decode(raw)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 audio data")


def _check_and_increment_daily_limit(user_id: str, action: str, db) -> dict:
    """
    Check and atomically increment daily usage for pronunciation endpoints.

    action: "transcribe" | "score"
    Returns dict with used/remaining/limit.
    Raises 429 if limit exceeded.
    """
    today = date.today().isoformat()
    col = db["pronunciation_daily_usage"]

    # Atomic upsert — increment counter, set date/user on insert
    result = col.find_one_and_update(
        {"user_id": user_id, "date": today, "action": action},
        {
            "$inc": {"count": 1},
            "$setOnInsert": {"user_id": user_id, "date": today, "action": action},
        },
        upsert=True,
        return_document=True,  # returns updated doc
    )

    count = result["count"] if result else 1
    if count > DAILY_LIMIT:
        # Undo the increment so the count stays accurate
        col.update_one(
            {"user_id": user_id, "date": today, "action": action},
            {"$inc": {"count": -1}},
        )
        raise HTTPException(
            status_code=429,
            detail={
                "error": "daily_limit_exceeded",
                "message": f"Bạn đã dùng hết {DAILY_LIMIT} lượt {action} miễn phí hôm nay. Quay lại vào ngày mai!",
                "used": DAILY_LIMIT,
                "limit": DAILY_LIMIT,
                "remaining": 0,
            },
        )

    return {
        "used": count,
        "limit": DAILY_LIMIT,
        "remaining": max(0, DAILY_LIMIT - count),
    }


# ── POST /transcribe ─────────────────────────────────────────────────────────


@router.post("/transcribe")
async def transcribe_endpoint(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Transcribe audio → English text using faster-whisper tiny.

    FREE — requires login, limited to 10 uses/day.

    Request body:
      audio_base64  (str, required)  — base64-encoded audio file
      audio_mime_type (str, optional) — "audio/webm" | "audio/mp3" | etc. (informational only)

    Response:
      transcript   — recognized English text
      language     — detected language code
      duration_s   — audio duration in seconds
      daily_usage  — {used, limit, remaining}
    """
    body: dict[str, Any] = await request.json()
    audio_bytes = _decode_audio(body)
    user_id = current_user["uid"]

    daily = _check_and_increment_daily_limit(user_id, "transcribe", db)

    try:
        from src.services.pronunciation_service import transcribe_audio

        result = transcribe_audio(audio_bytes)
    except Exception as e:
        logger.error(f"Transcribe error for {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

    return {
        "success": True,
        **result,
        "daily_usage": daily,
    }


# ── POST /score ──────────────────────────────────────────────────────────────


@router.post("/score")
async def score_endpoint(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Score pronunciation against expected text using Wav2Vec2 phoneme recognition.

    FREE — requires login, limited to 10 uses/day.

    Supports: single word, phrase, or full sentence.

    Request body:
      audio_base64   (str, required) — base64-encoded audio
      expected_text  (str, required) — word / phrase / sentence to compare against
      audio_mime_type (str, optional)

    Response:
      overall_score     — 0.0 to 1.0 (1.0 = perfect)
      transcript        — what Whisper heard (sanity check)
      expected_text     — your input
      expected_ipa      — reference IPA phoneme sequence
      actual_ipa        — phonemes extracted from your audio
      phoneme_alignment — [{expected, actual, correct}, ...] (global alignment)
      words             — per-word breakdown:
                          [{word, expected_ipa, score, phonemes: [{expected, actual, correct}]}]
      feedback          — human-readable score summary
      daily_usage       — {used, limit, remaining}

    Score interpretation:
      ≥ 0.90 → Excellent
      ≥ 0.75 → Good
      ≥ 0.55 → Fair
       < 0.55 → Needs practice
    """
    body: dict[str, Any] = await request.json()
    audio_bytes = _decode_audio(body)

    expected_text: str = body.get("expected_text", "").strip()
    if not expected_text:
        raise HTTPException(status_code=400, detail="expected_text is required")
    if len(expected_text) > 500:
        raise HTTPException(
            status_code=400, detail="expected_text too long (max 500 chars)"
        )

    user_id = current_user["uid"]

    daily = _check_and_increment_daily_limit(user_id, "score", db)

    try:
        from src.services.pronunciation_service import score_pronunciation

        result = score_pronunciation(audio_bytes, expected_text)
    except Exception as e:
        logger.error(f"Score error for {user_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Pronunciation scoring failed: {str(e)}"
        )

    # Add human-readable feedback
    score = result["overall_score"]
    if score >= 0.90:
        feedback = "Excellent! Your pronunciation is very accurate."
    elif score >= 0.75:
        feedback = "Good job! Minor phoneme differences detected."
    elif score >= 0.55:
        feedback = "Fair. Some phonemes need improvement — check highlighted sounds."
    else:
        feedback = "Keep practicing! Focus on the highlighted phonemes."

    return {
        "success": True,
        "feedback": feedback,
        **result,
        "daily_usage": daily,
    }
