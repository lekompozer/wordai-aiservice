"""
Book Advanced Routes - Translation & Duplication
Advanced features for book and chapter management:
- Translate Chapter: Dịch chapter sang ngôn ngữ khác và auto generate chapter mới
- Duplicate Book: Copy toàn bộ book với chapters
- Duplicate Chapter: Copy chapter trong cùng book
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import logging
import uuid

# Authentication
from src.middleware.firebase_auth import get_current_user

# Services
from src.services.book_chapter_manager import GuideBookBookChapterManager
from src.services.ai_chat_service import ai_chat_service, AIProvider
from src.services.points_service import get_points_service
from src.services.r2_storage_service import get_r2_service
from config.config import get_mongodb

# Models
from src.api.ai_editor_routes import BilingualStyle

logger = logging.getLogger("chatbot")
router = APIRouter(prefix="/api/v1/books", tags=["Book Advanced"])

# MongoDB
db = get_mongodb()
chapter_manager = GuideBookBookChapterManager(db)
# ai_chat_service imported from src.services.ai_chat_service


# ============ MODELS ============


class TranslateChapterRequest(BaseModel):
    """Request to translate chapter and create new chapter"""

    source_language: str = Field(..., description="Source language (e.g., 'English')")
    target_language: str = Field(
        ..., description="Target language (e.g., 'Vietnamese')"
    )
    create_new_chapter: bool = Field(
        True, description="Create new chapter with translated content (default: true)"
    )
    new_chapter_title_suffix: str = Field(
        default=" (Translated)",
        description="Suffix for new chapter title (e.g., ' (VI)', ' (EN)')",
    )


class TranslateChapterResponse(BaseModel):
    """Response after translating chapter"""

    success: bool
    original_chapter_id: str
    new_chapter_id: Optional[str] = Field(
        None, description="ID of newly created chapter (if create_new_chapter=true)"
    )
    new_chapter_title: Optional[str] = None
    new_chapter_slug: Optional[str] = None
    translated_html: str = Field(..., description="Translated HTML content")
    message: str


class DuplicateBookRequest(BaseModel):
    """Request to duplicate book"""

    new_title_suffix: str = Field(
        default="_copy", description="Suffix for new book title"
    )
    copy_chapters: bool = Field(True, description="Copy all chapters (default: true)")
    visibility: Optional[str] = Field(
        "private", description="Visibility of duplicated book"
    )


class DuplicateBookResponse(BaseModel):
    """Response after duplicating book"""

    success: bool
    original_book_id: str
    new_book_id: str
    new_book_title: str
    new_book_slug: str
    chapters_copied: int = Field(0, description="Number of chapters copied")
    message: str


class DuplicateChapterRequest(BaseModel):
    """Request to duplicate chapter"""

    new_title_suffix: str = Field(
        default="_copy", description="Suffix for new chapter title"
    )
    copy_to_book_id: Optional[str] = Field(
        None,
        description="Target book ID (if None, copy to same book)",
    )


class DuplicateChapterResponse(BaseModel):
    """Response after duplicating chapter"""

    success: bool
    original_chapter_id: str
    new_chapter_id: str
    new_chapter_title: str
    new_chapter_slug: str
    book_id: str
    message: str


# ============ HELPER FUNCTIONS ============


def generate_unique_slug(base_slug: str, book_id: str, attempt: int = 0) -> str:
    """Generate unique slug within book"""
    if attempt == 0:
        test_slug = base_slug
    else:
        test_slug = f"{base_slug}-{attempt}"

    # Check if slug exists in this book
    existing = db.book_chapters.find_one({"book_id": book_id, "slug": test_slug})

    if existing:
        return generate_unique_slug(base_slug, book_id, attempt + 1)
    return test_slug


def generate_unique_title(base_title: str, suffix: str, book_id: str) -> str:
    """Generate unique title with _copy, _copy_2, etc."""
    attempt = 0
    while True:
        if attempt == 0:
            test_title = f"{base_title}{suffix}"
        else:
            test_title = f"{base_title}{suffix}_{attempt + 1}"

        # Check if title exists in this book
        existing = db.book_chapters.find_one({"book_id": book_id, "title": test_title})

        if not existing:
            return test_title
        attempt += 1


def slugify(text: str) -> str:
    """Convert Vietnamese text to URL-friendly slug (without diacritics)"""
    import re

    # Vietnamese character mapping (with diacritics -> without diacritics)
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

    # Replace Vietnamese characters
    for vn_char, en_char in vietnamese_map.items():
        text = text.replace(vn_char, en_char)

    # Convert to lowercase
    text = text.lower()

    # Remove special characters, keep only alphanumeric and hyphens
    text = re.sub(r"[^\w\s-]", "", text)

    # Replace multiple spaces/hyphens with single hyphen
    text = re.sub(r"[-\s]+", "-", text)

    # Strip leading/trailing hyphens
    text = text.strip("-")

    return text[:100]  # Limit length


# ============ ENDPOINTS ============


@router.post(
    "/{book_id}/chapters/{chapter_id}/translate",
    response_model=TranslateChapterResponse,
    status_code=status.HTTP_200_OK,
)
async def translate_chapter(
    book_id: str,
    chapter_id: str,
    request: TranslateChapterRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Translate chapter to another language and optionally create new chapter

    **Cost: 2 points** (AI translation operation)

    **Workflow:**
    1. Verify user owns the book
    2. Check sufficient points (2 points)
    3. Get chapter content
    4. AI translates content to target language
    5. Create new chapter with translated content (if create_new_chapter=true)
    6. Deduct points

    **Returns:**
    - 200: Translation successful
    - 403: Not owner or insufficient points
    - 404: Book or chapter not found
    - 500: Translation failed
    """
    try:
        user_id = current_user["uid"]

        logger.info(
            f"🌍 Translate chapter request: {chapter_id} "
            f"({request.source_language} → {request.target_language})"
        )

        # 1. Verify ownership
        book = db.online_books.find_one({"book_id": book_id, "user_id": user_id})
        if not book:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Book not found or you don't have permission",
            )

        # 2. Get chapter
        chapter = db.book_chapters.find_one(
            {"chapter_id": chapter_id, "book_id": book_id}
        )
        if not chapter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Chapter {chapter_id} not found in book {book_id}",
            )

        # 3. Check points (2 points for translation)
        points_service = get_points_service()
        points_needed = 2

        check_result = await points_service.check_sufficient_points(
            user_id=user_id, points_needed=points_needed, service="ai_translation"
        )

        if not check_result["has_points"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "insufficient_points",
                    "message": f"Không đủ points để dịch chapter. Cần: {points_needed}, Còn: {check_result['points_available']}",
                    "points_needed": points_needed,
                    "points_available": check_result["points_available"],
                },
            )

        # 4. Get chapter content
        chapter_with_content = chapter_manager.get_chapter_with_content(chapter_id)
        if not chapter_with_content:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chapter content not found",
            )

        content_html = chapter_with_content.get("content_html", "")
        if not content_html:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chapter has no content to translate",
            )

        # 5. AI Translation
        prompt = f"""You are a professional translator. Translate the following HTML content from {request.source_language} to {request.target_language}.

**CRITICAL RULES:**
1. ONLY return the translated HTML content
2. DO NOT translate HTML tags, attributes, CSS classes, or inline styles
3. Preserve the exact HTML structure
4. Translate ONLY the text content inside tags
5. Keep all formatting, links, and images intact

**Original HTML:**
{content_html}

**Return only the translated HTML (no explanations, no markdown):**"""

        messages = [
            {
                "role": "system",
                "content": f"You are a professional translator specializing in {request.target_language}. You only return clean translated HTML.",
            },
            {"role": "user", "content": prompt},
        ]

        # Call AI (Gemini Pro for better quality)
        translated_html = await ai_chat_service.chat(
            provider=AIProvider.GEMINI_PRO,
            messages=messages,
            temperature=0.3,
            max_tokens=16000,
        )

        translated_html = translated_html.strip()

        logger.info(
            f"✅ Translation completed: {len(content_html)} → {len(translated_html)} chars"
        )

        # 6. Create new chapter (if requested)
        new_chapter_id = None
        new_chapter_title = None
        new_chapter_slug = None

        if request.create_new_chapter:
            # Generate new title
            new_chapter_title = generate_unique_title(
                chapter["title"], request.new_chapter_title_suffix, book_id
            )

            # Generate slug from new title
            base_slug = slugify(new_chapter_title)
            new_chapter_slug = generate_unique_slug(base_slug, book_id)

            new_chapter_id = f"chapter_{uuid.uuid4().hex[:12]}"
            now = datetime.utcnow()

            # Create new chapter document
            new_chapter = {
                "chapter_id": new_chapter_id,
                "book_id": book_id,
                "parent_id": chapter.get("parent_id"),
                "title": new_chapter_title,
                "slug": new_chapter_slug,
                "order_index": chapter.get("order_index", 0)
                + 1,  # Place after original
                "depth": chapter.get("depth", 0),
                "content_source": "inline",
                "document_id": None,
                "content_html": translated_html,
                "content_json": None,
                "is_published": True,
                "is_preview_free": chapter.get("is_preview_free", False),
                "created_at": now,
                "updated_at": now,
            }

            db.book_chapters.insert_one(new_chapter)

            logger.info(
                f"✅ Created new translated chapter: {new_chapter_id} "
                f"(title: '{new_chapter_title}')"
            )

        # 7. Deduct points
        try:
            await points_service.deduct_points(
                user_id=user_id,
                amount=points_needed,
                service="ai_translation",
                resource_id=chapter_id,
                description=f"AI Translation: {request.source_language} → {request.target_language}",
            )
            logger.info(f"💸 Deducted {points_needed} points for translation")
        except Exception as points_error:
            logger.error(f"❌ Error deducting points: {points_error}")

        # 8. Return response
        message = (
            f"Chapter translated and new chapter created: {new_chapter_title}"
            if request.create_new_chapter
            else "Chapter translated successfully"
        )

        return TranslateChapterResponse(
            success=True,
            original_chapter_id=chapter_id,
            new_chapter_id=new_chapter_id,
            new_chapter_title=new_chapter_title,
            new_chapter_slug=new_chapter_slug,
            translated_html=translated_html,
            message=message,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Translation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Translation failed: {str(e)}",
        )


