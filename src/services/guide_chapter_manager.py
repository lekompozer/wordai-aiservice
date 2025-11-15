"""
Guide Chapter Manager Service
Phase 1: Database operations for Guide Chapters
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
import logging
from pymongo.errors import DuplicateKeyError

logger = logging.getLogger("chatbot")


class GuideChapterManager:
    """Quản lý Guide Chapters trong MongoDB"""

    MAX_DEPTH = 2  # 0, 1, 2 = 3 levels total

    def __init__(self, db):
        """
        Initialize GuideChapterManager

        Args:
            db: PyMongo Database object (synchronous)
        """
        self.db = db
        self.chapters_collection = db["guide_chapters"]

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
                    [("guide_id", 1), ("order", 1)], name="guide_chapters_order"
                )
                logger.info("✅ Created index: guide_chapters_order")

            # Nested structure queries
            if "nested_chapters" not in existing_indexes:
                self.chapters_collection.create_index(
                    [("guide_id", 1), ("parent_chapter_id", 1), ("order", 1)],
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
                    [("guide_id", 1), ("slug", 1)],
                    unique=True,
                    name="chapter_slug_unique",
                )
                logger.info("✅ Created index: chapter_slug_unique")

            logger.info("✅ Guide Chapter indexes verified/created")
        except Exception as e:
            logger.error(f"❌ Error creating chapter indexes: {e}")
            raise

    def add_chapter(
        self,
        guide_id: str,
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
            guide_id: Guide UUID
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
            "guide_id": guide_id,
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
                f"✅ Added chapter: {chapter_id} to guide {guide_id} (depth: {depth})"
            )
            return chapter_id
        except DuplicateKeyError:
            logger.error(f"❌ Slug '{slug}' already exists in guide {guide_id}")
            raise

    def get_chapter(self, chapter_id: str) -> Optional[Dict[str, Any]]:
        """Get chapter by ID"""
        return self.chapters_collection.find_one({"chapter_id": chapter_id})

    def get_chapters(
        self, guide_id: str, include_hidden: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get all chapters for a guide (flat list)

        Args:
            guide_id: Guide UUID
            include_hidden: Include hidden chapters

        Returns:
            List of chapter documents
        """
        query = {"guide_id": guide_id}
        if not include_hidden:
            query["is_visible"] = True

        chapters = list(self.chapters_collection.find(query).sort([("order", 1)]))

        logger.info(f"📊 Found {len(chapters)} chapters for guide {guide_id}")
        return chapters

    def get_chapter_tree(
        self, guide_id: str, include_hidden: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Build nested tree structure from flat chapter list

        Args:
            guide_id: Guide UUID
            include_hidden: Include hidden chapters

        Returns:
            List of root chapters with nested children
        """
        chapters = self.get_chapters(guide_id, include_hidden)

        # Build chapter map
        chapter_map = {}
        for chapter in chapters:
            chapter_id = chapter["chapter_id"]
            chapter_map[chapter_id] = {**chapter, "children": []}

        # Build tree
        tree = []
        for chapter in chapters:
            chapter_id = chapter["chapter_id"]
            parent_id = chapter.get("parent_chapter_id")

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

    def delete_chapters_by_guide(self, guide_id: str) -> int:
        """
        Delete all chapters for a guide (cascade delete when guide is deleted)

        Args:
            guide_id: Guide UUID

        Returns:
            Number of chapters deleted
        """
        result = self.chapters_collection.delete_many({"guide_id": guide_id})
        deleted_count = result.deleted_count

        logger.info(f"🗑️ Deleted {deleted_count} chapters for guide {guide_id}")
        return deleted_count

    def get_document_usage(self, document_id: str) -> List[Dict[str, Any]]:
        """
        Find which guides use this document

        Args:
            document_id: Document UUID

        Returns:
            List of chapters using this document
        """
        chapters = list(self.chapters_collection.find({"document_id": document_id}))
        logger.info(f"📊 Document {document_id} used in {len(chapters)} chapters")
        return chapters

    def count_chapters(self, guide_id: str) -> int:
        """Count total chapters in guide"""
        return self.chapters_collection.count_documents({"guide_id": guide_id})

    def slug_exists(
        self, guide_id: str, slug: str, exclude_chapter_id: Optional[str] = None
    ) -> bool:
        """
        Check if slug already exists in guide

        Args:
            guide_id: Guide UUID
            slug: Slug to check
            exclude_chapter_id: Optional chapter ID to exclude (for updates)

        Returns:
            True if exists
        """
        query = {"guide_id": guide_id, "slug": slug}
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
        nodes.sort(key=lambda x: x["order"])
        for node in nodes:
            if node.get("children"):
                self._sort_tree(node["children"])
