"""
File Cache Manager for Document Chat
Manages temporary file caching for R2 files during conversation sessions
"""

import os
import hashlib
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime, timedelta
import asyncio
from src.utils.logger import setup_logger

logger = setup_logger()


class FileCacheManager:
    """
    Manages file cache for document chat sessions

    Cache Strategy:
    - Files are cached per conversation_id
    - Cache is cleared when conversation ends
    - Multiple users can share same file (different cache entries)
    - Cache expires after 24 hours
    """

    def __init__(self, cache_dir: str = "temp_files/chat_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # In-memory cache metadata
        # Structure: {conversation_id: {file_id: {path, cached_at, file_type}}}
        self.cache_metadata: Dict[str, Dict[str, Dict]] = {}

        # Cache expiry time
        self.cache_expiry_hours = 24

        logger.info(f"📦 FileCacheManager initialized at {self.cache_dir}")

    def _get_cache_path(
        self, file_id: str, conversation_id: str, extension: str = ""
    ) -> Path:
        """
        Generate cache file path

        Format: temp_files/chat_cache/{conversation_id}/{file_id_hash}.{ext}
        """
        # Create conversation subdirectory
        conv_dir = self.cache_dir / conversation_id
        conv_dir.mkdir(parents=True, exist_ok=True)

        # Generate safe filename
        file_hash = hashlib.md5(file_id.encode()).hexdigest()[:12]
        filename = f"{file_id}_{file_hash}{extension}"

        return conv_dir / filename

    def is_cached(self, file_id: str, conversation_id: str) -> bool:
        """
        Check if file is cached for this conversation

        Returns:
            True if cached and not expired
        """
        try:
            # Check in-memory metadata
            if conversation_id not in self.cache_metadata:
                return False

            if file_id not in self.cache_metadata[conversation_id]:
                return False

            cache_info = self.cache_metadata[conversation_id][file_id]
            cache_path = Path(cache_info["path"])

            # Check if file exists
            if not cache_path.exists():
                logger.warning(f"⚠️ Cache file missing: {cache_path}")
                # Clean up metadata
                del self.cache_metadata[conversation_id][file_id]
                return False

            # Check expiry
            cached_at = cache_info["cached_at"]
            expiry_time = cached_at + timedelta(hours=self.cache_expiry_hours)

            if datetime.now() > expiry_time:
                logger.info(f"🕒 Cache expired for {file_id}")
                self.clear_file_cache(file_id, conversation_id)
                return False

            logger.info(f"✅ Cache hit: {file_id} in conversation {conversation_id}")
            return True

        except Exception as e:
            logger.error(f"❌ Error checking cache: {e}")
            return False

    def get_cached_path(self, file_id: str, conversation_id: str) -> Optional[str]:
        """
        Get cached file path if available

        Returns:
            Absolute path to cached file or None
        """
        try:
            if not self.is_cached(file_id, conversation_id):
                return None

            cache_info = self.cache_metadata[conversation_id][file_id]
            cache_path = cache_info["path"]

            logger.info(f"📄 Retrieved cached file: {cache_path}")
            return str(cache_path)

        except Exception as e:
            logger.error(f"❌ Error getting cached path: {e}")
            return None

    def add_to_cache(
        self,
        file_id: str,
        conversation_id: str,
        local_path: str,
        file_type: str,
        metadata: Optional[Dict] = None,
    ) -> bool:
        """
        Add file to cache

        Args:
            file_id: File identifier
            conversation_id: Conversation session ID
            local_path: Path to downloaded file
            file_type: File type (pdf, docx, txt)
            metadata: Additional metadata

        Returns:
            True if added successfully
        """
        try:
            # Initialize conversation cache if needed
            if conversation_id not in self.cache_metadata:
                self.cache_metadata[conversation_id] = {}

            # Store metadata
            self.cache_metadata[conversation_id][file_id] = {
                "path": local_path,
                "cached_at": datetime.now(),
                "file_type": file_type,
                "metadata": metadata or {},
            }

            logger.info(
                f"📦 Added to cache: {file_id} → {local_path} "
                f"(conversation: {conversation_id})"
            )
            return True

        except Exception as e:
            logger.error(f"❌ Error adding to cache: {e}")
            return False

    def clear_file_cache(self, file_id: str, conversation_id: str) -> bool:
        """
        Clear specific file from cache

        Returns:
            True if cleared successfully
        """
        try:
            if conversation_id not in self.cache_metadata:
                return True

            if file_id not in self.cache_metadata[conversation_id]:
                return True

            cache_info = self.cache_metadata[conversation_id][file_id]
            cache_path = Path(cache_info["path"])

            # Delete file
            if cache_path.exists():
                cache_path.unlink()
                logger.info(f"🗑️ Deleted cached file: {cache_path}")

            # Remove from metadata
            del self.cache_metadata[conversation_id][file_id]

            return True

        except Exception as e:
            logger.error(f"❌ Error clearing file cache: {e}")
            return False

    def clear_conversation_cache(self, conversation_id: str) -> bool:
        """
        Clear all cached files for a conversation

        Called when conversation session ends

        Returns:
            True if cleared successfully
        """
        try:
            if conversation_id not in self.cache_metadata:
                logger.info(f"ℹ️ No cache for conversation {conversation_id}")
                return True

            # Delete all files in conversation
            file_count = 0
            for file_id in list(self.cache_metadata[conversation_id].keys()):
                if self.clear_file_cache(file_id, conversation_id):
                    file_count += 1

            # Delete conversation directory
            conv_dir = self.cache_dir / conversation_id
            if conv_dir.exists():
                try:
                    conv_dir.rmdir()
                    logger.info(f"🗑️ Deleted conversation cache directory: {conv_dir}")
                except OSError:
                    # Directory not empty - that's ok
                    pass

            # Remove from metadata
            del self.cache_metadata[conversation_id]

            logger.info(
                f"✅ Cleared conversation cache: {conversation_id} "
                f"({file_count} files)"
            )
            return True

        except Exception as e:
            logger.error(f"❌ Error clearing conversation cache: {e}")
            return False

    def cleanup_expired_cache(self) -> int:
        """
        Clean up all expired cache entries

        Returns:
            Number of files cleaned up
        """
        try:
            cleaned_count = 0
            now = datetime.now()

            # Check all conversations
            for conversation_id in list(self.cache_metadata.keys()):
                for file_id in list(self.cache_metadata[conversation_id].keys()):
                    cache_info = self.cache_metadata[conversation_id][file_id]
                    cached_at = cache_info["cached_at"]
                    expiry_time = cached_at + timedelta(hours=self.cache_expiry_hours)

                    if now > expiry_time:
                        if self.clear_file_cache(file_id, conversation_id):
                            cleaned_count += 1

            if cleaned_count > 0:
                logger.info(f"🧹 Cleaned up {cleaned_count} expired cache files")

            return cleaned_count

        except Exception as e:
            logger.error(f"❌ Error during cache cleanup: {e}")
            return 0

    def get_cache_stats(self) -> Dict:
        """
        Get cache statistics

        Returns:
            Dict with cache stats
        """
        try:
            total_files = sum(len(files) for files in self.cache_metadata.values())
            total_conversations = len(self.cache_metadata)

            # Calculate total cache size
            total_size = 0
            for conv_files in self.cache_metadata.values():
                for file_info in conv_files.values():
                    cache_path = Path(file_info["path"])
                    if cache_path.exists():
                        total_size += cache_path.stat().st_size

            return {
                "total_files": total_files,
                "total_conversations": total_conversations,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "cache_dir": str(self.cache_dir),
            }

        except Exception as e:
            logger.error(f"❌ Error getting cache stats: {e}")
            return {}


# Global cache manager instance
file_cache = FileCacheManager()


# Utility functions for easy import
def is_file_cached(file_id: str, conversation_id: str) -> bool:
    """Check if file is cached"""
    return file_cache.is_cached(file_id, conversation_id)


def get_cached_file(file_id: str, conversation_id: str) -> Optional[str]:
    """Get cached file path"""
    return file_cache.get_cached_path(file_id, conversation_id)


def cache_file(
    file_id: str,
    conversation_id: str,
    local_path: str,
    file_type: str,
    metadata: Optional[Dict] = None,
) -> bool:
    """Add file to cache"""
    return file_cache.add_to_cache(
        file_id, conversation_id, local_path, file_type, metadata
    )


def clear_conversation_cache(conversation_id: str) -> bool:
    """Clear all cached files for conversation"""
    return file_cache.clear_conversation_cache(conversation_id)


def cleanup_expired_cache() -> int:
    """Clean up expired cache entries"""
    return file_cache.cleanup_expired_cache()
