"""
USDT Payment Verification Background Job

Background service to automatically verify and confirm pending USDT payments:
- Checks pending transactions every 30 seconds
- Verifies blockchain confirmations
- Auto-activates subscriptions/credits points after 12 confirmations
- Handles failed transactions and retries
"""

import asyncio
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any
from pymongo import MongoClient

from src.services.usdt_payment_service import USDTPaymentService
from src.services.bsc_service import get_bsc_service
from src.services.subscription_service import SubscriptionService
from src.services.points_service import PointsService
from src.models.subscription import CreateSubscriptionRequest
from src.utils.logger import setup_logger

logger = setup_logger()


class USDTPaymentVerificationJob:
    """Background job for verifying USDT payments"""

    def __init__(
        self,
        check_interval: int = 30,  # Check every 30 seconds
        max_retries: int = 20,  # Max retry attempts
        required_confirmations: int = 12,
    ):
        """
        Initialize verification job
        
        Args:
            check_interval: Seconds between checks
            max_retries: Maximum retry attempts before marking as failed
            required_confirmations: Required blockchain confirmations
        """
        self.check_interval = check_interval
        self.max_retries = max_retries
        self.required_confirmations = required_confirmations
        
        # Services
        self.payment_service = USDTPaymentService()
        self.bsc_service = get_bsc_service()
        self.subscription_service = SubscriptionService()
        self.points_service = PointsService()
        
        # Job state
        self.is_running = False
        self.last_check = None
        
        logger.info(f"🔧 USDTPaymentVerificationJob initialized (interval: {check_interval}s)")

    async def start(self):
        """Start the background job"""
        if self.is_running:
            logger.warning("⚠️ Verification job already running")
            return
        
        self.is_running = True
        logger.info("🚀 Starting USDT payment verification job...")
        
        try:
            while self.is_running:
                await self.check_pending_payments()
                await asyncio.sleep(self.check_interval)
        except Exception as e:
            logger.error(f"❌ Verification job crashed: {e}")
            self.is_running = False

    def stop(self):
        """Stop the background job"""
        logger.info("🛑 Stopping USDT payment verification job...")
        self.is_running = False

    async def check_pending_payments(self):
        """Check all pending transactions"""
        try:
            self.last_check = datetime.utcnow()
            
            # Get pending transactions
            pending = self.payment_service.get_pending_transactions(
                status="pending",
                limit=100
            )
            
            if not pending:
                logger.debug("✅ No pending transactions to check")
                return
            
            logger.info(f"🔍 Checking {len(pending)} pending transactions...")
            
            for pending_tx in pending:
                await self.verify_transaction(pending_tx)
            
        except Exception as e:
            logger.error(f"❌ Error checking pending payments: {e}")

    async def verify_transaction(self, pending_tx: Dict[str, Any]):
        """
        Verify a single pending transaction
        
        Args:
            pending_tx: Pending transaction document
        """
        try:
            tx_hash = pending_tx["transaction_hash"]
            payment_id = pending_tx["payment_id"]
            
            logger.info(f"🔍 Verifying transaction: {tx_hash} (payment: {payment_id})")
            
            # Get payment
            payment = self.payment_service.get_payment_by_id(payment_id)
            
            if not payment:
                logger.error(f"❌ Payment not found: {payment_id}")
                self.payment_service.remove_pending_transaction(tx_hash)
                return
            
            # Check if payment already completed
            if payment["status"] == "completed":
                logger.info(f"✅ Payment already completed: {payment_id}")
                self.payment_service.remove_pending_transaction(tx_hash)
                return
            
            # Get blockchain confirmations
            confirmations = self.bsc_service.get_transaction_confirmations(tx_hash)
            
            if confirmations < 0:
                # Error getting confirmations
                logger.error(f"❌ Error getting confirmations for {tx_hash}")
                await self.handle_verification_error(pending_tx, payment)
                return
            
            if confirmations == 0:
                # Not mined yet
                logger.info(f"⏳ Transaction not mined yet: {tx_hash}")
                await self.handle_not_mined(pending_tx, payment)
                return
            
            # Update confirmation count
            self.payment_service.update_pending_transaction(
                tx_hash,
                confirmation_count=confirmations
            )
            
            logger.info(f"📊 Confirmations: {confirmations}/{self.required_confirmations}")
            
            # Check if transaction is successful
            is_success, error_msg = self.bsc_service.is_transaction_successful(tx_hash)
            
            if not is_success:
                logger.error(f"❌ Transaction failed: {error_msg}")
                await self.handle_failed_transaction(pending_tx, payment, error_msg)
                return
            
            # Verify USDT transfer
            is_valid, message, details = self.bsc_service.verify_usdt_transfer(
                tx_hash=tx_hash,
                expected_recipient=payment["to_address"],
                expected_amount_usdt=payment["amount_usdt"],
                tolerance=0.01
            )
            
            if not is_valid:
                logger.error(f"❌ USDT transfer verification failed: {message}")
                await self.handle_invalid_transfer(pending_tx, payment, message)
                return
            
            # Update payment with blockchain details
            self.payment_service.update_payment_status(
                payment_id=payment_id,
                status="processing",
                transaction_hash=tx_hash,
                block_number=details.get("block_number"),
                confirmation_count=confirmations,
                from_address=details.get("from_address"),
            )
            
            # Check if we have enough confirmations
            if confirmations >= self.required_confirmations:
                logger.info(f"✅ Transaction confirmed! ({confirmations} confirmations)")
                await self.handle_confirmed_payment(pending_tx, payment, details)
            else:
                logger.info(f"⏳ Waiting for more confirmations: {confirmations}/{self.required_confirmations}")
            
        except Exception as e:
            logger.error(f"❌ Error verifying transaction {pending_tx.get('transaction_hash')}: {e}")

    async def handle_confirmed_payment(
        self,
        pending_tx: Dict[str, Any],
        payment: Dict[str, Any],
        details: Dict[str, Any]
    ):
        """
        Handle confirmed payment - activate subscription or credit points
        
        Args:
            pending_tx: Pending transaction document
            payment: Payment document
            details: Transaction details from blockchain
        """
        try:
            payment_id = payment["payment_id"]
            payment_type = payment["payment_type"]
            
            logger.info(f"🎉 Processing confirmed payment: {payment_id} (type: {payment_type})")
            
            # Update payment status to confirmed
            self.payment_service.update_payment_status(
                payment_id=payment_id,
                status="confirmed",
                confirmation_count=details.get("confirmations", 12),
            )
            
            # Process based on payment type
            if payment_type == "subscription":
                await self.activate_subscription(payment)
            elif payment_type == "points":
                await self.credit_points(payment)
            else:
                logger.error(f"❌ Unknown payment type: {payment_type}")
                return
            
            # Update payment to completed
            self.payment_service.update_payment_status(
                payment_id=payment_id,
                status="completed"
            )
            
            # Update wallet usage
            if payment.get("from_address"):
                self.payment_service.update_wallet_usage(
                    user_id=payment["user_id"],
                    wallet_address=payment["from_address"],
                    amount_usdt=payment["amount_usdt"]
                )
            
            # Remove from pending queue
            self.payment_service.remove_pending_transaction(pending_tx["transaction_hash"])
            
            logger.info(f"✅ Payment completed successfully: {payment_id}")
            
        except Exception as e:
            logger.error(f"❌ Error processing confirmed payment: {e}")

    async def activate_subscription(self, payment: Dict[str, Any]):
        """
        Activate subscription after payment confirmation
        
        Args:
            payment: Payment document
        """
        try:
            logger.info(f"🎫 Activating subscription for payment: {payment['payment_id']}")
            
            # Check if already activated
            if payment.get("subscription_id"):
                logger.info(f"✅ Subscription already activated: {payment['subscription_id']}")
                return
            
            # Create subscription
            sub_request = CreateSubscriptionRequest(
                user_id=payment["user_id"],
                plan=payment["plan"],
                duration=payment["duration"],
                payment_id=payment["payment_id"],
                payment_method="USDT_BEP20",
            )
            
            subscription = await self.subscription_service.create_paid_subscription(sub_request)
            subscription_id = str(subscription.id)
            
            # Link payment to subscription
            self.payment_service.link_subscription(payment["payment_id"], subscription_id)
            
            logger.info(f"✅ Subscription activated: {subscription_id}")
            
        except Exception as e:
            logger.error(f"❌ Error activating subscription: {e}")
            raise

    async def credit_points(self, payment: Dict[str, Any]):
        """
        Credit points after payment confirmation
        
        Args:
            payment: Payment document
        """
        try:
            logger.info(f"💎 Crediting points for payment: {payment['payment_id']}")
            
            # Check if already credited
            if payment.get("points_transaction_id"):
                logger.info(f"✅ Points already credited: {payment['points_transaction_id']}")
                return
            
            # Add points
            transaction_id = self.points_service.add_points(
                user_id=payment["user_id"],
                amount=payment["points_amount"],
                transaction_type="purchase",
                description=f"Points purchase via USDT: {payment['payment_id']}",
                metadata={
                    "payment_id": payment["payment_id"],
                    "payment_method": "USDT_BEP20",
                    "amount_usdt": payment["amount_usdt"],
                    "amount_vnd": payment["amount_vnd"],
                    "transaction_hash": payment.get("transaction_hash"),
                }
            )
            
            # Link payment to transaction
            self.payment_service.link_points_transaction(payment["payment_id"], transaction_id)
            
            logger.info(f"✅ Points credited: {payment['points_amount']} points (txn: {transaction_id})")
            
        except Exception as e:
            logger.error(f"❌ Error crediting points: {e}")
            raise

    async def handle_not_mined(self, pending_tx: Dict[str, Any], payment: Dict[str, Any]):
        """Handle transaction that hasn't been mined yet"""
        
        # Check if payment expired
        if payment.get("expires_at") and payment["expires_at"] < datetime.utcnow():
            logger.warning(f"⏰ Payment expired: {payment['payment_id']}")
            
            self.payment_service.update_payment_status(
                payment_id=payment["payment_id"],
                status="cancelled",
                error_message="Payment expired - transaction not mined"
            )
            
            self.payment_service.remove_pending_transaction(pending_tx["transaction_hash"])
        else:
            # Increment webhook attempts
            attempts = pending_tx.get("webhook_attempts", 0) + 1
            
            if attempts >= self.max_retries:
                logger.error(f"❌ Max retries reached for {pending_tx['transaction_hash']}")
                
                self.payment_service.update_payment_status(
                    payment_id=payment["payment_id"],
                    status="failed",
                    error_message="Transaction not mined after maximum retries"
                )
                
                self.payment_service.remove_pending_transaction(pending_tx["transaction_hash"])

    async def handle_failed_transaction(
        self,
        pending_tx: Dict[str, Any],
        payment: Dict[str, Any],
        error_msg: str
    ):
        """Handle failed blockchain transaction"""
        
        logger.error(f"❌ Transaction failed: {pending_tx['transaction_hash']} - {error_msg}")
        
        self.payment_service.update_payment_status(
            payment_id=payment["payment_id"],
            status="failed",
            error_message=f"Blockchain transaction failed: {error_msg}"
        )
        
        self.payment_service.remove_pending_transaction(pending_tx["transaction_hash"])

    async def handle_invalid_transfer(
        self,
        pending_tx: Dict[str, Any],
        payment: Dict[str, Any],
        error_msg: str
    ):
        """Handle invalid USDT transfer (wrong amount or recipient)"""
        
        logger.error(f"❌ Invalid USDT transfer: {error_msg}")
        
        self.payment_service.update_payment_status(
            payment_id=payment["payment_id"],
            status="failed",
            error_message=f"Invalid transfer: {error_msg}"
        )
        
        self.payment_service.remove_pending_transaction(pending_tx["transaction_hash"])

    async def handle_verification_error(
        self,
        pending_tx: Dict[str, Any],
        payment: Dict[str, Any]
    ):
        """Handle verification error (network issue, etc)"""
        
        attempts = pending_tx.get("webhook_attempts", 0) + 1
        
        if attempts >= self.max_retries:
            logger.error(f"❌ Max retries reached after verification errors")
            
            self.payment_service.update_payment_status(
                payment_id=payment["payment_id"],
                status="failed",
                error_message="Failed to verify transaction after maximum retries"
            )
            
            self.payment_service.remove_pending_transaction(pending_tx["transaction_hash"])


# Global job instance
_verification_job: Optional[USDTPaymentVerificationJob] = None


async def start_verification_job():
    """Start the global verification job"""
    global _verification_job
    
    if _verification_job is None:
        _verification_job = USDTPaymentVerificationJob(
            check_interval=30,  # Check every 30 seconds
            max_retries=20,
            required_confirmations=12,
        )
    
    await _verification_job.start()


def stop_verification_job():
    """Stop the global verification job"""
    global _verification_job
    
    if _verification_job:
        _verification_job.stop()


def get_verification_job() -> Optional[USDTPaymentVerificationJob]:
    """Get the global verification job instance"""
    return _verification_job
