"""
Test Google Cloud TTS Integration
Generate audio from Vietnamese text locally
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Load development environment
load_dotenv("development.env")

# Add src to path
sys.path.insert(0, os.path.abspath("."))

from src.services.google_tts_service import GoogleTTSService


async def test_tts():
    """Test TTS audio generation"""

    print("=" * 60)
    print("🎙️  Google Cloud TTS Test")
    print("=" * 60)

    # Initialize service
    print("\n1. Initializing Google TTS service...")
    tts_service = GoogleTTSService()
    print("   ✅ Service initialized")

    # Test 1: Get available voices
    print("\n2. Fetching available Vietnamese voices...")
    try:
        voices = await tts_service.get_available_voices("vi")
        print(f"   ✅ Found {len(voices)} voices")

        # Show first 3 voices
        print("\n   Sample voices:")
        for voice in voices[:3]:
            print(
                f"   - {voice['name']}: {voice['gender']}, {voice['natural_sample_rate_hertz']}Hz"
            )
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return

    # Test 2: Generate audio from simple text
    print("\n3. Generating audio with gemini-2.5-flash-tts (Despina voice)...")
    test_text = "Xin chào! Đây là bài kiểm tra tính năng tạo audio từ văn bản. Công nghệ Google Gemini Text-to-Speech cho phép chuyển đổi văn bản thành giọng nói tự nhiên."

    try:
        audio_content, metadata = await tts_service.generate_audio(
            text=test_text, language="vi", voice_name="Despina", use_pro_model=False
        )

        print(f"   ✅ Audio generated successfully!")
        print(f"   - Duration: ~{metadata['duration']:.1f}s")
        print(f"   - Format: {metadata['format']}")
        print(f"   - Sample rate: {metadata['sample_rate']}Hz")
        print(f"   - Voice: {metadata['voice_name']}")
        print(f"   - Model: {metadata['model']}")
        print(f"   - Word count: {metadata['word_count']}")
        print(f"   - Audio size: {len(audio_content):,} bytes")

        # Save to file
        output_file = "/tmp/test_tts_despina_flash.wav"
        await tts_service.save_audio_to_file(audio_content, output_file)
        print(f"\n4. Audio saved to: {output_file}")
        print(f"   ✅ You can play this file to test the audio quality")

    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return

    # Test 3: Generate with PRO model
    print("\n5. Testing gemini-2.5-pro-tts (Gacrux voice)...")
    try:
        audio_content2, metadata2 = await tts_service.generate_audio(
            text="Đây là thử nghiệm với mô hình Pro chất lượng cao hơn.",
            language="vi",
            voice_name="Gacrux",
            use_pro_model=True,
        )

        output_file2 = "/tmp/test_tts_gacrux_pro.wav"
        await tts_service.save_audio_to_file(audio_content2, output_file2)
        print(f"   ✅ PRO model audio saved to: {output_file2}")
        print(f"   - Model: {metadata2['model']}")
        print(f"   - Voice: {metadata2['voice_name']}")

    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback

        traceback.print_exc()

    # Test 4: Test male voices
    print("\n6. Testing male voices (Enceladus, Orus, Alnilam)...")
    male_voices = ["Enceladus", "Orus", "Alnilam"]
    test_text_short = "Đây là giọng nam."

    for voice in male_voices:
        try:
            audio_content3, metadata3 = await tts_service.generate_audio(
                text=test_text_short,
                language="vi",
                voice_name=voice,
            )

            output_file3 = f"/tmp/test_tts_{voice.lower()}.wav"
            await tts_service.save_audio_to_file(audio_content3, output_file3)
            print(f"   ✅ {voice} voice saved to: {output_file3}")

        except Exception as e:
            print(f"   ❌ Error with {voice}: {e}")

    print("\n" + "=" * 60)
    print("✅ TEST COMPLETED!")
    print("=" * 60)
    print("\nTest files created:")
    print("  - /tmp/test_tts_despina_flash.wav (Despina, flash model)")
    print("  - /tmp/test_tts_gacrux_pro.wav (Gacrux, PRO model)")
    print("  - /tmp/test_tts_enceladus.wav (Enceladus male)")
    print("  - /tmp/test_tts_orus.wav (Orus male)")
    print("  - /tmp/test_tts_alnilam.wav (Alnilam male)")
    print("\nPlay these files to verify audio quality.")


if __name__ == "__main__":
    asyncio.run(test_tts())
