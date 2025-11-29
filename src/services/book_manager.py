"""
User Book Manager Service
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
    """Manage Online Books trong MongoDB"""

    def __init__(self, db):
        """
        Initialize UserBookManager

        Args:
            db: PyMongo Database object (synchronous)
        """
        self.db = db
        self.books_collection = db["online_books"]

    def create_indexes(self):
        """Tạo indexes cho collection user_guides"""
        try:
            existing_indexes = [
                idx["name"] for idx in self.books_collection.list_indexes()
            ]

            # Primary key - unique identifier
            if "book_id_unique" not in existing_indexes:
                self.books_collection.create_index(
                    "book_id", unique=True, name="book_id_unique"
                )
                logger.info("✅ Created index: book_id_unique")

            # User's books listing (sorted by update time)
            if "user_guides_list" not in existing_indexes:
                self.books_collection.create_index(
                    [("user_id", 1), ("updated_at", -1)], name="user_guides_list"
                )
                logger.info("✅ Created index: user_guides_list")

            # Unique slug per user
            if "user_slug_unique" not in existing_indexes:
                self.books_collection.create_index(
                    [("user_id", 1), ("slug", 1)], unique=True, name="user_slug_unique"
                )
                logger.info("✅ Created index: user_slug_unique")

            # Public book lookup by slug
            if "public_guide_lookup" not in existing_indexes:
                self.books_collection.create_index(
                    [("slug", 1), ("visibility", 1)], name="public_guide_lookup"
                )
                logger.info("✅ Created index: public_guide_lookup")

            # Filter by visibility
            if "visibility_filter" not in existing_indexes:
                self.books_collection.create_index(
                    [("visibility", 1), ("is_published", 1)], name="visibility_filter"
                )
                logger.info("✅ Created index: visibility_filter")

            logger.info("✅ User Guide indexes verified/created")
        except Exception as e:
            logger.error(f"❌ Error creating book indexes: {e}")
            raise

    def create_book(
        self,
        user_id: str,
        guide_data,  # BookCreate Pydantic model or individual params
    ) -> Dict[str, Any]:
        """
        Tạo book mới

        Args:
            user_id: Firebase UID of owner
            guide_data: BookCreate Pydantic model with all fields

        Returns:
            book document dict

        Raises:
            DuplicateKeyError: If slug already exists for user
        """
        book_id = f"book_{uuid.uuid4().hex[:12]}"
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
            "is_deleted": False,  # ✅ CRITICAL: Mark as active (not deleted)
            # Authors (NEW - Support multiple authors)
            "authors": [],  # Empty array initially, populated when publishing to community
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
            self.books_collection.insert_one(guide_doc)
            logger.info(f"✅ Created book: {book_id} (slug: {data['slug']})")
            return guide_doc
        except DuplicateKeyError:
            logger.error(f"❌ Slug '{data['slug']}' already exists for user {user_id}")
            raise

    def get_book(
        self, book_id: str, user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Lấy book by ID

        Args:
            book_id: Guide UUID
            user_id: Optional - filter by owner

        Returns:
            Guide document or None
        """
        query = {"book_id": book_id}
        if user_id:
            query["user_id"] = user_id

        book = self.books_collection.find_one(query)
        return book

    def get_book_by_slug(
        self, slug: str, user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Lấy book by slug

        Args:
            slug: URL slug
            user_id: Optional - filter by owner

        Returns:
            Guide document or None
        """
        query = {"slug": slug}
        if user_id:
            query["user_id"] = user_id

        book = self.books_collection.find_one(query)
        return book

    def list_user_books(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 20,
        visibility: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List books của user với pagination (excludes deleted books)

        Args:
            user_id: Firebase UID
            skip: Pagination offset
            limit: Items per page
            visibility: Filter by visibility ("public", "private", "unlisted", or None for all)

        Returns:
            List of book documents
        """
        query = {"user_id": user_id, "is_deleted": False}  # Exclude deleted books
        if visibility:
            query["visibility"] = visibility

        # Get paginated results (sorted by updated_at desc)
        guides = list(
            self.books_collection.find(query)
            .sort("updated_at", -1)
            .skip(skip)
            .limit(limit)
        )

        logger.info(f"📊 Found {len(guides)} books for user {user_id}")
        return guides

    def count_user_books(
        self,
        user_id: str,
        visibility: Optional[str] = None,
    ) -> int:
        """Count total guides for user (excludes deleted books)"""
        query = {"user_id": user_id, "is_deleted": False}  # Exclude deleted books
        if visibility:
            query["visibility"] = visibility
        return self.books_collection.count_documents(query)

    def update_book(self, book_id: str, update_data) -> Optional[Dict[str, Any]]:
        """
        Update book metadata

        Args:
            book_id: Guide UUID
            update_data: BookUpdate Pydantic model or dict

        Returns:
            Updated book document or None if not found
        """
        # Convert Pydantic model to dict if needed
        if hasattr(update_data, "model_dump"):
            updates = update_data.model_dump(exclude_unset=True)
        elif isinstance(update_data, dict):
            updates = update_data
        else:
            raise ValueError("update_data must be a Pydantic model or dict")

        # Sync community_config.cover_image_url to root cover_image_url if updated
        if "community_config" in updates and isinstance(
            updates["community_config"], dict
        ):
            if "cover_image_url" in updates["community_config"]:
                updates["cover_image_url"] = updates["community_config"][
                    "cover_image_url"
                ]

        # Add updated_at
        updates["updated_at"] = datetime.utcnow()

        result = self.books_collection.find_one_and_update(
            {"book_id": book_id},
            {"$set": updates},
            return_document=ReturnDocument.AFTER,
        )

        if result:
            logger.info(f"✅ Updated book: {book_id}")
            return result
        else:
            logger.warning(f"⚠️ Book not found: {book_id}")
            return None

    def touch_book(self, book_id: str) -> bool:
        """
        Update the book's updated_at timestamp to current time.
        Useful when chapters or related content changes.

        Args:
            book_id: Guide UUID

        Returns:
            True if updated, False if not found
        """
        result = self.books_collection.update_one(
            {"book_id": book_id}, {"$set": {"updated_at": datetime.utcnow()}}
        )

        if result.modified_count > 0:
            logger.debug(f"⏱️ Updated book timestamp: {book_id}")
            return True
        return False

    def delete_book(self, book_id: str) -> bool:
        """
        Delete book

        Args:
            book_id: Guide UUID

        Returns:
            True if deleted, False if not found
        """
        result = self.books_collection.delete_one({"book_id": book_id})

        if result.deleted_count > 0:
            logger.info(f"🗑️ Deleted book: {book_id}")
            return True
        else:
            logger.warning(f"⚠️ Book not found: {book_id}")
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

        result = self.books_collection.update_one({"book_id": book_id}, updates)

        return result.modified_count > 0

    def slug_exists(
        self, slug: str, user_id: str, exclude_book_id: Optional[str] = None
    ) -> bool:
        """
        Check if slug already exists for user

        Args:
            slug: Slug to check
            user_id: User's Firebase UID
            exclude_book_id: Optional book ID to exclude (for updates)

        Returns:
            True if exists, False otherwise
        """
        query = {"slug": slug, "user_id": user_id}
        if exclude_book_id:
            query["book_id"] = {"$ne": exclude_book_id}

        return self.books_collection.count_documents(query) > 0

    def get_book_by_domain(self, domain: str) -> Optional[Dict[str, Any]]:
        """
        Get book by custom domain (Phase 5 - for Next.js middleware)

        Args:
            domain: Custom domain (e.g., "python.example.com")

        Returns:
            Guide document or None if not found
        """
        book = self.books_collection.find_one(
            {"custom_domain": domain}, {"_id": 0}  # Exclude MongoDB ObjectId
        )

        if book:
            logger.info(f"🌐 Found book for domain: {domain} → {book['slug']}")
        else:
            logger.warning(f"⚠️ No book found for domain: {domain}")

        return book

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
                # Set authors (NEW - array format for multi-author support)
                "authors": [author_id],  # Store as array
                # Legacy field for backward compatibility
                "author_id": author_id,  # Keep for old code that reads this field
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

        # Update book description if provided (optional)
        if publish_data.get("description") is not None:
            update_data["$set"]["description"] = publish_data["description"]

        # Update cover image if provided
        if publish_data.get("cover_image_url"):
            # Update both community_config and root level for consistency
            update_data["$set"]["community_config.cover_image_url"] = publish_data[
                "cover_image_url"
            ]
            update_data["$set"]["cover_image_url"] = publish_data["cover_image_url"]

        updated_book = self.books_collection.find_one_and_update(
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
        updated_book = self.books_collection.find_one_and_update(
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
        total = self.books_collection.count_documents(query)

        # Get books
        books = list(
            self.books_collection.find(query, {"_id": 0})
            .sort(sort_field)
            .skip(skip)
            .limit(limit)
        )

        logger.info(
            f"📚 Found {len(books)} community books (total: {total}, category: {category}, sort: {sort_by})"
        )

        return books, total

    # ============ TRASH SYSTEM (NEW) ============

    def soft_delete_book(self, book_id: str, user_id: str) -> bool:
        """
        Move book to trash (soft delete)

        Args:
            book_id: Book ID to delete
            user_id: Owner user ID (for verification)

        Returns:
            True if deleted, False if not found or not owner
        """
        now = datetime.utcnow()

        result = self.books_collection.update_one(
            {"book_id": book_id, "user_id": user_id},
            {
                "$set": {
                    "is_deleted": True,
                    "deleted_at": now,
                    "deleted_by": user_id,
                    "updated_at": now,
                }
            },
        )

        if result.modified_count > 0:
            logger.info(f"🗑️ Moved book {book_id} to trash")
            return True
        else:
            logger.warning(
                f"❌ Failed to move book {book_id} to trash (not found or not owner)"
            )
            return False

    def list_trash(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 20,
        sort_by: str = "deleted_at",
    ) -> tuple[List[Dict[str, Any]], int]:
        """
        List books in trash

        Args:
            user_id: Owner user ID
            skip: Pagination offset
            limit: Items per page
            sort_by: Sort field (default: deleted_at)

        Returns:
            Tuple of (books list, total count)
        """
        query = {"user_id": user_id, "is_deleted": True}

        # Get total count
        total = self.books_collection.count_documents(query)

        # Get books (sorted descending)
        sort_field = [(sort_by, -1)]
        books = list(
            self.books_collection.find(query, {"_id": 0})
            .sort(sort_field)
            .skip(skip)
            .limit(limit)
        )

        logger.info(f"🗑️ Found {len(books)} books in trash (total: {total})")
        return books, total

    def restore_book(self, book_id: str, user_id: str) -> bool:
        """
        Restore book from trash

        Args:
            book_id: Book ID to restore
            user_id: Owner user ID (for verification)

        Returns:
            True if restored, False if not found or not in trash
        """
        now = datetime.utcnow()

        result = self.books_collection.update_one(
            {"book_id": book_id, "user_id": user_id, "is_deleted": True},
            {
                "$set": {"is_deleted": False, "updated_at": now},
                "$unset": {"deleted_at": "", "deleted_by": ""},
            },
        )

        if result.modified_count > 0:
            logger.info(f"♻️ Restored book {book_id} from trash")
            return True
        else:
            logger.warning(
                f"❌ Failed to restore book {book_id} (not found or not in trash)"
            )
            return False

    def permanent_delete_book(self, book_id: str, user_id: str) -> bool:
        """
        Permanently delete book (hard delete)

        Args:
            book_id: Book ID to delete
            user_id: Owner user ID (for verification)

        Returns:
            True if deleted, False if not found
        """
        result = self.books_collection.delete_one(
            {"book_id": book_id, "user_id": user_id}
        )

        if result.deleted_count > 0:
            logger.info(f"💀 Permanently deleted book {book_id}")
            return True
        else:
            logger.warning(f"❌ Failed to delete book {book_id} (not found)")
            return False

    def empty_trash(self, user_id: str) -> Dict[str, int]:
        """
        Permanently delete all books in trash (hard delete)

        Args:
            user_id: Owner user ID

        Returns:
            Dict with stats: deleted_books, deleted_chapters, deleted_permissions
        """
        # Get all books in trash
        trash_books = list(
            self.books_collection.find(
                {"user_id": user_id, "is_deleted": True}, {"book_id": 1}
            )
        )

        stats = {
            "deleted_books": 0,
            "deleted_chapters": 0,
            "deleted_permissions": 0,
        }

        for book in trash_books:
            book_id = book["book_id"]

            # Delete chapters
            chapters_result = self.db["book_chapters"].delete_many({"book_id": book_id})
            stats["deleted_chapters"] += chapters_result.deleted_count

            # Delete permissions
            perms_result = self.db["book_permissions"].delete_many({"book_id": book_id})
            stats["deleted_permissions"] += perms_result.deleted_count

            # Delete book
            self.books_collection.delete_one({"book_id": book_id})
            stats["deleted_books"] += 1

        logger.info(
            f"🧹 Emptied trash for user {user_id}: {stats['deleted_books']} books, "
            f"{stats['deleted_chapters']} chapters, {stats['deleted_permissions']} permissions"
        )

        return stats
