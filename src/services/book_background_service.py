"""
Book Background Service
Service layer for managing book and chapter backgrounds
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import uuid

from src.services.gemini_image_service import get_gemini_image_service
from src.models.book_background_models import (
    BackgroundConfig,
    GenerateBackgroundRequest,
    AIMetadata,
)

logger = logging.getLogger("chatbot")


class BookBackgroundService:
    """Service for managing book/chapter backgrounds"""

    def __init__(self, db):
        self.db = db
        self.gemini_service = get_gemini_image_service()

    async def generate_ai_background(
        self, user_id: str, request: GenerateBackgroundRequest
    ) -> Dict[str, Any]:
        """
        Generate AI background using Gemini 3 Pro Image

        Args:
            user_id: Firebase user ID
            request: Background generation request

        Returns:
            Dict with image_url, r2_key, file_id, prompt_used, generation_time_ms, ai_metadata
        """
        try:
            # Build optimized prompt based on generation type
            if request.generation_type == "slide_background":
                optimized_prompt = self._build_slide_prompt(
                    request.prompt, request.style
                )
                gen_type = "slide_background"
                filename_prefix = "slide_bg"
            else:  # book_cover (default)
                optimized_prompt = self._build_a4_prompt(request.prompt, request.style)
                gen_type = "background_a4"
                filename_prefix = "background_a4"

            logger.info(f"🎨 Generating {request.generation_type} for user {user_id}")
            logger.info(f"   Prompt: {request.prompt[:50]}...")
            logger.info(f"   Aspect Ratio: {request.aspect_ratio}")

            # Generate image using Gemini service
            result = await self.gemini_service.generate_image(
                prompt=optimized_prompt,
                generation_type=gen_type,
                user_options={"style": request.style} if request.style else {},
                aspect_ratio=request.aspect_ratio,
            )

            # Upload to R2
            filename = f"{filename_prefix}_{uuid.uuid4().hex[:8]}.png"
            upload_result = await self.gemini_service.upload_to_r2(
                image_bytes=result["image_bytes"], user_id=user_id, filename=filename
            )

            logger.info(
                f"☁️  Uploaded {request.generation_type} to R2: {upload_result['file_url']}"
            )

            # Save to library
            from src.models.image_generation_models import ImageGenerationMetadata

            metadata = ImageGenerationMetadata(
                source="gemini-3-pro-image-preview",
                generation_type=gen_type,
                prompt=request.prompt,
                aspect_ratio=request.aspect_ratio,
                generation_time_ms=result["generation_time_ms"],
                model_version="gemini-3-pro-image-preview",
                reference_images_count=0,
                user_options={
                    "style": request.style,
                    "generation_type": request.generation_type,
                    "type": "background",
                },
            )

            library_doc = await self.gemini_service.save_to_library(
                user_id=user_id,
                filename=filename,
                file_size=result["image_size"],
                r2_key=upload_result["r2_key"],
                file_url=upload_result["file_url"],
                generation_metadata=metadata,
                db=self.db,
            )

            logger.info(f"📚 Saved background to library: {library_doc['file_id']}")

            return {
                "image_url": upload_result["file_url"],
                "r2_key": upload_result["r2_key"],
                "file_id": library_doc["file_id"],
                "prompt_used": optimized_prompt,
                "generation_time_ms": result["generation_time_ms"],
                "ai_metadata": AIMetadata(
                    prompt=request.prompt,
                    model="gemini-3-pro-image-preview",
                    generated_at=datetime.now(timezone.utc),
                    generation_time_ms=result["generation_time_ms"],
                    cost_points=2,
                ),
            }

        except Exception as e:
            logger.error(f"❌ Failed to generate AI background: {e}", exc_info=True)

            # Check if it's a 503 error (Gemini overloaded)
            error_str = str(e)
            if "503" in error_str or "overloaded" in error_str.lower():
                raise Exception(
                    "Gemini API đang quá tải. Vui lòng thử lại sau. (Không trừ điểm)"
                )

            raise Exception(f"Background generation failed: {str(e)}")

    def _build_a4_prompt(self, user_prompt: str, style: Optional[str]) -> str:
        """Build A4-optimized prompt for Gemini (book covers, documents)"""
        prompt_parts = [
            "Create a high-quality A4 portrait background image (3:4 aspect ratio, 210mm × 297mm).",
            "",
            f"BACKGROUND DESCRIPTION: {user_prompt}",
            "",
            "REQUIREMENTS:",
            "- Suitable for document/book chapter backgrounds",
            "- Professional and clean design",
            "- Not too busy or distracting (good for reading)",
            "- Excellent contrast for text overlay",
            "- Print-ready quality",
            "- Subtle and elegant patterns",
        ]

        if style:
            prompt_parts.append(f"- Artistic style: {style}")

        return "\n".join(prompt_parts)

    def _build_slide_prompt(self, user_prompt: str, style: Optional[str]) -> str:
        """Build slide-optimized prompt for Gemini (presentations, educational slides)"""

        # Map common style keywords to presentation contexts
        style_contexts = {
            "business": "corporate business presentation with professional aesthetics",
            "startup": "modern startup pitch deck with innovative and dynamic design",
            "corporate": "formal corporate presentation with clean and trustworthy design",
            "education": "educational presentation with clear learning-focused design",
            "academic": "academic presentation with scholarly and research-focused design",
            "creative": "creative presentation with artistic and expressive design",
            "minimalist": "minimalist presentation with clean and simple design",
            "modern": "modern presentation with contemporary and sleek design",
        }

        context = style_contexts.get(
            style.lower() if style else "", "professional presentation"
        )

        prompt_parts = [
            "Create a high-quality presentation slide background image (16:9 aspect ratio, 1920×1080px).",
            "",
            f"BACKGROUND DESCRIPTION: {user_prompt}",
            "",
            f"PRESENTATION CONTEXT: {context}",
            "",
            "REQUIREMENTS:",
            "- Designed specifically for presentation slides (not documents)",
            "- Optimized for 16:9 widescreen display",
            "- Maximum visual impact for audience engagement",
            "- Excellent readability for text/content overlay",
            "- Professional quality suitable for:",
            "  * Business presentations and pitch decks",
            "  * Educational lectures and training materials",
            "  * Conference talks and workshops",
            "  * Corporate communications",
            "- Balanced composition with strategic empty space for content",
            "- High contrast areas for text placement",
            "- Visually appealing but not overwhelming",
            "- Modern and polished aesthetic",
        ]

        # Add style-specific guidelines
        if style:
            style_lower = style.lower()
            if style_lower in ["business", "corporate"]:
                prompt_parts.extend(
                    [
                        "",
                        "STYLE GUIDELINES:",
                        "- Professional color palette (blues, grays, whites)",
                        "- Clean lines and geometric patterns",
                        "- Trustworthy and authoritative feel",
                        "- Subtle gradients or solid backgrounds",
                    ]
                )
            elif style_lower == "startup":
                prompt_parts.extend(
                    [
                        "",
                        "STYLE GUIDELINES:",
                        "- Bold and energetic color palette",
                        "- Dynamic angles and modern shapes",
                        "- Innovative and forward-thinking feel",
                        "- Gradients with vibrant colors",
                    ]
                )
            elif style_lower in ["education", "academic"]:
                prompt_parts.extend(
                    [
                        "",
                        "STYLE GUIDELINES:",
                        "- Clear and focused design",
                        "- Learning-friendly color palette",
                        "- Organized and structured layout",
                        "- Calm and concentration-promoting",
                    ]
                )
            elif style_lower == "minimalist":
                prompt_parts.extend(
                    [
                        "",
                        "STYLE GUIDELINES:",
                        "- Extremely clean and simple",
                        "- Monochromatic or limited color palette",
                        "- Lots of white/negative space",
                        "- Focus on essential elements only",
                    ]
                )
            else:
                prompt_parts.append(f"- Artistic style: {style}")

        return "\n".join(prompt_parts)

    def update_book_background(
        self, book_id: str, user_id: str, config: BackgroundConfig
    ) -> Optional[Dict[str, Any]]:
        """
        Update book background configuration

        Args:
            book_id: Book ID
            user_id: User ID (for ownership verification)
            config: Background configuration

        Returns:
            Updated book document or None if not found
        """
        try:
            result = self.db.online_books.find_one_and_update(
                {"book_id": book_id, "user_id": user_id},
                {
                    "$set": {
                        "background_config": config.model_dump(exclude_none=True),
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
                return_document=True,
            )

            if result:
                logger.info(
                    f"✅ Updated book background: {book_id} (type: {config.type})"
                )
                return result
            return None

        except Exception as e:
            logger.error(f"❌ Failed to update book background: {e}", exc_info=True)
            raise Exception(f"Failed to update book background: {str(e)}")

    def get_book_background(self, book_id: str) -> Optional[Dict[str, Any]]:
        """
        Get book background configuration

        Args:
            book_id: Book ID

        Returns:
            Background config or None
        """
        try:
            book = self.db.online_books.find_one(
                {"book_id": book_id}, {"background_config": 1}
            )
            return book.get("background_config") if book else None

        except Exception as e:
            logger.error(f"❌ Failed to get book background: {e}")
            return None

    def delete_book_background(self, book_id: str, user_id: str) -> bool:
        """
        Reset book background to default (remove background_config)

        Args:
            book_id: Book ID
            user_id: User ID (for ownership verification)

        Returns:
            True if deleted, False otherwise
        """
        try:
            result = self.db.online_books.update_one(
                {"book_id": book_id, "user_id": user_id},
                {
                    "$unset": {"background_config": ""},
                    "$set": {"updated_at": datetime.now(timezone.utc)},
                },
            )

            if result.modified_count > 0:
                logger.info(f"✅ Deleted book background: {book_id}")
                return True
            return False

        except Exception as e:
            logger.error(f"❌ Failed to delete book background: {e}")
            return False

    def update_chapter_background(
        self,
        book_id: str,
        chapter_id: str,
        user_id: str,
        use_book_background: bool,
        config: Optional[BackgroundConfig] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Update chapter background configuration

        Args:
            book_id: Book ID
            chapter_id: Chapter ID
            user_id: User ID (for ownership verification)
            use_book_background: Whether to use book background
            config: Custom background config (required if use_book_background=False)

        Returns:
            Updated chapter document or None if not found
        """
        try:
            # Verify book ownership
            book = self.db.online_books.find_one(
                {"book_id": book_id, "user_id": user_id}
            )
            if not book:
                logger.warning(f"Book not found or user not authorized: {book_id}")
                return None

            # Prepare update data
            update_data = {
                "use_book_background": use_book_background,
                "updated_at": datetime.now(timezone.utc),
            }

            if use_book_background:
                # Reset to use book background
                update_data["background_config"] = None
            else:
                # Use custom chapter background
                if not config:
                    raise ValueError(
                        "background_config required when use_book_background=false"
                    )
                update_data["background_config"] = config.model_dump(exclude_none=True)

            # Update chapter
            result = self.db.book_chapters.find_one_and_update(
                {"chapter_id": chapter_id, "book_id": book_id},
                {"$set": update_data},
                return_document=True,
            )

            if result:
                logger.info(
                    f"✅ Updated chapter background: {chapter_id} (use_book: {use_book_background})"
                )
                return result
            return None

        except Exception as e:
            logger.error(f"❌ Failed to update chapter background: {e}", exc_info=True)
            raise Exception(f"Failed to update chapter background: {str(e)}")

    def get_chapter_background(
        self, book_id: str, chapter_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get chapter background (with fallback to book background)

        Args:
            book_id: Book ID
            chapter_id: Chapter ID

        Returns:
            Dict with chapter_id, use_book_background, background_config, inherited_from_book
        """
        try:
            chapter = self.db.book_chapters.find_one(
                {"chapter_id": chapter_id, "book_id": book_id},
                {"use_book_background": 1, "background_config": 1},
            )

            if not chapter:
                return None

            use_book_bg = chapter.get("use_book_background", True)

            if use_book_bg:
                # Get book background
                book_bg = self.get_book_background(book_id)
                return {
                    "chapter_id": chapter_id,
                    "use_book_background": True,
                    "background_config": book_bg,
                    "inherited_from_book": True,
                }
            else:
                # Use chapter background
                return {
                    "chapter_id": chapter_id,
                    "use_book_background": False,
                    "background_config": chapter.get("background_config"),
                    "inherited_from_book": False,
                }

        except Exception as e:
            logger.error(f"❌ Failed to get chapter background: {e}")
            return None

    def delete_chapter_background(
        self, book_id: str, chapter_id: str, user_id: str
    ) -> bool:
        """
        Reset chapter background to use book background

        Args:
            book_id: Book ID
            chapter_id: Chapter ID
            user_id: User ID (for ownership verification)

        Returns:
            True if deleted, False otherwise
        """
        try:
            # Verify book ownership
            book = self.db.online_books.find_one(
                {"book_id": book_id, "user_id": user_id}
            )
            if not book:
                return False

            result = self.db.book_chapters.update_one(
                {"chapter_id": chapter_id, "book_id": book_id},
                {
                    "$set": {
                        "use_book_background": True,
                        "background_config": None,
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )

            if result.modified_count > 0:
                logger.info(f"✅ Reset chapter background to use book: {chapter_id}")
                return True
            return False

        except Exception as e:
            logger.error(f"❌ Failed to delete chapter background: {e}")
            return False

    # ========== DOCUMENT BACKGROUND METHODS ==========

    def update_document_background(
        self,
        document_id: str,
        user_id: str,
        config: BackgroundConfig,
    ) -> Optional[Dict[str, Any]]:
        """
        Update document background configuration (for A4 documents)

        Args:
            document_id: Document ID
            user_id: User ID (for ownership verification)
            config: Background configuration

        Returns:
            Updated document or None if not found
        """
        try:
            result = self.db.documents.find_one_and_update(
                {"document_id": document_id, "user_id": user_id},
                {
                    "$set": {
                        "background_config": config.model_dump(exclude_none=True),
                        "last_saved_at": datetime.now(timezone.utc),
                    }
                },
                return_document=True,
            )

            if result:
                logger.info(
                    f"✅ Updated document background: {document_id} (type: {config.type})"
                )
                return result
            return None

        except Exception as e:
            logger.error(f"❌ Failed to update document background: {e}", exc_info=True)
            raise Exception(f"Failed to update document background: {str(e)}")

    def get_document_background(
        self, document_id: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get document background configuration

        Args:
            document_id: Document ID
            user_id: User ID (for ownership verification)

        Returns:
            Background config or None
        """
        try:
            document = self.db.documents.find_one(
                {"document_id": document_id, "user_id": user_id},
                {"background_config": 1},
            )
            return document.get("background_config") if document else None

        except Exception as e:
            logger.error(f"❌ Failed to get document background: {e}")
            return None

    def delete_document_background(self, document_id: str, user_id: str) -> bool:
        """
        Remove document background (reset to default)

        Args:
            document_id: Document ID
            user_id: User ID (for ownership verification)

        Returns:
            True if deleted, False otherwise
        """
        try:
            result = self.db.documents.update_one(
                {"document_id": document_id, "user_id": user_id},
                {
                    "$unset": {"background_config": ""},
                    "$set": {"last_saved_at": datetime.now(timezone.utc)},
                },
            )

            if result.modified_count > 0:
                logger.info(f"✅ Deleted document background: {document_id}")
                return True
            return False

        except Exception as e:
            logger.error(f"❌ Failed to delete document background: {e}")
            return False


# Singleton instance
_book_background_service = None


def get_book_background_service(db) -> BookBackgroundService:
    """Get or create BookBackgroundService singleton"""
    global _book_background_service
    if _book_background_service is None:
        _book_background_service = BookBackgroundService(db)
    return _book_background_service
