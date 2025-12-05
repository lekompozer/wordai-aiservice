"""
Guide Permission Manager Service
Phase 1: Database operations for User Permissions
"""

import uuid
import secrets
from datetime import datetime
from typing import Optional, List, Dict, Any
import logging
from pymongo.errors import DuplicateKeyError

logger = logging.getLogger("chatbot")


class GuideBookBookPermissionManager:
    """Quản lý Guide Permissions trong MongoDB"""

    def __init__(self, db):
        """
        Initialize GuideBookBookPermissionManager

        Args:
            db: PyMongo Database object (synchronous)
        """
        self.db = db
        self.permissions_collection = db["book_permissions"]

    def create_indexes(self):
        """Tạo indexes cho collection guide_permissions"""
        try:
            existing_indexes = [
                idx["name"] for idx in self.permissions_collection.list_indexes()
            ]

            # Primary key
            if "permission_id_unique" not in existing_indexes:
                self.permissions_collection.create_index(
                    "permission_id", unique=True, name="permission_id_unique"
                )
                logger.info("✅ Created index: permission_id_unique")

            # One permission per user per guide
            if "guide_user_unique" not in existing_indexes:
                self.permissions_collection.create_index(
                    [("book_id", 1), ("user_id", 1)],
                    unique=True,
                    name="guide_user_unique",
                )
                logger.info("✅ Created index: guide_user_unique")

            # List permissions for a guide
            if "guide_permissions_list" not in existing_indexes:
                self.permissions_collection.create_index(
                    "book_id", name="guide_permissions_list"
                )
                logger.info("✅ Created index: guide_permissions_list")

            # List guides user has access to
            if "user_permissions_list" not in existing_indexes:
                self.permissions_collection.create_index(
                    "user_id", name="user_permissions_list"
                )
                logger.info("✅ Created index: user_permissions_list")

            # Email invitation lookup
            if "invitation_lookup" not in existing_indexes:
                self.permissions_collection.create_index(
                    [("invited_email", 1), ("invitation_token", 1)],
                    name="invitation_lookup",
                )
                logger.info("✅ Created index: invitation_lookup")

            # Expiration cleanup (TTL index)
            if "expiration_cleanup" not in existing_indexes:
                self.permissions_collection.create_index(
                    "expires_at", name="expiration_cleanup", expireAfterSeconds=0
                )
                logger.info("✅ Created index: expiration_cleanup (TTL)")

            logger.info("✅ Guide Permission indexes verified/created")
        except Exception as e:
            logger.error(f"❌ Error creating permission indexes: {e}")
            raise

    def grant_permission(
        self,
        book_id: str,
        user_id: str,
        granted_by: str,
        access_level: str = "viewer",
        expires_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Grant permission to user

        Args:
            book_id: Guide UUID
            user_id: User's Firebase UID
            granted_by: Owner's Firebase UID
            access_level: "viewer" | "editor"
            expires_at: Optional expiration date

        Returns:
            permission document

        Raises:
            DuplicateKeyError: If user already has permission
        """
        permission_id = str(uuid.uuid4())
        now = datetime.utcnow()

        permission_doc = {
            "permission_id": permission_id,
            "book_id": book_id,
            "user_id": user_id,
            "granted_by": granted_by,
            "access_level": access_level,
            "invited_email": None,
            "invitation_token": None,
            "invitation_accepted": True,  # Direct grant = auto accepted
            "invited_at": None,
            "accepted_at": now,
            "expires_at": expires_at,
            "created_at": now,
            "updated_at": now,
        }

        try:
            self.permissions_collection.insert_one(permission_doc)
            logger.info(
                f"✅ Granted {access_level} permission to {user_id} for guide {book_id}"
            )
            # Return the document (remove _id for clean response)
            result = dict(permission_doc)
            result.pop("_id", None)
            return result
        except DuplicateKeyError:
            logger.error(
                f"❌ User {user_id} already has permission for guide {book_id}"
            )
            raise

    def create_invitation(
        self,
        book_id: str,
        email: str,
        granted_by: str,
        access_level: str = "viewer",
        expires_at: Optional[datetime] = None,
        message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create email invitation

        Args:
            book_id: Guide UUID
            email: Email to invite
            granted_by: Owner's Firebase UID
            access_level: "viewer" | "editor"
            expires_at: Optional expiration date
            message: Optional personal message

        Returns:
            permission document with invitation details
        """
        permission_id = str(uuid.uuid4())
        invitation_token = secrets.token_urlsafe(32)
        now = datetime.utcnow()

        permission_doc = {
            "permission_id": permission_id,
            "book_id": book_id,
            "user_id": "",  # Will be filled when user registers with this email
            "granted_by": granted_by,
            "access_level": access_level,
            "invited_email": email,
            "invitation_token": invitation_token,
            "invitation_message": message,  # Store the personal message
            "invitation_accepted": True,  # Auto-accept: permission is active immediately
            "invited_at": now,
            "accepted_at": now,
            "expires_at": expires_at,
            "created_at": now,
            "updated_at": now,
        }

        self.permissions_collection.insert_one(permission_doc)
        logger.info(f"✅ Created invitation for {email} to guide {book_id}")

        # Return the document (remove _id for clean response)
        result = dict(permission_doc)
        result.pop("_id", None)
        return result

    def accept_invitation(self, invitation_token: str, user_id: str) -> Optional[str]:
        """
        Accept email invitation

        Args:
            invitation_token: Invitation token from email
            user_id: User's Firebase UID

        Returns:
            permission_id if accepted, None if not found
        """
        now = datetime.utcnow()

        result = self.permissions_collection.update_one(
            {"invitation_token": invitation_token, "invitation_accepted": False},
            {
                "$set": {
                    "user_id": user_id,
                    "invitation_accepted": True,
                    "accepted_at": now,
                    "updated_at": now,
                }
            },
        )

        if result.modified_count > 0:
            # Get permission ID
            permission = self.permissions_collection.find_one(
                {"invitation_token": invitation_token}
            )
            permission_id = permission["permission_id"] if permission else None
            logger.info(f"✅ User {user_id} accepted invitation: {permission_id}")
            return permission_id
        else:
            logger.warning(
                f"⚠️ Invitation not found or already accepted: {invitation_token}"
            )
            return None

    def revoke_permission(self, book_id: str, user_id: str) -> bool:
        """
        Revoke user's permission

        Args:
            book_id: Guide UUID
            user_id: User's Firebase UID

        Returns:
            True if revoked
        """
        result = self.permissions_collection.delete_one(
            {"book_id": book_id, "user_id": user_id}
        )

        if result.deleted_count > 0:
            logger.info(f"🗑️ Revoked permission for {user_id} on guide {book_id}")
            return True
        return False

    def check_permission(self, book_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Check if user has permission to access guide

        Args:
            book_id: Guide UUID
            user_id: User's Firebase UID

        Returns:
            Permission document if exists and valid, None otherwise
        """
        now = datetime.utcnow()

        permission = self.permissions_collection.find_one(
            {
                "book_id": book_id,
                "user_id": user_id,
                "invitation_accepted": True,
                "$or": [{"expires_at": None}, {"expires_at": {"$gt": now}}],
            }
        )

        return permission

    def get_permission(self, book_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get permission for a user on a guide (alias for check_permission)

        Args:
            book_id: Guide UUID
            user_id: User's Firebase UID

        Returns:
            Permission document if exists, None otherwise
        """
        return self.check_permission(book_id, user_id)

    def list_permissions(
        self,
        book_id: str,
        include_pending: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        List all users with access to guide

        Args:
            book_id: Guide UUID
            include_pending: Include pending invitations
            skip: Pagination offset
            limit: Results per page

        Returns:
            List of permission documents
        """
        # Note: All invitations are auto-accepted, show all permissions
        query = {"book_id": book_id}

        permissions = list(
            self.permissions_collection.find(query)
            .sort([("created_at", -1)])
            .skip(skip)
            .limit(limit)
        )

        logger.info(
            f"📊 Found {len(permissions)} permissions for guide {book_id} (skip={skip}, limit={limit})"
        )
        return permissions

    def list_user_accessible_guides(self, user_id: str) -> List[str]:
        """
        List all guide IDs user has access to

        Args:
            user_id: User's Firebase UID

        Returns:
            List of guide IDs
        """
        now = datetime.utcnow()

        # Note: All invitations are auto-accepted
        permissions = self.permissions_collection.find(
            {
                "user_id": user_id,
                "$or": [{"expires_at": None}, {"expires_at": {"$gt": now}}],
            }
        )

        guide_ids = [p["book_id"] for p in permissions]
        logger.info(f"📊 User {user_id} has access to {len(guide_ids)} guides")
        return guide_ids

    def delete_permissions_by_guide(self, book_id: str) -> int:
        """
        Delete all permissions for a guide (cascade delete)

        Args:
            book_id: Guide UUID

        Returns:
            Number of permissions deleted
        """
        result = self.permissions_collection.delete_many({"book_id": book_id})
        deleted_count = result.deleted_count

        logger.info(f"🗑️ Deleted {deleted_count} permissions for guide {book_id}")
        return deleted_count

    def count_permissions(self, book_id: str, include_pending: bool = False) -> int:
        """Count total permissions for guide"""
        query = {"book_id": book_id}
        # Note: All invitations are auto-accepted
        return self.permissions_collection.count_documents(query)

    def list_permissions_by_user(
        self, user_id: str, skip: int = 0, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        List all permissions for a specific user

        Args:
            user_id: User's Firebase UID
            skip: Pagination offset
            limit: Results per page

        Returns:
            List of permission documents
        """
        now = datetime.utcnow()

        query = {
            "user_id": user_id,
            "$or": [{"expires_at": None}, {"expires_at": {"$gt": now}}],
        }

        permissions = list(
            self.permissions_collection.find(query)
            .sort([("created_at", -1)])
            .skip(skip)
            .limit(limit)
        )

        logger.info(
            f"📊 Found {len(permissions)} permissions for user {user_id} (skip={skip}, limit={limit})"
        )
        return permissions

    def count_permissions_by_user(self, user_id: str) -> int:
        """
        Count total permissions for a user

        Args:
            user_id: User's Firebase UID

        Returns:
            Number of active permissions
        """
        now = datetime.utcnow()

        query = {
            "user_id": user_id,
            "$or": [{"expires_at": None}, {"expires_at": {"$gt": now}}],
        }

        count = self.permissions_collection.count_documents(query)
        logger.info(f"📊 User {user_id} has {count} total permissions")
        return count

    def cleanup_expired(self) -> int:
        """
        Manual cleanup of expired permissions (TTL index should handle this automatically)

        Returns:
            Number of expired permissions deleted
        """
        now = datetime.utcnow()

        result = self.permissions_collection.delete_many({"expires_at": {"$lte": now}})

        deleted_count = result.deleted_count
        if deleted_count > 0:
            logger.info(f"🗑️ Cleaned up {deleted_count} expired permissions")
        return deleted_count

    def check_user_book_access(self, user_id: str, book_id: str) -> bool:
        """
        Check if user has access to book (via purchase or permission)
        
        Args:
            user_id: User's Firebase UID
            book_id: Book ID
            
        Returns:
            True if user has access, False otherwise
        """
        # Check if user is owner
        book = self.db.online_books.find_one({"book_id": book_id})
        if book and book.get("user_id") == user_id:
            return True
        
        # Check book purchases
        purchase = self.db.book_purchases.find_one({
            "user_id": user_id,
            "book_id": book_id,
            "purchase_type": {"$in": ["one_time", "forever"]}
        })
        
        if purchase:
            # For one_time, check expiry
            if purchase.get("purchase_type") == "one_time":
                expires_at = purchase.get("access_expires_at")
                if expires_at and expires_at > datetime.utcnow():
                    return True
            else:
                # Forever access
                return True
        
        # Check book permissions
        permission = self.check_permission(book_id, user_id)
        return permission is not None


# Alias for backwards compatibility
BookPermissionManager = GuideBookBookPermissionManager
