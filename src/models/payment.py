"""
Payment Models for Payment System Integration

This module defines Pydantic models for:
- Payments
- Points Transactions
- Payment responses
"""

from datetime import datetime
from typing import Optional, Literal, Dict, Any
from pydantic import BaseModel, Field
from bson import ObjectId


class PyObjectId(ObjectId):
    """Custom ObjectId type for Pydantic v2"""

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        from pydantic_core import core_schema

        return core_schema.union_schema(
            [
                core_schema.is_instance_schema(ObjectId),
                core_schema.chain_schema(
                    [
                        core_schema.str_schema(),
                        core_schema.no_info_plain_validator_function(cls.validate),
                    ]
                ),
            ]
        )

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema, handler):
        return {"type": "string"}


# Type aliases
PaymentStatus = Literal["pending", "completed", "failed", "cancelled", "refunded"]
PaymentMethod = Literal[
    "BANK_TRANSFER",
    "BANK_TRANSFER_MANUAL",
    "SEPAY_BANK_TRANSFER",  # SePay payment gateway
    "VISA",
    "MASTERCARD",
    "MOMO",
    "ZALOPAY",
]
PlanType = Literal["premium", "pro", "vip"]
DurationType = Literal["3_months", "12_months"]
TransactionType = Literal["spend", "earn", "grant", "refund", "bonus", "purchase"]


class Payment(BaseModel):
    """Payment document stored in MongoDB"""

    id: Optional[PyObjectId] = Field(alias="_id", default=None)

    # Payment identifiers
    payment_id: Optional[str] = None  # SePay transaction ID (after payment)
    order_invoice_number: str = Field(
        ..., description="Unique order number WA-{timestamp}-{user_short}"
    )

    # User info
    user_id: str = Field(..., description="Firebase UID")
    user_email: Optional[str] = None
    user_name: Optional[str] = None

    # Amount
    amount: int = Field(..., description="Amount in VND")
    currency: str = Field(default="VND")

    # Subscription info
    plan: PlanType
    duration: DurationType

    # Payment status
    status: PaymentStatus = Field(default="pending")
    payment_method: Optional[PaymentMethod] = None

    # SePay data
    sepay_order_id: Optional[str] = None
    sepay_transaction_id: Optional[str] = None
    sepay_response: Optional[Dict[str, Any]] = None

    # URLs for redirect
    success_url: Optional[str] = None
    error_url: Optional[str] = None
    cancel_url: Optional[str] = None

    # Subscription reference (after activation)
    subscription_id: Optional[str] = None

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    paid_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    refunded_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None  # Payment link expiration (usually 15min)

    # Metadata
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    notes: Optional[str] = None

    # Admin fields (for manual payments)
    manually_processed: bool = Field(default=False)
    processed_by_admin: Optional[str] = None
    payment_reference: Optional[str] = None  # Bank reference number

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str, datetime: lambda v: v.isoformat()}
        schema_extra = {
            "example": {
                "payment_id": "sepay_txn_123",
                "order_invoice_number": "WA-1730123456-abc",
                "user_id": "firebase_uid_123",
                "user_email": "user@example.com",
                "amount": 279000,
                "currency": "VND",
                "plan": "premium",
                "duration": "3_months",
                "status": "completed",
                "payment_method": "BANK_TRANSFER",
                "created_at": "2025-11-05T09:30:00Z",
                "paid_at": "2025-11-05T09:45:00Z",
            }
        }


class PointsTransaction(BaseModel):
    """Points transaction document (audit log)"""

    id: Optional[PyObjectId] = Field(alias="_id", default=None)

    # User and subscription
    user_id: str = Field(..., description="Firebase UID")
    subscription_id: Optional[PyObjectId] = None

    # Transaction details
    type: Literal["earn", "spend", "refund", "expire", "grant", "deduct"] = Field(...)
    amount: int = Field(..., description="Points changed (positive/negative)")
    balance_before: int = Field(...)
    balance_after: int = Field(...)

    # Usage context
    service: Optional[str] = Field(
        None, description="ai_chat, ai_edit, online_test, subscription, manual"
    )
    resource_id: Optional[str] = Field(
        None, description="Chat ID, document ID, test ID, etc."
    )
    description: str = Field(...)

    # Admin action (if manual)
    is_manual: bool = Field(default=False)
    admin_id: Optional[str] = None
    admin_reason: Optional[str] = None

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    ip_address: Optional[str] = None

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str, datetime: lambda v: v.isoformat()}
        schema_extra = {
            "example": {
                "user_id": "firebase_uid_123",
                "subscription_id": "673456789abcdef",
                "type": "spend",
                "amount": -2,
                "balance_before": 300,
                "balance_after": 298,
                "service": "ai_chat",
                "resource_id": "chat_session_123",
                "description": "AI Chat Session",
                "created_at": "2025-11-05T10:15:00Z",
            }
        }


