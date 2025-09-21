#!/usr/bin/env python3
"""
Test Firebase Authentication Configuration
Verify that Firebase Admin SDK is properly configured
"""

import os
import sys
sys.path.append('src')

# Load environment variables
with open('.env', 'r') as f:
    for line in f:
        if line.strip() and not line.startswith('#') and '=' in line:
            key, value = line.strip().split('=', 1)
            value = value.strip('"\'')
            os.environ[key] = value

def test_firebase_config():
    """Test Firebase configuration"""
    print("🔥 Testing Firebase Configuration")
    print("=" * 50)

    # Check environment variables
    required_vars = [
        'FIREBASE_PROJECT_ID',
        'FIREBASE_PRIVATE_KEY',
        'FIREBASE_CLIENT_EMAIL',
        'FIREBASE_CLIENT_ID'
    ]

    print("📋 Environment Variables:")
    for var in required_vars:
        value = os.getenv(var)
        if value:
            if var == 'FIREBASE_PRIVATE_KEY':
                print(f"  ✅ {var}: [PRIVATE_KEY_SET] (length: {len(value)})")
            else:
                print(f"  ✅ {var}: {value}")
        else:
            print(f"  ❌ {var}: NOT SET")

    print("\n🔧 Firebase Admin SDK Test:")
    try:
        from src.config.firebase_config import FirebaseConfig
        firebase_config = FirebaseConfig()

        if firebase_config.app:
            print("  ✅ Firebase Admin SDK initialized successfully")
            print(f"  📁 Project ID: {firebase_config.app.project_id}")
        else:
            print("  ❌ Firebase Admin SDK initialization failed")

    except Exception as e:
        print(f"  ❌ Error initializing Firebase: {e}")

    print("\n🌐 OAuth Configuration Needed:")
    print("  Go to Google Cloud Console → APIs & Services → Credentials")
    print("  Find your OAuth 2.0 Client ID and add:")
    print("  ")
    print("  Authorized JavaScript Origins:")
    print("    - https://aivungtau.com")
    print("    - https://www.aivungtau.com")
    print("    - https://aivungtau-34724.firebaseapp.com")
    print("  ")
    print("  Authorized Redirect URIs:")
    print("    - https://aivungtau-34724.firebaseapp.com/__/auth/handler")

    print("\n🔥 Firebase Console Settings:")
    print("  Go to Firebase Console → Authentication → Sign-in method")
    print("  Ensure authorized domains include:")
    print("    - aivungtau.com")
    print("    - www.aivungtau.com")
    print("    - aivungtau-34724.firebaseapp.com")

if __name__ == "__main__":
    test_firebase_config()
