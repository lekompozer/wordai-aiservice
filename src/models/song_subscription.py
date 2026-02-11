"""
Song Learning Subscription Models
Pydantic models for subscription data validation
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class SubscriptionPlan(BaseModel):
    """Subscription plan configuration"""

    plan_id: str = Field(..., description="monthly, 6_months, yearly")
    name: str = Field(..., description="Display name")
    price: int = Field(..., description="Price in VND")
    duration_months: int = Field(..., description="Duration in months")
    price_per_month: int = Field(..., description="Price per month")
    discount_percentage: Optional[int] = Field(
        None, description="Discount percentage vs monthly"
    )
    features: List[str] = Field(..., description="List of features")
    is_popular: bool = Field(default=False, description="Show as popular choice")


class UserSubscription(BaseModel):
    """User subscription document"""

    user_id: str = Field(..., description="Firebase UID")
    plan_type: str = Field(..., description="monthly, 6_months, yearly")
    status: str = Field(..., description="active, expired, cancelled")

    # Dates
    start_date: datetime = Field(..., description="Subscription start")
    end_date: datetime = Field(..., description="Subscription expiry")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    cancelled_at: Optional[datetime] = Field(None, description="Cancellation date")

    # Payment Info
    price_paid: int = Field(..., description="Amount in VND")
    payment_method: str = Field(..., description="momo, vnpay, manual")
    payment_id: Optional[str] = Field(None, description="Payment transaction ID")
    order_invoice_number: Optional[str] = Field(None, description="Unique order ID")

    # Auto-renewal
    auto_renew: bool = Field(default=False, description="Auto-renew enabled")

    # Metadata
    source: str = Field(default="web", description="app or web")


class SubscriptionStatusResponse(BaseModel):
    """Subscription status response"""

    is_premium: bool
    subscription: Optional[dict] = None


class CreatePaymentRequest(BaseModel):
    """Request to create payment"""

    plan_id: str = Field(..., description="monthly, 6_months, yearly")


class CreatePaymentResponse(BaseModel):
    """Payment creation response"""

    payment_url: str = Field(..., description="MoMo payment URL")
    order_id: str = Field(..., description="Unique order ID")
    amount: int = Field(..., description="Amount in VND")
    expires_at: datetime = Field(..., description="Payment URL expiry")


class MoMoIPNRequest(BaseModel):
    """MoMo IPN webhook request"""

    partnerCode: str
    orderId: str
    requestId: str
    amount: int
    orderInfo: str
    orderType: str
    transId: str
    resultCode: int
    message: str
    payType: str
    responseTime: int
    extraData: str
    signature: str


# Plan configurations
SUBSCRIPTION_PLANS = {
    "monthly": SubscriptionPlan(
        plan_id="monthly",
        name="Monthly",
        price=29000,
        duration_months=1,
        price_per_month=29000,
        discount_percentage=None,
        features=[
            "Unlimited songs per day",
            "Access all difficulties",
            "Full progress tracking",
            "No ads",
        ],
        is_popular=False,
    ),
    "6_months": SubscriptionPlan(
        plan_id="6_months",
        name="6 Months",
        price=150000,
        duration_months=6,
        price_per_month=25000,
        discount_percentage=14,
        features=[
            "Unlimited songs per day",
            "Access all difficulties",
            "Full progress tracking",
            "No ads",
            "Save 14%",
        ],
        is_popular=True,
    ),
    "yearly": SubscriptionPlan(
        plan_id="yearly",
        name="Yearly",
        price=250000,
        duration_months=12,
        price_per_month=21000,
        discount_percentage=28,
        features=[
            "Unlimited songs per day",
            "Access all difficulties",
            "Full progress tracking",
            "No ads",
            "Save 28% - Best Value!",
        ],
        is_popular=False,
    ),
}
