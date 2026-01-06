"""
Service for Slide Template operations
"""

import re
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from bson import ObjectId

from src.database.db_manager import DBManager
from src.models.slide_template_models import (
    CreateTemplateRequest,
    UpdateTemplateRequest,
    ApplyTemplateRequest,
    SlideTemplate,
)
from src.utils.id_generator import generate_unique_id

logger = logging.getLogger(__name__)


class SlideTemplateService:
    """Service for managing slide templates"""

    def __init__(self):
        self.db = DBManager().db
        self.templates = self.db["slide_templates"]
        self.documents = self.db["documents"]
        self._ensure_indexes()

    def _ensure_indexes(self):
        """Create necessary indexes"""
        try:
            # User templates sorted by creation date
            self.templates.create_index([("user_id", 1), ("created_at", -1)])

            # Unique template_id
            self.templates.create_index("template_id", unique=True)

            # Filter by category
            self.templates.create_index([("user_id", 1), ("category", 1)])

            # Search by tags
            self.templates.create_index([("user_id", 1), ("tags", 1)])

            logger.info("✅ Slide template indexes created")
        except Exception as e:
            logger.warning(f"Index creation warning: {e}")

    def _extract_slide_html(self, content_html: str, slide_index: int) -> str:
        """Extract slide HTML from document content_html"""
        # Split by slide divs
        parts = content_html.split('<div class="slide"')

        # Find the slide with matching index
        for i, part in enumerate(parts):
            if f'data-slide-index="{slide_index}"' in part:
                # Reconstruct the slide HTML
                slide_html = '<div class="slide"' + part

                # Find the end of this slide (start of next slide or end of string)
                next_slide_pos = slide_html.find('<div class="slide"', 20)
                if next_slide_pos > 0:
                    slide_html = slide_html[:next_slide_pos]

                return slide_html

        raise ValueError(f"Slide index {slide_index} not found in document")

    def _extract_styles(self, slide_html: str) -> Dict[str, Optional[str]]:
        """Extract style properties from slide HTML"""
        styles = {
            "background": None,
            "font_family": None,
            "primary_color": None,
            "layout_type": None,
        }

        # Extract background
        bg_match = re.search(r"background:\s*([^;]+);", slide_html)
        if bg_match:
            styles["background"] = bg_match.group(1).strip()

        # Extract font-family
        font_match = re.search(r"font-family:\s*([^;]+);", slide_html)
        if font_match:
            styles["font_family"] = font_match.group(1).strip()

        # Detect layout type
        if (
            "grid-template-columns: 1fr 1fr" in slide_html
            or "display: grid" in slide_html
        ):
            if slide_html.count("1fr") >= 2:
                styles["layout_type"] = "two-column"
            else:
                styles["layout_type"] = "single-column"
        elif "<h1" in slide_html and slide_html.count("<p") == 0:
            styles["layout_type"] = "title"
        else:
            styles["layout_type"] = "custom"

        # Extract primary color (from h1 or first color found)
        color_match = re.search(r"color:\s*(#[0-9a-fA-F]{6}|rgb\([^)]+\))", slide_html)
        if color_match:
            styles["primary_color"] = color_match.group(1).strip()

        return styles

    def _replace_slide_html(
        self, content_html: str, slide_index: int, new_slide_html: str
    ) -> str:
        """Replace a slide in content_html with new HTML"""
        parts = content_html.split('<div class="slide"')

        # Find and replace the target slide
        for i, part in enumerate(parts):
            if f'data-slide-index="{slide_index}"' in part:
                # Extract the part after opening tag
                new_part = new_slide_html.replace('<div class="slide"', "", 1)

                # Find end of this slide
                next_slide_pos = part.find('<div class="slide"')
                if next_slide_pos > 0:
                    # Keep everything after this slide
                    new_part = new_part.split('<div class="slide"')[0]

                parts[i] = new_part
                break

        # Reconstruct HTML
        return '<div class="slide"'.join(parts)

    def _merge_template_with_content(
        self, template_html: str, target_slide_html: str
    ) -> str:
        """
        Merge template styles with existing content
        Preserves text/images from target, applies styles from template
        """
        # For Phase 1 MVP: simple background replacement
        # Extract background from template
        template_bg_match = re.search(r"background:\s*([^;]+);", template_html)
        if not template_bg_match:
            return template_html

        template_bg = template_bg_match.group(1)

        # Replace background in target slide
        updated_html = re.sub(
            r"background:\s*[^;]+;", f"background: {template_bg};", target_slide_html
        )

        return updated_html

    async def create_template(
        self, user_id: str, request: CreateTemplateRequest
    ) -> Dict[str, Any]:
        """
        Save a slide as template

        Args:
            user_id: Firebase UID of user
            request: Template creation request

        Returns:
            Template data dict

        Raises:
            ValueError: If document/slide not found or validation fails
        """
        # 1. Get source document
        doc = self.documents.find_one({"document_id": request.document_id})
        if not doc:
            raise ValueError(f"Document {request.document_id} not found")

        # Check ownership
        if doc.get("user_id") != user_id:
            raise ValueError("You don't have permission to access this document")

        # 2. Extract slide HTML
        try:
            slide_html = self._extract_slide_html(
                doc["content_html"], request.slide_index
            )
        except ValueError as e:
            raise ValueError(str(e))

        # 3. Extract styles
        styles = self._extract_styles(slide_html)

        # 4. Generate unique template_id
        template_id = f"tmpl_{generate_unique_id()}"

        # 5. Create template document
        template_doc = {
            "template_id": template_id,
            "user_id": user_id,
            "name": request.name,
            "description": request.description,
            "category": request.category,
            "tags": request.tags,
            "template_html": slide_html,
            "thumbnail_url": None,  # Phase 2: thumbnail generation
            **styles,
            "usage_count": 0,
            "last_used_at": None,
            "source_document_id": request.document_id,
            "source_slide_index": request.slide_index,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        # 6. Insert into database
        result = self.templates.insert_one(template_doc)

        logger.info(
            f"✅ Template created: {template_id} by user {user_id} from slide {request.slide_index}"
        )

        return {
            "template_id": template_id,
            "name": request.name,
            "thumbnail_url": None,
            "created_at": template_doc["created_at"],
        }

    async def list_templates(
        self,
        user_id: str,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        search: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        List user's templates with filtering and pagination

        Args:
            user_id: Firebase UID
            category: Filter by category
            tags: Filter by tags (any match)
            search: Search in name/description
            limit: Results per page
            offset: Pagination offset

        Returns:
            Dict with templates list and pagination info
        """
        # Build query
        query: Dict[str, Any] = {"user_id": user_id}

        if category:
            query["category"] = category

        if tags:
            query["tags"] = {"$in": tags}

        if search:
            # Case-insensitive search in name and description
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"description": {"$regex": search, "$options": "i"}},
            ]

        # Count total
        total = self.templates.count_documents(query)

        # Get templates with pagination
        cursor = (
            self.templates.find(query).sort("created_at", -1).skip(offset).limit(limit)
        )

        templates = []
        for doc in cursor:
            # Remove MongoDB _id from response
            doc.pop("_id", None)
            templates.append(doc)

        has_more = (offset + limit) < total

        logger.info(
            f"📋 Listed {len(templates)} templates for user {user_id} (total: {total})"
        )

        return {
            "templates": templates,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": has_more,
        }

    async def get_template(
        self, user_id: str, template_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get template details by ID

        Args:
            user_id: Firebase UID
            template_id: Template ID

        Returns:
            Template dict or None if not found

        Raises:
            ValueError: If template not found or access denied
        """
        template = self.templates.find_one({"template_id": template_id})

        if not template:
            raise ValueError(f"Template {template_id} not found")

        # Check ownership
        if template["user_id"] != user_id:
            raise ValueError("You don't have permission to access this template")

        # Remove MongoDB _id
        template.pop("_id", None)

        return template

    async def update_template(
        self, user_id: str, template_id: str, request: UpdateTemplateRequest
    ) -> Dict[str, Any]:
        """
        Update template metadata

        Args:
            user_id: Firebase UID
            template_id: Template ID
            request: Update request

        Returns:
            Updated template info

        Raises:
            ValueError: If template not found or access denied
        """
        # Check ownership
        template = self.templates.find_one({"template_id": template_id})
        if not template:
            raise ValueError(f"Template {template_id} not found")

        if template["user_id"] != user_id:
            raise ValueError("You don't have permission to update this template")

        # Build update dict (only update provided fields)
        update_data = {"updated_at": datetime.utcnow()}

        if request.name is not None:
            update_data["name"] = request.name
        if request.description is not None:
            update_data["description"] = request.description
        if request.category is not None:
            update_data["category"] = request.category
        if request.tags is not None:
            update_data["tags"] = request.tags

        # Update in database
        result = self.templates.update_one(
            {"template_id": template_id}, {"$set": update_data}
        )

        logger.info(
            f"✏️ Template updated: {template_id} by user {user_id} ({result.modified_count} doc)"
        )

        return {"template_id": template_id, "updated_at": update_data["updated_at"]}

    async def delete_template(self, user_id: str, template_id: str) -> bool:
        """
        Delete a template

        Args:
            user_id: Firebase UID
            template_id: Template ID

        Returns:
            True if deleted

        Raises:
            ValueError: If template not found or access denied
        """
        # Check ownership
        template = self.templates.find_one({"template_id": template_id})
        if not template:
            raise ValueError(f"Template {template_id} not found")

        if template["user_id"] != user_id:
            raise ValueError("You don't have permission to delete this template")

        # Delete from database
        result = self.templates.delete_one({"template_id": template_id})

        logger.info(
            f"🗑️ Template deleted: {template_id} by user {user_id} ({result.deleted_count} doc)"
        )

        return result.deleted_count > 0

    async def apply_template(
        self, user_id: str, template_id: str, request: ApplyTemplateRequest
    ) -> Dict[str, Any]:
        """
        Apply template to a slide

        Args:
            user_id: Firebase UID
            template_id: Template ID to apply
            request: Application request

        Returns:
            Result info

        Raises:
            ValueError: If template/document not found or access denied
        """
        # 1. Get template
        template = self.templates.find_one({"template_id": template_id})
        if not template:
            raise ValueError(f"Template {template_id} not found")

        if template["user_id"] != user_id:
            raise ValueError("You don't have permission to use this template")

        # 2. Get target document
        doc = self.documents.find_one({"document_id": request.document_id})
        if not doc:
            raise ValueError(f"Document {request.document_id} not found")

        if doc.get("user_id") != user_id:
            raise ValueError("You don't have permission to edit this document")

        # 3. Extract target slide
        try:
            target_slide_html = self._extract_slide_html(
                doc["content_html"], request.slide_index
            )
        except ValueError as e:
            raise ValueError(str(e))

        # 4. Merge template with content
        if request.preserve_content:
            new_slide_html = self._merge_template_with_content(
                template["template_html"], target_slide_html
            )
        else:
            # Replace entire slide with template
            new_slide_html = template["template_html"]
            # Update slide index in template HTML
            new_slide_html = re.sub(
                r'data-slide-index="\d+"',
                f'data-slide-index="{request.slide_index}"',
                new_slide_html,
            )

        # 5. Update document
        updated_html = self._replace_slide_html(
            doc["content_html"], request.slide_index, new_slide_html
        )

        self.documents.update_one(
            {"document_id": request.document_id},
            {"$set": {"content_html": updated_html}},
        )

        # 6. Update template usage statistics
        self.templates.update_one(
            {"template_id": template_id},
            {
                "$inc": {"usage_count": 1},
                "$set": {"last_used_at": datetime.utcnow()},
            },
        )

        logger.info(
            f"✅ Template {template_id} applied to slide {request.slide_index} in {request.document_id}"
        )

        return {
            "slide_updated": True,
            "slide_index": request.slide_index,
            "message": "Template applied successfully",
        }


# Singleton instance
_service_instance: Optional[SlideTemplateService] = None


def get_slide_template_service() -> SlideTemplateService:
    """Get singleton instance of SlideTemplateService"""
    global _service_instance
    if _service_instance is None:
        _service_instance = SlideTemplateService()
    return _service_instance
