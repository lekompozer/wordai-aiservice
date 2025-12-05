"""
Online Book Chapter Management API Routes
Handles chapter operations: create, read, update, delete, reorder, and bulk updates.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime, timezone
import re
import unicodedata

# Authentication
from src.middleware.firebase_auth import get_current_user

# Models
from src.models.book_chapter_models import (
    ChapterCreate,
    ChapterUpdate,
    ChapterContentUpdate,
    ChapterResponse,
    ChapterTreeNode,
    ChapterReorderBulk,
    ChapterBulkUpdate,
    TogglePreviewRequest,
)

# Services
from src.services.book_manager import UserBookManager
from src.services.book_chapter_manager import GuideBookBookChapterManager
from src.services.book_permission_manager import GuideBookBookPermissionManager
from src.services.document_manager import DocumentManager

# Database
from src.database.db_manager import DBManager

logger = logging.getLogger("chatbot")

router = APIRouter(prefix="/api/v1/books", tags=["Online Books Chapters"])

# Initialize DB connection
db_manager = DBManager()
db = db_manager.db

# Initialize managers with DB
book_manager = UserBookManager(db)
chapter_manager = GuideBookBookChapterManager(db)
permission_manager = GuideBookBookPermissionManager(db)
document_manager = DocumentManager(db)


@router.post(
    "/{book_id}/chapters",
    response_model=ChapterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_chapter(
    book_id: str,
    chapter_data: ChapterCreate,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Create a new chapter in a book

    **Authentication:** Required (Owner only)

    **Request Body:**
    - title: Chapter title (1-200 chars) [REQUIRED]
    - slug: URL-friendly slug (auto-generated from title if not provided)
    - document_id: Document ID from documents collection (auto-created if not provided)
    - parent_id: Parent chapter ID (null for root chapters)
    - order_index: Display order (default: 0)
    - order: Alias for order_index (for backward compatibility)
    - is_published: Publish status (default: true)

    **Auto-Generation:**
    - If slug not provided: Generated from title (Vietnamese-safe)
    - If document_id not provided: Creates empty document automatically

    **Validation:**
    - Slug must be unique within book
    - Parent chapter must exist in same book (if provided)
    - Max depth: 3 levels (0, 1, 2)

    **Returns:**
    - 201: Chapter created successfully
    - 400: Max depth exceeded or validation error
    - 403: User is not the book owner
    - 404: Guide or parent chapter not found
    - 409: Slug already exists in book
    """
    try:
        user_id = current_user["uid"]

        # Verify book ownership
        book = book_manager.get_book(book_id)

        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found",
            )

        if book["user_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only book owner can create chapters",
            )

        # Auto-generate or normalize slug
        if not chapter_data.slug:
            # Generate from title
            slug = chapter_data.title.lower()
            # Normalize unicode characters (Vietnamese → ASCII)
            slug = (
                unicodedata.normalize("NFKD", slug)
                .encode("ascii", "ignore")
                .decode("ascii")
            )
            # Replace spaces and special chars with hyphens
            slug = re.sub(r"[^a-z0-9]+", "-", slug)
            # Remove leading/trailing hyphens
            slug = slug.strip("-")
        else:
            # Normalize provided slug (remove Vietnamese diacritics, special chars)
            slug = chapter_data.slug.lower()
            # Normalize unicode characters (Vietnamese → ASCII)
            slug = (
                unicodedata.normalize("NFKD", slug)
                .encode("ascii", "ignore")
                .decode("ascii")
            )
            # Replace special chars (including :) with hyphens, keep only a-z0-9-
            slug = re.sub(r"[^a-z0-9]+", "-", slug)
            # Remove leading/trailing hyphens
            slug = slug.strip("-")

        # Ensure uniqueness by appending number if needed
        original_slug = slug
        counter = 1
        while chapter_manager.slug_exists(book_id, slug):
            slug = f"{original_slug}-{counter}"
            counter += 1

        chapter_data.slug = slug

        # Verify parent exists if provided
        if chapter_data.parent_id:
            parent = chapter_manager.get_chapter(chapter_data.parent_id)

            if not parent:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Parent chapter not found",
                )

            # Verify parent belongs to same book
            if parent["book_id"] != book_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Parent chapter must belong to the same book",
                )

        # Auto-create empty document if not provided
        if not chapter_data.document_id:
            document_id = document_manager.create_document(
                user_id=user_id,
                title=chapter_data.title,
                content_html="<p></p>",  # Empty content
                content_text="",
                source_type="created",
                document_type="doc",
            )
            chapter_data.document_id = document_id
            logger.info(
                f"✅ Auto-created empty document: {document_id} for chapter: {chapter_data.title}"
            )

        # Create chapter (depth is auto-calculated)
        chapter = chapter_manager.create_chapter(book_id, chapter_data)

        logger.info(
            f"✅ User {user_id} created chapter in book {book_id}: "
            f"{chapter['chapter_id']} ({chapter_data.title})"
        )
        return chapter

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to create chapter: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create chapter",
        )


