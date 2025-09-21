#!/usr/bin/env python3
"""
Test the exact production-compatible payload format
"""

import json
import requests


def test_production_chat_stream():
    """Test production chat-stream with working format"""
    url = "https://ai.aimoney.io.vn/api/unified/chat-stream"

    # This format should work based on our analysis
    payload = {
        "company_id": "test-company-001",
        "message": "Xin chào, tôi cần hỗ trợ tư vấn",
        "industry": "banking",
        "language": "vi",
        "user_info": {
            "user_id": "test_user_123",
            "source": "chatdemo",
            "name": "Test User",
            "device_id": "test_device_123",
        },
    }

    print("🔍 Testing Production Chat-Stream Endpoint")
    print(f"URL: {url}")
    print(f"Payload:\n{json.dumps(payload, indent=2, ensure_ascii=False)}")

    try:
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "User-Agent": "Python-Test/1.0",
        }

        print("\n📡 Sending request...")
        response = requests.post(
            url, json=payload, headers=headers, timeout=15, stream=True
        )

        print(f"Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")

        if response.status_code == 200:
            print("✅ SUCCESS! Chat-stream endpoint is working")

            # Read first few chunks to verify streaming
            print("\n📦 First few response chunks:")
            chunk_count = 0
            for line in response.iter_lines(decode_unicode=True):
                if line and chunk_count < 3:
                    print(f"Chunk {chunk_count + 1}: {line}")
                    chunk_count += 1
                elif chunk_count >= 3:
                    print("... (stopping after 3 chunks)")
                    break

        elif response.status_code == 422:
            print(f"❌ Validation Error (422):")
            print(response.text)

            # Parse the validation error
            try:
                error_data = response.json()
                if "detail" in error_data:
                    print("\n🔍 Validation Issues:")
                    for error in error_data["detail"]:
                        field = " -> ".join(str(x) for x in error.get("loc", []))
                        message = error.get("msg", "Unknown error")
                        print(f"   • {field}: {message}")
            except:
                pass

        else:
            print(f"❌ Unexpected status: {response.status_code}")
            print(response.text[:500])

    except requests.exceptions.Timeout:
        print("⏰ Request timed out - server might be processing")
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


if __name__ == "__main__":
    test_production_chat_stream()
