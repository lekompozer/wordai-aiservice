"""
Queue Manager Dependencies for API Routes
Dependencies cho Queue Manager trong API Routes
"""

import os
from typing import Optional
from src.queue.queue_manager import QueueManager
from src.utils.logger import setup_logger

logger = setup_logger()

# Global queue manager instances
_extraction_queue: Optional[QueueManager] = None
_document_queue: Optional[QueueManager] = None
_storage_queue: Optional[QueueManager] = None
_ai_editor_queue: Optional[QueueManager] = None
_slide_generation_queue: Optional[QueueManager] = None
_translation_queue: Optional[QueueManager] = None
_slide_format_queue: Optional[QueueManager] = None
_chapter_translation_queue: Optional[QueueManager] = None
_slide_narration_subtitle_queue: Optional[QueueManager] = None
_slide_narration_audio_queue: Optional[QueueManager] = None
_video_export_queue: Optional[QueueManager] = None
_lyria_music_queue: Optional[QueueManager] = None
_test_generation_queue: Optional[QueueManager] = None
_video_studio_queue: Optional[QueueManager] = None
_social_plan_queue: Optional[QueueManager] = None
_social_image_queue: Optional[QueueManager] = None


async def get_extraction_queue() -> QueueManager:
    """Get Redis queue manager for extraction tasks"""
    global _extraction_queue
    if _extraction_queue is None:
        redis_url = os.getenv("REDIS_URL", "redis://redis-server:6379")
        _extraction_queue = QueueManager(
            redis_url=redis_url,
            queue_name="products_extraction",
            status_expiry_hours=48,  # Keep status longer for extraction tasks
            max_queue_size=1000,
        )
        await _extraction_queue.connect()
        logger.info("✅ Extraction queue manager connected")
    return _extraction_queue


async def get_document_queue() -> QueueManager:
    """Get Redis queue manager for document processing tasks"""
    global _document_queue
    if _document_queue is None:
        redis_url = os.getenv("REDIS_URL", "redis://redis-server:6379")
        _document_queue = QueueManager(
            redis_url=redis_url,
            queue_name="document_processing",
            status_expiry_hours=24,  # Standard status retention
            max_queue_size=2000,
        )
        await _document_queue.connect()
        logger.info("✅ Document queue manager connected")
    return _document_queue


async def get_storage_queue() -> QueueManager:
    """Get Redis queue manager for storage processing tasks"""
    global _storage_queue
    if _storage_queue is None:
        redis_url = os.getenv("REDIS_URL", "redis://redis-server:6379")
        _storage_queue = QueueManager(
            redis_url=redis_url,
            queue_name="storage_processing",  # Separate queue for storage tasks
            status_expiry_hours=24,
            max_queue_size=1000,
        )
        await _storage_queue.connect()
        logger.info("✅ Storage queue manager connected")
    return _storage_queue


async def get_ai_editor_queue() -> QueueManager:
    """Get Redis queue manager for AI editor tasks (Edit/Format)"""
    global _ai_editor_queue
    if _ai_editor_queue is None:
        redis_url = os.getenv("REDIS_URL", "redis://redis-server:6379")
        _ai_editor_queue = QueueManager(
            redis_url=redis_url,
            queue_name="ai_editor",
            status_expiry_hours=24,
            max_queue_size=5000,  # Higher limit for AI tasks
        )
        await _ai_editor_queue.connect()
        logger.info("✅ AI Editor queue manager connected")
    return _ai_editor_queue


async def get_slide_generation_queue() -> QueueManager:
    """Get Redis queue manager for slide generation tasks"""
    global _slide_generation_queue
    if _slide_generation_queue is None:
        redis_url = os.getenv("REDIS_URL", "redis://redis-server:6379")
        _slide_generation_queue = QueueManager(
            redis_url=redis_url,
            queue_name="slide_generation",
            status_expiry_hours=48,  # Keep longer for slide analysis
            max_queue_size=3000,
        )
        await _slide_generation_queue.connect()
        logger.info("✅ Slide Generation queue manager connected")
    return _slide_generation_queue


async def get_translation_queue() -> QueueManager:
    """Get Redis queue manager for translation jobs"""
    global _translation_queue
    if _translation_queue is None:
        redis_url = os.getenv("REDIS_URL", "redis://redis-server:6379")
        _translation_queue = QueueManager(
            redis_url=redis_url,
            queue_name="translation_jobs",
            status_expiry_hours=48,  # Keep longer for book translations
            max_queue_size=2000,
        )
        await _translation_queue.connect()
        logger.info("✅ Translation queue manager connected")
    return _translation_queue


