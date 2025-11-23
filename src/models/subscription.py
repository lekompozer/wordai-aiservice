"""
Subscription Models for User Plans and Payment System

This module defines Pydantic models for:
- User Subscriptions
- Subscription Plans
- Usage Tracking
"""

from datetime import datetime
from typing import Optional, Literal
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


# Type aliases for better readability
PlanType = Literal["free", "premium", "pro", "vip"]
DurationType = Literal["3_months", "12_months"]
PaymentMethod = Literal[
    "BANK_TRANSFER",
    "BANK_TRANSFER_MANUAL",
    "SEPAY_BANK_TRANSFER",  # SePay payment gateway
    "VISA",
    "MASTERCARD",
    "MOMO",
    "ZALOPAY",
]


class SubscriptionPlan(BaseModel):
    """Definition of a subscription plan with features and pricing"""

    plan: PlanType
    name: str

    # Features
    storage_mb: int
    upload_files_limit: int  # -1 for unlimited
    documents_limit: int  # -1 for unlimited
    secret_files_limit: int  # -1 for unlimited
    can_create_tests: bool
    daily_chat_limit: int  # -1 for unlimited, 15 for free tier

    # Points
    points_3_months: int
    points_12_months: int

    # Pricing (VND)
    price_3_months: int
    price_12_months: int

    # Marketing
    description: str = ""
    features_list: list[str] = []
    is_popular: bool = False
    discount_percentage_12mo: float = 0.0

    class Config:
        schema_extra = {
            "example": {
                "plan": "premium",
                "name": "Premium",
                "storage_mb": 2048,
                "upload_files_limit": 100,
                "documents_limit": 100,
                "secret_files_limit": 100,
                "can_create_tests": True,
                "daily_chat_limit": -1,
                "points_3_months": 300,
                "points_12_months": 1200,
                "price_3_months": 279000,
                "price_12_months": 990000,
                "description": "Perfect for professionals",
                "features_list": ["2GB Storage", "300 AI Points", "100 Files"],
                "is_popular": True,
                "discount_percentage_12mo": 11.0,
            }
        }


class UserSubscription(BaseModel):
    """User subscription document stored in MongoDB"""

    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: str = Field(..., description="Firebase UID")

    # Plan details
    plan: PlanType = Field(default="free")
    duration: Optional[DurationType] = None
    price: int = Field(default=0, description="Amount paid in VND")

    # Points
    points_total: int = Field(default=0, description="Lifetime points received")
    points_used: int = Field(default=0, description="Lifetime points spent")
    points_remaining: int = Field(default=0, description="Current spending balance")
    earnings_points: int = Field(
        default=0, description="Revenue from Books + Tests sales (withdrawable)"
    )

    # Subscription period
    started_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    is_active: bool = Field(default=True)
    auto_renew: bool = Field(default=False)

    # Payment reference
    payment_id: Optional[str] = None
    payment_method: Optional[PaymentMethod] = None

    # Usage limits and tracking
    storage_used_mb: float = Field(default=0.0)
    storage_limit_mb: int = Field(default=50)  # Default: 50MB for free

    upload_files_count: int = Field(default=0)
    upload_files_limit: int = Field(default=10)  # Default: 10 files for free

    documents_count: int = Field(default=0)
    documents_limit: int = Field(default=10)  # Default: 10 docs for free

    secret_files_count: int = Field(default=0)
    secret_files_limit: int = Field(default=1)  # Default: 1 secret file for free

    # Daily limits (for free tier chat)
    daily_chat_count: int = Field(default=0)
    daily_chat_limit: int = Field(default=10)  # 10 for free, -1 for unlimited
    last_chat_reset: Optional[datetime] = None

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None

    # Admin fields
    manually_activated: bool = Field(default=False)
    activated_by_admin: Optional[str] = None
    notes: Optional[str] = None

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str, datetime: lambda v: v.isoformat()}
        schema_extra = {
            "example": {
                "user_id": "firebase_uid_123",
                "plan": "premium",
                "duration": "3_months",
                "price": 279000,
                "points_total": 300,
                "points_used": 15,
                "points_remaining": 285,
                "started_at": "2025-11-05T09:45:00Z",
                "expires_at": "2026-02-05T09:45:00Z",
                "is_active": True,
                "storage_used_mb": 145.5,
                "storage_limit_mb": 2048,
            }
        }


class CreateSubscriptionRequest(BaseModel):
    """Request model for creating/upgrading subscription"""

    user_id: str
    plan: Literal["premium", "pro", "vip"]  # Cannot create free manually
    duration: DurationType
    payment_id: Optional[str] = None
    payment_method: Optional[PaymentMethod] = None
    manually_activated: bool = Field(default=False)
    activated_by_admin: Optional[str] = None
    notes: Optional[str] = None


class UpdateSubscriptionRequest(BaseModel):
    """Request model for updating subscription"""

    auto_renew: Optional[bool] = None
    cancellation_reason: Optional[str] = None


