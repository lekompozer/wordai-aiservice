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

POINTS_COST_TEXT = 1  # DeepSeek text check
POINTS_COST_AUDIO = 2  # Gemini audio transcription + check

# 8 supported languages (same as Listen & Learn feature)
LANGUAGE_NAMES: dict[str, str] = {
    "vi": "Vietnamese (tiếng Việt)",
    "en": "English",
    "ja": "Japanese (日本語)",
    "ko": "Korean (한국어)",
    "zh": "Chinese (中文)",
    "fr": "French (Français)",
    "de": "German (Deutsch)",
    "es": "Spanish (Español)",
}


def _feedback_lang_instruction(lang: str) -> str:
    """Return instruction for AI to write feedback in the given language."""
    name = LANGUAGE_NAMES.get(lang, LANGUAGE_NAMES["vi"])
    return f"Write the 'feedback' field in {name}."


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
    logger.info(
        f"[grammar/check-sentences] body keys: {list(body.keys())}, body={body}"
    )

    # Accept both "text" and "sentences" (array or string)
    text = body.get("text") or body.get("sentence") or ""
    sentences_raw = body.get("sentences")
    if sentences_raw and not text:
        if isinstance(sentences_raw, list):
            text = " ".join(str(s) for s in sentences_raw)
        else:
            text = str(sentences_raw)
    text = text.strip()
    language: str = body.get("language", "vi").strip()

    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    if len(text) > 2000:
        raise HTTPException(
            status_code=400, detail="text must be 2000 characters or fewer"
        )

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

        feedback_instruction = _feedback_lang_instruction(language)

        system_prompt = (
            "You are an expert English grammar checker. "
            "Analyse the user's text for grammar, spelling, and punctuation errors. "
            f"{feedback_instruction} "
            "Return ONLY valid JSON, no markdown."
        )
        user_prompt = (
            f'User text: "{text}"\n\n'
            "Return JSON:\n"
            '{"is_correct": true/false, '
            '"feedback": "1-3 sentence feedback in the requested language", '
            '"corrected_text": null_or_corrected_string, '
            '"errors": ["short error 1", ...]}'
        )

        def _call():
            client = _OpenAI(
                api_key=deepseek_key, base_url="https://api.deepseek.com/v1"
            )
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
        raise HTTPException(
            status_code=503, detail="AI service temporarily unavailable"
        )

    return {
        "is_correct": bool(result.get("is_correct", False)),
        "feedback": result.get("feedback", ""),
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
    Pronunciation check: compare user's audio against a reference text.

    Frontend flow:
      1. STT (speech-to-text) on device → get transcribed_text to display
      2. Send audio + reference_text together → AI evaluates pronunciation accuracy

    Request Body:
      audio_base64     (str, required): Base64-encoded audio (single file, frontend merges if multi-sentence).
      reference_text   (str, required): The target text the user was supposed to say.
                                        Can be one sentence or multiple sentences separated by newlines / periods.
      audio_mime_type  (str, optional): Default "audio/webm". Supports webm, mp4, wav, ogg.
      language         (str, optional): Feedback language. Default "vi". Supports vi/en/ja/ko/zh/fr/de/es.

    Response:
      transcribed_text  (str): What AI actually heard in the audio.
      overall_score     (int): 0-100 pronunciation accuracy score.
      is_correct        (bool): true if overall_score >= 80.
      feedback          (str): Overall 1-3 sentence summary in requested language.
      sentences         (list): Per-sentence breakdown — see structure below.
      points_deducted   (int)
      new_balance       (int|null)

    sentences[] structure:
      {
        "reference":       "The original sentence",
        "transcribed":     "What was heard for this sentence",
        "score":           85,          // 0-100
        "is_correct":      true,
        "mispronounced":   ["word1"],   // words pronounced incorrectly
        "feedback":        "Short note in requested language"
      }
    """
    user_id = current_user["uid"]
    body = await request.json()

    audio_base64: str = body.get("audio_base64", "").strip()
    reference_text: str = body.get("reference_text", "").strip()
    audio_mime_type: str = body.get("audio_mime_type", "audio/webm").strip()
    language: str = body.get("language", "vi").strip()

    if not audio_base64:
        raise HTTPException(status_code=400, detail="audio_base64 is required")
    if not reference_text:
        raise HTTPException(status_code=400, detail="reference_text is required")

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
                description="Đánh giá phát âm qua giọng nói",
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
        from google import genai as genai_new
        from google.genai import types as genai_types

        gemini_key = os.getenv("GEMINI_API_KEY", "")
        if not gemini_key:
            raise HTTPException(status_code=503, detail="Gemini API not configured")

        try:
            audio_bytes = base64.b64decode(audio_base64)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid base64 audio data")

        feedback_lang = _feedback_lang_instruction(language)

        prompt = f"""You are a professional English pronunciation coach. The user has already done speech-to-text on their device. Your job is to listen to their audio and evaluate pronunciation accuracy in detail — word by word and sentence by sentence — comparing against the reference text.

REFERENCE TEXT (what the user was supposed to say):
\"\"\"{reference_text}\"\"\"

INSTRUCTIONS:
1. Transcribe exactly what you hear in the audio.
2. Split the reference text into individual sentences (split on . ! ? or newlines).
3. For each sentence evaluate:
   a. The sentence-level pronunciation score (0-100).
   b. Every word in the sentence — mark each as correct or mispronounced.
   c. For mispronounced words: describe HOW they were mispronounced (wrong vowel, missing consonant, stress error, etc.) and provide the correct IPA or simple phonetic hint.
4. Compute overall_score = average of sentence scores.
5. {feedback_lang}
6. Return ONLY valid JSON (no markdown, no extra text):

{{
  "transcribed_text": "full transcription of what was heard",
  "overall_score": 85,
  "feedback": "overall 1-3 sentence summary in the requested language",
  "sentences": [
    {{
      "reference": "The original sentence",
      "transcribed": "What was heard for this sentence",
      "score": 90,
      "words": [
        {{
          "word": "school",
          "correct": true,
          "issue": null,
          "hint": null
        }},
        {{
          "word": "environment",
          "correct": false,
          "issue": "stress on wrong syllable — said en-VI-ron-ment instead of en-vi-RON-ment",
          "hint": "en-vi-RON-ment"
        }}
      ],
      "feedback": "1-2 sentence comment about this sentence in the requested language"
    }}
  ]
}}

SCORING GUIDE:
- 90-100: Excellent, near-native
- 75-89: Good, minor issues
- 60-74: Acceptable, noticeable errors
- 40-59: Poor, many errors
- 0-39: Very poor, hard to understand
"""

        def _call():
            client = genai_new.Client(api_key=gemini_key)
            response = client.models.generate_content(
                model="gemini-3.1-flash-lite-preview",
                contents=[
                    genai_types.Part.from_bytes(
                        data=audio_bytes, mime_type=audio_mime_type
                    ),
                    prompt,
                ],
            )
            return response.text.strip()

        raw = await asyncio.to_thread(_call)
        result = json.loads(_strip_json_fences(raw))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[grammar/check-audio] Gemini error: {e}")
        raise HTTPException(
            status_code=503, detail="AI service temporarily unavailable"
        )

    overall_score = int(result.get("overall_score", 0))
    return {
        "transcribed_text": result.get("transcribed_text", ""),
        "overall_score": overall_score,
        "is_correct": overall_score >= 80,
        "feedback": result.get("feedback", ""),
        "sentences": result.get("sentences") or [],
        "points_deducted": 0 if has_bundle else POINTS_COST_AUDIO,
        "new_balance": new_balance,
    }
