#!/usr/bin/env python3
"""
Script to test CORS configuration
Kiểm tra cấu hình CORS
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import get_app_config


def test_cors_config():
    """Test CORS configuration"""
    print("🧪 Testing CORS Configuration...")
    print("=" * 50)

    # Test with different environment settings
    test_cases = [
        {
            "name": "Production (with CORS_ORIGINS env)",
            "env_vars": {
                "ENVIRONMENT": "production",
                "CORS_ORIGINS": "https://api.agent8x.io.vn,https://agent8x.io.vn,https://admin.agent8x.io.vn",
            },
        },
        {
            "name": "Production (with duplicate CORS_ORIGINS)",
            "env_vars": {
                "ENVIRONMENT": "production",
                "CORS_ORIGINS": "https://admin.agent8x.io.vn,https://admin.agent8x.io.vn,https://api.agent8x.io.vn",
            },
        },
        {"name": "Development", "env_vars": {"ENVIRONMENT": "development"}},
    ]

    for test_case in test_cases:
        print(f"\n📋 Test Case: {test_case['name']}")
        print("-" * 40)

        # Set environment variables
        for key, value in test_case["env_vars"].items():
            os.environ[key] = value

        try:
            config = get_app_config()
            cors_origins = config.get("cors_origins", [])

            print(f"CORS Origins: {cors_origins}")
            print(f"Count: {len(cors_origins)}")
            print(f"Unique: {len(set(cors_origins)) == len(cors_origins)}")

            # Check for duplicates
            seen = set()
            duplicates = []
            for origin in cors_origins:
                if origin in seen:
                    duplicates.append(origin)
                seen.add(origin)

            if duplicates:
                print(f"❌ Duplicates found: {duplicates}")
            else:
                print("✅ No duplicates")

        except Exception as e:
            print(f"❌ Error: {e}")

        # Clean up environment
        for key in test_case["env_vars"].keys():
            if key in os.environ:
                del os.environ[key]


def test_cors_headers():
    """Test CORS headers simulation"""
    print("\n🌐 Testing CORS Headers Simulation...")
    print("=" * 50)

    import requests

    # Test preflight request
    test_url = "https://ai.aimoney.io.vn/api/unified/chat-stream"
    origin = "https://admin.agent8x.io.vn"

    try:
        # OPTIONS preflight request
        response = requests.options(
            test_url,
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
            timeout=10,
        )

        print(f"Preflight Request to: {test_url}")
        print(f"Origin: {origin}")
        print(f"Status Code: {response.status_code}")
        print("Response Headers:")
        for key, value in response.headers.items():
            if "access-control" in key.lower() or "cors" in key.lower():
                print(f"  {key}: {value}")

    except Exception as e:
        print(f"❌ Request failed: {e}")


if __name__ == "__main__":
    test_cors_config()
    test_cors_headers()
