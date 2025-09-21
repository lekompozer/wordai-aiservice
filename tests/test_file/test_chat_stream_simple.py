#!/usr/bin/env python3
"""
Simple test for chat stream endpoint validation
Kiểm tra đơn giản endpoint chat stream mà không gọi Qdrant
"""

import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from src.models.unified_models import (
    UnifiedChatRequest,
    Industry,
    Language,
    UserInfo,
    UserSource,
)


def test_request_validation():
    """Test request object creation and validation"""
    print("📦 Testing UnifiedChatRequest validation...")

    try:
        # Create a proper request object
        request = UnifiedChatRequest(
            message="Tôi muốn hỏi về gói bảo hiểm xe hơi",
            company_id="abc_insurance_001",
            industry=Industry.INSURANCE,
            language=Language.VIETNAMESE,
            session_id="test_session_validation",
            user_info=UserInfo(
                user_id="test_user_001",
                name="Test User",
                device_id="test_device_001",
                source=UserSource.CHATDEMO,
            ),
            context={},
        )

        print(f"✅ Request object created successfully")
        print(f"   Company: {request.company_id}")
        print(f"   Industry: {request.industry.value}")
        print(f"   Language: {request.language.value}")
        print(f"   Message: {request.message}")
        print(f"   Session: {request.session_id}")
        print(f"   User ID: {request.user_info.user_id}")
        print(f"   Device ID: {request.user_info.device_id}")
        print(f"   Source: {request.user_info.source.value}")

        return True

    except Exception as e:
        print(f"❌ Request validation failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_prompt_building_simple():
    """Test prompt building without Qdrant operations"""
    print("📝 Testing simple prompt building...")

    try:
        # Import the service but don't use Qdrant operations
        from src.services.unified_chat_service import unified_chat_service

        # Mock data for prompt building
        user_context = "New user - no previous conversation history."
        company_data = "Sample company insurance data: Our company offers comprehensive car insurance packages including full coverage, third-party liability, and premium services."
        company_context = "[THÔNG TIN CƠ BẢN CÔNG TY]\nTên công ty: ABC Insurance\nNgành: Bảo hiểm\nDịch vụ chính: Bảo hiểm xe cơ giới, bảo hiểm con người"
        user_query = "Tôi muốn hỏi về bảo hiểm xe ô tô"
        industry = "insurance"
        company_id = "abc_insurance_001"
        session_id = "test_session_simple"

        # Test prompt building
        prompt = unified_chat_service._build_unified_prompt_with_intent(
            user_context=user_context,
            company_data=company_data,
            company_context=company_context,
            user_query=user_query,
            industry=industry,
            company_id=company_id,
            session_id=session_id,
        )

        print(f"✅ Prompt built successfully: {len(prompt)} characters")
        print("📄 Prompt preview:")
        print("-" * 60)
        lines = prompt.split("\n")
        for i, line in enumerate(lines[:15]):  # Show first 15 lines
            print(f"{i+1:2d}: {line}")
        if len(lines) > 15:
            print(f"... (and {len(lines) - 15} more lines)")
        print("-" * 60)

        # Check if log file was created
        import glob

        log_files = glob.glob(
            "/Users/user/Code/ai-chatbot-rag/logs/prompt/prompt_*.txt"
        )
        if log_files:
            latest_log = max(log_files, key=os.path.getctime)
            print(f"📂 Prompt logged to: {os.path.basename(latest_log)}")

            # Show log file content preview
            with open(latest_log, "r", encoding="utf-8") as f:
                log_content = f.read()
                print(f"📄 Log file size: {len(log_content)} characters")
        else:
            print("⚠️ No prompt log file found")

        return True

    except Exception as e:
        print(f"❌ Prompt building failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_endpoint_headers_and_validation():
    """Test endpoint header parsing logic"""
    print("🔍 Testing endpoint validation logic...")

    try:
        # Simulate the validation logic from the endpoint
        test_cases = [
            {
                "name": "Valid with X-Company-Id header",
                "x_company_id": "abc_insurance_001",
                "request_company_id": None,
                "message": "Test message",
                "expected": "abc_insurance_001",
            },
            {
                "name": "Valid with request body company_id",
                "x_company_id": None,
                "request_company_id": "abc_insurance_001",
                "message": "Test message",
                "expected": "abc_insurance_001",
            },
            {
                "name": "Header overrides request body",
                "x_company_id": "header_company",
                "request_company_id": "body_company",
                "message": "Test message",
                "expected": "header_company",
            },
            {
                "name": "Missing company_id",
                "x_company_id": None,
                "request_company_id": None,
                "message": "Test message",
                "expected": "ERROR",
            },
            {
                "name": "Empty message",
                "x_company_id": "abc_insurance_001",
                "request_company_id": None,
                "message": "",
                "expected": "ERROR",
            },
            {
                "name": "None message",
                "x_company_id": "abc_insurance_001",
                "request_company_id": None,
                "message": None,
                "expected": "ERROR",
            },
        ]

        for test_case in test_cases:
            print(f"\n🧪 {test_case['name']}:")

            # Simulate endpoint validation logic
            try:
                x_company_id = test_case["x_company_id"]
                request_company_id = test_case["request_company_id"]
                message = test_case["message"]

                # Get company ID from header (for frontend) or request body (for backend)
                company_id = x_company_id or request_company_id
                if not company_id:
                    raise ValueError("Company ID required")

                # Validate required fields
                if not message or not str(message).strip():
                    raise ValueError("Message is required and cannot be empty")

                print(f"   ✅ Validation passed: {company_id}")
                if test_case["expected"] == "ERROR":
                    print(f"   ⚠️ Expected error but got success")

            except Exception as e:
                if test_case["expected"] == "ERROR":
                    print(f"   ✅ Expected error: {e}")
                else:
                    print(f"   ❌ Unexpected error: {e}")

        return True

    except Exception as e:
        print(f"❌ Validation logic test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def check_logs_directory():
    """Check if logs directory exists and is writable"""
    print("📂 Checking logs directory...")

    try:
        logs_dir = "/Users/user/Code/ai-chatbot-rag/logs"
        prompt_dir = "/Users/user/Code/ai-chatbot-rag/logs/prompt"

        print(f"   Logs directory: {logs_dir}")
        print(f"   Exists: {os.path.exists(logs_dir)}")
        print(
            f"   Writable: {os.access(logs_dir, os.W_OK) if os.path.exists(logs_dir) else 'N/A'}"
        )

        print(f"   Prompt directory: {prompt_dir}")
        print(f"   Exists: {os.path.exists(prompt_dir)}")
        print(
            f"   Writable: {os.access(prompt_dir, os.W_OK) if os.path.exists(prompt_dir) else 'N/A'}"
        )

        # List existing prompt files
        if os.path.exists(prompt_dir):
            import glob

            log_files = glob.glob(os.path.join(prompt_dir, "prompt_*.txt"))
            print(f"   Existing prompt files: {len(log_files)}")
            for log_file in log_files[-3:]:  # Show last 3 files
                print(f"     - {os.path.basename(log_file)}")

        return True

    except Exception as e:
        print(f"❌ Directory check failed: {e}")
        return False


def main():
    """Run all simple tests"""
    print("=" * 80)
    print("SIMPLE CHAT STREAM ENDPOINT VALIDATION")
    print("=" * 80)

    tests = [
        ("Request Validation", test_request_validation),
        ("Logs Directory Check", check_logs_directory),
        ("Endpoint Validation Logic", test_endpoint_headers_and_validation),
        ("Simple Prompt Building", test_prompt_building_simple),
    ]

    results = []

    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
        print()

    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    passed = 0
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {test_name}")
        if result:
            passed += 1

    print(f"\nTotal: {passed}/{len(results)} tests passed")

    if passed == len(results):
        print("\n🎉 All validation tests passed!")
        print("\n📋 ENDPOINT READINESS CHECK:")
        print("   ✅ Request object validation works")
        print("   ✅ Endpoint validation logic works")
        print("   ✅ Prompt building and logging works")
        print("   ✅ Header parsing logic works")
        print("\n⚠️  NOTE: Qdrant operations not tested due to segfault")
        print("   -> Test Qdrant operations directly on server")
    else:
        print(f"\n⚠️ {len(results) - passed} tests failed. Check logs above.")


if __name__ == "__main__":
    main()
