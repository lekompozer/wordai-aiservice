#!/usr/bin/env python3
"""
Test YouTube audio download + Gemini audio understanding
Usage: python test_youtube_audio_gemini.py <youtube_url>
"""
import asyncio
import os
import sys
import tempfile
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv("development.env")

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import yt_dlp
from google import genai
from google.genai import types


async def download_youtube_audio(youtube_url: str) -> str:
    """Download YouTube audio using yt-dlp (no conversion needed)."""
    print(f"\n📥 Downloading audio from: {youtube_url}")

    # Create temp file with .webm extension (common audio format from YouTube)
    temp_fd, temp_path = tempfile.mkstemp(suffix=".webm", prefix="yt_audio_")
    os.close(temp_fd)

    ydl_opts = {
        "format": "bestaudio/best",  # Get best audio stream (usually webm/opus)
        "outtmpl": temp_path,
        "quiet": False,  # Show progress
        "no_warnings": False,
        "nocache": True,  # Force fresh download
        "overwrites": True,  # Overwrite existing files
        # Add headers to bypass YouTube blocks
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-us,en;q=0.5",
        },
    }

    def _download():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=True)
            return info

    info = await asyncio.to_thread(_download)

    # Check different possible paths
    possible_paths = [
        temp_path,
        f"{temp_path}.webm",
        f"{temp_path}.m4a",
        f"{temp_path}.opus",
    ]

    final_path = None
    for path in possible_paths:
        if os.path.exists(path):
            final_path = path
            break

    if not final_path:
        raise FileNotFoundError(f"Download failed: no audio file found at {temp_path}")

    file_size = os.path.getsize(final_path) / (1024 * 1024)  # MB
    print(f"✅ Downloaded: {final_path}")
    print(f"   Size: {file_size:.2f} MB")
    print(f"   Title: {info.get('title', 'Unknown')}")
    print(f"   Duration: {info.get('duration', 0)} seconds")

    return final_path


async def test_gemini_audio(audio_path: str):
    """Upload audio to Gemini and test understanding."""
    print(f"\n☁️ Uploading to Gemini File API...")

    # Initialize Gemini client
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in environment")

    client = genai.Client(api_key=api_key)

    # Upload file using path parameter (like in service code)
    print(f"   File path: {audio_path}")
    print(f"   File exists: {os.path.exists(audio_path)}")
    print(f"   File size: {os.path.getsize(audio_path) / (1024*1024):.2f} MB")

    audio_file = await asyncio.to_thread(client.files.upload, path=audio_path)

    print(f"✅ Uploaded to Gemini:")
    print(f"   URI: {audio_file.uri}")
    print(f"   Name: {audio_file.name}")
    print(f"   State: {audio_file.state}")

    # Simple prompt to test understanding
    prompt = """
    Analyze this audio and provide:
    1. Language detected
    2. Brief summary of content (2-3 sentences)
    3. Duration estimate
    4. Number of speakers
    5. Audio quality (good/fair/poor)

    Return as JSON with keys: language, summary, duration_seconds, num_speakers, quality
    """

    print(f"\n🎯 Testing Gemini 2.0 Flash Experimental audio understanding...")
    print(f"   Model: gemini-2.0-flash-exp")

    response = await asyncio.to_thread(
        client.models.generate_content,
        model="gemini-2.0-flash-exp",
        contents=[
            types.Content(
                parts=[
                    types.Part(file_data=types.FileData(file_uri=audio_file.uri)),
                    types.Part(text=prompt),
                ]
            )
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            max_output_tokens=2000,
            temperature=0.3,
        ),
    )

    print(f"\n✅ Gemini Response:")
    result = json.loads(response.text)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    return result


async def main():
    if len(sys.argv) < 2:
        print("Usage: python test_youtube_audio_gemini.py <youtube_url>")
        print(
            "Example: python test_youtube_audio_gemini.py https://www.youtube.com/watch?v=ry9SYnV3svc"
        )
        sys.exit(1)

    youtube_url = sys.argv[1]
    audio_path = None

    try:
        # Step 1: Download audio
        audio_path = await download_youtube_audio(youtube_url)

        # Step 2: Test Gemini understanding
        result = await test_gemini_audio(audio_path)

        print("\n" + "=" * 50)
        print("🎉 TEST PASSED!")
        print("=" * 50)
        print(f"✅ Audio downloaded successfully")
        print(f"✅ Gemini understood the audio")
        print(f"✅ Language: {result.get('language', 'Unknown')}")
        print(f"✅ Quality: {result.get('quality', 'Unknown')}")

    except Exception as e:
        print(f"\n❌ TEST FAILED:")
        print(f"   Error: {str(e)}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    finally:
        # Cleanup
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)
            print(f"\n🧹 Cleaned up: {audio_path}")


if __name__ == "__main__":
    asyncio.run(main())
