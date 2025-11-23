"""
Guide Chapter Manager Service
Phase 1: Database operations for Guide Chapters
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
import logging
from pymongo.errors import DuplicateKeyError
from pymongo import ReturnDocument

logger = logging.getLogger("chatbot")


class GuideBookBookChapterManager:
    """Quản lý Guide Chapters trong MongoDB"""

    MAX_DEPTH = 2  # 0, 1, 2 = 3 levels total

    def __init__(self, db):
        """
        Initialize GuideBookBookChapterManager

        Args:
            db: PyMongo Database object (synchronous)
        """
        self.db = db
        self.chapters_collection = db["book_chapters"]

    def create_indexes(self):
        """Tạo indexes cho collection guide_chapters"""
        try:
            existing_indexes = [
                idx["name"] for idx in self.chapters_collection.list_indexes()
            ]

            # Primary key
            if "chapter_id_unique" not in existing_indexes:
                self.chapters_collection.create_index(
                    "chapter_id", unique=True, name="chapter_id_unique"
                )
                logger.info("✅ Created index: chapter_id_unique")

            # Get all chapters for a guide (ordered)
            if "guide_chapters_order" not in existing_indexes:
                self.chapters_collection.create_index(
                    [("book_id", 1), ("order", 1)], name="guide_chapters_order"
                )
                logger.info("✅ Created index: guide_chapters_order")

            # Nested structure queries
            if "nested_chapters" not in existing_indexes:
                self.chapters_collection.create_index(
                    [("book_id", 1), ("parent_chapter_id", 1), ("order", 1)],
                    name="nested_chapters",
                )
                logger.info("✅ Created index: nested_chapters")

            # Document usage tracking
            if "document_usage" not in existing_indexes:
                self.chapters_collection.create_index(
                    "document_id", name="document_usage"
                )
                logger.info("✅ Created index: document_usage")

            # Unique chapter slug per guide
            if "chapter_slug_unique" not in existing_indexes:
                self.chapters_collection.create_index(
                    [("book_id", 1), ("slug", 1)],
                    unique=True,
                    name="chapter_slug_unique",
                )
                logger.info("✅ Created index: chapter_slug_unique")

            logger.info("✅ Guide Chapter indexes verified/created")
        except Exception as e:
            logger.error(f"❌ Error creating chapter indexes: {e}")
            raise

    def create_chapter(self, book_id: str, chapter_data) -> Dict[str, Any]:
        """
        Create a new chapter (Pydantic model interface)

        Args:
            book_id: Guide UUID
            chapter_data: ChapterCreate Pydantic model

        Returns:
            Chapter document dict
        """
        # Convert Pydantic model to dict
        if hasattr(chapter_data, "model_dump"):
            data = chapter_data.model_dump(exclude_unset=True)
        elif isinstance(chapter_data, dict):
            data = chapter_data
        else:
            raise ValueError("chapter_data must be a Pydantic model or dict")

        chapter_id = f"chapter_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow()

        # Calculate depth
        parent_id = data.get("parent_id")
        depth = self._calculate_depth(parent_id)
        if depth > self.MAX_DEPTH:
            raise ValueError(
                f"Maximum nesting depth ({self.MAX_DEPTH + 1} levels) exceeded"
            )

        # Get order_index (support both 'order' and 'order_index' fields)
        order_index = data.get("order", data.get("order_index", 0))

        # Determine content storage model
        content_source = data.get("content_source", "inline")  # Default: inline
        document_id = data.get("document_id")

        # If document_id provided, force content_source to 'document'
        if document_id:
            content_source = "document"

        chapter_doc = {
            "chapter_id": chapter_id,
            "book_id": book_id,
            "parent_id": parent_id,
            "title": data["title"],
            "slug": data["slug"],
            "order_index": order_index,
            "depth": depth,
            # Content storage model
            "content_source": content_source,  # "inline" or "document"
            "document_id": document_id if content_source == "document" else None,
            # Inline content (only for content_source="inline")
            "content_html": (
                data.get("content_html") if content_source == "inline" else None
            ),
            "content_json": (
                data.get("content_json") if content_source == "inline" else None
            ),
            # Publishing & preview
            "is_published": data.get("is_published", True),
            "is_preview_free": data.get("is_preview_free", False),
            # Timestamps
            "created_at": now,
            "updated_at": now,
        }

        try:
            self.chapters_collection.insert_one(chapter_doc)
            logger.info(
                f"✅ Created chapter: {chapter_id} in guide {book_id} (depth: {depth})"
            )
            return chapter_doc
        except DuplicateKeyError:
            logger.error(f"❌ Slug '{data['slug']}' already exists in guide {book_id}")
            raise

    def add_chapter(
        self,
        book_id: str,
        document_id: str,
        order: int,
        slug: str,
        title: Optional[str] = None,
        parent_chapter_id: Optional[str] = None,
        icon: str = "📘",
        is_visible: bool = True,
        is_expanded: bool = True,
    ) -> str:
        """
        Add chapter to guide

        Args:
            book_id: Guide UUID
            document_id: Document UUID
            order: Display order
            slug: Chapter URL slug
            title: Optional title override
            parent_chapter_id: Parent chapter for nesting
            icon: Emoji or icon
            is_visible: Show in navigation
            is_expanded: Default expanded state

        Returns:
            chapter_id: UUID of created chapter

        Raises:
            ValueError: If max depth exceeded
            DuplicateKeyError: If slug already exists in guide
        """
        chapter_id = str(uuid.uuid4())
        now = datetime.utcnow()

        # Calculate depth
        depth = self._calculate_depth(parent_chapter_id)
        if depth > self.MAX_DEPTH:
            raise ValueError(
                f"Maximum nesting depth ({self.MAX_DEPTH + 1} levels) exceeded"
            )

        chapter_doc = {
            "chapter_id": chapter_id,
            "book_id": book_id,
            "document_id": document_id,
            "parent_chapter_id": parent_chapter_id,
            "order": order,
            "depth": depth,
            "title": title,
            "slug": slug,
            "icon": icon,
            "is_visible": is_visible,
            "is_expanded": is_expanded,
            "added_at": now,
            "updated_at": now,
        }

        try:
            self.chapters_collection.insert_one(chapter_doc)
            logger.info(
                f"✅ Added chapter: {chapter_id} to guide {book_id} (depth: {depth})"
            )
            return chapter_id
        except DuplicateKeyError:
            logger.error(f"❌ Slug '{slug}' already exists in guide {book_id}")
            raise

    def get_chapter(self, chapter_id: str) -> Optional[Dict[str, Any]]:
        """Get chapter by ID"""
        return self.chapters_collection.find_one({"chapter_id": chapter_id}, {"_id": 0})

    def get_chapters(
        self, book_id: str, include_hidden: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get all chapters for a guide (flat list)

        Args:
            book_id: Guide UUID
            include_hidden: Include hidden chapters

        Returns:
            List of chapter documents
        """
        query = {"book_id": book_id}
        if not include_hidden:
            query["is_visible"] = True

        chapters = list(
            self.chapters_collection.find(query, {"_id": 0}).sort([("order", 1)])
        )

        logger.info(f"📊 Found {len(chapters)} chapters for guide {book_id}")
        return chapters

    def list_chapters(self, book_id: str) -> List[Dict[str, Any]]:
        """
        List all published chapters for a guide (alias for get_chapters)
        Used by Phase 5 public API

        Args:
            book_id: Guide UUID

        Returns:
            List of chapter documents sorted by order_index
        """
        query = {"book_id": book_id, "is_published": True}
        chapters = list(
            self.chapters_collection.find(query, {"_id": 0}).sort([("order_index", 1)])
        )

        logger.info(f"📊 Found {len(chapters)} published chapters for guide {book_id}")
        return chapters

    def get_chapter_tree(
        self, book_id: str, include_unpublished: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Build nested tree structure from flat chapter list

        Args:
            book_id: Guide UUID
            include_unpublished: Include unpublished chapters

        Returns:
            List of root chapters with nested children
        """
        query = {"book_id": book_id}
        if not include_unpublished:
            query["is_published"] = True

        # Exclude MongoDB _id field to avoid serialization issues
        chapters = list(
            self.chapters_collection.find(query, {"_id": 0}).sort("order_index", 1)
        )

        # Build chapter map
        chapter_map = {}
        for chapter in chapters:
            chapter_id = chapter["chapter_id"]
            chapter_map[chapter_id] = {**chapter, "children": []}

        # Build tree
        tree = []
        for chapter in chapters:
            chapter_id = chapter["chapter_id"]
            parent_id = chapter.get("parent_id")

            if parent_id is None:
                # Root level
                tree.append(chapter_map[chapter_id])
            else:
                # Nested - add to parent's children
                parent = chapter_map.get(parent_id)
                if parent:
                    parent["children"].append(chapter_map[chapter_id])

        # Sort tree recursively
        self._sort_tree(tree)

        return tree

    def update_chapter(self, chapter_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update chapter settings

        Args:
            chapter_id: Chapter UUID
            updates: Fields to update

        Returns:
            True if updated
        """
        # Validate depth if changing parent
        if "parent_chapter_id" in updates:
            new_parent = updates["parent_chapter_id"]
            new_depth = self._calculate_depth(new_parent)
            if new_depth > self.MAX_DEPTH:
                raise ValueError(
                    f"Maximum nesting depth ({self.MAX_DEPTH + 1} levels) exceeded"
                )
            updates["depth"] = new_depth

        updates["updated_at"] = datetime.utcnow()

        result = self.chapters_collection.update_one(
            {"chapter_id": chapter_id}, {"$set": updates}
        )

        if result.modified_count > 0:
            logger.info(f"✅ Updated chapter: {chapter_id}")
            return True
        return False

    def reorder_chapters(self, chapters: List[Dict[str, Any]]) -> int:
        """
        Bulk reorder chapters

        Args:
            chapters: List of {chapter_id, order, parent_chapter_id}

        Returns:
            Number of chapters updated
        """
        updated_count = 0
        now = datetime.utcnow()

        for chapter_data in chapters:
            chapter_id = chapter_data["chapter_id"]
            order = chapter_data["order"]
            parent_id = chapter_data.get("parent_chapter_id")

            # Calculate new depth
            depth = self._calculate_depth(parent_id)
            if depth > self.MAX_DEPTH:
                logger.warning(f"⚠️ Skipping chapter {chapter_id}: max depth exceeded")
                continue

            result = self.chapters_collection.update_one(
                {"chapter_id": chapter_id},
                {
                    "$set": {
                        "order": order,
                        "parent_chapter_id": parent_id,
                        "depth": depth,
                        "updated_at": now,
                    }
                },
            )

            if result.modified_count > 0:
                updated_count += 1

        logger.info(f"✅ Reordered {updated_count} chapters")
        return updated_count

    def delete_chapter(self, chapter_id: str) -> bool:
        """
        Delete chapter (does not cascade delete children)

        Args:
            chapter_id: Chapter UUID

        Returns:
            True if deleted
        """
        result = self.chapters_collection.delete_one({"chapter_id": chapter_id})

        if result.deleted_count > 0:
            logger.info(f"🗑️ Deleted chapter: {chapter_id}")
            return True
        return False

    def delete_chapters_by_guide(self, book_id: str) -> int:
        """
        Delete all chapters for a guide (cascade delete when guide is deleted)

        Args:
            book_id: Guide UUID

        Returns:
            Number of chapters deleted
        """
        result = self.chapters_collection.delete_many({"book_id": book_id})
        deleted_count = result.deleted_count

        logger.info(f"🗑️ Deleted {deleted_count} chapters for guide {book_id}")
        return deleted_count

    def get_document_usage(self, document_id: str) -> List[Dict[str, Any]]:
        """
        Find which guides use this document

        Args:
            document_id: Document UUID

        Returns:
            List of chapters using this document
        """
        chapters = list(
            self.chapters_collection.find({"document_id": document_id}, {"_id": 0})
        )
        logger.info(f"📊 Document {document_id} used in {len(chapters)} chapters")
        return chapters

    def count_chapters(self, book_id: str) -> int:
        """Count total chapters in guide"""
        return self.chapters_collection.count_documents({"book_id": book_id})

    def slug_exists(
        self, book_id: str, slug: str, exclude_chapter_id: Optional[str] = None
    ) -> bool:
        """
        Check if slug already exists in guide

        Args:
            book_id: Guide UUID
            slug: Slug to check
            exclude_chapter_id: Optional chapter ID to exclude (for updates)

        Returns:
            True if exists
        """
        query = {"book_id": book_id, "slug": slug}
        if exclude_chapter_id:
            query["chapter_id"] = {"$ne": exclude_chapter_id}

        return self.chapters_collection.count_documents(query) > 0

    def _calculate_depth(self, parent_chapter_id: Optional[str]) -> int:
        """
        Calculate depth of chapter based on parent

        Args:
            parent_chapter_id: Parent chapter UUID or None

        Returns:
            Depth level (0 = root, 1 = nested, 2 = deeply nested)
        """
        if parent_chapter_id is None:
            return 0

        parent = self.get_chapter(parent_chapter_id)
        if not parent:
            return 0

        return parent.get("depth", 0) + 1

    def _sort_tree(self, nodes: List[Dict[str, Any]]):
        """
        Recursively sort tree by order

        Args:
            nodes: List of chapter nodes (modified in place)
        """
        nodes.sort(key=lambda x: x.get("order_index", x.get("order", 0)))
        for node in nodes:
            if node.get("children"):
                self._sort_tree(node["children"])

    def update_chapter(self, chapter_id: str, update_data) -> Optional[Dict[str, Any]]:
        """
        Update chapter (Pydantic model interface)

        Args:
            chapter_id: Chapter UUID
            update_data: ChapterUpdate Pydantic model

        Returns:
            Updated chapter document or None
        """
        # Convert Pydantic model to dict
        if hasattr(update_data, "model_dump"):
            updates = update_data.model_dump(exclude_unset=True)
        elif isinstance(update_data, dict):
            updates = update_data
        else:
            raise ValueError("update_data must be a Pydantic model or dict")

        # Add updated_at
        updates["updated_at"] = datetime.utcnow()

        # Recalculate depth if parent changed
        if "parent_id" in updates:
            updates["depth"] = self._calculate_depth(updates["parent_id"])

        result = self.chapters_collection.find_one_and_update(
            {"chapter_id": chapter_id},
            {"$set": updates},
            return_document=ReturnDocument.AFTER,
        )

        if result:
            logger.info(f"✅ Updated chapter: {chapter_id}")
            return result
        else:
            logger.warning(f"⚠️ Chapter not found: {chapter_id}")
            return None

    def update_chapter_content(
        self,
        chapter_id: str,
        content_html: str,
        content_json: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Update chapter content (handles both inline and document-linked chapters)

        Args:
            chapter_id: Chapter UUID
            content_html: HTML content to save
            content_json: Optional JSON content (TipTap format)

        Returns:
            True if updated successfully

        Raises:
            ValueError: If chapter not found or invalid content_source
        """
        # Get chapter to check content_source
        chapter = self.chapters_collection.find_one(
            {"chapter_id": chapter_id},
            {"_id": 0, "content_source": 1, "document_id": 1, "book_id": 1},
        )

        if not chapter:
            raise ValueError(f"Chapter not found: {chapter_id}")

        content_source = chapter.get("content_source", "inline")
        now = datetime.utcnow()

        if content_source == "inline":
            # Update content directly in chapter document
            result = self.chapters_collection.update_one(
                {"chapter_id": chapter_id},
                {
                    "$set": {
                        "content_html": content_html,
                        "content_json": content_json,
                        "updated_at": now,
                    }
                },
            )

            if result.modified_count > 0:
                logger.info(
                    f"✅ Updated inline chapter content: {chapter_id} "
                    f"({len(content_html)} chars)"
                )
                return True
            return False

        elif content_source == "document":
            # Update content in linked document
            document_id = chapter.get("document_id")
            if not document_id:
                raise ValueError(
                    f"Chapter {chapter_id} has content_source='document' but no document_id"
                )

            result = self.db["documents"].update_one(
                {"document_id": document_id},
                {
                    "$set": {
                        "content_html": content_html,
                        "file_size_bytes": len(content_html.encode("utf-8")),
                        "last_saved_at": now,
                        "updated_at": now,
                    },
                    "$inc": {"version": 1},
                },
            )

            if result.modified_count > 0:
                logger.info(
                    f"✅ Updated document content for chapter {chapter_id}: "
                    f"document {document_id} ({len(content_html)} chars)"
                )

                # Also update chapter's updated_at timestamp
                self.chapters_collection.update_one(
                    {"chapter_id": chapter_id}, {"$set": {"updated_at": now}}
                )
                return True
            return False

        else:
            raise ValueError(f"Unknown content_source: {content_source}")

    def delete_chapter_cascade(self, chapter_id: str) -> List[str]:
        """
        Delete chapter and all descendants recursively

        Args:
            chapter_id: Chapter UUID to delete

        Returns:
            List of deleted chapter IDs
        """
        deleted_ids = []

        # Find all children recursively
        def find_descendants(parent_id: str):
            children = list(
                self.chapters_collection.find({"parent_id": parent_id}, {"_id": 0})
            )
            for child in children:
                find_descendants(child["chapter_id"])
                deleted_ids.append(child["chapter_id"])

        # Find all descendants
        find_descendants(chapter_id)

        # Delete all descendants
        if deleted_ids:
            self.chapters_collection.delete_many({"chapter_id": {"$in": deleted_ids}})

        # Delete the chapter itself
        self.chapters_collection.delete_one({"chapter_id": chapter_id})
        deleted_ids.append(chapter_id)

        logger.info(
            f"🗑️ Cascade deleted chapter {chapter_id} and {len(deleted_ids) - 1} descendants"
        )
        return deleted_ids

    def delete_guide_chapters(self, book_id: str) -> int:
        """
        Delete all chapters in a guide

        Args:
            book_id: Guide UUID

        Returns:
            Number of deleted chapters
        """
        result = self.chapters_collection.delete_many({"book_id": book_id})
        logger.info(f"🗑️ Deleted {result.deleted_count} chapters from guide {book_id}")
        return result.deleted_count

    def get_chapter_by_slug(
        self, book_id: str, chapter_slug: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get chapter by slug within a guide (Phase 5 - for public access)

        Args:
            book_id: Guide UUID
            chapter_slug: Chapter slug (URL-friendly identifier)

        Returns:
            Chapter document or None if not found
        """
        chapter = self.chapters_collection.find_one(
            {"book_id": book_id, "slug": chapter_slug},
            {"_id": 0},  # Exclude MongoDB ObjectId
        )

        if chapter:
            logger.info(f"📄 Found chapter: {book_id}/{chapter_slug}")
        else:
            logger.warning(f"⚠️ Chapter not found: {book_id}/{chapter_slug}")

        return chapter

    def reorder_chapters(self, book_id: str, updates: List) -> List[Dict[str, Any]]:
        """
        Bulk reorder chapters

        Args:
            book_id: Guide UUID
            updates: List of ChapterReorder objects

        Returns:
            List of updated chapters
        """
        updated_chapters = []

        for update_item in updates:
            # Convert Pydantic model to dict
            if hasattr(update_item, "model_dump"):
                update = update_item.model_dump()
            elif isinstance(update_item, dict):
                update = update_item
            else:
                continue

            chapter_id = update["chapter_id"]
            parent_id = update.get("parent_id")
            order_index = update.get("order_index", 0)

            # Calculate new depth
            depth = self._calculate_depth(parent_id)

            # Update chapter
            result = self.chapters_collection.find_one_and_update(
                {"chapter_id": chapter_id, "book_id": book_id},
                {
                    "$set": {
                        "parent_id": parent_id,
                        "order_index": order_index,
                        "depth": depth,
                        "updated_at": datetime.utcnow(),
                    }
                },
                return_document=ReturnDocument.AFTER,
            )

            if result:
                updated_chapters.append(result)

        logger.info(f"🔄 Reordered {len(updated_chapters)} chapters in guide {book_id}")
        return updated_chapters

    # ============ DOCUMENT INTEGRATION METHODS (NEW - Phase 6) ============

    def create_chapter_from_document(
        self,
        book_id: str,
        document_id: str,
        title: str,
        order_index: int = 0,
        parent_id: Optional[str] = None,
        icon: str = "📄",
        is_published: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Create a chapter that references a document (no content duplication)

        Args:
            book_id: Book UUID
            document_id: Document UUID to reference
            title: Chapter title
            order_index: Position in chapter list
            parent_id: Parent chapter for nesting
            icon: Chapter icon (emoji)
            is_published: Publish immediately

        Returns:
            Created chapter document or None
        """
        # Verify document exists
        document = self.db["documents"].find_one(
            {"document_id": document_id},
            {"_id": 0, "user_id": 1, "name": 1, "content": 1},
        )

        if not document:
            logger.error(f"❌ Document not found: {document_id}")
            return None

        # Calculate depth
        depth = self._calculate_depth(parent_id)
        if depth > self.MAX_DEPTH:
            logger.error(f"❌ Max depth exceeded: {depth} > {self.MAX_DEPTH}")
            return None

        # Create chapter
        chapter_id = str(uuid.uuid4())
        now = datetime.utcnow()

        chapter_doc = {
            "chapter_id": chapter_id,
            "book_id": book_id,
            "title": title,
            "slug": f"chapter-{chapter_id[:8]}",  # Auto-generate slug
            "icon": icon,
            "order_index": order_index,
            "parent_id": parent_id,
            "depth": depth,
            # Document reference (Phase 6 - no content duplication)
            "content_source": "document",  # "document" or "inline"
            "document_id": document_id,
            "content_html": None,  # Not stored here - loaded from document
            "content_json": None,
            "is_published": is_published,
            "created_at": now,
            "updated_at": now,
        }

        try:
            self.chapters_collection.insert_one(chapter_doc)

            # Update document's used_in_books array
            self.db["documents"].update_one(
                {"document_id": document_id},
                {
                    "$addToSet": {
                        "used_in_books": {
                            "book_id": book_id,
                            "chapter_id": chapter_id,
                            "added_at": now,
                        }
                    }
                },
            )

            logger.info(
                f"✅ Created chapter from document: {chapter_id} → doc:{document_id}"
            )
            return chapter_doc

        except Exception as e:
            logger.error(f"❌ Failed to create chapter from document: {e}")
            return None

    def get_chapter_with_content(self, chapter_id: str) -> Optional[Dict[str, Any]]:
        """
        Get chapter with content (loads from document if content_source='document')

        Args:
            chapter_id: Chapter UUID

        Returns:
            Chapter with content loaded
        """
        chapter = self.chapters_collection.find_one(
            {"chapter_id": chapter_id}, {"_id": 0}
        )

        if not chapter:
            return None

        # Only support inline content - chapters are independent from documents
        content_html = chapter.get("content_html") or ""
        chapter["content"] = content_html  # Set 'content' for frontend compatibility

        logger.info(
            f"📄 Loaded chapter content: {chapter_id} ({len(content_html)} chars)"
        )

        return chapter

    def convert_document_to_chapter(
        self,
        document_id: str,
        book_id: str,
        user_id: str,
        title: Optional[str] = None,
        order_index: int = 0,
        parent_id: Optional[str] = None,
        copy_content: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        Convert an existing document to a chapter in a book

        Args:
            document_id: Document UUID to convert
            book_id: Target book UUID
            user_id: User ID (for ownership verification)
            title: Optional chapter title (uses document name if not provided)
            order_index: Position in chapter list
            parent_id: Parent chapter for nesting
            copy_content: If True, copy content to chapter (inline). If False, link to document.

        Returns:
            Created chapter document or None

        Raises:
            ValueError: If document/book not found or user doesn't own them
        """
        # Verify document exists and user owns it
        document = self.db["documents"].find_one(
            {"document_id": document_id, "user_id": user_id, "is_deleted": False},
            {"_id": 0},
        )

        if not document:
            raise ValueError(f"Document not found or access denied: {document_id}")

        # Verify book exists and user owns it
        book = self.db["online_books"].find_one(
            {"book_id": book_id, "user_id": user_id, "is_deleted": False},
            {"_id": 0, "book_id": 1},
        )

        if not book:
            raise ValueError(f"Book not found or access denied: {book_id}")

        # Calculate depth
        depth = self._calculate_depth(parent_id)
        if depth > self.MAX_DEPTH:
            raise ValueError(f"Max depth exceeded: {depth} > {self.MAX_DEPTH}")

        # Create chapter
        chapter_id = f"chapter_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow()

        # Use document name/title for chapter title if not provided
        chapter_title = (
            title or document.get("name") or document.get("title") or "Untitled Chapter"
        )

        # Generate slug from title
        slug = chapter_title.lower().replace(" ", "-")
        slug = "".join(c for c in slug if c.isalnum() or c == "-")

        if copy_content:
            # INLINE MODE: Copy content to chapter
            content_html = document.get("content_html", "")

            chapter_doc = {
                "chapter_id": chapter_id,
                "book_id": book_id,
                "parent_id": parent_id,
                "title": chapter_title,
                "slug": slug,
                "order_index": order_index,
                "depth": depth,
                # Inline content storage
                "content_source": "inline",
                "document_id": None,
                "content_html": content_html,
                "content_json": None,
                # Metadata
                "is_published": True,
                "is_preview_free": False,
                "converted_from_document": document_id,  # Track origin
                # Timestamps
                "created_at": now,
                "updated_at": now,
            }

            logger.info(
                f"✅ Converting document {document_id} to INLINE chapter "
                f"(copied {len(content_html)} chars)"
            )
        else:
            # LINKED MODE: Reference document
            chapter_doc = {
                "chapter_id": chapter_id,
                "book_id": book_id,
                "parent_id": parent_id,
                "title": chapter_title,
                "slug": slug,
                "order_index": order_index,
                "depth": depth,
                # Document reference storage
                "content_source": "document",
                "document_id": document_id,
                "content_html": None,
                "content_json": None,
                # Metadata
                "is_published": True,
                "is_preview_free": False,
                # Timestamps
                "created_at": now,
                "updated_at": now,
            }

            # Update document's used_in_books array
            self.db["documents"].update_one(
                {"document_id": document_id},
                {
                    "$addToSet": {
                        "used_in_books": {
                            "book_id": book_id,
                            "chapter_id": chapter_id,
                            "added_at": now,
                        }
                    }
                },
            )

            logger.info(
                f"✅ Converting document {document_id} to LINKED chapter "
                f"(references document)"
            )

        try:
            self.chapters_collection.insert_one(chapter_doc)
            logger.info(
                f"✅ Created chapter {chapter_id} from document {document_id} "
                f"(mode: {'inline' if copy_content else 'linked'})"
            )
            return chapter_doc
        except DuplicateKeyError:
            logger.error(f"❌ Slug '{slug}' already exists in book {book_id}")
            raise