class CreatePaymentRequest(BaseModel):
    """Request model for initiating payment"""

    user_id: str
    plan: PlanType
    duration: DurationType
    user_email: Optional[str] = None
    user_name: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class PaymentResponse(BaseModel):
    """Response model for payment endpoints"""

    payment_id: Optional[str] = None
    order_invoice_number: str
    amount: int
    currency: str = "VND"
    plan: PlanType
    duration: DurationType
    status: PaymentStatus

    # Checkout URL (for redirect)
    checkout_url: Optional[str] = None

    # Timestamps
    created_at: datetime
    paid_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    # Subscription (if activated)
    subscription_id: Optional[str] = None
    subscription_activated: bool = False

    class Config:
        schema_extra = {
            "example": {
                "order_invoice_number": "WA-1730123456-abc",
                "amount": 279000,
                "currency": "VND",
                "plan": "premium",
                "duration": "3_months",
                "status": "pending",
                "checkout_url": "https://sandbox.sepay.vn/checkout/abc123",
                "created_at": "2025-11-05T09:30:00Z",
                "expires_at": "2025-11-05T09:45:00Z",
            }
        }


class CheckoutResponse(BaseModel):
    """Response from payment service with checkout URL"""

    checkout_url: str
    order_invoice_number: str
    amount: int
    expires_at: datetime

    class Config:
        schema_extra = {
            "example": {
                "checkout_url": "https://sandbox.sepay.vn/checkout/abc123",
                "order_invoice_number": "WA-1730123456-abc",
                "amount": 279000,
                "expires_at": "2025-11-05T09:45:00Z",
            }
        }


class ActivateSubscriptionRequest(BaseModel):
    """Request from payment service to activate subscription"""

    user_id: str
    payment_id: str
    order_invoice_number: str
    plan: PlanType
    duration: DurationType
    paid_amount: int
    paid_at: datetime


class ActivateSubscriptionResponse(BaseModel):
    """Response after activating subscription"""

    subscription_id: str
    expires_at: datetime
    points_granted: int
    message: str = "Subscription activated successfully"

    class Config:
        schema_extra = {
            "example": {
                "subscription_id": "673456789abcdef",
                "expires_at": "2026-02-05T09:45:00Z",
                "points_granted": 300,
                "message": "Subscription activated successfully",
            }
        }


class WebhookPayload(BaseModel):
    """SePay webhook payload"""

    order_invoice_number: str
    transaction_id: str
    status: str  # "SUCCESS", "FAILED", "CANCELLED"
    amount: int
    paid_at: str  # ISO datetime string
    payment_method: str

    class Config:
        schema_extra = {
            "example": {
                "order_invoice_number": "WA-1730123456-abc",
                "transaction_id": "sepay_txn_123",
                "status": "SUCCESS",
                "amount": 279000,
                "paid_at": "2025-11-05T09:45:00Z",
                "payment_method": "BANK_TRANSFER",
            }
        }


class PointsGrantRequest(BaseModel):
    """Admin request to grant points"""

    user_id: str
    points_amount: int = Field(..., gt=0)
    reason: str
    granted_by_admin: str


class PointsDeductRequest(BaseModel):
    """Admin request to deduct points"""

    user_id: str
    points_amount: int = Field(..., gt=0)
    reason: str
    deducted_by_admin: str


class PointsBalance(BaseModel):
    """Points balance response"""

    user_id: str
    subscription_id: Optional[str]
    points_total: int
    points_used: int
    points_remaining: int
    plan: str

    class Config:
        schema_extra = {
            "example": {
                "user_id": "firebase_uid_123",
                "subscription_id": "673456789abcdef",
                "points_total": 300,
                "points_used": 15,
                "points_remaining": 285,
                "plan": "premium",
            }
        }


class ReconciliationSummary(BaseModel):
    """Payment reconciliation summary for admin"""

    period_start: datetime
    period_end: datetime
    total_payments: int
    completed_payments: int
    failed_payments: int
    pending_payments: int
    refunded_payments: int
    total_revenue: int
    by_plan: Dict[str, Dict[str, int]]
    by_duration: Dict[str, Dict[str, int]]
    by_payment_method: Dict[str, Dict[str, int]]

    class Config:
        schema_extra = {
            "example": {
                "period_start": "2025-11-01T00:00:00Z",
                "period_end": "2025-11-30T23:59:59Z",
                "total_payments": 145,
                "completed_payments": 138,
                "failed_payments": 5,
                "pending_payments": 2,
                "refunded_payments": 0,
                "total_revenue": 40530000,
                "by_plan": {
                    "premium": {"count": 85, "amount": 23715000},
                    "pro": {"count": 42, "amount": 16758000},
                    "vip": {"count": 11, "amount": 8217000},
                },
                "by_duration": {
                    "3_months": {"count": 98, "amount": 27342000},
                    "12_months": {"count": 40, "amount": 39600000},
                },
                "by_payment_method": {
                    "BANK_TRANSFER": {"count": 120, "amount": 33480000},
                    "VISA": {"count": 18, "amount": 5022000},
                },
            }
        }
