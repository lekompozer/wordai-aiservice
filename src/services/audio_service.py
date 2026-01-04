"""
Audio Service
Handles audio upload, storage, and management for book chapters
"""

import logging
import os
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from pymongo.database import Database
import mimetypes

logger = logging.getLogger("chatbot")


class AudioService:
    """Service for managing chapter audio files"""

    def __init__(self, db: Database, r2_service=None, library_manager=None):
        """
        Initialize AudioService

        Args:
            db: MongoDB database instance
            r2_service: R2StorageService instance for file uploads
            library_manager: LibraryManager instance for file tracking
        """
        self.db = db
        self.book_chapters = db["book_chapters"]
        self.r2_service = r2_service
        self.library_manager = library_manager

        # Supported audio formats
        self.supported_formats = {
            "audio/mpeg": "mp3",
            "audio/mp3": "mp3",
            "audio/wav": "wav",
            "audio/x-wav": "wav",
            "audio/wave": "wav",
            "audio/mp4": "m4a",
            "audio/m4a": "m4a",
            "audio/ogg": "ogg",
            "audio/vorbis": "ogg",
        }

        logger.info("✅ AudioService initialized")

    def validate_audio_file(
        self, filename: str, content_type: str, file_size: int
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validate audio file before upload

        Args:
            filename: Original filename
            content_type: MIME type
            file_size: File size in bytes

        Returns:
            Tuple of (is_valid, error_message, audio_format)
        """
        # Check file size (max 50MB)
        max_size = 50 * 1024 * 1024  # 50MB
        if file_size > max_size:
            return (
                False,
                f"File size exceeds 50MB limit ({file_size / 1024 / 1024:.2f}MB)",
                None,
            )

        # Check MIME type
        if content_type not in self.supported_formats:
            # Try to detect from filename
            guessed_type, _ = mimetypes.guess_type(filename)
            if guessed_type and guessed_type in self.supported_formats:
                content_type = guessed_type
            else:
                supported_list = ", ".join(set(self.supported_formats.values()))
                return (
                    False,
                    f"Unsupported audio format. Supported: {supported_list}",
                    None,
                )

        audio_format = self.supported_formats[content_type]
        return True, None, audio_format

    def generate_r2_path(
        self, user_id: str, chapter_id: str, language: Optional[str], audio_format: str
    ) -> str:
        """
        Generate R2 storage path for audio file

        Args:
            user_id: User ID who owns the audio
            chapter_id: Chapter ID
            language: Language code (optional)
            audio_format: Audio file format

        Returns:
            R2 storage path
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]

        lang_suffix = f"_{language}" if language else ""
        filename = f"{chapter_id}{lang_suffix}_{timestamp}_{unique_id}.{audio_format}"

        return f"audio/users/{user_id}/chapters/{filename}"

    async def upload_audio_file(
        self,
        user_id: str,
        book_id: str,
        chapter_id: str,
        file_content: bytes,
        filename: str,
        content_type: str,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Upload audio file to R2 and save to library

        Args:
            user_id: User ID
            book_id: Book ID
            chapter_id: Chapter ID
            file_content: Audio file binary content
            filename: Original filename
            content_type: MIME type
            language: Language code for translation audio

        Returns:
            Dict with audio info (audio_url, file_id, duration, etc.)
        """
        try:
            # Validate file
            is_valid, error_msg, audio_format = self.validate_audio_file(
                filename, content_type, len(file_content)
            )
            if not is_valid:
                raise ValueError(error_msg)

            # Generate R2 path
            r2_path = self.generate_r2_path(
                user_id, chapter_id, language, audio_format or "mp3"
            )

            # Upload to R2
            if not self.r2_service:
                raise ValueError("R2 service not configured")

            upload_result = await self.r2_service.upload_file(
                file_content=file_content,
                r2_key=r2_path,
                content_type=content_type,
            )

            audio_url = upload_result.get("public_url")
            if not audio_url:
                raise ValueError("Failed to upload file to R2")

            # Create library record
            if not self.library_manager:
                raise ValueError("Library manager not configured")

            library_file = self.library_manager.save_library_file(
                user_id=user_id,
                filename=filename,
                file_type="audio",
                category="audio",
                r2_url=audio_url,
                r2_key=r2_path,
                file_size=len(file_content),
                mime_type=content_type,
                metadata={
                    "audio_format": audio_format,
                    "source_type": "user_upload",
                    "linked_to": {
                        "type": "book_chapter",
                        "book_id": book_id,
                        "chapter_id": chapter_id,
                        "language": language or "default",
                    },
                },
            )

            logger.info(
                f"✅ Audio uploaded: user={user_id}, chapter={chapter_id}, "
                f"lang={language or 'default'}, file={library_file['library_id']}"
            )

            return {
                "audio_url": audio_url,
                "audio_file_id": library_file["library_id"],
                "file_size_bytes": len(file_content),
                "format": audio_format,
                "source_type": "user_upload",
            }

        except Exception as e:
            logger.error(f"❌ Failed to upload audio: {e}", exc_info=True)
            raise

    def save_audio_to_chapter(
        self,
        chapter_id: str,
        audio_url: str,
        audio_file_id: str,
        file_size_bytes: int,
        audio_format: str,
        source_type: str,
        duration_seconds: Optional[int] = None,
        voice_settings: Optional[Dict[str, Any]] = None,
        language: Optional[str] = None,
        generated_by_user_id: Optional[str] = None,
        generation_cost_points: Optional[int] = None,
    ) -> bool:
        """
        Save audio config to chapter document (for owner's audio)

        Args:
            chapter_id: Chapter ID
            audio_url: Public audio URL
            audio_file_id: Library file ID
            file_size_bytes: File size
            audio_format: Audio format
            source_type: user_upload or ai_generated
            duration_seconds: Audio duration
            voice_settings: Voice settings for AI audio
            language: Language code (for translations)
            generated_by_user_id: User who generated
            generation_cost_points: Points cost

        Returns:
            True if successful
        """
        try:
            audio_config = {
                "enabled": True,
                "audio_url": audio_url,
                "audio_file_id": audio_file_id,
                "duration_seconds": duration_seconds or 0,
                "file_size_bytes": file_size_bytes,
                "format": audio_format,
                "source_type": source_type,
                "generated_at": datetime.utcnow(),
            }

            if voice_settings:
                audio_config["voice_settings"] = voice_settings

            if generated_by_user_id:
                audio_config["generated_by_user_id"] = generated_by_user_id

            if generation_cost_points:
                audio_config["generation_cost_points"] = generation_cost_points

            # Save to appropriate field
            if language:
                # Save to audio_translations
                update_field = {f"audio_translations.{language}": audio_config}
            else:
                # Save to root audio_config
                update_field = {"audio_config": audio_config}

            result = self.book_chapters.update_one(
                {"chapter_id": chapter_id}, {"$set": update_field}
            )

            if result.modified_count > 0:
                logger.info(
                    f"✅ Audio saved to chapter: {chapter_id}, lang={language or 'default'}"
                )
                return True
            else:
                logger.warning(f"⚠️ Chapter not updated: {chapter_id}")
                return False

        except Exception as e:
            logger.error(f"❌ Failed to save audio to chapter: {e}", exc_info=True)
            raise

    def get_chapter_audio(
        self, chapter_id: str, language: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get audio config for chapter

        Args:
            chapter_id: Chapter ID
            language: Language code (optional)

        Returns:
            Audio config dict or None
        """
        try:
            chapter = self.book_chapters.find_one(
                {"chapter_id": chapter_id},
                {"audio_config": 1, "audio_translations": 1},
            )

            if not chapter:
                return None

            # Try language-specific audio first
            if language and "audio_translations" in chapter:
                lang_audio = chapter["audio_translations"].get(language)
                if lang_audio:
                    return lang_audio

            # Fallback to default audio
            return chapter.get("audio_config")

        except Exception as e:
            logger.error(f"❌ Failed to get chapter audio: {e}", exc_info=True)
            return None

    def get_user_audio_for_chapter(
        self, user_id: str, chapter_id: str, language: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get user's personal audio for a chapter (from library)

        Args:
            user_id: User ID
            chapter_id: Chapter ID
            language: Language code

        Returns:
            Library file record or None
        """
        try:
            if not self.library_manager:
                return None

            # Query library for user's audio linked to this chapter
            query = {
                "user_id": user_id,
                "file_type": "audio",
                "is_deleted": False,
                "metadata.linked_to.type": "book_chapter",
                "metadata.linked_to.chapter_id": chapter_id,
            }

            if language:
                query["metadata.linked_to.language"] = language

            files = (
                self.library_manager.library_files.find(query)
                .sort("created_at", -1)
                .limit(1)
            )

            file_list = list(files)
            if file_list:
                return file_list[0]

            return None

        except Exception as e:
            logger.error(f"❌ Failed to get user audio: {e}", exc_info=True)
            return None

    def delete_chapter_audio(
        self, chapter_id: str, language: Optional[str] = None
    ) -> bool:
        """
        Delete audio from chapter (archives in library)

        Args:
            chapter_id: Chapter ID
            language: Language code (optional)

        Returns:
            True if successful
        """
        try:
            if language:
                # Remove from audio_translations
                update_op = {"$unset": {f"audio_translations.{language}": ""}}
            else:
                # Remove root audio_config
                update_op = {"$unset": {"audio_config": ""}}

            result = self.book_chapters.update_one(
                {"chapter_id": chapter_id}, update_op
            )

            if result.modified_count > 0:
                logger.info(
                    f"✅ Audio deleted from chapter: {chapter_id}, lang={language or 'default'}"
                )
                return True

            return False

        except Exception as e:
            logger.error(f"❌ Failed to delete chapter audio: {e}", exc_info=True)
            raise
