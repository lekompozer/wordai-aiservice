"""
USDT BEP20 Payment Models for Subscription & Points Purchase

This module defines Pydantic models and MongoDB schemas for:
- USDT BEP20 payments (BSC network)
- Pending transaction tracking
- User wallet address management
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
PaymentStatus = Literal[
    "pending", "processing", "confirmed", "completed", "failed", "cancelled", "refunded"
]
PaymentType = Literal["subscription", "points"]
PlanType = Literal["premium", "pro", "vip"]
DurationType = Literal["3_months", "12_months"]


# =====================================
# USDT PAYMENT MODELS
# =====================================


class USDTPayment(BaseModel):
    """
    USDT Payment document stored in MongoDB
    Collection: usdt_payments
    """

    id: Optional[PyObjectId] = Field(alias="_id", default=None)

    # Payment identifiers
    payment_id: str = Field(
        ..., description="Unique payment ID: USDT-{timestamp}-{random}"
    )
    order_invoice_number: str = Field(
        ..., description="Order number: WA-USDT-{timestamp}-{user_short}"
    )

    # User info
    user_id: str = Field(..., description="Firebase UID")
    user_email: Optional[str] = None
    user_name: Optional[str] = None

    # Payment type and details
    payment_type: PaymentType = Field(..., description="subscription or points")

    # For subscription payments
    plan: Optional[PlanType] = None
    duration: Optional[DurationType] = None

    # For points payments
    points_amount: Optional[int] = Field(
        None, description="Number of points to purchase"
    )

    # Amount
    amount_usdt: float = Field(..., description="Amount in USDT")
    amount_vnd: int = Field(..., description="Equivalent amount in VND (for reference)")
    usdt_rate: float = Field(
        ..., description="USDT/VND exchange rate at time of payment"
    )

    # Blockchain info
    from_address: Optional[str] = Field(None, description="User's wallet address")
    to_address: str = Field(..., description="WordAI's BEP20 wallet address")
    transaction_hash: Optional[str] = Field(None, description="BSC transaction hash")
    block_number: Optional[int] = Field(None, description="Block number on BSC")
    gas_used: Optional[str] = None

    # Payment status
    status: PaymentStatus = Field(default="pending")
    confirmation_count: int = Field(
        default=0, description="Number of block confirmations"
    )
    required_confirmations: int = Field(
        default=12, description="Required confirmations (default 12)"
    )

    # Subscription/Points reference (after activation)
    subscription_id: Optional[str] = None
    points_transaction_id: Optional[str] = None

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    payment_received_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None  # Payment request expiration (usually 30min)

    # Metadata
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    notes: Optional[str] = None
    error_message: Optional[str] = None

    # Admin fields
    manually_processed: bool = Field(default=False)
    processed_by_admin: Optional[str] = None
    admin_notes: Optional[str] = None

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str, datetime: lambda v: v.isoformat()}
        schema_extra = {
            "example": {
                "payment_id": "USDT-1730123456-abc",
                "order_invoice_number": "WA-USDT-1730123456-abc",
                "user_id": "firebase_uid_123",
                "user_email": "user@example.com",
                "payment_type": "subscription",
                "plan": "premium",
                "duration": "3_months",
                "amount_usdt": 12.5,
                "amount_vnd": 279000,
                "usdt_rate": 22320,
                "to_address": "0xbab94f5bf90550c9f0147fffae8a1ef006b85a07",
                "status": "completed",
                "created_at": "2025-11-05T09:30:00Z",
            }
        }


class USDTPendingTransaction(BaseModel):
    """
    Pending USDT transaction awaiting confirmation
    Collection: usdt_pending_transactions
    """

    id: Optional[PyObjectId] = Field(alias="_id", default=None)

    # References
    payment_id: str = Field(..., description="Reference to usdt_payments collection")
    user_id: str = Field(..., description="Firebase UID")
    transaction_hash: str = Field(..., description="BSC transaction hash")

    # Transaction details
    from_address: str
    to_address: str
    amount_usdt: float

    # Confirmation tracking
    first_seen_at: datetime = Field(default_factory=datetime.utcnow)
    last_checked_at: datetime = Field(default_factory=datetime.utcnow)
    confirmation_count: int = Field(default=0)
    required_confirmations: int = Field(default=12)

    # Status
    status: Literal["pending", "confirmed", "failed"] = Field(default="pending")

    # Webhook/background job
    webhook_attempts: int = Field(default=0)
    last_webhook_attempt: Optional[datetime] = None

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str, datetime: lambda v: v.isoformat()}


class USDTWalletAddress(BaseModel):
    """
    User wallet address management
    Collection: usdt_wallet_addresses
    """

    id: Optional[PyObjectId] = Field(alias="_id", default=None)

    # User info
    user_id: str = Field(..., description="Firebase UID")
    wallet_address: str = Field(..., description="BEP20 wallet address")

    # Verification
    is_verified: bool = Field(default=False)
    verified_at: Optional[datetime] = None

    # Usage tracking
    first_used_at: datetime = Field(default_factory=datetime.utcnow)
    last_used_at: datetime = Field(default_factory=datetime.utcnow)
    payment_count: int = Field(default=0, description="Number of successful payments")
    total_amount_usdt: float = Field(
        default=0.0, description="Total USDT sent from this address"
    )

    # Metadata
    label: Optional[str] = Field(None, description="User-defined label for wallet")
    notes: Optional[str] = None

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str, datetime: lambda v: v.isoformat()}


# =====================================
# REQUEST/RESPONSE MODELS
# =====================================


class CreateUSDTSubscriptionPaymentRequest(BaseModel):
    """Request to create USDT payment for subscription"""

    plan: PlanType = Field(..., description="Subscription plan")
    duration: DurationType = Field(..., description="Subscription duration")
    from_address: str = Field(
        ..., description="User's wallet address (required for balance check)"
    )

    class Config:
        schema_extra = {
            "example": {
                "plan": "premium",
                "duration": "3_months",
                "from_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
            }
        }


class CreateUSDTPointsPaymentRequest(BaseModel):
    """Request to create USDT payment for points purchase"""

    points_amount: int = Field(
        ..., ge=50, description="Number of points to purchase (min 50)"
    )
    from_address: str = Field(
        ..., description="User's wallet address (required for balance check)"
    )

    class Config:
        schema_extra = {
            "example": {
                "points_amount": 100,
                "from_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
            }
        }


class USDTPaymentResponse(BaseModel):
    """Response after creating USDT payment request"""

    payment_id: str
    order_invoice_number: str
    payment_type: PaymentType

    # Payment details
    amount_usdt: float
    amount_vnd: int
    usdt_rate: float

    # Wallet info
    to_address: str = Field(..., description="WordAI's BEP20 wallet address")
    network: str = Field(default="BSC", description="BNB Smart Chain")
    token_contract: str = Field(
        default="0x55d398326f99059fF775485246999027B3197955",
        description="USDT BEP20 contract",
    )

    # Instructions
    instructions: str = Field(
        default="Send the exact USDT amount to the provided address. Payment will be confirmed after 12 block confirmations.",
        description="Payment instructions",
    )

    # Timing
    expires_at: datetime
    status: PaymentStatus

    class Config:
        schema_extra = {
            "example": {
                "payment_id": "USDT-1730123456-abc",
                "order_invoice_number": "WA-USDT-1730123456-abc",
                "payment_type": "subscription",
                "amount_usdt": 12.5,
                "amount_vnd": 279000,
                "usdt_rate": 22320,
                "to_address": "0xbab94f5bf90550c9f0147fffae8a1ef006b85a07",
                "network": "BSC",
                "token_contract": "0x55d398326f99059fF775485246999027B3197955",
                "expires_at": "2025-11-05T10:00:00Z",
                "status": "pending",
            }
        }


class CheckUSDTPaymentStatusResponse(BaseModel):
    """Response for checking payment status"""

    payment_id: str
    status: PaymentStatus
    payment_type: PaymentType

    # Transaction info
    transaction_hash: Optional[str] = None
    confirmation_count: int = 0
    required_confirmations: int = 12

    # Amount
    amount_usdt: float
    from_address: Optional[str] = None

    # Timestamps
    created_at: datetime
    payment_received_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Subscription/Points info
    subscription_id: Optional[str] = None
    points_transaction_id: Optional[str] = None

    # Message
    message: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "payment_id": "USDT-1730123456-abc",
                "status": "confirmed",
                "payment_type": "subscription",
                "transaction_hash": "0x1234567890abcdef",
                "confirmation_count": 12,
                "required_confirmations": 12,
                "amount_usdt": 12.5,
                "from_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
                "created_at": "2025-11-05T09:30:00Z",
                "confirmed_at": "2025-11-05T09:35:00Z",
                "completed_at": "2025-11-05T09:35:05Z",
                "subscription_id": "sub_abc123",
                "message": "Payment confirmed and subscription activated",
            }
        }


class VerifyTransactionRequest(BaseModel):
    """Request to manually verify transaction hash"""

    payment_id: str = Field(..., description="Payment ID")
    transaction_hash: str = Field(..., description="BSC transaction hash")

    class Config:
        schema_extra = {
            "example": {
                "payment_id": "USDT-1730123456-abc",
                "transaction_hash": "0x1234567890abcdef",
            }
        }


class USDTRateResponse(BaseModel):
    """Current USDT exchange rate"""

    rate: float = Field(..., description="USDT/VND exchange rate")
    last_updated: datetime
    source: str = Field(default="binance", description="Price source")

    class Config:
        schema_extra = {
            "example": {
                "rate": 22320.0,
                "last_updated": "2025-11-05T09:30:00Z",
                "source": "binance",
            }
        }
