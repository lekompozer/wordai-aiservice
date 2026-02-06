"""
Online Book Chapter Management API Routes
Handles chapter operations: create, read, update, delete, reorder, and bulk updates.
"""

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Query,
    Request,
    UploadFile,
    File,
    Form,
)
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
    ChapterSummaryUpdate,
    # Phase 2: Multi-format content
    ChapterCreatePDFPages,
    ChapterCreateImagePages,
    ChapterCreateFromUploadedImages,
    ChapterPagesUpdate,
    PageBackgroundUpdate,
    PageReorderRequest,
)

# Services
from src.services.book_manager import UserBookManager
from src.services.book_chapter_manager import GuideBookBookChapterManager
from src.services.book_permission_manager import GuideBookBookPermissionManager
from src.services.document_manager import DocumentManager
from src.services.r2_storage_service import get_r2_service

# Database
from src.database.db_manager import DBManager

logger = logging.getLogger("chatbot")

router = APIRouter(prefix="/api/v1/books", tags=["Online Books Chapters"])

# Initialize DB connection
db_manager = DBManager()
db = db_manager.db

# Initialize R2 storage
r2_service = get_r2_service()

# Initialize managers with DB and R2
book_manager = UserBookManager(db)
chapter_manager = GuideBookBookChapterManager(
    db=db,
    book_manager=book_manager,
    s3_client=r2_service.s3_client,
    r2_config={
        "bucket": r2_service.bucket_name,
        "cdn_base_url": "https://static.wordai.pro",
    },
)
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

                    # Translate summary if available
                    chapter_summary = chapter.get("summary", {})
                    if (
                        isinstance(chapter_summary, dict)
                        and language in chapter_summary
                    ):
                        chapter["current_summary"] = chapter_summary[language]
                    elif (
                        isinstance(chapter_summary, dict)
                        and default_language in chapter_summary
                    ):
                        # Fallback to default language summary
                        chapter["current_summary"] = chapter_summary[default_language]
                    else:
                        chapter["current_summary"] = None

                    # Recursively translate children
                    if "children" in chapter and chapter["children"]:
                        chapter["children"] = translate_chapters_recursive(
                            chapter["children"]
                        )

                    translated_list.append(chapter)
                return translated_list

            chapters = translate_chapters_recursive(chapters)
        else:
            # No language specified, use default language summary if available
            def add_current_summary(chapter_list):
                """Add current_summary field based on default language"""
                for chapter in chapter_list:
                    chapter_summary = chapter.get("summary", {})
                    if (
                        isinstance(chapter_summary, dict)
                        and default_language in chapter_summary
                    ):
                        chapter["current_summary"] = chapter_summary[default_language]
                    else:
                        chapter["current_summary"] = None

                    # Recursively add to children
                    if "children" in chapter and chapter["children"]:
                        add_current_summary(chapter["children"])
                return chapter_list

            chapters = add_current_summary(chapters)

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

        # Get chapter first to check is_preview_free
        chapter = chapter_manager.get_chapter(chapter_id)

        if not chapter or chapter.get("book_id") != book_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Chapter not found in book {book_id}",
            )

        # Check if chapter is preview-free (public preview)
        is_preview_free = chapter.get("is_preview_free", False)

        # Determine access level
        is_owner = False
        has_access = (
            is_public or is_preview_free
        )  # Allow access if book is public OR chapter is preview-free

        if current_user:
            user_id = current_user["uid"]
            is_owner = book["user_id"] == user_id

            if is_owner:
                has_access = True
            elif not is_public and not is_preview_free:
                # Private book and not preview chapter - check purchase/permission
                has_permission = permission_manager.check_permission(
                    book_id=book_id, user_id=user_id
                )
                has_access = has_permission

        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this chapter. Purchase the book or check if it's a free preview.",
            )

        # If content_source='document', load content from document
        content_source = chapter.get("content_source", "inline")
        if content_source == "document":
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
    language: Optional[str] = Query(
        None,
        description="Language code to update translated metadata (e.g., 'en', 'zh'). If not specified, updates default language.",
    ),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Update chapter metadata or move to different parent

    **Authentication:** Required (Owner only)

    **Query Parameters:**
    - `language`: Optional language code (e.g., 'en', 'vi', 'zh')
      * If specified, updates `translations.{language}.title/description`
      * If not specified, updates root-level (default language)
      * Structural changes (order_index, parent_id, is_published) ALWAYS update root-level regardless of language

    **Request Body:**
    - title: Chapter title (updated in specified language)
    - description: Chapter description (updated in specified language)
    - order_index: Position in chapter list (always root-level, ignores language)
    - parent_id: Parent chapter ID (always root-level, ignores language)
    - is_published: Publish status (always root-level, ignores language)
    - slug: URL slug (always root-level, ignores language)

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

        # Determine if updating default language or translation
        default_language = chapter.get(
            "default_language", book.get("default_language", "vi")
        )
        is_translation = language and language != default_language

        if is_translation:
            # Update translation metadata only (title, description)
            # Structural fields (order_index, parent_id, etc.) are ignored for translations
            updated_chapter = chapter_manager.update_chapter_translation_metadata(
                chapter_id=chapter_id,
                language=language,
                title=chapter_data.title,
                description=chapter_data.description,
            )
            message = f"Chapter translation ({language}) metadata updated"
        else:
            # Update root-level metadata (default language + structural changes)
            updated_chapter = chapter_manager.update_chapter(chapter_id, chapter_data)
            message = "Chapter metadata updated"

        if not updated_chapter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chapter not found",
            )

        logger.info(
            f"✏️ User {user_id} updated chapter {chapter_id}"
            + (f" (language: {language})" if is_translation else "")
        )
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


