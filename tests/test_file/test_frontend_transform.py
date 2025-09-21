#!/usr/bin/env python3
"""
Test the exact payload from frontend with proper transformation
"""

import json
import requests


def test_transformed_payload():
    """Test with the exact payload structure from frontend, but transformed"""

    # This is your exact frontend payload structure, but with correct formatting
    original_payload = {
        "company_id": "9a974d00-1a4b-4d5d-8dc3-4b5058255b8f",
        "industry": "INSURANCE",  # Frontend sends UPPERCASE
        "language": "ENGLISH",  # Frontend sends UPPERCASE
        "message": "cho tao thông tin về AIA xem",
        "session_id": "firebase_2Fi60Cy2jHcMhkn5o2VcjfUef7p2_1753905688",
        "user_info": {
            "user_id": "2Fi60Cy2jHcMhkn5o2VcjfUef7p2",
            "source": "chatdemo",
            "name": "Michael Le",
            "email": "tienhoi.lh@gmail.com",
            "device_id": "web_eczqgo",
            "is_authenticated": True,
        },
        "context": {
            "context_data": {
                "page_url": "https://admin.agent8x.io.vn/9a974d00-1a4b-4d5d-8dc3-4b5058255b8f/chat-demo",
                "page_views": 4,
                "referrer": None,
                "session_duration_minutes": 62,
            },
            "platform_data": {
                "browser": "Chrome 138",
                "language": "en-US",
                "operating_system": "macOS",
                "platform": "web",
                "timezone": "Asia/Saigon",
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
            },
        },
        "metadata": {
            "api_version": "v2",
            "app_source": "website",
            "app_version": "2.1.4",
            "request_id": "req_1753905688220zdqsqy",
        },
    }

    # Transform to server-compatible format
    def transform_payload(payload):
        """Transform frontend payload to server format"""

        # Language mapping
        lang_map = {"ENGLISH": "en", "VIETNAMESE": "vi", "AUTO": "auto"}

        # Industry mapping (uppercase to lowercase)
        industry = payload.get("industry", "other").lower()

        # Language transformation
        language = lang_map.get(payload.get("language", "AUTO"), "auto")

        # Context transformation - flatten the nested structure
        context = None
        if payload.get("context"):
            context_data = payload["context"].get("context_data", {})
            context = {
                "page_url": context_data.get("page_url"),
                "referrer": context_data.get("referrer"),
                "timestamp": "2025-07-30T19:00:00Z",
                "session_duration": (
                    context_data.get("session_duration_minutes", 0) * 60
                    if context_data.get("session_duration_minutes")
                    else None
                ),
            }

        # Metadata transformation
        metadata = None
        if payload.get("metadata"):
            meta = payload["metadata"]
            metadata = {
                "source": meta.get("app_source", "website"),
                "version": meta.get("app_version", "1.0.0"),
                "request_id": meta.get("request_id"),
            }

        # User info - keep most fields as is, but add platform_specific_data
        user_info = payload.get("user_info", {}).copy()
        if payload.get("context", {}).get("platform_data"):
            platform_data = payload["context"]["platform_data"]
            user_info["platform_specific_data"] = {
                "browser": platform_data.get("browser"),
                "user_agent": platform_data.get("user_agent"),
                "platform": platform_data.get("operating_system"),
                "language": platform_data.get("language"),
                "timezone": platform_data.get("timezone"),
            }

        # Remove non-standard fields
        if "is_authenticated" in user_info:
            del user_info["is_authenticated"]

        return {
            "company_id": payload["company_id"],
            "message": payload["message"],
            "industry": industry,
            "language": language,
            "session_id": payload.get("session_id"),
            "user_info": user_info,
            "context": context,
            "metadata": metadata,
        }

    print("🔄 Testing Frontend Payload Transformation")
    print("=" * 50)

    print("📥 Original Frontend Payload:")
    print(json.dumps(original_payload, indent=2, ensure_ascii=False))

    # Transform payload
    transformed_payload = transform_payload(original_payload)

    print("\n📤 Transformed Server Payload:")
    print(json.dumps(transformed_payload, indent=2, ensure_ascii=False))

    # Test the transformed payload
    url = "https://ai.aimoney.io.vn/api/unified/chat-stream"

    try:
        headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}

        print(f"\n📡 Sending to: {url}")
        response = requests.post(
            url, json=transformed_payload, headers=headers, timeout=10, stream=True
        )

        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            print("✅ SUCCESS! Transformation worked!")

            # Read a few chunks
            chunk_count = 0
            for line in response.iter_lines(decode_unicode=True):
                if line and chunk_count < 2:
                    print(f"Sample response: {line}")
                    chunk_count += 1
                elif chunk_count >= 2:
                    break

        elif response.status_code == 422:
            print(f"❌ Still getting 422. Details:")
            print(response.text)
        else:
            print(f"❌ Status {response.status_code}: {response.text}")

    except Exception as e:
        print(f"❌ Request failed: {e}")


if __name__ == "__main__":
    test_transformed_payload()
