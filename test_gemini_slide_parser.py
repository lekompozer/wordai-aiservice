"""
Test Gemini Slide Parser with direct PDF support

Usage:
    python test_gemini_slide_parser.py <file_id> <firebase_token>

Example:
    python test_gemini_slide_parser.py file_abc123 eyJhbGc...
"""

import asyncio
import sys
import httpx
import json
from typing import Optional


async def test_gemini_parser(
    file_id: str, token: str, base_url: str = "http://localhost:5001"
):
    """
    Test Gemini slide parser endpoint

    Args:
        file_id: File ID from user_files collection
        token: Firebase authentication token
        base_url: API base URL (default: localhost:5001)
    """

    url = f"{base_url}/api/gemini/slides/parse-file"

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    payload = {"file_id": file_id}

    print(f"🎬 Testing Gemini Slide Parser...")
    print(f"📄 File ID: {file_id}")
    print(f"🔗 URL: {url}")
    print(f"⏱️  Starting request...\n")

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)

            print(f"📊 Status Code: {response.status_code}")

            if response.status_code == 200:
                data = response.json()

                print(f"\n✅ SUCCESS!")
                print(f"📁 File: {data.get('file_name')}")
                print(f"📊 Total Slides: {data.get('total_slides')}")
                print(f"\n{'='*80}")

                # Display each slide
                slides = data.get("slides", [])
                for slide in slides:
                    slide_num = slide.get("slide_number")
                    html_len = len(slide.get("html_content", ""))
                    notes = slide.get("notes")

                    print(f"\n🎬 Slide {slide_num}:")
                    print(f"   HTML Length: {html_len} chars")
                    if notes:
                        print(f"   Notes: {notes}")

                    # Show first 200 chars of HTML
                    html_preview = slide.get("html_content", "")[:200]
                    print(f"   Preview: {html_preview}...")

                # Save full response to file
                output_file = f"test_gemini_output_{file_id}.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

                print(f"\n{'='*80}")
                print(f"💾 Full response saved to: {output_file}")

                # Save HTML files for each slide
                for slide in slides:
                    slide_num = slide.get("slide_number")
                    html_content = slide.get("html_content", "")
                    html_file = f"test_slide_{slide_num}.html"

                    with open(html_file, "w", encoding="utf-8") as f:
                        f.write(html_content)

                    print(f"📄 Slide {slide_num} HTML saved to: {html_file}")

                return True

            else:
                print(f"\n❌ FAILED!")
                print(f"Response: {response.text}")
                return False

        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback

            traceback.print_exc()
            return False


async def test_upload_direct(
    pdf_path: str, token: str, base_url: str = "http://localhost:5001"
):
    """
    Test direct upload endpoint (for testing without R2)

    Args:
        pdf_path: Local path to PDF file
        token: Firebase authentication token
        base_url: API base URL
    """

    url = f"{base_url}/api/gemini/slides/parse-upload"

    headers = {"Authorization": f"Bearer {token}"}

    print(f"🎬 Testing Direct Upload Parser...")
    print(f"📄 File: {pdf_path}")
    print(f"🔗 URL: {url}")
    print(f"⏱️  Starting upload...\n")

    with open(pdf_path, "rb") as f:
        files = {"file": (pdf_path, f, "application/pdf")}

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(url, headers=headers, files=files)

                print(f"📊 Status Code: {response.status_code}")

                if response.status_code == 200:
                    data = response.json()

                    print(f"\n✅ SUCCESS!")
                    print(f"📁 File: {data.get('file_name')}")
                    print(f"📊 Total Slides: {data.get('total_slides')}")

                    # Save results
                    output_file = "test_gemini_upload_output.json"
                    with open(output_file, "w", encoding="utf-8") as out:
                        json.dump(data, out, indent=2, ensure_ascii=False)

                    print(f"\n💾 Full response saved to: {output_file}")
                    return True

                else:
                    print(f"\n❌ FAILED!")
                    print(f"Response: {response.text}")
                    return False

            except Exception as e:
                print(f"\n❌ ERROR: {e}")
                import traceback

                traceback.print_exc()
                return False


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("❌ Missing arguments!")
        print("\nUsage:")
        print("  Test with file_id:")
        print("    python test_gemini_slide_parser.py <file_id> <token>")
        print("\n  Test with local file:")
        print("    python test_gemini_slide_parser.py --upload <pdf_path> <token>")
        print("\nExample:")
        print("    python test_gemini_slide_parser.py file_abc123 eyJhbGc...")
        print("    python test_gemini_slide_parser.py --upload sample.pdf eyJhbGc...")
        sys.exit(1)

    if sys.argv[1] == "--upload":
        # Direct upload mode
        if len(sys.argv) < 4:
            print("❌ Missing PDF path or token!")
            sys.exit(1)
        pdf_path = sys.argv[2]
        token = sys.argv[3]
        base_url = sys.argv[4] if len(sys.argv) > 4 else "http://localhost:5001"

        result = asyncio.run(test_upload_direct(pdf_path, token, base_url))
    else:
        # File ID mode
        file_id = sys.argv[1]
        token = sys.argv[2]
        base_url = sys.argv[3] if len(sys.argv) > 3 else "http://localhost:5001"

        result = asyncio.run(test_gemini_parser(file_id, token, base_url))

    sys.exit(0 if result else 1)