async def get_slide_format_queue() -> QueueManager:
    """Get Redis queue manager for slide AI format tasks"""
    global _slide_format_queue
    if _slide_format_queue is None:
        redis_url = os.getenv("REDIS_URL", "redis://redis-server:6379")
        _slide_format_queue = QueueManager(
            redis_url=redis_url,
            queue_name="slide_format",
            status_expiry_hours=24,
            max_queue_size=3000,
        )
        await _slide_format_queue.connect()
        logger.info("✅ Slide Format queue manager connected")
    return _slide_format_queue


async def get_chapter_translation_queue() -> QueueManager:
    """Get Redis queue manager for chapter translation tasks"""
    global _chapter_translation_queue
    if _chapter_translation_queue is None:
        redis_url = os.getenv("REDIS_URL", "redis://redis-server:6379")
        _chapter_translation_queue = QueueManager(
            redis_url=redis_url,
            queue_name="chapter_translation",
            status_expiry_hours=24,
            max_queue_size=2000,
        )
        await _chapter_translation_queue.connect()
        logger.info("✅ Chapter Translation queue manager connected")
    return _chapter_translation_queue


async def get_slide_narration_subtitle_queue() -> QueueManager:
    """Get Redis queue manager for slide narration subtitle generation"""
    global _slide_narration_subtitle_queue
    if _slide_narration_subtitle_queue is None:
        redis_url = os.getenv("REDIS_URL", "redis://redis-server:6379")
        _slide_narration_subtitle_queue = QueueManager(
            redis_url=redis_url,
            queue_name="slide_narration_subtitle",
            status_expiry_hours=24,
            max_queue_size=1000,
        )
        await _slide_narration_subtitle_queue.connect()
        logger.info("✅ Slide Narration Subtitle queue manager connected")
    return _slide_narration_subtitle_queue


async def get_slide_narration_audio_queue() -> QueueManager:
    """Get Redis queue manager for slide narration audio generation"""
    global _slide_narration_audio_queue
    if _slide_narration_audio_queue is None:
        redis_url = os.getenv("REDIS_URL", "redis://redis-server:6379")
        _slide_narration_audio_queue = QueueManager(
            redis_url=redis_url,
            queue_name="slide_narration_audio",
            status_expiry_hours=24,
            max_queue_size=1000,
        )
        await _slide_narration_audio_queue.connect()
        logger.info("✅ Slide Narration Audio queue manager connected")
    return _slide_narration_audio_queue


async def get_video_export_queue() -> QueueManager:
    """Get Redis queue manager for video export tasks"""
    global _video_export_queue
    if _video_export_queue is None:
        redis_url = os.getenv("REDIS_URL", "redis://redis-server:6379")
        _video_export_queue = QueueManager(
            redis_url=redis_url,
            queue_name="video_export",
            status_expiry_hours=24,  # Keep job status for 24h
            max_queue_size=500,  # Limit concurrent exports
        )
        await _video_export_queue.connect()
        logger.info("✅ Video Export queue manager connected")
    return _video_export_queue


async def get_lyria_music_queue() -> QueueManager:
    """Get Redis queue manager for Lyria music generation tasks"""
    global _lyria_music_queue
    if _lyria_music_queue is None:
        redis_url = os.getenv("REDIS_URL", "redis://redis-server:6379")
        _lyria_music_queue = QueueManager(
            redis_url=redis_url,
            queue_name="lyria_music",
            status_expiry_hours=24,  # Standard status retention
            max_queue_size=1000,
        )
        await _lyria_music_queue.connect()
        logger.info("✅ Lyria Music queue manager connected")
    return _lyria_music_queue


async def get_test_generation_queue() -> QueueManager:
    """Get Redis queue manager for test generation tasks (listening, grammar, vocabulary)"""
    global _test_generation_queue
    if _test_generation_queue is None:
        redis_url = os.getenv("REDIS_URL", "redis://redis-server:6379")
        _test_generation_queue = QueueManager(
            redis_url=redis_url,
            queue_name="test_generation",
            status_expiry_hours=48,  # Keep longer for test analysis
            max_queue_size=2000,
        )
        await _test_generation_queue.connect()
        logger.info("✅ Test Generation queue manager connected")
    return _test_generation_queue


