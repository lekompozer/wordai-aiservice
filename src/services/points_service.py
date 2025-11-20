"""
Points Service - Business Logic for Points Management

This service handles:
- Checking points balance
- Deducting points for AI operations
- Granting points (admin/payment)
- Points transaction history
- Points expiration
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.database import Database
from bson import ObjectId
import os
import logging

from src.models.payment import (
    PointsTransaction,
    TransactionType,
    PointsGrantRequest,
    PointsDeductRequest,
)
from src.exceptions import InsufficientPointsError

logger = logging.getLogger(__name__)


# Points cost for each service type
# VARIABLE PRICING by AI provider and operation
SERVICE_POINTS_COST = {
    # Chat operations - Variable pricing by provider
    "ai_chat_deepseek": 1,  # Deepseek: 1 point (cheaper)
    "ai_chat_deepseek_chat": 1,  # DeepSeek Chat: 1 point (cheaper) - handle both variants
    "ai_chat_claude": 2,  # Claude: 2 points
    "ai_chat_chatgpt": 2,  # ChatGPT: 2 points
    "ai_chat_gemini": 2,  # Gemini: 2 points
    "ai_chat_cerebras": 2,  # Cerebras: 2 points
    "ai_chat_default": 2,  # Other providers: 2 points
    # Document chat operations - Same pricing
    "ai_document_chat_deepseek": 1,  # DeepSeek: 1 point
    "ai_document_chat_deepseek_chat": 1,  # DeepSeek Chat: 1 point - handle both variants
    "ai_document_chat_claude": 2,  # Claude: 2 points
    "ai_document_chat_chatgpt": 2,  # ChatGPT: 2 points
    "ai_document_chat_gemini": 2,  # Gemini: 2 points
    "ai_document_chat_cerebras": 2,  # Cerebras: 2 points
    # Document AI operations
    "ai_edit": 2,
    "ai_translate": 2,
    "ai_format": 2,
    "ai_dual_language": 2,
    "document_generation": 2,
    # File/Slide AI operations
    "slide_generation": 2,
    "file_to_doc_conversion": 2,
    "file_to_slide_conversion": 2,
    "file_analysis": 2,
    # Other AI operations
    "quote_generation": 2,
    "test_generation": 2,
    "default": 2,  # Default cost for any AI operation
}


class PointsService:
    """Service for managing user points and transactions"""

    def __init__(self, mongodb_client: Optional[MongoClient] = None):
        """
        Initialize points service

        Args:
            mongodb_client: MongoDB client instance (optional)
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
        self.transactions = self.db["points_transactions"]
        self.subscriptions = self.db["user_subscriptions"]
        self.users = self.db["users"]

        # Create indexes
        self._ensure_indexes()

    def _ensure_indexes(self):
        """Create necessary indexes for performance"""
        try:
            # points_transactions indexes
            self.transactions.create_index(
                [("user_id", ASCENDING), ("created_at", DESCENDING)]
            )
            self.transactions.create_index([("subscription_id", ASCENDING)])
            self.transactions.create_index(
                [("service", ASCENDING), ("created_at", DESCENDING)]
            )
            self.transactions.create_index([("type", ASCENDING)])
            self.transactions.create_index([("created_at", DESCENDING)])

            logger.info("Points transaction indexes created successfully")
        except Exception as e:
            logger.error(f"Error creating indexes: {e}")

    @staticmethod
    def get_chat_points_cost(provider: str) -> int:
        """
        Get points cost for chat operation based on AI provider

        Args:
            provider: AI provider name (deepseek, claude, chatgpt, gemini, cerebras)

        Returns:
            Points cost (1 for deepseek, 2 for others)
        """
        provider_lower = provider.lower() if provider else "default"
        
        # Normalize provider name: remove _chat suffix if present
        # Example: deepseek_chat -> deepseek
        if provider_lower.endswith("_chat"):
            provider_lower = provider_lower.replace("_chat", "")
        
        service_key = f"ai_chat_{provider_lower}"

        # Return provider-specific cost or default to 2 points
        return SERVICE_POINTS_COST.get(
            service_key, SERVICE_POINTS_COST.get("ai_chat_default", 2)
        )

    async def get_points_balance(self, user_id: str) -> Dict[str, Any]:
        """
        Get current points balance for user

        Args:
            user_id: Firebase UID

        Returns:
            Dict with balance info
        """
        subscription = self.subscriptions.find_one({"user_id": user_id})

        if not subscription:
            return {
                "user_id": user_id,
                "points_total": 0,
                "points_used": 0,
                "points_remaining": 0,
                "plan": "free",
                "expires_at": None,
            }

        return {
            "user_id": user_id,
            "points_total": subscription.get("points_total", 0),
            "points_used": subscription.get("points_used", 0),
            "points_remaining": subscription.get("points_remaining", 0),
            "plan": subscription.get("plan"),
            "expires_at": subscription.get("expires_at"),
        }

    async def check_sufficient_points(
        self, user_id: str, points_needed: int, service: str = "default"
    ) -> Dict[str, Any]:
        """
        Check if user has enough points for operation

        Args:
            user_id: Firebase UID
            points_needed: Number of points required
            service: Service type (for logging)

        Returns:
            Dict with has_points bool and current balance
        """
        balance = await self.get_points_balance(user_id)

        has_points = balance["points_remaining"] >= points_needed

        return {
            "has_points": has_points,
            "points_needed": points_needed,
            "points_available": balance["points_remaining"],
            "points_deficit": max(0, points_needed - balance["points_remaining"]),
            "service": service,
        }

    async def deduct_points(
        self,
        user_id: str,
        amount: int,
        service: str,
        resource_id: Optional[str] = None,
        description: Optional[str] = None,
    ) -> PointsTransaction:
        """
        Deduct points from user balance

        Args:
            user_id: Firebase UID
            amount: Number of points to deduct
            service: Service type (ai_chat, document_generation, etc.)
            resource_id: ID of resource created (chat_id, document_id, etc.)
            description: Optional description

        Returns:
            PointsTransaction object

        Raises:
            InsufficientPointsError: If insufficient points
        """
        # Get current subscription
        subscription = self.subscriptions.find_one({"user_id": user_id})

        if not subscription:
            raise ValueError(f"No subscription found for user: {user_id}")

        current_points = subscription.get("points_remaining", 0)

        if current_points < amount:
            raise InsufficientPointsError(
                message=f"Không đủ điểm để thực hiện thao tác. Cần: {amount} điểm, Còn: {current_points} điểm",
                points_needed=amount,
                points_available=current_points,
                service=service,
            )

        # Calculate new balances
        balance_before = current_points
        balance_after = balance_before - amount
        points_used = subscription.get("points_used", 0) + amount

        # Create transaction record
        transaction = PointsTransaction(
            user_id=user_id,
            subscription_id=str(subscription["_id"]),
            type="spend",
            amount=amount,
            balance_before=balance_before,
            balance_after=balance_after,
            service=service,
            resource_id=resource_id,
            description=description or f"Used for {service}",
        )

        # Insert transaction
        result = self.transactions.insert_one(
            transaction.dict(by_alias=True, exclude={"id"})
        )
        transaction.id = result.inserted_id

        # Update subscription points
        self.subscriptions.update_one(
            {"_id": subscription["_id"]},
            {
                "$set": {
                    "points_remaining": balance_after,
                    "points_used": points_used,
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        # Update user document with unified points field
        self.users.update_one(
            {"firebase_uid": user_id},  # Use firebase_uid for unified schema
            {"$set": {"points": balance_after}},  # Update unified points field
        )

        logger.info(
            f"Deducted {amount} points from user: {user_id} for {service}. "
            f"Balance: {balance_before} → {balance_after}"
        )

        return transaction

    async def grant_points(self, request: PointsGrantRequest) -> PointsTransaction:
        """
        Grant points to user (admin only)

        Args:
            request: PointsGrantRequest with user_id, amount, reason

        Returns:
            PointsTransaction object
        """
        subscription = self.subscriptions.find_one({"user_id": request.user_id})

        if not subscription:
            raise ValueError(f"No subscription found for user: {request.user_id}")

        balance_before = subscription.get("points_remaining", 0)
        balance_after = balance_before + request.amount

        # Create transaction
        transaction = PointsTransaction(
            user_id=request.user_id,
            subscription_id=str(subscription["_id"]),
            type="grant",
            amount=request.amount,
            balance_before=balance_before,
            balance_after=balance_after,
            service="admin",
            description=request.reason,
            granted_by_admin=request.admin_id,
        )

        # Insert transaction
        result = self.transactions.insert_one(
            transaction.dict(by_alias=True, exclude={"id"})
        )
        transaction.id = result.inserted_id

        # Update subscription
        self.subscriptions.update_one(
            {"_id": subscription["_id"]},
            {
                "$set": {
                    "points_remaining": balance_after,
                    "points_total": subscription.get("points_total", 0)
                    + request.amount,
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        # Update user document with unified points field
        self.users.update_one(
            {"firebase_uid": request.user_id},  # Use firebase_uid for unified schema
            {"$set": {"points": balance_after}},  # Update unified points field
        )

        logger.info(
            f"Granted {request.amount} points to user: {request.user_id} by admin: {request.admin_id}. "
            f"Reason: {request.reason}. Balance: {balance_before} → {balance_after}"
        )

        return transaction

    async def deduct_points_admin(
        self, request: PointsDeductRequest
    ) -> PointsTransaction:
        """
        Manually deduct points from user (admin only)

        Args:
            request: PointsDeductRequest with user_id, amount, reason

        Returns:
            PointsTransaction object

        Raises:
            InsufficientPointsError: If insufficient points
        """
        subscription = self.subscriptions.find_one({"user_id": request.user_id})

        if not subscription:
            raise ValueError(f"No subscription found for user: {request.user_id}")

        balance_before = subscription.get("points_remaining", 0)

        if balance_before < request.amount:
            raise InsufficientPointsError(
                message=f"Không đủ điểm để trừ. Cần: {request.amount} điểm, Còn: {balance_before} điểm",
                points_needed=request.amount,
                points_available=balance_before,
                service=f"admin_deduct_{request.user_id}",
            )

        balance_after = balance_before - request.amount
        points_used = subscription.get("points_used", 0) + request.amount

        # Create transaction
        transaction = PointsTransaction(
            user_id=request.user_id,
            subscription_id=str(subscription["_id"]),
            type="deduct",
            amount=request.amount,
            balance_before=balance_before,
            balance_after=balance_after,
            service="admin",
            description=request.reason,
            granted_by_admin=request.admin_id,
        )

        # Insert transaction
        result = self.transactions.insert_one(
            transaction.dict(by_alias=True, exclude={"id"})
        )
        transaction.id = result.inserted_id

        # Update subscription
        self.subscriptions.update_one(
            {"_id": subscription["_id"]},
            {
                "$set": {
                    "points_remaining": balance_after,
                    "points_used": points_used,
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        # Update user document with unified points field
        self.users.update_one(
            {"firebase_uid": request.user_id},  # Use firebase_uid for unified schema
            {"$set": {"points": balance_after}},  # Update unified points field
        )

        logger.info(
            f"Deducted {request.amount} points from user: {request.user_id} by admin: {request.admin_id}. "
            f"Reason: {request.reason}. Balance: {balance_before} → {balance_after}"
        )

        return transaction

    async def refund_points(
        self,
        user_id: str,
        amount: int,
        reason: str,
        original_transaction_id: Optional[str] = None,
    ) -> PointsTransaction:
        """
        Refund points to user

        Args:
            user_id: Firebase UID
            amount: Number of points to refund
            reason: Refund reason
            original_transaction_id: ID of original transaction being refunded

        Returns:
            PointsTransaction object
        """
        subscription = self.subscriptions.find_one({"user_id": user_id})

        if not subscription:
            raise ValueError(f"No subscription found for user: {user_id}")

        balance_before = subscription.get("points_remaining", 0)
        balance_after = balance_before + amount
        points_used = max(0, subscription.get("points_used", 0) - amount)

        # Create transaction
        transaction = PointsTransaction(
            user_id=user_id,
            subscription_id=str(subscription["_id"]),
            type="refund",
            amount=amount,
            balance_before=balance_before,
            balance_after=balance_after,
            service="refund",
            resource_id=original_transaction_id,
            description=reason,
        )

        # Insert transaction
        result = self.transactions.insert_one(
            transaction.dict(by_alias=True, exclude={"id"})
        )
        transaction.id = result.inserted_id

        # Update subscription
        self.subscriptions.update_one(
            {"_id": subscription["_id"]},
            {
                "$set": {
                    "points_remaining": balance_after,
                    "points_used": points_used,
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        # Update user document with unified points field
        self.users.update_one(
            {"firebase_uid": user_id},  # Use firebase_uid for unified schema
            {"$set": {"points": balance_after}},  # Update unified points field
        )

        logger.info(
            f"Refunded {amount} points to user: {user_id}. "
            f"Reason: {reason}. Balance: {balance_before} → {balance_after}"
        )

        return transaction

    async def get_transaction_history(
        self,
        user_id: str,
        transaction_type: Optional[TransactionType] = None,
        service: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Get user's points transaction history

        Args:
            user_id: Firebase UID
            transaction_type: Filter by type (spend, earn, grant, etc.)
            service: Filter by service
            start_date: Filter transactions after this date
            end_date: Filter transactions before this date
            page: Page number (1-indexed)
            limit: Items per page

        Returns:
            Dict with transactions, total, page info
        """
        query = {"user_id": user_id}

        if transaction_type:
            query["type"] = transaction_type

        if service:
            query["service"] = service

        if start_date or end_date:
            query["created_at"] = {}
            if start_date:
                query["created_at"]["$gte"] = start_date
            if end_date:
                query["created_at"]["$lte"] = end_date

        total = self.transactions.count_documents(query)
        skip = (page - 1) * limit

        transactions = list(
            self.transactions.find(query)
            .sort("created_at", DESCENDING)
            .skip(skip)
            .limit(limit)
        )

        return {
            "transactions": transactions,
            "total": total,
            "page": page,
            "pages": (total + limit - 1) // limit,
            "limit": limit,
        }

    async def get_points_cost_for_service(self, service: str) -> int:
        """
        Get points cost for a service type

        Args:
            service: Service type

        Returns:
            Points cost (default 2)
        """
        return SERVICE_POINTS_COST.get(service, SERVICE_POINTS_COST["default"])

    async def get_usage_summary(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get usage summary by service type

        Args:
            user_id: Firebase UID
            start_date: Start date for summary
            end_date: End date for summary

        Returns:
            Dict with usage breakdown by service
        """
        query = {"user_id": user_id, "type": "spend"}

        if start_date or end_date:
            query["created_at"] = {}
            if start_date:
                query["created_at"]["$gte"] = start_date
            if end_date:
                query["created_at"]["$lte"] = end_date

        # Aggregate by service
        pipeline = [
            {"$match": query},
            {
                "$group": {
                    "_id": "$service",
                    "total_points": {"$sum": "$amount"},
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"total_points": -1}},
        ]

        results = list(self.transactions.aggregate(pipeline))

        total_points = sum(r["total_points"] for r in results)

        return {
            "user_id": user_id,
            "period_start": start_date,
            "period_end": end_date,
            "total_points_spent": total_points,
            "breakdown_by_service": [
                {
                    "service": r["_id"],
                    "points": r["total_points"],
                    "operations": r["count"],
                    "percentage": (
                        round((r["total_points"] / total_points * 100), 2)
                        if total_points > 0
                        else 0
                    ),
                }
                for r in results
            ],
        }

    async def get_all_transactions(
        self,
        transaction_type: Optional[TransactionType] = None,
        service: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Get all points transactions (admin only)

        Args:
            transaction_type: Filter by type
            service: Filter by service
            start_date: Filter after date
            end_date: Filter before date
            page: Page number
            limit: Items per page

        Returns:
            Dict with transactions, total, page info
        """
        query = {}

        if transaction_type:
            query["type"] = transaction_type

        if service:
            query["service"] = service

        if start_date or end_date:
            query["created_at"] = {}
            if start_date:
                query["created_at"]["$gte"] = start_date
            if end_date:
                query["created_at"]["$lte"] = end_date

        total = self.transactions.count_documents(query)
        skip = (page - 1) * limit

        transactions = list(
            self.transactions.find(query)
            .sort("created_at", DESCENDING)
            .skip(skip)
            .limit(limit)
        )

        # Enrich with user data
        for txn in transactions:
            user = self.users.find_one({"uid": txn["user_id"]})
            if user:
                txn["user_email"] = user.get("email")
                txn["user_name"] = user.get("name") or user.get("display_name")

        return {
            "transactions": transactions,
            "total": total,
            "page": page,
            "pages": (total + limit - 1) // limit,
            "limit": limit,
        }


# Global service instance helper
def get_points_service() -> PointsService:
    """Get or create global points service instance"""
    return PointsService()
