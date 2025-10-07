#!/usr/bin/env python3
"""
Test Brevo Email Service
Send test emails to verify Brevo integration
"""

import os
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent
sys.path.insert(0, str(src_path))

from src.services.brevo_email_service import get_brevo_service


def test_welcome_email():
    """Test sending welcome email"""
    print("=" * 60)
    print("🧪 Testing Welcome Email")
    print("=" * 60)

    brevo = get_brevo_service()

    success = brevo.send_welcome_email(
        to_email="tienhoi.lh@gmail.com",
        user_name="Tiến Hội",
    )

    if success:
        print("✅ Welcome email sent successfully!")
    else:
        print("❌ Failed to send welcome email")

    return success


def test_share_notification_email():
    """Test sending file share notification email"""
    print("\n" + "=" * 60)
    print("🧪 Testing File Share Notification Email")
    print("=" * 60)

    brevo = get_brevo_service()

    success = brevo.send_file_share_notification(
        to_email="tienhoi.lh@gmail.com",
        recipient_name="Tiến Hội",
        owner_name="WordAI Admin",
        filename="test-document.pdf",
        permission="download",
        share_url="https://wordai.pro/shared/test123",
    )

    if success:
        print("✅ Share notification email sent successfully!")
    else:
        print("❌ Failed to send share notification email")

    return success


def main():
    """Run all email tests"""
    print("🚀 Brevo Email Service Test")
    print("📧 Testing email delivery to: tienhoi.lh@gmail.com")
    print()

    # Check environment variables
    print("🔧 Checking Brevo configuration...")
    smtp_server = os.getenv("BREVO_SMTP_SERVER", "smtp-relay.brevo.com")
    smtp_port = os.getenv("BREVO_SMTP_PORT", "587")
    smtp_login = os.getenv("BREVO_SMTP_LOGIN", "NOT_SET")
    api_key = os.getenv("BREVO_API_KEY", "NOT_SET")
    sender_email = os.getenv("BREVO_SENDER_EMAIL", "noreply@wordai.pro")

    print(f"   SMTP Server: {smtp_server}")
    print(f"   SMTP Port: {smtp_port}")
    print(f"   SMTP Login: {smtp_login}")
    print(
        f"   API Key: {'SET ✅' if api_key != 'NOT_SET' and len(api_key) > 10 else 'NOT SET ❌'}"
    )
    print(f"   Sender Email: {sender_email}")
    print()

    if api_key == "NOT_SET" or smtp_login == "NOT_SET":
        print("❌ ERROR: Brevo credentials not configured!")
        print()
        print("Please set environment variables:")
        print("   export BREVO_API_KEY='your_api_key'")
        print("   export BREVO_SMTP_LOGIN='your_smtp_login'")
        print()
        print("Or add to development.env file:")
        print("   BREVO_API_KEY=xkeysib-...")
        print("   BREVO_SMTP_LOGIN=98c447001@smtp-brevo.com")
        return False

    # Run tests
    results = []

    results.append(("Welcome Email", test_welcome_email()))
    results.append(("Share Notification Email", test_share_notification_email()))

    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)

    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {test_name}")

    total = len(results)
    passed = sum(1 for _, success in results if success)

    print()
    print(f"Total: {passed}/{total} tests passed")

    return passed == total


if __name__ == "__main__":
    # Load environment variables from .env.development (preferred) or development.env (fallback)
    env_files = [
        Path(__file__).parent / ".env.development",
        Path(__file__).parent / "development.env",
    ]

    loaded = False
    for env_file in env_files:
        if env_file.exists():
            print(f"📄 Loading environment from: {env_file}")
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        os.environ[key] = value
            print()
            loaded = True
            break

    if not loaded:
        print("⚠️ No environment file found!")
        print()

    success = main()
    sys.exit(0 if success else 1)
