"""
Library Manager Service
Handles library files (Type 3) - Reference materials, templates, guides
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from pymongo import MongoClient
from pymongo.database import Database
import uuid

logger = logging.getLogger("chatbot")


class LibraryManager:
    """
    Quản lý thư viện files (Type 3)
    - 4 categories: templates, guides, references, resources
    - Tags support
    - Full-text search
    - Trash management
    """

    def __init__(self, db: Database, s3_client=None):
        """
        Initialize LibraryManager

        Args:
            db: MongoDB database instance
            s3_client: boto3 S3 client for R2
        """
        self.db = db
        self.library_files = db["library_files"]
        self.s3_client = s3_client

        logger.info("✅ LibraryManager initialized")

    def create_indexes(self):
        """
        Tạo indexes cho library_files collection
        Run này một lần duy nhất khi setup database
        """
        try:
            # Unique library_id
            self.library_files.create_index("library_id", unique=True, sparse=True)

            # User queries
            self.library_files.create_index("user_id")
            self.library_files.create_index([("user_id", 1), ("category", 1)])
            self.library_files.create_index([("user_id", 1), ("tags", 1)])
            self.library_files.create_index([("user_id", 1), ("uploaded_at", -1)])
            self.library_files.create_index([("user_id", 1), ("is_deleted", 1)])

            # Text search
            self.library_files.create_index(
                [("filename", "text"), ("description", "text")]
            )

            logger.info("✅ Library files indexes created successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Error creating indexes: {e}")
            return False

    def _detect_category_from_file_type(self, file_type: str, filename: str) -> str:
        """
        Auto-detect category based on MIME type or file extension

        Categories:
        - documents: PDF, Word, Excel, PPT, Text files
        - images: JPG, PNG, GIF, SVG, WebP, etc.
        - videos: MP4, AVI, MOV, WebM, etc.
        - audio: MP3, WAV, OGG, etc.

        Args:
            file_type: MIME type (e.g., "image/jpeg")
            filename: Original filename for extension fallback

        Returns:
            Category string: "documents", "images", "videos", or "audio"
        """
        file_type_lower = file_type.lower()

        # Check MIME type first
        if file_type_lower.startswith("image/"):
            return "images"
        elif file_type_lower.startswith("video/"):
            return "videos"
        elif file_type_lower.startswith("audio/"):
            return "audio"

        # Document MIME types
        document_mimes = [
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-powerpoint",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "text/plain",
            "text/csv",
            "application/json",
            "application/xml",
            "text/html",
        ]

        if any(mime in file_type_lower for mime in document_mimes):
            return "documents"

        # Fallback: Check file extension
        if "." in filename:
            ext = filename.split(".")[-1].lower()

            # Image extensions
            if ext in [
                "jpg",
                "jpeg",
                "png",
                "gif",
                "svg",
                "webp",
                "bmp",
                "ico",
                "tiff",
                "tif",
            ]:
                return "images"

            # Video extensions
            elif ext in ["mp4", "avi", "mov", "wmv", "flv", "webm", "mkv", "m4v"]:
                return "videos"

            # Audio extensions
            elif ext in ["mp3", "wav", "ogg", "m4a", "flac", "aac", "wma"]:
                return "audio"

            # Document extensions
            elif ext in [
                "pdf",
                "doc",
                "docx",
                "xls",
                "xlsx",
                "ppt",
                "pptx",
                "txt",
                "csv",
                "json",
                "xml",
                "html",
            ]:
                return "documents"

        # Default: documents
        return "documents"

    def upload_library_file(
        self,
        user_id: str,
        filename: str,
        file_type: str,
        file_size: int,
        r2_key: str,
        file_url: str,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Upload file to library with auto-categorization

        Category is auto-detected from file_type/extension:
        - documents: PDF, Word, Excel, PPT, Text files
        - images: JPG, PNG, GIF, SVG, WebP
        - videos: MP4, AVI, MOV, WebM
        - audio: MP3, WAV, OGG, M4A

        Args:
            user_id: Firebase UID
            filename: Original filename
            file_type: MIME type
            file_size: File size in bytes
            r2_key: R2 storage key
            file_url: R2 URL
            description: Optional description
            tags: Optional tags list
            metadata: Optional metadata (dimensions, duration, etc.)

        Returns:
            Library file document
        """
        try:
            now = datetime.now(timezone.utc)
            library_id = f"lib_{uuid.uuid4().hex[:12]}"

            # Auto-detect category from file type
            category = self._detect_category_from_file_type(file_type, filename)

            library_doc = {
                # 🔄 SYNCHRONIZED SCHEMA với upload files
                "file_id": library_id,  # Đổi từ library_id → file_id để đồng bộ
                "library_id": library_id,  # Giữ lại để backward compatibility
                "user_id": user_id,
                "filename": filename,  # Tên file đã được sanitize
                "original_name": filename,  # Thêm original_name để đồng bộ
                "file_type": file_type,
                "file_size": file_size,
                "folder_id": None,  # Library files không có folder, để None
                "r2_key": r2_key,
                "file_url": file_url,
                # 📚 Library-specific fields
                "category": category,
                "description": description or "",
                "tags": tags or [],
                "metadata": metadata or {},
                # 🗑️ Deletion tracking
                "is_deleted": False,
                "deleted_at": None,
                # ⏰ Timestamps
                "uploaded_at": now,
                "updated_at": now,
            }

            result = self.library_files.insert_one(library_doc)

            if result.inserted_id:
                logger.info(f"📚 Library file uploaded: {library_id} ({category})")
                return library_doc
            else:
                raise Exception("Failed to insert library file")

        except Exception as e:
            logger.error(f"❌ Error uploading library file: {e}")
            raise

    def list_library_files(
        self,
        user_id: str,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        List library files with optional filters

        Args:
            user_id: Firebase UID
            category: Filter by category (optional)
            tags: Filter by tags (optional)
            limit: Max results
            offset: Pagination offset

        Returns:
            List of library file documents
        """
        try:
            query = {"user_id": user_id, "is_deleted": False}

            if category:
                query["category"] = category

            if tags and len(tags) > 0:
                query["tags"] = {"$all": tags}

            files = list(
                self.library_files.find(query)
                .sort("uploaded_at", -1)
                .skip(offset)
                .limit(limit)
            )

            logger.info(
                f"📚 Listed {len(files)} library files for user {user_id} "
                f"(category={category}, tags={tags})"
            )
            return files

        except Exception as e:
            logger.error(f"❌ Error listing library files: {e}")
            return []

    def get_library_file(
        self, library_id: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get single library file

        Args:
            library_id: Library file ID
            user_id: Firebase UID (for authorization)

        Returns:
            Library file document or None
        """
        try:
            file_doc = self.library_files.find_one(
                {"library_id": library_id, "user_id": user_id}
            )

            if file_doc:
                logger.info(f"📚 Retrieved library file: {library_id}")
            else:
                logger.warning(f"⚠️ Library file not found: {library_id}")

            return file_doc

        except Exception as e:
            logger.error(f"❌ Error getting library file {library_id}: {e}")
            return None

    def update_library_metadata(
        self,
        library_id: str,
        user_id: str,
        filename: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> bool:
        """
        Update library file metadata

        Args:
            library_id: Library file ID
            user_id: Firebase UID (for authorization)
            filename: New filename (optional)
            description: New description (optional)
            category: New category (optional)
            tags: New tags list (optional)

        Returns:
            Success status
        """
        try:
            update_fields = {"updated_at": datetime.now(timezone.utc)}

            if filename is not None:
                update_fields["filename"] = filename

            if description is not None:
                update_fields["description"] = description

            if category is not None:
                valid_categories = ["templates", "guides", "references", "resources"]
                if category not in valid_categories:
                    raise ValueError(
                        f"Invalid category. Must be one of: {valid_categories}"
                    )
                update_fields["category"] = category

            if tags is not None:
                update_fields["tags"] = tags

            result = self.library_files.update_one(
                {"library_id": library_id, "user_id": user_id},
                {"$set": update_fields},
            )

            if result.modified_count > 0:
                logger.info(f"📚 Library file updated: {library_id}")
                return True
            else:
                logger.warning(
                    f"⚠️ Library file not found or not modified: {library_id}"
                )
                return False

        except Exception as e:
            logger.error(f"❌ Error updating library file {library_id}: {e}")
            return False

    def soft_delete_library_file(self, library_id: str, user_id: str) -> bool:
        """
        Soft delete library file (move to trash)

        Args:
            library_id: Library file ID
            user_id: Firebase UID (for authorization)

        Returns:
            Success status
        """
        try:
            now = datetime.now(timezone.utc)

            result = self.library_files.update_one(
                {"library_id": library_id, "user_id": user_id},
                {"$set": {"is_deleted": True, "deleted_at": now}},
            )

            if result.modified_count > 0:
                logger.info(f"🗑️ Library file soft deleted: {library_id}")
                return True
            else:
                logger.warning(f"⚠️ Library file not found: {library_id}")
                return False

        except Exception as e:
            logger.error(f"❌ Error soft deleting library file {library_id}: {e}")
            return False

    def restore_library_file(self, library_id: str, user_id: str) -> bool:
        """
        Restore library file from trash

        Args:
            library_id: Library file ID
            user_id: Firebase UID (for authorization)

        Returns:
            Success status
        """
        try:
            result = self.library_files.update_one(
                {"library_id": library_id, "user_id": user_id, "is_deleted": True},
                {"$set": {"is_deleted": False, "deleted_at": None}},
            )

            if result.modified_count > 0:
                logger.info(f"♻️ Library file restored: {library_id}")
                return True
            else:
                logger.warning(f"⚠️ Library file not found in trash: {library_id}")
                return False

        except Exception as e:
            logger.error(f"❌ Error restoring library file {library_id}: {e}")
            return False

    def delete_library_file_permanent(self, library_id: str, user_id: str) -> bool:
        """
        Permanently delete library file from R2 and MongoDB
        ⚠️ WARNING: This cannot be undone!

        Args:
            library_id: Library file ID
            user_id: Firebase UID (for authorization)

        Returns:
            Success status
        """
        try:
            # 1. Get file info
            file_doc = self.library_files.find_one(
                {"library_id": library_id, "user_id": user_id}
            )

            if not file_doc:
                logger.warning(f"⚠️ Library file not found: {library_id}")
                return False

            # 2. Delete from R2 if exists
            r2_key = file_doc.get("r2_key")
            if r2_key and self.s3_client:
                try:
                    from config.config import R2_BUCKET_NAME

                    self.s3_client.delete_object(Bucket=R2_BUCKET_NAME, Key=r2_key)
                    logger.info(f"🗑️ Deleted R2 file: {r2_key}")
                except Exception as e:
                    logger.error(f"❌ Error deleting R2 file {r2_key}: {e}")
                    # Continue to delete MongoDB record anyway

            # 3. Delete from MongoDB
            result = self.library_files.delete_one(
                {"library_id": library_id, "user_id": user_id}
            )

            if result.deleted_count > 0:
                logger.info(f"🗑️ Library file permanently deleted: {library_id}")
                return True
            else:
                logger.warning(
                    f"⚠️ Failed to delete library file from MongoDB: {library_id}"
                )
                return False

        except Exception as e:
            logger.error(
                f"❌ Error permanently deleting library file {library_id}: {e}"
            )
            return False

    def list_deleted_library_files(
        self, user_id: str, limit: int = 100, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List deleted library files (trash)

        Args:
            user_id: Firebase UID
            limit: Max results
            offset: Pagination offset

        Returns:
            List of deleted library file documents
        """
        try:
            files = list(
                self.library_files.find({"user_id": user_id, "is_deleted": True})
                .sort("deleted_at", -1)
                .skip(offset)
                .limit(limit)
            )

            logger.info(
                f"🗑️ Listed {len(files)} deleted library files for user {user_id}"
            )
            return files

        except Exception as e:
            logger.error(f"❌ Error listing deleted library files: {e}")
            return []

    def empty_library_trash(self, user_id: str) -> int:
        """
        Permanently delete ALL library files in trash
        ⚠️ WARNING: This cannot be undone!

        Args:
            user_id: Firebase UID

        Returns:
            Number of files deleted
        """
        try:
            # 1. Get all deleted files
            deleted_files = self.list_deleted_library_files(
                user_id=user_id, limit=10000
            )

            deleted_count = 0

            # 2. Delete each file from R2 and MongoDB
            for file_doc in deleted_files:
                library_id = file_doc.get("library_id")
                if self.delete_library_file_permanent(
                    library_id=library_id, user_id=user_id
                ):
                    deleted_count += 1

            logger.info(
                f"🗑️ Emptied library trash: {deleted_count} files deleted for user {user_id}"
            )
            return deleted_count

        except Exception as e:
            logger.error(f"❌ Error emptying library trash: {e}")
            return 0

    def search_library(
        self,
        user_id: str,
        query: str,
        category: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Full-text search in library files

        Args:
            user_id: Firebase UID
            query: Search query (searches filename and description)
            category: Optional category filter
            limit: Max results

        Returns:
            List of matching library file documents
        """
        try:
            # Build search query
            search_query = {
                "user_id": user_id,
                "is_deleted": False,
                "$text": {"$search": query},
            }

            if category:
                search_query["category"] = category

            # Execute search with text score
            files = list(
                self.library_files.find(search_query, {"score": {"$meta": "textScore"}})
                .sort([("score", {"$meta": "textScore"})])
                .limit(limit)
            )

            logger.info(
                f"🔍 Search '{query}' returned {len(files)} results for user {user_id}"
            )
            return files

        except Exception as e:
            logger.error(f"❌ Error searching library: {e}")
            return []

    def get_library_stats(self, user_id: str) -> Dict[str, Any]:
        """
        Get library statistics for user

        Args:
            user_id: Firebase UID

        Returns:
            Statistics dictionary
        """
        try:
            pipeline = [
                {"$match": {"user_id": user_id, "is_deleted": False}},
                {
                    "$group": {
                        "_id": "$category",
                        "count": {"$sum": 1},
                        "total_size": {"$sum": "$file_size"},
                    }
                },
            ]

            results = list(self.library_files.aggregate(pipeline))

            stats = {
                "total_files": 0,
                "total_bytes": 0,
                "by_category": {},
            }

            for item in results:
                category = item["_id"]
                count = item["count"]
                size = item["total_size"]

                stats["total_files"] += count
                stats["total_bytes"] += size
                stats["by_category"][category] = {
                    "count": count,
                    "size_bytes": size,
                }

            logger.info(
                f"📊 Library stats for user {user_id}: {stats['total_files']} files"
            )
            return stats

        except Exception as e:
            logger.error(f"❌ Error getting library stats: {e}")
            return {"total_files": 0, "total_bytes": 0, "by_category": {}}

    def save_library_file(
        self,
        user_id: str,
        filename: str,
        file_type: str,
        category: str,
        r2_url: str,
        r2_key: str,
        file_size: int,
        mime_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Save file to library with specific category (for audio service)

        Args:
            user_id: Firebase UID
            filename: Original filename
            file_type: File type (e.g., "audio")
            category: Category (e.g., "audio")
            r2_url: Public R2 URL
            r2_key: R2 storage key
            file_size: File size in bytes
            mime_type: MIME type
            metadata: Optional metadata (linked_to, voice_settings, etc.)

        Returns:
            Library file document
        """
        try:
            now = datetime.now(timezone.utc)
            library_id = f"lib_{uuid.uuid4().hex[:12]}"

            library_doc = {
                "file_id": library_id,
                "library_id": library_id,
                "user_id": user_id,
                "filename": filename,
                "original_name": filename,
                "file_type": file_type,
                "category": category,
                "file_size": file_size,
                "mime_type": mime_type,
                "r2_key": r2_key,
                "file_url": r2_url,
                "r2_url": r2_url,
                "metadata": metadata or {},
                "is_deleted": False,
                "deleted_at": None,
                "uploaded_at": now,
                "updated_at": now,
                "created_at": now,
            }

            result = self.library_files.insert_one(library_doc)

            if result.inserted_id:
                logger.info(
                    f"✅ Library file saved: {library_id} ({category}) for user {user_id}"
                )
                return library_doc
            else:
                raise Exception("Failed to insert library file")

        except Exception as e:
            logger.error(f"❌ Error saving library file: {e}")
            raise