async def get_video_studio_queue() -> QueueManager:
    """Get Redis queue manager for AI Video Studio tasks (story/narration/script/image/tts)"""
    global _video_studio_queue
    if _video_studio_queue is None:
        redis_url = os.getenv("REDIS_URL", "redis://redis-server:6379")
        _video_studio_queue = QueueManager(
            redis_url=redis_url,
            queue_name="video_studio",
            status_expiry_hours=48,  # Keep longer — AI jobs can take time
            max_queue_size=1000,
        )
        await _video_studio_queue.connect()
        logger.info("✅ Video Studio queue manager connected")
    return _video_studio_queue


async def get_social_plan_queue() -> QueueManager:
    """Get Redis queue manager for social marketing plan generation tasks"""
    global _social_plan_queue
    if _social_plan_queue is None:
        redis_url = os.getenv("REDIS_URL", "redis://redis-server:6379")
        _social_plan_queue = QueueManager(
            redis_url=redis_url,
            queue_name="social_plan_jobs",
            status_expiry_hours=48,
            max_queue_size=500,
        )
        await _social_plan_queue.connect()
        logger.info("✅ Social Plan queue manager connected")
    return _social_plan_queue


async def get_social_image_queue() -> QueueManager:
    """Get Redis queue manager for social plan image generation tasks"""
    global _social_image_queue
    if _social_image_queue is None:
        redis_url = os.getenv("REDIS_URL", "redis://redis-server:6379")
        _social_image_queue = QueueManager(
            redis_url=redis_url,
            queue_name="social_image_jobs",
            status_expiry_hours=48,
            max_queue_size=1000,
        )
        await _social_image_queue.connect()
        logger.info("✅ Social Image queue manager connected")
    return _social_image_queue


async def cleanup_queues():
    """Cleanup queue connections on shutdown"""
    global _extraction_queue, _document_queue, _storage_queue
    global _ai_editor_queue, _slide_generation_queue, _translation_queue
    global _slide_format_queue, _chapter_translation_queue
    global _slide_narration_subtitle_queue, _slide_narration_audio_queue
    global _video_export_queue, _lyria_music_queue, _test_generation_queue, _video_studio_queue
    global _social_plan_queue, _social_image_queue

    if _extraction_queue:
        await _extraction_queue.disconnect()
        _extraction_queue = None
        logger.info("🧹 Extraction queue disconnected")

    if _document_queue:
        await _document_queue.disconnect()
        _document_queue = None
        logger.info("🧹 Document queue disconnected")

    if _storage_queue:
        await _storage_queue.disconnect()
        _storage_queue = None
        logger.info("🧹 Storage queue disconnected")

    if _ai_editor_queue:
        await _ai_editor_queue.disconnect()
        _ai_editor_queue = None
        logger.info("🧹 AI Editor queue disconnected")

    if _slide_generation_queue:
        await _slide_generation_queue.disconnect()
        _slide_generation_queue = None
        logger.info("🧹 Slide Generation queue disconnected")

    if _translation_queue:
        await _translation_queue.disconnect()
        _translation_queue = None
        logger.info("🧹 Translation queue disconnected")

    if _slide_format_queue:
        await _slide_format_queue.disconnect()
        _slide_format_queue = None
        logger.info("🧹 Slide Format queue disconnected")

    if _chapter_translation_queue:
        await _chapter_translation_queue.disconnect()
        _chapter_translation_queue = None
        logger.info("🧹 Chapter Translation queue disconnected")

    if _slide_narration_subtitle_queue:
        await _slide_narration_subtitle_queue.disconnect()
        _slide_narration_subtitle_queue = None
        logger.info("🧹 Slide Narration Subtitle queue disconnected")

    if _slide_narration_audio_queue:
        await _slide_narration_audio_queue.disconnect()
        _slide_narration_audio_queue = None
        logger.info("🧹 Slide Narration Audio queue disconnected")

    if _video_export_queue:
        await _video_export_queue.disconnect()
        _video_export_queue = None
        logger.info("🧹 Video Export queue disconnected")

    if _lyria_music_queue:
        await _lyria_music_queue.disconnect()
        _lyria_music_queue = None
        logger.info("🧹 Lyria Music queue disconnected")

    if _test_generation_queue:
        await _test_generation_queue.disconnect()
        _test_generation_queue = None
        logger.info("🧹 Test Generation queue disconnected")

    if _video_studio_queue:
        await _video_studio_queue.disconnect()
        _video_studio_queue = None
        logger.info("🧹 Video Studio queue disconnected")

    if _social_plan_queue:
        await _social_plan_queue.disconnect()
        _social_plan_queue = None
        logger.info("🧹 Social Plan queue disconnected")

    if _social_image_queue:
        await _social_image_queue.disconnect()
        _social_image_queue = None
        logger.info("🧹 Social Image queue disconnected")
