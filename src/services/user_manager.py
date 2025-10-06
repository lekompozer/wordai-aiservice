"""
User Management Service
Quản lý users, conversations và files trong MongoDB
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import uuid
from pymongo.errors import DuplicateKeyError
from src.database.db_manager import DBManager
from src.utils.logger import setup_logger

logger = setup_logger()


class UserManager:
    """Manages users, conversations, and files in MongoDB"""

    def __init__(self, db_manager: Optional[DBManager]):
        self.db = db_manager

        if self.db and self.db.client:
            # MongoDB collections
            self.users = self.db.db["users"]
            self.conversations = self.db.db["conversations"]
            self.user_files = self.db.db["user_files"]

            # Create indexes for better performance
            self._create_indexes()
            logger.info("✅ UserManager initialized with MongoDB")
        else:
            # Fallback storage - use dictionaries
            self.users = {}
            self.conversations = {}
            self.user_files = {}
            logger.warning(
                "⚠️ UserManager initialized with fallback storage (no MongoDB)"
            )
            logger.info("✅ UserManager fallback storage ready")
            self.users = {}
            self.conversations = {}
            self.user_files = {}

    def _create_indexes(self):
        """Create database indexes for better performance"""
        if not self.db or not self.db.client:
            return

        try:
            # Check existing indexes to avoid conflicts
            existing_users_indexes = [idx["name"] for idx in self.users.list_indexes()]
            existing_conv_indexes = [
                idx["name"] for idx in self.conversations.list_indexes()
            ]
            existing_files_indexes = [
                idx["name"] for idx in self.user_files.list_indexes()
            ]

            # User indexes - use unique names with sparse=True
            if (
                "firebase_uid_1_sparse" not in existing_users_indexes
                and "firebase_uid_1" not in existing_users_indexes
            ):
                self.users.create_index(
                    "firebase_uid",
                    unique=True,
                    sparse=True,
                    name="firebase_uid_1_sparse",
                )

            if "email_1" not in existing_users_indexes:
                self.users.create_index("email", name="email_1")

            # Conversation indexes
            if (
                "conversation_id_1_sparse" not in existing_conv_indexes
                and "conversation_id_1" not in existing_conv_indexes
            ):
                self.conversations.create_index(
                    "conversation_id",
                    unique=True,
                    sparse=True,
                    name="conversation_id_1_sparse",
                )

            if "user_id_1" not in existing_conv_indexes:
                self.conversations.create_index("user_id", name="user_id_1")

            if "user_id_1_updated_at_-1" not in existing_conv_indexes:
                self.conversations.create_index(
                    [("user_id", 1), ("updated_at", -1)], name="user_id_1_updated_at_-1"
                )

            # File indexes
            if (
                "file_id_1_sparse" not in existing_files_indexes
                and "file_id_1" not in existing_files_indexes
            ):
                self.user_files.create_index(
                    "file_id", unique=True, sparse=True, name="file_id_1_sparse"
                )

            # These might already exist with different names, so check carefully
            if "user_id_1" not in existing_files_indexes:
                self.user_files.create_index("user_id", name="user_files_user_id_1")

            if (
                "user_files_user_id_1_uploaded_at_-1" not in existing_files_indexes
                and "user_id_1_uploaded_at_-1" not in existing_files_indexes
            ):
                self.user_files.create_index(
                    [("user_id", 1), ("uploaded_at", -1)],
                    name="user_files_user_id_1_uploaded_at_-1",
                )

            logger.info("✅ Database indexes created successfully")
        except Exception as e:
            logger.error(f"❌ Failed to create indexes: {e}")

    async def create_or_update_user(
        self, firebase_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create new user or update existing user from Firebase auth data

        Args:
            firebase_data: User data from Firebase token

        Returns:
            User document
        """
        try:
            firebase_uid = firebase_data.get("firebase_uid")

            if not firebase_uid:
                raise ValueError("Firebase UID is required")

            now = datetime.now(timezone.utc)

            user_doc = {
                "firebase_uid": firebase_uid,
                "email": firebase_data.get("email"),
                "display_name": firebase_data.get("display_name"),
                "photo_url": firebase_data.get("photo_url"),
                "email_verified": firebase_data.get("email_verified", False),
                "provider": firebase_data.get("provider", "unknown"),
                "last_login": now,
                "updated_at": now,
                "preferences": {
                    "default_ai_provider": "openai",
                    "theme": "light",
                    "language": "vi",
                },
            }

            if self.db and self.db.client:
                # MongoDB update
                result = self.users.update_one(
                    {"firebase_uid": firebase_uid},
                    {
                        "$set": user_doc,
                        "$setOnInsert": {
                            "created_at": now,
                            "subscription_plan": "free",
                            "total_conversations": 0,
                            "total_files": 0,
                        },
                    },
                    upsert=True,
                )

                # Get the updated document
                user = self.users.find_one({"firebase_uid": firebase_uid})
                logger.info(
                    f"✅ User {'updated' if result.matched_count else 'created'}: {user_doc['email']}"
                )
                return user
            else:
                # Fallback storage
                if firebase_uid not in self.users:
                    user_doc.update(
                        {
                            "created_at": now,
                            "subscription_plan": "free",
                            "total_conversations": 0,
                            "total_files": 0,
                        }
                    )

                self.users[firebase_uid] = user_doc
                logger.info(f"✅ User stored in memory: {user_doc['email']}")
                return user_doc

        except Exception as e:
            logger.error(f"❌ Error creating/updating user: {e}")
            raise

    async def get_user(self, firebase_uid: str) -> Optional[Dict[str, Any]]:
        """
        Get user by Firebase UID

        Args:
            firebase_uid: Firebase user ID

        Returns:
            User document or None
        """
        try:
            if self.db.client:
                return self.users.find_one({"firebase_uid": firebase_uid})
            else:
                return self.users.get(firebase_uid)
        except Exception as e:
            logger.error(f"❌ Error getting user {firebase_uid}: {e}")
            return None

    # Conversation Management Methods
    async def save_conversation(
        self,
        user_id: str,
        conversation_id: str,
        messages: List[Dict[str, str]],
        ai_provider: str,
        metadata: Dict[str, Any] = None,
    ) -> bool:
        """
        Save or update a conversation

        Args:
            user_id: Firebase UID
            conversation_id: Unique conversation ID
            messages: List of messages in conversation
            ai_provider: AI provider used
            metadata: Additional metadata

        Returns:
            True if successful
        """
        try:
            now = datetime.now(timezone.utc)

            conversation_doc = {
                "conversation_id": conversation_id,
                "user_id": user_id,
                "messages": messages,
                "ai_provider": ai_provider,
                "metadata": metadata or {},
                "updated_at": now,
            }

            if self.db.client:
                # Check if conversation exists
                existing = self.conversations.find_one(
                    {"conversation_id": conversation_id}
                )

                if existing:
                    # Update existing conversation
                    self.conversations.update_one(
                        {"conversation_id": conversation_id}, {"$set": conversation_doc}
                    )
                    logger.info(f"✅ Updated conversation {conversation_id}")
                else:
                    # Create new conversation
                    conversation_doc["created_at"] = now
                    self.conversations.insert_one(conversation_doc)
                    logger.info(f"✅ Created new conversation {conversation_id}")
            else:
                # Fallback storage
                if conversation_id not in self.conversations:
                    conversation_doc["created_at"] = now

                self.conversations[conversation_id] = conversation_doc
                logger.info(f"✅ Conversation saved in memory: {conversation_id}")

            return True

        except Exception as e:
            logger.error(f"❌ Error saving conversation {conversation_id}: {e}")
            return False

    async def get_user_conversations(
        self, user_id: str, limit: int = 20, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get user's conversations

        Args:
            user_id: Firebase UID
            limit: Number of conversations to return
            offset: Number of conversations to skip

        Returns:
            List of conversations
        """
        try:
            if self.db.client:
                conversations = list(
                    self.conversations.find({"user_id": user_id})
                    .sort("updated_at", -1)
                    .skip(offset)
                    .limit(limit)
                )
            else:
                # Fallback storage
                user_convs = [
                    conv
                    for conv in self.conversations.values()
                    if conv.get("user_id") == user_id
                ]
                user_convs.sort(
                    key=lambda x: x.get("updated_at", datetime.min), reverse=True
                )
                conversations = user_convs[offset : offset + limit]

            logger.info(
                f"📋 Retrieved {len(conversations)} conversations for user {user_id}"
            )
            return conversations

        except Exception as e:
            logger.error(f"❌ Error getting conversations for user {user_id}: {e}")
            return []

    async def get_conversation_detail(
        self, user_id: str, conversation_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get detailed conversation with all messages

        Args:
            user_id: Firebase UID
            conversation_id: Conversation ID

        Returns:
            Full conversation or None
        """
        try:
            if self.db.client:
                conversation = self.conversations.find_one(
                    {"conversation_id": conversation_id, "user_id": user_id}
                )
            else:
                # Fallback storage
                conversation = self.conversations.get(conversation_id)
                if conversation and conversation.get("user_id") != user_id:
                    conversation = None

            if conversation:
                logger.info(f"📖 Retrieved conversation detail {conversation_id}")
            else:
                logger.warning(
                    f"❌ Conversation {conversation_id} not found for user {user_id}"
                )

            return conversation

        except Exception as e:
            logger.error(f"❌ Error getting conversation {conversation_id}: {e}")
            return None

    async def delete_conversation(self, user_id: str, conversation_id: str) -> bool:
        """
        Delete a conversation

        Args:
            user_id: Firebase UID
            conversation_id: Conversation ID

        Returns:
            True if deleted successfully
        """
        try:
            if self.db.client:
                result = self.conversations.delete_one(
                    {"conversation_id": conversation_id, "user_id": user_id}
                )
                success = result.deleted_count > 0
            else:
                # Fallback storage
                conversation = self.conversations.get(conversation_id)
                if conversation and conversation.get("user_id") == user_id:
                    del self.conversations[conversation_id]
                    success = True
                else:
                    success = False

            if success:
                logger.info(f"🗑️ Deleted conversation {conversation_id}")
            else:
                logger.warning(
                    f"❌ Conversation {conversation_id} not found for deletion"
                )

            return success

        except Exception as e:
            logger.error(f"❌ Error deleting conversation {conversation_id}: {e}")
            return False

    async def clear_conversation_messages(
        self, user_id: str, conversation_id: str
    ) -> bool:
        """
        Clear all messages from a conversation

        Args:
            user_id: Firebase UID
            conversation_id: Conversation ID

        Returns:
            True if cleared successfully
        """
        try:
            if self.db.client:
                result = self.conversations.update_one(
                    {"conversation_id": conversation_id, "user_id": user_id},
                    {
                        "$set": {
                            "messages": [],
                            "updated_at": datetime.now(timezone.utc),
                        }
                    },
                )
                success = result.modified_count > 0
            else:
                # Fallback storage
                conversation = self.conversations.get(conversation_id)
                if conversation and conversation.get("user_id") == user_id:
                    conversation["messages"] = []
                    conversation["updated_at"] = datetime.now(timezone.utc)
                    success = True
                else:
                    success = False

            if success:
                logger.info(f"🧹 Cleared messages from conversation {conversation_id}")
            else:
                logger.warning(
                    f"❌ Conversation {conversation_id} not found for clearing"
                )

            return success

        except Exception as e:
            logger.error(f"❌ Error clearing conversation {conversation_id}: {e}")
            return False

    async def get_user_chat_stats(self, user_id: str) -> Dict[str, Any]:
        """
        Get user's chat statistics

        Args:
            user_id: Firebase UID

        Returns:
            Statistics dictionary
        """
        try:
            if self.db.client:
                # Count conversations
                total_conversations = self.conversations.count_documents(
                    {"user_id": user_id}
                )

                # Get conversation with most messages
                pipeline = [
                    {"$match": {"user_id": user_id}},
                    {
                        "$project": {
                            "conversation_id": 1,
                            "ai_provider": 1,
                            "message_count": {"$size": "$messages"},
                            "updated_at": 1,
                        }
                    },
                    {"$sort": {"message_count": -1}},
                    {"$limit": 1},
                ]

                longest_conversation = list(self.conversations.aggregate(pipeline))

                # Count by AI provider
                provider_pipeline = [
                    {"$match": {"user_id": user_id}},
                    {"$group": {"_id": "$ai_provider", "count": {"$sum": 1}}},
                ]

                provider_stats = list(self.conversations.aggregate(provider_pipeline))

            else:
                # Fallback storage
                user_convs = [
                    conv
                    for conv in self.conversations.values()
                    if conv.get("user_id") == user_id
                ]

                total_conversations = len(user_convs)

                # Find longest conversation
                longest_conversation = []
                if user_convs:
                    max_conv = max(user_convs, key=lambda x: len(x.get("messages", [])))
                    longest_conversation = [
                        {
                            "conversation_id": max_conv.get("conversation_id"),
                            "ai_provider": max_conv.get("ai_provider"),
                            "message_count": len(max_conv.get("messages", [])),
                            "updated_at": max_conv.get("updated_at"),
                        }
                    ]

                # Count by provider
                provider_counts = {}
                for conv in user_convs:
                    provider = conv.get("ai_provider", "unknown")
                    provider_counts[provider] = provider_counts.get(provider, 0) + 1

                provider_stats = [
                    {"_id": provider, "count": count}
                    for provider, count in provider_counts.items()
                ]

            stats = {
                "total_conversations": total_conversations,
                "longest_conversation": (
                    longest_conversation[0] if longest_conversation else None
                ),
                "provider_usage": {
                    stat["_id"]: stat["count"] for stat in provider_stats
                },
                "generated_at": datetime.now(timezone.utc),
            }

            logger.info(f"📊 Generated chat stats for user {user_id}")
            return stats

        except Exception as e:
            logger.error(f"❌ Error generating chat stats for user {user_id}: {e}")
            return {
                "total_conversations": 0,
                "longest_conversation": None,
                "provider_usage": {},
                "generated_at": datetime.now(timezone.utc),
                "error": str(e),
            }

    async def create_conversation(
        self, user_id: str, title: Optional[str] = None, ai_provider: str = "openai"
    ) -> str:
        """
        Create new conversation for user

        Args:
            user_id: Firebase UID
            title: Conversation title (auto-generated if None)
            ai_provider: AI provider to use

        Returns:
            Conversation ID
        """
        try:
            conversation_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)

            # Auto-generate title if not provided
            if not title:
                title = f"New Conversation {now.strftime('%m/%d %H:%M')}"

            conversation_doc = {
                "conversation_id": conversation_id,
                "user_id": user_id,
                "title": title,
                "created_at": now,
                "updated_at": now,
                "messages": [],
                "settings": {
                    "ai_provider": ai_provider,
                    "temperature": 0.7,
                    "max_tokens": 1000,
                },
            }

            if self.db.client:
                self.conversations.insert_one(conversation_doc)

                # Update user stats
                self.users.update_one(
                    {"firebase_uid": user_id}, {"$inc": {"total_conversations": 1}}
                )
            else:
                self.conversations[conversation_id] = conversation_doc
                if user_id in self.users:
                    self.users[user_id]["total_conversations"] = (
                        self.users[user_id].get("total_conversations", 0) + 1
                    )

            logger.info(f"✅ Created conversation {conversation_id} for user {user_id}")
            return conversation_id

        except Exception as e:
            logger.error(f"❌ Error creating conversation: {e}")
            raise

    async def get_conversation(
        self, conversation_id: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get conversation detail with messages

        Args:
            conversation_id: Conversation ID
            user_id: Firebase UID (for authorization)

        Returns:
            Conversation document with messages
        """
        try:
            if self.db.client:
                conversation = self.conversations.find_one(
                    {
                        "conversation_id": conversation_id,
                        "user_id": user_id,  # Ensure user owns this conversation
                    }
                )
            else:
                conversation = self.conversations.get(conversation_id)
                if conversation and conversation.get("user_id") != user_id:
                    conversation = None  # User doesn't own this conversation

            return conversation

        except Exception as e:
            logger.error(f"❌ Error getting conversation {conversation_id}: {e}")
            return None

    async def delete_conversation(self, conversation_id: str, user_id: str) -> bool:
        """
        Delete conversation (user must own it)

        Args:
            conversation_id: Conversation ID
            user_id: Firebase UID

        Returns:
            True if deleted successfully
        """
        try:
            if self.db.client:
                result = self.conversations.delete_one(
                    {"conversation_id": conversation_id, "user_id": user_id}
                )

                if result.deleted_count > 0:
                    # Update user stats
                    self.users.update_one(
                        {"firebase_uid": user_id}, {"$inc": {"total_conversations": -1}}
                    )
                    logger.info(f"✅ Deleted conversation {conversation_id}")
                    return True
            else:
                conversation = self.conversations.get(conversation_id)
                if conversation and conversation.get("user_id") == user_id:
                    del self.conversations[conversation_id]
                    if user_id in self.users:
                        self.users[user_id]["total_conversations"] = max(
                            0, self.users[user_id].get("total_conversations", 1) - 1
                        )
                    logger.info(f"✅ Deleted conversation {conversation_id}")
                    return True

            return False

        except Exception as e:
            logger.error(f"❌ Error deleting conversation {conversation_id}: {e}")
            return False

    async def add_message_to_conversation(
        self,
        conversation_id: str,
        user_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Add message to conversation

        Args:
            conversation_id: Conversation ID
            user_id: Firebase UID
            role: Message role (user/assistant/system)
            content: Message content
            metadata: Additional metadata

        Returns:
            True if message added successfully
        """
        try:
            now = datetime.now(timezone.utc)
            message = {
                "message_id": str(uuid.uuid4()),
                "role": role,
                "content": content,
                "timestamp": now,
                "metadata": metadata or {},
            }

            if self.db.client:
                result = self.conversations.update_one(
                    {"conversation_id": conversation_id, "user_id": user_id},
                    {"$push": {"messages": message}, "$set": {"updated_at": now}},
                )
                return result.modified_count > 0
            else:
                conversation = self.conversations.get(conversation_id)
                if conversation and conversation.get("user_id") == user_id:
                    conversation["messages"].append(message)
                    conversation["updated_at"] = now
                    return True
                return False

        except Exception as e:
            logger.error(
                f"❌ Error adding message to conversation {conversation_id}: {e}"
            )
            return False

    # File Management Methods
    def get_file_by_id(self, file_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get file information by file_id - Synchronous for compatibility

        Args:
            file_id: File ID
            user_id: Firebase UID (for authorization)

        Returns:
            File document or None
        """
        try:
            if self.db and self.db.client:
                file_doc = self.user_files.find_one(
                    {"file_id": file_id, "user_id": user_id, "is_deleted": False}
                )
                return file_doc
            else:
                # Fallback storage
                file_doc = self.user_files.get(file_id)
                if file_doc and file_doc.get("user_id") == user_id:
                    return file_doc
                return None

        except Exception as e:
            logger.error(f"❌ Error getting file {file_id}: {e}")
            return None

    def save_file_metadata(
        self,
        file_id: str,
        user_id: str,
        filename: str,
        original_name: str,
        file_type: str,
        file_size: int,
        folder_id: Optional[str],
        r2_key: str,
        private_url: str,
    ) -> bool:
        """
        Save file metadata to MongoDB

        Args:
            file_id: Unique file ID
            user_id: Firebase UID
            filename: Safe filename with timestamp
            original_name: Original uploaded filename
            file_type: File extension (.pdf, .docx, etc.)
            file_size: File size in bytes
            folder_id: Folder ID or None for root
            r2_key: R2 storage key
            private_url: Private R2 URL

        Returns:
            bool: Success status
        """
        try:
            now = datetime.now(timezone.utc)

            file_doc = {
                "file_id": file_id,
                "user_id": user_id,
                "filename": filename,
                "original_name": original_name,
                "file_type": file_type,
                "file_size": file_size,
                "folder_id": folder_id,
                "r2_key": r2_key,
                "file_url": private_url,  # For compatibility with document_manager
                "is_deleted": False,
                "deleted_at": None,
                "uploaded_at": now,
                "updated_at": now,
            }

            if self.db and self.db.client:
                self.user_files.insert_one(file_doc)
                logger.info(f"✅ Saved file metadata: {file_id}")
            else:
                # Fallback storage
                self.user_files[file_id] = file_doc
                logger.info(f"✅ Saved file metadata (fallback): {file_id}")

            return True

        except Exception as e:
            logger.error(f"❌ Error saving file metadata {file_id}: {e}")
            return False

    def list_user_files(
        self,
        user_id: str,
        folder_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        List files for user from MongoDB (excludes deleted files)

        Args:
            user_id: Firebase UID
            folder_id: Filter by folder ID (None = root folder if passed explicitly,
                      use folder_id="__ALL__" to get all folders)
            limit: Maximum number of files
            offset: Pagination offset

        Returns:
            List of file documents
        """
        try:
            if self.db and self.db.client:
                query = {"user_id": user_id, "is_deleted": False}

                # Filter by folder
                # Special value "__ALL__" means get ALL folders
                if folder_id == "__ALL__":
                    # No folder filter - get all
                    pass
                elif folder_id:
                    # Specific folder
                    query["folder_id"] = folder_id
                else:
                    # Root folder: folder_id is None or "root"
                    query["folder_id"] = {"$in": [None, "root"]}

                files = list(
                    self.user_files.find(query)
                    .sort("uploaded_at", -1)
                    .skip(offset)
                    .limit(limit)
                )

                logger.info(f"📋 Listed {len(files)} files for user {user_id}")
                return files
            else:
                # Fallback storage
                if folder_id == "__ALL__":
                    files = [
                        f
                        for f in self.user_files.values()
                        if f.get("user_id") == user_id
                        and not f.get("is_deleted", False)
                    ]
                else:
                    files = [
                        f
                        for f in self.user_files.values()
                        if f.get("user_id") == user_id
                        and not f.get("is_deleted", False)
                        and (
                            f.get("folder_id") == folder_id
                            if folder_id
                            else f.get("folder_id") in [None, "root"]
                        )
                    ]
                return sorted(
                    files,
                    key=lambda x: x.get("uploaded_at", datetime.min),
                    reverse=True,
                )[offset : offset + limit]

        except Exception as e:
            logger.error(f"❌ Error listing files for user {user_id}: {e}")
            return []

    def soft_delete_file(self, file_id: str, user_id: str) -> bool:
        """
        Soft delete file (set is_deleted=True)

        Args:
            file_id: File ID
            user_id: Firebase UID (for authorization)

        Returns:
            bool: Success status
        """
        try:
            now = datetime.now(timezone.utc)

            if self.db and self.db.client:
                result = self.user_files.update_one(
                    {"file_id": file_id, "user_id": user_id},
                    {"$set": {"is_deleted": True, "deleted_at": now}},
                )

                if result.modified_count > 0:
                    logger.info(f"🗑️ Soft deleted file: {file_id}")
                    return True
                else:
                    logger.warning(f"⚠️ File not found: {file_id}")
                    return False
            else:
                # Fallback storage
                if file_id in self.user_files:
                    file_doc = self.user_files[file_id]
                    if file_doc.get("user_id") == user_id:
                        file_doc["is_deleted"] = True
                        file_doc["deleted_at"] = now
                        logger.info(f"🗑️ Soft deleted file (fallback): {file_id}")
                        return True
                return False

        except Exception as e:
            logger.error(f"❌ Error soft deleting file {file_id}: {e}")
            return False

    def restore_file(self, file_id: str, user_id: str) -> bool:
        """
        Restore soft-deleted file

        Args:
            file_id: File ID
            user_id: Firebase UID (for authorization)

        Returns:
            bool: Success status
        """
        try:
            if self.db and self.db.client:
                result = self.user_files.update_one(
                    {"file_id": file_id, "user_id": user_id, "is_deleted": True},
                    {"$set": {"is_deleted": False, "deleted_at": None}},
                )

                if result.modified_count > 0:
                    logger.info(f"♻️ Restored file: {file_id}")
                    return True
                else:
                    logger.warning(f"⚠️ File not found in trash: {file_id}")
                    return False
            else:
                # Fallback storage
                if file_id in self.user_files:
                    file_doc = self.user_files[file_id]
                    if file_doc.get("user_id") == user_id and file_doc.get(
                        "is_deleted"
                    ):
                        file_doc["is_deleted"] = False
                        file_doc["deleted_at"] = None
                        logger.info(f"♻️ Restored file (fallback): {file_id}")
                        return True
                return False

        except Exception as e:
            logger.error(f"❌ Error restoring file {file_id}: {e}")
            return False

    def list_deleted_files(
        self, user_id: str, limit: int = 100, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List deleted files (trash)

        Args:
            user_id: Firebase UID
            limit: Maximum number of files
            offset: Pagination offset

        Returns:
            List of deleted file documents
        """
        try:
            if self.db and self.db.client:
                files = list(
                    self.user_files.find({"user_id": user_id, "is_deleted": True})
                    .sort("deleted_at", -1)
                    .skip(offset)
                    .limit(limit)
                )

                logger.info(f"🗑️ Listed {len(files)} deleted files for user {user_id}")
                return files
            else:
                # Fallback storage
                files = [
                    f
                    for f in self.user_files.values()
                    if f.get("user_id") == user_id and f.get("is_deleted", False)
                ]
                return sorted(
                    files, key=lambda x: x.get("deleted_at", datetime.min), reverse=True
                )[offset : offset + limit]

        except Exception as e:
            logger.error(f"❌ Error listing deleted files for user {user_id}: {e}")
            return []


# Global user manager instance - Initialize immediately
def initialize_user_manager():
    """Initialize user manager with database connection"""
    try:
        from src.database.db_manager import DBManager

        db_manager = DBManager()
        return UserManager(db_manager)
    except Exception as e:
        logger.error(f"❌ Failed to initialize user manager: {e}")
        # Return a fallback manager without database
        return UserManager(None)


user_manager = initialize_user_manager()


def get_user_manager() -> UserManager:
    """Get global user manager instance"""
    global user_manager
    if user_manager is None:
        user_manager = initialize_user_manager()
    return user_manager
