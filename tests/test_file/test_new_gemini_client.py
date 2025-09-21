#!/usr/bin/env python3
"""
Test New Gemini Client File Upload
Test client file upload với API mới
"""
import asyncio
import sys
import os

# Add src to path
sys.path.append("src")

from core.config import APP_CONFIG


async def test_new_gemini_client():
    """Test Gemini client với file upload"""
    print("🧪 TESTING NEW GEMINI CLIENT FILE UPLOAD")
    print("=" * 50)

    try:
        # Import Gemini client
        from src.clients.gemini_client import GeminiClient

        # Get API key
        api_key = APP_CONFIG.get("gemini_api_key")
        if not api_key:
            print("❌ No Gemini API key found")
            return

        # Create Gemini client
        client = GeminiClient(api_key)
        print("✅ Gemini client created successfully")

        # Create test content
        test_content = """SAMPLE HOTEL DATA FOR TESTING

MERMAID SEASIDE HOTEL VUNG TAU
===============================

ROOMS AVAILABLE:
- Deluxe Sea View Room: 2,500,000 VND/night
  * Beautiful ocean view
  * King size bed
  * Balcony with sea view
  * Air conditioning, WiFi

- Superior Room: 1,800,000 VND/night
  * Garden view
  * Queen size bed
  * Modern amenities

- Standard Room: 1,200,000 VND/night
  * City view
  * Double bed
  * Basic amenities

HOTEL SERVICES:
- Spa & Wellness Center: 800,000 VND per session
- City Tour Package: 500,000 VND per person
- Seafood Restaurant: 300,000 VND per meal
- Airport Transfer: 150,000 VND

CONTACT INFORMATION:
- Phone: +84 123 456 789
- Email: booking@mermaidhotel.vn
- Address: 123 Beach Street, Vung Tau
"""

        # Convert to bytes
        test_content_bytes = test_content.encode("utf-8")

        try:
            print("📁 Testing file upload and analysis...")
            print(f"File size: {len(test_content_bytes)} bytes")

            # Test file upload using new client
            print("🚀 Uploading and analyzing file with Gemini...")

            response = await client.upload_file_and_analyze(
                file_content=test_content_bytes,
                file_name="test_hotel_data.txt",
                prompt="Hãy phân tích file này và trích xuất thông tin về các loại phòng nghỉ, giá cả và dịch vụ của khách sạn. Trả lời bằng tiếng Việt.",
            )

            print("✅ File upload and analysis successful!")
            print("📄 Analysis Result:")
            print("-" * 30)
            print(response[:500] + "..." if len(response) > 500 else response)

        except Exception as upload_error:
            print(f"❌ File upload test failed: {upload_error}")
            print(f"🔍 Error type: {type(upload_error)}")

            # Test basic chat to ensure client works
            print("\n🧪 Testing basic chat functionality...")
            try:
                basic_response = await client.chat_completion(
                    [
                        {
                            "role": "user",
                            "content": "Xin chào, bạn có thể giúp tôi không?",
                        }
                    ]
                )
                print(f"✅ Basic chat works: {basic_response[:100]}...")
            except Exception as chat_error:
                print(f"❌ Basic chat also failed: {chat_error}")

    except ImportError as e:
        print(f"❌ Import failed: {e}")
        print("Make sure src.clients.gemini_client is available")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        print(f"🔍 Error type: {type(e)}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_new_gemini_client())
