"""
Public Conversation Endpoints — No Authentication Required

Designed for Next.js SSR & Googlebot indexing.

Slugs are derived from conversation_id:
  conv_beginner_greetings_introductions_01_001
  → beginner-greetings-introductions-01-001

Frontend may prefix the English title for display URLs:
  hello-how-are-you-beginner-greetings-introductions-01-001
  (backend extracts the canonical suffix starting at beginner|intermediate|advanced)

Endpoints:
  GET /api/v1/public/listen-learn/conversations/sitemap?page=1&limit=500
  GET /api/v1/public/listen-learn/conversations/{slug}
"""

import re
import unicodedata
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from src.database.db_manager import DBManager

router = APIRouter(
    prefix="/api/v1/public/listen-learn/conversations",
    tags=["SEO Public - Conversations"],
)

# Levels in conversation_id so we can extract the canonical suffix from a
# title-prefixed slug like: "hello-how-are-you-beginner-greetings-01-001"
_LEVEL_RE = re.compile(r"\b(beginner|intermediate|advanced)\b")
_ID_SUFFIX_RE = re.compile(r"(\d{2}-\d{3})$")


def get_db():
    return DBManager().db


def _conv_id_to_slug(conversation_id: str) -> str:
    """conv_beginner_greetings_introductions_01_001 → beginner-greetings-introductions-01-001"""
    return conversation_id.removeprefix("conv_").replace("_", "-")


def _slug_to_conv_id(slug: str) -> str:
    """
    Convert a URL slug back to a conversation_id.

    Handles two formats:
    1. Canonical: beginner-greetings-introductions-01-001
       → conv_beginner_greetings_introductions_01_001  (direct reverse)

    2. Title-prefixed: hello-how-are-you-beginner-greetings-introductions-01-001
       → extract from the first 'beginner|intermediate|advanced' word onward
       → conv_beginner_greetings_introductions_01_001
    """
    # Try direct full reversal first (most common path)
    candidate = "conv_" + slug.replace("-", "_")
    # If slug starts with a level word it's already canonical
    if _LEVEL_RE.match(slug):
        return candidate

    # Title-prefixed: find the first occurrence of a level keyword
    m = _LEVEL_RE.search(slug)
    if m:
        canonical_part = slug[m.start() :].replace("-", "_")
        return "conv_" + canonical_part

    # Fallback: hope the full reversal works
    return candidate


def _format_conversation(doc: dict) -> dict:
    """Strip heavy / internal fields and build public-safe response."""
    doc.pop("_id", None)
    if doc.get("online_test_id"):
        doc["online_test_id"] = str(doc["online_test_id"])

    # Build audio URL from r2_key
    audio_url = None
    ai = doc.get("audio_info") or {}
    if ai.get("r2_key"):
        audio_url = f"https://static.wordai.pro/{ai['r2_key']}"
    elif ai.get("r2_url"):
        audio_url = ai["r2_url"]
    elif ai.get("url"):
        audio_url = ai["url"]

    slug = _conv_id_to_slug(doc["conversation_id"])

    return {
        "id": doc.get("conversation_id"),
        "slug": slug,
        "title": doc.get("title", {}),
        "topic": doc.get("topic", {}),
        "topic_slug": doc.get("topic_slug"),
        "level": doc.get("level"),
        "situation": doc.get("situation"),
        "audio_url": audio_url,
        "has_audio": bool(audio_url),
        "word_count": doc.get("word_count", 0),
        "turn_count": doc.get("turn_count", 0),
        "difficulty_score": doc.get("difficulty_score"),
        "transcript": doc.get("dialogue", []),
        "updated_at": doc.get("updated_at") or doc.get("created_at"),
    }


# ============================================================================
# ENDPOINT 1: Sitemap feed
# ============================================================================


@router.get("/sitemap")
async def get_conversations_sitemap(
    page: int = 1,
    limit: int = 500,
    db=Depends(get_db),
):
    """
    Return slug + updatedAt for every conversation, paginated.

    Used by Next.js to generate sitemap.xml.
    No authentication required.
    """
    limit = min(limit, 500)
    skip = (max(page, 1) - 1) * limit

    cursor = (
        db["conversation_library"]
        .find(
            {},
            {
                "_id": 0,
                "conversation_id": 1,
                "title": 1,
                "level": 1,
                "topic_slug": 1,
                "updated_at": 1,
                "created_at": 1,
            },
        )
        .sort("conversation_id", 1)
        .skip(skip)
        .limit(limit)
    )

    items = []
    for doc in cursor:
        slug = _conv_id_to_slug(doc["conversation_id"])
        updated = doc.get("updated_at") or doc.get("created_at")
        items.append(
            {
                "slug": slug,
                "conversation_id": doc["conversation_id"],
                "title": doc.get("title", {}).get("en", ""),
                "level": doc.get("level"),
                "topic_slug": doc.get("topic_slug"),
                "updated_at": updated.isoformat() if updated else None,
            }
        )

    total = db["conversation_library"].count_documents({})

    return {
        "success": True,
        "data": items,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": -(-total // limit),  # ceil
        },
    }


# ============================================================================
# ENDPOINT 2: Detail by slug (must be after /sitemap to avoid catch-all)
# ============================================================================


@router.get("/{slug}")
async def get_conversation_public(slug: str, db=Depends(get_db)):
    """
    Return full conversation detail for SSR page rendering.

    Accepts:
    - Canonical slug:      beginner-greetings-introductions-01-001
    - Title-prefixed slug: hello-how-are-you-beginner-greetings-introductions-01-001

    No authentication required.
    Includes: title, topic, level, transcript (en+vi), vocabulary, audio_url.
    """
    conversation_id = _slug_to_conv_id(slug)

    conv_col = db["conversation_library"]
    doc = conv_col.find_one({"conversation_id": conversation_id})

    if not doc:
        raise HTTPException(status_code=404, detail="Conversation not found")

    result = _format_conversation(doc)

    # Attach vocabulary (best-effort, no 404 if missing)
    vocab_doc = db["conversation_vocabulary"].find_one(
        {"conversation_id": conversation_id},
        {"_id": 0, "vocabulary": 1, "grammar_points": 1},
    )
    if vocab_doc:
        result["vocabulary"] = vocab_doc.get("vocabulary", [])
        result["grammar_points"] = vocab_doc.get("grammar_points", [])
    else:
        result["vocabulary"] = []
        result["grammar_points"] = []

    return {"success": True, "data": result}
