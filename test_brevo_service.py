#!/usr/bin/env python3
"""
Test Brevo Email Service
Tests the newly refactored REST API-based email service
"""

import sys
import os
from dotenv import load_dotenv

# Load environment
load_dotenv(".env.development")

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from services.brevo_email_service import get_brevo_service


def test_welcome_email():
    """Test welcome email"""
    print("📧 Testing Welcome Email...")
    service = get_brevo_service()

    result = service.send_welcome_email(
        to_email="tienhoi.lh@gmail.com", user_name="Hoàng Tiến Hôi"
    )

    if result:
        print("✅ Welcome email sent successfully!")
        return True
    else:
        print("❌ Failed to send welcome email")
        return False


def test_share_notification():
    """Test file share notification"""
    print("\n📧 Testing Share Notification...")
    service = get_brevo_service()

    result = service.send_file_share_notification(
        to_email="tienhoi.lh@gmail.com",
        recipient_name="Hoàng Tiến Hôi",
        owner_name="Nguyễn Văn A",
        filename="Báo cáo tài chính Q4.docx",
        permission="edit",
        share_url="https://wordai.pro/shared/abc123",
    )

    if result:
        print("✅ Share notification sent successfully!")
        return True
    else:
        print("❌ Failed to send share notification")
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("TESTING BREVO EMAIL SERVICE (REST API)")
    print("=" * 60)

    tests = [
        test_welcome_email,
        test_share_notification,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed}/{len(tests)} tests passed")
    if failed == 0:
        print("✅ ALL TESTS PASSED!")
    else:
        print(f"❌ {failed} test(s) failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
