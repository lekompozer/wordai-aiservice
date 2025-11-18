"""
Subscription Service - Business Logic for User Plans and Subscriptions

This service handles:
- Creating and managing subscriptions
- Checking usage limits
- Updating usage counters
- Plan upgrades/downgrades
- Subscription cancellation
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.database import Database
from bson import ObjectId
import os
import logging

from src.models.subscription import (
    UserSubscription,
    CreateSubscriptionRequest,
    UpdateSubscriptionRequest,
    SubscriptionUsageUpdate,
    SubscriptionResponse,
    PlanType,
    DurationType,
    PLAN_CONFIGS,
    get_plan_config,
    get_points_for_plan,
    get_price_for_plan,
)

logger = logging.getLogger(__name__)


class SubscriptionService:
    """Service for managing user subscriptions"""

    def __init__(self, mongodb_client: Optional[MongoClient] = None):
        """
        Initialize subscription service

        Args:
            mongodb_client: MongoDB client instance (optional, will create if not provided)
        """
        if mongodb_client:
            self.client = mongodb_client
        else:
            # Use authenticated URI if available, fallback to basic URI
            mongodb_uri = os.getenv("MONGODB_URI_AUTH")
            if not mongodb_uri:
                # Fallback: build authenticated URI from components
                mongo_user = os.getenv("MONGODB_APP_USERNAME")
                mongo_pass = os.getenv("MONGODB_APP_PASSWORD")
                mongo_host = (
                    os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
                    .replace("mongodb://", "")
                    .rstrip("/")
                )
                db_name = os.getenv("MONGODB_NAME", "ai_service_db")

                if mongo_user and mongo_pass:
                    mongodb_uri = f"mongodb://{mongo_user}:{mongo_pass}@{mongo_host}/{db_name}?authSource=admin"
                else:
                    mongodb_uri = os.getenv("MONGODB_URI")

            self.client = MongoClient(mongodb_uri)

        self.db: Database = self.client[os.getenv("MONGODB_DATABASE", "ai_service_db")]
        self.subscriptions = self.db["user_subscriptions"]
        self.users = self.db["users"]

        # Create indexes on initialization
        self._ensure_indexes()

    def _ensure_indexes(self):
        """Create necessary indexes for performance"""
        try:
            # user_subscriptions indexes
            self.subscriptions.create_index([("user_id", ASCENDING)], unique=True)
            self.subscriptions.create_index([("expires_at", ASCENDING)])
            self.subscriptions.create_index([("is_active", ASCENDING)])
            self.subscriptions.create_index(
                [("plan", ASCENDING), ("is_active", ASCENDING)]
            )
            self.subscriptions.create_index([("created_at", DESCENDING)])

            logger.info("Subscription indexes created successfully")
        except Exception as e:
            logger.error(f"Error creating indexes: {e}")

    async def get_or_create_subscription(self, user_id: str) -> UserSubscription:
        """
        Get existing subscription or create free tier for new user

        Args:
            user_id: Firebase UID

        Returns:
            UserSubscription object
        """
        subscription_doc = self.subscriptions.find_one({"user_id": user_id})

        if subscription_doc:
            return UserSubscription(**subscription_doc)

        # Create free subscription for new user
        logger.info(f"Creating free subscription for user: {user_id}")
        return await self.create_free_subscription(user_id)

    async def create_free_subscription(self, user_id: str) -> UserSubscription:
        """
        Create free tier subscription for new user

        FREE tier includes:
        - 10 bonus points to try AI features (Claude, ChatGPT, AI operations)
        - 10 FREE Deepseek chats/day (no points deduction)
        - Basic storage and document limits

        Args:
            user_id: Firebase UID

        Returns:
            UserSubscription object
        """
        free_config = PLAN_CONFIGS["free"]

        # FREE tier gets 10 bonus points
        bonus_points = free_config.points_3_months  # 10 points

        subscription = UserSubscription(
            user_id=user_id,
            plan="free",
            duration=None,
            price=0,
            points_total=bonus_points,  # Updated: 10 bonus points
            points_used=0,
            points_remaining=bonus_points,  # Updated: 10 bonus points available
            earnings_points=0,  # ✅ Revenue from sales (starts at 0)
            started_at=datetime.utcnow(),
            expires_at=None,  # Free never expires
            is_active=True,
            storage_limit_mb=free_config.storage_mb,
            upload_files_limit=free_config.upload_files_limit,
            documents_limit=free_config.documents_limit,
            secret_files_limit=free_config.secret_files_limit,
            daily_chat_limit=free_config.daily_chat_limit,  # 10 chats/day
            last_chat_reset=datetime.utcnow(),
        )

        # Insert to database
        result = self.subscriptions.insert_one(
            subscription.dict(by_alias=True, exclude={"id"})
        )
        subscription.id = result.inserted_id

        # Update user document with unified points system
        self.users.update_one(
            {"firebase_uid": user_id},  # Use firebase_uid for consistency
            {
                "$set": {
                    "current_plan": "free",
                    "subscription_id": str(result.inserted_id),
                    "subscription_expires_at": None,
                    "points_remaining": bonus_points,  # Legacy field (keep for compatibility)
                    "points": bonus_points,  # ✅ UNIFIED: Sync to main points field
                    "storage_limit_mb": free_config.storage_mb,
                    "plan_updated_at": datetime.utcnow(),
                }
            },
            upsert=True,  # Create if not exists
        )

        logger.info(
            f"Created free subscription with {bonus_points} bonus points: {result.inserted_id} for user: {user_id}"
        )
        logger.info(f"✅ Synced {bonus_points} points to user.points (unified system)")
        return subscription

    async def create_paid_subscription(
        self, request: CreateSubscriptionRequest
    ) -> UserSubscription:
        """
        Create or upgrade to paid subscription

        Args:
            request: CreateSubscriptionRequest with plan details

        Returns:
            UserSubscription object

        Raises:
            ValueError: If user already has active paid subscription
        """
        # Check if user already has subscription
        existing = self.subscriptions.find_one({"user_id": request.user_id})

        plan_config = PLAN_CONFIGS[request.plan]
        points = get_points_for_plan(request.plan, request.duration)
        price = get_price_for_plan(request.plan, request.duration)

        # Calculate expiration date
        started_at = datetime.utcnow()
        if request.duration == "3_months":
            expires_at = started_at + timedelta(days=90)
        else:  # 12_months
            expires_at = started_at + timedelta(days=365)

        subscription_data = {
            "user_id": request.user_id,
            "plan": request.plan,
            "duration": request.duration,
            "price": price,
            "points_total": points,
            "points_used": 0,
            "points_remaining": points,
            "earnings_points": (
                existing.get("earnings_points", 0) if existing else 0
            ),  # ✅ Preserve earnings
            "started_at": started_at,
            "expires_at": expires_at,
            "is_active": True,
            "auto_renew": False,
            "payment_id": request.payment_id,
            "payment_method": request.payment_method,
            "storage_used_mb": existing["storage_used_mb"] if existing else 0.0,
            "storage_limit_mb": plan_config.storage_mb,
            "upload_files_count": existing["upload_files_count"] if existing else 0,
            "upload_files_limit": plan_config.upload_files_limit,
            "documents_count": existing["documents_count"] if existing else 0,
            "documents_limit": plan_config.documents_limit,
            "secret_files_count": existing["secret_files_count"] if existing else 0,
            "secret_files_limit": plan_config.secret_files_limit,
            "daily_chat_count": 0,
            "daily_chat_limit": plan_config.daily_chat_limit,
            "last_chat_reset": started_at,
            "manually_activated": request.manually_activated,
            "activated_by_admin": request.activated_by_admin,
            "notes": request.notes,
            "created_at": started_at,
            "updated_at": started_at,
        }

        if existing:
            # Update existing subscription
            result = self.subscriptions.update_one(
                {"user_id": request.user_id}, {"$set": subscription_data}
            )
            subscription_id = existing["_id"]
            logger.info(
                f"Upgraded subscription for user: {request.user_id} to {request.plan}"
            )
        else:
            # Create new subscription
            result = self.subscriptions.insert_one(subscription_data)
            subscription_id = result.inserted_id
            logger.info(
                f"Created subscription: {subscription_id} for user: {request.user_id}"
            )

        # Update user document
        self.users.update_one(
            {"uid": request.user_id},
            {
                "$set": {
                    "current_plan": request.plan,
                    "subscription_id": str(subscription_id),
                    "subscription_expires_at": expires_at,
                    "points_remaining": points,
                    "storage_limit_mb": plan_config.storage_mb,
                    "plan_updated_at": started_at,
                }
            },
        )

        # Fetch and return created/updated subscription
        subscription_doc = self.subscriptions.find_one({"_id": subscription_id})
        return UserSubscription(**subscription_doc)

    async def cancel_subscription(
        self, user_id: str, reason: Optional[str] = None
    ) -> UserSubscription:
        """
        Cancel user subscription (will remain active until expiration)

        Args:
            user_id: Firebase UID
            reason: Cancellation reason

        Returns:
            Updated UserSubscription

        Raises:
            ValueError: If subscription not found
        """
        subscription = self.subscriptions.find_one({"user_id": user_id})
        if not subscription:
            raise ValueError(f"Subscription not found for user: {user_id}")

        # Update subscription
        self.subscriptions.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "auto_renew": False,
                    "cancelled_at": datetime.utcnow(),
                    "cancellation_reason": reason,
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        logger.info(f"Cancelled subscription for user: {user_id}")

        # Fetch and return updated subscription
        subscription_doc = self.subscriptions.find_one({"user_id": user_id})
        return UserSubscription(**subscription_doc)

    async def extend_subscription(
        self,
        user_id: str,
        extend_days: int,
        reason: str,
        admin_id: Optional[str] = None,
    ) -> UserSubscription:
        """
        Extend subscription expiration date (admin only)

        Args:
            user_id: Firebase UID
            extend_days: Number of days to extend
            reason: Reason for extension
            admin_id: Admin who performed the action

        Returns:
            Updated UserSubscription
        """
        subscription = self.subscriptions.find_one({"user_id": user_id})
        if not subscription:
            raise ValueError(f"Subscription not found for user: {user_id}")

        old_expires_at = subscription["expires_at"]
        new_expires_at = old_expires_at + timedelta(days=extend_days)

        self.subscriptions.update_one(
            {"user_id": user_id},
            {
                "$set": {"expires_at": new_expires_at, "updated_at": datetime.utcnow()},
                "$push": {
                    "extension_history": {
                        "extended_by_admin": admin_id,
                        "extended_days": extend_days,
                        "reason": reason,
                        "old_expires_at": old_expires_at,
                        "new_expires_at": new_expires_at,
                        "extended_at": datetime.utcnow(),
                    }
                },
            },
        )

        # Update user document
        self.users.update_one(
            {"uid": user_id}, {"$set": {"subscription_expires_at": new_expires_at}}
        )

        logger.info(f"Extended subscription for user: {user_id} by {extend_days} days")

        subscription_doc = self.subscriptions.find_one({"user_id": user_id})
        return UserSubscription(**subscription_doc)

    async def check_and_update_expired_subscriptions(self) -> int:
        """
        Check for expired subscriptions and downgrade to free
        Should be run daily via cron job

        Returns:
            Number of subscriptions downgraded
        """
        now = datetime.utcnow()

        expired = self.subscriptions.find(
            {"is_active": True, "expires_at": {"$lte": now}, "plan": {"$ne": "free"}}
        )

        count = 0
        for subscription in expired:
            user_id = subscription["user_id"]

            # Downgrade to free
            await self.downgrade_to_free(user_id, "Subscription expired")
            count += 1

        logger.info(f"Downgraded {count} expired subscriptions to free")
        return count

    async def downgrade_to_free(self, user_id: str, reason: str) -> UserSubscription:
        """
        Downgrade subscription to free tier

        Args:
            user_id: Firebase UID
            reason: Reason for downgrade

        Returns:
            Updated UserSubscription
        """
        free_config = PLAN_CONFIGS["free"]

        self.subscriptions.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "plan": "free",
                    "duration": None,
                    "is_active": True,
                    "points_total": 0,
                    "points_remaining": 0,
                    "storage_limit_mb": free_config.storage_mb,
                    "upload_files_limit": free_config.upload_files_limit,
                    "documents_limit": free_config.documents_limit,
                    "secret_files_limit": free_config.secret_files_limit,
                    "daily_chat_limit": free_config.daily_chat_limit,
                    "updated_at": datetime.utcnow(),
                    "downgrade_reason": reason,
                }
            },
        )

        # Update user document
        self.users.update_one(
            {"uid": user_id},
            {
                "$set": {
                    "current_plan": "free",
                    "subscription_expires_at": None,
                    "points_remaining": 0,
                    "storage_limit_mb": free_config.storage_mb,
                    "plan_updated_at": datetime.utcnow(),
                }
            },
        )

        logger.info(f"Downgraded user: {user_id} to free - Reason: {reason}")

        subscription_doc = self.subscriptions.find_one({"user_id": user_id})
        return UserSubscription(**subscription_doc)

    async def update_usage(
        self, user_id: str, update: SubscriptionUsageUpdate
    ) -> UserSubscription:
        """
        Update usage counters using $inc (increment)

        Args:
            user_id: Firebase UID
            update: SubscriptionUsageUpdate with INCREMENT values (not absolute values)
                - storage_mb: MB to ADD to current storage
                - upload_files: Number of files to ADD to counter
                - documents: Number of documents to ADD to counter
                - secret_files: Number of secret files to ADD to counter

        Returns:
            Updated UserSubscription
        """
        inc_fields = {}
        set_fields = {}

        # Use $inc for counters (increment, not set)
        if update.storage_mb is not None:
            inc_fields["storage_used_mb"] = update.storage_mb

        if update.upload_files is not None:
            inc_fields["upload_files_count"] = update.upload_files

        if update.documents is not None:
            inc_fields["documents_count"] = update.documents

        if update.secret_files is not None:
            inc_fields["secret_files_count"] = update.secret_files

        if update.daily_chat is not None:
            # Check if need to reset daily counter
            subscription = self.subscriptions.find_one({"user_id": user_id})
            last_reset = subscription.get("last_chat_reset")

            if last_reset and (datetime.utcnow() - last_reset).days >= 1:
                # Reset counter
                set_fields["daily_chat_count"] = 1
                set_fields["last_chat_reset"] = datetime.utcnow()
            else:
                # Increment counter
                inc_fields["daily_chat_count"] = 1

        # Apply updates
        update_ops = {}
        if inc_fields:
            update_ops["$inc"] = inc_fields
        if set_fields:
            set_fields["updated_at"] = datetime.utcnow()
            update_ops["$set"] = set_fields
        elif inc_fields:
            # Only $inc, still need to update timestamp
            update_ops["$set"] = {"updated_at": datetime.utcnow()}

        if update_ops:
            self.subscriptions.update_one({"user_id": user_id}, update_ops)

        subscription_doc = self.subscriptions.find_one({"user_id": user_id})
        return UserSubscription(**subscription_doc)

    async def check_storage_limit(self, user_id: str, additional_mb: float) -> bool:
        """
        Check if user can upload more files (storage limit)

        Args:
            user_id: Firebase UID
            additional_mb: Size of file to upload in MB

        Returns:
            True if within limit, False otherwise
        """
        subscription = await self.get_or_create_subscription(user_id)

        total_after_upload = subscription.storage_used_mb + additional_mb

        return total_after_upload <= subscription.storage_limit_mb

    async def check_upload_files_limit(self, user_id: str) -> bool:
        """
        Check if user can upload more files (count limit)

        Returns:
            True if within limit, False otherwise
        """
        subscription = await self.get_or_create_subscription(user_id)

        # -1 means unlimited
        if subscription.upload_files_limit == -1:
            return True

        return subscription.upload_files_count < subscription.upload_files_limit

    async def check_documents_limit(self, user_id: str) -> bool:
        """
        Check if user can create more documents

        Returns:
            True if within limit, False otherwise
        """
        subscription = await self.get_or_create_subscription(user_id)

        # -1 means unlimited
        if subscription.documents_limit == -1:
            return True

        return subscription.documents_count < subscription.documents_limit

    async def check_daily_chat_limit(self, user_id: str) -> bool:
        """
        Check if user can make more AI chats today (free tier only)

        Returns:
            True if within limit, False otherwise
        """
        subscription = await self.get_or_create_subscription(user_id)

        # -1 means unlimited (paid plans)
        if subscription.daily_chat_limit == -1:
            return True

        # Check if need to reset counter
        if (
            subscription.last_chat_reset
            and (datetime.utcnow() - subscription.last_chat_reset).days >= 1
        ):
            # Reset and allow
            await self.update_usage(user_id, SubscriptionUsageUpdate(daily_chat=0))
            return True

        return subscription.daily_chat_count < subscription.daily_chat_limit

    async def can_create_test(self, user_id: str) -> bool:
        """
        Check if user can create online tests

        Returns:
            True if allowed (paid plans only), False otherwise
        """
        subscription = await self.get_or_create_subscription(user_id)
        plan_config = PLAN_CONFIGS[subscription.plan]

        return plan_config.can_create_tests

    async def get_subscription_response(self, user_id: str) -> SubscriptionResponse:
        """
        Get subscription with calculated fields for API response

        Args:
            user_id: Firebase UID

        Returns:
            SubscriptionResponse with all fields calculated
        """
        subscription = await self.get_or_create_subscription(user_id)

        # Calculate days remaining
        days_remaining = None
        if subscription.expires_at:
            delta = subscription.expires_at - datetime.utcnow()
            days_remaining = max(0, delta.days)

        # Calculate storage percentage
        storage_percentage = 0.0
        if subscription.storage_limit_mb > 0:
            storage_percentage = (
                subscription.storage_used_mb / subscription.storage_limit_mb
            ) * 100

        # Check limits
        can_upload = await self.check_upload_files_limit(
            user_id
        ) and await self.check_storage_limit(user_id, 0)
        can_create_doc = await self.check_documents_limit(user_id)
        can_create_test_val = await self.can_create_test(user_id)

        return SubscriptionResponse(
            subscription_id=str(subscription.id),
            user_id=subscription.user_id,
            plan=subscription.plan,
            duration=subscription.duration,
            is_active=subscription.is_active,
            started_at=subscription.started_at,
            expires_at=subscription.expires_at,
            days_remaining=days_remaining,
            points_total=subscription.points_total,
            points_used=subscription.points_used,
            points_remaining=subscription.points_remaining,
            storage_used_mb=subscription.storage_used_mb,
            storage_limit_mb=subscription.storage_limit_mb,
            storage_percentage=round(storage_percentage, 2),
            upload_files_count=subscription.upload_files_count,
            upload_files_limit=subscription.upload_files_limit,
            documents_count=subscription.documents_count,
            documents_limit=subscription.documents_limit,
            can_upload_file=can_upload,
            can_create_document=can_create_doc,
            can_create_test=can_create_test_val,
        )

    async def get_all_subscriptions(
        self,
        plan: Optional[PlanType] = None,
        status: Optional[str] = None,  # "active", "expired", "cancelled"
        page: int = 1,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """
        Get all subscriptions with filters (admin only)

        Args:
            plan: Filter by plan type
            status: Filter by status
            page: Page number (1-indexed)
            limit: Items per page

        Returns:
            Dict with subscriptions, total, page info
        """
        query = {}

        if plan:
            query["plan"] = plan

        if status == "active":
            query["is_active"] = True
            query["expires_at"] = {"$gt": datetime.utcnow()}
        elif status == "expired":
            query["expires_at"] = {"$lte": datetime.utcnow()}
        elif status == "cancelled":
            query["cancelled_at"] = {"$ne": None}

        total = self.subscriptions.count_documents(query)
        skip = (page - 1) * limit

        subscriptions = list(
            self.subscriptions.find(query)
            .sort("created_at", DESCENDING)
            .skip(skip)
            .limit(limit)
        )

        # Enrich with user data
        for sub in subscriptions:
            user = self.users.find_one({"uid": sub["user_id"]})
            if user:
                sub["user_email"] = user.get("email")
                sub["user_name"] = user.get("name") or user.get("display_name")

        return {
            "subscriptions": subscriptions,
            "total": total,
            "page": page,
            "pages": (total + limit - 1) // limit,
            "limit": limit,
        }


# Global service instance helper
def get_subscription_service() -> SubscriptionService:
    """Get or create global subscription service instance"""
    return SubscriptionService()
