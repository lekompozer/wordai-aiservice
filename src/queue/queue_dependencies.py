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


async def get_extraction_queue() -> QueueManager:
    """Get Redis queue manager for extraction tasks"""
    global _extraction_queue
    if _extraction_queue is None:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
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
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
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
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        _storage_queue = QueueManager(
            redis_url=redis_url,
            queue_name="storage_processing",  # Separate queue for storage tasks
            status_expiry_hours=24,
            max_queue_size=1000,
        )
        await _storage_queue.connect()
        logger.info("✅ Storage queue manager connected")
    return _storage_queue


async def cleanup_queues():
    """Cleanup queue connections on shutdown"""
    global _extraction_queue, _document_queue, _storage_queue

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
