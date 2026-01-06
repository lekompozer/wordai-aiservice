"""
ID generation utilities for unique identifiers
"""

import uuid
import secrets
from datetime import datetime


def generate_unique_id(length: int = 12) -> str:
    """
    Generate a unique ID using timestamp + random hex

    Args:
        length: Length of random part (default 12)

    Returns:
        Unique ID string
    """
    # Use current timestamp (milliseconds) + random hex
    timestamp = int(datetime.utcnow().timestamp() * 1000)
    random_part = secrets.token_hex(length // 2)
    return f"{timestamp}{random_part}"


def generate_short_id(length: int = 8) -> str:
    """
    Generate a short unique ID (URL-safe)

    Args:
        length: Length of ID (default 8)

    Returns:
        Short unique ID
    """
    return secrets.token_urlsafe(length)[:length]


def generate_uuid() -> str:
    """
    Generate a UUID4 string

    Returns:
        UUID string
    """
    return str(uuid.uuid4())
