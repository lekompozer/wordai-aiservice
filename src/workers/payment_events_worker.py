"""
Payment Events Worker
=====================
Listens to Redis queue ``queue:payment_events`` and handles post-payment
side-effects for Conversation Learning subscriptions.

Events processed:
  - conversation_subscription_paid
      → Create/extend user_conversation_subscription
      → Record affiliate_commissions + update affiliate balances
      → Record supervisor_commissions + update supervisor balances (if any)
      → Mark payment record as subscription_activated in payments collection

This worker decouples the SePay IPN webhook from MongoDB writes, so the
Node.js payment service can return 200 to SePay instantly, while all
database updates happen reliably in the background.
"""

import asyncio
import json
import logging
import signal
from datetime import datetime, timedelta
from bson import ObjectId

from src.database.db_manager import DBManager
from src.queue.queue_manager import QueueManager

logger = logging.getLogger(__name__)

QUEUE_NAME = "payment_events"
REDIS_URL = "redis://redis-server:6379"

# ── Commission rates (mirror Python model) ───────────────────────────────────
AFFILIATE_COMMISSION_RATES = {1: 0.40, 2: 0.25}
SUPERVISOR_COMMISSION_RATE = 0.10

PACKAGE_MONTHS = {"3_months": 3, "6_months": 6, "12_months": 12}


# ─────────────────────────────────────────────────────────────────────────────
# Event Handler
# ─────────────────────────────────────────────────────────────────────────────


