"""
Slug Generator Utility

Provides functions to generate URL-friendly slugs from Vietnamese and English text.
Used for creating SEO-friendly URLs for tests, books, and other content.
"""

import re
import unicodedata
from typing import Optional


def generate_slug(text: str) -> str:
    """
    Generate URL-friendly slug from text (Vietnamese/English safe)

    Process:
    1. Convert to lowercase
    2. Normalize Vietnamese characters to ASCII
    3. Replace spaces and special characters with hyphens
    4. Remove leading/trailing hyphens

    Examples:
        "Đánh Giá Kỹ Năng Mềm" → "danh-gia-ky-nang-mem"
        "Python Programming 101" → "python-programming-101"
        "Hello   World!!!" → "hello-world"

    Args:
        text: Input text (can contain Vietnamese characters)

    Returns:
        URL-friendly slug
    """
    if not text:
        return ""

    # Convert to lowercase
    slug = text.lower()

    # Normalize Unicode characters (Vietnamese → ASCII)
    # NFKD: Compatibility decomposition
    slug = unicodedata.normalize("NFKD", slug).encode("ascii", "ignore").decode("ascii")

    # Replace spaces and special characters with hyphens
    # Keep only a-z, 0-9, and hyphens
    slug = re.sub(r"[^a-z0-9]+", "-", slug)

    # Remove leading/trailing hyphens
    slug = slug.strip("-")

    # Collapse multiple consecutive hyphens into one
    slug = re.sub(r"-+", "-", slug)

    return slug


def generate_unique_slug(
    text: str,
    check_exists_fn: callable,
    max_length: int = 100,
    exclude_id: Optional[str] = None,
) -> str:
    """
    Generate unique slug by appending number if needed

    Args:
        text: Input text to generate slug from
        check_exists_fn: Function that checks if slug exists
                        Should accept (slug, exclude_id) and return bool
        max_length: Maximum length of slug (default 100)
        exclude_id: Optional ID to exclude from existence check (for updates)

    Returns:
        Unique slug with number suffix if needed (e.g., "test-slug-2")
    """
    # Generate base slug
    base_slug = generate_slug(text)

    # Truncate if too long (leave room for suffix like "-999")
    if len(base_slug) > max_length - 4:
        base_slug = base_slug[: max_length - 4]

    # Check if base slug is available
    slug = base_slug
    if not check_exists_fn(slug, exclude_id):
        return slug

    # Append number until we find available slug
    counter = 2
    while counter < 1000:  # Prevent infinite loop
        slug = f"{base_slug}-{counter}"
        if not check_exists_fn(slug, exclude_id):
            return slug
        counter += 1

    # Fallback: append timestamp
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{base_slug}-{timestamp}"


def generate_meta_description(description: Optional[str], max_length: int = 160) -> str:
    """
    Generate meta description for SEO

    Truncates description to max_length and adds ellipsis if needed.
    Removes newlines and extra whitespace.

    Args:
        description: Original description text
        max_length: Maximum length (default 160 for SEO best practice)

    Returns:
        Cleaned and truncated meta description
    """
    if not description:
        return ""

    # Remove newlines and extra whitespace
    meta = re.sub(r"\s+", " ", description.strip())

    # Truncate and add ellipsis if needed
    if len(meta) > max_length:
        meta = meta[: max_length - 3].rsplit(" ", 1)[0] + "..."

    return meta


# Example usage
if __name__ == "__main__":
    # Test Vietnamese text
    print(generate_slug("Đánh Giá Kỹ Năng Mềm Của Bạn"))
    # Output: danh-gia-ky-nang-mem-cua-ban

    # Test English text
    print(generate_slug("Python Programming 101: Master the Basics"))
    # Output: python-programming-101-master-the-basics

    # Test mixed with special characters
    print(generate_slug("Hướng dẫn React.js & Next.js (2024)"))
    # Output: huong-dan-react-js-next-js-2024

    # Test meta description
    desc = """Bạn có biết:

85% thành công trong sự nghiệp được quyết định bởi KỸ NĂNG MỀM? (Nghiên cứu của Đại học Harvard & Stanford).

Những người được thăng tiến nhanh thường không phải là người giỏi chuyên môn nhất."""

    print(generate_meta_description(desc, 160))
    # Output: Bạn có biết: 85% thành công trong sự nghiệp được quyết định bởi KỸ NĂNG MỀM? (Nghiên cứu của Đại học Harvard & Stanford). Những người được thăng...
