"""
Encrypted Folder Manager Service
Folder management for E2EE Library Images
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class EncryptedFolderManager:
    """Manage folders for encrypted library images"""

    def __init__(self, db):
        """
        Initialize EncryptedFolderManager

        Args:
            db: MongoDB database instance
        """
        self.db = db
        self.collection = db["library_folders"]
        logger.info("✅ EncryptedFolderManager initialized")

    def create_indexes(self) -> bool:
        """
        Create indexes for library_folders collection

        Returns:
            bool: True if successful
        """
        try:
            # Index for owner queries
            self.collection.create_index([("owner_id", 1), ("is_deleted", 1)])

            # Index for parent folder queries
            self.collection.create_index([("owner_id", 1), ("parent_folder_id", 1)])

            # Index for folder_id (unique)
            self.collection.create_index([("folder_id", 1)], unique=True)

            logger.info("✅ Folder indexes created")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to create folder indexes: {e}")
            return False

    def create_folder(
        self,
        owner_id: str,
        name: str,
        parent_folder_id: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new folder

        Args:
            owner_id: Firebase UID of owner
            name: Folder name
            parent_folder_id: Parent folder ID (None = root level)
            description: Optional folder description

        Returns:
            Dict: Created folder document
        """
        try:
            # Validate parent folder exists if provided
            if parent_folder_id:
                parent = self.collection.find_one(
                    {
                        "folder_id": parent_folder_id,
                        "owner_id": owner_id,
                        "is_deleted": False,
                    }
                )
                if not parent:
                    raise ValueError("Parent folder not found")

            # Build path
            path = []
            if parent_folder_id:
                parent = self.collection.find_one({"folder_id": parent_folder_id})
                if parent:
                    path = parent.get("path", []) + [parent_folder_id]

            folder_id = f"folder_{uuid.uuid4().hex[:12]}"
            now = datetime.utcnow()

            folder_doc = {
                "folder_id": folder_id,
                "owner_id": owner_id,
                "name": name,
                "description": description,
                "parent_folder_id": parent_folder_id,
                "path": path,
                "created_at": now,
                "updated_at": now,
                "deleted_at": None,
                "is_deleted": False,
            }

            self.collection.insert_one(folder_doc)

            # Remove _id before returning
            folder_doc.pop("_id", None)

            logger.info(f"✅ Folder created: {folder_id} by {owner_id}")
            return folder_doc

        except Exception as e:
            logger.error(f"❌ Error creating folder: {e}")
            raise

    def list_folders(
        self,
        owner_id: str,
        parent_folder_id: Optional[str] = None,
        include_deleted: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        List folders for a user

        Args:
            owner_id: Firebase UID of owner
            parent_folder_id: Filter by parent folder (None = root level folders)
            include_deleted: Include soft-deleted folders

        Returns:
            List[Dict]: List of folder documents
        """
        try:
            query = {"owner_id": owner_id}

            # Filter by parent
            if parent_folder_id is None:
                # Root level folders (no parent)
                query["$or"] = [
                    {"parent_folder_id": None},
                    {"parent_folder_id": {"$exists": False}},
                ]
            else:
                query["parent_folder_id"] = parent_folder_id

            # Filter deleted
            if not include_deleted:
                query["is_deleted"] = False

            folders = list(self.collection.find(query).sort("name", 1))

            # Remove MongoDB _id field
            for folder in folders:
                folder.pop("_id", None)

            logger.info(f"📂 Listed {len(folders)} folders for {owner_id}")
            return folders

        except Exception as e:
            logger.error(f"❌ Error listing folders: {e}")
            raise

    def get_folder(self, folder_id: str, owner_id: str) -> Optional[Dict[str, Any]]:
        """
        Get folder by ID

        Args:
            folder_id: Folder ID
            owner_id: Firebase UID of owner

        Returns:
            Dict or None: Folder document
        """
        try:
            folder = self.collection.find_one(
                {"folder_id": folder_id, "owner_id": owner_id}
            )

            if folder:
                folder.pop("_id", None)

            return folder

        except Exception as e:
            logger.error(f"❌ Error getting folder: {e}")
            raise

    def update_folder(
        self,
        folder_id: str,
        owner_id: str,
        updates: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Update folder metadata

        Args:
            folder_id: Folder ID
            owner_id: Firebase UID of owner
            updates: Dictionary of fields to update

        Returns:
            Dict or None: Updated folder document
        """
        try:
            # Validate folder exists and user owns it
            folder = self.get_folder(folder_id=folder_id, owner_id=owner_id)
            if not folder:
                return None

            # Validate parent folder if moving
            if "parent_folder_id" in updates and updates["parent_folder_id"]:
                parent = self.collection.find_one(
                    {
                        "folder_id": updates["parent_folder_id"],
                        "owner_id": owner_id,
                        "is_deleted": False,
                    }
                )
                if not parent:
                    raise ValueError("Parent folder not found")

                # Prevent circular reference
                if updates["parent_folder_id"] == folder_id:
                    raise ValueError("Cannot move folder into itself")

                # Update path
                parent_path = parent.get("path", [])
                if folder_id in parent_path:
                    raise ValueError("Cannot create circular folder structure")

                updates["path"] = parent_path + [updates["parent_folder_id"]]

            # Add updated_at
            updates["updated_at"] = datetime.utcnow()

            # Update document
            result = self.collection.find_one_and_update(
                {"folder_id": folder_id, "owner_id": owner_id},
                {"$set": updates},
                return_document=True,
            )

            if result:
                result.pop("_id", None)
                logger.info(f"✅ Folder updated: {folder_id}")

            return result

        except Exception as e:
            logger.error(f"❌ Error updating folder: {e}")
            raise

    def soft_delete_folder(self, folder_id: str, owner_id: str) -> bool:
        """
        Soft delete folder (mark as deleted)

        Args:
            folder_id: Folder ID
            owner_id: Firebase UID of owner

        Returns:
            bool: True if successful
        """
        try:
            result = self.collection.update_one(
                {"folder_id": folder_id, "owner_id": owner_id},
                {
                    "$set": {
                        "is_deleted": True,
                        "deleted_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                    }
                },
            )

            if result.modified_count > 0:
                logger.info(f"🗑️ Folder soft deleted: {folder_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"❌ Error soft deleting folder: {e}")
            raise

    def restore_folder(self, folder_id: str, owner_id: str) -> bool:
        """
        Restore soft-deleted folder

        Args:
            folder_id: Folder ID
            owner_id: Firebase UID of owner

        Returns:
            bool: True if successful
        """
        try:
            result = self.collection.update_one(
                {"folder_id": folder_id, "owner_id": owner_id, "is_deleted": True},
                {
                    "$set": {
                        "is_deleted": False,
                        "deleted_at": None,
                        "updated_at": datetime.utcnow(),
                    }
                },
            )

            if result.modified_count > 0:
                logger.info(f"♻️ Folder restored: {folder_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"❌ Error restoring folder: {e}")
            raise

    def delete_folder_permanent(self, folder_id: str, owner_id: str) -> bool:
        """
        Permanently delete folder and all subfolders
        Images in the folder are NOT deleted, just lose folder reference

        Args:
            folder_id: Folder ID
            owner_id: Firebase UID of owner

        Returns:
            bool: True if successful
        """
        try:
            # Delete folder
            result = self.collection.delete_one(
                {"folder_id": folder_id, "owner_id": owner_id}
            )

            if result.deleted_count > 0:
                # Delete all subfolders (where folder_id is in path)
                self.collection.delete_many({"owner_id": owner_id, "path": folder_id})

                logger.info(f"🗑️ Folder permanently deleted: {folder_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"❌ Error permanently deleting folder: {e}")
            raise
