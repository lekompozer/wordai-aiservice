"""
Guide Chapter Manager Service
Phase 1: Database operations for Guide Chapters
Phase 2: Multi-format content support (PDF pages, Image pages)
"""

import uuid
import os
import tempfile
from datetime import datetime
from typing import Optional, List, Dict, Any
import logging
from pymongo.errors import DuplicateKeyError
from pymongo import ReturnDocument

logger = logging.getLogger("chatbot")


class GuideBookBookChapterManager:
    """Quản lý Guide Chapters trong MongoDB"""

    MAX_DEPTH = 2  # 0, 1, 2 = 3 levels total

    def __init__(self, db, book_manager=None, s3_client=None, r2_config=None):
        """
        Initialize GuideBookBookChapterManager

        Args:
            db: PyMongo Database object (synchronous)
            book_manager: Optional UserBookManager instance for updating book timestamps
            s3_client: Optional boto3 S3 client for R2 uploads (required for PDF/image chapters)
            r2_config: Optional dict with R2 config {bucket, cdn_base_url}
        """
        self.db = db
        self.chapters_collection = db["book_chapters"]
        self.book_manager = book_manager

        # R2 storage for PDF/image pages
        self.s3_client = s3_client
        self.r2_config = r2_config or {}

        # Lazy import to avoid circular dependency
        if book_manager is None:
            from src.services.book_manager import UserBookManager

            self.book_manager = UserBookManager(db)

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
        document_id = data.get("document_id")
        content_source = data.get("content_source", "inline")  # Default: inline

        # NEW LOGIC: Only use 'document' mode if EXPLICITLY set
        # If document_id exists but content_source not specified → use 'inline' (copy content)
        # This ensures chapters store their own content in book_chapters collection

        # If inline mode but document_id provided, fetch content from document
        content_html_to_save = data.get("content_html")
        content_json_to_save = data.get("content_json")

        if content_source == "inline" and document_id and not content_html_to_save:
            # Fetch content from document and copy to chapter
            doc = self.db["documents"].find_one(
                {"document_id": document_id},
                {"content_html": 1, "content": 1, "_id": 0},
            )
            if doc:
                content_html_to_save = doc.get("content_html") or doc.get("content", "")
                logger.info(
                    f"📋 Copying content from document {document_id} to chapter (inline mode)"
                )

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
            "document_id": document_id,  # Keep reference even in inline mode
            # Inline content (always save for inline mode)
            "content_html": (
                content_html_to_save if content_source == "inline" else None
            ),
            "content_json": (
                content_json_to_save if content_source == "inline" else None
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

            # Update parent book's updated_at timestamp
            self.book_manager.touch_book(book_id)

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

        # Get book_id before update
        chapter = self.chapters_collection.find_one(
            {"chapter_id": chapter_id}, {"book_id": 1}
        )

        result = self.chapters_collection.update_one(
            {"chapter_id": chapter_id}, {"$set": updates}
        )

        if result.modified_count > 0:
            # Update parent book timestamp
            if chapter:
                self.book_manager.touch_book(chapter["book_id"])
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
        affected_books = set()  # Track which books need timestamp update

        for chapter_data in chapters:
            chapter_id = chapter_data["chapter_id"]
            order = chapter_data["order"]
            parent_id = chapter_data.get("parent_chapter_id")

            # Calculate new depth
            depth = self._calculate_depth(parent_id)
            if depth > self.MAX_DEPTH:
                logger.warning(f"⚠️ Skipping chapter {chapter_id}: max depth exceeded")
                continue

            # Get book_id before update
            chapter = self.chapters_collection.find_one(
                {"chapter_id": chapter_id}, {"book_id": 1}
            )

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
                if chapter:
                    affected_books.add(chapter["book_id"])

        # Update all affected books' timestamps
        for book_id in affected_books:
            self.book_manager.touch_book(book_id)

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
        # Get book_id before delete
        chapter = self.chapters_collection.find_one(
            {"chapter_id": chapter_id}, {"book_id": 1}
        )

        result = self.chapters_collection.delete_one({"chapter_id": chapter_id})

        if result.deleted_count > 0:
            # Update parent book timestamp
            if chapter:
                self.book_manager.touch_book(chapter["book_id"])
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
            # Update parent book timestamp
            self.book_manager.touch_book(result["book_id"])
            logger.info(f"✅ Updated chapter: {chapter_id}")
            return result
        else:
            logger.warning(f"⚠️ Chapter not found: {chapter_id}")
            return None

    def update_chapter_translation_metadata(
        self,
        chapter_id: str,
        language: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Update chapter translation metadata (title, description only)

        Args:
            chapter_id: Chapter UUID
            language: Language code (e.g., 'en', 'zh')
            title: Translated title (optional)
            description: Translated description (optional)

        Returns:
            Updated chapter document or None
        """
        chapter = self.chapters_collection.find_one(
            {"chapter_id": chapter_id}, {"_id": 0, "book_id": 1}
        )

        if not chapter:
            logger.warning(f"⚠️ Chapter not found: {chapter_id}")
            return None

        now = datetime.utcnow()
        translation_update = {}

        if title is not None:
            translation_update[f"translations.{language}.title"] = title

        if description is not None:
            translation_update[f"translations.{language}.description"] = description

        if not translation_update:
            # No fields to update
            return self.chapters_collection.find_one(
                {"chapter_id": chapter_id}, {"_id": 0}
            )

        translation_update[f"translations.{language}.updated_at"] = now
        translation_update["updated_at"] = now

        result = self.chapters_collection.find_one_and_update(
            {"chapter_id": chapter_id},
            {"$set": translation_update},
            return_document=ReturnDocument.AFTER,
        )

        if result:
            # Update parent book timestamp
            self.book_manager.touch_book(chapter["book_id"])
            logger.info(
                f"✅ Updated chapter translation ({language}) metadata: {chapter_id}"
            )
            return result
        else:
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
                # Update parent book timestamp
                self.book_manager.touch_book(chapter["book_id"])
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

                # Update parent book timestamp
                self.book_manager.touch_book(chapter["book_id"])
                return True
            return False

        else:
            raise ValueError(f"Unknown content_source: {content_source}")

    def update_chapter_translation(
        self,
        chapter_id: str,
        language: str,
        content_html: str,
        content_json: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Update chapter translation content (saves to translations.{language})

        Args:
            chapter_id: Chapter UUID
            language: Language code (e.g., 'en', 'zh')
            content_html: Translated HTML content
            content_json: Optional translated JSON content (TipTap format)

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

        # Build translation update object
        translation_update = {
            f"translations.{language}.content_html": content_html,
            f"translations.{language}.updated_at": now,
        }

        if content_json:
            translation_update[f"translations.{language}.content_json"] = content_json

        if content_source == "inline":
            # Update translation in chapter document
            result = self.chapters_collection.update_one(
                {"chapter_id": chapter_id},
                {
                    "$set": {
                        **translation_update,
                        "updated_at": now,
                    }
                },
            )

            if result.modified_count > 0:
                # Update parent book timestamp
                self.book_manager.touch_book(chapter["book_id"])
                logger.info(
                    f"✅ Updated chapter translation ({language}): {chapter_id} "
                    f"({len(content_html)} chars)"
                )
                return True
            return False

        elif content_source == "document":
            # Update translation in linked document
            document_id = chapter.get("document_id")
            if not document_id:
                raise ValueError(
                    f"Chapter {chapter_id} has content_source='document' but no document_id"
                )

            result = self.db["documents"].update_one(
                {"document_id": document_id},
                {
                    "$set": {
                        **translation_update,
                        "updated_at": now,
                    }
                },
            )

            if result.modified_count > 0:
                logger.info(
                    f"✅ Updated document translation ({language}) for chapter {chapter_id}: "
                    f"document {document_id} ({len(content_html)} chars)"
                )

                # Also update chapter's updated_at timestamp
                self.chapters_collection.update_one(
                    {"chapter_id": chapter_id}, {"$set": {"updated_at": now}}
                )

                # Update parent book timestamp
                self.book_manager.touch_book(chapter["book_id"])
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
        Get chapter with content (UPDATED - handles all content modes)

        Content modes:
        - inline: HTML/JSON content in chapter
        - document: Load content from documents collection (DEPRECATED)
        - pdf_pages: Pages array with backgrounds
        - image_pages: Pages array with backgrounds + manga metadata

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

        content_source = chapter.get("content_source", "inline")

        if content_source == "document":
            # ❌ DEPRECATED - Load from documents collection
            # Phase 3 will migrate to inline mode
            document_id = chapter.get("document_id")
            if document_id:
                document = self.db["documents"].find_one(
                    {"document_id": document_id},
                    {"_id": 0, "content_html": 1, "content": 1},
                )

                if document:
                    # Try content_html first, fallback to content
                    content_html = document.get("content_html") or document.get(
                        "content", ""
                    )
                    chapter["content_html"] = content_html
                    chapter["content"] = content_html  # Alias for compatibility
                    logger.info(
                        f"📄 Loaded chapter content from document {document_id}: "
                        f"{chapter_id} ({len(content_html)} chars)"
                    )
                else:
                    logger.warning(
                        f"⚠️ Document {document_id} not found for chapter {chapter_id}"
                    )
                    chapter["content_html"] = ""
                    chapter["content"] = ""
            else:
                logger.warning(
                    f"⚠️ Chapter {chapter_id} has content_source='document' but no document_id"
                )
                chapter["content_html"] = ""
                chapter["content"] = ""

        elif content_source in ["pdf_pages", "image_pages"]:
            # ✅ NEW - Pages array with backgrounds
            pages = chapter.get("pages", [])
            total_pages = chapter.get("total_pages", len(pages))

            logger.info(
                f"📄 Loaded {content_source} chapter: {chapter_id} "
                f"({total_pages} pages)"
            )

            # Enrich with file details if available
            file_id = chapter.get("file_id")
            if file_id:
                file_doc = self.db["studyhub_files"].find_one({"file_id": file_id})
                if file_doc:
                    chapter["file_details"] = {
                        "file_name": file_doc.get("file_name"),
                        "file_type": file_doc.get("file_type"),
                        "file_size": file_doc.get("file_size"),
                        "uploaded_at": file_doc.get("uploaded_at"),
                    }

            # For image_pages, include manga metadata
            if content_source == "image_pages":
                manga_metadata = chapter.get("manga_metadata")
                if manga_metadata:
                    logger.info(
                        f"   Manga: {manga_metadata.get('reading_direction')}, "
                        f"colored={manga_metadata.get('is_colored')}"
                    )

        else:  # inline (default)
            # ✅ Inline content - already in chapter
            content_html = chapter.get("content_html") or ""
            chapter["content"] = (
                content_html  # Set 'content' for frontend compatibility
            )
            logger.info(
                f"📄 Loaded inline chapter content: {chapter_id} ({len(content_html)} chars)"
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

    # ═══════════════════════════════════════════════════════════════════════
    # PHASE 2: Multi-format Content Support (PDF Pages, Image Pages)
    # ═══════════════════════════════════════════════════════════════════════

    async def create_chapter_from_pdf(
        self,
        book_id: str,
        user_id: str,
        file_id: str,
        title: str,
        slug: Optional[str] = None,
        order_index: int = 0,
        parent_id: Optional[str] = None,
        is_published: bool = True,
        is_preview_free: bool = False,
    ) -> Dict[str, Any]:
        """
        Create chapter from PDF file (convert to page backgrounds)

        Args:
            book_id: Book ID
            user_id: User ID (for authorization)
            file_id: StudyHub file ID (must exist in studyhub_files)
            title: Chapter title
            slug: URL slug (auto-generated if not provided)
            order_index: Position in book
            parent_id: Parent chapter ID (for nested chapters)
            is_published: Published status
            is_preview_free: Free preview access

        Returns:
            Created chapter document with pages array
        """
        try:
            # 1. Validate book ownership
            book = self.db.guide_books.find_one({"_id": book_id, "user_id": user_id})
            if not book:
                raise ValueError("Book not found or access denied")

            # 2. Get PDF file from user_files (uploaded via POST /api/files/upload)
            file_doc = self.db.user_files.find_one({"id": file_id, "user_id": user_id})
            if not file_doc:
                raise ValueError("PDF file not found or access denied")

            # Check file type (user_files uses 'type' field, not 'file_type')
            file_type = file_doc.get("type") or file_doc.get("file_type") or ""
            if (
                not file_type.lower().endswith(".pdf")
                and file_type != "application/pdf"
            ):
                raise ValueError(f"File must be a PDF (got: {file_type})")

            logger.info(
                f"📄 [PDF_CHAPTER] Creating chapter from PDF: {file_doc.get('filename')}"
            )
            logger.info(f"   Book: {book_id}, User: {user_id}")

            # 3. Download PDF from R2 to temp file
            pdf_url = file_doc.get("private_url") or file_doc.get("file_url")
            if not pdf_url:
                raise ValueError("PDF file has no URL")

            temp_pdf_path = await self._download_file_from_r2(pdf_url, ".pdf")

            try:
                # 4. Process PDF to pages
                from src.services.pdf_chapter_processor import PDFChapterProcessor

                chapter_id = str(uuid.uuid4())

                processor = PDFChapterProcessor(
                    s3_client=self.s3_client,
                    r2_bucket=self.r2_config.get("bucket", "wordai-storage"),
                    cdn_base_url=self.r2_config.get(
                        "cdn_base_url", "https://cdn.wordai.com"
                    ),
                )

                result = await processor.process_pdf_to_pages(
                    pdf_path=temp_pdf_path,
                    user_id=user_id,
                    chapter_id=chapter_id,
                    dpi=150,  # A4 @ 150 DPI = 1240×1754px
                )

                logger.info(f"✅ PDF processed: {result['total_pages']} pages")

                # 5. Create chapter document
                chapter_doc = {
                    "_id": chapter_id,
                    "book_id": book_id,
                    "user_id": user_id,
                    "title": title,
                    "slug": slug or self._generate_slug(title),
                    "order_index": order_index,
                    "parent_id": parent_id,
                    "depth": (
                        0 if not parent_id else self._calculate_depth(parent_id) + 1
                    ),
                    "content_mode": "pdf_pages",  # NEW
                    "pages": result["pages"],  # Pages array
                    "total_pages": result["total_pages"],
                    "source_file_id": file_id,  # Reference to original PDF
                    "is_published": is_published,
                    "is_preview_free": is_preview_free,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }

                # Insert chapter
                self.chapters_collection.insert_one(chapter_doc)
                logger.info(f"✅ [PDF_CHAPTER] Created chapter: {chapter_id}")

                # 6. Update book timestamp
                if self.book_manager:
                    self.book_manager.update_book_timestamp(book_id)

                # 7. Mark file as used in chapter (optional - for tracking)
                try:
                    self.db.user_files.update_one(
                        {"id": file_id},
                        {
                            "$set": {
                                "used_in_chapter": chapter_id,
                                "updated_at": datetime.utcnow(),
                            }
                        },
                    )
                except Exception as e:
                    logger.warning(f"⚠️ Could not update file metadata: {e}")

                return chapter_doc

            finally:
                # Cleanup temp file
                if os.path.exists(temp_pdf_path):
                    os.remove(temp_pdf_path)
                    logger.info(f"🗑️ Cleaned up temp PDF file")

        except Exception as e:
            logger.error(f"❌ [PDF_CHAPTER] Failed to create chapter from PDF: {e}")
            raise

    async def create_chapter_from_images(
        self,
        book_id: str,
        user_id: str,
        image_urls: List[str],
        title: str,
        slug: Optional[str] = None,
        order_index: int = 0,
        parent_id: Optional[str] = None,
        is_published: bool = True,
        is_preview_free: bool = False,
        manga_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create chapter from image URLs (manga, comics, photo books)

        Args:
            book_id: Book ID
            user_id: User ID
            image_urls: List of image URLs
            title: Chapter title
            slug: URL slug
            order_index: Position in book
            parent_id: Parent chapter ID
            is_published: Published status
            is_preview_free: Free preview access
            manga_metadata: Optional manga settings {
                reading_direction: "ltr" | "rtl",
                is_colored: bool,
                artist: str,
                genre: str
            }

        Returns:
            Created chapter document with pages array
        """
        try:
            # 1. Validate book ownership
            book = self.db.guide_books.find_one({"_id": book_id, "user_id": user_id})
            if not book:
                raise ValueError("Book not found or access denied")

            if not image_urls:
                raise ValueError("No image URLs provided")

            logger.info(
                f"🎨 [IMAGE_CHAPTER] Creating chapter from {len(image_urls)} images"
            )
            logger.info(f"   Book: {book_id}, User: {user_id}")

            # 2. Download images to temp directory
            from src.services.image_chapter_processor import ImageChapterProcessor

            processor = ImageChapterProcessor(
                s3_client=self.s3_client,
                r2_bucket=self.r2_config.get("bucket", "wordai-storage"),
                cdn_base_url=self.r2_config.get(
                    "cdn_base_url", "https://cdn.wordai.com"
                ),
            )

            temp_dir = tempfile.mkdtemp()

            try:
                # Download images
                local_paths = await processor.download_images_from_urls(
                    image_urls, temp_dir
                )

                # 3. Process images to pages
                chapter_id = str(uuid.uuid4())

                # Check if URLs are from temp folder (need cleanup)
                temp_urls = [url for url in image_urls if "/temp/" in url]

                result = await processor.process_images_to_pages(
                    image_paths=local_paths,
                    user_id=user_id,
                    chapter_id=chapter_id,
                    preserve_order=True,  # Keep order for manga
                    cleanup_temp_urls=(
                        temp_urls if temp_urls else None
                    ),  # Cleanup temp files
                )

                logger.info(f"✅ Images processed: {result['total_pages']} pages")
                if temp_urls:
                    logger.info(f"🗑️ Cleaned up {len(temp_urls)} temp files")

                # 4. Create chapter document
                chapter_doc = {
                    "_id": chapter_id,
                    "book_id": book_id,
                    "user_id": user_id,
                    "title": title,
                    "slug": slug or self._generate_slug(title),
                    "order_index": order_index,
                    "parent_id": parent_id,
                    "depth": (
                        0 if not parent_id else self._calculate_depth(parent_id) + 1
                    ),
                    "content_mode": "image_pages",  # NEW
                    "pages": result["pages"],  # Pages array
                    "total_pages": result["total_pages"],
                    "is_published": is_published,
                    "is_preview_free": is_preview_free,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }

                # Add manga metadata if provided
                if manga_metadata:
                    chapter_doc["manga_metadata"] = manga_metadata
                    logger.info(f"📖 Added manga metadata: {manga_metadata}")

                # Insert chapter
                self.chapters_collection.insert_one(chapter_doc)
                logger.info(f"✅ [IMAGE_CHAPTER] Created chapter: {chapter_id}")

                # 5. Update book timestamp
                if self.book_manager:
                    self.book_manager.update_book_timestamp(book_id)

                return chapter_doc

            finally:
                # Cleanup temp directory
                import shutil

                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                    logger.info(f"🗑️ Cleaned up temp directory")

        except Exception as e:
            logger.error(
                f"❌ [IMAGE_CHAPTER] Failed to create chapter from images: {e}"
            )
            raise

    async def create_chapter_from_uploaded_images(
        self,
        book_id: str,
        user_id: str,
        chapter_id: str,
        title: str,
        slug: Optional[str] = None,
        order_index: int = 0,
        parent_id: Optional[str] = None,
        is_published: bool = True,
        is_preview_free: bool = False,
        manga_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create chapter from previously uploaded images (simplified - no file operations)

        Images are already in R2 at: studyhub/chapters/{chapter_id}/page-{N}.jpg

        Args:
            book_id: Book ID
            user_id: User ID
            chapter_id: Chapter ID from upload-images endpoint
            title: Chapter title
            slug: URL slug
            order_index: Position in book
            parent_id: Parent chapter ID
            is_published: Published status
            is_preview_free: Free preview access
            manga_metadata: Optional manga settings

        Returns:
            Created chapter document with pages array
        """
        try:
            # 1. Validate book ownership
            book = self.db.guide_books.find_one({"_id": book_id, "user_id": user_id})
            if not book:
                raise ValueError("Book not found or access denied")

            logger.info(f"🎨 [UPLOADED_IMAGES] Creating chapter from uploaded images")
            logger.info(f"   Book: {book_id}, User: {user_id}")
            logger.info(f"   Chapter ID: {chapter_id}")

            # 2. List uploaded images from R2
            from PIL import Image
            import io

            prefix = f"studyhub/chapters/{chapter_id}/"
            try:
                response = self.s3_client.list_objects_v2(
                    Bucket=self.r2_config.get("bucket", "wordai-storage"), Prefix=prefix
                )
                objects = response.get("Contents", [])
                if not objects:
                    raise ValueError(
                        f"No images found for chapter_id {chapter_id}. "
                        "Upload images first via POST /upload-images"
                    )

                # Sort by page number (page-1.jpg, page-2.jpg, etc.)
                objects.sort(key=lambda x: x["Key"])

                logger.info(f"📄 Found {len(objects)} uploaded pages")

            except Exception as e:
                logger.error(f"❌ Failed to list R2 objects: {e}")
                raise ValueError(f"Failed to access uploaded images: {str(e)}")

            # 3. Build pages array from R2 metadata
            pages = []
            for idx, obj in enumerate(objects, 1):
                object_key = obj["Key"]
                cdn_url = f"{self.r2_config.get('cdn_base_url', 'https://cdn.wordai.com')}/{object_key}"

                # Get image dimensions from R2
                try:
                    response = self.s3_client.get_object(
                        Bucket=self.r2_config.get("bucket", "wordai-storage"),
                        Key=object_key,
                    )
                    image_data = response["Body"].read()
                    image = Image.open(io.BytesIO(image_data))
                    width, height = image.size
                except Exception as e:
                    logger.warning(f"⚠️ Could not get dimensions for {object_key}: {e}")
                    width, height = 0, 0

                pages.append(
                    {
                        "page_number": idx,
                        "background_image": cdn_url,
                        "width": width,
                        "height": height,
                        "elements": [],  # Empty initially
                    }
                )

            logger.info(f"✅ Built {len(pages)} pages from uploaded images")

            # 4. Create chapter document
            chapter_doc = {
                "_id": chapter_id,  # Use uploaded chapter_id
                "book_id": book_id,
                "user_id": user_id,
                "title": title,
                "slug": slug or self._generate_slug(title),
                "order_index": order_index,
                "parent_id": parent_id,
                "depth": 0 if not parent_id else self._calculate_depth(parent_id) + 1,
                "content_mode": "image_pages",
                "pages": pages,
                "total_pages": len(pages),
                "is_published": is_published,
                "is_preview_free": is_preview_free,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }

            # Add manga metadata if provided
            if manga_metadata:
                chapter_doc["manga_metadata"] = manga_metadata
                logger.info(f"📖 Added manga metadata: {manga_metadata}")

            # Insert chapter
            self.chapters_collection.insert_one(chapter_doc)
            logger.info(f"✅ [UPLOADED_IMAGES] Created chapter: {chapter_id}")

            # 5. Update book timestamp
            if self.book_manager:
                self.book_manager.update_book_timestamp(book_id)

            return chapter_doc

        except Exception as e:
            logger.error(
                f"❌ [UPLOADED_IMAGES] Failed to create chapter: {e}", exc_info=True
            )
            raise

    async def create_chapter_from_zip(
        self,
        book_id: str,
        user_id: str,
        zip_file_id: str,
        title: str,
        slug: Optional[str] = None,
        order_index: int = 0,
        parent_id: Optional[str] = None,
        is_published: bool = True,
        is_preview_free: bool = False,
        manga_metadata: Optional[Dict[str, Any]] = None,
        auto_sort: bool = True,
    ) -> Dict[str, Any]:
        """
        Create chapter from manga ZIP file

        Args:
            book_id: Book ID
            user_id: User ID
            zip_file_id: StudyHub file ID (must be a ZIP file)
            title: Chapter title
            slug: URL slug
            order_index: Position in book
            parent_id: Parent chapter ID
            is_published: Published status
            is_preview_free: Free preview access
            manga_metadata: Optional manga settings
            auto_sort: Auto-sort files numerically (True for manga)

        Returns:
            Created chapter document with pages array
        """
        try:
            # 1. Validate book ownership
            book = self.db.guide_books.find_one({"_id": book_id, "user_id": user_id})
            if not book:
                raise ValueError("Book not found or access denied")

            # 2. Get ZIP file from studyhub_files
            file_doc = self.db.studyhub_files.find_one(
                {"_id": zip_file_id, "user_id": user_id}
            )
            if not file_doc:
                raise ValueError("ZIP file not found or access denied")

            if not file_doc.get("file_name", "").lower().endswith(".zip"):
                raise ValueError("File must be a ZIP archive")

            logger.info(
                f"📦 [ZIP_CHAPTER] Creating chapter from ZIP: {file_doc.get('file_name')}"
            )
            logger.info(f"   Book: {book_id}, User: {user_id}")

            # 3. Download ZIP from R2 to temp file
            zip_url = file_doc.get("file_url")
            if not zip_url:
                raise ValueError("ZIP file has no URL")

            temp_zip_path = await self._download_file_from_r2(zip_url, ".zip")

            try:
                # 4. Process ZIP to pages
                from src.services.image_chapter_processor import ImageChapterProcessor

                chapter_id = str(uuid.uuid4())

                processor = ImageChapterProcessor(
                    s3_client=self.s3_client,
                    r2_bucket=self.r2_config.get("bucket", "wordai-storage"),
                    cdn_base_url=self.r2_config.get(
                        "cdn_base_url", "https://cdn.wordai.com"
                    ),
                )

                result = await processor.process_zip_to_pages(
                    zip_path=temp_zip_path,
                    user_id=user_id,
                    chapter_id=chapter_id,
                    auto_sort=auto_sort,
                )

                logger.info(f"✅ ZIP processed: {result['total_pages']} pages")

                # 5. Create chapter document
                chapter_doc = {
                    "_id": chapter_id,
                    "book_id": book_id,
                    "user_id": user_id,
                    "title": title,
                    "slug": slug or self._generate_slug(title),
                    "order_index": order_index,
                    "parent_id": parent_id,
                    "depth": (
                        0 if not parent_id else self._calculate_depth(parent_id) + 1
                    ),
                    "content_mode": "image_pages",  # NEW
                    "pages": result["pages"],  # Pages array
                    "total_pages": result["total_pages"],
                    "source_file_id": zip_file_id,  # Reference to original ZIP
                    "is_published": is_published,
                    "is_preview_free": is_preview_free,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }

                # Add manga metadata if provided
                if manga_metadata:
                    chapter_doc["manga_metadata"] = manga_metadata
                    logger.info(f"📖 Added manga metadata: {manga_metadata}")

                # Insert chapter
                self.chapters_collection.insert_one(chapter_doc)
                logger.info(f"✅ [ZIP_CHAPTER] Created chapter: {chapter_id}")

                # 6. Update book timestamp
                if self.book_manager:
                    self.book_manager.update_book_timestamp(book_id)

                # 7. Update file studyhub_context
                self.db.studyhub_files.update_one(
                    {"_id": zip_file_id},
                    {
                        "$set": {
                            "studyhub_context": {
                                "type": "book_chapter",
                                "book_id": book_id,
                                "chapter_id": chapter_id,
                            },
                            "updated_at": datetime.utcnow(),
                        }
                    },
                )

                return chapter_doc

            finally:
                # Cleanup temp file
                if os.path.exists(temp_zip_path):
                    os.remove(temp_zip_path)
                    logger.info(f"🗑️ Cleaned up temp ZIP file")

        except Exception as e:
            logger.error(f"❌ [ZIP_CHAPTER] Failed to create chapter from ZIP: {e}")
            raise

    async def update_manga_metadata(
        self, chapter_id: str, user_id: str, manga_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update manga metadata for image_pages chapter

        Args:
            chapter_id: Chapter ID
            user_id: User ID (for authorization)
            manga_metadata: Manga settings {
                reading_direction: "ltr" | "rtl",
                is_colored: bool,
                artist: str,
                genre: str
            }

        Returns:
            Updated chapter document
        """
        try:
            # 1. Validate chapter ownership and mode
            chapter = self.chapters_collection.find_one(
                {"_id": chapter_id, "user_id": user_id}
            )
            if not chapter:
                raise ValueError("Chapter not found or access denied")

            if chapter.get("content_mode") != "image_pages":
                raise ValueError(
                    "Manga metadata only available for image_pages chapters"
                )

            logger.info(f"📖 [MANGA_METADATA] Updating chapter: {chapter_id}")
            logger.info(f"   Metadata: {manga_metadata}")

            # 2. Update manga metadata
            updated_chapter = self.chapters_collection.find_one_and_update(
                {"_id": chapter_id},
                {
                    "$set": {
                        "manga_metadata": manga_metadata,
                        "updated_at": datetime.utcnow(),
                    }
                },
                return_document=ReturnDocument.AFTER,
            )

            # 3. Update book timestamp
            if self.book_manager:
                self.book_manager.update_book_timestamp(chapter["book_id"])

            logger.info(f"✅ [MANGA_METADATA] Updated successfully")

            return updated_chapter

        except Exception as e:
            logger.error(f"❌ [MANGA_METADATA] Failed to update: {e}")
            raise

    async def _download_file_from_r2(self, file_url: str, suffix: str = "") -> str:
        """
        Download file from R2 to temp file

        Args:
            file_url: R2 CDN URL
            suffix: File extension (e.g., ".pdf", ".zip")

        Returns:
            Local temp file path
        """
        import aiohttp

        try:
            logger.info(f"⬇️ Downloading file from R2: {file_url}")

            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            temp_path = temp_file.name
            temp_file.close()

            async with aiohttp.ClientSession() as session:
                async with session.get(file_url) as response:
                    if response.status != 200:
                        raise ValueError(
                            f"Failed to download file: HTTP {response.status}"
                        )

                    content = await response.read()

                    with open(temp_path, "wb") as f:
                        f.write(content)

            logger.info(
                f"✅ Downloaded to temp file: {temp_path} ({len(content)} bytes)"
            )

            return temp_path

        except Exception as e:
            logger.error(f"❌ Failed to download file: {e}")
            raise