@router.put(
    "/{book_id}/chapters/{chapter_id}/summary",
    response_model=ChapterResponse,
    status_code=status.HTTP_200_OK,
    summary="Update chapter summary (multi-language)",
)
async def update_chapter_summary(
    book_id: str,
    chapter_id: str,
    summary_data: ChapterSummaryUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Update Chapter Summary for Specific Language**

    Allows book owner to add/update chapter summary for preview page.
    Supports multi-language summaries (stored as {lang_code: summary_text}).

    **Authentication:** Required (Owner only)

    **Use Cases:**
    - Add Vietnamese summary for chapter preview
    - Add English summary for international readers
    - Update existing summary text

    **Path Parameters:**
    - `book_id`: Book ID
    - `chapter_id`: Chapter ID

    **Request Body:**
    - `language`: Language code (e.g., 'en', 'vi', 'zh')
    - `summary`: Summary text (1-5000 characters)

    **Returns:**
    - 200: Updated chapter with new summary
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
                detail="Only book owner can update chapter summary",
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

        # Get existing summary dict or create new one
        existing_summary = chapter.get("summary", {})

        # Update summary for the specified language
        existing_summary[summary_data.language] = summary_data.summary

        # Update chapter with new summary dict
        update_data = ChapterUpdate(summary=existing_summary)
        updated_chapter = chapter_manager.update_chapter(chapter_id, update_data)

        if not updated_chapter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Failed to update chapter summary",
            )

        logger.info(
            f"📝 User {user_id} updated summary for chapter {chapter_id} (lang: {summary_data.language})"
        )

        return updated_chapter

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update chapter summary: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update chapter summary",
        )


@router.delete(
    "/{book_id}/chapters/{chapter_id}/summary/{language}",
    response_model=ChapterResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete chapter summary for specific language",
)
async def delete_chapter_summary(
    book_id: str,
    chapter_id: str,
    language: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Delete Chapter Summary for Specific Language**

    Removes summary text for a specific language from chapter.

    **Authentication:** Required (Owner only)

    **Path Parameters:**
    - `book_id`: Book ID
    - `chapter_id`: Chapter ID
    - `language`: Language code to remove (e.g., 'en', 'vi')

    **Returns:**
    - 200: Updated chapter without the specified summary
    - 403: User is not book owner
    - 404: Book, chapter, or summary not found
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
                detail="Only book owner can delete chapter summary",
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

        # Get existing summary dict
        existing_summary = chapter.get("summary", {})

        # Check if language exists
        if language not in existing_summary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Summary for language '{language}' not found",
            )

        # Remove summary for the specified language
        del existing_summary[language]

        # Update chapter with modified summary dict
        update_data = ChapterUpdate(summary=existing_summary)
        updated_chapter = chapter_manager.update_chapter(chapter_id, update_data)

        if not updated_chapter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Failed to delete chapter summary",
            )

        logger.info(
            f"🗑️ User {user_id} deleted summary for chapter {chapter_id} (lang: {language})"
        )

        return updated_chapter

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete chapter summary: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete chapter summary",
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
    language: Optional[str] = Query(
        None,
        description="Language code to update translated metadata (e.g., 'en', 'zh'). If not specified, updates default language.",
    ),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Bulk update chapters (title, slug, description, order, parent) and optionally book info - For reorganizing book menu

    **Authentication:** Required (Owner only)

    **Query Parameters:**
    - `language`: Optional language code (e.g., 'en', 'vi', 'zh')
      * If specified, updates `translations.{language}` for book and chapter titles/descriptions
      * If not specified, updates root-level (default language)
      * Structural changes (order, parent, slug) ALWAYS update root-level regardless of language

    **Use Case:**
    Frontend displays chapter list → User edits titles, descriptions, reorders, reparents → Submit all changes at once

    **Request Body:**
    - updates: Array of chapter updates
      * chapter_id: Required (which chapter to update)
      * title: Optional (new title - updated in specified language)
      * slug: Optional (new slug - always root-level, ignores language)
      * description: Optional (new description - updated in specified language)
      * parent_id: Optional (new parent - always root-level, ignores language)
      * order_index: Optional (new position - always root-level, ignores language)
    - book_info: Optional book information update
      * title: Optional (new book title - updated in specified language)
      * slug: Optional (new book slug - always root-level, ignores language)
      * cover_image_url: Optional (new book cover URL - always root-level, ignores language)

    **Features:**
    - Update multiple chapters in single request
    - Update book title, slug, and cover in same request
    - Multi-language support: Update translations when language parameter provided
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

        # Determine if updating default language or translation
        default_language = book.get("default_language", "vi")
        is_translation = language and language != default_language

        # 4. Update book info if provided (title, slug, and/or cover)
        if update_data.book_info:
            if is_translation:
                # Update book translation metadata
                book_update_fields = {}

                if update_data.book_info.title is not None:
                    book_update_fields[f"translations.{language}.title"] = (
                        update_data.book_info.title
                    )
                    logger.info(
                        f"📝 Updating book title ({language}): {update_data.book_info.title}"
                    )

                if update_data.book_info.description is not None:
                    book_update_fields[f"translations.{language}.description"] = (
                        update_data.book_info.description
                    )
                    logger.info(
                        f"📝 Updating book description ({language}): {len(update_data.book_info.description)} chars"
                    )

                # Note: slug and cover_image_url are always root-level (structural), ignore for translations

                if book_update_fields:
                    book_update_fields[f"translations.{language}.updated_at"] = (
                        datetime.now(timezone.utc)
                    )
                    book_update_fields["updated_at"] = datetime.now(timezone.utc)
                    db.online_books.update_one(
                        {"book_id": book_id}, {"$set": book_update_fields}
                    )
                    logger.info(f"✅ Updated book {book_id} translation ({language})")
            else:
                # Update root-level (default language)
                book_update_fields = {}

                if update_data.book_info.title is not None:
                    book_update_fields["title"] = update_data.book_info.title
                    logger.info(
                        f"📝 Updating book title to: {update_data.book_info.title}"
                    )

                if update_data.book_info.description is not None:
                    book_update_fields["description"] = (
                        update_data.book_info.description
                    )
                    logger.info(
                        f"📝 Updating book description to: {len(update_data.book_info.description)} chars"
                    )

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

            if is_translation:
                # Update translation metadata only (title, description)
                # Structural fields (slug, order, parent) are ignored

                if update.title is not None:
                    update_fields[f"translations.{language}.title"] = update.title

                if update.description is not None:
                    update_fields[f"translations.{language}.description"] = (
                        update.description
                    )

                if update_fields:
                    update_fields[f"translations.{language}.updated_at"] = (
                        datetime.utcnow()
                    )
                    update_fields["updated_at"] = datetime.utcnow()

                    db.book_chapters.update_one(
                        {"chapter_id": update.chapter_id}, {"$set": update_fields}
                    )

                    logger.info(
                        f"✅ Updated chapter {update.chapter_id} translation ({language}): {list(update_fields.keys())}"
                    )
            else:
                # Update root-level (default language + structural changes)

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

                    logger.info(
                        f"✅ Updated chapter {update.chapter_id}: {list(update_fields.keys())}"
                    )

            # Get updated chapter for response
            if update_fields:
                updated_chapter = db.book_chapters.find_one(
                    {"chapter_id": update.chapter_id}
                )

                # Convert to dict and remove _id for JSON serialization
                chapter_dict = dict(updated_chapter)
                if "_id" in chapter_dict:
                    del chapter_dict["_id"]

                updated_chapters.append(chapter_dict)

        logger.info(
            f"✅ Bulk updated {len(updated_chapters)} chapters in book {book_id}"
            + (f" (language: {language})" if is_translation else "")
        )

        return {
            "success": True,
            "updated_count": len(updated_chapters),
            "chapters": updated_chapters,
            "language": language if is_translation else default_language,
            "message": f"Successfully updated {len(updated_chapters)} chapters"
            + (f" in {language}" if is_translation else ""),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to bulk update chapters: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to bulk update chapters: {str(e)}",
        )


