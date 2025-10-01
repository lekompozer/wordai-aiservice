"""
HTML Sanitization Service
Service for sanitizing HTML content from AI responses
"""

import re
from typing import Set, Tuple
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)


class HTMLSanitizationService:
    """Service for sanitizing HTML content from AI responses"""

    ALLOWED_TAGS: Set[str] = {
        # Text formatting
        "p",
        "br",
        "span",
        "strong",
        "b",
        "em",
        "i",
        "u",
        "s",
        "mark",
        "code",
        "pre",
        # Headings
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        # Lists
        "ul",
        "ol",
        "li",
        # Tables
        "table",
        "thead",
        "tbody",
        "tfoot",
        "tr",
        "th",
        "td",
        # Links & Media
        "a",
        "img",
        # Structural
        "div",
        "blockquote",
        "hr",
    }

    ALLOWED_ATTRIBUTES: Set[str] = {"class", "href", "src", "alt", "colspan", "rowspan"}

    FORBIDDEN_TAGS: Set[str] = {
        "script",
        "iframe",
        "object",
        "embed",
        "form",
        "input",
        "button",
        "select",
        "style",
    }

    FORBIDDEN_ATTRS_PATTERN = re.compile(
        r"(on\w+|style|javascript:|data:text/html)", re.IGNORECASE
    )

    @classmethod
    def sanitize(cls, html: str) -> str:
        """
        Sanitize HTML content

        Args:
            html: Raw HTML string

        Returns:
            Sanitized HTML string

        Raises:
            ValueError: If HTML contains forbidden elements
        """
        try:
            # Parse HTML
            soup = BeautifulSoup(html, "html.parser")

            # Remove forbidden tags
            for tag in cls.FORBIDDEN_TAGS:
                for element in soup.find_all(tag):
                    element.decompose()

            # Process all tags
            for element in soup.find_all():
                # Check if tag is allowed
                if element.name not in cls.ALLOWED_TAGS:
                    # Replace with span or remove
                    if element.string:
                        element.replace_with(element.string)
                    else:
                        element.unwrap()
                    continue

                # Filter attributes
                attrs_to_remove = []
                for attr in list(element.attrs.keys()):
                    if attr not in cls.ALLOWED_ATTRIBUTES:
                        attrs_to_remove.append(attr)
                    elif cls.FORBIDDEN_ATTRS_PATTERN.search(str(element[attr])):
                        attrs_to_remove.append(attr)
                        logger.warning(
                            f"Removed forbidden attribute: {attr}={element[attr]}"
                        )

                for attr in attrs_to_remove:
                    del element[attr]

                # Special validation for links
                if element.name == "a" and "href" in element.attrs:
                    href = element["href"]
                    if not (href.startswith("http://") or href.startswith("https://")):
                        del element["href"]
                        logger.warning(f"Removed invalid href: {href}")

            sanitized = str(soup)

            # Final safety check
            if "<script" in sanitized.lower() or "javascript:" in sanitized.lower():
                raise ValueError("Potentially unsafe content detected")

            return sanitized

        except Exception as e:
            logger.error(f"HTML sanitization failed: {e}")
            raise ValueError(f"Invalid HTML content: {str(e)}")

    @classmethod
    def validate_and_sanitize(cls, html: str) -> Tuple[bool, str, str]:
        """
        Validate and sanitize HTML

        Returns:
            (is_valid, sanitized_html, error_message)
        """
        try:
            sanitized = cls.sanitize(html)
            return True, sanitized, ""
        except Exception as e:
            return False, "", str(e)

    @classmethod
    def extract_text_from_html(cls, html: str) -> str:
        """Extract plain text from HTML"""
        try:
            soup = BeautifulSoup(html, "html.parser")
            return soup.get_text(separator=" ", strip=True)
        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            return html
