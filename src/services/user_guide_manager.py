"""
User Guide Manager Service
Phase 1: Database operations for User Guides
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
import logging
from pymongo.errors import DuplicateKeyError

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
        title: str,
        slug: str,
        description: Optional[str] = None,
        visibility: str = "public",
        is_published: bool = False,
        **kwargs,
    ) -> str:
        """
        Tạo guide mới

        Args:
            user_id: Firebase UID of owner
            title: Guide title
            slug: URL-friendly slug
            description: Guide description
            visibility: "public" | "private" | "unlisted"
            is_published: Published state
            **kwargs: Additional fields (logo_url, primary_color, etc.)

        Returns:
            guide_id: UUID of created guide

        Raises:
            DuplicateKeyError: If slug already exists for user
        """
        guide_id = str(uuid.uuid4())
        now = datetime.utcnow()

        guide_doc = {
            "guide_id": guide_id,
            "user_id": user_id,
            "title": title,
            "description": description,
            "slug": slug,
            "visibility": visibility,
            "is_published": is_published,
            "logo_url": kwargs.get("logo_url"),
            "cover_image_url": kwargs.get("cover_image_url"),
            "primary_color": kwargs.get("primary_color", "#4F46E5"),
            "meta_title": kwargs.get("meta_title"),
            "meta_description": kwargs.get("meta_description"),
            "view_count": 0,
            "unique_visitors": 0,
            "created_at": now,
            "updated_at": now,
            "last_published_at": now if is_published else None,
        }

        try:
            self.guides_collection.insert_one(guide_doc)
            logger.info(f"✅ Created guide: {guide_id} (slug: {slug})")
            return guide_id
        except DuplicateKeyError:
            logger.error(f"❌ Slug '{slug}' already exists for user {user_id}")
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
        page: int = 1,
        limit: int = 20,
        visibility: Optional[str] = None,
        sort_by: str = "updated",
    ) -> tuple[List[Dict[str, Any]], int]:
        """
        List guides của user với pagination

        Args:
            user_id: Firebase UID
            page: Page number (1-indexed)
            limit: Items per page
            visibility: Filter by visibility ("public", "private", "unlisted", or None for all)
            sort_by: "updated" | "created" | "title"

        Returns:
            (guides list, total count)
        """
        query = {"user_id": user_id}
        if visibility:
            query["visibility"] = visibility

        # Sort mapping
        sort_map = {
            "updated": [("updated_at", -1)],
            "created": [("created_at", -1)],
            "title": [("title", 1)],
        }
        sort = sort_map.get(sort_by, [("updated_at", -1)])

        # Get total count
        total = self.guides_collection.count_documents(query)

        # Get paginated results
        skip = (page - 1) * limit
        guides = list(
            self.guides_collection.find(query).sort(sort).skip(skip).limit(limit)
        )

        logger.info(f"📊 Found {len(guides)} guides for user {user_id} (page {page})")
        return guides, total

    def update_guide(
        self, guide_id: str, user_id: str, updates: Dict[str, Any]
    ) -> bool:
        """
        Update guide metadata

        Args:
            guide_id: Guide UUID
            user_id: Owner's Firebase UID
            updates: Fields to update

        Returns:
            True if updated, False if not found
        """
        # Add updated_at
        updates["updated_at"] = datetime.utcnow()

        # If publishing, update last_published_at
        if updates.get("is_published") is True:
            updates["last_published_at"] = datetime.utcnow()

        result = self.guides_collection.update_one(
            {"guide_id": guide_id, "user_id": user_id}, {"$set": updates}
        )

        if result.modified_count > 0:
            logger.info(f"✅ Updated guide: {guide_id}")
            return True
        else:
            logger.warning(f"⚠️ Guide not found or not modified: {guide_id}")
            return False

    def delete_guide(self, guide_id: str, user_id: str) -> bool:
        """
        Delete guide

        Args:
            guide_id: Guide UUID
            user_id: Owner's Firebase UID

        Returns:
            True if deleted, False if not found
        """
        result = self.guides_collection.delete_one(
            {"guide_id": guide_id, "user_id": user_id}
        )

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
