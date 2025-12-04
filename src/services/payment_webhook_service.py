"""
Payment Webhook Service

Send webhook notifications when payment status changes
"""

import os
import asyncio
import aiohttp
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger("chatbot")


class PaymentWebhookService:
    """Service for sending payment webhook notifications"""

    def __init__(self):
        """Initialize webhook service"""
        self.timeout = aiohttp.ClientTimeout(total=10)
        self.max_retries = 3
        
    async def send_payment_update(
        self,
        webhook_url: str,
        payment_id: str,
        status: str,
        payment_type: str,
        user_id: str,
        amount_usdt: float,
        transaction_hash: Optional[str] = None,
        points_amount: Optional[int] = None,
        subscription_id: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """
        Send payment status update to webhook URL
        
        Args:
            webhook_url: Frontend webhook endpoint URL
            payment_id: Payment ID
            status: Payment status
            payment_type: "points" or "subscription"
            user_id: Firebase user ID
            amount_usdt: Payment amount in USDT
            transaction_hash: BSC transaction hash
            points_amount: Points amount (for points purchase)
            subscription_id: Subscription ID (for subscription)
            error_message: Error message if failed
            
        Returns:
            True if webhook sent successfully
        """
        try:
            payload = {
                "event": "payment.status_changed",
                "timestamp": datetime.utcnow().isoformat(),
                "data": {
                    "payment_id": payment_id,
                    "status": status,
                    "payment_type": payment_type,
                    "user_id": user_id,
                    "amount_usdt": amount_usdt,
                    "transaction_hash": transaction_hash,
                    "points_amount": points_amount,
                    "subscription_id": subscription_id,
                    "error_message": error_message,
                }
            }
            
            logger.info(f"📤 Sending webhook for payment {payment_id} (status: {status}) to {webhook_url}")
            
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                for attempt in range(1, self.max_retries + 1):
                    try:
                        async with session.post(
                            webhook_url,
                            json=payload,
                            headers={"Content-Type": "application/json"}
                        ) as response:
                            if response.status == 200:
                                logger.info(f"✅ Webhook sent successfully for payment {payment_id}")
                                return True
                            else:
                                logger.warning(
                                    f"⚠️ Webhook returned status {response.status} for payment {payment_id} (attempt {attempt}/{self.max_retries})"
                                )
                                
                    except asyncio.TimeoutError:
                        logger.warning(f"⏱️ Webhook timeout for payment {payment_id} (attempt {attempt}/{self.max_retries})")
                        
                    except Exception as e:
                        logger.error(f"❌ Webhook error for payment {payment_id} (attempt {attempt}/{self.max_retries}): {e}")
                    
                    # Wait before retry (exponential backoff)
                    if attempt < self.max_retries:
                        await asyncio.sleep(2 ** attempt)
                        
            logger.error(f"❌ Failed to send webhook for payment {payment_id} after {self.max_retries} attempts")
            return False
            
        except Exception as e:
            logger.error(f"❌ Error sending webhook for payment {payment_id}: {e}")
            return False
            
    async def send_payment_completed(
        self,
        webhook_url: str,
        payment: Dict[str, Any],
    ) -> bool:
        """
        Send payment completed webhook
        
        Args:
            webhook_url: Frontend webhook endpoint
            payment: Payment document
            
        Returns:
            True if sent successfully
        """
        return await self.send_payment_update(
            webhook_url=webhook_url,
            payment_id=payment["payment_id"],
            status="completed",
            payment_type=payment["payment_type"],
            user_id=payment["user_id"],
            amount_usdt=payment["amount_usdt"],
            transaction_hash=payment.get("transaction_hash"),
            points_amount=payment.get("points_amount"),
            subscription_id=payment.get("subscription_id"),
        )
        
    async def send_payment_failed(
        self,
        webhook_url: str,
        payment: Dict[str, Any],
        error_message: str,
    ) -> bool:
        """
        Send payment failed webhook
        
        Args:
            webhook_url: Frontend webhook endpoint
            payment: Payment document
            error_message: Failure reason
            
        Returns:
            True if sent successfully
        """
        return await self.send_payment_update(
            webhook_url=webhook_url,
            payment_id=payment["payment_id"],
            status="failed",
            payment_type=payment["payment_type"],
            user_id=payment["user_id"],
            amount_usdt=payment["amount_usdt"],
            transaction_hash=payment.get("transaction_hash"),
            points_amount=payment.get("points_amount"),
            error_message=error_message,
        )


# Global instance
_webhook_service: Optional[PaymentWebhookService] = None


def get_webhook_service() -> PaymentWebhookService:
    """Get or create webhook service instance"""
    global _webhook_service
    if _webhook_service is None:
        _webhook_service = PaymentWebhookService()
    return _webhook_service