# ═══════════════════════════════════════════════════════════════════════
# PHASE 2: Multi-format Content Support (PDF Pages, Image Pages)
# ═══════════════════════════════════════════════════════════════════════


@router.post(
    "/{book_id}/chapters/from-pdf",
    response_model=Dict[str, Any],
    status_code=status.HTTP_201_CREATED,
)
async def create_chapter_from_pdf(
    book_id: str,
    request: ChapterCreatePDFPages,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Create chapter from existing PDF file (pdf_pages mode)

    **Authentication:** Required (Owner only)

    **Flow:**
    1. Validate PDF file exists in studyhub_files
    2. Download PDF from R2
    3. Extract pages → Convert to PNG images
    4. Upload page images to R2
    5. Create chapter with pages array

    **Request Body:**
    - file_id: Existing PDF file ID from studyhub_files [REQUIRED]
    - title: Chapter title [REQUIRED]
    - slug: URL slug (auto-generated if not provided)
    - parent_id: Parent chapter ID for nesting
    - order_index: Display order (default: 0)
    - is_published: Publish status (default: true)
    - is_preview_free: Allow free preview (default: false)

    **Returns:**
    - 201: Chapter created with pages array
    - 400: PDF file not found or invalid
    - 403: User is not the book owner
    - 404: Book not found
    - 500: PDF processing failed
    """
    try:
        user_id = current_user["uid"]

        # Verify book ownership
        book = book_manager.get_book(book_id)
        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Book {book_id} not found",
            )

        if book.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only book owner can create chapters",
            )

        logger.info(
            f"📄 [API] Creating PDF chapter in book {book_id} from file {request.file_id}"
        )

        # Create chapter from PDF
        chapter = await chapter_manager.create_chapter_from_pdf(
            book_id=book_id,
            user_id=user_id,
            file_id=request.file_id,
            title=request.title,
            slug=request.slug,
            order_index=request.order_index,
            parent_id=request.parent_id,
            is_published=request.is_published,
            is_preview_free=request.is_preview_free,
        )

        logger.info(
            f"✅ [API] Created PDF chapter {chapter['chapter_id']} with {chapter['total_pages']} pages"
        )

        return {
            "success": True,
            "chapter": chapter,
            "message": f"Chapter created from PDF with {chapter['total_pages']} pages",
        }

    except ValueError as e:
        logger.error(f"❌ Validation error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to create PDF chapter: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create PDF chapter: {str(e)}",
        )


@router.put(
    "/chapters/{chapter_id}/pages",
    response_model=Dict[str, Any],
)
async def update_chapter_pages(
    chapter_id: str,
    request: ChapterPagesUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Update page elements (add highlights, notes, annotations)

    **Authentication:** Required (Owner only)

    **Supported Content Types:**
    - pdf_pages: PDF chapters
    - image_pages: Manga/Comic chapters

    **Request Body:**
    - pages: Array of pages with updated elements
      - page_number: Page number (1-indexed)
      - elements: Array of overlay elements
        - id: Element ID
        - type: Element type (highlight, text, shape, etc.)
        - x, y: Position in pixels
        - width, height: Dimensions (for shapes/images)
        - color, content, etc.: Type-specific properties

    **Notes:**
    - Only updates specified pages (partial update)
    - Preserves background URLs and dimensions
    - Elements are overlay graphics on top of page backgrounds

    **Returns:**
    - 200: Pages updated successfully
    - 400: Invalid content_source (not pdf_pages or image_pages)
    - 403: User is not the book owner
    - 404: Chapter not found
    """
    try:
        user_id = current_user["uid"]

        logger.info(
            f"📝 [API] Updating {len(request.pages)} pages for chapter {chapter_id}"
        )

        # Convert Pydantic models to dicts
        pages_data = [page.model_dump() for page in request.pages]

        # Update pages
        updated_chapter = await chapter_manager.update_chapter_pages(
            chapter_id=chapter_id,
            user_id=user_id,
            pages_update=pages_data,
        )

        total_elements = sum(
            len(page.get("elements", [])) for page in updated_chapter.get("pages", [])
        )

        logger.info(
            f"✅ [API] Updated chapter {chapter_id}: "
            f"{len(request.pages)} pages, {total_elements} total elements"
        )

        return {
            "success": True,
            "chapter": updated_chapter,
            "pages_updated": len(request.pages),
            "total_elements": total_elements,
            "message": f"Updated {len(request.pages)} pages with {total_elements} elements",
        }

    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        logger.error(f"❌ Validation error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update chapter pages: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update chapter pages: {str(e)}",
        )


@router.put(
    "/chapters/{chapter_id}/pages/{page_number}/background",
    response_model=Dict[str, Any],
)
async def update_page_background(
    chapter_id: str,
    page_number: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
    file: Optional[UploadFile] = File(None),
    background_url: Optional[str] = Form(None),
    width: Optional[int] = Form(None),
    height: Optional[int] = Form(None),
    keep_elements: bool = Form(True),
):
    """
    Update background image for a specific page

    **Authentication:** Required (Owner only)

    **Supported Content Types:**
    - pdf_pages: PDF chapters
    - image_pages: Manga/Comic chapters

    **Request Methods:**
    1. Upload new file: Send file via multipart/form-data
    2. Use existing URL: Send background_url in form data

    **Form Fields:**
    - file: Image file to upload (JPG, PNG, WEBP) - EITHER this OR background_url
    - background_url: Existing image URL - EITHER this OR file
    - width: Optional - New page width (auto-detect if not provided)
    - height: Optional - New page height (auto-detect if not provided)
    - keep_elements: Optional - Keep existing elements (default: true)

    **Use Cases:**
    - Replace corrupted page image
    - Update to higher quality image
    - Change page image entirely (e.g., fix wrong page in manga)

    **Returns:**
    - 200: Background updated successfully
    - 400: Invalid content_mode, page not found, or both file and URL provided
    - 403: User is not the book owner
    - 404: Chapter not found
    """
    try:
        user_id = current_user["uid"]

        logger.info(
            f"🖼️ [API] Updating page {page_number} background for chapter {chapter_id}"
        )

        # Validate: Must provide EITHER file OR background_url, not both
        if file and background_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provide either 'file' or 'background_url', not both",
            )
        if not file and not background_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Must provide either 'file' to upload or 'background_url'",
            )

        # If file provided → Upload to R2
        final_url = background_url
        if file:
            logger.info(f"📤 [API] Uploading replacement image: {file.filename}")

            # Validate file type
            allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
            if file.content_type not in allowed_types:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid file type. Allowed: JPG, PNG, WEBP. Got: {file.content_type}",
                )

            # Process and upload image
            from PIL import Image
            from io import BytesIO

            contents = await file.read()
            img = Image.open(BytesIO(contents))

            # Convert to RGB (handle transparency)
            if img.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                background.paste(
                    img, mask=img.split()[-1] if img.mode == "RGBA" else None
                )
                img = background

            # Auto-detect dimensions if not provided
            if width is None or height is None:
                width = width or img.size[0]
                height = height or img.size[1]
                logger.info(f"   📐 Detected dimensions: {width}×{height}px")

            # Compress to JPEG
            output = BytesIO()
            img.save(output, format="JPEG", quality=90, optimize=True)
            output.seek(0)

            # Upload to R2: studyhub/chapters/{chapter_id}/page-{page_number}.jpg
            r2_service = get_r2_service()
            r2_key = f"studyhub/chapters/{chapter_id}/page-{page_number}.jpg"

            r2_service.s3_client.put_object(
                Bucket=r2_service.bucket_name,
                Key=r2_key,
                Body=output.getvalue(),
                ContentType="image/jpeg",
            )

            final_url = f"{r2_service.public_url}/{r2_key}"
            logger.info(f"✅ [API] Uploaded to R2: {final_url}")

        # Update background
        updated_chapter = await chapter_manager.update_page_background(
            chapter_id=chapter_id,
            user_id=user_id,
            page_number=page_number,
            background_url=final_url,
            width=width,
            height=height,
            keep_elements=keep_elements,
        )

        # Get updated page info
        updated_page = None
        for page in updated_chapter.get("pages", []):
            if page["page_number"] == page_number:
                updated_page = page
                break

        if updated_page:
            logger.info(
                f"✅ [API] Updated page {page_number} background: "
                f"{updated_page['width']}×{updated_page['height']}px"
            )
        else:
            logger.warning(f"⚠️ Page {page_number} not found in updated chapter")

        return {
            "success": True,
            "chapter": updated_chapter,
            "updated_page": updated_page,
            "message": f"Page {page_number} background updated successfully",
        }

    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        logger.error(f"❌ Validation error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update page background: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update page background: {str(e)}",
        )


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 2: Image Pages & Manga Support
# ══════════════════════════════════════════════════════════════════════════════