@router.get("/{book_id}/chapters", response_model=Dict[str, Any])
async def get_chapter_tree(
    book_id: str,
    language: Optional[str] = Query(
        None,
        description="Language code (e.g., 'en', 'vi') to retrieve translated chapter titles",
    ),
    include_unpublished: bool = Query(
        False, description="Include unpublished chapters (owner only)"
    ),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """
    Get hierarchical tree structure of all chapters in a book

    **Authentication:** Optional (public access for published Community books)

    **Query Parameters:**
    - language: Optional language code to retrieve translated chapter metadata
      * If specified, returns translated title/description for each chapter
      * Original structure preserved, only text content translated
      * Silently falls back to default language if translation missing
    - include_unpublished: Include unpublished chapters (default: false)
      * Always true for book owner
      * Ignored for non-owners

    **Public Access:**
    - If book is published to Community (is_public=true): Returns chapter TOC
    - Chapter list includes is_preview_free flag
    - No authentication required

    **Authenticated Access:**
    - Owner: Full access, can see unpublished chapters
    - Shared users: Access based on permissions
    - Buyers: Access based on purchase

    **Tree Structure:**
    - Max 3 levels: Level 0 (root), Level 1 (sub), Level 2 (sub-sub)
    - Ordered by order_index at each level
    - Unpublished chapters hidden for non-owners

    **Response Fields:**
    - book_id: Book ID
    - title: Book title (translated if language specified)
    - slug: Book slug
    - cover: Book cover image URL
    - description: Book description (translated if language specified)
    - chapters: Hierarchical chapter tree (with translations if language specified)
    - total_chapters: Total chapter count
    - current_language: Active language code

    **Returns:**
    - 200: Chapter tree structure with book info (optionally translated)
    - 403: User doesn't have access to book
    - 404: Book not found
    """
    try:
        # Verify book exists
        book = book_manager.get_book(book_id)

        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found",
            )

        # Check if book is public (published to Community)
        is_public = book.get("community_config", {}).get("is_public", False)

        # If no user and book not public, require authentication
        if not current_user and not is_public:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required for this book",
            )

        # Determine access level
        is_owner = False
        has_access = is_public  # Public books are accessible by default

        if current_user:
            user_id = current_user["uid"]
            is_owner = book["user_id"] == user_id

            if is_owner:
                has_access = True
            elif not is_public:
                # Private book - check permissions
                has_permission = permission_manager.check_permission(
                    book_id=book_id, user_id=user_id
                )
                has_access = has_permission

        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this book",
            )

        # Owner always sees unpublished chapters
        show_unpublished = is_owner or include_unpublished

        # Get chapter tree
        chapters = chapter_manager.get_chapter_tree(
            book_id=book_id, include_unpublished=show_unpublished
        )

        # Apply language translations if requested
        default_language = book.get("default_language", "vi")
        current_language = language if language else default_language

        # Get book translations for title/description
        book_title = book.get("title")
        book_description = book.get("description")

        if language and language != default_language:
            book_translations = book.get("translations", {})
            if language in book_translations:
                book_trans = book_translations[language]
                book_title = book_trans.get("title", book_title)
                book_description = book_trans.get("description", book_description)

            # Apply translations to chapters recursively
            def translate_chapters_recursive(chapter_list):
                """Apply translations to chapter tree nodes"""
                translated_list = []
                for chapter in chapter_list:
                    # Get chapter translations
                    chapter_translations = chapter.get("translations", {})
                    if language in chapter_translations:
                        trans = chapter_translations[language]
                        chapter["title"] = trans.get("title", chapter.get("title"))
                        chapter["description"] = trans.get(
                            "description", chapter.get("description")
                        )

                    # Recursively translate children
                    if "children" in chapter and chapter["children"]:
                        chapter["children"] = translate_chapters_recursive(
                            chapter["children"]
                        )

                    translated_list.append(chapter)
                return translated_list

            chapters = translate_chapters_recursive(chapters)

        # Count total chapters
        total = chapter_manager.count_chapters(book_id)

        logger.info(
            f"📄 {'User ' + current_user['uid'] if current_user else 'Anonymous'} retrieved chapter tree for book {book_id} in language {current_language}: {total} chapters"
        )

        return {
            "book_id": book_id,
            "title": book_title,
            "slug": book.get("slug"),
            "cover": book.get("cover_image_url"),
            "description": book_description,
            "chapters": chapters,
            "total_chapters": total,
            "current_language": current_language,
            "available_languages": book.get("available_languages", [default_language]),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get chapter tree: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get chapter tree",
        )


