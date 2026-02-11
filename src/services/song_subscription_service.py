"""
Song Learning Subscription Service
Handles subscription CRUD operations
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pymongo.database import Database

from src.utils.logger import setup_logger

logger = setup_logger()


class SongSubscriptionService:
    """Service for managing song learning subscriptions"""

    def __init__(self, db: Database):
        self.db = db
        self.subscriptions = db["user_song_subscription"]
        logger.info("✅ SongSubscriptionService initialized")

    async def get_subscription(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user's active subscription"""
        subscription = self.subscriptions.find_one(
            {"user_id": user_id, "status": "active", "end_date": {"$gt": datetime.utcnow()}}
        )
        return subscription

    async def is_premium(self, user_id: str) -> bool:
        """Check if user has active premium subscription"""
        subscription = await self.get_subscription(user_id)
        return subscription is not None

    async def create_subscription(
        self,
        user_id: str,
        plan_type: str,
        price_paid: int,
        duration_months: int,
        payment_method: str = "momo",
        payment_id: Optional[str] = None,
        order_invoice_number: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create new subscription after successful payment"""
        
        start_date = datetime.utcnow()
        end_date = start_date + timedelta(days=30 * duration_months)

        subscription_data = {
            "user_id": user_id,
            "plan_type": plan_type,
            "status": "active",
            "start_date": start_date,
            "end_date": end_date,
            "created_at": start_date,
            "updated_at": start_date,
            "cancelled_at": None,
            "price_paid": price_paid,
            "payment_method": payment_method,
            "payment_id": payment_id,
            "order_invoice_number": order_invoice_number,
            "auto_renew": False,
            "source": "web",
        }

        # Cancel any existing active subscriptions (extend instead)
        existing = await self.get_subscription(user_id)
        if existing:
            logger.info(f"🔄 Extending existing subscription for user {user_id}")
            # Extend from current end_date
            new_end_date = existing["end_date"] + timedelta(days=30 * duration_months)
            
            self.subscriptions.update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {
                        "end_date": new_end_date,
                        "updated_at": datetime.utcnow(),
                        "price_paid": existing["price_paid"] + price_paid,
                    }
                },
            )
            
            existing["end_date"] = new_end_date
            return existing

        # Create new subscription
        result = self.subscriptions.insert_one(subscription_data)
        subscription_data["_id"] = result.inserted_id

        logger.info(
            f"✅ Subscription created for user {user_id}: {plan_type} until {end_date}"
        )

        return subscription_data

    async def cancel_subscription(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Cancel subscription (keeps access until end_date)"""
        
        subscription = await self.get_subscription(user_id)
        if not subscription:
            return None

        self.subscriptions.update_one(
            {"_id": subscription["_id"]},
            {
                "$set": {
                    "status": "cancelled",
                    "cancelled_at": datetime.utcnow(),
                    "auto_renew": False,
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        logger.info(
            f"✅ Subscription cancelled for user {user_id}, access until {subscription['end_date']}"
        )

        subscription["status"] = "cancelled"
        subscription["cancelled_at"] = datetime.utcnow()
        return subscription

    async def check_and_expire_subscriptions(self):
        """Cron job: Mark expired subscriptions as expired"""
        
        result = self.subscriptions.update_many(
            {"status": "active", "end_date": {"$lt": datetime.utcnow()}},
            {"$set": {"status": "expired", "updated_at": datetime.utcnow()}},
        )

        if result.modified_count > 0:
            logger.info(f"✅ Expired {result.modified_count} subscriptions")

        return result.modified_count


# Singleton instance
_subscription_service: Optional[SongSubscriptionService] = None


def get_song_subscription_service(db: Database) -> SongSubscriptionService:
    """Get or create SongSubscriptionService instance"""
    global _subscription_service
    if _subscription_service is None:
        _subscription_service = SongSubscriptionService(db)
    return _subscription_service
