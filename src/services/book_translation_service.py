"""
Book Translation Service
AI-powered translation service for books and chapters using Gemini 2.5 Pro
"""

import logging
import json
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from pymongo.database import Database

from src.services.ai_chat_service import ai_chat_service, AIProvider
from src.models.book_translation_models import (
    SUPPORTED_LANGUAGES,
    LANGUAGE_NAMES,
    get_language_name,
    get_language_flag,
)

logger = logging.getLogger("chatbot")


class BookTranslationService:
    """Service for translating books and chapters"""

    def __init__(self, db: Database):
        self.db = db
        self.books_collection = db["online_books"]
        self.chapters_collection = db["book_chapters"]

    # ==================== TRANSLATION PROMPTS ====================

    def _generate_book_metadata_translation_prompt(
        self,
        title: str,
        description: str,
        source_language: str,
        target_language: str,
    ) -> str:
        """Generate prompt for translating book metadata (title + description)"""

        source_lang_name = get_language_name(source_language)
        target_lang_name = get_language_name(target_language)

        return f"""You are a professional translator specializing in {target_lang_name}.

**TASK:**
Translate the following book metadata from {source_lang_name} to {target_lang_name}.

**RULES:**
1. Maintain the same tone and style
2. Keep technical terms accurate
3. Adapt cultural references appropriately
4. Return ONLY valid JSON format (no markdown, no explanations, no code blocks)

**INPUT (in {source_lang_name}):**
- Title: "{title}"
- Description: "{description or 'N/A'}"

**OUTPUT FORMAT (JSON only):**
{{
  "title": "translated title in {target_lang_name}",
  "description": "translated description in {target_lang_name}"
}}

Return only the JSON object:"""

    def _generate_chapter_translation_prompt(
        self,
        title: str,
        description: Optional[str],
        content_html: str,
        source_language: str,
        target_language: str,
    ) -> str:
        """Generate prompt for translating chapter content (title + description + HTML)"""

        source_lang_name = get_language_name(source_language)
        target_lang_name = get_language_name(target_language)

        return f"""You are a professional translator specializing in {target_lang_name}.

**TASK:**
Translate chapter content from {source_lang_name} to {target_lang_name}.

**CRITICAL RULES FOR HTML TRANSLATION:**
1. PRESERVE HTML STRUCTURE: Keep ALL HTML tags, attributes, classes, IDs intact
2. TRANSLATE ONLY TEXT CONTENT: Only translate text inside HTML tags
3. DO NOT translate:
   - HTML tag names (<div>, <p>, <h1>, etc.)
   - CSS classes and IDs (class="text-blue-500", id="intro")
   - Inline styles (style="color: red;")
   - URLs in href and src attributes
   - Data attributes (data-*)
4. PRESERVE FORMATTING: Keep line breaks, indentation, spacing
5. HANDLE SPECIAL CONTENT:
   - Code blocks (<pre>, <code>): Keep code unchanged, translate only comments
   - Links: Translate link text but NOT the URL
   - Images: Translate alt text but NOT src
6. Return ONLY valid JSON (no markdown code blocks, no explanations)

**INPUT (in {source_lang_name}):**
- Title: "{title}"
- Description: "{description or 'N/A'}"
- Content HTML: {len(content_html)} characters

**OUTPUT FORMAT (JSON only):**
{{
  "title": "translated title in {target_lang_name}",
  "description": "translated description in {target_lang_name}",
  "content_html": "translated HTML content with preserved structure"
}}

**Content HTML to translate:**
{content_html}

Return only the JSON object:"""

    # ==================== AI TRANSLATION ====================

    async def _call_ai_translation(
        self, prompt: str, max_retries: int = 3
    ) -> Dict[str, Any]:
        """Call AI for translation with retry logic"""

        for attempt in range(max_retries):
            try:
                messages = [
                    {
                        "role": "system",
                        "content": "You are a professional translator. You only return clean JSON objects without any markdown formatting or explanations.",
                    },
                    {"role": "user", "content": prompt},
                ]

                # Use Gemini 2.5 Pro for high-quality translation
                response = await ai_chat_service.chat(
                    provider=AIProvider.GEMINI_PRO,
                    messages=messages,
                    temperature=0.3,
                    max_tokens=48000,
                )

                # Clean response (remove markdown code blocks if present)
                response = response.strip()
                if response.startswith("```json"):
                    response = response[7:]
                if response.startswith("```"):
                    response = response[3:]
                if response.endswith("```"):
                    response = response[:-3]
                response = response.strip()

                # Parse JSON
                result = json.loads(response)
                return result

            except json.JSONDecodeError as e:
                logger.warning(
                    f"⚠️ JSON decode error on attempt {attempt + 1}/{max_retries}: {e}"
                )
                if attempt == max_retries - 1:
                    raise ValueError(f"Failed to parse AI response as JSON: {response}")

            except Exception as e:
                logger.error(f"❌ AI translation error on attempt {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    raise

        raise Exception("Translation failed after all retries")

    # ==================== BOOK TRANSLATION ====================

    async def translate_book_metadata(
        self,
        book_id: str,
        target_language: str,
        source_language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Translate book title and description

        Returns:
            {
                "title": "translated title",
                "description": "translated description"
            }
        """
        book = self.books_collection.find_one({"book_id": book_id})
        if not book:
            raise ValueError(f"Book {book_id} not found")

        # Get source language
        if not source_language:
            source_language = book.get("default_language", "vi")

        # Get source content (from original or existing translation)
        if source_language == book.get("default_language", "vi"):
            title = book.get("title", "")
            description = book.get("description", "")
        else:
            translations = book.get("translations", {})
            if source_language not in translations:
                raise ValueError(
                    f"Source language {source_language} not found in book translations"
                )
            source_data = translations[source_language]
            title = source_data.get("title", "")
            description = source_data.get("description", "")

        # Generate prompt
        prompt = self._generate_book_metadata_translation_prompt(
            title=title,
            description=description,
            source_language=source_language,
            target_language=target_language,
        )

        # Call AI
        result = await self._call_ai_translation(prompt)

        logger.info(
            f"✅ Translated book metadata: {book_id} "
            f"({source_language} → {target_language})"
        )

        return result

    async def save_book_translation(
        self,
        book_id: str,
        target_language: str,
        translated_data: Dict[str, Any],
        custom_background: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Save book translation to database"""

        now = datetime.utcnow()

        # Prepare translation data
        translation_entry = {
            "title": translated_data.get("title"),
            "description": translated_data.get("description"),
            "translated_at": now,
            "translated_by": "gemini-2.5-pro",
            "translation_cost_points": 2,
        }

        # Update book
        update_query = {
            "$set": {
                f"translations.{target_language}": translation_entry,
                "updated_at": now,
            },
            "$addToSet": {"available_languages": target_language},
        }

        # Add custom background if provided
        if custom_background:
            update_query["$set"][
                f"background_translations.{target_language}"
            ] = custom_background

        result = self.books_collection.update_one({"book_id": book_id}, update_query)

        return result.modified_count > 0

    # ==================== CHAPTER TRANSLATION ====================

    async def translate_chapter_content(
        self,
        chapter_id: str,
        target_language: str,
        source_language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Translate chapter title, description, and content_html

        Returns:
            {
                "title": "translated title",
                "description": "translated description",
                "content_html": "translated HTML"
            }
        """
        chapter = self.chapters_collection.find_one({"chapter_id": chapter_id})
        if not chapter:
            raise ValueError(f"Chapter {chapter_id} not found")

        # Get source language
        if not source_language:
            source_language = chapter.get("default_language", "vi")

        # Get source content
        if source_language == chapter.get("default_language", "vi"):
            title = chapter.get("title", "")
            description = chapter.get("description", "")
            content_html = chapter.get("content_html", "")
        else:
            translations = chapter.get("translations", {})
            if source_language not in translations:
                raise ValueError(
                    f"Source language {source_language} not found in chapter translations"
                )
            source_data = translations[source_language]
            title = source_data.get("title", "")
            description = source_data.get("description", "")
            content_html = source_data.get("content_html", "")

        if not content_html:
            raise ValueError(f"Chapter {chapter_id} has no content to translate")

        # Generate prompt
        prompt = self._generate_chapter_translation_prompt(
            title=title,
            description=description,
            content_html=content_html,
            source_language=source_language,
            target_language=target_language,
        )

        # Call AI
        result = await self._call_ai_translation(prompt)

        logger.info(
            f"✅ Translated chapter: {chapter_id} "
            f"({source_language} → {target_language}, "
            f"{len(content_html)} → {len(result.get('content_html', ''))} chars)"
        )

        return result

    async def save_chapter_translation(
        self,
        chapter_id: str,
        target_language: str,
        translated_data: Dict[str, Any],
        custom_background: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Save chapter translation to database"""

        now = datetime.utcnow()

        # Prepare translation data
        translation_entry = {
            "title": translated_data.get("title"),
            "description": translated_data.get("description"),
            "content_html": translated_data.get("content_html"),
            "translated_at": now,
            "translated_by": "gemini-2.5-pro",
            "translation_cost_points": 2,
        }

        # Update chapter
        update_query = {
            "$set": {
                f"translations.{target_language}": translation_entry,
                "updated_at": now,
            },
            "$addToSet": {"available_languages": target_language},
        }

        # Add custom background if provided
        if custom_background:
            update_query["$set"][
                f"background_translations.{target_language}"
            ] = custom_background

        result = self.chapters_collection.update_one(
            {"chapter_id": chapter_id}, update_query
        )

        return result.modified_count > 0

    # ==================== BULK TRANSLATION ====================

    async def translate_entire_book(
        self,
        book_id: str,
        target_language: str,
        source_language: Optional[str] = None,
        translate_chapters: bool = True,
        preserve_background: bool = True,
        custom_background: Optional[Dict[str, Any]] = None,
    ) -> Tuple[int, int]:
        """
        Translate entire book including all chapters

        Returns:
            (chapters_translated, total_points_cost)
        """
        # 1. Translate book metadata
        book_translation = await self.translate_book_metadata(
            book_id=book_id,
            target_language=target_language,
            source_language=source_language,
        )

        # Save book translation
        background_to_save = None if preserve_background else custom_background
        await self.save_book_translation(
            book_id=book_id,
            target_language=target_language,
            translated_data=book_translation,
            custom_background=background_to_save,
        )

        points_cost = 2  # Book metadata translation

        # 2. Translate chapters if requested
        chapters_translated = 0
        if translate_chapters:
            chapters = list(
                self.chapters_collection.find({"book_id": book_id}).sort(
                    "order_index", 1
                )
            )

            for chapter in chapters:
                try:
                    chapter_translation = await self.translate_chapter_content(
                        chapter_id=chapter["chapter_id"],
                        target_language=target_language,
                        source_language=source_language,
                    )

                    await self.save_chapter_translation(
                        chapter_id=chapter["chapter_id"],
                        target_language=target_language,
                        translated_data=chapter_translation,
                        custom_background=background_to_save,
                    )

                    chapters_translated += 1
                    points_cost += 2  # Each chapter costs 2 points

                    logger.info(
                        f"✅ Translated chapter {chapters_translated}/{len(chapters)}: "
                        f"{chapter['title']}"
                    )

                except Exception as e:
                    logger.error(
                        f"❌ Failed to translate chapter {chapter['chapter_id']}: {e}"
                    )
                    # Continue with other chapters

        return chapters_translated, points_cost

    # ==================== LANGUAGE MANAGEMENT ====================

    def get_available_languages(self, book_id: str) -> List[Dict[str, Any]]:
        """Get list of available languages for a book"""

        book = self.books_collection.find_one({"book_id": book_id})
        if not book:
            raise ValueError(f"Book {book_id} not found")

        default_language = book.get("default_language", "vi")
        available_languages = book.get("available_languages", [default_language])
        translations = book.get("translations", {})

        result = []
        for lang_code in available_languages:
            is_default = lang_code == default_language
            translated_at = None

            if not is_default and lang_code in translations:
                translated_at = translations[lang_code].get("translated_at")

            result.append(
                {
                    "code": lang_code,
                    "name": get_language_name(lang_code),
                    "flag": get_language_flag(lang_code),
                    "is_default": is_default,
                    "translated_at": translated_at,
                }
            )

        return result

    def delete_translation(
        self, book_id: str, language: str, delete_chapters: bool = True
    ) -> int:
        """
        Delete translation for a specific language

        Returns:
            Number of items deleted (1 book + N chapters)
        """
        book = self.books_collection.find_one({"book_id": book_id})
        if not book:
            raise ValueError(f"Book {book_id} not found")

        # Cannot delete default language
        default_language = book.get("default_language", "vi")
        if language == default_language:
            raise ValueError("Cannot delete default language")

        # Delete from book
        self.books_collection.update_one(
            {"book_id": book_id},
            {
                "$unset": {
                    f"translations.{language}": "",
                    f"background_translations.{language}": "",
                },
                "$pull": {"available_languages": language},
            },
        )

        deleted_count = 1

        # Delete from chapters
        if delete_chapters:
            result = self.chapters_collection.update_many(
                {"book_id": book_id},
                {
                    "$unset": {
                        f"translations.{language}": "",
                        f"background_translations.{language}": "",
                    },
                    "$pull": {"available_languages": language},
                },
            )
            deleted_count += result.modified_count

        logger.info(
            f"✅ Deleted {language} translation from book {book_id} "
            f"({deleted_count} items updated)"
        )

        return deleted_count

    def update_background_for_language(
        self,
        book_id: Optional[str],
        chapter_id: Optional[str],
        language: str,
        background_config: Dict[str, Any],
    ) -> bool:
        """Update background for specific language"""

        if book_id:
            result = self.books_collection.update_one(
                {"book_id": book_id},
                {"$set": {f"background_translations.{language}": background_config}},
            )
            return result.modified_count > 0

        elif chapter_id:
            result = self.chapters_collection.update_one(
                {"chapter_id": chapter_id},
                {"$set": {f"background_translations.{language}": background_config}},
            )
            return result.modified_count > 0

        return False