@router.get("/{book_id}/chapters/{chapter_id}", response_model=Dict[str, Any])
async def get_chapter(
    book_id: str,
    chapter_id: str,
    language: Optional[str] = Query(
        None,
        description="Language code (e.g., 'en', 'vi') to retrieve translated content",
    ),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """
    Get single chapter with full content_html in specified language

    **Use Case:** Load chapter content into Tiptap editor with language support

    **Authentication:** Optional (public access for published Community books)

    **Query Parameters:**
    - language: Optional language code to retrieve translated content
      * If specified and translation exists, returns translated title/description/content_html
      * If not specified or no translation, returns default language content_html
      * Silently falls back to default if translation missing

    **Response:**
    {
        "chapter_id": "...",
        "book_id": "...",
        "title": "Translated title",
        "description": "Translated description",
        "content_html": "<p>Translated HTML content...</p>",
        "current_language": "en",
        "default_language": "vi",
        "available_languages": ["vi", "en", "zh-CN"],
        "order_index": 1,
        "level": 0,
        "parent_id": null,
        "is_published": true,
        "is_preview_free": false
    }

    **Returns:**
    - 200: Chapter details with content_html (optionally translated)
    - 403: User doesn't have access to this chapter
    - 404: Book or chapter not found
    """
    try:
        # Verify book exists
        book = book_manager.get_book(book_id)

        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found",
            )

        # Check if book is public
        is_public = book.get("community_config", {}).get("is_public", False)

        # If no user and book not public, require authentication
        if not current_user and not is_public:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required for this book",
            )

        # Determine access level
        is_owner = False
        has_access = is_public

        if current_user:
            user_id = current_user["uid"]
            is_owner = book["user_id"] == user_id

            if is_owner:
                has_access = True
            elif not is_public:
                has_permission = permission_manager.check_permission(
                    book_id=book_id, user_id=user_id
                )
                has_access = has_permission

        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this book",
            )

        # Get chapter
        chapter = chapter_manager.get_chapter(chapter_id)

        if not chapter or chapter.get("book_id") != book_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Chapter not found in book {book_id}",
            )

        # Get document content
        document_id = chapter.get("document_id")
        if document_id:
            document = document_manager.get_document(document_id)
            if document:
                chapter["content_html"] = document.get("content_html", "")
                chapter["content_text"] = document.get("content_text", "")

        # Apply language translation if requested
        default_language = chapter.get(
            "default_language", book.get("default_language", "vi")
        )
        current_language = language if language else default_language

        if language and language != default_language:
            translations = chapter.get("translations", {})
            if language in translations:
                trans = translations[language]
                chapter["title"] = trans.get("title", chapter.get("title"))
                chapter["description"] = trans.get(
                    "description", chapter.get("description")
                )
                chapter["content_html"] = trans.get(
                    "content_html", chapter.get("content_html", "")
                )

                # Handle background_config for translation
                # If translation has custom background, use it
                # Otherwise, fallback to default background (sync from root)
                if "background_config" in trans:
                    chapter["background_config"] = trans["background_config"]
                # If no custom background in translation, keep the default background_config
                # (already loaded from root level, no need to change)

        # Add language metadata to response
        chapter["current_language"] = current_language
        chapter["default_language"] = default_language
        chapter["available_languages"] = chapter.get(
            "available_languages", [default_language]
        )

        logger.info(
            f"📖 {'User ' + current_user['uid'] if current_user else 'Anonymous'} "
            f"accessed chapter {chapter_id} in language {current_language}"
        )

        return chapter

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get chapter: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get chapter",
        )