@router.post(
    "/{book_id}/duplicate",
    response_model=DuplicateBookResponse,
    status_code=status.HTTP_201_CREATED,
)
async def duplicate_book(
    book_id: str,
    request: DuplicateBookRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Duplicate entire book with all chapters

    **Free operation** (no points required)

    **Workflow:**
    1. Verify user owns the book
    2. Create new book with title_copy suffix
    3. Copy all chapters with new IDs and slugs
    4. Return new book info

    **Naming Logic:**
    - First copy: "Original Title_copy"
    - Second copy: "Original Title_copy_2"
    - Third copy: "Original Title_copy_3"
    - etc.

    **Returns:**
    - 201: Book duplicated successfully
    - 403: Not owner
    - 404: Book not found
    - 500: Duplication failed
    """
    try:
        user_id = current_user["uid"]

        logger.info(f"📚 Duplicate book request: {book_id}")

        # 1. Verify ownership
        book = db.online_books.find_one({"book_id": book_id, "user_id": user_id})
        if not book:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Book not found or you don't have permission",
            )

        # 2. Generate unique book title
        base_title = book["title"]
        attempt = 0
        while True:
            if attempt == 0:
                new_title = f"{base_title}{request.new_title_suffix}"
            else:
                new_title = f"{base_title}{request.new_title_suffix}_{attempt + 1}"

            # Check if title exists for this user
            existing = db.online_books.find_one(
                {"user_id": user_id, "title": new_title}
            )
            if not existing:
                break
            attempt += 1

        # 3. Generate unique slug
        base_slug = slugify(new_title)
        slug_attempt = 0
        while True:
            if slug_attempt == 0:
                new_slug = base_slug
            else:
                new_slug = f"{base_slug}-{slug_attempt}"

            existing_slug = db.online_books.find_one({"slug": new_slug})
            if not existing_slug:
                break
            slug_attempt += 1

        # 4. Create new book
        new_book_id = f"book_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow()

        new_book = {
            "book_id": new_book_id,
            "user_id": user_id,
            "title": new_title,
            "slug": new_slug,
            "description": book.get("description"),
            "visibility": request.visibility,
            "is_published": False,  # Unpublished by default
            "logo_url": book.get("logo_url"),
            "cover_image_url": book.get("cover_image_url"),
            "primary_color": book.get("primary_color", "#4F46E5"),
            "icon": book.get("icon"),
            "color": book.get("color"),
            "access_config": book.get("access_config"),
            "community_config": {
                "is_public": False,  # Not published to community
                "category": book.get("community_config", {}).get("category"),
                "tags": book.get("community_config", {}).get("tags", []),
                "total_views": 0,
                "total_downloads": 0,
                "total_purchases": 0,
            },
            "created_at": now,
            "updated_at": now,
        }

        db.online_books.insert_one(new_book)
        logger.info(f"✅ Created duplicated book: {new_book_id} (title: '{new_title}')")

        chapters_copied = 0

        # 5. Copy chapters (if requested)
        if request.copy_chapters:
            chapters = list(
                db.book_chapters.find({"book_id": book_id}).sort("order_index", 1)
            )

            for chapter in chapters:
                # Generate new chapter title
                new_chapter_title = generate_unique_title(
                    chapter["title"], request.new_title_suffix, new_book_id
                )

                # Generate new slug
                base_chapter_slug = slugify(new_chapter_title)
                new_chapter_slug = generate_unique_slug(base_chapter_slug, new_book_id)

                new_chapter_id = f"chapter_{uuid.uuid4().hex[:12]}"

                new_chapter = {
                    "chapter_id": new_chapter_id,
                    "book_id": new_book_id,
                    "parent_id": chapter.get("parent_id"),  # Keep parent structure
                    "title": new_chapter_title,
                    "slug": new_chapter_slug,
                    "order_index": chapter.get("order_index", 0),
                    "depth": chapter.get("depth", 0),
                    "content_source": chapter.get("content_source", "inline"),
                    "document_id": chapter.get("document_id"),  # Keep reference
                    "content_html": chapter.get("content_html"),
                    "content_json": chapter.get("content_json"),
                    "is_published": chapter.get("is_published", True),
                    "is_preview_free": chapter.get("is_preview_free", False),
                    "created_at": now,
                    "updated_at": now,
                }

                db.book_chapters.insert_one(new_chapter)
                chapters_copied += 1

            logger.info(f"✅ Copied {chapters_copied} chapters to new book")

        return DuplicateBookResponse(
            success=True,
            original_book_id=book_id,
            new_book_id=new_book_id,
            new_book_title=new_title,
            new_book_slug=new_slug,
            chapters_copied=chapters_copied,
            message=f"Book duplicated successfully with {chapters_copied} chapters",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Book duplication failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Book duplication failed: {str(e)}",
        )


@router.post(
    "/{book_id}/chapters/{chapter_id}/duplicate",
    response_model=DuplicateChapterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def duplicate_chapter(
    book_id: str,
    chapter_id: str,
    request: DuplicateChapterRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Duplicate chapter within same book or to another book

    **Free operation** (no points required)

    **Workflow:**
    1. Verify user owns the source book (and target book if different)
    2. Get chapter content
    3. Create new chapter with title_copy suffix
    4. Generate unique slug within target book
    5. Return new chapter info

    **Naming Logic:**
    - First copy: "Original Title_copy"
    - Second copy: "Original Title_copy_2"
    - etc.

    **Slug Uniqueness:**
    - Slug only needs to be unique within the target book
    - Same slug can exist in different books

    **Returns:**
    - 201: Chapter duplicated successfully
    - 403: Not owner
    - 404: Book or chapter not found
    - 500: Duplication failed
    """
    try:
        user_id = current_user["uid"]

        logger.info(f"📄 Duplicate chapter request: {chapter_id}")

        # Determine target book
        target_book_id = request.copy_to_book_id or book_id

        # 1. Verify ownership of source book
        source_book = db.online_books.find_one({"book_id": book_id, "user_id": user_id})
        if not source_book:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Source book not found or you don't have permission",
            )

        # 2. Verify ownership of target book (if different)
        if target_book_id != book_id:
            target_book = db.online_books.find_one(
                {"book_id": target_book_id, "user_id": user_id}
            )
            if not target_book:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Target book not found or you don't have permission",
                )

        # 3. Get source chapter
        chapter = db.book_chapters.find_one(
            {"chapter_id": chapter_id, "book_id": book_id}
        )
        if not chapter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Chapter {chapter_id} not found in book {book_id}",
            )

        # 4. Get chapter content (if inline)
        chapter_with_content = chapter_manager.get_chapter_with_content(chapter_id)
        content_html = chapter_with_content.get("content_html", "")

        # 5. Generate unique title in target book
        new_chapter_title = generate_unique_title(
            chapter["title"], request.new_title_suffix, target_book_id
        )

        # 6. Generate unique slug in target book
        base_slug = slugify(new_chapter_title)
        new_chapter_slug = generate_unique_slug(base_slug, target_book_id)

        # 7. Create new chapter
        new_chapter_id = f"chapter_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow()

        new_chapter = {
            "chapter_id": new_chapter_id,
            "book_id": target_book_id,
            "parent_id": (
                chapter.get("parent_id") if target_book_id == book_id else None
            ),  # Reset parent if different book
            "title": new_chapter_title,
            "slug": new_chapter_slug,
            "order_index": chapter.get("order_index", 0) + 1,  # Place after original
            "depth": (
                chapter.get("depth", 0) if target_book_id == book_id else 0
            ),  # Reset depth if different book
            "content_source": "inline",  # Always inline for duplicated chapters
            "document_id": None,  # Don't link to original document
            "content_html": content_html,
            "content_json": chapter.get("content_json"),
            "is_published": True,
            "is_preview_free": chapter.get("is_preview_free", False),
            "created_at": now,
            "updated_at": now,
        }

        db.book_chapters.insert_one(new_chapter)

        logger.info(
            f"✅ Duplicated chapter: {new_chapter_id} "
            f"(title: '{new_chapter_title}', target book: {target_book_id})"
        )

        return DuplicateChapterResponse(
            success=True,
            original_chapter_id=chapter_id,
            new_chapter_id=new_chapter_id,
            new_chapter_title=new_chapter_title,
            new_chapter_slug=new_chapter_slug,
            book_id=target_book_id,
            message=f"Chapter duplicated successfully to book {target_book_id}",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Chapter duplication failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chapter duplication failed: {str(e)}",
        )


