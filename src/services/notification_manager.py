"""
Notification Manager Service
Handles InApp notifications and Email notifications for file sharing
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from pymongo.database import Database
import uuid

logger = logging.getLogger(__name__)


class NotificationManager:
    """
    Quản lý notifications cho file sharing system
    - InApp notifications (lưu MongoDB)
    - Email notifications (gửi qua SMTP)
    """

    def __init__(self, db: Database):
        """
        Initialize NotificationManager

        Args:
            db: MongoDB database instance
        """
        self.db = db
        self.notifications = db["notifications"]
        self.users = db["users"]

        logger.info("✅ NotificationManager initialized")

    def create_indexes(self):
        """
        Tạo indexes cho notifications collection
        """
        try:
            self.notifications.create_index("notification_id", unique=True, sparse=True)
            self.notifications.create_index("user_id")
            self.notifications.create_index([("user_id", 1), ("is_read", 1)])
            self.notifications.create_index([("user_id", 1), ("created_at", -1)])
            self.notifications.create_index("created_at")

            logger.info("✅ Notification indexes created successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Error creating notification indexes: {e}")
            return False

    def create_share_notification(
        self,
        recipient_id: str,
        owner_id: str,
        owner_name: str,
        file_id: str,
        filename: str,
        file_type: str,
        permission: str,
        share_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Tạo InApp notification khi file được share

        Args:
            recipient_id: Người nhận notification
            owner_id: Người share file
            owner_name: Tên người share
            file_id: File ID
            filename: Tên file
            file_type: Loại file (upload/document/library)
            permission: Quyền được cấp
            share_id: Share ID

        Returns:
            Notification document nếu thành công
        """
        try:
            now = datetime.now(timezone.utc)
            notification_id = f"notif_{uuid.uuid4().hex[:16]}"

            # Permission labels
            permission_labels = {
                "view": "xem",
                "download": "tải xuống",
                "edit": "chỉnh sửa",
            }

            notification = {
                "notification_id": notification_id,
                "user_id": recipient_id,
                "type": "file_shared",
                "title": "File được chia sẻ",
                "message": f"{owner_name} đã chia sẻ file '{filename}' với bạn (quyền: {permission_labels.get(permission, permission)})",
                "data": {
                    "share_id": share_id,
                    "file_id": file_id,
                    "file_type": file_type,
                    "filename": filename,
                    "owner_id": owner_id,
                    "owner_name": owner_name,
                    "permission": permission,
                },
                "is_read": False,
                "created_at": now,
                "read_at": None,
            }

            result = self.notifications.insert_one(notification)

            if result.inserted_id:
                logger.info(
                    f"✅ Created share notification {notification_id} for user {recipient_id}"
                )
                return notification
            else:
                logger.error("❌ Failed to create notification")
                return None

        except Exception as e:
            logger.error(f"❌ Error creating share notification: {e}")
            return None

    def list_user_notifications(
        self,
        user_id: str,
        is_read: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Lấy danh sách notifications của user

        Args:
            user_id: User ID
            is_read: Filter by read status (None = all)
            limit: Số lượng kết quả tối đa
            offset: Offset cho pagination

        Returns:
            List of notification documents
        """
        try:
            query = {"user_id": user_id}
            if is_read is not None:
                query["is_read"] = is_read

            notifications = list(
                self.notifications.find(query)
                .sort("created_at", -1)
                .skip(offset)
                .limit(limit)
            )

            logger.info(
                f"✅ Listed {len(notifications)} notifications for user {user_id}"
            )
            return notifications

        except Exception as e:
            logger.error(f"❌ Error listing notifications: {e}")
            return []

    def mark_notification_as_read(self, notification_id: str, user_id: str) -> bool:
        """
        Đánh dấu notification đã đọc

        Args:
            notification_id: Notification ID
            user_id: User ID (để verify ownership)

        Returns:
            True if successful
        """
        try:
            now = datetime.now(timezone.utc)

            result = self.notifications.update_one(
                {"notification_id": notification_id, "user_id": user_id},
                {"$set": {"is_read": True, "read_at": now}},
            )

            if result.modified_count > 0:
                logger.info(f"✅ Marked notification {notification_id} as read")
                return True
            else:
                logger.warning(f"⚠️ Notification not found: {notification_id}")
                return False

        except Exception as e:
            logger.error(f"❌ Error marking notification as read: {e}")
            return False

    def mark_all_as_read(self, user_id: str) -> int:
        """
        Đánh dấu tất cả notifications của user là đã đọc

        Args:
            user_id: User ID

        Returns:
            Number of notifications marked as read
        """
        try:
            now = datetime.now(timezone.utc)

            result = self.notifications.update_many(
                {"user_id": user_id, "is_read": False},
                {"$set": {"is_read": True, "read_at": now}},
            )

            logger.info(
                f"✅ Marked {result.modified_count} notifications as read for user {user_id}"
            )
            return result.modified_count

        except Exception as e:
            logger.error(f"❌ Error marking all notifications as read: {e}")
            return 0

    def get_unread_count(self, user_id: str) -> int:
        """
        Lấy số lượng notifications chưa đọc

        Args:
            user_id: User ID

        Returns:
            Number of unread notifications
        """
        try:
            count = self.notifications.count_documents(
                {"user_id": user_id, "is_read": False}
            )

            logger.info(f"✅ User {user_id} has {count} unread notifications")
            return count

        except Exception as e:
            logger.error(f"❌ Error getting unread count: {e}")
            return 0

    def delete_notification(self, notification_id: str, user_id: str) -> bool:
        """
        Xoá notification

        Args:
            notification_id: Notification ID
            user_id: User ID (để verify ownership)

        Returns:
            True if successful
        """
        try:
            result = self.notifications.delete_one(
                {"notification_id": notification_id, "user_id": user_id}
            )

            if result.deleted_count > 0:
                logger.info(f"✅ Deleted notification {notification_id}")
                return True
            else:
                logger.warning(f"⚠️ Notification not found: {notification_id}")
                return False

        except Exception as e:
            logger.error(f"❌ Error deleting notification: {e}")
            return False

    def create_test_grading_notification(
        self,
        student_id: str,
        test_id: str,
        test_title: str,
        submission_id: str,
        score: float,
        score_percentage: float,
        is_passed: bool,
    ) -> Optional[Dict[str, Any]]:
        """
        Tạo InApp notification khi bài test được chấm điểm

        Args:
            student_id: Student's Firebase UID
            test_id: Test ID
            test_title: Test title
            submission_id: Submission ID
            score: Score out of 10
            score_percentage: Score percentage (0-100)
            is_passed: Whether student passed

        Returns:
            Notification document nếu thành công
        """
        try:
            now = datetime.now(timezone.utc)
            notification_id = f"notif_{uuid.uuid4().hex[:16]}"

            # Status message
            status = "✅ Đạt" if is_passed else "❌ Chưa đạt"
            message = f"Bài kiểm tra '{test_title}' đã được chấm điểm. Điểm: {score}/10 ({score_percentage}%) - {status}"

            notification = {
                "notification_id": notification_id,
                "user_id": student_id,
                "type": "test_graded",
                "title": "Bài kiểm tra đã được chấm",
                "message": message,
                "data": {
                    "test_id": test_id,
                    "test_title": test_title,
                    "submission_id": submission_id,
                    "score": score,
                    "score_percentage": score_percentage,
                    "is_passed": is_passed,
                },
                "is_read": False,
                "created_at": now,
                "read_at": None,
            }

            result = self.notifications.insert_one(notification)

            if result.inserted_id:
                logger.info(
                    f"✅ Created test grading notification {notification_id} for user {student_id}"
                )
                return notification
            else:
                logger.error("❌ Failed to create test grading notification")
                return None

        except Exception as e:
            logger.error(f"❌ Error creating test grading notification: {e}")
            return None

    def send_share_email_notification(
        self,
        recipient_email: str,
        recipient_name: str,
        owner_name: str,
        filename: str,
        permission: str,
    ) -> bool:
        """
        Gửi email notification khi file được share (sử dụng Brevo)

        Args:
            recipient_email: Email người nhận
            recipient_name: Tên người nhận
            owner_name: Tên người share
            filename: Tên file
            permission: Quyền (view/download/edit)

        Returns:
            True if successful
        """
        try:
            from src.services.brevo_email_service import get_brevo_service

            brevo = get_brevo_service()
            success = brevo.send_file_share_notification(
                to_email=recipient_email,
                recipient_name=recipient_name,
                owner_name=owner_name,
                filename=filename,
                permission=permission,
            )

            if success:
                logger.info(f"✅ Share email sent to {recipient_email}")
            else:
                logger.warning(f"⚠️ Failed to send share email to {recipient_email}")

            return success

        except Exception as e:
            logger.error(f"❌ Error sending share email: {e}")
            return False

    def send_welcome_email(
        self,
        recipient_email: str,
        user_name: str,
    ) -> bool:
        """
        Gửi welcome email khi user đăng ký (sử dụng Brevo)

        Args:
            recipient_email: Email người nhận
            user_name: Tên user

        Returns:
            True if successful
        """
        try:
            from src.services.brevo_email_service import get_brevo_service

            brevo = get_brevo_service()
            success = brevo.send_welcome_email(
                to_email=recipient_email,
                user_name=user_name,
            )

            if success:
                logger.info(f"✅ Welcome email sent to {recipient_email}")
            else:
                logger.warning(f"⚠️ Failed to send welcome email to {recipient_email}")

            return success

        except Exception as e:
            logger.error(f"❌ Error sending welcome email: {e}")
            return False