@router.patch(
    "/{book_id}/chapters/{chapter_id}",
    response_model=ChapterResponse,
)
async def update_chapter(
    book_id: str,
    chapter_id: str,
    chapter_data: ChapterUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Update chapter metadata or move to different parent

    **Authentication:** Required (Owner only)

    **Request Body:**
    - Any fields from ChapterCreate (all optional)
    - Moving chapter recalculates depth and validates max 3 levels

    **Validation:**
    - Cannot move chapter to its own descendant (circular reference)
    - Slug must be unique within book (if changed)
    - Max depth validation after parent change

    **Returns:**
    - 200: Chapter updated successfully
    - 400: Circular reference or max depth exceeded
    - 403: User is not the book owner
    - 404: Chapter not found
    - 409: Slug already exists in book
    """
    try:
        user_id = current_user["uid"]

        # Verify book ownership
        book = book_manager.get_book(book_id)

        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found",
            )

        if book["user_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only book owner can update chapters",
            )

        # Get existing chapter
        chapter = chapter_manager.get_chapter(chapter_id)

        if not chapter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chapter not found",
            )

        # Verify chapter belongs to book
        if chapter["book_id"] != book_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chapter does not belong to this book",
            )

        # Check slug uniqueness if changed
        if chapter_data.slug and chapter_data.slug != chapter["slug"]:
            if chapter_manager.slug_exists(book_id, chapter_data.slug):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Slug '{chapter_data.slug}' already exists in this book",
                )

        # Update chapter
        updated_chapter = chapter_manager.update_chapter(chapter_id, chapter_data)

        if not updated_chapter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chapter not found",
            )

        logger.info(f"✏️ User {user_id} updated chapter: {chapter_id}")
        return updated_chapter

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update chapter: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update chapter",
        )


@router.patch(
    "/{book_id}/chapters/{chapter_id}/preview",
    response_model=ChapterResponse,
    status_code=status.HTTP_200_OK,
    summary="Toggle chapter preview status",
)
async def toggle_chapter_preview(
    book_id: str,
    chapter_id: str,
    preview_data: TogglePreviewRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Toggle Free Preview Status for Chapter**

    Allows book owner to mark/unmark chapters as free preview on Community Books.
    Free preview chapters can be read without purchase on the preview page.

    **Authentication:** Required (Owner only)

    **Use Cases:**
    - Mark first chapter as free to attract readers
    - Unmark chapter to make it paid-only
    - Change preview strategy based on engagement

    **Path Parameters:**
    - `book_id`: Book ID
    - `chapter_id`: Chapter ID to toggle

    **Request Body:**
    - `is_preview_free`: true to allow free preview, false to require purchase

    **Returns:**
    - 200: Updated chapter with new preview status
    - 403: User is not book owner
    - 404: Book or chapter not found
    """
    try:
        user_id = current_user["uid"]

        # Verify book ownership
        book = book_manager.get_book(book_id)

        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found",
            )

        if book["user_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only book owner can toggle chapter preview status",
            )

        # Verify chapter belongs to book
        chapter = chapter_manager.get_chapter(chapter_id)

        if not chapter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chapter not found",
            )

        if chapter["book_id"] != book_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chapter does not belong to this book",
            )

        # Update preview status
        update_data = ChapterUpdate(is_preview_free=preview_data.is_preview_free)
        updated_chapter = chapter_manager.update_chapter(chapter_id, update_data)

        if not updated_chapter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Failed to update chapter",
            )

        action = "enabled" if preview_data.is_preview_free else "disabled"
        logger.info(
            f"👁️ User {user_id} {action} free preview for chapter {chapter_id} in book {book_id}"
        )

        return updated_chapter

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to toggle chapter preview: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to toggle chapter preview",
        )


