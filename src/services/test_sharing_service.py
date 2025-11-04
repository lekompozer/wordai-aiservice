"""
Test Sharing Service for Online Test System - Phase 4

Handles sharing tests with other users via email invitations,
access control, deadline management, and status tracking.

Author: GitHub Copilot
Date: 03/11/2025
"""

import uuid
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pymongo.database import Database
from bson import ObjectId  # ✅ Add ObjectId import

logger = logging.getLogger(__name__)


class TestSharingService:
    """
    Service for managing test sharing and collaboration
    - Share tests with users via email
    - Track invitation status (pending/accepted/completed/expired/declined)
    - Validate access permissions
    - Handle deadline management
    """

    def __init__(self, db: Database):
        """Initialize with MongoDB database"""
        self.db = db
        self.test_shares = db.test_shares
        self.online_tests = db.online_tests
        self.users = db.users
        self.test_submissions = db.test_submissions

    def create_indexes(self):
        """Create indexes for test_shares collection (called from init script)"""
        # This is handled by scripts/init_test_shares_db.py
        pass

    def share_test(
        self,
        test_id: str,
        sharer_id: str,
        sharee_emails: List[str],
        deadline: Optional[datetime] = None,
        message: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Share test with multiple users via email

        Args:
            test_id: Test ID to share
            sharer_id: Firebase UID of test owner
            sharee_emails: List of recipient emails
            deadline: Optional deadline override (if None, uses test's global deadline)
            message: Optional message from sharer

        Returns:
            List of created share documents

        Raises:
            ValueError: If test not found or not owned by sharer
        """
        try:
            # Validate test exists and user is owner
            test = self.online_tests.find_one({"_id": ObjectId(test_id)})
            if not test:
                raise ValueError("Test not found")

            if test.get("creator_id") != sharer_id:
                raise ValueError("Only test owner can share test")

            if not test.get("is_active", True):
                raise ValueError("Cannot share inactive test")

            # Use test's global deadline if no override provided
            if deadline is None:
                deadline = test.get("deadline")

            # Validate deadline is in future
            if deadline:
                deadline = deadline.replace(tzinfo=timezone.utc)
                if deadline <= datetime.now(timezone.utc):
                    raise ValueError("Deadline must be in the future")

            # Remove duplicate emails
            unique_emails = list(set(sharee_emails))

            created_shares = []
            now = datetime.now(timezone.utc)

            for email in unique_emails:
                email = email.strip().lower()

                # Check if already shared with this email
                existing = self.test_shares.find_one(
                    {
                        "test_id": test_id,
                        "sharee_email": email,
                        "status": {"$nin": ["declined", "expired"]},
                    }
                )

                if existing:
                    logger.warning(f"⚠️ Test {test_id} already shared with {email}")
                    continue

                # Look up user by email (may not exist yet)
                user = self.users.find_one({"email": email})
                sharee_id = user.get("firebase_uid") if user else None

                # Generate unique tokens
                share_id = str(uuid.uuid4())
                invitation_token = str(
                    uuid.uuid4()
                )  # ✅ Generate token for DB schema compatibility

                # ✅ AUTO-ACCEPT: No need for invitation flow, directly accepted
                share_doc = {
                    "share_id": share_id,
                    "invitation_token": invitation_token,  # ✅ Required by unique index
                    "test_id": test_id,
                    "sharer_id": sharer_id,
                    "sharee_email": email,
                    "sharee_id": sharee_id,
                    "status": "accepted",  # ✅ Auto-accepted (no pending state)
                    "deadline": deadline,
                    "message": message,
                    "created_at": now,
                    "accepted_at": now,  # ✅ Accepted immediately
                    "completed_at": None,
                }

                # Insert share
                self.test_shares.insert_one(share_doc)
                logger.info(
                    f"✅ Created test share {share_id} for {email} (auto-accepted)"
                )

                # Convert ObjectId to string for response
                share_doc["_id"] = str(share_doc["_id"])
                created_shares.append(share_doc)

            return created_shares

        except Exception as e:
            logger.error(f"❌ Error sharing test: {e}")
            raise

    def delete_shared_test_for_user(self, test_id: str, user_id: str) -> bool:
        """
        Delete (soft delete) shared test from user's list
        User can remove tests shared with them if they don't want to see it

        Args:
            test_id: Test ID
            user_id: Firebase UID of user

        Returns:
            True if successful

        Raises:
            ValueError: If share not found
        """
        try:
            # Find share for this user
            share = self.test_shares.find_one(
                {
                    "test_id": test_id,
                    "sharee_id": user_id,
                    "status": {"$nin": ["declined", "expired"]},
                }
            )

            if not share:
                raise ValueError("Shared test not found")

            # Soft delete by setting status to 'declined'
            result = self.test_shares.update_one(
                {"share_id": share["share_id"]}, {"$set": {"status": "declined"}}
            )

            if result.modified_count > 0:
                logger.info(f"✅ User {user_id} deleted shared test {test_id}")
                return True
            else:
                return False

        except Exception as e:
            logger.error(f"❌ Error deleting shared test: {e}")
            raise

    def list_my_invitations(
        self, user_id: str, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List test invitations for user (tests shared with me)

        Args:
            user_id: Firebase UID
            status: Optional filter by status

        Returns:
            List of invitations with test details
        """
        try:
            # Get user email
            user = self.users.find_one({"firebase_uid": user_id})
            if not user:
                return []

            user_email = user.get("email", "").lower()

            # Build query
            query = {"$or": [{"sharee_id": user_id}, {"sharee_email": user_email}]}

            if status:
                query["status"] = status

            # Find shares
            shares = list(self.test_shares.find(query).sort("created_at", -1))

            # Enrich with test and sharer info
            result = []
            for share in shares:
                # Get test (share["test_id"] is ObjectId string)
                test = self.online_tests.find_one({"_id": ObjectId(share["test_id"])})
                if not test:
                    continue

                # Get sharer info
                sharer = self.users.find_one({"firebase_uid": share["sharer_id"]})
                sharer_name = "Unknown"
                sharer_email = None
                if sharer:
                    sharer_name = (
                        sharer.get("name")
                        or sharer.get("display_name")
                        or sharer.get("email", "Unknown")
                    )
                    sharer_email = sharer.get("email")

                # Get user's attempt statistics
                test_id_str = share["test_id"]
                my_attempts = 0
                my_best_score = None
                has_completed = False

                if share["status"] in ["accepted", "completed"]:
                    # Get all user's submissions for this test
                    submissions = list(
                        self.test_submissions.find(
                            {"test_id": test_id_str, "user_id": user_id}
                        ).sort("submitted_at", -1)
                    )

                    my_attempts = len(submissions)
                    has_completed = my_attempts > 0

                    if submissions:
                        # Get best score
                        my_best_score = max(sub.get("score", 0) for sub in submissions)

                # Get total number of participants (unique users who submitted)
                total_participants = len(
                    self.test_submissions.distinct("user_id", {"test_id": test_id_str})
                )

                result.append(
                    {
                        "share_id": share["share_id"],
                        "status": share["status"],
                        "deadline": (
                            share.get("deadline").isoformat()
                            if share.get("deadline")
                            else None
                        ),
                        "message": share.get("message"),
                        "test": {
                            "test_id": str(
                                test["_id"]
                            ),  # ✅ Fixed: Use _id, not test_id
                            "title": test["title"],
                            "description": test.get("description", ""),
                            "num_questions": len(test.get("questions", [])),
                            "time_limit_minutes": test.get("time_limit_minutes"),
                            "max_retries": test.get("max_retries", -1),
                            "passing_score": test.get(
                                "passing_score", 50
                            ),  # Default 50% for old tests
                            "total_participants": total_participants,
                        },
                        "sharer": {
                            "name": sharer_name,
                            "email": sharer_email,
                        },
                        "created_at": share["created_at"].isoformat(),
                        "accepted_at": (
                            share.get("accepted_at").isoformat()
                            if share.get("accepted_at")
                            else None
                        ),
                        "has_completed": has_completed,
                        "my_attempts": my_attempts,
                        "my_best_score": my_best_score,
                    }
                )

            return result

        except Exception as e:
            logger.error(f"❌ Error listing invitations: {e}")
            raise

    def list_test_shares(self, test_id: str, owner_id: str) -> List[Dict[str, Any]]:
        """
        List all shares for a specific test (owner only)

        Args:
            test_id: Test ID
            owner_id: Firebase UID of test owner

        Returns:
            List of shares with user info

        Raises:
            ValueError: If test not found or user not owner
        """
        try:
            # Validate ownership
            test = self.online_tests.find_one({"_id": ObjectId(test_id)})
            if not test:
                raise ValueError("Test not found")

            if test.get("creator_id") != owner_id:
                raise ValueError("Only test owner can view shares")

            # Get all shares
            shares = list(
                self.test_shares.find({"test_id": test_id}).sort("created_at", -1)
            )

            # Enrich with sharee info and submission status
            result = []
            for share in shares:
                sharee_name = share.get("sharee_email")
                sharee_info = None

                # Get sharee details if they accepted
                if share.get("sharee_id"):
                    sharee = self.users.find_one({"firebase_uid": share["sharee_id"]})
                    if sharee:
                        sharee_name = (
                            sharee.get("name")
                            or sharee.get("display_name")
                            or sharee.get("email")
                        )
                        sharee_info = {
                            "user_id": share["sharee_id"],
                            "name": sharee_name,
                            "email": sharee.get("email"),
                        }

                # Check submission status
                submission = None
                if share.get("sharee_id"):
                    submission = self.test_submissions.find_one(
                        {"test_id": test_id, "user_id": share["sharee_id"]},
                        sort=[("submitted_at", -1)],
                    )

                result.append(
                    {
                        "share_id": share["share_id"],
                        "sharee_email": share["sharee_email"],
                        "sharee": sharee_info,
                        "status": share["status"],
                        "deadline": (
                            share.get("deadline").isoformat()
                            if share.get("deadline")
                            else None
                        ),
                        "message": share.get("message"),
                        "created_at": share["created_at"].isoformat(),
                        "accepted_at": (
                            share.get("accepted_at").isoformat()
                            if share.get("accepted_at")
                            else None
                        ),
                        "completed_at": (
                            share.get("completed_at").isoformat()
                            if share.get("completed_at")
                            else None
                        ),
                        "submission": (
                            {
                                "score": submission.get("score"),
                                "is_passed": submission.get("is_passed"),
                                "submitted_at": submission["submitted_at"].isoformat(),
                            }
                            if submission
                            else None
                        ),
                    }
                )

            return result

        except Exception as e:
            logger.error(f"❌ Error listing test shares: {e}")
            raise

    def revoke_share(self, share_id: str, owner_id: str) -> bool:
        """
        Revoke access to shared test (owner only)

        Args:
            share_id: Share ID to revoke
            owner_id: Firebase UID of test owner

        Returns:
            True if successful

        Raises:
            ValueError: If share not found or not owner
        """
        try:
            # Get share
            share = self.test_shares.find_one({"share_id": share_id})
            if not share:
                raise ValueError("Share not found")

            # Validate ownership
            test = self.online_tests.find_one({"_id": ObjectId(share["test_id"])})
            if not test or test.get("creator_id") != owner_id:
                raise ValueError("Only test owner can revoke shares")

            # Update status to declined (effectively revoked)
            result = self.test_shares.update_one(
                {"share_id": share_id}, {"$set": {"status": "declined"}}
            )

            if result.modified_count > 0:
                logger.info(f"✅ Revoked share {share_id}")
                return True
            else:
                return False

        except Exception as e:
            logger.error(f"❌ Error revoking share: {e}")
            raise

    def update_deadline(
        self, share_id: str, owner_id: str, new_deadline: Optional[datetime]
    ) -> bool:
        """
        Update deadline for a share (owner only)

        Args:
            share_id: Share ID
            owner_id: Firebase UID of test owner
            new_deadline: New deadline (None to remove)

        Returns:
            True if successful

        Raises:
            ValueError: If invalid deadline or not owner
        """
        try:
            # Get share
            share = self.test_shares.find_one({"share_id": share_id})
            if not share:
                raise ValueError("Share not found")

            # Validate ownership
            test = self.online_tests.find_one({"_id": ObjectId(share["test_id"])})
            if not test or test.get("creator_id") != owner_id:
                raise ValueError("Only test owner can update deadline")

            # Validate new deadline
            if new_deadline:
                new_deadline = new_deadline.replace(tzinfo=timezone.utc)
                if new_deadline <= datetime.now(timezone.utc):
                    raise ValueError("Deadline must be in the future")

            # Update deadline
            result = self.test_shares.update_one(
                {"share_id": share_id}, {"$set": {"deadline": new_deadline}}
            )

            if result.modified_count > 0:
                logger.info(f"✅ Updated deadline for share {share_id}")
                return True
            else:
                return False

        except Exception as e:
            logger.error(f"❌ Error updating deadline: {e}")
            raise

    def check_user_access(self, test_id: str, user_id: str) -> Dict[str, Any]:
        """
        Check if user has access to test (owner or shared)

        Args:
            test_id: Test ID
            user_id: Firebase UID

        Returns:
            Access info dict with access_type and permissions

        Raises:
            ValueError: If no access
        """
        try:
            # Check if user is owner
            test = self.online_tests.find_one({"_id": ObjectId(test_id)})
            if not test:
                raise ValueError("Test not found")

            if test.get("creator_id") == user_id:
                return {
                    "has_access": True,
                    "access_type": "owner",
                    "test": test,
                }

            # Check if user has accepted share
            share = self.test_shares.find_one(
                {"test_id": test_id, "sharee_id": user_id, "status": "accepted"}
            )

            if not share:
                raise ValueError("Access denied: Test not shared with you")

            # Check deadline
            deadline = share.get("deadline")
            if deadline:
                deadline = deadline.replace(tzinfo=timezone.utc)
                if deadline < datetime.now(timezone.utc):
                    # Auto-expire
                    self.test_shares.update_one(
                        {"share_id": share["share_id"]}, {"$set": {"status": "expired"}}
                    )
                    raise ValueError("Access denied: Deadline has passed")

            return {
                "has_access": True,
                "access_type": "shared",
                "test": test,
                "share": share,
            }

        except Exception as e:
            logger.error(f"❌ Error checking user access: {e}")
            raise

    def mark_test_completed(self, test_id: str, user_id: str) -> bool:
        """
        Mark test as completed for user (update share status)

        Args:
            test_id: Test ID
            user_id: Firebase UID

        Returns:
            True if successful
        """
        try:
            now = datetime.now(timezone.utc)
            result = self.test_shares.update_one(
                {"test_id": test_id, "sharee_id": user_id, "status": "accepted"},
                {"$set": {"status": "completed", "completed_at": now}},
            )

            if result.modified_count > 0:
                logger.info(f"✅ Marked test {test_id} as completed for user {user_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"❌ Error marking test completed: {e}")
            return False

    def expire_deadline_shares(self) -> int:
        """
        Expire shares that passed deadline (for cron job)

        Returns:
            Number of shares expired
        """
        try:
            now = datetime.now(timezone.utc)

            result = self.test_shares.update_many(
                {"status": "accepted", "deadline": {"$exists": True, "$lt": now}},
                {"$set": {"status": "expired"}},
            )

            expired_count = result.modified_count
            if expired_count > 0:
                logger.info(f"✅ Expired {expired_count} test shares")

            return expired_count

        except Exception as e:
            logger.error(f"❌ Error expiring shares: {e}")
            return 0


# Singleton instance
_test_sharing_service = None


def get_test_sharing_service() -> TestSharingService:
    """Get singleton instance of TestSharingService"""
    global _test_sharing_service
    if _test_sharing_service is None:
        from config.config import get_mongodb  # ✅ Correct function name

        db = get_mongodb()
        _test_sharing_service = TestSharingService(db)
    return _test_sharing_service
