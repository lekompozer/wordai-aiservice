#!/usr/bin/env python3
"""
Script to setup Firebase configuration on production server
"""

import os
import json
from pathlib import Path


def check_firebase_config():
    """Check current Firebase configuration"""
    print("🔍 Checking Firebase Configuration...")

    # Check environment variables
    required_vars = [
        "FIREBASE_PROJECT_ID",
        "FIREBASE_PRIVATE_KEY",
        "FIREBASE_CLIENT_EMAIL",
        "FIREBASE_PRIVATE_KEY_ID",
        "FIREBASE_CLIENT_ID",
        "FIREBASE_CLIENT_CERT_URL",
    ]

    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing_vars.append(var)
        else:
            # Mask sensitive data
            if "PRIVATE_KEY" in var:
                display_value = value[:30] + "..." if len(value) > 30 else value
            else:
                display_value = value
            print(f"✅ {var}: {display_value}")

    if missing_vars:
        print(f"\n❌ Missing environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        return False

    print("\n✅ All Firebase environment variables are set!")
    return True


def test_firebase_import():
    """Test Firebase import and initialization"""
    print("\n🔍 Testing Firebase import...")

    try:
        from src.config.firebase_config import firebase_config

        if firebase_config.app:
            print("✅ Firebase Admin SDK initialized successfully!")
            return True
        else:
            print("❌ Firebase Admin SDK failed to initialize")
            return False

    except Exception as e:
        print(f"❌ Firebase import error: {e}")
        return False


def create_service_account_file():
    """Create Firebase service account JSON file from environment variables"""
    print("\n🔧 Creating Firebase service account file...")

    try:
        service_account_data = {
            "type": "service_account",
            "project_id": os.getenv("FIREBASE_PROJECT_ID"),
            "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
            "private_key": os.getenv("FIREBASE_PRIVATE_KEY", "").replace("\\n", "\n"),
            "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
            "client_id": os.getenv("FIREBASE_CLIENT_ID"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_CERT_URL"),
        }

        # Validate required fields
        required_fields = ["project_id", "private_key", "client_email"]
        missing_fields = [
            field for field in required_fields if not service_account_data.get(field)
        ]

        if missing_fields:
            print(f"❌ Missing required fields: {missing_fields}")
            return False

        # Write to file
        with open("firebase-service-account.json", "w") as f:
            json.dump(service_account_data, f, indent=2)

        print("✅ Firebase service account file created: firebase-service-account.json")

        # Set environment variable
        os.environ["FIREBASE_SERVICE_ACCOUNT_PATH"] = "./firebase-service-account.json"
        print("✅ FIREBASE_SERVICE_ACCOUNT_PATH environment variable set")

        return True

    except Exception as e:
        print(f"❌ Error creating service account file: {e}")
        return False


def main():
    """Main function"""
    print("🚀 Firebase Production Setup Tool")
    print("=" * 50)

    # Check environment variables
    env_ok = check_firebase_config()

    if not env_ok:
        print("\n💡 To fix this, you need to set the missing environment variables.")
        print("   You can copy them from development.env file.")
        return

    # Try to create service account file
    if create_service_account_file():
        print("\n🔍 Testing Firebase after creating service account file...")

        # Test Firebase import
        if test_firebase_import():
            print("\n🎉 Firebase setup completed successfully!")
            print("\n📋 Next steps:")
            print("   1. Restart your FastAPI application")
            print("   2. Test authentication endpoints")
        else:
            print("\n❌ Firebase setup failed. Check the logs for details.")


if __name__ == "__main__":
    main()
