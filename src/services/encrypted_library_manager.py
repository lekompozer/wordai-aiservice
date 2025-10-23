"""
Encrypted Library Manager Service
Handles E2EE (End-to-End Encrypted) library images
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from pymongo.database import Database
import uuid

logger = logging.getLogger(__name__)


class EncryptedLibraryManager:
    """
    Quản lý thư viện ảnh được mã hóa đầu-cuối (E2EE)

    Features:
    - Upload encrypted images (with encrypted thumbnails)
    - Client-side encryption (AES-256-GCM)
    - RSA-encrypted file keys
    - Sharing with multiple users
    - Zero-knowledge architecture (server never sees plaintext)
    """

    def __init__(self, db: Database, s3_client=None):
        """
        Initialize EncryptedLibraryManager

        Args:
            db: MongoDB database instance
            s3_client: boto3 S3 client for R2
        """
        self.db = db
        self.library_images = db["library_images"]
        self.s3_client = s3_client

        logger.info("✅ EncryptedLibraryManager initialized")

    def create_indexes(self):
        """
        Tạo indexes cho library_images collection
        Run này một lần duy nhất khi setup database
        """
        try:
            # Unique image_id
            self.library_images.create_index("image_id", unique=True, sparse=True)

            # Owner queries
            self.library_images.create_index("owner_id")
            self.library_images.create_index([("owner_id", 1), ("created_at", -1)])
            self.library_images.create_index([("owner_id", 1), ("is_encrypted", 1)])
            self.library_images.create_index([("owner_id", 1), ("is_deleted", 1)])

            # Sharing queries
            self.library_images.create_index("shared_with")

            # Folder organization
            self.library_images.create_index([("owner_id", 1), ("folder_id", 1)])

            # Tags
            self.library_images.create_index([("owner_id", 1), ("tags", 1)])

            logger.info("✅ Library images (encrypted) indexes created successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Error creating library_images indexes: {e}")
            return False

    def upload_encrypted_image(
        self,
        owner_id: str,
        filename: str,
        file_size: int,
        r2_image_path: str,
        r2_thumbnail_path: str,
        encrypted_file_key: str,
        encryption_iv_original: str,
        encryption_iv_thumbnail: str,
        image_width: Optional[int] = None,
        image_height: Optional[int] = None,
        thumbnail_width: Optional[int] = None,
        thumbnail_height: Optional[int] = None,
        encrypted_exif: Optional[str] = None,
        encryption_iv_exif: Optional[str] = None,
        folder_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        description: str = "",
    ) -> Dict[str, Any]:
        """
        Upload encrypted image to library

        Args:
            owner_id: Firebase UID of owner
            filename: Original filename
            file_size: Size of original encrypted file
            r2_image_path: R2 path for encrypted image
            r2_thumbnail_path: R2 path for encrypted thumbnail
            encrypted_file_key: RSA-OAEP encrypted AES file key (base64)
            encryption_iv_original: IV for original image (base64, 12 bytes)
            encryption_iv_thumbnail: IV for thumbnail (base64, 12 bytes)
            image_width: Original image width (pixels)
            image_height: Original image height (pixels)
            thumbnail_width: Thumbnail width (pixels)
            thumbnail_height: Thumbnail height (pixels)
            encrypted_exif: Encrypted EXIF data (base64, optional)
            encryption_iv_exif: IV for EXIF (base64, 12 bytes, optional)
            folder_id: Optional folder for organization
            tags: Optional tags for search
            description: Optional description

        Returns:
            Created document dict
        """
        try:
            image_id = f"img_{uuid.uuid4().hex[:12]}"
            now = datetime.now(timezone.utc)

            # Initialize encrypted_file_keys with owner's key
            encrypted_file_keys = {owner_id: encrypted_file_key}

            doc = {
                "image_id": image_id,
                "owner_id": owner_id,
                "filename": filename,
                "description": description,
                "file_size": file_size,
                "tags": tags or [],
                "folder_id": folder_id,
                # Encryption flag
                "is_encrypted": True,
                # Encrypted file keys (one per user with access)
                "encrypted_file_keys": encrypted_file_keys,
                # IVs for decryption
                "encryption_iv_original": encryption_iv_original,
                "encryption_iv_thumbnail": encryption_iv_thumbnail,
                "encryption_iv_exif": encryption_iv_exif if encrypted_exif else None,
                # Encrypted EXIF data
                "encrypted_exif": encrypted_exif,
                # Image dimensions
                "image_width": image_width,
                "image_height": image_height,
                "thumbnail_width": thumbnail_width,
                "thumbnail_height": thumbnail_height,
                # R2 storage paths
                "r2_image_path": r2_image_path,
                "r2_thumbnail_path": r2_thumbnail_path,
                # Sharing
                "shared_with": [],  # Will be populated when sharing
                # Timestamps
                "created_at": now,
                "updated_at": now,
                "deleted_at": None,
                "is_deleted": False,
            }

            result = self.library_images.insert_one(doc)

            if result.inserted_id:
                logger.info(f"🔐 Encrypted image uploaded: {image_id} by {owner_id}")
                return doc
            else:
                raise Exception("Failed to insert document")

        except Exception as e:
            logger.error(f"❌ Error uploading encrypted image: {e}")
            raise

    def get_encrypted_image(
        self, image_id: str, user_id: str, include_deleted: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Get encrypted image metadata by ID

        Args:
            image_id: Image ID
            user_id: Requesting user ID (for access check)
            include_deleted: Whether to include soft-deleted images

        Returns:
            Image document or None if not found/no access
        """
        try:
            query = {
                "image_id": image_id,
                "$or": [{"owner_id": user_id}, {"shared_with": user_id}],
            }

            if not include_deleted:
                query["is_deleted"] = False

            doc = self.library_images.find_one(query)

            if doc:
                # Remove MongoDB's _id for cleaner response
                doc.pop("_id", None)
                return doc

            return None

        except Exception as e:
            logger.error(f"❌ Error getting encrypted image {image_id}: {e}")
            return None

    def list_encrypted_images(
        self,
        owner_id: str,
        folder_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        search_filename: Optional[str] = None,
        include_shared: bool = False,
        include_deleted: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        List encrypted images for a user

        Args:
            owner_id: User ID
            folder_id: Filter by folder
            tags: Filter by tags (OR condition)
            search_filename: Search by filename (case-insensitive regex)
            include_shared: Include images shared with user
            include_deleted: Include soft-deleted images
            limit: Max results
            offset: Skip results

        Returns:
            List of image documents
        """
        try:
            # Build query
            if include_shared:
                # Owner OR shared with user
                query = {"$or": [{"owner_id": owner_id}, {"shared_with": owner_id}]}
            else:
                # Owner only
                query = {"owner_id": owner_id}

            # Folder filter
            if folder_id:
                query["folder_id"] = folder_id

            # Tags filter (OR)
            if tags and len(tags) > 0:
                query["tags"] = {"$in": tags}

            # Filename search (case-insensitive)
            if search_filename:
                query["filename"] = {"$regex": search_filename, "$options": "i"}

            # Deleted filter
            if not include_deleted:
                query["is_deleted"] = False

            # Execute query
            cursor = (
                self.library_images.find(query)
                .sort("created_at", -1)
                .skip(offset)
                .limit(limit)
            )

            results = []
            for doc in cursor:
                doc.pop("_id", None)
                results.append(doc)

            logger.info(f"📚 Listed {len(results)} encrypted images for {owner_id}")
            return results

        except Exception as e:
            logger.error(f"❌ Error listing encrypted images: {e}")
            return []

    def count_encrypted_images(
        self,
        owner_id: str,
        folder_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        search_filename: Optional[str] = None,
        include_shared: bool = False,
        include_deleted: bool = False,
    ) -> int:
        """
        Count encrypted images for pagination

        Args:
            owner_id: User ID
            folder_id: Filter by folder
            tags: Filter by tags (OR condition)
            search_filename: Search by filename
            include_shared: Include images shared with user
            include_deleted: Include soft-deleted images

        Returns:
            Total count of images matching filters
        """
        try:
            # Build same query as list_encrypted_images
            if include_shared:
                query = {"$or": [{"owner_id": owner_id}, {"shared_with": owner_id}]}
            else:
                query = {"owner_id": owner_id}

            if folder_id:
                query["folder_id"] = folder_id

            if tags and len(tags) > 0:
                query["tags"] = {"$in": tags}

            if search_filename:
                query["filename"] = {"$regex": search_filename, "$options": "i"}

            if not include_deleted:
                query["is_deleted"] = False

            count = self.library_images.count_documents(query)

            return count

        except Exception as e:
            logger.error(f"❌ Error counting encrypted images: {e}")
            return 0

    def add_share_access(
        self,
        image_id: str,
        owner_id: str,
        recipient_id: str,
        encrypted_file_key_for_recipient: str,
    ) -> bool:
        """
        Share encrypted image with another user

        Args:
            image_id: Image ID
            owner_id: Owner user ID (for verification)
            recipient_id: Recipient user ID
            encrypted_file_key_for_recipient: File key encrypted with recipient's public key

        Returns:
            True if successful
        """
        try:
            # Verify owner
            image = self.library_images.find_one(
                {"image_id": image_id, "owner_id": owner_id, "is_deleted": False}
            )

            if not image:
                logger.warning(
                    f"⚠️ Image {image_id} not found or user {owner_id} is not owner"
                )
                return False

            # Update document
            result = self.library_images.update_one(
                {"image_id": image_id},
                {
                    "$set": {
                        f"encrypted_file_keys.{recipient_id}": encrypted_file_key_for_recipient,
                        "updated_at": datetime.now(timezone.utc),
                    },
                    "$addToSet": {"shared_with": recipient_id},
                },
            )

            if result.modified_count > 0:
                logger.info(f"🤝 Image {image_id} shared with {recipient_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"❌ Error sharing image {image_id}: {e}")
            return False

    def revoke_share_access(
        self,
        image_id: str,
        owner_id: str,
        recipient_id: str,
    ) -> bool:
        """
        Revoke share access for a user

        Args:
            image_id: Image ID
            owner_id: Owner user ID (for verification)
            recipient_id: Recipient user ID to revoke

        Returns:
            True if successful
        """
        try:
            # Verify owner
            image = self.library_images.find_one(
                {"image_id": image_id, "owner_id": owner_id, "is_deleted": False}
            )

            if not image:
                logger.warning(
                    f"⚠️ Image {image_id} not found or user {owner_id} is not owner"
                )
                return False

            # Update document
            result = self.library_images.update_one(
                {"image_id": image_id},
                {
                    "$unset": {f"encrypted_file_keys.{recipient_id}": ""},
                    "$pull": {"shared_with": recipient_id},
                    "$set": {"updated_at": datetime.now(timezone.utc)},
                },
            )

            if result.modified_count > 0:
                logger.info(f"🚫 Image {image_id} access revoked for {recipient_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"❌ Error revoking access for image {image_id}: {e}")
            return False

    def soft_delete_image(
        self,
        image_id: str,
        owner_id: str,
    ) -> bool:
        """
        Soft delete an image (mark as deleted, don't remove R2 files yet)

        Args:
            image_id: Image ID
            owner_id: Owner user ID (for verification)

        Returns:
            True if successful
        """
        try:
            result = self.library_images.update_one(
                {"image_id": image_id, "owner_id": owner_id, "is_deleted": False},
                {
                    "$set": {
                        "is_deleted": True,
                        "deleted_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )

            if result.modified_count > 0:
                logger.info(f"🗑️ Image {image_id} soft deleted by {owner_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"❌ Error soft deleting image {image_id}: {e}")
            return False

    def restore_image(
        self,
        image_id: str,
        owner_id: str,
    ) -> bool:
        """
        Restore a soft-deleted image

        Args:
            image_id: Image ID
            owner_id: Owner user ID (for verification)

        Returns:
            True if successful
        """
        try:
            result = self.library_images.update_one(
                {"image_id": image_id, "owner_id": owner_id, "is_deleted": True},
                {
                    "$set": {
                        "is_deleted": False,
                        "deleted_at": None,
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )

            if result.modified_count > 0:
                logger.info(f"♻️ Image {image_id} restored by {owner_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"❌ Error restoring image {image_id}: {e}")
            return False

    def update_image_metadata(
        self,
        image_id: str,
        owner_id: str,
        updates: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Update image metadata (filename, description, tags, folder_id)

        Args:
            image_id: Image ID
            owner_id: Owner user ID (for verification)
            updates: Dictionary of fields to update

        Returns:
            Updated image document or None if not found
        """
        try:
            # Validate folder exists if updating folder_id
            if "folder_id" in updates and updates["folder_id"]:
                from config.config import get_mongodb

                db = get_mongodb()
                folder_collection = db["library_folders"]

                folder = folder_collection.find_one(
                    {
                        "folder_id": updates["folder_id"],
                        "owner_id": owner_id,
                        "is_deleted": False,
                    }
                )

                if not folder:
                    raise ValueError("Folder not found or you don't have access")

            # Add updated_at timestamp
            updates["updated_at"] = datetime.now(timezone.utc)

            # Update the document
            result = self.library_images.find_one_and_update(
                {"image_id": image_id, "owner_id": owner_id},
                {"$set": updates},
                return_document=True,
            )

            if result:
                logger.info(f"✅ Image metadata updated: {image_id}")

            return result

        except Exception as e:
            logger.error(f"❌ Error updating image metadata {image_id}: {e}")
            raise
