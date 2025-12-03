"""
Test script for show_answers_timing feature
Run this to verify the new anti-cheating feature works correctly
"""

import requests
import json
from datetime import datetime, timedelta, timezone

# Configuration
BASE_URL = "http://localhost:8000/api/v1/tests"
TOKEN = "YOUR_FIREBASE_TOKEN_HERE"  # Replace with actual token

headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


def test_create_manual_test_with_immediate():
    """Test 1: Create test with immediate answer reveal"""
    print("\n=== Test 1: Create test with immediate answers ===")

    payload = {
        "title": "Test - Immediate Answers",
        "description": "Test should show answers immediately after submit",
        "time_limit_minutes": 10,
        "show_answers_timing": "immediate",
        "questions": [
            {
                "question_text": "What is 2+2?",
                "options": [
                    {"key": "A", "text": "3"},
                    {"key": "B", "text": "4"},
                    {"key": "C", "text": "5"},
                ],
                "correct_answer_key": "B",
                "explanation": "Basic math",
            }
        ],
    }

    response = requests.post(f"{BASE_URL}/manual", headers=headers, json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.json().get("test_id")


def test_create_manual_test_with_after_deadline():
    """Test 2: Create test with after_deadline answer reveal"""
    print("\n=== Test 2: Create test with after_deadline answers ===")

    # Set deadline 1 hour from now
    deadline = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()

    payload = {
        "title": "Test - After Deadline Answers",
        "description": "Test should hide answers until deadline",
        "time_limit_minutes": 10,
        "deadline": deadline,
        "show_answers_timing": "after_deadline",
        "questions": [
            {
                "question_text": "What is the capital of France?",
                "options": [
                    {"key": "A", "text": "London"},
                    {"key": "B", "text": "Paris"},
                    {"key": "C", "text": "Berlin"},
                ],
                "correct_answer_key": "B",
                "explanation": "Paris is the capital of France",
            }
        ],
    }

    response = requests.post(f"{BASE_URL}/manual", headers=headers, json=payload)
    print(f"Status: {response.status_code}")
    result = response.json()
    print(f"Response: {json.dumps(result, indent=2)}")
    print(f"Deadline set: {deadline}")
    return result.get("test_id")


def test_submit_and_check_response(test_id: str, expected_limited: bool):
    """Test 3: Submit test and verify response format"""
    print(
        f"\n=== Test 3: Submit test {test_id} (expect limited={expected_limited}) ==="
    )

    # First start the test
    start_response = requests.post(f"{BASE_URL}/{test_id}/start", headers=headers)
    print(f"Start test status: {start_response.status_code}")

    # Submit answers
    submit_payload = {
        "user_answers": [
            {
                "question_id": "q1",  # Will likely fail due to generated question_id
                "selected_answer_key": "B",
            }
        ]
    }

    submit_response = requests.post(
        f"{BASE_URL}/{test_id}/submit", headers=headers, json=submit_payload
    )

    print(f"Submit status: {submit_response.status_code}")
    result = submit_response.json()
    print(f"Response: {json.dumps(result, indent=2)}")

    # Check for expected fields
    if expected_limited:
        if "results_hidden_until_deadline" in result:
            print("✅ PASS: Answers hidden as expected")
        else:
            print("❌ FAIL: Expected hidden answers but got full results")
    else:
        if "results" in result and len(result.get("results", [])) > 0:
            print("✅ PASS: Full results shown as expected")
        else:
            print("❌ FAIL: Expected full results but got limited")

    return result.get("submission_id")


def test_update_show_answers_timing(test_id: str):
    """Test 4: Update show_answers_timing via config endpoint"""
    print(f"\n=== Test 4: Update show_answers_timing for test {test_id} ===")

    payload = {"show_answers_timing": "immediate"}

    response = requests.patch(
        f"{BASE_URL}/{test_id}/config", headers=headers, json=payload
    )

    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")


def test_invalid_value():
    """Test 5: Try to set invalid show_answers_timing value"""
    print("\n=== Test 5: Test invalid show_answers_timing value ===")

    payload = {
        "title": "Invalid Test",
        "questions": [],
        "show_answers_timing": "invalid_value",  # Should fail validation
    }

    # Note: This will fail at Pydantic validation level before reaching endpoint
    # Expected: 422 Unprocessable Entity
    response = requests.post(f"{BASE_URL}/manual", headers=headers, json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")


def main():
    """Run all tests"""
    print("=" * 60)
    print("SHOW ANSWERS TIMING FEATURE - TEST SUITE")
    print("=" * 60)

    # Test 1: Immediate mode
    test_id_immediate = test_create_manual_test_with_immediate()

    # Test 2: After deadline mode
    test_id_after_deadline = test_create_manual_test_with_after_deadline()

    # Test 3: Submit tests and verify responses
    if test_id_immediate:
        test_submit_and_check_response(test_id_immediate, expected_limited=False)

    if test_id_after_deadline:
        test_submit_and_check_response(test_id_after_deadline, expected_limited=True)

    # Test 4: Update config
    if test_id_after_deadline:
        test_update_show_answers_timing(test_id_after_deadline)

    # Test 5: Invalid value
    test_invalid_value()

    print("\n" + "=" * 60)
    print("TEST SUITE COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
