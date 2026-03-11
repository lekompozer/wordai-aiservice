"""
AI Bundle Quota Middleware

Checks whether a user has an active AI Bundle subscription with remaining
monthly requests. If yes, atomically increments the counter.

Usage in endpoints:
    from src.middleware.ai_bundle_quota import check_ai_bundle_quota

    has_bundle = await check_ai_bundle_quota(user_id, db)
    # True  → bundle used, do NOT deduct points
    # False → no bundle, fall through to points_service
    # raises HTTPException(429) → has bundle but quota exhausted for the month
"""

from datetime import datetime, timezone
from fastapi import HTTPException
from src.utils.logger import setup_logger

logger = setup_logger()


def _first_day_next_month(now: datetime) -> datetime:
    """Return UTC midnight on the 1st of the next month."""
    if now.month == 12:
        return datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    return datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)


async def check_ai_bundle_quota(user_id: str, db) -> bool:
    """
    Check and consume 1 AI Bundle request for user_id.

    Returns:
        True   — user has an active bundle and a request was consumed.
        False  — user has no active bundle (fall through to points system).

    Raises:
        HTTPException(429) — user HAS a bundle but quota is exhausted.
        HTTPException(403) — user's bundle has expired.
    """
    now = datetime.now(timezone.utc)

    # ── Step 1: Auto-reset if past the reset date ─────────────────────────
    db["user_ai_bundle_subscriptions"].update_many(
        {
            "user_id": user_id,
            "status": "active",
            "requests_reset_date": {"$lte": now},
        },
        {
            "$set": {
                "requests_used_this_month": 0,
                "requests_reset_date": _first_day_next_month(now),
            }
        },
    )

    # ── Step 2: Atomic increment if quota remaining ───────────────────────
    updated = db["user_ai_bundle_subscriptions"].find_one_and_update(
        {
            "user_id": user_id,
            "status": "active",
            "expires_at": {"$gt": now},
            "$expr": {"$lt": ["$requests_used_this_month", "$requests_monthly_limit"]},
        },
        {"$inc": {"requests_used_this_month": 1}},
        return_document=True,
    )

    if updated:
        logger.debug(
            f"[ai_bundle_quota] ✅ user={user_id} "
            f"used={updated['requests_used_this_month']}/{updated['requests_monthly_limit']}"
        )
        return True

    # ── Step 3: Diagnose why update failed ────────────────────────────────
    sub = db["user_ai_bundle_subscriptions"].find_one(
        {"user_id": user_id, "status": "active"},
        {
            "expires_at": 1,
            "requests_used_this_month": 1,
            "requests_monthly_limit": 1,
            "requests_reset_date": 1,
            "plan": 1,
        },
    )

    if not sub:
        # No active bundle at all — caller should fall through to points
        return False

    if sub.get("expires_at") and sub["expires_at"] <= now:
        raise HTTPException(
            status_code=403,
            detail="Gói AI Bundle của bạn đã hết hạn. Vui lòng gia hạn để tiếp tục.",
        )

    # Bundle exists and is active but quota is full
    reset_date = sub.get("requests_reset_date")
    reset_str = reset_date.strftime("%d/%m/%Y") if reset_date else "đầu tháng sau"
    raise HTTPException(
        status_code=429,
        detail=(
            f"Bạn đã dùng hết {sub['requests_monthly_limit']} requests "
            f"tháng này (Gói {sub.get('plan', '').capitalize()}). "
            f"Quota reset vào {reset_str}."
        ),
    )
