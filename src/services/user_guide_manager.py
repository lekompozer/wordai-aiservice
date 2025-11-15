"""
User Guide Manager Service
Phase 1: Database operations for User Guides
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
import logging
from pymongo.errors import DuplicateKeyError
from pymongo import ReturnDocument

logger = logging.getLogger("chatbot")


class UserGuideManager:
    """Quản lý User Guides trong MongoDB"""

    def __init__(self, db):
        """
        Initialize UserGuideManager

        Args:
            db: PyMongo Database object (synchronous)
        """
        self.db = db
        self.guides_collection = db["user_guides"]

    def create_indexes(self):
        """Tạo indexes cho collection user_guides"""
        try:
            existing_indexes = [
                idx["name"] for idx in self.guides_collection.list_indexes()
            ]

            # Primary key - unique identifier
            if "guide_id_unique" not in existing_indexes:
                self.guides_collection.create_index(
                    "guide_id", unique=True, name="guide_id_unique"
                )
                logger.info("✅ Created index: guide_id_unique")

            # User's guides listing (sorted by update time)
            if "user_guides_list" not in existing_indexes:
                self.guides_collection.create_index(
                    [("user_id", 1), ("updated_at", -1)], name="user_guides_list"
                )
                logger.info("✅ Created index: user_guides_list")

            # Unique slug per user
            if "user_slug_unique" not in existing_indexes:
                self.guides_collection.create_index(
                    [("user_id", 1), ("slug", 1)], unique=True, name="user_slug_unique"
                )
                logger.info("✅ Created index: user_slug_unique")

            # Public guide lookup by slug
            if "public_guide_lookup" not in existing_indexes:
                self.guides_collection.create_index(
                    [("slug", 1), ("visibility", 1)], name="public_guide_lookup"
                )
                logger.info("✅ Created index: public_guide_lookup")

            # Filter by visibility
            if "visibility_filter" not in existing_indexes:
                self.guides_collection.create_index(
                    [("visibility", 1), ("is_published", 1)], name="visibility_filter"
                )
                logger.info("✅ Created index: visibility_filter")

            logger.info("✅ User Guide indexes verified/created")
        except Exception as e:
            logger.error(f"❌ Error creating guide indexes: {e}")
            raise

    def create_guide(
        self,
        user_id: str,
        guide_data,  # GuideCreate Pydantic model or individual params
    ) -> Dict[str, Any]:
        """
        Tạo guide mới

        Args:
            user_id: Firebase UID of owner
            guide_data: GuideCreate Pydantic model with all fields

        Returns:
            guide document dict

        Raises:
            DuplicateKeyError: If slug already exists for user
        """
        guide_id = f"guide_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow()

        # Convert Pydantic model to dict if needed
        if hasattr(guide_data, "model_dump"):
            data = guide_data.model_dump(exclude_unset=True)
        elif isinstance(guide_data, dict):
            data = guide_data
        else:
            raise ValueError("guide_data must be a Pydantic model or dict")

        guide_doc = {
            "guide_id": guide_id,
            "user_id": user_id,
            "title": data["title"],
            "slug": data["slug"],
            "description": data.get("description"),
            "visibility": data.get("visibility", "public"),
            "is_indexed": data.get(
                "is_indexed", data.get("visibility", "public") == "public"
            ),
            "custom_domain": data.get("custom_domain"),
            "cover_image_url": data.get("cover_image_url"),
            "logo_url": data.get("logo_url"),
            "favicon_url": data.get("favicon_url"),
            "author_name": data.get("author_name"),
            "author_avatar": data.get("author_avatar"),
            "branding": data.get("branding"),
            "icon": data.get("icon"),
            "color": data.get("color", "#4F46E5"),
            "enable_toc": data.get("enable_toc", True),
            "enable_search": data.get("enable_search", True),
            "enable_feedback": data.get("enable_feedback", True),
            "created_at": now,
            "updated_at": now,
        }

        try:
            self.guides_collection.insert_one(guide_doc)
            logger.info(f"✅ Created guide: {guide_id} (slug: {data['slug']})")
            return guide_doc
        except DuplicateKeyError:
            logger.error(f"❌ Slug '{data['slug']}' already exists for user {user_id}")
            raise

    def get_guide(
        self, guide_id: str, user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Lấy guide by ID

        Args:
            guide_id: Guide UUID
            user_id: Optional - filter by owner

        Returns:
            Guide document or None
        """
        query = {"guide_id": guide_id}
        if user_id:
            query["user_id"] = user_id

        guide = self.guides_collection.find_one(query)
        return guide

    def get_guide_by_slug(
        self, slug: str, user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Lấy guide by slug

        Args:
            slug: URL slug
            user_id: Optional - filter by owner

        Returns:
            Guide document or None
        """
        query = {"slug": slug}
        if user_id:
            query["user_id"] = user_id

        guide = self.guides_collection.find_one(query)
        return guide

    def list_user_guides(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 20,
        visibility: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List guides của user với pagination

        Args:
            user_id: Firebase UID
            skip: Pagination offset
            limit: Items per page
            visibility: Filter by visibility ("public", "private", "unlisted", or None for all)

        Returns:
            List of guide documents
        """
        query = {"user_id": user_id}
        if visibility:
            query["visibility"] = visibility

        # Get paginated results (sorted by updated_at desc)
        guides = list(
            self.guides_collection.find(query)
            .sort("updated_at", -1)
            .skip(skip)
            .limit(limit)
        )

        logger.info(f"📊 Found {len(guides)} guides for user {user_id}")
        return guides

    def count_user_guides(
        self,
        user_id: str,
        visibility: Optional[str] = None,
    ) -> int:
        """Count total guides for user"""
        query = {"user_id": user_id}
        if visibility:
            query["visibility"] = visibility
        return self.guides_collection.count_documents(query)

    def update_guide(self, guide_id: str, update_data) -> Optional[Dict[str, Any]]:
        """
        Update guide metadata

        Args:
            guide_id: Guide UUID
            update_data: GuideUpdate Pydantic model or dict

        Returns:
            Updated guide document or None if not found
        """
        # Convert Pydantic model to dict if needed
        if hasattr(update_data, "model_dump"):
            updates = update_data.model_dump(exclude_unset=True)
        elif isinstance(update_data, dict):
            updates = update_data
        else:
            raise ValueError("update_data must be a Pydantic model or dict")

        # Add updated_at
        updates["updated_at"] = datetime.utcnow()

        result = self.guides_collection.find_one_and_update(
            {"guide_id": guide_id},
            {"$set": updates},
            return_document=ReturnDocument.AFTER,
        )

        if result:
            logger.info(f"✅ Updated guide: {guide_id}")
            return result
        else:
            logger.warning(f"⚠️ Guide not found: {guide_id}")
            return None

    def delete_guide(self, guide_id: str) -> bool:
        """
        Delete guide

        Args:
            guide_id: Guide UUID

        Returns:
            True if deleted, False if not found
        """
        result = self.guides_collection.delete_one({"guide_id": guide_id})

        if result.deleted_count > 0:
            logger.info(f"🗑️ Deleted guide: {guide_id}")
            return True
        else:
            logger.warning(f"⚠️ Guide not found: {guide_id}")
            return False

    def increment_view_count(self, guide_id: str, is_unique: bool = False) -> bool:
        """
        Increment view counter

        Args:
            guide_id: Guide UUID
            is_unique: Whether this is a unique visitor

        Returns:
            True if incremented
        """
        updates = {"$inc": {"view_count": 1}}
        if is_unique:
            updates["$inc"]["unique_visitors"] = 1

        result = self.guides_collection.update_one({"guide_id": guide_id}, updates)

        return result.modified_count > 0

    def slug_exists(
        self, slug: str, user_id: str, exclude_guide_id: Optional[str] = None
    ) -> bool:
        """
        Check if slug already exists for user

        Args:
            slug: Slug to check
            user_id: User's Firebase UID
            exclude_guide_id: Optional guide ID to exclude (for updates)

        Returns:
            True if exists, False otherwise
        """
        query = {"slug": slug, "user_id": user_id}
        if exclude_guide_id:
            query["guide_id"] = {"$ne": exclude_guide_id}

        return self.guides_collection.count_documents(query) > 0

    def get_guide_by_domain(self, domain: str) -> Optional[Dict[str, Any]]:
        """
        Get guide by custom domain (Phase 5 - for Next.js middleware)

        Args:
            domain: Custom domain (e.g., "python.example.com")

        Returns:
            Guide document or None if not found
        """
        guide = self.guides_collection.find_one(
            {"custom_domain": domain}, {"_id": 0}  # Exclude MongoDB ObjectId
        )

        if guide:
            logger.info(f"🌐 Found guide for domain: {domain} → {guide['slug']}")
        else:
            logger.warning(f"⚠️ No guide found for domain: {domain}")

        return guide
