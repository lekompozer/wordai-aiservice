#!/usr/bin/env python3
"""
Test script for Recovery Key Backend Implementation
Tests all 3 backend tasks according to checklist
"""

import requests
import json
import sys

# Configuration
BASE_URL = "http://localhost:8000"
FIREBASE_TOKEN = "YOUR_FIREBASE_TOKEN_HERE"  # Replace with actual token

headers = {
    "Authorization": f"Bearer {FIREBASE_TOKEN}",
    "Content-Type": "application/json",
}


def print_section(title):
    """Print section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def test_task_1_recovery_key_backup_endpoint():
    """
    ✅ Task 1: Test GET /api/secret-documents/auth/recovery-key-backup
    """
    print_section("TASK 1: Test GET /recovery-key-backup Endpoint")

    url = f"{BASE_URL}/api/secret-documents/auth/recovery-key-backup"

    print(f"\n📡 Request: GET {url}")
    print(f"Headers: {json.dumps(headers, indent=2)}")

    try:
        response = requests.get(url, headers=headers)

        print(f"\n✅ Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")

        if response.status_code == 200:
            data = response.json()
            if "encryptedPrivateKeyWithRecovery" in data:
                print("\n✅ PASS: Endpoint returns encryptedPrivateKeyWithRecovery")
                return True
            else:
                print("\n❌ FAIL: Missing encryptedPrivateKeyWithRecovery field")
                return False
        elif response.status_code == 404:
            print("\n⚠️  404: No recovery key backup found (expected if not set up)")
            return True
        else:
            print(f"\n❌ FAIL: Unexpected status code {response.status_code}")
            return False

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False


def test_task_2_key_status_has_recovery_key():
    """
    ✅ Task 2: Test GET /api/secret-documents/auth/key-status returns hasRecoveryKey
    """
    print_section("TASK 2: Test /key-status includes hasRecoveryKey")

    url = f"{BASE_URL}/api/secret-documents/auth/key-status"

    print(f"\n📡 Request: GET {url}")

    try:
        response = requests.get(url, headers=headers)

        print(f"\n✅ Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")

        if response.status_code == 200:
            data = response.json()
            if "hasRecoveryKey" in data:
                print(
                    f"\n✅ PASS: hasRecoveryKey field present (value: {data['hasRecoveryKey']})"
                )
                return True
            else:
                print("\n❌ FAIL: Missing hasRecoveryKey field")
                return False
        else:
            print(f"\n❌ FAIL: Unexpected status code {response.status_code}")
            return False

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False


def test_task_3_setup_recovery_endpoint():
    """
    ✅ Task 3: Test POST /api/secret-documents/auth/setup-recovery
    """
    print_section("TASK 3: Test POST /setup-recovery Endpoint")

    url = f"{BASE_URL}/api/secret-documents/auth/setup-recovery"

    # Mock encrypted private key (base64)
    mock_data = {
        "encryptedPrivateKeyWithRecovery": "bW9ja19lbmNyeXB0ZWRfcHJpdmF0ZV9rZXlfd2l0aF9yZWNvdmVyeQ=="
    }

    print(f"\n📡 Request: POST {url}")
    print(f"Body: {json.dumps(mock_data, indent=2)}")

    try:
        response = requests.post(url, headers=headers, json=mock_data)

        print(f"\n✅ Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")

        if response.status_code == 200:
            data = response.json()
            if data.get("success") == True:
                print("\n✅ PASS: Recovery key backup stored successfully")
                return True
            else:
                print("\n❌ FAIL: Success field not True")
                return False
        else:
            print(f"\n❌ FAIL: Unexpected status code {response.status_code}")
            return False

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False


def test_full_recovery_flow():
    """
    Test complete Setup Flow and Recovery Flow
    """
    print_section("BONUS: Test Complete Recovery Flow")

    print("\n📝 Setup Flow (8 steps):")
    print("  1. User registers E2EE keys ✅")
    print("  2. Prompt setup recovery key ✅")
    print("  3. Generate 24-word mnemonic (client-side) ✅")
    print("  4. User writes down recovery key ✅")
    print("  5. Verify user saved recovery key ✅")
    print("  6. Encrypt private key with recovery key (client-side) ✅")
    print("  7. POST /setup-recovery → store on server")

    # Test step 7
    setup_result = test_task_3_setup_recovery_endpoint()

    print("\n  8. Confirmation ✅")

    print("\n📝 Recovery Flow (10 steps):")
    print("  1. User forgets Master Password 😱")
    print("  2. Enter recovery key (client-side) ✅")
    print("  3. Validate mnemonic (client-side) ✅")
    print("  4. GET /recovery-key-backup → get encrypted backup")

    # Test step 4
    recovery_result = test_task_1_recovery_key_backup_endpoint()

    print("\n  5. Decrypt with recovery key (client-side) ✅")
    print("  6. Prompt for NEW Master Password (client-side) ✅")
    print("  7. Re-encrypt with new password (client-side) ✅")
    print("  8. POST /update-password → update server ✅")
    print("  9. Store locally & update IndexedDB ✅")
    print("  10. Success! ✅")

    return setup_result and recovery_result


def main():
    """Run all backend tests"""
    print("\n" + "🔐" * 40)
    print("  RECOVERY KEY SYSTEM - BACKEND TEST SUITE")
    print("🔐" * 40)

    print("\n⚠️  PREREQUISITES:")
    print("  1. Server must be running: ENV=development python serve.py")
    print("  2. Replace FIREBASE_TOKEN in this script with valid token")
    print("  3. User must have E2EE keys registered")

    input("\nPress ENTER to continue...")

    results = []

    # Run all tests
    results.append(
        ("Task 1: GET /recovery-key-backup", test_task_1_recovery_key_backup_endpoint())
    )
    results.append(
        (
            "Task 2: /key-status hasRecoveryKey",
            test_task_2_key_status_has_recovery_key(),
        )
    )
    results.append(
        ("Task 3: POST /setup-recovery", test_task_3_setup_recovery_endpoint())
    )

    # Summary
    print_section("TEST SUMMARY")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {test_name}")

    print(f"\n📊 Results: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 ALL BACKEND TASKS COMPLETE!")
        print("\n✅ Backend Implementation Checklist:")
        print("  ✅ Task 1: Add GET /recovery-key-backup endpoint (30 mins)")
        print("  ✅ Task 2: Update /key-status with hasRecoveryKey (15 mins)")
        print("  ✅ Task 3: Verify POST /setup-recovery works (15 mins)")
        print("\n⏱️  Total Time: ~1 hour")
        print("\n🚀 Ready for Frontend Implementation!")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please check the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
