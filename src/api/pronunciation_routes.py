"""
Pronunciation API Routes

POST /api/v1/pronunciation/transcribe
  - Audio → English transcript using faster-whisper
  - Input:  {audio_base64, audio_mime_type?}
  - Cost:   1 point
  - Auth:   required

POST /api/v1/pronunciation/score
  - Audio + expected_text → phoneme-level pronunciation score
  - Works for word / phrase / full sentence
  - Input:  {audio_base64, expected_text, audio_mime_type?}
  - Cost:   2 points
  - Auth:   required

Model loading:
  - Models are lazy-loaded on first request (NOT at startup)
  - faster-whisper tiny: ~75 MB, already cached from alignment batch
  - Wav2Vec2 lv-60-espeak: ~370 MB, downloaded on first score request
"""

import base64
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from src.database.db_manager import DBManager
from src.middleware.firebase_auth import get_current_user
from src.services.points_service import get_points_service

logger = logging.getLogger("chatbot")

router = APIRouter(prefix="/api/v1/pronunciation", tags=["Pronunciation Assessment"])

POINTS_COST_TRANSCRIBE = 1
POINTS_COST_SCORE = 2


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


# ── POST /transcribe ─────────────────────────────────────────────────────────


@router.post("/transcribe")
async def transcribe_endpoint(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Transcribe audio → English text using faster-whisper tiny.

    Request body:
      audio_base64  (str, required)  — base64-encoded audio file
      audio_mime_type (str, optional) — "audio/webm" | "audio/mp3" | etc. (informational only)

    Response:
      transcript   — recognized English text
      language     — detected language code
      duration_s   — audio duration in seconds
    """
    body: dict[str, Any] = await request.json()
    audio_bytes = _decode_audio(body)
    user_id = current_user["uid"]

    # Deduct points
    points_service = get_points_service(db)
    ok, msg = await points_service.use_points(
        user_id, POINTS_COST_TRANSCRIBE, "pronunciation_transcribe"
    )
    if not ok:
        raise HTTPException(status_code=402, detail=msg)

    try:
        from src.services.pronunciation_service import transcribe_audio

        result = transcribe_audio(audio_bytes)
    except Exception as e:
        # Refund on error
        await points_service.add_points(
            user_id, POINTS_COST_TRANSCRIBE, "refund_pronunciation_transcribe"
        )
        logger.error(f"Transcribe error for {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

    return {
        "success": True,
        **result,
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

    # Deduct points
    points_service = get_points_service(db)
    ok, msg = await points_service.use_points(
        user_id, POINTS_COST_SCORE, "pronunciation_score"
    )
    if not ok:
        raise HTTPException(status_code=402, detail=msg)

    try:
        from src.services.pronunciation_service import score_pronunciation

        result = score_pronunciation(audio_bytes, expected_text)
    except Exception as e:
        await points_service.add_points(
            user_id, POINTS_COST_SCORE, "refund_pronunciation_score"
        )
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
    }