@router.delete("/{book_id}/chapters/{chapter_id}", response_model=Dict[str, Any])
async def delete_chapter(
    book_id: str,
    chapter_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Delete chapter and all child chapters recursively

    **Authentication:** Required (Owner only)

    **Cascade Deletion:**
    1. Find all descendant chapters recursively
    2. Delete all descendants from database
    3. Delete the target chapter
    4. Return list of deleted chapter IDs

    **Returns:**
    - 200: Chapter(s) deleted successfully with count
    - 403: User is not the book owner
    - 404: Chapter not found
    """
    try:
        user_id = current_user["uid"]

        # Verify book ownership
        book = book_manager.get_book(book_id)

        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found",
            )

        if book["user_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only book owner can delete chapters",
            )

        # Get chapter to verify it exists
        chapter = chapter_manager.get_chapter(chapter_id)

        if not chapter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chapter not found",
            )

        # Verify chapter belongs to book
        if chapter["book_id"] != book_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chapter does not belong to this book",
            )

        # Delete chapter and all children (cascade)
        deleted_ids = chapter_manager.delete_chapter_cascade(chapter_id)

        logger.info(
            f"🗑️ User {user_id} deleted chapter {chapter_id} "
            f"and {len(deleted_ids) - 1} children"
        )

        return {
            "deleted_chapter_id": chapter_id,
            "deleted_children_count": len(deleted_ids) - 1,
            "deleted_chapter_ids": deleted_ids,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete chapter: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete chapter",
        )


@router.patch(
    "/{book_id}/chapters/{chapter_id}/content",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Update chapter content (inline or document-linked)",
)
async def update_chapter_content(
    book_id: str,
    chapter_id: str,
    content_data: ChapterContentUpdate,
    language: Optional[str] = Query(
        None,
        description="Language code to save translated content (e.g., 'en', 'zh'). If not specified, updates default language content.",
    ),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Update chapter content (handles both inline and document-linked chapters)**

    **Authentication:** Required (Owner only)

    **Content Storage:**
    - **Default language** (no language parameter): Updates root-level `content_html`
    - **Translated content** (with language parameter): Updates `translations.{lang}.content_html`
    - **Inline chapters** (`content_source='inline'`): Updates `book_chapters` collection
    - **Document-linked chapters** (`content_source='document'`): Updates `documents` collection

    **Query Parameters:**
    - `language`: Optional language code (e.g., 'en', 'vi', 'zh')
      * If specified, saves content to `translations.{language}.content_html`
      * If not specified, saves to root-level `content_html` (default language)
      * Enables separate editing for each language version

    **Request Body:**
    - `content_html`: HTML content (required)
    - `content_json`: Optional JSON content (TipTap editor format)

    **Returns:**
    - 200: Content updated successfully
    - 403: User is not the book owner
    - 404: Chapter or book not found
    - 500: Update failed
    """
    try:
        user_id = current_user["uid"]

        # Verify book ownership
        book = db.online_books.find_one(
            {"book_id": book_id, "user_id": user_id, "is_deleted": False}
        )

        if not book:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Book not found or access denied",
            )

        # Determine if saving to default language or translation
        default_language = book.get("default_language", "vi")
        is_translation = language and language != default_language

        if is_translation:
            # Save to translations.{language}.content_html
            success = chapter_manager.update_chapter_translation(
                chapter_id=chapter_id,
                language=language,
                content_html=content_data.content_html,
                content_json=content_data.content_json,
            )
            message = f"Chapter translation ({language}) updated successfully"
        else:
            # Save to root-level content_html (default language)
            success = chapter_manager.update_chapter_content(
                chapter_id=chapter_id,
                content_html=content_data.content_html,
                content_json=content_data.content_json,
            )
            message = "Chapter content updated successfully"

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chapter not found or content not updated",
            )

        return {
            "success": True,
            "message": message,
            "chapter_id": chapter_id,
            "language": language if is_translation else default_language,
            "content_length": len(content_data.content_html),
        }

    except ValueError as e:
        logger.error(f"❌ Invalid chapter content update: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update chapter content: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update chapter content",
        )


