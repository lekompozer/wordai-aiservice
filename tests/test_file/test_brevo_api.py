#!/usr/bin/env python3
"""
Test Brevo Email Service using REST API instead of SMTP
This is a more reliable method and doesn't require IP whitelist
"""

import os
import sys
import requests
from pathlib import Path


def load_env():
    """Load environment variables from .env.development"""
    env_file = Path(__file__).parent / ".env.development"
    if env_file.exists():
        print(f"📄 Loading environment from: {env_file}\n")
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key] = value


def test_brevo_api():
    """Test sending email via Brevo REST API"""
    api_key = os.getenv("BREVO_API_KEY", "")
    sender_email = os.getenv("BREVO_SENDER_EMAIL", "noreply@wordai.pro")
    sender_name = os.getenv("BREVO_SENDER_NAME", "WordAI Notification")

    if not api_key:
        print("❌ BREVO_API_KEY not set!")
        return False

    print("=" * 60)
    print("🧪 Testing Brevo REST API")
    print("=" * 60)
    print(f"API Key: {api_key[:20]}...")
    print(f"Sender: {sender_name} <{sender_email}>")
    print()

    # Test 1: Get account info
    print("1️⃣ Testing API connection...")
    try:
        response = requests.get(
            "https://api.brevo.com/v3/account",
            headers={
                "accept": "application/json",
                "api-key": api_key,
            },
        )

        if response.status_code == 200:
            account = response.json()
            print(f"✅ API Connection successful!")
            print(f"   Email: {account.get('email')}")
            print(f"   Plan: {account.get('plan', [{}])[0].get('type', 'Unknown')}")
            print()
        else:
            print(f"❌ API Connection failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Error connecting to API: {e}")
        return False

    # Test 2: Send welcome email
    print("2️⃣ Sending welcome email to tienhoi.lh@gmail.com...")
    try:
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                          color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }
                .content { background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }
                .button { display: inline-block; padding: 12px 24px; background: #667eea;
                         color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎉 Chào mừng đến với WordAI!</h1>
                </div>
                <div class="content">
                    <p>Xin chào <strong>Tiến Hội</strong>,</p>
                    <p>Đây là email test từ Brevo REST API!</p>
                    <p>Nếu bạn nhận được email này, nghĩa là hệ thống email đã hoạt động thành công.</p>
                    <p>Trân trọng,<br><strong>Đội ngũ WordAI</strong></p>
                </div>
            </div>
        </body>
        </html>
        """

        data = {
            "sender": {"name": sender_name, "email": sender_email},
            "to": [{"email": "tienhoi.lh@gmail.com", "name": "Tiến Hội"}],
            "subject": "🎉 Chào mừng đến với WordAI - Test Email",
            "htmlContent": html_content,
        }

        response = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "accept": "application/json",
                "api-key": api_key,
                "content-type": "application/json",
            },
            json=data,
        )

        if response.status_code == 201:
            result = response.json()
            print(f"✅ Email sent successfully!")
            print(f"   Message ID: {result.get('messageId')}")
            print()
            return True
        else:
            print(f"❌ Failed to send email: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Error sending email: {e}")
        return False


def test_share_notification():
    """Test sending file share notification via Brevo REST API"""
    api_key = os.getenv("BREVO_API_KEY", "")
    sender_email = os.getenv("BREVO_SENDER_EMAIL", "noreply@wordai.pro")
    sender_name = os.getenv("BREVO_SENDER_NAME", "WordAI Notification")

    print("3️⃣ Sending file share notification to tienhoi.lh@gmail.com...")

    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
            .container { max-width: 600px; margin: 0 auto; padding: 20px; }
            .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                      color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }
            .content { background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }
            .file-info { background: white; padding: 20px; border-radius: 8px; margin: 20px 0;
                        border-left: 4px solid #667eea; }
            .permission { display: inline-block; padding: 6px 12px; background: #e3f2fd;
                         color: #1976d2; border-radius: 4px; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📄 File được chia sẻ</h1>
            </div>
            <div class="content">
                <p>Xin chào <strong>Tiến Hội</strong>,</p>
                <p><strong>WordAI Admin</strong> đã chia sẻ một file với bạn trên WordAI.</p>
                <div class="file-info">
                    <p><strong>📄 Tên file:</strong> test-document.pdf</p>
                    <p><strong>🔐 Quyền truy cập:</strong> <span class="permission">Tải xuống</span></p>
                    <p><strong>👤 Người chia sẻ:</strong> WordAI Admin</p>
                </div>
                <p>Đây là email test từ Brevo REST API!</p>
                <p>Trân trọng,<br><strong>Đội ngũ WordAI</strong></p>
            </div>
        </div>
    </body>
    </html>
    """

    data = {
        "sender": {"name": sender_name, "email": sender_email},
        "to": [{"email": "tienhoi.lh@gmail.com", "name": "Tiến Hội"}],
        "subject": "📄 WordAI Admin đã chia sẻ file với bạn - test-document.pdf",
        "htmlContent": html_content,
    }

    try:
        response = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "accept": "application/json",
                "api-key": api_key,
                "content-type": "application/json",
            },
            json=data,
        )

        if response.status_code == 201:
            result = response.json()
            print(f"✅ Share notification sent successfully!")
            print(f"   Message ID: {result.get('messageId')}")
            print()
            return True
        else:
            print(f"❌ Failed to send notification: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Error sending notification: {e}")
        return False


def main():
    """Run all tests"""
    print("🚀 Brevo REST API Test")
    print("📧 Testing email delivery to: tienhoi.lh@gmail.com")
    print()

    load_env()

    results = []

    # Test API connection and send emails
    if test_brevo_api():
        results.append(("Welcome Email (REST API)", True))

        # Test share notification
        if test_share_notification():
            results.append(("Share Notification (REST API)", True))
        else:
            results.append(("Share Notification (REST API)", False))
    else:
        results.append(("Welcome Email (REST API)", False))
        results.append(("Share Notification (REST API)", False))

    # Summary
    print("=" * 60)
    print("📊 Test Summary")
    print("=" * 60)

    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {test_name}")

    total = len(results)
    passed = sum(1 for _, success in results if success)

    print()
    print(f"Total: {passed}/{total} tests passed")
    print()

    if passed == total:
        print("🎉 All tests passed! Brevo REST API is working correctly.")
        print("💡 Recommendation: Use REST API instead of SMTP for better reliability.")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
