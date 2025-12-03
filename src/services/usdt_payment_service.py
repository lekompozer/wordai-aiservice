"""
USDT Payment Database Service

Service class for managing USDT BEP20 payments:
- Payment CRUD operations
- Transaction tracking
- Status updates
- Wallet management
"""

import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pymongo import MongoClient, ASCENDING, DESCENDING
from bson import ObjectId

from src.utils.logger import setup_logger
from src.models.usdt_payment import (
    USDTPayment,
    USDTPendingTransaction,
    USDTWalletAddress,
    PaymentStatus,
    PaymentType,
)

logger = setup_logger()


class USDTPaymentService:
    """Service for USDT payment operations"""

    def __init__(self, mongodb_client: Optional[MongoClient] = None):
        """
        Initialize USDT payment service

        Args:
            mongodb_client: Optional MongoDB client. If not provided, creates new connection.
        """
        if mongodb_client:
            self.client = mongodb_client
            db_name = os.getenv("MONGODB_NAME", "wordai_db")
            self.db = self.client[db_name]
        else:
            # Create new connection
            mongo_uri = os.getenv("MONGODB_URI_AUTH")
            if not mongo_uri:
                mongo_user = os.getenv("MONGODB_APP_USERNAME")
                mongo_pass = os.getenv("MONGODB_APP_PASSWORD")
                mongo_host = os.getenv("MONGODB_HOST", "localhost:27017")
                db_name = os.getenv("MONGODB_NAME", "wordai_db")

                if mongo_user and mongo_pass:
                    mongodb_uri = f"mongodb://{mongo_user}:{mongo_pass}@{mongo_host}/{db_name}?authSource=admin"
                else:
                    mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
            else:
                mongodb_uri = mongo_uri
                db_name = os.getenv("MONGODB_NAME", "wordai_db")

            self.client = MongoClient(mongodb_uri)
            self.db = self.client[db_name]

        # Collections
        self.payments = self.db.usdt_payments
        self.pending = self.db.usdt_pending_transactions
        self.wallets = self.db.usdt_wallet_addresses

        logger.info("✅ USDTPaymentService initialized")

    # =========================================================================
    # PAYMENT CRUD OPERATIONS
    # =========================================================================

    def create_payment(
        self,
        user_id: str,
        payment_type: PaymentType,
        amount_usdt: float,
        amount_vnd: int,
        usdt_rate: float,
        to_address: str,
        plan: Optional[str] = None,
        duration: Optional[str] = None,
        points_amount: Optional[int] = None,
        from_address: Optional[str] = None,
        user_email: Optional[str] = None,
        user_name: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create new USDT payment request

        Args:
            user_id: Firebase UID
            payment_type: "subscription" or "points"
            amount_usdt: Amount in USDT
            amount_vnd: Amount in VND (reference)
            usdt_rate: Exchange rate
            to_address: WordAI wallet address
            plan: Subscription plan (if type=subscription)
            duration: Subscription duration (if type=subscription)
            points_amount: Points to purchase (if type=points)
            from_address: User's wallet address (optional)
            user_email: User email
            user_name: User name
            ip_address: Request IP
            user_agent: User agent

        Returns:
            Created payment document
        """
        try:
            # Generate unique IDs
            timestamp = int(datetime.utcnow().timestamp())
            user_short = user_id[:8]

            payment_id = f"USDT-{timestamp}-{user_short}"
            order_invoice = f"WA-USDT-{timestamp}-{user_short}"

            # Expiration time (30 minutes)
            expires_at = datetime.utcnow() + timedelta(minutes=30)

            # Create payment document
            payment_data = {
                "payment_id": payment_id,
                "order_invoice_number": order_invoice,
                "user_id": user_id,
                "user_email": user_email,
                "user_name": user_name,
                "payment_type": payment_type,
                "plan": plan,
                "duration": duration,
                "points_amount": points_amount,
                "amount_usdt": amount_usdt,
                "amount_vnd": amount_vnd,
                "usdt_rate": usdt_rate,
                "from_address": from_address,
                "to_address": to_address,
                "status": "pending",
                "confirmation_count": 0,
                "required_confirmations": 12,
                "created_at": datetime.utcnow(),
                "expires_at": expires_at,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "manually_processed": False,
            }

            result = self.payments.insert_one(payment_data)
            payment_data["_id"] = result.inserted_id

            logger.info(f"✅ Created USDT payment: {payment_id} for user {user_id}")

            return payment_data

        except Exception as e:
            logger.error(f"❌ Failed to create payment: {e}")
            raise

    def get_payment_by_id(self, payment_id: str) -> Optional[Dict[str, Any]]:
        """Get payment by payment_id"""
        try:
            return self.payments.find_one({"payment_id": payment_id})
        except Exception as e:
            logger.error(f"❌ Failed to get payment {payment_id}: {e}")
            return None

    def get_payment_by_invoice(self, order_invoice: str) -> Optional[Dict[str, Any]]:
        """Get payment by order invoice number"""
        try:
            return self.payments.find_one({"order_invoice_number": order_invoice})
        except Exception as e:
            logger.error(f"❌ Failed to get payment by invoice {order_invoice}: {e}")
            return None

    def get_payment_by_tx_hash(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        """Get payment by transaction hash"""
        try:
            return self.payments.find_one({"transaction_hash": tx_hash})
        except Exception as e:
            logger.error(f"❌ Failed to get payment by tx_hash {tx_hash}: {e}")
            return None

    def get_user_payments(
        self,
        user_id: str,
        payment_type: Optional[PaymentType] = None,
        status: Optional[PaymentStatus] = None,
        limit: int = 20,
        skip: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get user's payment history

        Args:
            user_id: Firebase UID
            payment_type: Filter by type (optional)
            status: Filter by status (optional)
            limit: Max results
            skip: Skip results (pagination)

        Returns:
            List of payment documents
        """
        try:
            query = {"user_id": user_id}

            if payment_type:
                query["payment_type"] = payment_type
            if status:
                query["status"] = status

            payments = (
                self.payments.find(query)
                .sort("created_at", DESCENDING)
                .limit(limit)
                .skip(skip)
            )

            return list(payments)

        except Exception as e:
            logger.error(f"❌ Failed to get user payments for {user_id}: {e}")
            return []

    def update_payment_status(
        self,
        payment_id: str,
        status: PaymentStatus,
        transaction_hash: Optional[str] = None,
        block_number: Optional[int] = None,
        confirmation_count: Optional[int] = None,
        from_address: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """
        Update payment status

        Args:
            payment_id: Payment ID
            status: New status
            transaction_hash: BSC transaction hash
            block_number: Block number
            confirmation_count: Number of confirmations
            from_address: Sender wallet address
            error_message: Error message if failed

        Returns:
            Success status
        """
        try:
            update_data = {"status": status}

            if transaction_hash:
                update_data["transaction_hash"] = transaction_hash
            if block_number is not None:
                update_data["block_number"] = block_number
            if confirmation_count is not None:
                update_data["confirmation_count"] = confirmation_count
            if from_address:
                update_data["from_address"] = from_address
            if error_message:
                update_data["error_message"] = error_message

            # Update timestamps based on status
            if status == "processing":
                update_data["payment_received_at"] = datetime.utcnow()
            elif status == "confirmed":
                update_data["confirmed_at"] = datetime.utcnow()
            elif status == "completed":
                if not self.get_payment_by_id(payment_id).get("confirmed_at"):
                    update_data["confirmed_at"] = datetime.utcnow()
                update_data["completed_at"] = datetime.utcnow()
            elif status == "cancelled":
                update_data["cancelled_at"] = datetime.utcnow()

            result = self.payments.update_one(
                {"payment_id": payment_id}, {"$set": update_data}
            )

            if result.modified_count > 0:
                logger.info(f"✅ Updated payment {payment_id} status to {status}")
                return True
            else:
                logger.warning(f"⚠️ No changes made to payment {payment_id}")
                return False

        except Exception as e:
            logger.error(f"❌ Failed to update payment status: {e}")
            return False

    def link_subscription(self, payment_id: str, subscription_id: str) -> bool:
        """Link payment to subscription after activation"""
        try:
            result = self.payments.update_one(
                {"payment_id": payment_id},
                {"$set": {"subscription_id": subscription_id}},
            )

            if result.modified_count > 0:
                logger.info(
                    f"✅ Linked payment {payment_id} to subscription {subscription_id}"
                )
                return True
            return False

        except Exception as e:
            logger.error(f"❌ Failed to link subscription: {e}")
            return False

    def link_points_transaction(self, payment_id: str, transaction_id: str) -> bool:
        """Link payment to points transaction"""
        try:
            result = self.payments.update_one(
                {"payment_id": payment_id},
                {"$set": {"points_transaction_id": transaction_id}},
            )

            if result.modified_count > 0:
                logger.info(
                    f"✅ Linked payment {payment_id} to points transaction {transaction_id}"
                )
                return True
            return False

        except Exception as e:
            logger.error(f"❌ Failed to link points transaction: {e}")
            return False

    # =========================================================================
    # PENDING TRANSACTION TRACKING
    # =========================================================================

    def add_pending_transaction(
        self,
        payment_id: str,
        user_id: str,
        transaction_hash: str,
        from_address: str,
        to_address: str,
        amount_usdt: float,
        required_confirmations: int = 12,
    ) -> bool:
        """
        Add transaction to pending queue for confirmation tracking

        Args:
            payment_id: Payment ID
            user_id: User ID
            transaction_hash: BSC transaction hash
            from_address: Sender address
            to_address: Recipient address
            amount_usdt: Amount in USDT
            required_confirmations: Required confirmations

        Returns:
            Success status
        """
        try:
            pending_data = {
                "payment_id": payment_id,
                "user_id": user_id,
                "transaction_hash": transaction_hash,
                "from_address": from_address,
                "to_address": to_address,
                "amount_usdt": amount_usdt,
                "first_seen_at": datetime.utcnow(),
                "last_checked_at": datetime.utcnow(),
                "confirmation_count": 0,
                "required_confirmations": required_confirmations,
                "status": "pending",
                "webhook_attempts": 0,
            }

            self.pending.insert_one(pending_data)
            logger.info(f"✅ Added pending transaction: {transaction_hash}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to add pending transaction: {e}")
            return False

    def get_pending_transactions(
        self,
        status: str = "pending",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get pending transactions that need confirmation checking"""
        try:
            query = {"status": status}

            transactions = (
                self.pending.find(query).sort("last_checked_at", ASCENDING).limit(limit)
            )

            return list(transactions)

        except Exception as e:
            logger.error(f"❌ Failed to get pending transactions: {e}")
            return []

    def update_pending_transaction(
        self,
        transaction_hash: str,
        confirmation_count: int,
        status: Optional[str] = None,
    ) -> bool:
        """Update pending transaction confirmation count"""
        try:
            update_data = {
                "confirmation_count": confirmation_count,
                "last_checked_at": datetime.utcnow(),
            }

            if status:
                update_data["status"] = status

            result = self.pending.update_one(
                {"transaction_hash": transaction_hash}, {"$set": update_data}
            )

            return result.modified_count > 0

        except Exception as e:
            logger.error(f"❌ Failed to update pending transaction: {e}")
            return False

    def remove_pending_transaction(self, transaction_hash: str) -> bool:
        """Remove transaction from pending queue"""
        try:
            result = self.pending.delete_one({"transaction_hash": transaction_hash})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"❌ Failed to remove pending transaction: {e}")
            return False

    # =========================================================================
    # WALLET MANAGEMENT
    # =========================================================================

    def register_wallet(
        self,
        user_id: str,
        wallet_address: str,
        label: Optional[str] = None,
    ) -> bool:
        """Register user's wallet address"""
        try:
            wallet_data = {
                "user_id": user_id,
                "wallet_address": wallet_address.lower(),
                "is_verified": False,
                "first_used_at": datetime.utcnow(),
                "last_used_at": datetime.utcnow(),
                "payment_count": 0,
                "total_amount_usdt": 0.0,
                "label": label,
            }

            self.wallets.update_one(
                {"user_id": user_id, "wallet_address": wallet_address.lower()},
                {"$setOnInsert": wallet_data},
                upsert=True,
            )

            logger.info(f"✅ Registered wallet {wallet_address} for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to register wallet: {e}")
            return False

    def update_wallet_usage(
        self,
        user_id: str,
        wallet_address: str,
        amount_usdt: float,
    ) -> bool:
        """Update wallet usage stats after successful payment"""
        try:
            result = self.wallets.update_one(
                {"user_id": user_id, "wallet_address": wallet_address.lower()},
                {
                    "$set": {"last_used_at": datetime.utcnow()},
                    "$inc": {"payment_count": 1, "total_amount_usdt": amount_usdt},
                },
            )

            return result.modified_count > 0

        except Exception as e:
            logger.error(f"❌ Failed to update wallet usage: {e}")
            return False

    def get_user_wallets(self, user_id: str) -> List[Dict[str, Any]]:
        """Get user's registered wallet addresses"""
        try:
            wallets = self.wallets.find({"user_id": user_id}).sort(
                "last_used_at", DESCENDING
            )
            return list(wallets)
        except Exception as e:
            logger.error(f"❌ Failed to get user wallets: {e}")
            return []

    # =========================================================================
    # ADMIN OPERATIONS
    # =========================================================================

    def get_all_payments(
        self,
        status: Optional[PaymentStatus] = None,
        payment_type: Optional[PaymentType] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get all payments (admin)"""
        try:
            query = {}

            if status:
                query["status"] = status
            if payment_type:
                query["payment_type"] = payment_type

            payments = (
                self.payments.find(query)
                .sort("created_at", DESCENDING)
                .limit(limit)
                .skip(skip)
            )

            return list(payments)

        except Exception as e:
            logger.error(f"❌ Failed to get all payments: {e}")
            return []

    def manual_confirm_payment(
        self,
        payment_id: str,
        admin_user_id: str,
        admin_notes: Optional[str] = None,
    ) -> bool:
        """Manually confirm payment (admin action)"""
        try:
            update_data = {
                "status": "completed",
                "manually_processed": True,
                "processed_by_admin": admin_user_id,
                "admin_notes": admin_notes,
                "confirmed_at": datetime.utcnow(),
                "completed_at": datetime.utcnow(),
            }

            result = self.payments.update_one(
                {"payment_id": payment_id}, {"$set": update_data}
            )

            if result.modified_count > 0:
                logger.info(
                    f"✅ Admin {admin_user_id} manually confirmed payment {payment_id}"
                )
                return True
            return False

        except Exception as e:
            logger.error(f"❌ Failed to manually confirm payment: {e}")
            return False

    def get_payment_stats(self) -> Dict[str, Any]:
        """Get payment statistics (admin)"""
        try:
            total = self.payments.count_documents({})
            pending = self.payments.count_documents({"status": "pending"})
            processing = self.payments.count_documents({"status": "processing"})
            completed = self.payments.count_documents({"status": "completed"})
            failed = self.payments.count_documents({"status": "failed"})

            # Total USDT processed
            pipeline = [
                {"$match": {"status": "completed"}},
                {"$group": {"_id": None, "total_usdt": {"$sum": "$amount_usdt"}}},
            ]
            result = list(self.payments.aggregate(pipeline))
            total_usdt = result[0]["total_usdt"] if result else 0.0

            return {
                "total_payments": total,
                "pending": pending,
                "processing": processing,
                "completed": completed,
                "failed": failed,
                "total_usdt_processed": total_usdt,
            }

        except Exception as e:
            logger.error(f"❌ Failed to get payment stats: {e}")
            return {}

    def close(self):
        """Close database connection"""
        if self.client:
            self.client.close()
            logger.info("✅ USDTPaymentService connection closed")
