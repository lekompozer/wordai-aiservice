#!/usr/bin/env python3
"""
Test Firebase Configuration for WordAI
Kiểm tra cấu hình Firebase mới cho project WordAI
"""

import os
import sys
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv('development.env')

def test_firebase_file():
    """Test Firebase credentials file"""
    print("🔥 Testing Firebase Credentials File...")
    
    cred_file = "firebase-credentials.json"
    if not os.path.exists(cred_file):
        print(f"❌ Firebase credentials file not found: {cred_file}")
        return False
    
    try:
        with open(cred_file, 'r') as f:
            creds = json.load(f)
        
        required_fields = [
            'type', 'project_id', 'private_key_id', 'private_key',
            'client_email', 'client_id', 'auth_uri', 'token_uri'
        ]
        
        missing_fields = [field for field in required_fields if field not in creds]
        if missing_fields:
            print(f"❌ Missing fields in credentials: {missing_fields}")
            return False
        
        print(f"✅ Firebase credentials file valid")
        print(f"   📋 Project ID: {creds['project_id']}")
        print(f"   📧 Client Email: {creds['client_email']}")
        print(f"   🔑 Private Key ID: {creds['private_key_id'][:20]}...")
        return True
        
    except Exception as e:
        print(f"❌ Error reading credentials file: {e}")
        return False

def test_environment_variables():
    """Test Firebase environment variables"""
    print("\n🌍 Testing Environment Variables...")
    
    env_vars = {
        'FIREBASE_PROJECT_ID': os.getenv('FIREBASE_PROJECT_ID'),
        'FIREBASE_CLIENT_EMAIL': os.getenv('FIREBASE_CLIENT_EMAIL'),
        'FIREBASE_PRIVATE_KEY_ID': os.getenv('FIREBASE_PRIVATE_KEY_ID'),
        'FIREBASE_PRIVATE_KEY': os.getenv('FIREBASE_PRIVATE_KEY'),
        'GOOGLE_APPLICATION_CREDENTIALS': os.getenv('GOOGLE_APPLICATION_CREDENTIALS'),
    }
    
    all_good = True
    for var_name, var_value in env_vars.items():
        if var_value:
            if var_name == 'FIREBASE_PRIVATE_KEY':
                print(f"✅ {var_name}: {var_value[:50]}...")
            else:
                print(f"✅ {var_name}: {var_value}")
        else:
            print(f"⚠️  {var_name}: Not set")
            if var_name in ['FIREBASE_PROJECT_ID', 'GOOGLE_APPLICATION_CREDENTIALS']:
                all_good = False
    
    return all_good

def test_firebase_import():
    """Test Firebase SDK import and initialization"""
    print("\n🐍 Testing Firebase SDK Import...")
    
    try:
        import firebase_admin
        from firebase_admin import credentials, auth
        print("✅ Firebase Admin SDK imported successfully")
        
        # Test credentials loading
        cred_file = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', 'firebase-credentials.json')
        if os.path.exists(cred_file):
            cred = credentials.Certificate(cred_file)
            print(f"✅ Credentials loaded from {cred_file}")
            
            # Test project ID
            project_id = cred.project_id
            expected_project_id = os.getenv('FIREBASE_PROJECT_ID', 'wordai-6779e')
            if project_id == expected_project_id:
                print(f"✅ Project ID matches: {project_id}")
                return True
            else:
                print(f"❌ Project ID mismatch: {project_id} != {expected_project_id}")
                return False
        else:
            print(f"❌ Credentials file not found: {cred_file}")
            return False
            
    except ImportError as e:
        print(f"❌ Firebase SDK not installed: {e}")
        print("   Run: pip install firebase-admin")
        return False
    except Exception as e:
        print(f"❌ Firebase initialization error: {e}")
        return False

def main():
    """Main test function"""
    print("🚀 WordAI Firebase Configuration Test")
    print("=" * 50)
    
    # Test results
    tests = [
        ("Firebase File", test_firebase_file),
        ("Environment Variables", test_environment_variables),
        ("Firebase SDK", test_firebase_import)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Summary:")
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status} {test_name}")
        if result:
            passed += 1
    
    print(f"\n🏆 Results: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 All Firebase tests passed! WordAI is ready to use Firebase.")
        return True
    else:
        print("⚠️  Some tests failed. Please check your Firebase configuration.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)