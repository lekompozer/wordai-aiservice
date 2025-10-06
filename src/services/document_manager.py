"""
Document Manager Service
Quản lý documents trong MongoDB với auto-save functionality
Using synchronous PyMongo to maintain compatibility with production
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


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

            logger.info("✅ Document indexes verified/created")
        except Exception as e:
            logger.error(f"❌ Error creating indexes: {e}")
            raise

    def get_document_by_file_id(
        self, file_id: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Lấy document theo file_id"""
        document = self.documents.find_one(
            {"file_id": file_id, "user_id": user_id, "is_deleted": False}
        )
        return document

    def create_document(
        self,
        user_id: str,
        file_id: str,
        title: str,
        content_html: str,
        content_text: str,
        original_r2_url: str,
        original_file_type: str,
    ) -> str:
        """Tạo document mới, trả về document_id"""
        document_id = f"doc_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow()

        document = {
            "document_id": document_id,
            "user_id": user_id,
            "file_id": file_id,
            "title": title,
            "content_html": content_html,
            "content_text": content_text,
            "version": 1,
            "auto_save_count": 0,
            "manual_save_count": 1,  # Lần tạo = manual save
            "original_r2_url": original_r2_url,
            "original_file_type": original_file_type,
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
            logger.info(f"📄 Loaded document {document_id}")

        return document

    def update_document(
        self,
        document_id: str,
        user_id: str,
        content_html: str,
        content_text: Optional[str] = None,
        is_auto_save: bool = False,
    ) -> bool:
        """Cập nhật nội dung document"""
        now = datetime.utcnow()

        update_data = {
            "content_html": content_html,
            "file_size_bytes": len(content_html.encode("utf-8")),
            "last_saved_at": now,
        }

        if content_text:
            update_data["content_text"] = content_text

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
            logger.info(f"💾 Document {document_id} {save_type} (version +1)")
            return True

        logger.warning(f"⚠️ Document {document_id} not found or not modified")
        return False

    def list_user_documents(
        self, user_id: str, limit: int = 20, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Lấy danh sách documents của user, sắp xếp theo last_opened_at"""
        documents = list(
            self.documents.find({"user_id": user_id, "is_deleted": False})
            .sort("last_opened_at", -1)
            .skip(offset)
            .limit(limit)
        )

        logger.info(f"📋 Listed {len(documents)} documents for user {user_id}")
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
