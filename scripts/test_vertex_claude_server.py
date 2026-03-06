"""
Test script to verify Claude 4.5 Sonnet on Vertex AI connection ON PRODUCTION SERVER
Uses the credentials file to test direct connection and quota
"""

import os
import sys
from anthropic import AnthropicVertex

# Set credentials file (production path)
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/app/wordai-6779e-ed6189c466f1.json"

# Configuration
PROJECT_ID = "wordai-6779e"
REGION = "asia-southeast1"
MODEL = "claude-sonnet-4-5@20250929"

print("=" * 80)
print("🧪 Testing Claude 4.5 Sonnet on Vertex AI")
print("=" * 80)
print(f"📁 Credentials: {os.environ['GOOGLE_APPLICATION_CREDENTIALS']}")
print(f"🌍 Project: {PROJECT_ID}")
print(f"📍 Region: {REGION}")
print(f"🤖 Model: {MODEL}")
print("=" * 80)

try:
    # Initialize client
    print("\n1️⃣ Initializing Vertex AI client...")
    client = AnthropicVertex(project_id=PROJECT_ID, region=REGION)
    print("   ✅ Client initialized successfully")

    # Test simple request
    print("\n2️⃣ Sending test request...")
    print("   Prompt: 'What is 2+2? Answer in one sentence.'")

    response = client.messages.create(
        model=MODEL,
        max_tokens=100,
        messages=[{"role": "user", "content": "What is 2+2? Answer in one sentence."}],
    )

    print("   ✅ Request successful!")
    print("\n3️⃣ Response:")
    print(f"   Model: {response.model}")
    print(f"   Stop reason: {response.stop_reason}")
    print(f"   Input tokens: {response.usage.input_tokens}")
    print(f"   Output tokens: {response.usage.output_tokens}")
    print(f"   Content: {response.content[0].text}")

    print("\n" + "=" * 80)
    print("✅ SUCCESS - Vertex AI connection works perfectly!")
    print("=" * 80)

except Exception as e:
    print("\n" + "=" * 80)
    print("❌ ERROR - Connection failed")
    print("=" * 80)
    print(f"\nError type: {type(e).__name__}")
    print(f"Error message: {str(e)}")

    # Check if it's quota error
    if "429" in str(e) or "quota" in str(e).lower() or "RESOURCE_EXHAUSTED" in str(e):
        print("\n🚨 QUOTA EXCEEDED ERROR")
        print("   This means:")
        print("   - Vertex AI connection works ✅")
        print("   - Credentials are valid ✅")
        print("   - But quota limit is 0 or too low ❌")
        print("\n   📊 Current quota status:")
        print("   - Model: anthropic-claude-sonnet-4-5")
        print(
            "   - Quota: aiplatform.googleapis.com/online_prediction_input_tokens_per_minute_per_base_model"
        )
        print("   - Current limit: 0 or very low")
        print("\n   🔧 Solutions:")
        print("   1. Request quota increase:")
        print(
            "      https://console.cloud.google.com/iam-admin/quotas?project=wordai-6779e"
        )
        print("   2. Search: 'Claude 3.5 Sonnet' or 'online_prediction_input_tokens'")
        print("   3. Request increase to at least 60 RPM")
        print("   OR")
        print("   4. Use Anthropic API Key directly (current fallback)")

    print("\n" + "=" * 80)
    sys.exit(1)
