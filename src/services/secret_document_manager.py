"""
Secret Document Manager Service
Handles E2EE secret document CRUD operations
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from pymongo.database import Database
from pymongo import ASCENDING, DESCENDING
import uuid

logger = logging.getLogger(__name__)


class SecretDocumentManager:
    """
    Manages E2EE secret documents with zero-knowledge encryption

    Server can only:
    - Store encrypted content
    - Store encrypted file keys per user
    - Manage access control
    - Audit logging

    Server CANNOT:
    - Decrypt document content
    - Read plaintext data
    - Access user private keys
    """

    def __init__(self, db: Database):
        self.db = db
        self.secret_documents = db["secret_documents"]
        self.secret_access_logs = db["secret_access_logs"]
        self.documents = db["documents"]  # For conversion
        logger.info("✅ SecretDocumentManager initialized")

    # ============ CREATE ============

    def create_secret_document(
        self,
        owner_id: str,
        title: str,
        document_type: str,  # "doc" | "slide" | "note"
        encrypted_content: str,
        encryption_iv: str,
        encrypted_file_key: str,  # Owner's encrypted file key
        folder_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Create new E2EE secret document

        Args:
            owner_id: Firebase UID of document owner
            title: Document title (plaintext for listing)
            document_type: "doc" | "slide" | "note"
            encrypted_content: AES-256-GCM encrypted HTML content
            encryption_iv: Initialization Vector for AES
            encrypted_file_key: File key encrypted with owner's public RSA key
            folder_id: Optional folder ID
            tags: Optional tags for organization

        Returns:
            Created secret document dict
        """
        try:
            secret_id = f"secret_{uuid.uuid4().hex[:12]}"
            now = datetime.utcnow()

            secret_doc = {
                "secret_id": secret_id,
                "owner_id": owner_id,
                "title": title,
                "document_type": document_type,
                "source": "created",  # "created" vs "converted"
                # E2EE Data
                "encrypted_content": encrypted_content,
                "encryption_iv": encryption_iv,
                "encrypted_file_keys": {
                    owner_id: encrypted_file_key,
                },
                # Organization
                "folder_id": folder_id,
                "tags": tags or [],
                # Metadata
                "created_at": now,
                "updated_at": now,
                "last_accessed_at": now,
                # Access control
                "shared_with": [],  # List of user_ids with access
                "is_trashed": False,
                "trashed_at": None,
                # Conversion tracking (if converted from regular doc)
                "converted_from_document_id": None,
                "conversion_action": None,
            }

            result = self.secret_documents.insert_one(secret_doc)

            if result.inserted_id:
                logger.info(
                    f"✅ Created secret document {secret_id} for user {owner_id}"
                )

                # Log creation
                self._log_access(
                    secret_id=secret_id,
                    user_id=owner_id,
                    action="create",
                    ip_address=None,
                    user_agent=None,
                )

                return secret_doc
            else:
                raise Exception("Failed to insert secret document")

        except Exception as e:
            logger.error(f"❌ Error creating secret document: {e}")
            raise

    # ============ CONVERT ============

    def convert_document_to_secret(
        self,
        document_id: str,
        owner_id: str,
        encrypted_content: str,
        encryption_iv: str,
        encrypted_file_key: str,
        conversion_action: str,  # "keep_shares" | "remove_shares"
        share_encrypted_file_keys: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Convert existing document to secret document

        Args:
            document_id: Original document ID
            owner_id: Firebase UID of document owner
            encrypted_content: Encrypted version of document content
            encryption_iv: AES IV
            encrypted_file_key: Owner's encrypted file key
            conversion_action: "keep_shares" or "remove_shares"
            share_encrypted_file_keys: If keeping shares, encrypted file keys for each shared user

        Returns:
            Created secret document dict
        """
        try:
            # Get original document
            original_doc = self.documents.find_one({"document_id": document_id})
            if not original_doc:
                raise ValueError(f"Document {document_id} not found")

            # Verify ownership
            if original_doc["user_id"] != owner_id:
                raise ValueError("Only document owner can convert to secret")

            secret_id = f"secret_{uuid.uuid4().hex[:12]}"
            now = datetime.utcnow()

            # Prepare shared users and file keys
            shared_with = []
            encrypted_file_keys = {owner_id: encrypted_file_key}

            if conversion_action == "keep_shares" and share_encrypted_file_keys:
                shared_with = list(share_encrypted_file_keys.keys())
                encrypted_file_keys.update(share_encrypted_file_keys)

            secret_doc = {
                "secret_id": secret_id,
                "owner_id": owner_id,
                "title": original_doc["title"],
                "document_type": original_doc["document_type"],
                "source": "converted",
                # E2EE Data
                "encrypted_content": encrypted_content,
                "encryption_iv": encryption_iv,
                "encrypted_file_keys": encrypted_file_keys,
                # Organization
                "folder_id": original_doc.get("folder_id"),
                "tags": original_doc.get("tags", []),
                # Metadata
                "created_at": now,
                "updated_at": now,
                "last_accessed_at": now,
                # Access control
                "shared_with": shared_with,
                "is_trashed": False,
                "trashed_at": None,
                # Conversion tracking
                "converted_from_document_id": document_id,
                "conversion_action": conversion_action,
            }

            result = self.secret_documents.insert_one(secret_doc)

            if result.inserted_id:
                # Mark original document as converted
                self.documents.update_one(
                    {"document_id": document_id},
                    {
                        "$set": {
                            "converted_to_secret": True,
                            "secret_document_id": secret_id,
                            "converted_at": now,
                        }
                    },
                )

                logger.info(
                    f"✅ Converted document {document_id} to secret {secret_id} "
                    f"(action: {conversion_action})"
                )

                # Log conversion
                self._log_access(
                    secret_id=secret_id,
                    user_id=owner_id,
                    action="convert",
                    ip_address=None,
                    user_agent=None,
                    metadata={
                        "original_document_id": document_id,
                        "conversion_action": conversion_action,
                    },
                )

                return secret_doc
            else:
                raise Exception("Failed to convert document to secret")

        except Exception as e:
            logger.error(f"❌ Error converting document to secret: {e}")
            raise

    # ============ READ ============

    def get_secret_document(
        self, secret_id: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get secret document by ID

        Args:
            secret_id: Secret document ID
            user_id: Firebase UID requesting access

        Returns:
            Secret document dict with encrypted_file_key for this user
        """
        try:
            secret_doc = self.secret_documents.find_one({"secret_id": secret_id})

            if not secret_doc:
                return None

            # Check access
            if not self._has_access(secret_doc, user_id):
                logger.warning(
                    f"⚠️ User {user_id} attempted unauthorized access to {secret_id}"
                )
                return None

            # Update last accessed
            self.secret_documents.update_one(
                {"secret_id": secret_id},
                {"$set": {"last_accessed_at": datetime.utcnow()}},
            )

            # Log access
            self._log_access(
                secret_id=secret_id,
                user_id=user_id,
                action="read",
                ip_address=None,
                user_agent=None,
            )

            # Return with user's encrypted file key
            result = dict(secret_doc)
            result["user_encrypted_file_key"] = secret_doc["encrypted_file_keys"].get(
                user_id
            )

            # Remove other users' keys for privacy
            result.pop("encrypted_file_keys", None)

            return result

        except Exception as e:
            logger.error(f"❌ Error getting secret document: {e}")
            raise

    # ============ UPDATE ============

    def update_secret_document(
        self,
        secret_id: str,
        user_id: str,
        encrypted_content: str,
        encryption_iv: str,
    ) -> bool:
        """
        Update secret document content
        Only owner can update

        Args:
            secret_id: Secret document ID
            user_id: Firebase UID
            encrypted_content: New encrypted content
            encryption_iv: New IV

        Returns:
            Success boolean
        """
        try:
            secret_doc = self.secret_documents.find_one({"secret_id": secret_id})

            if not secret_doc:
                raise ValueError("Secret document not found")

            # Only owner can update
            if secret_doc["owner_id"] != user_id:
                raise ValueError("Only owner can update secret document")

            result = self.secret_documents.update_one(
                {"secret_id": secret_id},
                {
                    "$set": {
                        "encrypted_content": encrypted_content,
                        "encryption_iv": encryption_iv,
                        "updated_at": datetime.utcnow(),
                    }
                },
            )

            if result.modified_count > 0:
                logger.info(f"✅ Updated secret document {secret_id}")

                # Log update
                self._log_access(
                    secret_id=secret_id,
                    user_id=user_id,
                    action="update",
                    ip_address=None,
                    user_agent=None,
                )

                return True
            else:
                return False

        except Exception as e:
            logger.error(f"❌ Error updating secret document: {e}")
            raise

    # ============ UPDATE METADATA ============

    def update_secret_metadata(
        self,
        secret_id: str,
        user_id: str,
        title: Optional[str] = None,
        folder_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> bool:
        """
        Update secret document metadata (not encrypted content)
        Only owner can update
        """
        try:
            secret_doc = self.secret_documents.find_one({"secret_id": secret_id})

            if not secret_doc:
                raise ValueError("Secret document not found")

            if secret_doc["owner_id"] != user_id:
                raise ValueError("Only owner can update metadata")

            update_fields = {"updated_at": datetime.utcnow()}

            if title is not None:
                update_fields["title"] = title
            if folder_id is not None:
                update_fields["folder_id"] = folder_id
            if tags is not None:
                update_fields["tags"] = tags

            result = self.secret_documents.update_one(
                {"secret_id": secret_id}, {"$set": update_fields}
            )

            return result.modified_count > 0

        except Exception as e:
            logger.error(f"❌ Error updating secret metadata: {e}")
            raise

    # ============ LIST ============

    def list_secret_documents(
        self,
        user_id: str,
        folder_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        List user's secret documents (owned or shared)

        Returns list of documents WITHOUT encrypted content (for listing UI)
        """
        try:
            query = {
                "$or": [
                    {"owner_id": user_id},
                    {"shared_with": user_id},
                ],
                "is_trashed": False,
            }

            if folder_id:
                query["folder_id"] = folder_id

            cursor = (
                self.secret_documents.find(
                    query,
                    {
                        "encrypted_content": 0,  # Don't return content in list
                        "encrypted_file_keys": 0,  # Don't return keys in list
                    },
                )
                .sort("updated_at", DESCENDING)
                .skip(skip)
                .limit(limit)
            )

            documents = list(cursor)

            # Add access type
            for doc in documents:
                doc["access_type"] = "owner" if doc["owner_id"] == user_id else "shared"

            return documents

        except Exception as e:
            logger.error(f"❌ Error listing secret documents: {e}")
            raise

    def list_shared_with_me(
        self, user_id: str, skip: int = 0, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List secret documents shared with user"""
        try:
            cursor = (
                self.secret_documents.find(
                    {
                        "shared_with": user_id,
                        "is_trashed": False,
                    },
                    {
                        "encrypted_content": 0,
                        "encrypted_file_keys": 0,
                    },
                )
                .sort("updated_at", DESCENDING)
                .skip(skip)
                .limit(limit)
            )

            return list(cursor)

        except Exception as e:
            logger.error(f"❌ Error listing shared documents: {e}")
            raise

    # ============ TRASH ============

    def trash_secret_document(self, secret_id: str, user_id: str) -> bool:
        """Move secret document to trash (soft delete). Only owner can trash."""
        try:
            secret_doc = self.secret_documents.find_one({"secret_id": secret_id})

            if not secret_doc:
                raise ValueError("Secret document not found")

            if secret_doc["owner_id"] != user_id:
                raise ValueError("Only owner can trash secret document")

            result = self.secret_documents.update_one(
                {"secret_id": secret_id},
                {
                    "$set": {
                        "is_trashed": True,
                        "trashed_at": datetime.utcnow(),
                    }
                },
            )

            if result.modified_count > 0:
                logger.info(f"✅ Trashed secret document {secret_id}")

                self._log_access(
                    secret_id=secret_id,
                    user_id=user_id,
                    action="trash",
                    ip_address=None,
                    user_agent=None,
                )

                return True

            return False

        except Exception as e:
            logger.error(f"❌ Error trashing secret document: {e}")
            raise

    # ============ SHARING ============

    def share_secret_document(
        self,
        secret_id: str,
        owner_id: str,
        recipient_id: str,
        encrypted_file_key_for_recipient: str,
    ) -> bool:
        """
        Share secret document with another user

        Args:
            secret_id: Secret document ID
            owner_id: Document owner Firebase UID
            recipient_id: Recipient Firebase UID
            encrypted_file_key_for_recipient: File key encrypted with recipient's public key

        Returns:
            Success boolean
        """
        try:
            secret_doc = self.secret_documents.find_one({"secret_id": secret_id})

            if not secret_doc:
                raise ValueError("Secret document not found")

            if secret_doc["owner_id"] != owner_id:
                raise ValueError("Only owner can share secret document")

            # Add recipient to shared_with and store encrypted key
            result = self.secret_documents.update_one(
                {"secret_id": secret_id},
                {
                    "$addToSet": {"shared_with": recipient_id},
                    "$set": {
                        f"encrypted_file_keys.{recipient_id}": encrypted_file_key_for_recipient,
                        "updated_at": datetime.utcnow(),
                    },
                },
            )

            if result.modified_count > 0:
                logger.info(
                    f"✅ Shared secret document {secret_id} with user {recipient_id}"
                )

                self._log_access(
                    secret_id=secret_id,
                    user_id=owner_id,
                    action="share",
                    ip_address=None,
                    user_agent=None,
                    metadata={"recipient_id": recipient_id},
                )

                return True

            return False

        except Exception as e:
            logger.error(f"❌ Error sharing secret document: {e}")
            raise

    def revoke_secret_share(
        self, secret_id: str, owner_id: str, user_id_to_revoke: str
    ) -> bool:
        """Revoke access to secret document. Only owner can revoke."""
        try:
            secret_doc = self.secret_documents.find_one({"secret_id": secret_id})

            if not secret_doc:
                raise ValueError("Secret document not found")

            if secret_doc["owner_id"] != owner_id:
                raise ValueError("Only owner can revoke access")

            result = self.secret_documents.update_one(
                {"secret_id": secret_id},
                {
                    "$pull": {"shared_with": user_id_to_revoke},
                    "$unset": {f"encrypted_file_keys.{user_id_to_revoke}": ""},
                    "$set": {"updated_at": datetime.utcnow()},
                },
            )

            if result.modified_count > 0:
                logger.info(
                    f"✅ Revoked access to {secret_id} from user {user_id_to_revoke}"
                )

                self._log_access(
                    secret_id=secret_id,
                    user_id=owner_id,
                    action="revoke",
                    ip_address=None,
                    user_agent=None,
                    metadata={"revoked_user_id": user_id_to_revoke},
                )

                return True

            return False

        except Exception as e:
            logger.error(f"❌ Error revoking secret share: {e}")
            raise

    # ============ AUDIT LOGS ============

    def get_access_logs(
        self, secret_id: str, owner_id: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get access logs for secret document. Only owner can view logs."""
        try:
            # Verify ownership
            secret_doc = self.secret_documents.find_one({"secret_id": secret_id})
            if not secret_doc or secret_doc["owner_id"] != owner_id:
                raise ValueError("Only owner can view access logs")

            cursor = (
                self.secret_access_logs.find({"secret_id": secret_id})
                .sort("timestamp", DESCENDING)
                .limit(limit)
            )

            return list(cursor)

        except Exception as e:
            logger.error(f"❌ Error getting access logs: {e}")
            raise

    # ============ HELPER METHODS ============

    def _has_access(self, secret_doc: Dict[str, Any], user_id: str) -> bool:
        """Check if user has access to secret document"""
        return (
            secret_doc["owner_id"] == user_id
            or user_id in secret_doc.get("shared_with", [])
        ) and not secret_doc.get("is_trashed", False)

    def _log_access(
        self,
        secret_id: str,
        user_id: str,
        action: str,
        ip_address: Optional[str],
        user_agent: Optional[str],
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Log access to secret document"""
        try:
            log_entry = {
                "log_id": f"log_{uuid.uuid4().hex[:12]}",
                "secret_id": secret_id,
                "user_id": user_id,
                "action": action,
                "timestamp": datetime.utcnow(),
                "ip_address": ip_address,
                "user_agent": user_agent,
                "metadata": metadata or {},
            }

            self.secret_access_logs.insert_one(log_entry)

        except Exception as e:
            logger.error(f"❌ Error logging access: {e}")
            # Don't raise - logging failure shouldn't block operations

    # ============ INDEXES ============

    def create_indexes(self):
        """Create database indexes for secret documents"""
        try:
            # Secret documents indexes
            self.secret_documents.create_index([("secret_id", ASCENDING)], unique=True)
            self.secret_documents.create_index([("owner_id", ASCENDING)])
            self.secret_documents.create_index([("shared_with", ASCENDING)])
            self.secret_documents.create_index([("folder_id", ASCENDING)])
            self.secret_documents.create_index([("is_trashed", ASCENDING)])
            self.secret_documents.create_index([("updated_at", DESCENDING)])
            self.secret_documents.create_index(
                [("owner_id", ASCENDING), ("is_trashed", ASCENDING)]
            )

            # Access logs indexes
            self.secret_access_logs.create_index([("log_id", ASCENDING)], unique=True)
            self.secret_access_logs.create_index([("secret_id", ASCENDING)])
            self.secret_access_logs.create_index([("user_id", ASCENDING)])
            self.secret_access_logs.create_index([("timestamp", DESCENDING)])

            logger.info("✅ Secret document indexes created successfully")

        except Exception as e:
            logger.error(f"❌ Error creating indexes: {e}")
            raise
