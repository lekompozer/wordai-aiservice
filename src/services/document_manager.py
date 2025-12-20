"""
Document Manager Service
Quản lý documents trong MongoDB với auto-save functionality
Using synchronous PyMongo to maintain compatibility with production
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
import logging

# Use 'chatbot' logger to match app.py logging configuration
logger = logging.getLogger("chatbot")


class DocumentManager:
    """Quản lý documents trong MongoDB - Synchronous PyMongo"""

    def __init__(self, db):
        """
        Initialize DocumentManager

        Args:
            db: PyMongo Database object (synchronous) từ DBManager
        """
        self.db = db
        self.documents = db["documents"]

    def create_indexes(self):
        """Tạo indexes cho collection documents"""
        try:
            # Check existing indexes
            existing_indexes = [idx["name"] for idx in self.documents.list_indexes()]

            # Document ID index (unique)
            if "document_id_1_unique" not in existing_indexes:
                self.documents.create_index(
                    "document_id", unique=True, sparse=True, name="document_id_1_unique"
                )
                logger.info("✅ Created index: document_id_1_unique")

            # User documents listing index
            if "user_id_1_last_opened_at_-1" not in existing_indexes:
                self.documents.create_index(
                    [("user_id", 1), ("last_opened_at", -1)],
                    name="user_id_1_last_opened_at_-1",
                )
                logger.info("✅ Created index: user_id_1_last_opened_at_-1")

            # File ID lookup index
            if "file_id_1" not in existing_indexes:
                self.documents.create_index("file_id", name="file_id_1")
                logger.info("✅ Created index: file_id_1")

            # Filter deleted documents index
            if "user_id_1_is_deleted_1" not in existing_indexes:
                self.documents.create_index(
                    [("user_id", 1), ("is_deleted", 1)], name="user_id_1_is_deleted_1"
                )
                logger.info("✅ Created index: user_id_1_is_deleted_1")

            # Folder filter index for efficient folder queries
            if "user_id_1_folder_id_1" not in existing_indexes:
                self.documents.create_index(
                    [("user_id", 1), ("folder_id", 1)], name="user_id_1_folder_id_1"
                )
                logger.info("✅ Created index: user_id_1_folder_id_1")

            logger.info("✅ Document indexes verified/created")
        except Exception as e:
            logger.error(f"❌ Error creating indexes: {e}")
            raise

    def get_document_by_file_id(
        self, file_id: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Lấy document theo file_id (deprecated - use count/get_latest instead)"""
        document = self.documents.find_one(
            {"file_id": file_id, "user_id": user_id, "is_deleted": False}
        )
        return document

    def count_documents_by_file_id(self, file_id: str, user_id: str) -> int:
        """Đếm số lượng documents đã tạo từ file_id này"""
        count = self.documents.count_documents(
            {"file_id": file_id, "user_id": user_id, "is_deleted": False}
        )
        logger.info(f"📊 Found {count} existing documents for file {file_id}")
        return count

    def get_latest_document_by_file_id(
        self, file_id: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Lấy document mới nhất từ file_id (để reuse content)"""
        document = self.documents.find_one(
            {"file_id": file_id, "user_id": user_id, "is_deleted": False},
            sort=[("created_at", -1)],  # Sort by newest first
        )
        if document:
            logger.info(
                f"📄 Found latest document {document['document_id']} for content reuse"
            )
        return document

    def create_document(
        self,
        user_id: str,
        title: str,
        content_html: str,
        content_text: str,
        source_type: str = "file",
        document_type: Optional[str] = None,
        file_id: Optional[str] = None,
        original_r2_url: Optional[str] = None,
        original_file_type: Optional[str] = None,
        folder_id: Optional[str] = None,
    ) -> str:
        """
        Tạo document mới, trả về document_id

        Args:
            source_type: "file" (từ upload) hoặc "created" (tạo mới)
            document_type: "doc", "slide", "note" (chỉ cho created documents)
            file_id: Optional - chỉ có khi source_type="file"
            folder_id: Optional - folder to organize document
        """
        document_id = f"doc_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow()

        document = {
            "document_id": document_id,
            "user_id": user_id,
            "title": title,
            "content_html": content_html,
            "content_text": content_text,
            "version": 1,
            "auto_save_count": 0,
            "manual_save_count": 1,  # Lần tạo = manual save
            # Source tracking
            "source_type": source_type,  # "file" | "created"
            "document_type": document_type,  # "doc" | "slide" | "note" (for created)
            # File reference (optional)
            "file_id": file_id,
            "original_r2_url": original_r2_url,
            "original_file_type": original_file_type,
            # Organization
            "folder_id": folder_id,
            "file_size_bytes": len(content_html.encode("utf-8")),
            "created_at": now,
            "last_saved_at": now,
            "last_auto_save_at": None,
            "last_manual_save_at": now,
            "last_opened_at": now,
            "is_deleted": False,
            "deleted_at": None,
        }

        self.documents.insert_one(document)

        if source_type == "created":
            logger.info(
                f"✅ Created NEW document {document_id} (type: {document_type})"
            )
        else:
            logger.info(f"✅ Created document {document_id} for file {file_id}")

        return document_id

    def get_document(self, document_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Lấy document theo ID và update last_opened_at"""
        document = self.documents.find_one(
            {"document_id": document_id, "user_id": user_id, "is_deleted": False}
        )

        if document:
            # Update last_opened_at
            self.documents.update_one(
                {"document_id": document_id},
                {"$set": {"last_opened_at": datetime.utcnow()}},
            )

            # ✅ Ensure slide_elements is returned (default to empty array for slides)
            if "slide_elements" not in document:
                document["slide_elements"] = []
                logger.info(
                    f"📄 [SLIDE_ELEMENTS_LOAD] document_id={document_id}, user_id={user_id}, slide_elements=[] (no stored overlays)"
                )
            else:
                # Count total elements
                slide_elements = document["slide_elements"]
                total_elements = (
                    sum(len(slide.get("elements", [])) for slide in slide_elements)
                    if slide_elements
                    else 0
                )
                logger.info(
                    f"🎨 [SLIDE_ELEMENTS_LOAD] document_id={document_id}, user_id={user_id}, "
                    f"slides={len(slide_elements)}, total_overlay_elements={total_elements}"
                )

            logger.info(f"📄 Loaded document {document_id}")

        return document

    def update_document(
        self,
        document_id: str,
        user_id: str,
        content_html: str,
        content_text: Optional[str] = None,
        title: Optional[str] = None,
        is_auto_save: bool = False,
        slide_elements: Optional[list] = None,
        slide_backgrounds: Optional[list] = None,
    ) -> bool:
        """Cập nhật nội dung document (bao gồm title, slide_elements, và slide_backgrounds cho slide documents)"""
        now = datetime.utcnow()

        update_data = {
            "content_html": content_html,
            "file_size_bytes": len(content_html.encode("utf-8")),
            "last_saved_at": now,
        }

        if content_text:
            update_data["content_text"] = content_text

        # Update title if provided
        if title is not None:
            update_data["title"] = title

        # ✅ Save slide_elements separately (only for slide documents)
        if slide_elements is not None:
            update_data["slide_elements"] = slide_elements
            # Count total elements across all slides
            total_elements = sum(
                len(slide.get("elements", [])) for slide in slide_elements
            )
            logger.info(
                f"🎨 [SLIDE_ELEMENTS_SAVE] Preparing to save: document_id={document_id}, "
                f"user_id={user_id}, slides={len(slide_elements)}, "
                f"total_overlay_elements={total_elements}"
            )
        else:
            logger.info(
                f"📄 [SLIDE_ELEMENTS_SAVE] No overlay elements to save: document_id={document_id}, "
                f"user_id={user_id}"
            )

        # ✅ NEW: Save slide_backgrounds separately (only for slide documents)
        if slide_backgrounds is not None:
            update_data["slide_backgrounds"] = slide_backgrounds
            logger.info(
                f"🎨 [SLIDE_BACKGROUNDS_SAVE] Preparing to save: document_id={document_id}, "
                f"user_id={user_id}, slides_with_backgrounds={len(slide_backgrounds)}"
            )
        else:
            logger.info(
                f"📄 [SLIDE_BACKGROUNDS_SAVE] No backgrounds to save: document_id={document_id}, "
                f"user_id={user_id}"
            )

        if is_auto_save:
            update_data["last_auto_save_at"] = now
        else:
            update_data["last_manual_save_at"] = now

        # Use $inc for version and save counts
        inc_data = {
            "version": 1,
            "auto_save_count" if is_auto_save else "manual_save_count": 1,
        }

        result = self.documents.update_one(
            {"document_id": document_id, "user_id": user_id, "is_deleted": False},
            {"$set": update_data, "$inc": inc_data},
        )

        if result.modified_count > 0:
            save_type = "auto-saved" if is_auto_save else "manually saved"
            title_info = f" (title: {title})" if title else ""

            # ✅ Enhanced logging for slide_elements and slide_backgrounds database confirmation
            log_parts = [f"✅ [DB_SAVED] Document {document_id} {save_type}"]

            if slide_elements is not None:
                total_elements = sum(
                    len(slide.get("elements", [])) for slide in slide_elements
                )
                log_parts.append(f"{len(slide_elements)} slides with {total_elements} overlay elements")

            if slide_backgrounds is not None:
                log_parts.append(f"{len(slide_backgrounds)} slides with backgrounds")

            log_parts.append(f"(version +1){title_info}")
            logger.info(" ".join(log_parts))
                )
            return True

        logger.warning(f"⚠️ Document {document_id} not found or not modified")
        return False

    def list_user_documents(
        self,
        user_id: str,
        limit: int = 20,
        offset: int = 0,
        source_type: Optional[str] = None,
        document_type: Optional[str] = None,
        folder_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Lấy danh sách documents của user, sắp xếp theo last_opened_at

        Args:
            source_type: Filter by "file" hoặc "created"
            document_type: Filter by "doc", "slide", "note" (chỉ cho created)
            folder_id: Filter by folder ID
        """
        query = {"user_id": user_id, "is_deleted": False}

        # Add filters
        if source_type:
            query["source_type"] = source_type

        if document_type:
            query["document_type"] = document_type

        if folder_id is not None:
            query["folder_id"] = folder_id

        documents = list(
            self.documents.find(query)
            .sort("last_opened_at", -1)
            .skip(offset)
            .limit(limit)
        )

        logger.info(
            f"📋 Listed {len(documents)} documents for user {user_id} "
            f"(source={source_type}, type={document_type}, folder={folder_id})"
        )
        return documents

    def delete_document(
        self, document_id: str, user_id: str, soft_delete: bool = True
    ) -> bool:
        """Xóa document (soft hoặc hard delete)"""
        if soft_delete:
            result = self.documents.update_one(
                {"document_id": document_id, "user_id": user_id},
                {"$set": {"is_deleted": True, "deleted_at": datetime.utcnow()}},
            )
            success = result.modified_count > 0
            if success:
                logger.info(f"🗑️ Document {document_id} soft deleted")
        else:
            result = self.documents.delete_one(
                {"document_id": document_id, "user_id": user_id}
            )
            success = result.deleted_count > 0
            if success:
                logger.info(f"🗑️ Document {document_id} permanently deleted")

        return success

    def move_document_to_folder(
        self, document_id: str, user_id: str, folder_id: Optional[str]
    ) -> bool:
        """
        Di chuyển document sang folder khác

        Args:
            document_id: ID của document cần move
            user_id: ID của user sở hữu document
            folder_id: ID của folder đích (None để move về root)

        Returns:
            True nếu move thành công, False nếu không tìm thấy document
        """
        result = self.documents.update_one(
            {"document_id": document_id, "user_id": user_id, "is_deleted": False},
            {"$set": {"folder_id": folder_id}},
        )

        if result.modified_count > 0:
            folder_info = (
                f"to folder {folder_id}" if folder_id else "to root (ungrouped)"
            )
            logger.info(f"📁 Document {document_id} moved {folder_info}")
            return True

        logger.warning(
            f"⚠️ Document {document_id} not found or already in target folder"
        )
        return False

    def get_storage_stats(self, user_id: str) -> Dict[str, Any]:
        """Lấy thống kê storage của user"""
        pipeline = [
            {"$match": {"user_id": user_id, "is_deleted": False}},
            {
                "$group": {
                    "_id": None,
                    "total_documents": {"$sum": 1},
                    "total_bytes": {"$sum": "$file_size_bytes"},
                    "total_versions": {"$sum": "$version"},
                    "total_auto_saves": {"$sum": "$auto_save_count"},
                    "total_manual_saves": {"$sum": "$manual_save_count"},
                }
            },
        ]

        result = list(self.documents.aggregate(pipeline))

        if result:
            stats = result[0]
            stats.pop("_id")
            # Convert to MB
            stats["total_mb"] = round(stats["total_bytes"] / (1024 * 1024), 2)
            logger.info(
                f"📊 Storage stats for user {user_id}: {stats['total_documents']} docs, {stats['total_mb']} MB"
            )
            return stats

        return {
            "total_documents": 0,
            "total_bytes": 0,
            "total_mb": 0,
            "total_versions": 0,
            "total_auto_saves": 0,
            "total_manual_saves": 0,
        }

    def list_trash_documents(
        self, user_id: str, limit: int = 100, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Lấy danh sách documents trong trash"""
        documents = list(
            self.documents.find({"user_id": user_id, "is_deleted": True})
            .sort("deleted_at", -1)
            .skip(offset)
            .limit(limit)
        )

        logger.info(f"🗑️ Listed {len(documents)} documents in trash for user {user_id}")
        return documents

    def restore_document(self, document_id: str, user_id: str) -> bool:
        """Khôi phục document từ trash"""
        result = self.documents.update_one(
            {"document_id": document_id, "user_id": user_id, "is_deleted": True},
            {"$set": {"is_deleted": False, "deleted_at": None}},
        )

        if result.modified_count > 0:
            logger.info(f"♻️ Document {document_id} restored from trash")
            return True

        logger.warning(f"⚠️ Document {document_id} not found in trash")
        return False

    def empty_trash(self, user_id: str) -> int:
        """Xóa vĩnh viễn tất cả documents trong trash"""
        result = self.documents.delete_many({"user_id": user_id, "is_deleted": True})

        deleted_count = result.deleted_count
        logger.info(
            f"🗑️ Permanently deleted {deleted_count} documents from trash for user {user_id}"
        )
        return deleted_count

    def get_documents_by_folders(
        self,
        user_id: str,
        source_type: Optional[str] = None,
        document_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Lấy tất cả documents của user, nhóm theo folders

        Returns list of folders with their documents:
        [
            {
                "folder_id": None,
                "folder_name": None,
                "folder_description": None,
                "document_count": 3,
                "documents": [...]
            },
            {
                "folder_id": "folder_abc",
                "folder_name": "Work Documents",
                "folder_description": "...",
                "document_count": 5,
                "documents": [...]
            }
        ]
        """
        # Build query
        query = {"user_id": user_id, "is_deleted": False}

        if source_type:
            query["source_type"] = source_type

        if document_type:
            query["document_type"] = document_type

        # Get all documents sorted by last_opened_at
        all_documents = list(self.documents.find(query).sort("last_opened_at", -1))

        # Get all folders for this user from document_folders collection
        folders_collection = self.db[
            "document_folders"
        ]  # ✅ Dùng document_folders thay vì folders
        all_user_folders = list(folders_collection.find({"user_id": user_id}))
        user_folders = {folder["folder_id"]: folder for folder in all_user_folders}

        # Group documents by folder_id
        documents_by_folder: Dict[Optional[str], List[Dict[str, Any]]] = {}

        for doc in all_documents:
            folder_id = doc.get("folder_id")
            if folder_id not in documents_by_folder:
                documents_by_folder[folder_id] = []
            documents_by_folder[folder_id].append(doc)

        # Add empty folders (folders with no documents)
        for folder in all_user_folders:
            folder_id = folder["folder_id"]
            if folder_id not in documents_by_folder:
                documents_by_folder[folder_id] = []  # Empty folder

        # Build response with folder info
        result = []

        # Sort folder keys: None first (ungrouped), then others alphabetically
        sorted_folder_ids = sorted(
            documents_by_folder.keys(), key=lambda x: (x is not None, x or "")
        )

        for folder_id in sorted_folder_ids:
            docs = documents_by_folder[folder_id]
            folder_info = user_folders.get(folder_id) if folder_id else None

            result.append(
                {
                    "folder_id": folder_id,
                    "folder_name": folder_info["name"] if folder_info else None,
                    "folder_description": (
                        folder_info.get("description") if folder_info else None
                    ),
                    "document_count": len(docs),
                    "documents": docs,
                }
            )

        total_docs = sum(len(docs) for docs in documents_by_folder.values())

        logger.info(
            f"📁 Grouped {total_docs} documents into {len(result)} folders "
            f"for user {user_id} (source={source_type}, type={document_type})"
        )

        return result


# Global instance
from src.config.database import get_db_manager

db_manager = get_db_manager()
document_manager = DocumentManager(db=db_manager.db)