# ============ AUTHOR AVATAR UPLOAD (New Author Creation) ============


class AuthorAvatarUploadRequest(BaseModel):
    """Request model for avatar upload presigned URL"""

    filename: str = Field(..., description="Avatar filename (e.g., avatar.jpg)")
    content_type: str = Field(..., description="MIME type (e.g., image/jpeg)")


@router.post(
    "/authors/avatar/presigned-url",
    summary="Generate presigned URL for avatar upload (before creating author)",
)
async def get_new_author_avatar_presigned_url(
    request: AuthorAvatarUploadRequest,
    user: dict = Depends(get_current_user),
):
    """
    **Generate presigned URL for author avatar upload (NEW AUTHOR)**

    Use this endpoint when creating a new author (before author_id exists).
    For existing authors, use `/api/v1/authors/{author_id}/avatar/presigned-url` instead.

    **Endpoint:** `POST /api/v1/books/authors/avatar/presigned-url`

    **Supported Image Types:**
    - JPEG (image/jpeg)
    - PNG (image/png)
    - WebP (image/webp)
    - AVIF (image/avif)

    **Flow:**
    1. Frontend calls this endpoint with filename and content_type
    2. Backend generates presigned URL (valid for 5 minutes)
    3. Frontend uploads file directly to presigned URL using PUT request
    4. Frontend uses returned file_url in avatar_url field when creating author

    **Returns:**
    - `presigned_url`: URL for uploading file (use PUT request)
    - `file_url`: Public CDN URL to use in create author request
    - `expires_in`: Presigned URL expiration time in seconds (300 = 5 minutes)
    """
    user_id = user["uid"]

    filename = request.filename
    content_type = request.content_type

    logger.info(
        f"📸 Generating presigned URL for new author avatar: {filename} - User: {user_id}"
    )

    try:
        # Validate content type
        allowed_types = ["image/jpeg", "image/png", "image/webp", "image/avif"]
        if content_type not in allowed_types:
            logger.warning(
                f"❌ Invalid content type '{content_type}' for user {user_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid content type. Allowed: {', '.join(allowed_types)}",
            )

        # Validate filename extension
        valid_extensions = [".jpg", ".jpeg", ".png", ".webp", ".avif"]
        if not any(filename.lower().endswith(ext) for ext in valid_extensions):
            logger.warning(
                f"❌ Invalid filename extension '{filename}' for user {user_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid filename. Allowed: {', '.join(valid_extensions)}",
            )

        # Get R2 service
        r2_service = get_r2_service()

        # Generate presigned URL
        result = r2_service.generate_presigned_upload_url(
            filename=filename,
            content_type=content_type,
            folder="author-avatars",
        )

        logger.info(
            f"✅ Generated presigned URL for new author avatar: {result['file_url']} - User: {user_id}"
        )

        return {
            "success": True,
            "presigned_url": result["presigned_url"],
            "file_url": result["file_url"],
            "expires_in": result["expires_in"],
        }

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"❌ R2 configuration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"R2 service not configured: {str(e)}",
        )
    except Exception as e:
        logger.error(f"❌ Failed to generate presigned URL: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate presigned URL: {str(e)}",
        )
