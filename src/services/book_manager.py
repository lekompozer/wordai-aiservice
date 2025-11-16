"""
User Guide Manager Service
Phase 1: Database operations for Online Books
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
import logging
from pymongo.errors import DuplicateKeyError
from pymongo import ReturnDocument

logger = logging.getLogger("chatbot")


class UserBookManager:
    """Quản lý Online Books trong MongoDB"""

    def __init__(self, db):
        """
        Initialize UserBookManager

        Args:
            db: PyMongo Database object (synchronous)
        """
        self.db = db
        self.guides_collection = db["online_books"]

    def create_indexes(self):
        """Tạo indexes cho collection user_guides"""
        try:
            existing_indexes = [
                idx["name"] for idx in self.guides_collection.list_indexes()
            ]

            # Primary key - unique identifier
            if "book_id_unique" not in existing_indexes:
                self.guides_collection.create_index(
                    "book_id", unique=True, name="book_id_unique"
                )
                logger.info("✅ Created index: book_id_unique")

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
        guide_data,  # BookCreate Pydantic model or individual params
    ) -> Dict[str, Any]:
        """
        Tạo guide mới

        Args:
            user_id: Firebase UID of owner
            guide_data: BookCreate Pydantic model with all fields

        Returns:
            guide document dict

        Raises:
            DuplicateKeyError: If slug already exists for user
        """
        book_id = f"guide_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow()

        # Convert Pydantic model to dict if needed
        if hasattr(guide_data, "model_dump"):
            data = guide_data.model_dump(exclude_unset=True)
        elif isinstance(guide_data, dict):
            data = guide_data
        else:
            raise ValueError("guide_data must be a Pydantic model or dict")

        guide_doc = {
            "book_id": book_id,
            "user_id": user_id,
            "title": data["title"],
            "slug": data["slug"],
            "description": data.get("description"),
            "visibility": data.get("visibility", "private"),  # Default: private
            "is_published": data.get("is_published", False),
            # Point-based access (NEW)
            "access_config": data.get("access_config"),  # Will be None or dict
            # Community config (initialized, not public by default)
            "community_config": {
                "is_public": False,
                "category": None,
                "tags": [],
                "short_description": None,
                "difficulty_level": None,
                "cover_image_url": data.get("cover_image_url"),
                "total_views": 0,
                "total_downloads": 0,
                "total_purchases": 0,
                "average_rating": 0.0,
                "rating_count": 0,
                "version": "1.0.0",
                "published_at": None,
            },
            # Revenue stats (initialized)
            "stats": {
                "total_revenue_points": 0,
                "owner_reward_points": 0,
                "system_fee_points": 0,
            },
            # SEO
            "is_indexed": data.get(
                "is_indexed", data.get("visibility", "public") == "public"
            ),
            "meta_title": data.get("meta_title"),
            "meta_description": data.get("meta_description"),
            # Branding
            "custom_domain": data.get("custom_domain"),
            "cover_image_url": data.get("cover_image_url"),
            "logo_url": data.get("logo_url"),
            "primary_color": data.get("primary_color", "#4F46E5"),
            # Analytics
            "view_count": 0,
            "unique_visitors": 0,
            # Timestamps
            "created_at": now,
            "updated_at": now,
            "last_published_at": None,
        }

        try:
            self.guides_collection.insert_one(guide_doc)
            logger.info(f"✅ Created guide: {book_id} (slug: {data['slug']})")
            return guide_doc
        except DuplicateKeyError:
            logger.error(f"❌ Slug '{data['slug']}' already exists for user {user_id}")
            raise

    def get_guide(
        self, book_id: str, user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Lấy guide by ID

        Args:
            book_id: Guide UUID
            user_id: Optional - filter by owner

        Returns:
            Guide document or None
        """
        query = {"book_id": book_id}
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

    def update_guide(self, book_id: str, update_data) -> Optional[Dict[str, Any]]:
        """
        Update guide metadata

        Args:
            book_id: Guide UUID
            update_data: BookUpdate Pydantic model or dict

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
            {"book_id": book_id},
            {"$set": updates},
            return_document=ReturnDocument.AFTER,
        )

        if result:
            logger.info(f"✅ Updated guide: {book_id}")
            return result
        else:
            logger.warning(f"⚠️ Guide not found: {book_id}")
            return None

    def delete_guide(self, book_id: str) -> bool:
        """
        Delete guide

        Args:
            book_id: Guide UUID

        Returns:
            True if deleted, False if not found
        """
        result = self.guides_collection.delete_one({"book_id": book_id})

        if result.deleted_count > 0:
            logger.info(f"🗑️ Deleted guide: {book_id}")
            return True
        else:
            logger.warning(f"⚠️ Guide not found: {book_id}")
            return False

    def increment_view_count(self, book_id: str, is_unique: bool = False) -> bool:
        """
        Increment view counter

        Args:
            book_id: Guide UUID
            is_unique: Whether this is a unique visitor

        Returns:
            True if incremented
        """
        updates = {"$inc": {"view_count": 1}}
        if is_unique:
            updates["$inc"]["unique_visitors"] = 1

        result = self.guides_collection.update_one({"book_id": book_id}, updates)

        return result.modified_count > 0

    def slug_exists(
        self, slug: str, user_id: str, exclude_book_id: Optional[str] = None
    ) -> bool:
        """
        Check if slug already exists for user

        Args:
            slug: Slug to check
            user_id: User's Firebase UID
            exclude_book_id: Optional guide ID to exclude (for updates)

        Returns:
            True if exists, False otherwise
        """
        query = {"slug": slug, "user_id": user_id}
        if exclude_book_id:
            query["book_id"] = {"$ne": exclude_book_id}

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

    # ============ COMMUNITY BOOKS METHODS (NEW - Phase 6) ============

    def publish_to_community(
        self,
        book_id: str,
        user_id: str,
        publish_data: Dict[str, Any],
        author_id: str,  # Resolved author_id (from existing or newly created)
    ) -> Optional[Dict[str, Any]]:
        """
        Publish book to community marketplace

        Args:
            book_id: Book UUID
            user_id: Owner's Firebase UID
            publish_data: CommunityPublishRequest data
            author_id: Author ID to publish under (e.g., @john_doe)

        Returns:
            Updated book document or None
        """
        now = datetime.utcnow()

        update_data = {
            "$set": {
                # Set author
                "author_id": author_id,
                # Set visibility & access config
                "visibility": publish_data["visibility"],
                "access_config": publish_data.get("access_config"),
                # Community marketplace metadata
                "community_config.is_public": True,
                "community_config.category": publish_data["category"],
                "community_config.tags": publish_data["tags"],
                "community_config.difficulty_level": publish_data["difficulty_level"],
                "community_config.short_description": publish_data["short_description"],
                "community_config.published_at": now,
                "updated_at": now,
            }
        }

        # Update cover image if provided
        if publish_data.get("cover_image_url"):
            update_data["$set"]["community_config.cover_image_url"] = publish_data[
                "cover_image_url"
            ]

        updated_book = self.guides_collection.find_one_and_update(
            {"book_id": book_id, "user_id": user_id},
            update_data,
            return_document=ReturnDocument.AFTER,
        )

        if updated_book:
            logger.info(
                f"✅ Published book to community: {book_id} by author {author_id} (category: {publish_data['category']})"
            )
        else:
            logger.warning(f"⚠️ Book not found or not owned by user: {book_id}")

        return updated_book

    def unpublish_from_community(
        self, book_id: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Unpublish book from community marketplace

        Args:
            book_id: Book UUID
            user_id: Owner's Firebase UID

        Returns:
            Updated book document or None
        """
        updated_book = self.guides_collection.find_one_and_update(
            {"book_id": book_id, "user_id": user_id},
            {
                "$set": {
                    "visibility": "private",  # Reset to private when unpublishing
                    "access_config": None,  # Clear access config
                    "community_config.is_public": False,
                    "updated_at": datetime.utcnow(),
                }
            },
            return_document=ReturnDocument.AFTER,
        )

        if updated_book:
            logger.info(f"✅ Unpublished book from community: {book_id}")
        else:
            logger.warning(f"⚠️ Book not found or not owned by user: {book_id}")

        return updated_book

    def list_community_books(
        self,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        difficulty: Optional[str] = None,
        sort_by: str = "popular",  # popular, newest, rating
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[List[Dict[str, Any]], int]:
        """
        List public community books with filters

        Args:
            category: Filter by category
            tags: Filter by tags (any match)
            difficulty: Filter by difficulty level
            sort_by: Sort method (popular, newest, rating)
            skip: Pagination offset
            limit: Items per page

        Returns:
            (books list, total count)
        """
        query = {"community_config.is_public": True}

        if category:
            query["community_config.category"] = category
        if tags:
            query["community_config.tags"] = {"$in": tags}
        if difficulty:
            query["community_config.difficulty_level"] = difficulty

        # Determine sort order
        if sort_by == "popular":
            sort_field = [
                ("community_config.total_purchases", -1),
                ("community_config.total_views", -1),
            ]
        elif sort_by == "newest":
            sort_field = [("community_config.published_at", -1)]
        elif sort_by == "rating":
            sort_field = [
                ("community_config.average_rating", -1),
                ("community_config.rating_count", -1),
            ]
        else:
            sort_field = [("community_config.published_at", -1)]

        # Get total count
        total = self.guides_collection.count_documents(query)

        # Get books
        books = list(
            self.guides_collection.find(query, {"_id": 0})
            .sort(sort_field)
            .skip(skip)
            .limit(limit)
        )

        logger.info(
            f"📚 Found {len(books)} community books (total: {total}, category: {category}, sort: {sort_by})"
        )

        return books, total