@router.post(
    "/{book_id}/chapters/upload-images",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Upload images directly to chapter storage",
    description="""
    Upload images and get chapter_id + CDN URLs immediately.

    **Simplified Flow:**
    - First upload: Auto-generates chapter_id
    - Subsequent uploads: Use same chapter_id to add more pages
    - Images uploaded directly to permanent storage
    - No temp storage, no re-upload, no cleanup needed

    **Process:**
    1. Generate/use chapter_id
    2. Upload to studyhub/chapters/{chapter_id}/page-{N}.jpg
    3. Return chapter_id + URLs
    4. Images ready for chapter creation

    **Required:** Owner access to the book
    """,
)
async def upload_images_for_chapter(
    book_id: str,
    file: List[UploadFile] = File(
        ..., description="Image file(s) to upload - can be single or multiple"
    ),
    chapter_id: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Upload multiple images and get CDN URLs"""
    from PIL import Image
    import io
    import uuid

    try:
        user_id = current_user["uid"]

        # Support both single file and multiple files
        files = file if isinstance(file, list) else [file]

        # 1. Validate book ownership (online_books collection)
        book = db.online_books.find_one({"book_id": book_id, "user_id": user_id})
        if not book:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Book not found or access denied",
            )

        # 2. Validate constraints
        if len(files) > 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum 10 files per request",
            )

        # Check total size
        total_size = 0
        for file in files:
            content = await file.read()
            total_size += len(content)
            await file.seek(0)  # Reset for re-reading

        if total_size > 100 * 1024 * 1024:  # 100 MB
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Total size {total_size / 1024 / 1024:.1f}MB exceeds 100MB limit",
            )

        # 3. Generate or use existing chapter_id
        if not chapter_id:
            chapter_id = str(uuid.uuid4())
            logger.info(f"📝 [UPLOAD] Generated new chapter_id: {chapter_id}")
        else:
            logger.info(f"📝 [UPLOAD] Using existing chapter_id: {chapter_id}")

        logger.info(f"📤 [UPLOAD] Uploading {len(files)} images to book {book_id}")
        logger.info(f"   User: {user_id}, Total size: {total_size / 1024 / 1024:.2f}MB")

        # 4. Get current page count for this chapter_id
        s3_client = r2_service.s3_client
        r2_config = {
            "bucket": r2_service.bucket_name,
            "cdn_base_url": r2_service.public_url,
        }

        # List existing pages to get next page number
        prefix = f"studyhub/chapters/{chapter_id}/"
        try:
            response = s3_client.list_objects_v2(
                Bucket=r2_config["bucket"], Prefix=prefix
            )
            existing_pages = len(response.get("Contents", []))
        except:
            existing_pages = 0

        next_page_number = existing_pages + 1

        # 5. Process and upload each image
        uploaded_images = []

        for idx, file in enumerate(files, 1):
            try:
                # Validate file type
                if not file.content_type or not file.content_type.startswith("image/"):
                    raise ValueError(f"File {file.filename} is not an image")

                # Check individual file size
                content = await file.read()
                if len(content) > 20 * 1024 * 1024:  # 20 MB per file
                    raise ValueError(f"File {file.filename} exceeds 20MB limit")

                # Load image
                image = Image.open(io.BytesIO(content))
                original_width, original_height = image.size

                # Convert to RGB (handle transparency)
                if image.mode in ("RGBA", "LA", "P"):
                    background = Image.new("RGB", image.size, (255, 255, 255))
                    if image.mode == "P":
                        image = image.convert("RGBA")
                    background.paste(
                        image,
                        mask=(
                            image.split()[-1] if image.mode in ("RGBA", "LA") else None
                        ),
                    )
                    image = background
                elif image.mode != "RGB":
                    image = image.convert("RGB")

                # Compress to JPEG
                buffer = io.BytesIO()
                image.save(buffer, format="JPEG", quality=90, optimize=True)
                buffer.seek(0)

                # R2 path: studyhub/chapters/{chapter_id}/page-{N}.jpg (PERMANENT)
                page_number = next_page_number + idx - 1
                object_key = f"studyhub/chapters/{chapter_id}/page-{page_number}.jpg"

                # Upload to R2
                s3_client.upload_fileobj(
                    buffer,
                    r2_config["bucket"],
                    object_key,
                    ExtraArgs={"ContentType": "image/jpeg"},
                )

                # Generate CDN URL
                cdn_url = f"{r2_config['cdn_base_url']}/{object_key}"

                uploaded_images.append(
                    {
                        "file_name": file.filename,
                        "file_size": len(content),
                        "url": cdn_url,
                        "width": original_width,
                        "height": original_height,
                        "page_number": page_number,
                    }
                )

                logger.info(
                    f"  ✅ Uploaded page {page_number}: {file.filename} → {cdn_url}"
                )

            except Exception as e:
                logger.error(f"❌ Failed to process {file.filename}: {e}")
                raise ValueError(f"Failed to process {file.filename}: {str(e)}")

        current_page_count = existing_pages + len(uploaded_images)

        logger.info(f"✅ [UPLOAD] Successfully uploaded {len(uploaded_images)} images")
        logger.info(f"   Chapter ID: {chapter_id}, Total pages: {current_page_count}")

        return {
            "success": True,
            "chapter_id": chapter_id,  # Return for subsequent uploads
            "images": uploaded_images,
            "total_uploaded": len(uploaded_images),
            "total_size": total_size,
            "current_page_count": current_page_count,
            "message": f"Uploaded {len(uploaded_images)} images successfully",
        }

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"❌ Validation error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Failed to upload images: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload images: {str(e)}",
        )


@router.post(
    "/chapters/{chapter_id}/upload-element-image",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Upload/copy image for page element (IMAGE/VIDEO thumbnail)",
    description="""
    Upload or copy image to use in page elements. Supports 2 methods:

    **Method 1: Upload new file**
    - Send `file` in multipart form-data
    - Backend uploads to public CDN (permanent)

    **Method 2: Copy from Library**
    - Send `library_id` in form-data
    - Backend downloads from Library → re-uploads to public CDN
    - Converts private presigned URL → permanent public URL

    **Storage:** Public CDN (permanent, no expiry)
    **Path:** `studyhub/chapters/{chapter_id}/elements/{uuid}.jpg`
    **URL Format:** `https://static.wordai.pro/studyhub/chapters/{chapter_id}/elements/{uuid}.jpg`

    **Use Cases:**
    - Upload new image for IMAGE element
    - Copy image from Library (fixes presigned URL expiry issue)
    - Video thumbnail for VIDEO element

    **Required:** Owner access to the chapter's book
    """,
)
async def upload_element_image(
    chapter_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    file: Optional[UploadFile] = File(None),
    library_id: Optional[str] = Form(None),
):
    """Upload or copy image for page element overlay"""
    from PIL import Image
    import io
    import uuid
    import requests

    try:
        user_id = current_user["uid"]

        logger.info(f"🖼️ [ELEMENT_IMAGE] Processing for chapter {chapter_id}")

        # Validate: Must provide EITHER file OR library_id
        if file and library_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provide either 'file' or 'library_id', not both",
            )
        if not file and not library_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Must provide either 'file' to upload or 'library_id' to copy from Library",
            )

        # 1. Get chapter and validate ownership
        chapter = chapter_manager.chapters_collection.find_one({"_id": chapter_id})
        if not chapter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found"
            )

        # Check book ownership
        book = db.online_books.find_one(
            {"book_id": chapter["book_id"], "user_id": user_id}
        )
        if not book:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied - not book owner",
            )

        # 2. Get image content (from file upload OR library)
        if file:
            # Method 1: Upload file
            logger.info(f"   📤 Uploading file: {file.filename}")

            if not file.content_type or not file.content_type.startswith("image/"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File must be an image. Got: {file.content_type}",
                )

            content = await file.read()
            source_name = file.filename

        else:
            # Method 2: Copy from Library
            logger.info(f"   📥 Copying from Library: {library_id}")

            # Get library file
            library_file = db.library_files.find_one(
                {"library_id": library_id, "user_id": user_id}
            )
            if not library_file:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Library file not found or access denied",
                )

            # Get file URL (might be presigned or r2_key)
            file_url = library_file.get("file_url")
            r2_key = library_file.get("r2_key")

            if not file_url and not r2_key:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Library file has no URL or R2 key",
                )

            # If has r2_key, regenerate presigned URL
            if r2_key:
                s3_client = r2_service.s3_client
                file_url = s3_client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": r2_service.bucket_name, "Key": r2_key},
                    ExpiresIn=3600,
                )
                logger.info(f"   🔑 Regenerated presigned URL from r2_key")

            # Download image from Library
            try:
                response = requests.get(file_url, timeout=30)
                response.raise_for_status()
                content = response.content
                source_name = library_file.get("filename", "library_image")
                logger.info(
                    f"   ✅ Downloaded {len(content) / 1024:.1f}KB from Library"
                )
            except Exception as e:
                logger.error(f"   ❌ Failed to download from Library: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to download image from Library: {str(e)}",
                )

        # Check size
        if len(content) > 10 * 1024 * 1024:  # 10 MB
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size {len(content) / 1024 / 1024:.1f}MB exceeds 10MB limit",
            )

        # 3. Process image
        image = Image.open(io.BytesIO(content))
        original_width, original_height = image.size

        # Convert to RGB
        if image.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", image.size, (255, 255, 255))
            if image.mode == "P":
                image = image.convert("RGBA")
            background.paste(
                image,
                mask=(image.split()[-1] if image.mode in ("RGBA", "LA") else None),
            )
            image = background
        elif image.mode != "RGB":
            image = image.convert("RGB")

        # Compress to JPEG
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=90, optimize=True)
        buffer.seek(0)

        # 4. Upload to R2: studyhub/chapters/{chapter_id}/elements/{uuid}.jpg
        element_id = uuid.uuid4().hex
        object_key = f"studyhub/chapters/{chapter_id}/elements/{element_id}.jpg"

        s3_client = r2_service.s3_client
        s3_client.upload_fileobj(
            buffer,
            r2_service.bucket_name,
            object_key,
            ExtraArgs={"ContentType": "image/jpeg"},
        )

        # 5. Generate public CDN URL (permanent)
        cdn_url = f"{r2_service.public_url}/{object_key}"

        logger.info(f"✅ [ELEMENT_IMAGE] Uploaded to public CDN: {cdn_url}")
        logger.info(f"   Source: {source_name}, Size: {len(content) / 1024:.1f}KB")

        return {
            "success": True,
            "url": cdn_url,
            "width": original_width,
            "height": original_height,
            "file_size": len(content),
            "file_name": source_name,
            "message": "Element image uploaded successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to process element image: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process element image: {str(e)}",
        )


@router.post(
    "/{book_id}/chapters/from-images",
    response_model=Dict[str, Any],
    status_code=status.HTTP_201_CREATED,
    summary="Create chapter from uploaded images",
    description="""
    Create a new chapter from previously uploaded images.

    **Simplified Flow:**
    1. Upload images via POST /upload-images (get chapter_id)
    2. Call this endpoint with chapter_id + metadata
    3. Chapter created immediately (no re-upload)

    **Features:**
    - Images already in permanent storage
    - No download/re-upload needed
    - Variable dimensions (manga/comics/photo books)
    - Optional manga metadata
    - Element overlays support

    **Content Mode:** `image_pages`

    **Required:** Owner access to the book
    """,
)
async def create_chapter_from_images_endpoint(
    book_id: str,
    request: ChapterCreateFromUploadedImages,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Create chapter from uploaded images (simplified - no file operations)"""
    try:
        user_id = current_user["uid"]

        logger.info(f"🎨 [API] Creating chapter from uploaded images")
        logger.info(f"   Book: {book_id}, User: {user_id}")
        logger.info(f"   Chapter ID: {request.chapter_id}, Title: {request.title}")

        # Create chapter from uploaded images
        chapter = await chapter_manager.create_chapter_from_uploaded_images(
            book_id=book_id,
            user_id=user_id,
            chapter_id=request.chapter_id,
            title=request.title,
            slug=request.slug,
            order_index=request.order_index,
            parent_id=request.parent_id,
            is_published=request.is_published,
            is_preview_free=request.is_preview_free,
            manga_metadata=(
                request.manga_metadata.dict() if request.manga_metadata else None
            ),
        )

        logger.info(
            f"✅ [API] Created chapter {chapter['_id']}: {chapter['total_pages']} pages"
        )

        return {
            "success": True,
            "chapter": chapter,
            "total_pages": chapter["total_pages"],
            "message": f"Chapter created with {chapter['total_pages']} pages",
        }

    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        logger.error(f"❌ Validation error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Failed to create image chapter: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create image chapter: {str(e)}",
        )


@router.post(
    "/{book_id}/chapters/from-zip",
    response_model=Dict[str, Any],
    status_code=status.HTTP_201_CREATED,
    summary="Create chapter from manga ZIP file",
    description="""
    Create a new chapter from a manga ZIP archive.

    **Features:**
    - Extract all images from ZIP
    - Auto-sort files numerically (page-01.jpg, page-02.jpg, ...)
    - Support for manga metadata (reading direction, artist, genre)
    - Reference to original ZIP file preserved

    **Process:**
    1. Downloads ZIP from StudyHub files
    2. Extracts images (JPG, PNG, WEBP, GIF)
    3. Sorts pages numerically
    4. Uploads to R2 as chapter backgrounds
    5. Creates chapter with pages array

    **Content Mode:** `image_pages`

    **Required:** Owner access to the book and ZIP file
    """,
)
async def create_chapter_from_zip_endpoint(
    book_id: str,
    zip_file_id: str,
    title: str,
    slug: Optional[str] = None,
    order_index: int = 0,
    parent_id: Optional[str] = None,
    is_published: bool = True,
    is_preview_free: bool = False,
    reading_direction: Optional[str] = "rtl",  # Right-to-left for manga
    is_colored: Optional[bool] = False,
    artist: Optional[str] = None,
    genre: Optional[str] = None,
    auto_sort: bool = True,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Create chapter from manga ZIP file"""
    try:
        user_id = current_user["uid"]

        logger.info(f"📦 [API] Creating chapter from ZIP in book {book_id}")
        logger.info(f"   User: {user_id}, Title: {title}, ZIP: {zip_file_id}")

        # Build manga metadata
        manga_metadata = None
        if reading_direction or is_colored or artist or genre:
            manga_metadata = {}
            if reading_direction:
                manga_metadata["reading_direction"] = reading_direction
            if is_colored is not None:
                manga_metadata["is_colored"] = is_colored
            if artist:
                manga_metadata["artist"] = artist
            if genre:
                manga_metadata["genre"] = genre

        # Create chapter from ZIP
        chapter = await chapter_manager.create_chapter_from_zip(
            book_id=book_id,
            user_id=user_id,
            zip_file_id=zip_file_id,
            title=title,
            slug=slug,
            order_index=order_index,
            parent_id=parent_id,
            is_published=is_published,
            is_preview_free=is_preview_free,
            manga_metadata=manga_metadata,
            auto_sort=auto_sort,
        )

        logger.info(
            f"✅ [API] Created chapter from ZIP {chapter['_id']}: "
            f"{chapter['total_pages']} pages"
        )

        return {
            "success": True,
            "chapter": chapter,
            "total_pages": chapter["total_pages"],
            "source_file_id": zip_file_id,
            "message": f"Chapter created from ZIP with {chapter['total_pages']} pages",
        }

    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        logger.error(f"❌ Validation error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Failed to create chapter from ZIP: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create chapter from ZIP: {str(e)}",
        )


@router.put(
    "/chapters/{chapter_id}/manga-metadata",
    response_model=Dict[str, Any],
    summary="Update manga metadata",
    description="""
    Update manga-specific metadata for an image_pages chapter.

    **Fields:**
    - `reading_direction`: "ltr" (left-to-right) or "rtl" (right-to-left, default for manga)
    - `is_colored`: true for colored manga, false for black & white
    - `artist`: Artist/illustrator name
    - `genre`: Genre tags (action, romance, comedy, etc.)

    **Required:** Owner access and content_mode = "image_pages"
    """,
)
async def update_manga_metadata_endpoint(
    chapter_id: str,
    reading_direction: Optional[str] = None,
    is_colored: Optional[bool] = None,
    artist: Optional[str] = None,
    genre: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Update manga metadata for image_pages chapter"""
    try:
        user_id = current_user["uid"]

        logger.info(f"📖 [API] Updating manga metadata for chapter {chapter_id}")

        # Build manga metadata
        manga_metadata = {}
        if reading_direction:
            if reading_direction not in ["ltr", "rtl"]:
                raise ValueError("reading_direction must be 'ltr' or 'rtl'")
            manga_metadata["reading_direction"] = reading_direction
        if is_colored is not None:
            manga_metadata["is_colored"] = is_colored
        if artist:
            manga_metadata["artist"] = artist
        if genre:
            manga_metadata["genre"] = genre

        if not manga_metadata:
            raise ValueError("No manga metadata provided")

        # Update metadata
        updated_chapter = await chapter_manager.update_manga_metadata(
            chapter_id=chapter_id,
            user_id=user_id,
            manga_metadata=manga_metadata,
        )

        logger.info(f"✅ [API] Updated manga metadata for chapter {chapter_id}")

        return {
            "success": True,
            "chapter": updated_chapter,
            "manga_metadata": updated_chapter.get("manga_metadata", {}),
            "message": "Manga metadata updated successfully",
        }

    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        logger.error(f"❌ Validation error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Failed to update manga metadata: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update manga metadata: {str(e)}",
        )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE MANAGEMENT: Delete & Reorder
# ══════════════════════════════════════════════════════════════════════════════


@router.delete(
    "/chapters/{chapter_id}/pages/{page_number}",
    status_code=status.HTTP_200_OK,
    summary="Delete a page from chapter",
    description="""
    Delete a specific page from chapter (for pdf_pages or image_pages mode).

    **Process:**
    1. Removes page from pages array
    2. Renumbers remaining pages sequentially
    3. Updates total_pages count
    4. Deletes page image from R2 storage

    **Note:** Cannot undo this operation

    **Required:** Owner access to the book
    """,
)
async def delete_chapter_page(
    chapter_id: str,
    page_number: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Delete a page from chapter"""
    try:
        user_id = current_user["uid"]

        logger.info(
            f"🗑️ [DELETE_PAGE] Deleting page {page_number} from chapter {chapter_id}"
        )
        logger.info(f"   User: {user_id}")

        # Get chapter
        chapter = chapter_manager.chapters_collection.find_one({"_id": chapter_id})
        if not chapter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found"
            )

        # Check ownership (online_books collection)
        book = db.online_books.find_one(
            {"book_id": chapter["book_id"], "user_id": user_id}
        )
        if not book:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied - not book owner",
            )

        # Validate content mode
        if chapter.get("content_mode") not in ["pdf_pages", "image_pages"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only delete pages from pdf_pages or image_pages chapters",
            )

        # Get pages
        pages = chapter.get("pages", [])
        if not pages:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Chapter has no pages"
            )

        # Find page to delete
        page_to_delete = None
        for page in pages:
            if page.get("page_number") == page_number:
                page_to_delete = page
                break

        if not page_to_delete:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Page {page_number} not found",
            )

        # Delete image from R2
        try:
            background_url = page_to_delete.get("background_url", "")
            if background_url:
                # Extract R2 key from URL
                cdn_base = f"{r2_service.public_url}/"
                if background_url.startswith(cdn_base):
                    r2_key = background_url[len(cdn_base) :]
                    r2_service.s3_client.delete_object(
                        Bucket=r2_service.bucket_name, Key=r2_key
                    )
                    logger.info(f"   🗑️ Deleted image from R2: {r2_key}")
        except Exception as e:
            logger.warning(f"⚠️ Could not delete image from R2: {e}")

        # Remove page from array
        pages.remove(page_to_delete)

        # Renumber remaining pages
        for idx, page in enumerate(pages, 1):
            page["page_number"] = idx

        # Update chapter
        result = chapter_manager.chapters_collection.update_one(
            {"_id": chapter_id},
            {
                "$set": {
                    "pages": pages,
                    "total_pages": len(pages),
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        if result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update chapter",
            )

        # Update book timestamp
        if chapter_manager.book_manager:
            chapter_manager.book_manager.touch_book(chapter["book_id"])

        logger.info(
            f"✅ [DELETE_PAGE] Deleted page {page_number}, "
            f"remaining pages: {len(pages)}"
        )

        return {
            "success": True,
            "deleted_page": page_number,
            "total_pages": len(pages),
            "message": f"Page {page_number} deleted successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete page: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete page: {str(e)}",
        )


@router.put(
    "/chapters/{chapter_id}/pages/reorder",
    status_code=status.HTTP_200_OK,
    summary="Reorder pages in chapter",
    description="""
    Reorder pages in chapter - supports 2 request formats:

    **Format 1: page_order (array)**
    ```json
    {
      "page_order": [3, 1, 2, 4]
    }
    ```
    Result: Page 3 → position 1, Page 1 → position 2, etc.

    **Format 2: page_mapping (dict)**
    ```json
    {
      "page_mapping": {"1": 2, "2": 1, "3": 3, "4": 4}
    }
    ```
    Result: Page 1 → position 2, Page 2 → position 1, etc.

    **Validation:**
    - Must provide EITHER page_order OR page_mapping (not both)
    - All page numbers must be unique
    - All page numbers must be valid (1 to total_pages)

    **Required:** Owner access to the book
    """,
)
async def reorder_chapter_pages(
    chapter_id: str,
    request: PageReorderRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Reorder pages in chapter"""
    try:
        user_id = current_user["uid"]

        logger.info(f"🔄 [REORDER_PAGES] Reordering pages in chapter {chapter_id}")
        logger.info(f"   User: {user_id}")

        # Convert page_mapping to page_order if provided
        if request.page_mapping:
            # Convert {"1": 2, "2": 1, ...} to [2, 1, ...]
            page_order = []
            mapping_dict = {int(k): v for k, v in request.page_mapping.items()}
            for i in range(1, len(mapping_dict) + 1):
                if i not in mapping_dict:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"page_mapping missing page {i}",
                    )
                page_order.append(mapping_dict[i])
            logger.info(f"   Converted page_mapping to page_order: {page_order}")
        else:
            page_order = request.page_order
            logger.info(f"   Using page_order: {page_order}")

        # Type narrowing check (should never be None due to PageReorderRequest validation)
        if page_order is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="page_order is required",
            )

        # Get chapter
        chapter = chapter_manager.chapters_collection.find_one({"_id": chapter_id})
        if not chapter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found"
            )

        # Check ownership (online_books collection)
        book = db.online_books.find_one(
            {"book_id": chapter["book_id"], "user_id": user_id}
        )
        if not book:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied - not book owner",
            )

        # Validate content mode
        if chapter.get("content_mode") not in ["pdf_pages", "image_pages"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only reorder pages in pdf_pages or image_pages chapters",
            )

        # Get pages
        pages = chapter.get("pages", [])
        total_pages = len(pages)

        if not pages:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Chapter has no pages"
            )

        # Validate page_order
        if len(page_order) != total_pages:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"page_order length ({len(page_order)}) must match total_pages ({total_pages})",
            )

        # Check all numbers are unique
        if len(set(page_order)) != len(page_order):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="page_order contains duplicate numbers",
            )

        # Check all numbers are valid
        valid_numbers = set(range(1, total_pages + 1))
        provided_numbers = set(page_order)
        if provided_numbers != valid_numbers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"page_order must contain all numbers from 1 to {total_pages}",
            )

        # Create page lookup by original page number
        page_lookup = {page["page_number"]: page for page in pages}

        # Reorder pages
        reordered_pages = []
        for new_position, old_page_number in enumerate(page_order, 1):
            page = page_lookup[old_page_number].copy()
            page["page_number"] = new_position  # Assign new page number
            reordered_pages.append(page)

        # Update chapter
        result = chapter_manager.chapters_collection.update_one(
            {"_id": chapter_id},
            {"$set": {"pages": reordered_pages, "updated_at": datetime.utcnow()}},
        )

        if result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update chapter",
            )

        # Update book timestamp
        if chapter_manager.book_manager:
            chapter_manager.book_manager.touch_book(chapter["book_id"])

        logger.info(f"✅ [REORDER_PAGES] Reordered {total_pages} pages successfully")

        return {
            "success": True,
            "total_pages": total_pages,
            "new_order": page_order,
            "message": "Pages reordered successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to reorder pages: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reorder pages: {str(e)}",
        )
