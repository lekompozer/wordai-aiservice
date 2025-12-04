"""
Book Translation Routes
API endpoints for multi-language support in books and chapters
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
import logging

# Authentication
from src.middleware.firebase_auth import get_current_user

# Services
from src.services.book_translation_service import BookTranslationService
from src.services.points_service import get_points_service

# Database
from src.database.db_manager import DBManager

# Models
from src.models.book_translation_models import (
    TranslateBookRequest,
    TranslateBookResponse,
    TranslateChapterRequest,
    TranslateChapterResponse,
    TranslatedFields,
    LanguageListResponse,
    LanguageInfo,
    UpdateBackgroundForLanguageRequest,
    UpdateBackgroundForLanguageResponse,
    DeleteTranslationResponse,
    SUPPORTED_LANGUAGES,
)

logger = logging.getLogger("chatbot")
router = APIRouter(prefix="/api/v1/books", tags=["Book Translation"])

# MongoDB
db_manager = DBManager()
db = db_manager.db


def get_translation_service() -> BookTranslationService:
    """Get translation service instance"""
    return BookTranslationService(db)


# ==================== ENDPOINT 1: Translate Entire Book ====================


@router.post(
    "/{book_id}/translate",
    response_model=TranslateBookResponse,
    status_code=status.HTTP_200_OK,
)
async def translate_book(
    book_id: str,
    request: TranslateBookRequest,
    current_user: dict = Depends(get_current_user),
    translation_service: BookTranslationService = Depends(get_translation_service),
):
    """
    Translate entire book to another language

    **Cost:**
    - Book metadata: 2 points
    - Each chapter: 2 points
    - Total: 2 + (num_chapters × 2) points

    **Workflow:**
    1. Verify user owns the book
    2. Check sufficient points
    3. Translate book metadata (title, description)
    4. Translate all chapters (if translate_chapters=true)
    5. Save translations to database
    6. Deduct points

    **Returns:**
    - 200: Translation successful
    - 403: Not owner or insufficient points
    - 404: Book not found
    - 500: Translation failed
    """
    try:
        user_id = current_user["uid"]

        logger.info(f"🌍 Translate book request: {book_id} → {request.target_language}")

        # 1. Verify ownership
        book = db.online_books.find_one({"book_id": book_id, "user_id": user_id})
        if not book:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Book not found or you don't have permission",
            )

        # 2. Get chapter count for cost calculation
        chapter_count = (
            db.book_chapters.count_documents({"book_id": book_id})
            if request.translate_chapters
            else 0
        )
        points_needed = 2 + (chapter_count * 2)  # Book + chapters

        # 3. Check points
        points_service = get_points_service()
        check_result = await points_service.check_sufficient_points(
            user_id=user_id, points_needed=points_needed, service="book_translation"
        )

        if not check_result["has_points"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "insufficient_points",
                    "message": f"Không đủ points để dịch book. Cần: {points_needed}, Còn: {check_result['points_available']}",
                    "points_needed": points_needed,
                    "points_available": check_result["points_available"],
                },
            )

        # 4. Translate book
        source_language = request.source_language or book.get("default_language", "vi")

        chapters_translated, total_cost = (
            await translation_service.translate_entire_book(
                book_id=book_id,
                target_language=request.target_language,
                source_language=source_language,
                translate_chapters=request.translate_chapters,
                preserve_background=request.preserve_background,
                custom_background=request.custom_background,
            )
        )

        # 5. Get translated data for response
        updated_book = db.online_books.find_one({"book_id": book_id})
        translation_data = updated_book.get("translations", {}).get(
            request.target_language, {}
        )

        # 6. Deduct points
        try:
            await points_service.deduct_points(
                user_id=user_id,
                amount=total_cost,
                service="book_translation",
                resource_id=book_id,
                description=f"Book Translation: {source_language} → {request.target_language} ({chapters_translated} chapters)",
            )
            logger.info(f"💸 Deducted {total_cost} points for book translation")
        except Exception as points_error:
            logger.error(f"❌ Error deducting points: {points_error}")

        # 7. Return response
        return TranslateBookResponse(
            success=True,
            book_id=book_id,
            target_language=request.target_language,
            source_language=source_language,
            translated_fields=TranslatedFields(
                title=translation_data.get("title"),
                description=translation_data.get("description"),
            ),
            chapters_translated=chapters_translated,
            total_cost_points=total_cost,
            message=f"Book translated successfully to {request.target_language}",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Book translation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Translation failed: {str(e)}",
        )


# ==================== ENDPOINT 2: Translate Single Chapter ====================


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
    translation_service: BookTranslationService = Depends(get_translation_service),
):
    """
    Translate single chapter to another language

    **Cost:** 2 points per chapter

    **Workflow:**
    1. Verify user owns the book
    2. Check sufficient points (2 points)
    3. Translate chapter (title, description, content_html)
    4. Save translation to database
    5. Deduct points

    **Returns:**
    - 200: Translation successful
    - 403: Not owner or insufficient points
    - 404: Book or chapter not found
    - 500: Translation failed
    """
    try:
        user_id = current_user["uid"]

        logger.info(
            f"🌍 Translate chapter request: {chapter_id} → {request.target_language}"
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

        # 3. Check points
        points_needed = 2
        points_service = get_points_service()
        check_result = await points_service.check_sufficient_points(
            user_id=user_id, points_needed=points_needed, service="chapter_translation"
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

        # 4. Translate chapter
        source_language = request.source_language or chapter.get(
            "default_language", "vi"
        )

        translated_data = await translation_service.translate_chapter_content(
            chapter_id=chapter_id,
            target_language=request.target_language,
            source_language=source_language,
        )

        # 5. Save translation
        background_to_save = (
            None if request.preserve_background else request.custom_background
        )
        await translation_service.save_chapter_translation(
            chapter_id=chapter_id,
            target_language=request.target_language,
            translated_data=translated_data,
            custom_background=background_to_save,
        )

        # 6. Deduct points
        try:
            await points_service.deduct_points(
                user_id=user_id,
                amount=points_needed,
                service="chapter_translation",
                resource_id=chapter_id,
                description=f"Chapter Translation: {source_language} → {request.target_language}",
            )
            logger.info(f"💸 Deducted {points_needed} points for chapter translation")
        except Exception as points_error:
            logger.error(f"❌ Error deducting points: {points_error}")

        # 7. Return response
        return TranslateChapterResponse(
            success=True,
            chapter_id=chapter_id,
            book_id=book_id,
            target_language=request.target_language,
            source_language=source_language,
            translated_fields=TranslatedFields(
                title=translated_data.get("title"),
                description=translated_data.get("description"),
                content_html=translated_data.get("content_html"),
            ),
            translation_cost_points=points_needed,
            message=f"Chapter translated successfully to {request.target_language}",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Chapter translation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Translation failed: {str(e)}",
        )


# ==================== ENDPOINT 3 & 4: Get Book/Chapter in Language ====================
# These are handled by modifying existing endpoints to accept ?language= parameter
# Will be added to book_routes.py and book_chapter_routes.py


# ==================== ENDPOINT 5: List Available Languages ====================


@router.get(
    "/{book_id}/languages",
    response_model=LanguageListResponse,
    status_code=status.HTTP_200_OK,
)
async def list_book_languages(
    book_id: str,
    translation_service: BookTranslationService = Depends(get_translation_service),
):
    """
    List all available languages for a book

    **No authentication required** (public endpoint)

    **Returns:**
    - 200: List of available languages
    - 404: Book not found
    """
    try:
        book = db.online_books.find_one({"book_id": book_id})
        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Book {book_id} not found",
            )

        languages = translation_service.get_available_languages(book_id)

        return LanguageListResponse(
            book_id=book_id,
            default_language=book.get("default_language", "vi"),
            available_languages=[LanguageInfo(**lang) for lang in languages],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to list languages: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list languages: {str(e)}",
        )


# ==================== ENDPOINT 6: Update Background for Language ====================


@router.put(
    "/{book_id}/background/{language}",
    response_model=UpdateBackgroundForLanguageResponse,
    status_code=status.HTTP_200_OK,
)
async def update_book_background_for_language(
    book_id: str,
    language: str,
    request: UpdateBackgroundForLanguageRequest,
    current_user: dict = Depends(get_current_user),
    translation_service: BookTranslationService = Depends(get_translation_service),
):
    """
    Update background configuration for specific language

    **Workflow:**
    1. Verify user owns the book
    2. Validate language code
    3. Update background_translations for this language

    **Returns:**
    - 200: Background updated
    - 403: Not owner
    - 404: Book not found
    """
    try:
        user_id = current_user["uid"]

        # 1. Verify ownership
        book = db.online_books.find_one({"book_id": book_id, "user_id": user_id})
        if not book:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Book not found or you don't have permission",
            )

        # 2. Validate language
        if language not in SUPPORTED_LANGUAGES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported language: {language}",
            )

        # 3. Update background
        success = translation_service.update_background_for_language(
            book_id=book_id,
            chapter_id=None,
            language=language,
            background_config=request.background_config,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update background",
            )

        return UpdateBackgroundForLanguageResponse(
            success=True,
            book_id=book_id,
            language=language,
            background_config=request.background_config,
            message=f"Background updated for {language} version",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update background: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update background: {str(e)}",
        )


@router.put(
    "/{book_id}/chapters/{chapter_id}/background/{language}",
    response_model=UpdateBackgroundForLanguageResponse,
    status_code=status.HTTP_200_OK,
)
async def update_chapter_background_for_language(
    book_id: str,
    chapter_id: str,
    language: str,
    request: UpdateBackgroundForLanguageRequest,
    current_user: dict = Depends(get_current_user),
    translation_service: BookTranslationService = Depends(get_translation_service),
):
    """
    Update chapter background configuration for specific language

    **Similar to book background update but for chapters**
    """
    try:
        user_id = current_user["uid"]

        # 1. Verify ownership
        book = db.online_books.find_one({"book_id": book_id, "user_id": user_id})
        if not book:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Book not found or you don't have permission",
            )

        # 2. Validate language
        if language not in SUPPORTED_LANGUAGES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported language: {language}",
            )

        # 3. Update background
        success = translation_service.update_background_for_language(
            book_id=None,
            chapter_id=chapter_id,
            language=language,
            background_config=request.background_config,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update background",
            )

        return UpdateBackgroundForLanguageResponse(
            success=True,
            chapter_id=chapter_id,
            language=language,
            background_config=request.background_config,
            message=f"Chapter background updated for {language} version",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update chapter background: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update background: {str(e)}",
        )


# ==================== ENDPOINT 7: Delete Translation ====================


@router.delete(
    "/{book_id}/translations/{language}",
    response_model=DeleteTranslationResponse,
    status_code=status.HTTP_200_OK,
)
async def delete_book_translation(
    book_id: str,
    language: str,
    delete_chapters: bool = Query(
        True, description="Also delete translations from chapters"
    ),
    current_user: dict = Depends(get_current_user),
    translation_service: BookTranslationService = Depends(get_translation_service),
):
    """
    Delete translation for specific language

    **Workflow:**
    1. Verify user owns the book
    2. Cannot delete default language
    3. Remove translation from book and chapters
    4. Update available_languages list

    **Returns:**
    - 200: Translation deleted
    - 400: Cannot delete default language
    - 403: Not owner
    - 404: Book not found
    """
    try:
        user_id = current_user["uid"]

        # 1. Verify ownership
        book = db.online_books.find_one({"book_id": book_id, "user_id": user_id})
        if not book:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Book not found or you don't have permission",
            )

        # 2. Delete translation
        deleted_count = translation_service.delete_translation(
            book_id=book_id, language=language, delete_chapters=delete_chapters
        )

        # 3. Get remaining languages
        updated_book = db.online_books.find_one({"book_id": book_id})
        remaining_languages = updated_book.get("available_languages", [])

        return DeleteTranslationResponse(
            success=True,
            book_id=book_id,
            language_deleted=language,
            remaining_languages=remaining_languages,
            message=f"Translation for {language} deleted successfully ({deleted_count} items updated)",
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete translation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete translation: {str(e)}",
        )