class SubscriptionUsageUpdate(BaseModel):
    """Model for updating usage counters"""

    storage_mb: Optional[float] = None
    upload_files: Optional[int] = None
    documents: Optional[int] = None
    secret_files: Optional[int] = None
    daily_chat: Optional[int] = None


class SubscriptionResponse(BaseModel):
    """Response model for subscription endpoints"""

    subscription_id: str
    user_id: str
    plan: PlanType
    duration: Optional[DurationType]

    # Status
    is_active: bool
    started_at: Optional[datetime]
    expires_at: Optional[datetime]
    days_remaining: Optional[int] = None

    # Points
    points_total: int
    points_used: int
    points_remaining: int

    # Usage
    storage_used_mb: float
    storage_limit_mb: int
    storage_percentage: float = 0.0

    upload_files_count: int
    upload_files_limit: int

    documents_count: int
    documents_limit: int

    # Limits check
    can_upload_file: bool = True
    can_create_document: bool = True
    can_create_test: bool = True

    class Config:
        schema_extra = {
            "example": {
                "subscription_id": "673456789abcdef",
                "user_id": "firebase_uid_123",
                "plan": "premium",
                "duration": "3_months",
                "is_active": True,
                "started_at": "2025-11-05T09:45:00Z",
                "expires_at": "2026-02-05T09:45:00Z",
                "days_remaining": 92,
                "points_total": 300,
                "points_used": 15,
                "points_remaining": 285,
                "storage_used_mb": 145.5,
                "storage_limit_mb": 2048,
                "storage_percentage": 7.1,
                "can_upload_file": True,
                "can_create_document": True,
                "can_create_test": True,
            }
        }


# Plan configurations (can be loaded from config file)
PLAN_CONFIGS = {
    "free": SubscriptionPlan(
        plan="free",
        name="Free",
        storage_mb=50,
        upload_files_limit=10,
        documents_limit=10,
        secret_files_limit=1,
        can_create_tests=False,
        daily_chat_limit=10,  # Updated: 10 chats/day with Deepseek
        points_3_months=20,  # Updated: 20 bonus points to try AI features
        points_12_months=20,  # Same bonus for any duration
        price_3_months=0,
        price_12_months=0,
        description="Basic features for getting started",
        features_list=[
            "50MB Storage",
            "10 FREE Deepseek chats/day",
            "20 bonus points to try AI features",
            "Join tests (cannot create)",
            "10 documents",
            "1 secret file (no share)",
        ],
    ),
    "premium": SubscriptionPlan(
        plan="premium",
        name="Premium",
        storage_mb=2048,
        upload_files_limit=100,
        documents_limit=100,
        secret_files_limit=100,
        can_create_tests=True,
        daily_chat_limit=-1,
        points_3_months=300,
        points_12_months=1200,
        price_3_months=279000,
        price_12_months=990000,
        description="Perfect for professionals",
        features_list=[
            "2GB Storage",
            "300 AI Points (3mo) / 1200 (12mo)",
            "Unlimited AI chats",
            "Create online tests",
            "100 documents & secret files",
        ],
        is_popular=True,
        discount_percentage_12mo=11.0,
    ),
    "pro": SubscriptionPlan(
        plan="pro",
        name="Pro",
        storage_mb=15360,  # 15GB
        upload_files_limit=-1,
        documents_limit=1000,
        secret_files_limit=1000,
        can_create_tests=True,
        daily_chat_limit=-1,
        points_3_months=500,
        points_12_months=2000,
        price_3_months=447000,
        price_12_months=1699000,
        description="For power users and small teams",
        features_list=[
            "15GB Storage",
            "500 AI Points (3mo) / 2000 (12mo)",
            "Unlimited files upload",
            "1000 documents",
            "1000 secret files",
        ],
        discount_percentage_12mo=16.0,
    ),
    "vip": SubscriptionPlan(
        plan="vip",
        name="VIP",
        storage_mb=51200,  # 50GB
        upload_files_limit=-1,
        documents_limit=-1,
        secret_files_limit=-1,
        can_create_tests=True,
        daily_chat_limit=-1,
        points_3_months=1000,
        points_12_months=4000,
        price_3_months=747000,
        price_12_months=2799000,
        description="Unlimited power for professionals",
        features_list=[
            "50GB Storage",
            "1000 AI Points (3mo) / 4000 (12mo)",
            "Unlimited everything",
            "Priority support",
            "Advanced features",
        ],
        discount_percentage_12mo=7.0,
    ),
}


def get_plan_config(plan: PlanType) -> SubscriptionPlan:
    """Get configuration for a specific plan"""
    return PLAN_CONFIGS[plan]


def get_points_for_plan(plan: PlanType, duration: DurationType) -> int:
    """Get points amount for a plan and duration"""
    config = PLAN_CONFIGS[plan]
    if duration == "3_months":
        return config.points_3_months
    return config.points_12_months


def get_price_for_plan(plan: PlanType, duration: DurationType) -> int:
    """Get price for a plan and duration"""
    config = PLAN_CONFIGS[plan]
    if duration == "3_months":
        return config.price_3_months
    return config.price_12_months
