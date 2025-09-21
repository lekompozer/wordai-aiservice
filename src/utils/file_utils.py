"""
File utilities for document generation
"""

import os
from pathlib import Path
from typing import Optional


def ensure_directory_exists(directory_path: str) -> None:
    """Ensure directory exists, create if not"""
    Path(directory_path).mkdir(parents=True, exist_ok=True)


def get_file_size(file_path: str) -> Optional[int]:
    """Get file size in bytes"""
    try:
        if os.path.exists(file_path):
            return os.path.getsize(file_path)
        return None
    except Exception:
        return None


def is_file_exists(file_path: str) -> bool:
    """Check if file exists"""
    return os.path.exists(file_path) and os.path.isfile(file_path)


def get_file_extension(file_path: str) -> str:
    """Get file extension"""
    return Path(file_path).suffix.lower()


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage"""
    # Remove or replace unsafe characters
    unsafe_chars = '<>:"/\\|?*'
    for char in unsafe_chars:
        filename = filename.replace(char, "_")
    return filename.strip()
