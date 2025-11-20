"""
Author Manager Service
Manages author profiles for community books publishing
"""

import uuid
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from pymongo.errors import DuplicateKeyError
from pymongo import ReturnDocument

logger = logging.getLogger("chatbot")


class AuthorManager:
    """Manages author profiles in MongoDB"""

    def __init__(self, db):
        """
        Initialize AuthorManager

        Args:
            db: PyMongo Database object
        """
        self.db = db
        self.authors_collection = db["book_authors"]

    def create_indexes(self):
        """Create indexes for authors collection"""
        try:
            existing_indexes = [
                idx["name"] for idx in self.authors_collection.list_indexes()
            ]

            # Unique author_id
            if "author_id_unique" not in existing_indexes:
                self.authors_collection.create_index(
                    "author_id", unique=True, name="author_id_unique"
                )
                logger.info("✅ Created index: author_id_unique")

            # Query by user_id (1 user can have multiple authors)
            if "user_id_index" not in existing_indexes:
                self.authors_collection.create_index("user_id", name="user_id_index")
                logger.info("✅ Created index: user_id_index")

            # Search by name
            if "name_text_index" not in existing_indexes:
                self.authors_collection.create_index(
                    [("name", "text")], name="name_text_index"
                )
                logger.info("✅ Created index: name_text_index")

        except Exception as e:
            logger.error(f"❌ Failed to create indexes: {e}")

    def create_author(
        self, user_id: str, author_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Create new author profile

        Args:
            user_id: Firebase UID (owner)
            author_data: AuthorCreate data

        Returns:
            Created author document or None

        Raises:
            DuplicateKeyError: If author_id already exists
        """
        now = datetime.utcnow()

        author_doc = {
            "author_id": author_data["author_id"],  # Already validated and lowercased
            "name": author_data["name"],
            "bio": author_data.get("bio"),
            "avatar_url": author_data.get("avatar_url"),
            "website_url": author_data.get("website_url"),
            "social_links": author_data.get("social_links", {}),
            # Owner
            "user_id": user_id,
            # Stats
            "total_books": 0,
            "total_followers": 0,
            "total_revenue_points": 0,
            "books": [],  # List of published book_ids
            # Timestamps
            "created_at": now,
            "updated_at": now,
        }

        try:
            self.authors_collection.insert_one(author_doc)
            logger.info(
                f"✅ Created author: {author_data['author_id']} for user {user_id}"
            )
            return author_doc
        except DuplicateKeyError:
            logger.error(f"❌ Author ID already exists: {author_data['author_id']}")
            raise

    def get_author(self, author_id: str) -> Optional[Dict[str, Any]]:
        """Get author by ID"""
        return self.authors_collection.find_one(
            {"author_id": author_id.lower()}, {"_id": 0}
        )

    def get_author_by_user(
        self, user_id: str, skip: int = 0, limit: int = 20
    ) -> tuple[List[Dict[str, Any]], int]:
        """
        Get all authors created by a user

        Args:
            user_id: Firebase UID
            skip: Pagination offset
            limit: Items per page

        Returns:
            (authors list, total count)
        """
        total = self.authors_collection.count_documents({"user_id": user_id})
        authors = list(
            self.authors_collection.find({"user_id": user_id}, {"_id": 0})
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )

        logger.info(
            f"📚 Found {len(authors)} authors for user {user_id} (total: {total})"
        )
        return authors, total

    def update_author(
        self, author_id: str, update_data: Any, user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Update author profile

        Args:
            author_id: Author ID
            update_data: AuthorUpdate data (Pydantic model or dict)
            user_id: Firebase UID (must be owner)

        Returns:
            Updated author or None
        """
        # Convert to dict if it's a Pydantic model
        if hasattr(update_data, "model_dump"):
            update_dict = update_data.model_dump(exclude_unset=True, exclude_none=True)
        elif isinstance(update_data, dict):
            update_dict = {k: v for k, v in update_data.items() if v is not None}
        else:
            update_dict = {}

        if not update_dict:
            return self.get_author(author_id)

        update_dict["updated_at"] = datetime.utcnow()

        updated_author = self.authors_collection.find_one_and_update(
            {"author_id": author_id.lower(), "user_id": user_id},
            {"$set": update_dict},
            return_document=ReturnDocument.AFTER,
        )

        if updated_author:
            logger.info(f"✅ Updated author: {author_id}")
        else:
            logger.warning(f"⚠️ Author not found or not owned by user: {author_id}")

        return updated_author

    def delete_author(self, author_id: str, user_id: str) -> bool:
        """
        Delete author (only if no books published)

        Args:
            author_id: Author ID
            user_id: Firebase UID (must be owner)

        Returns:
            True if deleted
        """
        author = self.get_author(author_id)
        if not author:
            return False

        if author["user_id"] != user_id:
            logger.warning(f"⚠️ User {user_id} cannot delete author {author_id}")
            return False

        if author.get("total_books", 0) > 0:
            logger.warning(
                f"⚠️ Cannot delete author {author_id}: has {author['total_books']} published books"
            )
            return False

        result = self.authors_collection.delete_one(
            {"author_id": author_id.lower(), "user_id": user_id}
        )

        if result.deleted_count > 0:
            logger.info(f"✅ Deleted author: {author_id}")
            return True

        return False

    def add_book_to_author(self, author_id: str, book_id: str) -> bool:
        """
        Add book to author's published books list

        Args:
            author_id: Author ID
            book_id: Book UUID

        Returns:
            True if added
        """
        result = self.authors_collection.update_one(
            {"author_id": author_id.lower()},
            {
                "$addToSet": {"books": book_id},
                "$inc": {"total_books": 1},
                "$set": {"updated_at": datetime.utcnow()},
            },
        )

        if result.modified_count > 0:
            logger.info(f"✅ Added book {book_id} to author {author_id}")
            return True

        return False

    def remove_book_from_author(self, author_id: str, book_id: str) -> bool:
        """
        Remove book from author's published books list

        Args:
            author_id: Author ID
            book_id: Book UUID

        Returns:
            True if removed
        """
        result = self.authors_collection.update_one(
            {"author_id": author_id.lower()},
            {
                "$pull": {"books": book_id},
                "$inc": {"total_books": -1},
                "$set": {"updated_at": datetime.utcnow()},
            },
        )

        if result.modified_count > 0:
            logger.info(f"✅ Removed book {book_id} from author {author_id}")
            return True

        return False

    def list_authors(
        self,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[List[Dict[str, Any]], int]:
        """
        List all authors (public)

        Args:
            search: Search by name
            skip: Pagination offset
            limit: Items per page

        Returns:
            (authors list, total count)
        """
        query = {}

        if search:
            query["$text"] = {"$search": search}

        total = self.authors_collection.count_documents(query)
        authors = list(
            self.authors_collection.find(query, {"_id": 0})
            .sort([("total_books", -1), ("total_followers", -1)])
            .skip(skip)
            .limit(limit)
        )

        logger.info(
            f"📚 Listed {len(authors)} authors (total: {total}, search: {search})"
        )
        return authors, total

    def get_author_books(
        self, author_id: str, skip: int = 0, limit: int = 20
    ) -> tuple[List[str], int]:
        """
        Get list of book IDs published by author

        Args:
            author_id: Author ID
            skip: Pagination offset
            limit: Items per page

        Returns:
            (book_ids list, total count)
        """
        author = self.get_author(author_id)
        if not author:
            return [], 0

        all_book_ids = author.get("books", [])
        total = len(all_book_ids)

        # Paginate
        paginated_ids = all_book_ids[skip : skip + limit]

        return paginated_ids, total
