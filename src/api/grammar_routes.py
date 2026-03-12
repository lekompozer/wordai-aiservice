"""
Grammar Check API Routes

Two synchronous endpoints for standalone grammar checking.
  POST /api/grammar/check-sentences  → Text grammar check (DeepSeek, 1 point)
  POST /api/grammar/check-audio      → Audio grammar check (Gemini, 2 points)

Both endpoints:
  - Require Firebase authentication
  - Use AI Bundle quota if the user has an active bundle
  - Fall back to points deduction if no bundle
"""

import json
import re
import base64
import asyncio
import logging
import os
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Request

from src.database.db_manager import DBManager
from src.middleware.firebase_auth import get_current_user
from src.services.points_service import get_points_service
from src.middleware.ai_bundle_quota import check_ai_bundle_quota

logger = logging.getLogger("chatbot")

router = APIRouter(prefix="/api/grammar", tags=["Grammar Check"])

POINTS_COST_TEXT = 1   # DeepSeek text check
POINTS_COST_AUDIO = 2  # Gemini audio transcription + check


def get_db():
    return DBManager().db


def _strip_json_fences(raw: str) -> str:
    return re.sub(r"^```[a-z]*\n?|```$", "", raw.strip(), flags=re.MULTILINE).strip()


# ============================================================================
# POST /api/grammar/check-sentences
# Text-based grammar check using DeepSeek
# ============================================================================


