"""
AI Bundle Subscription Models

Pricing (yearly only — no monthly option):
- no_code:  basic=449,000 VND/year  advanced=899,000 VND/year
- tier_2:   basic=399,000 VND/year  advanced=799,000 VND/year  (~11% off)
- tier_1:   basic=359,000 VND/year  advanced=719,000 VND/year  (~20% off)

Commission (same rates as Conversations, separate accounts):
- Tier-1 affiliate: 40% on sale price
- Tier-2 affiliate: 25% on sale price
- Supervisor:       10% on sale price

AI Bundle includes:
- AI Learning Assistant: /solve (1 req) + /grade (1 req)
- AI Code Studio:        /generate + /explain + /transform  (each 1 req)
  → basic:    100 requests/month, resets 1st of each month
  → advanced: 200 requests/month, resets 1st of each month
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ============================================================================
# Pricing Configuration
# ============================================================================

AI_BUNDLE_PRICING = {
    "no_code": {"basic": 449_000, "advanced": 899_000},
    "tier_2": {"basic": 399_000, "advanced": 799_000},
    "tier_1": {"basic": 359_000, "advanced": 719_000},
}

AI_BUNDLE_REQUESTS_LIMIT = {
    "basic": 100,
    "advanced": 200,
}

PLAN_LABELS = {
    "basic": "Gói Cơ Bản",
    "advanced": "Gói Nâng Cao",
}

AFFILIATE_COMMISSION_RATES = {
    1: 0.40,  # Tier-1: 40%
    2: 0.25,  # Tier-2: 25%
}

SUPERVISOR_COMMISSION_RATE = 0.10  # 10% of sale price


def get_price(price_tier: str, plan: str) -> int:
    """Return the VND amount for a given tier + plan combination."""
    tier_pricing = AI_BUNDLE_PRICING.get(price_tier, AI_BUNDLE_PRICING["no_code"])
    return tier_pricing.get(plan, tier_pricing["basic"])


# ============================================================================
# Pydantic Models
# ============================================================================


class AiBundlePlan(BaseModel):
    plan_id: str  # "basic" | "advanced"
    plan_label: str  # "Gói Cơ Bản" | "Gói Nâng Cao"
    requests_per_month: int  # 100 | 200
    months: int = 12  # Always yearly
    price_tier: str  # "no_code" | "tier_1" | "tier_2"
    original_price: int  # no-code price (for strikethrough UI)
    price: int  # Actual price with affiliate code
    is_popular: bool = False
    features: list = []


class AiBundleSubscriptionStatus(BaseModel):
    is_active: bool
    plan: Optional[str] = None
    plan_label: Optional[str] = None
    requests_monthly_limit: Optional[int] = None
    requests_used_this_month: Optional[int] = None
    requests_remaining: Optional[int] = None
    requests_reset_date: Optional[str] = None
    expires_at: Optional[str] = None
    features: Optional[dict] = None


class ActivateAiBundleSubscriptionRequest(BaseModel):
    user_id: str = Field(..., description="Firebase UID")
    plan: str = Field(..., description="basic | advanced")
    price_tier: str = Field(..., description="no_code | tier_1 | tier_2")
    amount_paid: int = Field(..., description="Actual amount paid in VND")
    payment_id: str = Field(..., description="Payment transaction ID")
    order_invoice_number: str = Field(..., description="Unique order invoice number")
    payment_method: str = Field(default="SEPAY_BANK_TRANSFER")
    affiliate_code: Optional[str] = Field(None, description="Affiliate code if used")


class ActivateAiBundleSubscriptionResponse(BaseModel):
    subscription_id: str
    user_id: str
    plan: str
    plan_label: str
    requests_monthly_limit: int
    expires_at: str
    message: str
