import os
import pymongo
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from src.utils.logger import setup_logger

logger = setup_logger()


class DBManager:
    def __init__(self):
        """
        Enhanced MongoDB manager with user_id, device_id, session_id support
        Quản lý MongoDB nâng cao với hỗ trợ user_id, device_id, session_id
        """
        # Use MONGODB_URI or MONGODB_URI_AUTH if available (most reliable)
        mongo_uri = os.getenv("MONGODB_URI") or os.getenv("MONGODB_URI_AUTH")

        if not mongo_uri:
            # Fallback: Build URI from components only if no URI provided
            # Check environment (use ENV to match project standard)
            environment = os.getenv("ENV", "development").lower()

            mongo_user = os.getenv("MONGODB_APP_USERNAME")
            mongo_pass = os.getenv("MONGODB_APP_PASSWORD")
            db_name = os.getenv("MONGODB_NAME", "ai_service_db")

            # Determine host based on environment
            if environment == "production":
                mongo_host = "mongodb:27017"  # Docker network container name
                logger.info(f"🐳 [PROD] Using Docker network MongoDB")
            else:
                mongo_host = "localhost:27017"
                logger.info(f"🏠 [DEV] Using local MongoDB")

            if mongo_user and mongo_pass:
                mongo_uri = f"mongodb://{mongo_user}:{mongo_pass}@{mongo_host}/{db_name}?authSource=admin"
            else:
                mongo_uri = f"mongodb://{mongo_host}/"
        else:
            logger.info(f"✅ Using MONGODB_URI from environment")

        db_name = os.getenv("MONGODB_NAME", "ai_service_db")

        try:
            self.client = pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=10000)
            self.db = self.client[db_name]
            self.conversations = self.db["conversations"]

            # Test connection first
            self.client.admin.command("ping")
            logger.info(f"✅ MongoDB connection successful using authenticated URI")

            # Enhanced indexing for better user identification and performance
            # Tạo index nâng cao cho nhận dạng user tốt hơn và hiệu suất cao
            self.conversations.create_index("user_id")
            self.conversations.create_index("device_id")
            self.conversations.create_index("session_id")
            self.conversations.create_index("lastMessageTime")

            # Compound indexes for efficient queries
            # Index kết hợp cho truy vấn hiệu quả
            self.conversations.create_index([("user_id", 1), ("lastMessageTime", -1)])
            self.conversations.create_index([("device_id", 1), ("lastMessageTime", -1)])
            self.conversations.create_index(
                [("session_id", 1), ("lastMessageTime", -1)]
            )

            logger.info(f"Connected to MongoDB with enhanced schema: {db_name}")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            # Fallback: sử dụng dict để lưu trữ tạm thời
            self.client = None
            self.conversations = {}

    def add_message_enhanced(
        self,
        user_id: str = None,
        device_id: str = None,
        session_id: str = None,
        role: str = None,
        content: str = None,
    ) -> bool:
        """
        Enhanced message saving with comprehensive user identification
        Lưu tin nhắn nâng cao với nhận dạng user toàn diện

        Args:
            user_id: Authenticated user ID (highest priority)
            device_id: Device identifier for anonymous users
            session_id: Session identifier
            role: 'user' hoặc 'assistant'
            content: Nội dung tin nhắn

        Returns:
            bool: True nếu thêm thành công
        """
        if not role or not content:
            logger.error("Role and content are required for saving message")
            return False

        current_time = datetime.now()
        message = {"role": role, "content": content, "timestamp": current_time}

        try:
            if self.client:
                # Prepare document with all user identifiers
                document_id = {
                    "user_id": user_id or "unknown",
                    "device_id": device_id or "unknown",
                    "session_id": session_id or "unknown",
                }

                # Use user_id as primary key if available, otherwise device_id, otherwise session_id
                primary_key = (
                    user_id
                    or device_id
                    or session_id
                    or f"anonymous_{current_time.timestamp()}"
                )

                result = self.conversations.update_one(
                    {"primary_key": primary_key},
                    {
                        "$push": {"messages": message},
                        "$set": {
                            "user_id": user_id or "unknown",
                            "device_id": device_id or "unknown",
                            "session_id": session_id or "unknown",
                            "primary_key": primary_key,
                            "lastMessageTime": current_time,
                        },
                    },
                    upsert=True,
                )

                logger.info(
                    f"💾 Message saved with primary_key: {primary_key} (user_id: {user_id}, device_id: {device_id}, session_id: {session_id})"
                )
                return result.acknowledged
            else:
                # Fallback khi không có MongoDB
                primary_key = (
                    user_id
                    or device_id
                    or session_id
                    or f"anonymous_{current_time.timestamp()}"
                )
                if primary_key not in self.conversations:
                    self.conversations[primary_key] = {
                        "primary_key": primary_key,
                        "user_id": user_id or "unknown",
                        "device_id": device_id or "unknown",
                        "session_id": session_id or "unknown",
                        "messages": [],
                        "lastMessageTime": current_time,
                    }
                self.conversations[primary_key]["messages"].append(message)
                self.conversations[primary_key]["lastMessageTime"] = current_time
                return True
        except Exception as e:
            logger.error(f"Error adding enhanced message: {e}")
            return False

    def add_message(self, user_id: str, role: str, content: str) -> bool:
        """
        Legacy method for backward compatibility - delegates to enhanced method
        Phương thức legacy cho tương thích ngược - ủy quyền cho phương thức nâng cao
        """
        return self.add_message_enhanced(user_id=user_id, role=role, content=content)

    def get_recent_messages_enhanced(
        self,
        user_id: str = None,
        device_id: str = None,
        session_id: str = None,
        hours: int = 72,
    ) -> List[Dict]:
        """
        Enhanced method to get recent messages with priority-based user identification
        Phương thức nâng cao lấy tin nhắn gần đây với nhận dạng user theo độ ưu tiên

        Priority order: user_id > device_id > session_id
        Thứ tự ưu tiên: user_id > device_id > session_id

        Args:
            user_id: Authenticated user ID (highest priority)
            device_id: Device identifier
            session_id: Session identifier
            hours: Số giờ gần đây để lọc tin nhắn

        Returns:
            List[Dict]: Danh sách các tin nhắn gần đây từ session gần nhất
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)

        try:
            if self.client:
                # Try to find conversation by priority order
                # Thử tìm conversation theo thứ tự ưu tiên
                conversation = None
                used_identifier = None

                # Priority 1: user_id (authenticated users)
                if user_id and user_id != "unknown":
                    conversations = list(
                        self.conversations.find({"user_id": user_id})
                        .sort("lastMessageTime", -1)
                        .limit(1)
                    )

                    if conversations:
                        conversation = conversations[0]
                        used_identifier = f"user_id:{user_id}"
                        logger.info(f"👤 Found conversation using user_id: {user_id}")

                # Priority 2: device_id if no user_id found
                if not conversation and device_id and device_id != "unknown":
                    conversations = list(
                        self.conversations.find({"device_id": device_id})
                        .sort("lastMessageTime", -1)
                        .limit(1)
                    )

                    if conversations:
                        conversation = conversations[0]
                        used_identifier = f"device_id:{device_id}"
                        logger.info(
                            f"📱 Found conversation using device_id: {device_id}"
                        )

                # Priority 3: session_id as fallback
                if not conversation and session_id and session_id != "unknown":
                    conversations = list(
                        self.conversations.find({"session_id": session_id})
                        .sort("lastMessageTime", -1)
                        .limit(1)
                    )

                    if conversations:
                        conversation = conversations[0]
                        used_identifier = f"session_id:{session_id}"
                        logger.info(
                            f"🔗 Found conversation using session_id: {session_id}"
                        )

                if not conversation:
                    logger.info(
                        f"👤 No conversation found for user_id:{user_id}, device_id:{device_id}, session_id:{session_id}"
                    )
                    return []

                # Filter messages within time window
                # Lọc tin nhắn trong khung thời gian
                recent_messages = [
                    {"role": msg["role"], "content": msg["content"]}
                    for msg in conversation.get("messages", [])
                    if msg["timestamp"] >= cutoff_time
                ]

                logger.info(
                    f"📥 Retrieved {len(recent_messages)} recent messages using {used_identifier}"
                )
                return recent_messages

            else:
                # Fallback khi không có MongoDB
                # Try priority order for in-memory storage
                identifiers = [user_id, device_id, session_id]

                for identifier in identifiers:
                    if (
                        identifier
                        and identifier != "unknown"
                        and identifier in self.conversations
                    ):
                        conversation = self.conversations[identifier]
                        recent_messages = [
                            {"role": msg["role"], "content": msg["content"]}
                            for msg in conversation["messages"]
                            if msg["timestamp"] >= cutoff_time
                        ]
                        logger.info(
                            f"📥 Retrieved {len(recent_messages)} messages from memory using: {identifier}"
                        )
                        return recent_messages

                return []

        except Exception as e:
            logger.error(f"Error getting enhanced messages: {e}")
            return []

    def get_recent_messages(self, user_id: str, hours: int = 72) -> List[Dict]:
        """
        Legacy method for backward compatibility - delegates to enhanced method
        Phương thức legacy cho tương thích ngược - ủy quyền cho phương thức nâng cao
        """
        return self.get_recent_messages_enhanced(user_id=user_id, hours=hours)

    def get_recent_messages_optimized(
        self,
        user_id: str = None,
        device_id: str = None,
        session_id: str = None,
        hours: int = 72,
    ) -> List[Dict]:
        """
        OPTIMIZED method for frontend requirements - user_id first, then device_id
        Phương thức tối ưu cho yêu cầu frontend - user_id trước, sau đó device_id

        Frontend always sends user_id, so check user_id first for speed optimization
        If user_id exists, get latest session_id conversation history
        Frontend luôn gửi user_id, nên check user_id trước để tối ưu tốc độ
        Nếu có user_id, lấy history chat từ session_id gần nhất

        Args:
            user_id: Always provided by frontend (authenticated or anon_web_xxx)
            device_id: Device identifier fallback
            session_id: Session identifier (lowest priority)
            hours: Hours to look back for messages

        Returns:
            List[Dict]: Recent messages from latest session
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)

        try:
            if self.client:
                conversation = None
                used_identifier = None

                # OPTIMIZED: Check user_id FIRST (since frontend always provides it)
                if user_id and user_id != "unknown":
                    # Find the LATEST session for this user_id (most recent conversation)
                    conversations = list(
                        self.conversations.find({"user_id": user_id})
                        .sort("lastMessageTime", -1)
                        .limit(1)
                    )

                    if conversations:
                        conversation = conversations[0]
                        used_identifier = f"user_id:{user_id}"
                        logger.info(
                            f"👤 [OPTIMIZED] Found latest session for user_id: {user_id}"
                        )
                        logger.info(
                            f"👤 [OPTIMIZED] Latest session_id: {conversation.get('session_id', 'unknown')}"
                        )

                # Fallback to device_id only if user_id failed
                elif device_id and device_id != "unknown":
                    conversations = list(
                        self.conversations.find({"device_id": device_id})
                        .sort("lastMessageTime", -1)
                        .limit(1)
                    )

                    if conversations:
                        conversation = conversations[0]
                        used_identifier = f"device_id:{device_id}"
                        logger.info(
                            f"📱 [OPTIMIZED] Found conversation using device_id: {device_id}"
                        )

                # Last resort: session_id (rarely used now)
                elif session_id and session_id != "unknown":
                    conversations = list(
                        self.conversations.find({"session_id": session_id})
                        .sort("lastMessageTime", -1)
                        .limit(1)
                    )

                    if conversations:
                        conversation = conversations[0]
                        used_identifier = f"session_id:{session_id}"
                        logger.info(
                            f"🔗 [OPTIMIZED] Found conversation using session_id: {session_id}"
                        )

                if not conversation:
                    logger.info(
                        f"👤 [OPTIMIZED] No conversation found for user_id:{user_id}, device_id:{device_id}"
                    )
                    return []

                # Filter messages within time window
                recent_messages = [
                    {"role": msg["role"], "content": msg["content"]}
                    for msg in conversation.get("messages", [])
                    if msg["timestamp"] >= cutoff_time
                ]

                logger.info(
                    f"📥 [OPTIMIZED] Retrieved {len(recent_messages)} messages using {used_identifier}"
                )
                return recent_messages

            else:
                # Fallback for in-memory storage (development)
                identifiers = [user_id, device_id, session_id]

                for identifier in identifiers:
                    if (
                        identifier
                        and identifier != "unknown"
                        and identifier in self.conversations
                    ):
                        conversation = self.conversations[identifier]
                        recent_messages = [
                            {"role": msg["role"], "content": msg["content"]}
                            for msg in conversation["messages"]
                            if msg["timestamp"] >= cutoff_time
                        ]
                        logger.info(
                            f"📥 [OPTIMIZED] Retrieved {len(recent_messages)} messages from memory using: {identifier}"
                        )
                        return recent_messages

                return []

        except Exception as e:
            logger.error(f"❌ [OPTIMIZED] Error getting messages: {e}")
            return []

    def cleanup_old_conversations(self, days: int = 3) -> int:
        """
        Dọn dẹp các cuộc hội thoại cũ hơn số ngày chỉ định

        Args:
            days: Số ngày tối đa giữ lịch sử

        Returns:
            int: Số lượng cuộc hội thoại đã xóa
        """
        cutoff_time = datetime.now() - timedelta(days=days)

        try:
            if self.client:
                result = self.conversations.delete_many(
                    {"lastMessageTime": {"$lt": cutoff_time}}
                )
                return result.deleted_count
            else:
                # Fallback khi không có MongoDB
                deleted_count = 0
                users_to_delete = []

                for user_id, conversation in self.conversations.items():
                    if conversation["lastMessageTime"] < cutoff_time:
                        users_to_delete.append(user_id)
                        deleted_count += 1

                for user_id in users_to_delete:
                    del self.conversations[user_id]

                return deleted_count
        except Exception as e:
            logger.error(f"Error cleaning up old conversations: {e}")
            return 0

    def clear_history(self, user_id: str) -> bool:
        """
        Xóa toàn bộ lịch sử hội thoại của một người dùng

        Args:
            user_id: ID của người dùng

        Returns:
            bool: True nếu xóa thành công
        """
        try:
            if self.client:
                result = self.conversations.delete_one({"userID": user_id})
                return result.deleted_count > 0
            else:
                # Fallback khi không có MongoDB
                if user_id in self.conversations:
                    del self.conversations[user_id]
                    return True
                return False
        except Exception as e:
            logger.error(f"Error clearing history for user {user_id}: {e}")
            return False