@router.post("/check-sentences")
async def grammar_check_text(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Check grammar of a provided text using DeepSeek AI.

    Request Body:
      text (str, required): The sentence or paragraph to check.
      language (str, optional): Target language for feedback. Default "vi" (Vietnamese).

    Response:
      is_correct (bool)
      feedback_vi (str): 1-3 sentence feedback in Vietnamese.
      corrected_text (str|null): Corrected version if errors found, else null.
      errors (list[str]): Short list of error descriptions (may be empty).
      points_deducted (int)
    """
    user_id = current_user["uid"]
    body = await request.json()

    text: str = body.get("text", "").strip()
    language: str = body.get("language", "vi").strip()

    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    if len(text) > 2000:
        raise HTTPException(status_code=400, detail="text must be 2000 characters or fewer")

    # ── AI Bundle quota or points ─────────────────────────────────────────
    has_bundle = await check_ai_bundle_quota(user_id, db)

    new_balance = None
    if not has_bundle:
        points_service = get_points_service()
        try:
            transaction = await points_service.deduct_points(
                user_id=user_id,
                amount=POINTS_COST_TEXT,
                service="grammar_check_text",
                description=f"Kiểm tra ngữ pháp: {text[:60]}...",
            )
            new_balance = transaction.balance_after
        except Exception as e:
            if "Không đủ điểm" in str(e) or "insufficient" in str(e).lower():
                balance = await points_service.get_points_balance(user_id)
                raise HTTPException(
                    status_code=403,
                    detail=f"Không đủ điểm. Cần: {POINTS_COST_TEXT}, Còn lại: {balance['points_remaining']}",
                )
            raise HTTPException(status_code=500, detail=str(e))

    # ── DeepSeek call ─────────────────────────────────────────────────────
    try:
        from openai import OpenAI as _OpenAI

        deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")
        if not deepseek_key:
            raise HTTPException(status_code=503, detail="DeepSeek API not configured")

        system_prompt = (
            "You are an expert English grammar checker. "
            "Analyse the user's text for grammar, spelling, and punctuation errors. "
            "Return ONLY valid JSON, no markdown."
        )
        user_prompt = (
            f'User text: "{text}"\n\n'
            "Return JSON:\n"
            '{"is_correct": true/false, '
            '"feedback_vi": "1-3 câu nhận xét bằng tiếng Việt", '
            '"corrected_text": null_or_corrected_string, '
            '"errors": ["short error 1", ...]}'
        )

        def _call():
            client = _OpenAI(api_key=deepseek_key, base_url="https://api.deepseek.com/v1")
            resp = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=512,
            )
            return resp.choices[0].message.content.strip()

        raw = await asyncio.to_thread(_call)
        result = json.loads(_strip_json_fences(raw))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[grammar/check-sentences] DeepSeek error: {e}")
        raise HTTPException(status_code=503, detail="AI service temporarily unavailable")

    return {
        "is_correct": bool(result.get("is_correct", False)),
        "feedback_vi": result.get("feedback_vi", ""),
        "corrected_text": result.get("corrected_text") or None,
        "errors": result.get("errors") or [],
        "points_deducted": 0 if has_bundle else POINTS_COST_TEXT,
        "new_balance": new_balance,
    }


# ============================================================================
# POST /api/grammar/check-audio
# Audio-based grammar check using Gemini (transcribe + check)
# ============================================================================


@router.post("/check-audio")
async def grammar_check_audio(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Transcribe audio then check grammar using Gemini AI.

    Request Body:
      audio_base64 (str, required): Base64-encoded audio data.
      audio_mime_type (str, optional): MIME type of audio. Default "audio/webm".
      language (str, optional): Target language for feedback. Default "vi".

    Response:
      transcribed_text (str): What was heard in the audio.
      is_correct (bool)
      feedback_vi (str): 1-3 sentence feedback in Vietnamese.
      corrected_text (str|null): Corrected version if errors found, else null.
      errors (list[str])
      points_deducted (int)
    """
    user_id = current_user["uid"]
    body = await request.json()

    audio_base64: str = body.get("audio_base64", "").strip()
    audio_mime_type: str = body.get("audio_mime_type", "audio/webm").strip()

    if not audio_base64:
        raise HTTPException(status_code=400, detail="audio_base64 is required")

    # ── AI Bundle quota or points ─────────────────────────────────────────
    has_bundle = await check_ai_bundle_quota(user_id, db)

    new_balance = None
    if not has_bundle:
        points_service = get_points_service()
        try:
            transaction = await points_service.deduct_points(
                user_id=user_id,
                amount=POINTS_COST_AUDIO,
                service="grammar_check_audio",
                description="Kiểm tra ngữ pháp qua giọng nói",
            )
            new_balance = transaction.balance_after
        except Exception as e:
            if "Không đủ điểm" in str(e) or "insufficient" in str(e).lower():
                balance = await points_service.get_points_balance(user_id)
                raise HTTPException(
                    status_code=403,
                    detail=f"Không đủ điểm. Cần: {POINTS_COST_AUDIO}, Còn lại: {balance['points_remaining']}",
                )
            raise HTTPException(status_code=500, detail=str(e))

    # ── Gemini call ───────────────────────────────────────────────────────
    try:
        import google.generativeai as genai_mod

        gemini_key = os.getenv("GEMINI_API_KEY", "")
        if not gemini_key:
            raise HTTPException(status_code=503, detail="Gemini API not configured")

        genai_mod.configure(api_key=gemini_key)

        try:
            audio_bytes = base64.b64decode(audio_base64)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid base64 audio data")

        prompt = (
            "1. Transcribe exactly what was said in the audio.\n"
            "2. Check the transcribed text for English grammar, spelling, and pronunciation errors.\n"
            "3. Return ONLY valid JSON (no markdown):\n"
            '{"transcribed_text": "...", '
            '"is_correct": true/false, '
            '"feedback_vi": "1-3 câu nhận xét bằng tiếng Việt", '
            '"corrected_text": null_or_corrected_string, '
            '"errors": ["short error 1", ...]}'
        )

        def _call():
            model = genai_mod.GenerativeModel("gemini-2.5-flash")
            response = model.generate_content(
                [{"mime_type": audio_mime_type, "data": audio_bytes}, prompt]
            )
            return response.text.strip()

        raw = await asyncio.to_thread(_call)
        result = json.loads(_strip_json_fences(raw))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[grammar/check-audio] Gemini error: {e}")
        raise HTTPException(status_code=503, detail="AI service temporarily unavailable")

    return {
        "transcribed_text": result.get("transcribed_text", ""),
        "is_correct": bool(result.get("is_correct", False)),
        "feedback_vi": result.get("feedback_vi", ""),
        "corrected_text": result.get("corrected_text") or None,
        "errors": result.get("errors") or [],
        "points_deducted": 0 if has_bundle else POINTS_COST_AUDIO,
        "new_balance": new_balance,
    }
