#!/usr/bin/env python3
"""
Create payloads that work with current production server
Tạo payload tương thích với server production hiện tại
"""

import json


def get_working_payloads():
    """Get payload formats that should work with production server"""

    # Based on test results, these formats work:
    working_payloads = {
        "minimal_chat_stream": {
            "company_id": "your-company-id",
            "message": "Your message here",
            "industry": "other",  # Add industry to avoid validation error
        },
        "complete_compatible": {
            "company_id": "your-company-id",
            "message": "Your message here",
            "industry": "banking",  # or other, restaurant, etc.
            "language": "vi",
            "user_info": {
                "user_id": "authenticated_user_123",
                "source": "web_device",  # This field is required when user_info exists
                "name": "User Name",
                "device_id": "device_fingerprint_123",
            },
            "session_id": "session_123",
        },
    }

    return working_payloads


def print_production_compatible_formats():
    """Print formats that should work with production"""
    print("🎯 Production-Compatible Payload Formats")
    print("=" * 50)

    payloads = get_working_payloads()

    for name, payload in payloads.items():
        print(f"\n📋 {name.replace('_', ' ').title()}:")
        print("```json")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        print("```")

    print("\n⚠️  Important Notes:")
    print("1. company_id is ALWAYS required")
    print("2. industry should be included to avoid validation errors")
    print("3. If user_info is provided, 'source' field is required")
    print("4. user_id and device_id are required when user_info exists")
    print("5. For anonymous users, omit user_info entirely")


def create_frontend_compatible_payload():
    """Create a payload format for frontend integration"""
    print("\n🔧 Frontend Integration Payload:")
    print("-" * 30)

    frontend_payload = {
        "company_id": "{{COMPANY_ID}}",  # Replace with actual company ID
        "message": "{{USER_MESSAGE}}",  # Replace with user's message
        "industry": "{{COMPANY_INDUSTRY}}",  # banking, restaurant, other, etc.
        "language": "vi",
        "user_info": {
            "user_id": "{{USER_ID}}",  # From authentication
            "source": "web_device",
            "name": "{{USER_NAME}}",  # Optional but recommended
            "device_id": "{{DEVICE_FINGERPRINT}}",  # Browser fingerprint
            "platform_specific_data": {
                "browser": "{{BROWSER_NAME}}",
                "platform": "{{OS_PLATFORM}}",
                "screen_resolution": "{{SCREEN_RES}}",
            },
        },
        "context": {
            "page_url": "{{CURRENT_URL}}",
            "referrer": "{{REFERRER_URL}}",
            "timestamp": "{{TIMESTAMP}}",
        },
        "session_id": "{{SESSION_ID}}",  # Optional, will auto-generate
    }

    print("Frontend JavaScript example:")
    print("```javascript")
    print(
        """
const payload = {
    company_id: "your-company-id",
    message: userMessage,
    industry: "banking", // or your company's industry
    language: "vi",
    user_info: {
        user_id: authUser.uid,
        source: "web_device", 
        name: authUser.displayName,
        device_id: deviceFingerprint
    }
};

// For chat-stream endpoint
fetch('https://ai.aimoney.io.vn/api/unified/chat-stream', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
});
"""
    )
    print("```")


if __name__ == "__main__":
    print_production_compatible_formats()
    create_frontend_compatible_payload()

    print("\n🚀 Ready to use! Copy the appropriate payload format.")
