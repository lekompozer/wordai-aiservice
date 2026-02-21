"""
Conversation Learning Subscription Models

Pricing tiers:
- no_code:  149,000 VND/month (organic)
- tier_2:   119,000 VND/month (tier-2 affiliate code)
- tier_1:    99,000 VND/month (tier-1 affiliate: language centres)

Package discounts:
- 3 months:  no discount
- 6 months:  10% off
- 12 months: 15% off

A Conversation Learning subscription also unlocks Song Learning.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ============================================================================
# Pricing Configuration
# ============================================================================

PRICING_TIERS = {
    "no_code": 149_000,  # VND/month — no affiliate code
    "tier_2": 119_000,  # VND/month — tier-2 affiliate
    "tier_1": 99_000,  # VND/month — tier-1 affiliate (language centres)
}

PACKAGE_DISCOUNTS = {
    "3_months": 0.00,  # No discount
    "6_months": 0.10,  # 10% off
    "12_months": 0.15,  # 15% off
}

PACKAGE_MONTHS = {
    "3_months": 3,
    "6_months": 6,
    "12_months": 12,
}

AFFILIATE_COMMISSION_RATES = {
    1: 0.40,  # Tier-1 affiliate: 40%
    2: 0.25,  # Tier-2 affiliate: 25%
}


def calculate_price(tier: str, package: str) -> dict:
    """
    Calculate total price for a given tier + package combination.

    Returns dict with:
      - base_per_month: Monthly price before discount
      - months: Duration
      - subtotal: base * months (before discount)
      - discount_amount: Amount discounted
      - total: Final amount to pay (rounded to nearest 1000 VND)
    """
    base_per_month = PRICING_TIERS.get(tier, PRICING_TIERS["no_code"])
    months = PACKAGE_MONTHS.get(package, 3)
    discount_rate = PACKAGE_DISCOUNTS.get(package, 0.0)

    subtotal = base_per_month * months
    discount_amount = round(subtotal * discount_rate)
    total = subtotal - discount_amount

    return {
        "base_per_month": base_per_month,
        "months": months,
        "subtotal": subtotal,
        "discount_rate": discount_rate,
        "discount_amount": discount_amount,
        "total": total,
    }


# ============================================================================
# Pydantic Models
# ============================================================================


class ConversationSubscriptionPlan(BaseModel):
    package_id: str  # "3_months", "6_months", "12_months"
    package_label: str  # "3 Tháng", "6 Tháng", "12 Tháng"
    months: int
    price_tier: str  # "no_code", "tier_1", "tier_2"
    base_per_month: int  # VND/month (original, no discount)
    original_per_month: int  # VND/month at "no_code" rate (for UI strikethrough)
    subtotal: int
    discount_rate: float
    discount_amount: int
    total: int  # Final amount to pay
    is_popular: bool = False


class ConversationSubscriptionStatus(BaseModel):
    is_premium: bool
    subscription: Optional[dict] = None  # Full subscription detail if active


class CheckoutPreviewRequest(BaseModel):
    package: str = Field(..., description="3_months | 6_months | 12_months")
    affiliate_code: Optional[str] = Field(None, description="Mã đại lý (optional)")
    student_id: Optional[str] = Field(
        None, description="Mã học viên tại trung tâm (optional, required for tier-1)"
    )


class CheckoutPreviewResponse(BaseModel):
    package: str
    months: int
    # Pricing
    base_per_month: int
    original_per_month: int  # no-code price for strikethrough UI
    original_total: int
    subtotal: int
    discount_rate: float
    discount_amount: int
    total: int
    # Affiliate info
    price_tier: str
    affiliate_code: Optional[str] = None
    affiliate_name: Optional[str] = None
    affiliate_tier: Optional[int] = None
    # Student info (tier-1 centers)
    student_id: Optional[str] = None
    requires_student_id: bool = False


class ActivateConversationSubscriptionRequest(BaseModel):
    user_id: str = Field(..., description="Firebase UID")
    package: str = Field(..., description="3_months | 6_months | 12_months")
    price_tier: str = Field(..., description="no_code | tier_1 | tier_2")
    amount_paid: int = Field(..., description="Actual amount paid in VND")
    payment_id: str = Field(..., description="Payment transaction ID")
    order_invoice_number: str = Field(..., description="Unique order invoice number")
    payment_method: str = Field(default="SEPAY_BANK_TRANSFER")
    affiliate_code: Optional[str] = Field(None, description="Affiliate code if used")
    student_id: Optional[str] = Field(
        None, description="Mã học viên tại trung tâm (for tier-1 affiliates)"
    )


class ActivateConversationSubscriptionResponse(BaseModel):
    subscription_id: str
    expires_at: datetime
    message: str = "Conversation subscription activated successfully"