def _handle_conversation_subscription_paid(db, event: dict):
    """
    Full subscription + commission cascade for a conversation_learning payment.

    event fields:
      payment_id, order_invoice_number, user_id,
      package_id, price_tier, amount_paid, duration_months,
      payment_method, affiliate_code, student_id
    """
    user_id = event["user_id"]
    package_id = event.get("package_id", "3_months")
    price_tier = event.get("price_tier", "no_code")
    amount_paid = int(event.get("amount_paid", 0))
    duration_months = int(
        event.get("duration_months", PACKAGE_MONTHS.get(package_id, 3))
    )
    payment_id = event.get("payment_id", "")
    order_invoice_number = event.get("order_invoice_number", "")
    payment_method = event.get("payment_method", "SEPAY_BANK_TRANSFER")
    affiliate_code = event.get("affiliate_code") or None
    student_id = event.get("student_id") or None

    now = datetime.utcnow()

    logger.info(
        f"[payment_events] Processing conversation_subscription_paid: "
        f"user={user_id} package={package_id} tier={price_tier} "
        f"amount={amount_paid} affiliate={affiliate_code}"
    )

    # ── 1. Create / extend subscription ──────────────────────────────────────
    existing = db["user_conversation_subscription"].find_one(
        {"user_id": user_id, "is_active": True, "end_date": {"$gte": now}}
    )

    if existing:
        new_end = existing["end_date"] + timedelta(days=30 * duration_months)
        db["user_conversation_subscription"].update_one(
            {"_id": existing["_id"]},
            {
                "$set": {
                    "end_date": new_end,
                    "plan_type": package_id,
                    "price_tier": price_tier,
                    "amount_paid": existing.get("amount_paid", 0) + amount_paid,
                    "updated_at": now,
                }
            },
        )
        subscription_id = str(existing["_id"])
        logger.info(f"  ↗ Extended subscription to {new_end.date()} (user={user_id})")
    else:
        new_end = now + timedelta(days=30 * duration_months)
        sub_doc = {
            "user_id": user_id,
            "is_active": True,
            "start_date": now,
            "end_date": new_end,
            "plan_type": package_id,
            "price_tier": price_tier,
            "amount_paid": amount_paid,
            "payment_id": payment_id,
            "order_invoice_number": order_invoice_number,
            "payment_method": payment_method,
            "affiliate_code": affiliate_code,
            "student_id": student_id,
            "created_at": now,
            "updated_at": now,
        }
        result = db["user_conversation_subscription"].insert_one(sub_doc)
        subscription_id = str(result.inserted_id)
        logger.info(
            f"  ✅ New subscription created, expires {new_end.date()} (user={user_id})"
        )

    # ── 2. Affiliate commission cascade ──────────────────────────────────────
    if affiliate_code:
        aff = db["affiliates"].find_one(
            {"code": affiliate_code.upper(), "is_active": True}
        )
        if aff:
            commission_rate = AFFILIATE_COMMISSION_RATES.get(aff["tier"], 0.0)
            commission_amount = round(amount_paid * commission_rate)

            db["affiliate_commissions"].insert_one(
                {
                    "affiliate_id": str(aff["_id"]),
                    "affiliate_code": affiliate_code.upper(),
                    "user_id": user_id,
                    "subscription_id": subscription_id,
                    "amount_paid_by_user": amount_paid,
                    "commission_rate": commission_rate,
                    "commission_amount": commission_amount,
                    "package_id": package_id,
                    "price_tier": price_tier,
                    "student_id": student_id,
                    "status": "pending",
                    "created_at": now,
                }
            )

            db["affiliates"].update_one(
                {"_id": aff["_id"]},
                {
                    "$inc": {
                        "total_earned": commission_amount,
                        "pending_balance": commission_amount,
                        "total_referred_users": 1,
                    },
                    "$set": {"updated_at": now},
                },
            )

            logger.info(
                f"  💰 Affiliate commission: {commission_amount:,} VNĐ "
                f"for {affiliate_code} (tier {aff['tier']}, rate {commission_rate*100:.0f}%)"
            )

            # ── 3. Supervisor commission cascade ─────────────────────────────
            supervisor_id = aff.get("supervisor_id")
            if supervisor_id:
                try:
                    sup = db["supervisors"].find_one(
                        {"_id": ObjectId(supervisor_id), "is_active": True}
                    )
                except Exception:
                    sup = None

                if sup:
                    sup_commission = round(amount_paid * SUPERVISOR_COMMISSION_RATE)

                    db["supervisor_commissions"].insert_one(
                        {
                            "supervisor_id": supervisor_id,
                            "supervisor_code": sup["code"],
                            "affiliate_id": str(aff["_id"]),
                            "affiliate_code": affiliate_code.upper(),
                            "user_id": user_id,
                            "subscription_id": subscription_id,
                            "amount_paid_by_user": amount_paid,
                            "commission_rate": SUPERVISOR_COMMISSION_RATE,
                            "commission_amount": sup_commission,
                            "package_id": package_id,
                            "status": "pending",
                            "created_at": now,
                        }
                    )

                    db["supervisors"].update_one(
                        {"_id": sup["_id"]},
                        {
                            "$inc": {
                                "total_earned": sup_commission,
                                "pending_balance": sup_commission,
                            },
                            "$set": {"updated_at": now},
                        },
                    )

                    logger.info(
                        f"  💼 Supervisor commission: {sup_commission:,} VNĐ "
                        f"for {sup['code']} (10%)"
                    )
        else:
            logger.warning(
                f"  ⚠️  Affiliate code '{affiliate_code}' not found or inactive — "
                f"skipping commission"
            )

    # ── 4. Mark payment record as activated ──────────────────────────────────
    if order_invoice_number:
        db["payments"].update_one(
            {"order_invoice_number": order_invoice_number},
            {
                "$set": {
                    "subscription_activated": True,
                    "subscription_id": subscription_id,
                    "activated_at": now,
                    "updated_at": now,
                }
            },
        )

    logger.info(
        f"[payment_events] ✅ Done: user={user_id} sub={subscription_id} "
        f"expires={new_end.date()}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Worker Class
# ─────────────────────────────────────────────────────────────────────────────


class PaymentEventsWorker:
    def __init__(
        self,
        worker_id: str = "payment-events-worker",
        redis_url: str = REDIS_URL,
    ):
        self.worker_id = worker_id
        self.redis_url = redis_url
        self.running = False
        self.queue = QueueManager(redis_url=redis_url, queue_name=QUEUE_NAME)
        self.db_manager = DBManager()
        logger.info(f"💳 PaymentEventsWorker [{worker_id}] initialized")

    async def initialize(self):
        await self.queue.connect()
        logger.info(
            f"✅ Worker [{self.worker_id}] connected to Redis queue 'queue:{QUEUE_NAME}'"
        )

    async def start(self):
        self.running = True
        logger.info(
            f"🚀 Worker [{self.worker_id}] listening on 'queue:{QUEUE_NAME}' ..."
        )

        db = self.db_manager.db

        while self.running:
            try:
                # BRPOP blocks for up to 2s then loops — allows clean shutdown
                raw = await self.queue.redis_client.brpop(
                    self.queue.task_queue_key, timeout=2
                )
                if not raw:
                    continue

                _, raw_payload = raw
                event = json.loads(raw_payload)
                event_type = event.get("event_type", "")

                logger.info(
                    f"📥 [{self.worker_id}] event={event_type} "
                    f"order={event.get('order_invoice_number', '?')}"
                )

                if event_type == "conversation_subscription_paid":
                    _handle_conversation_subscription_paid(db, event)
                else:
                    logger.warning(
                        f"[{self.worker_id}] Unknown event_type: {event_type}"
                    )

            except json.JSONDecodeError as e:
                logger.error(f"[{self.worker_id}] JSON parse error: {e}")
            except Exception as e:
                logger.error(
                    f"[{self.worker_id}] Error processing event: {e}", exc_info=True
                )
                await asyncio.sleep(2)  # brief pause on error

    def stop(self):
        self.running = False
        logger.info(f"🛑 Worker [{self.worker_id}] stopping...")


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    worker = PaymentEventsWorker()
    await worker.initialize()

    loop = asyncio.get_running_loop()

    def _shutdown(*_):
        worker.stop()

    loop.add_signal_handler(signal.SIGINT, _shutdown)
    loop.add_signal_handler(signal.SIGTERM, _shutdown)

    await worker.start()


if __name__ == "__main__":
    asyncio.run(main())