@router.post("/{book_id}/chapters/reorder", response_model=Dict[str, Any])
async def reorder_chapters(
    book_id: str,
    reorder_data: ChapterReorderBulk,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Bulk reorder chapters (drag-and-drop support)

    **Authentication:** Required (Owner only)

    **Request Body:**
    - updates: Array of chapter updates with new parent_id and order_index

    **Validation:**
    - All chapter_ids must exist in the book
    - Validates max depth for each chapter after reordering
    - Prevents circular references

    **Returns:**
    - 200: Chapters reordered successfully
    - 400: Invalid chapter IDs, circular reference, or max depth exceeded
    - 403: User is not the book owner
    """
    try:
        user_id = current_user["uid"]

        # Verify book ownership
        book = book_manager.get_book(book_id)

        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found",
            )

        if book["user_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only book owner can reorder chapters",
            )

        # Reorder chapters
        updated_chapters = chapter_manager.reorder_chapters(
            book_id=book_id, updates=reorder_data.updates
        )

        logger.info(
            f"🔄 User {user_id} reordered {len(updated_chapters)} chapters in book {book_id}"
        )

        return {
            "updated_count": len(updated_chapters),
            "chapters": updated_chapters,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to reorder chapters: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reorder chapters",
        )


@router.post("/{book_id}/chapters/bulk-update", response_model=Dict[str, Any])
async def bulk_update_chapters(
    book_id: str,
    update_data: ChapterBulkUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Bulk update chapters (title, slug, description, order, parent) and optionally book info - For reorganizing book menu

    **Authentication:** Required (Owner only)

    **Use Case:**
    Frontend displays chapter list → User edits titles, descriptions, reorders, reparents → Submit all changes at once

    **Request Body:**
    - updates: Array of chapter updates
      * chapter_id: Required (which chapter to update)
      * title: Optional (new title)
      * slug: Optional (new slug, must be unique in book)
      * description: Optional (new description, max 5000 chars)
      * parent_id: Optional (new parent, null for root)
      * order_index: Optional (new position)
    - book_info: Optional book information update
      * title: Optional (new book title)
      * slug: Optional (new book slug, auto-generated from title if not provided)
      * cover_image_url: Optional (new book cover URL)

    **Features:**
    - Update multiple chapters in single request
    - Update book title, slug, and cover in same request (NEW)
    - Auto-generate book slug from title if title changed but slug not provided
    - Auto-generate chapter slug from title if title changed but slug not provided
    - Validate slug uniqueness within book (for chapters) and user's books (for book)
    - Prevent circular parent references
    - Validate max depth (3 levels)
    - Atomic operation (all or nothing)

    **Returns:**
    - 200: Chapters updated successfully with list of updated chapters
    - 400: Invalid data (circular reference, max depth, duplicate slug)
    - 403: User is not the book owner
    - 404: Book or chapter not found
    """
    try:
        user_id = current_user["uid"]

        logger.info(
            f"📝 Bulk update {len(update_data.updates)} chapters in book {book_id}"
        )

        # 1. Verify book ownership
        book = book_manager.get_book(book_id)

        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found",
            )

        if book["user_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only book owner can update chapters",
            )

        # 2. Validate all chapters exist
        chapter_ids = [u.chapter_id for u in update_data.updates]
        chapters = list(
            db.book_chapters.find(
                {"chapter_id": {"$in": chapter_ids}, "book_id": book_id}
            )
        )

        if len(chapters) != len(chapter_ids):
            found_ids = {c["chapter_id"] for c in chapters}
            missing_ids = set(chapter_ids) - found_ids
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Chapters not found: {', '.join(missing_ids)}",
            )

        # 3. Prepare slug generation function
        def slugify(text: str) -> str:
            import re

            # Vietnamese character mapping
            vietnamese_map = {
                "à": "a",
                "á": "a",
                "ạ": "a",
                "ả": "a",
                "ã": "a",
                "â": "a",
                "ầ": "a",
                "ấ": "a",
                "ậ": "a",
                "ẩ": "a",
                "ẫ": "a",
                "ă": "a",
                "ằ": "a",
                "ắ": "a",
                "ặ": "a",
                "ẳ": "a",
                "ẵ": "a",
                "è": "e",
                "é": "e",
                "ẹ": "e",
                "ẻ": "e",
                "ẽ": "e",
                "ê": "e",
                "ề": "e",
                "ế": "e",
                "ệ": "e",
                "ể": "e",
                "ễ": "e",
                "ì": "i",
                "í": "i",
                "ị": "i",
                "ỉ": "i",
                "ĩ": "i",
                "ò": "o",
                "ó": "o",
                "ọ": "o",
                "ỏ": "o",
                "õ": "o",
                "ô": "o",
                "ồ": "o",
                "ố": "o",
                "ộ": "o",
                "ổ": "o",
                "ỗ": "o",
                "ơ": "o",
                "ờ": "o",
                "ớ": "o",
                "ợ": "o",
                "ở": "o",
                "ỡ": "o",
                "ù": "u",
                "ú": "u",
                "ụ": "u",
                "ủ": "u",
                "ũ": "u",
                "ư": "u",
                "ừ": "u",
                "ứ": "u",
                "ự": "u",
                "ử": "u",
                "ữ": "u",
                "ỳ": "y",
                "ý": "y",
                "ỵ": "y",
                "ỷ": "y",
                "ỹ": "y",
                "đ": "d",
                "À": "A",
                "Á": "A",
                "Ạ": "A",
                "Ả": "A",
                "Ã": "A",
                "Â": "A",
                "Ầ": "A",
                "Ấ": "A",
                "Ậ": "A",
                "Ẩ": "A",
                "Ẫ": "A",
                "Ă": "A",
                "Ằ": "A",
                "Ắ": "A",
                "Ặ": "A",
                "Ẳ": "A",
                "Ẵ": "A",
                "È": "E",
                "É": "E",
                "Ẹ": "E",
                "Ẻ": "E",
                "Ẽ": "E",
                "Ê": "E",
                "Ề": "E",
                "Ế": "E",
                "Ệ": "E",
                "Ể": "E",
                "Ễ": "E",
                "Ì": "I",
                "Í": "I",
                "Ị": "I",
                "Ỉ": "I",
                "Ĩ": "I",
                "Ò": "O",
                "Ó": "O",
                "Ọ": "O",
                "Ỏ": "O",
                "Õ": "O",
                "Ô": "O",
                "Ồ": "O",
                "Ố": "O",
                "Ộ": "O",
                "Ổ": "O",
                "Ỗ": "O",
                "Ơ": "O",
                "Ờ": "O",
                "Ớ": "O",
                "Ợ": "O",
                "Ở": "O",
                "Ỡ": "O",
                "Ù": "U",
                "Ú": "U",
                "Ụ": "U",
                "Ủ": "U",
                "Ũ": "U",
                "Ư": "U",
                "Ừ": "U",
                "Ứ": "U",
                "Ự": "U",
                "Ử": "U",
                "Ữ": "U",
                "Ỳ": "Y",
                "Ý": "Y",
                "Ỵ": "Y",
                "Ỷ": "Y",
                "Ỹ": "Y",
                "Đ": "D",
            }
            for vn_char, en_char in vietnamese_map.items():
                text = text.replace(vn_char, en_char)
            text = text.lower()
            text = re.sub(r"[^\w\s:.-]", "", text)  # Fixed: moved - to end
            text = re.sub(
                r"[\s:.-]+", "-", text
            )  # Convert spaces, colons, dots to hyphens
            return text.strip("-")[:100]

        # 4. Update book info if provided (title, slug, and/or cover)
        if update_data.book_info:
            book_update_fields = {}

            if update_data.book_info.title is not None:
                book_update_fields["title"] = update_data.book_info.title
                logger.info(f"📝 Updating book title to: {update_data.book_info.title}")

            # Update slug (or auto-generate from new title)
            if update_data.book_info.slug is not None:
                new_book_slug = update_data.book_info.slug
            elif update_data.book_info.title is not None:
                # Auto-generate slug from new title
                new_book_slug = slugify(update_data.book_info.title)
            else:
                new_book_slug = None

            if new_book_slug:
                # Check uniqueness (within user's books, excluding current book)
                existing_book = db.online_books.find_one(
                    {
                        "user_id": user_id,
                        "slug": new_book_slug,
                        "book_id": {"$ne": book_id},
                    }
                )

                if existing_book:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Book slug '{new_book_slug}' already exists in your books",
                    )

                book_update_fields["slug"] = new_book_slug
                logger.info(f"🔗 Updating book slug to: {new_book_slug}")

            if update_data.book_info.cover_image_url is not None:
                book_update_fields["cover_image_url"] = (
                    update_data.book_info.cover_image_url
                )
                logger.info(
                    f"🖼️  Updating book cover to: {update_data.book_info.cover_image_url}"
                )

            if book_update_fields:
                book_update_fields["updated_at"] = datetime.now(timezone.utc)
                db.online_books.update_one(
                    {"book_id": book_id}, {"$set": book_update_fields}
                )
                logger.info(
                    f"✅ Updated book {book_id} fields: {list(book_update_fields.keys())}"
                )

        # 5. Process each chapter update
        updated_chapters = []
        slug_map = {}  # Track slug changes to validate uniqueness

        for update in update_data.updates:
            chapter = next(c for c in chapters if c["chapter_id"] == update.chapter_id)
            update_fields = {}

            # Update title
            if update.title is not None:
                update_fields["title"] = update.title
                update_fields["updated_at"] = datetime.utcnow()

            # Update description
            if update.description is not None:
                update_fields["description"] = update.description
                update_fields["updated_at"] = datetime.utcnow()

            # Update slug (or auto-generate from new title)
            if update.slug is not None:
                new_slug = update.slug
            elif update.title is not None:
                # Auto-generate slug from new title
                new_slug = slugify(update.title)
            else:
                new_slug = None

            if new_slug:
                # Check uniqueness (within book, excluding current chapter)
                existing_slug = db.book_chapters.find_one(
                    {
                        "book_id": book_id,
                        "slug": new_slug,
                        "chapter_id": {"$ne": update.chapter_id},
                    }
                )

                # Also check against other updates in this batch
                if new_slug in slug_map and slug_map[new_slug] != update.chapter_id:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Duplicate slug in update batch: '{new_slug}'",
                    )

                if existing_slug:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Slug '{new_slug}' already exists in this book",
                    )

                update_fields["slug"] = new_slug
                slug_map[new_slug] = update.chapter_id

            # Update parent_id
            if update.parent_id is not None:
                # Validate not circular (chapter can't be parent of itself)
                if update.parent_id == update.chapter_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Chapter {update.chapter_id} cannot be its own parent",
                    )

                # Check parent exists
                if update.parent_id:  # Not null
                    parent = db.book_chapters.find_one(
                        {"chapter_id": update.parent_id, "book_id": book_id}
                    )
                    if not parent:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Parent chapter {update.parent_id} not found",
                        )

                    # Calculate new depth
                    parent_depth = parent.get("depth", 0)
                    new_depth = parent_depth + 1

                    if new_depth > 2:  # Max depth is 2 (0, 1, 2)
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Max nesting depth exceeded (max 3 levels). Parent depth: {parent_depth}",
                        )

                    update_fields["parent_id"] = update.parent_id
                    update_fields["depth"] = new_depth
                else:
                    # Setting parent to null (root level)
                    update_fields["parent_id"] = None
                    update_fields["depth"] = 0

            # Update order_index
            if update.order_index is not None:
                update_fields["order_index"] = update.order_index

            # Apply updates
            if update_fields:
                db.book_chapters.update_one(
                    {"chapter_id": update.chapter_id}, {"$set": update_fields}
                )

                # Get updated chapter
                updated_chapter = db.book_chapters.find_one(
                    {"chapter_id": update.chapter_id}
                )

                # Convert to dict and remove _id for JSON serialization
                chapter_dict = dict(updated_chapter)
                if "_id" in chapter_dict:
                    del chapter_dict["_id"]

                updated_chapters.append(chapter_dict)

                logger.info(
                    f"✅ Updated chapter {update.chapter_id}: {list(update_fields.keys())}"
                )

        logger.info(
            f"✅ Bulk updated {len(updated_chapters)} chapters in book {book_id}"
        )

        return {
            "success": True,
            "updated_count": len(updated_chapters),
            "chapters": updated_chapters,
            "message": f"Successfully updated {len(updated_chapters)} chapters",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to bulk update chapters: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to bulk update chapters: {str(e)}",
        )
