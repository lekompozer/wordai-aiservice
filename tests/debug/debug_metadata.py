#!/usr/bin/env python3
"""
Debug metadata để xem server nhận được gì
"""
import asyncio
import sys

sys.path.append("/Users/user/Code/ai-chatbot-rag")

from pathlib import Path


def test_metadata_extraction():
    """Test metadata extraction logic"""

    print("🔍 TESTING METADATA EXTRACTION")
    print("=" * 50)

    # Test cases
    test_cases = [
        {
            "name": "Case 1: original_name in metadata",
            "metadata": {
                "original_name": "20250714_103032_ivy-fashion-products.csv",
                "industry": "fashion",
            },
            "file_metadata": {
                "filename": "different-name.txt",
                "content_type": "text/csv",
            },
        },
        {
            "name": "Case 2: No original_name",
            "metadata": {"industry": "fashion"},
            "file_metadata": {
                "filename": "ivy-fashion-products.csv",
                "content_type": "text/csv",
            },
        },
        {
            "name": "Case 3: filename in file_metadata",
            "metadata": {"industry": "fashion", "filename": "metadata-filename.csv"},
            "file_metadata": {
                "filename": "file-metadata-filename.csv",
                "content_type": "text/csv",
            },
        },
    ]

    for case in test_cases:
        print(f"\n📋 {case['name']}")
        print("-" * 30)

        metadata = case["metadata"]
        file_metadata = case["file_metadata"]

        # Test current logic
        file_extension_current = Path(metadata.get("original_name", "")).suffix.lower()
        print(f"Current logic (original_name): '{file_extension_current}'")

        # Test alternative logic
        filename = metadata.get("original_name") or file_metadata.get("filename", "")
        file_extension_alt = Path(filename).suffix.lower()
        print(f"Alternative logic (filename): '{file_extension_alt}'")

        # Test content_type approach
        content_type = file_metadata.get("content_type", "")
        print(f"Content-Type: '{content_type}'")

        # Simulate AI provider selection
        text_extensions = [".txt", ".json", ".csv"]

        if file_extension_current in text_extensions:
            provider_current = "deepseek"
        else:
            provider_current = "chatgpt"

        if file_extension_alt in text_extensions:
            provider_alt = "deepseek"
        else:
            provider_alt = "chatgpt"

        print(f"AI Provider (current): {provider_current}")
        print(f"AI Provider (alternative): {provider_alt}")

        if content_type.startswith("text/") or content_type in ["application/json"]:
            provider_content = "deepseek"
        else:
            provider_content = "chatgpt"
        print(f"AI Provider (content-type): {provider_content}")


if __name__ == "__main__":
    test_metadata_extraction()
