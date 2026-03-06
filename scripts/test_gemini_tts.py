"""
Test Gemini 2.5 Pro TTS on Vertex AI to verify account quota
Generate actual audio to test TTS functionality
"""

import os
import base64
from google import genai
from google.genai import types

# Set credentials
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/app/wordai-6779e-ed6189c466f1.json"

PROJECT_ID = "wordai-6779e"
LOCATION = "us-central1"  # TTS models available in US regions
MODEL = "gemini-2.5-pro-tts"  # TTS model

print("=" * 80)
print("🧪 Testing Gemini 2.5 Pro TTS on Vertex AI")
print("=" * 80)
print(f"📁 Credentials: {os.environ['GOOGLE_APPLICATION_CREDENTIALS']}")
print(f"🌍 Project: {PROJECT_ID}")
print(f"📍 Location: {LOCATION}")
print(f"🤖 Model: {MODEL}")
print("=" * 80)

try:
    # Initialize client
    print("\n1️⃣ Initializing Gemini TTS client...")
    client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
    print("   ✅ Client initialized successfully")

    # Test TTS generation
    print("\n2️⃣ Testing TTS audio generation...")
    print("   Text: 'Hello, this is a test of Gemini text to speech.'")

    response = client.models.generate_content(
        model=MODEL,
        contents="Hello, this is a test of Gemini text to speech.",
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck")
                )
            ),
        ),
    )

    print("   ✅ Request successful!")

    # Check if audio was generated
    if hasattr(response, "candidates") and response.candidates:
        candidate = response.candidates[0]
        if hasattr(candidate, "content") and candidate.content.parts:
            for part in candidate.content.parts:
                if hasattr(part, "inline_data") and part.inline_data:
                    audio_data = part.inline_data.data
                    print(f"\n3️⃣ Audio generated:")
                    print(f"   MIME type: {part.inline_data.mime_type}")
                    print(f"   Size: {len(audio_data)} bytes")

                    # Save to file
                    with open("/tmp/test_tts_output.mp3", "wb") as f:
                        f.write(audio_data)
                    print(f"   ✅ Saved to: /tmp/test_tts_output.mp3")
                    break

    print("\n" + "=" * 80)
    print("✅ SUCCESS - Gemini TTS works on Vertex AI!")
    print("   This means: Account is OK, only Claude quota is limited")
    print("=" * 80)

except Exception as e:
    print("\n" + "=" * 80)
    print("❌ ERROR - Request failed")
    print("=" * 80)
    print(f"\nError type: {type(e).__name__}")
    print(f"Error message: {str(e)}")

    if "429" in str(e) or "quota" in str(e).lower() or "RESOURCE_EXHAUSTED" in str(e):
        print("\n🚨 QUOTA ERROR - Entire GCP account has quota issues")
        print("   Need to:")
        print("   1. Enable billing")
        print("   2. Upgrade from free tier")
        print("   3. Request quota increases")
    elif "404" in str(e) or "not found" in str(e).lower():
        print("\n🚨 MODEL NOT AVAILABLE")
        print(f"   Model '{MODEL}' not available in region '{LOCATION}'")
        print("   Try: us-central1 or global region")
    elif "403" in str(e) or "permission" in str(e).lower():
        print("\n🚨 PERMISSION ERROR - API not enabled")
        print("   Need to enable Vertex AI API at:")
        print(
            f"   https://console.cloud.google.com/apis/library/aiplatform.googleapis.com?project={PROJECT_ID}"
        )
    else:
        print("\n🚨 OTHER ERROR - Check error details above")

    print("\n" + "=" * 80)
