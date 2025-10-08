"""
Share Manager Service
Handles file sharing between users (Phase 2)
Supports Upload Files (Type 1), Documents (Type 2), Library Files (Type 3)
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from pymongo.database import Database
import uuid

logger = logging.getLogger(__name__)


class ShareManager:
    """
    Quản lý file sharing giữa users
    - Share Upload Files, Documents, Library Files
    - Permission levels: view, download, edit
    - Expiration dates
    - Access logging
    - Revoke shares
    """

    def __init__(self, db: Database):
        """
        Initialize ShareManager

        Args:
            db: MongoDB database instance
        """
        self.db = db
        self.file_shares = db["file_shares"]
        self.share_access_logs = db["share_access_logs"]
        self.users = db["users"]
        self.user_files = db["user_files"]
        self.documents = db["documents"]
        self.library_files = db["library_files"]

        logger.info("✅ ShareManager initialized")

    def create_indexes(self):
        """
        Tạo indexes cho file_shares và share_access_logs collections
        Run này một lần duy nhất khi setup database
        """
        try:
            # file_shares indexes
            self.file_shares.create_index("share_id", unique=True, sparse=True)
            self.file_shares.create_index("owner_id")
            self.file_shares.create_index("recipient_id")
            self.file_shares.create_index([("owner_id", 1), ("file_type", 1)])
            self.file_shares.create_index([("recipient_id", 1), ("file_type", 1)])
            self.file_shares.create_index("file_id")
            self.file_shares.create_index("expires_at")
            self.file_shares.create_index("is_active")
            self.file_shares.create_index([("owner_id", 1), ("is_active", 1)])
            self.file_shares.create_index([("recipient_id", 1), ("is_active", 1)])

            # share_access_logs indexes
            self.share_access_logs.create_index("log_id", unique=True, sparse=True)
            self.share_access_logs.create_index("share_id")
            self.share_access_logs.create_index("user_id")
            self.share_access_logs.create_index("accessed_at")
            self.share_access_logs.create_index([("share_id", 1), ("accessed_at", -1)])

            logger.info("✅ Share indexes created successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Error creating share indexes: {e}")
            return False

    def create_share(
        self,
        owner_id: str,
        recipient_email: str,
        file_id: str,
        file_type: str,
        permission: str = "view",
        expires_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Create a file share

        Args:
            owner_id: File owner's user ID
            recipient_email: Recipient's email address
            file_id: ID of file to share (file_id, doc_id, or library_id)
            file_type: Type of file ("upload", "document", "library")
            permission: Permission level ("view", "download", "edit")
            expires_at: Optional expiration datetime

        Returns:
            Share document

        Raises:
            ValueError: If file not found, recipient not found, or invalid permission
        """
        try:
            # Validate file type
            if file_type not in ["upload", "document", "library"]:
                raise ValueError(
                    "Invalid file_type. Must be: upload, document, or library"
                )

            # Validate permission
            if permission not in ["view", "download", "edit"]:
                raise ValueError("Invalid permission. Must be: view, download, or edit")

            # Get file info to verify ownership and existence
            file_doc = None
            if file_type == "upload":
                file_doc = self.user_files.find_one(
                    {"file_id": file_id, "user_id": owner_id}
                )
            elif file_type == "document":
                file_doc = self.documents.find_one(
                    {"doc_id": file_id, "user_id": owner_id}
                )
            elif file_type == "library":
                file_doc = self.library_files.find_one(
                    {"library_id": file_id, "user_id": owner_id}
                )

            if not file_doc:
                raise ValueError(f"File not found or you don't own this file")

            if file_doc.get("is_deleted", False):
                raise ValueError("Cannot share deleted files")

            # Find recipient user by email
            recipient = self.users.find_one({"email": recipient_email})
            if not recipient:
                raise ValueError(f"Recipient with email {recipient_email} not found")

            # Get firebase_uid as recipient_id (NOT "uid"!)
            recipient_id = recipient.get("firebase_uid")

            if not recipient_id:
                logger.error(
                    f"❌ User {recipient_email} has no firebase_uid in database"
                )
                raise ValueError(f"Invalid user data for {recipient_email}")

            # Cannot share with yourself
            if recipient_id == owner_id:
                raise ValueError("Cannot share file with yourself")

            # Check if already shared with this user
            existing_share = self.file_shares.find_one(
                {
                    "owner_id": owner_id,
                    "recipient_id": recipient_id,
                    "file_id": file_id,
                    "is_active": True,
                }
            )

            if existing_share:
                raise ValueError(
                    f"File already shared with {recipient_email}. Update or revoke the existing share."
                )

            # Create share record
            share_id = f"share_{uuid.uuid4().hex[:16]}"
            now = datetime.now(timezone.utc)

            share_doc = {
                "share_id": share_id,
                "owner_id": owner_id,
                "recipient_id": recipient_id,
                "recipient_email": recipient_email,
                "file_id": file_id,
                "file_type": file_type,
                "filename": file_doc.get("filename", ""),
                "permission": permission,
                "is_active": True,
                "expires_at": expires_at,
                "created_at": now,
                "updated_at": now,
            }

            self.file_shares.insert_one(share_doc)

            logger.info(
                f"✅ Share created: {share_id} | {file_type}:{file_id} | {owner_id} -> {recipient_email} ({permission})"
            )

            return share_doc

        except ValueError as e:
            logger.warning(f"⚠️ Share creation failed: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Error creating share: {e}")
            raise

    def list_my_shares(
        self,
        owner_id: str,
        file_type: Optional[str] = None,
        is_active: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        List files I have shared with others

        Args:
            owner_id: File owner's user ID
            file_type: Optional filter by file type
            is_active: Optional filter by active status
            limit: Max results
            offset: Pagination offset

        Returns:
            List of share documents
        """
        try:
            query = {"owner_id": owner_id}

            if file_type:
                query["file_type"] = file_type
            if is_active is not None:
                query["is_active"] = is_active

            shares = list(
                self.file_shares.find(query)
                .sort("created_at", -1)
                .skip(offset)
                .limit(limit)
            )

            logger.info(
                f"📋 Listed {len(shares)} shares for owner: {owner_id} (offset: {offset})"
            )

            return shares

        except Exception as e:
            logger.error(f"❌ Error listing my shares: {e}")
            raise

    def list_shared_with_me(
        self,
        recipient_id: str,
        file_type: Optional[str] = None,
        is_active: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        List files shared with me by others

        Args:
            recipient_id: Recipient's user ID
            file_type: Optional filter by file type
            is_active: Filter by active status (default: True)
            limit: Max results
            offset: Pagination offset

        Returns:
            List of share documents with file details
        """
        try:
            query = {"recipient_id": recipient_id, "is_active": is_active}

            if file_type:
                query["file_type"] = file_type

            # Check expiration
            now = datetime.now(timezone.utc)
            query["$or"] = [
                {"expires_at": None},
                {"expires_at": {"$gt": now}},
            ]

            shares = list(
                self.file_shares.find(query)
                .sort("created_at", -1)
                .skip(offset)
                .limit(limit)
            )

            # Filter out shares where the file has been deleted
            valid_shares = []
            for share in shares:
                file_id = share.get("file_id")
                file_type = share.get("file_type")

                # Check if file still exists and is not deleted
                file_exists = False

                if file_type == "upload":
                    file_doc = self.user_files.find_one(
                        {"file_id": file_id, "is_deleted": {"$ne": True}}  # Not deleted
                    )
                    file_exists = file_doc is not None

                elif file_type == "document":
                    file_doc = self.documents.find_one(
                        {"doc_id": file_id, "is_deleted": {"$ne": True}}  # Not deleted
                    )
                    file_exists = file_doc is not None

                elif file_type == "library":
                    file_doc = self.library_files.find_one(
                        {
                            "library_id": file_id,
                            "is_deleted": {"$ne": True},  # Not deleted
                        }
                    )
                    file_exists = file_doc is not None

                # Only include shares where file still exists and is not deleted
                if file_exists:
                    valid_shares.append(share)
                else:
                    logger.debug(
                        f"⚠️ Skipping share {share.get('share_id')} - file deleted or not found"
                    )

            logger.info(
                f"📋 Listed {len(valid_shares)} shares for recipient: {recipient_id} (filtered from {len(shares)}, offset: {offset})"
            )

            return valid_shares

        except Exception as e:
            logger.error(f"❌ Error listing shared with me: {e}")
            raise

    def update_share_permission(
        self,
        share_id: str,
        owner_id: str,
        permission: str,
        expires_at: Optional[datetime] = None,
    ) -> bool:
        """
        Update share permissions or expiration

        Args:
            share_id: Share ID
            owner_id: Owner's user ID (for verification)
            permission: New permission level
            expires_at: New expiration datetime (None = unchanged)

        Returns:
            True if updated successfully

        Raises:
            ValueError: If share not found or invalid permission
        """
        try:
            # Validate permission
            if permission not in ["view", "download", "edit"]:
                raise ValueError("Invalid permission. Must be: view, download, or edit")

            # Find share
            share = self.file_shares.find_one(
                {"share_id": share_id, "owner_id": owner_id}
            )

            if not share:
                raise ValueError("Share not found or you don't own this share")

            # Update
            update_data = {
                "permission": permission,
                "updated_at": datetime.now(timezone.utc),
            }

            if expires_at is not None:
                update_data["expires_at"] = expires_at

            result = self.file_shares.update_one(
                {"share_id": share_id}, {"$set": update_data}
            )

            if result.modified_count > 0:
                logger.info(f"✅ Share updated: {share_id} | permission: {permission}")
                return True

            return False

        except ValueError as e:
            logger.warning(f"⚠️ Share update failed: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Error updating share: {e}")
            raise

    def revoke_share(self, share_id: str, owner_id: str) -> bool:
        """
        Revoke a file share

        Args:
            share_id: Share ID
            owner_id: Owner's user ID (for verification)

        Returns:
            True if revoked successfully

        Raises:
            ValueError: If share not found
        """
        try:
            share = self.file_shares.find_one(
                {"share_id": share_id, "owner_id": owner_id}
            )

            if not share:
                raise ValueError("Share not found or you don't own this share")

            result = self.file_shares.update_one(
                {"share_id": share_id},
                {
                    "$set": {
                        "is_active": False,
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )

            if result.modified_count > 0:
                logger.info(f"🚫 Share revoked: {share_id}")
                return True

            return False

        except ValueError as e:
            logger.warning(f"⚠️ Share revoke failed: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Error revoking share: {e}")
            raise

    def validate_share_access(
        self, share_id: str, user_id: str, required_permission: str = "view"
    ) -> Dict[str, Any]:
        """
        Validate if user has access to shared file

        Args:
            share_id: Share ID
            user_id: User's ID
            required_permission: Required permission level

        Returns:
            Share document if valid

        Raises:
            ValueError: If access denied
        """
        try:
            # Find share
            share = self.file_shares.find_one(
                {"share_id": share_id, "recipient_id": user_id, "is_active": True}
            )

            if not share:
                raise ValueError("Share not found or access denied")

            # Check expiration
            expires_at = share.get("expires_at")
            if expires_at and expires_at < datetime.now(timezone.utc):
                raise ValueError("Share has expired")

            # Check permission
            permission_levels = {"view": 1, "download": 2, "edit": 3}
            user_permission = permission_levels.get(share.get("permission", "view"), 1)
            required_level = permission_levels.get(required_permission, 1)

            if user_permission < required_level:
                raise ValueError(
                    f"Insufficient permission. Required: {required_permission}, You have: {share.get('permission')}"
                )

            logger.info(f"✅ Share access validated: {share_id} | {user_id}")

            return share

        except ValueError as e:
            logger.warning(f"⚠️ Share access validation failed: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Error validating share access: {e}")
            raise

    def log_share_access(
        self,
        share_id: str,
        user_id: str,
        action: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> bool:
        """
        Log share access for audit trail

        Args:
            share_id: Share ID
            user_id: User's ID
            action: Action performed (view, download, edit)
            ip_address: Optional IP address
            user_agent: Optional user agent

        Returns:
            True if logged successfully
        """
        try:
            log_id = f"log_{uuid.uuid4().hex[:16]}"

            log_doc = {
                "log_id": log_id,
                "share_id": share_id,
                "user_id": user_id,
                "action": action,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "accessed_at": datetime.now(timezone.utc),
            }

            self.share_access_logs.insert_one(log_doc)

            logger.info(f"📝 Share access logged: {share_id} | {action} by {user_id}")

            return True

        except Exception as e:
            logger.error(f"❌ Error logging share access: {e}")
            # Don't raise - logging failure shouldn't block access
            return False

    def get_share_logs(
        self, share_id: str, owner_id: str, limit: int = 100, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get access logs for a share (owner only)

        Args:
            share_id: Share ID
            owner_id: Owner's user ID (for verification)
            limit: Max results
            offset: Pagination offset

        Returns:
            List of access log documents

        Raises:
            ValueError: If share not found or not owner
        """
        try:
            # Verify ownership
            share = self.file_shares.find_one(
                {"share_id": share_id, "owner_id": owner_id}
            )

            if not share:
                raise ValueError("Share not found or you don't own this share")

            # Get logs
            logs = list(
                self.share_access_logs.find({"share_id": share_id})
                .sort("accessed_at", -1)
                .skip(offset)
                .limit(limit)
            )

            logger.info(f"📊 Retrieved {len(logs)} access logs for share: {share_id}")

            return logs

        except ValueError as e:
            logger.warning(f"⚠️ Get share logs failed: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Error getting share logs: {e}")
            raise

    def get_share_by_id(self, share_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get share details by share_id
        User must be either owner or recipient

        Args:
            share_id: Share ID
            user_id: User's ID

        Returns:
            Share document or None

        Raises:
            ValueError: If access denied
        """
        try:
            share = self.file_shares.find_one(
                {
                    "share_id": share_id,
                    "$or": [{"owner_id": user_id}, {"recipient_id": user_id}],
                }
            )

            if not share:
                raise ValueError("Share not found or access denied")

            return share

        except ValueError as e:
            logger.warning(f"⚠️ Get share by ID failed: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Error getting share by ID: {e}")
            raise

    def check_user_exists_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Kiểm tra user có tồn tại trong hệ thống bằng email

        Args:
            email: Email cần check

        Returns:
            User document nếu tồn tại, None nếu không tìm thấy
        """
        try:
            user = self.users.find_one({"email": email})

            if user:
                logger.info(f"✅ Found user with email: {email}")
                return {
                    "user_id": user.get(
                        "firebase_uid"
                    ),  # Return firebase_uid as user_id
                    "email": user.get("email"),
                    "name": user.get("display_name", ""),
                    "display_name": user.get("display_name", ""),
                }
            else:
                logger.info(f"❌ User not found with email: {email}")
                return None

        except Exception as e:
            logger.error(f"❌ Error checking user by email: {e}")
            return None

    def list_file_shares(
        self, file_id: str, owner_id: str, limit: int = 100, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Lấy danh sách tất cả users đã được share file cụ thể
        Chỉ owner mới có quyền xem

        Args:
            file_id: File ID cần lấy danh sách shares
            owner_id: Owner ID (để verify quyền)
            limit: Số lượng kết quả tối đa
            offset: Offset cho pagination

        Returns:
            List of share documents với thông tin user
        """
        try:
            # Verify owner
            shares = list(
                self.file_shares.find({"file_id": file_id, "owner_id": owner_id})
                .sort("created_at", -1)
                .skip(offset)
                .limit(limit)
            )

            # Enrich với thông tin user
            result = []
            for share in shares:
                recipient_id = share.get("recipient_id")

                # Skip shares without recipient_id (invalid data)
                if not recipient_id:
                    logger.warning(
                        f"⚠️ Share {share.get('share_id')} has no recipient_id, skipping"
                    )
                    continue

                # Query user by firebase_uid instead of user_id
                user = self.users.find_one({"firebase_uid": recipient_id})

                share_info = {
                    "share_id": share.get("share_id", ""),
                    "recipient_id": recipient_id,
                    "recipient_email": share.get("recipient_email", ""),
                    "recipient_name": user.get("display_name", "") if user else "",
                    "recipient_display_name": (
                        user.get("display_name", "") if user else ""
                    ),
                    "permission": share.get("permission", "view"),
                    "is_active": share.get("is_active", True),
                    "expires_at": share.get("expires_at"),
                    "created_at": share.get("created_at"),
                    "updated_at": share.get("updated_at"),
                }
                result.append(share_info)

            logger.info(
                f"✅ Listed {len(result)} shares for file {file_id} by owner {owner_id}"
            )
            return result

        except Exception as e:
            logger.error(f"❌ Error listing file shares: {e}")
            return []
