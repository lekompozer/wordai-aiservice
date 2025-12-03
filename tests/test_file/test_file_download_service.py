"""
Test File Download Service
Test downloading and parsing files from R2
"""

import asyncio
from src.services.file_download_service import FileDownloadService


async def test_file_download_service():
    """
    Test file download and parsing

    Note: You'll need actual R2 URLs to test properly
    """
    print("=" * 60)
    print("Testing File Download Service")
    print("=" * 60)
    print()

    # Test user ID
    test_user_id = "test_user_download_001"

    # ===== Test 1: TXT file =====
    print("📝 Test 1: TXT file download and parse")
    print("-" * 60)

    # Example: Replace with actual R2 URL
    txt_url = "https://example.r2.url/test.txt"

    # Simulate with local test (if you have actual URL, replace this)
    print(f"URL: {txt_url}")
    print("Note: Replace with actual R2 URL to test properly")
    print()

    # ===== Test 2: DOCX file =====
    print("📄 Test 2: DOCX file download and parse")
    print("-" * 60)

    docx_url = "https://example.r2.url/test.docx"

    print(f"URL: {docx_url}")
    print("Expected: Download DOCX → Parse text → Return text content")
    print()

    # ===== Test 3: PDF file (non-Gemini) =====
    print("📕 Test 3: PDF file download and parse (for DeepSeek/ChatGPT)")
    print("-" * 60)

    pdf_url = "https://example.r2.url/test.pdf"

    text_content, temp_path = await FileDownloadService.download_and_parse_file(
        file_url=pdf_url, file_type="pdf", user_id=test_user_id, provider="deepseek"
    )

    print(f"URL: {pdf_url}")
    print("Expected: Download PDF → Parse text → Return text content")
    print(f"Result: text_content={text_content is not None}, temp_path={temp_path}")
    print()

    # ===== Test 4: PDF file (Gemini) =====
    print("🔥 Test 4: PDF file download (for Gemini - no parsing)")
    print("-" * 60)

    text_content, temp_path = await FileDownloadService.download_and_parse_file(
        file_url=pdf_url, file_type="pdf", user_id=test_user_id, provider="gemini"
    )

    print(f"URL: {pdf_url}")
    print("Expected: Download PDF → Return file path (no parsing)")
    print(f"Result: text_content={text_content}, temp_path={temp_path}")
    print()

    # ===== Test 5: Cleanup =====
    print("🗑️ Test 5: Cleanup temp files")
    print("-" * 60)

    await FileDownloadService._cleanup_user_temp_files(test_user_id)
    print("✅ Cleanup completed")
    print()

    # ===== Summary =====
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print()
    print("✅ Service Structure:")
    print("   1. download_and_parse_file() - Main entry point")
    print("   2. _download_file() - Download from R2 URL")
    print("   3. _parse_file() - Parse based on file type")
    print("   4. _parse_txt/docx/pdf() - Type-specific parsers")
    print("   5. _cleanup_user_temp_files() - Auto cleanup")
    print()
    print("📋 File Type Support:")
    print("   • TXT: Direct text extraction")
    print("   • DOCX: python-docx extraction")
    print("   • PDF (non-Gemini): PyPDF2 extraction")
    print("   • PDF (Gemini): File path only (no parsing)")
    print()
    print("🔄 Workflow:")
    print("   1. User sends message with file URL")
    print("   2. Backend downloads file from R2")
    print("   3. Backend parses to text (except PDF+Gemini)")
    print("   4. Inject text into currentFile.fullContent")
    print("   5. AI processes with full context")
    print("   6. Cleanup when user switches to new file")
    print()
    print("💡 Integration Points:")
    print("   • ai_chat.py: stream_chat_response()")
    print("   • ai_content_edit.py: edit_content_with_ai()")
    print("   • Check: if filePath.startswith('http')")
    print("   • Call: FileDownloadService.download_and_parse_file()")
    print()


if __name__ == "__main__":
    asyncio.run(test_file_download_service())
