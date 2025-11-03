#!/usr/bin/env python3
"""
Test Sharing Deadline Cron Job

Runs periodically (e.g., every hour) to:
1. Expire shares that passed their deadline
2. Send deadline reminder emails (24h before)

Usage:
    python scripts/test_sharing_deadline_cron.py

Crontab example (run every hour):
    0 * * * * cd /path/to/wordai-aiservice && python scripts/test_sharing_deadline_cron.py >> logs/deadline_cron.log 2>&1
"""

import os
import sys
from datetime import datetime, timezone, timedelta

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.test_sharing_service import get_test_sharing_service
from src.services.brevo_email_service import get_brevo_service
from config.config import get_mongo_db


def main():
    """Main cron job logic"""
    print(f"\n{'='*60}")
    print(f"🕐 Test Sharing Deadline Cron Job")
    print(f"{'='*60}")
    print(f"⏰ Started at: {datetime.now(timezone.utc).isoformat()}")

    try:
        # Initialize services
        sharing_service = get_test_sharing_service()
        brevo = get_brevo_service()
        db = get_mongo_db()

        # ===== Task 1: Expire shares with passed deadlines =====
        print("\n📅 Task 1: Expiring shares with passed deadlines...")
        expired_count = sharing_service.expire_deadline_shares()
        print(f"   ✅ Expired {expired_count} shares")

        # ===== Task 2: Send 24h deadline reminders =====
        print("\n⏰ Task 2: Sending deadline reminder emails (24h before)...")

        now = datetime.now(timezone.utc)
        reminder_window_start = now + timedelta(hours=23)  # 23h from now
        reminder_window_end = now + timedelta(hours=25)  # 25h from now

        # Find shares with deadline in 23-25h window (accepted, not completed)
        shares_to_remind = list(
            sharing_service.db.test_shares.find(
                {
                    "status": "accepted",
                    "deadline": {
                        "$gte": reminder_window_start,
                        "$lte": reminder_window_end,
                    },
                }
            )
        )

        print(f"   Found {len(shares_to_remind)} shares with upcoming deadlines")

        reminder_sent = 0
        for share in shares_to_remind:
            try:
                # Get test info
                test = db.online_tests.find_one({"test_id": share["test_id"]})
                if not test:
                    print(f"   ⚠️ Test {share['test_id']} not found, skipping")
                    continue

                # Get sharee info
                sharee = db.users.find_one({"firebase_uid": share["sharee_id"]})
                if not sharee or not sharee.get("email"):
                    print(f"   ⚠️ Sharee {share.get('sharee_id')} not found, skipping")
                    continue

                sharee_email = sharee.get("email")
                sharee_name = (
                    sharee.get("name")
                    or sharee.get("display_name")
                    or sharee_email.split("@")[0]
                )

                # Calculate hours remaining
                deadline = share.get("deadline")
                if deadline.tzinfo is None:
                    deadline = deadline.replace(tzinfo=timezone.utc)

                hours_remaining = int((deadline - now).total_seconds() / 3600)
                deadline_str = deadline.strftime("%d/%m/%Y %H:%M")

                # Send reminder email
                brevo.send_test_deadline_reminder(
                    to_email=sharee_email,
                    recipient_name=sharee_name,
                    test_title=test["title"],
                    deadline=deadline_str,
                    hours_remaining=hours_remaining,
                )

                print(f"   📧 Sent reminder to {sharee_email} (test: {test['title']})")
                reminder_sent += 1

            except Exception as e:
                print(
                    f"   ❌ Failed to send reminder for share {share.get('share_id')}: {e}"
                )

        print(f"   ✅ Sent {reminder_sent} reminder emails")

        # ===== Summary =====
        print(f"\n{'='*60}")
        print("📊 Summary:")
        print(f"   - Expired shares: {expired_count}")
        print(f"   - Reminder emails sent: {reminder_sent}")
        print(f"⏰ Completed at: {datetime.now(timezone.utc).isoformat()}")
        print(f"{'='*60}\n")

        return 0

    except Exception as e:
        print(f"\n❌ Cron job failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
