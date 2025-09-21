"""
Workers package initialization
"""

# Import only the main classes we actually use
from .document_processor import AIDocumentProcessor

__all__ = [
    "AIDocumentProcessor"
]