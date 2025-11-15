"""
Test Suite for Phase 4: User Permissions API
Tests grant, list, revoke, and invite endpoints for guide permissions
"""

import sys
import os
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from src.database.db_manager import DBManager
from src.services.user_guide_manager import UserGuideManager
from src.services.guide_permission_manager import GuidePermissionManager


def test_permissions_api():
    """Test all Phase 4 permission endpoints"""

    print("\n" + "=" * 70)
    print("TEST SUITE: Phase 4 - User Permissions API")
    print("=" * 70 + "\n")

    # Initialize
    db_manager = DBManager()
    db = db_manager.db

    guide_manager = UserGuideManager(db)
    permission_manager = GuidePermissionManager(db)

    # Test data
    owner_id = "test_owner_phase4_" + str(int(datetime.utcnow().timestamp()))
    viewer_id = "test_viewer_phase4_" + str(int(datetime.utcnow().timestamp()))
    viewer2_id = "test_viewer2_phase4_" + str(int(datetime.utcnow().timestamp()))

    guide_id = None
    permission_id = None

    tests_passed = 0
    tests_failed = 0

    try:
        # Setup: Create a test guide
        print("📋 Setup: Creating test guide...")
        guide = guide_manager.create_guide(
            user_id=owner_id,
            guide_data={
                "title": "Private Guide for Permissions Test",
                "slug": f"private-guide-{owner_id}",
                "description": "Testing permissions",
                "visibility": "private",
            },
        )
        guide_id = guide["guide_id"]
        print(f"✅ Guide created: {guide_id}\n")

        # ======================================================================
        # Test 1: Grant Permission
        # ======================================================================
        print("Test 1: Grant Permission to User")
        print("-" * 70)

        try:
            permission = permission_manager.grant_permission(
                guide_id=guide_id,
                user_id=viewer_id,
                granted_by=owner_id,
                access_level="viewer",
            )

            permission_id = permission["permission_id"]

            assert permission["guide_id"] == guide_id
            assert permission["user_id"] == viewer_id
            assert permission["granted_by"] == owner_id
            assert permission["access_level"] == "viewer"

            print(f"✅ PASSED - Permission granted: {permission_id}")
            tests_passed += 1
        except Exception as e:
            print(f"❌ FAILED - {e}")
            tests_failed += 1

        print()

        # ======================================================================
        # Test 2: Check Permission (User has access)
        # ======================================================================
        print("Test 2: Check Permission - User has access")
        print("-" * 70)

        try:
            has_permission = permission_manager.check_permission(
                guide_id=guide_id, user_id=viewer_id
            )

            assert has_permission is not None
            assert has_permission["user_id"] == viewer_id

            print(f"✅ PASSED - User has permission")
            tests_passed += 1
        except Exception as e:
            print(f"❌ FAILED - {e}")
            tests_failed += 1

        print()

        # ======================================================================
        # Test 3: Check Permission (User doesn't have access)
        # ======================================================================
        print("Test 3: Check Permission - User doesn't have access")
        print("-" * 70)

        try:
            has_permission = permission_manager.check_permission(
                guide_id=guide_id, user_id=viewer2_id
            )

            assert has_permission is None

            print(f"✅ PASSED - User correctly denied (no permission)")
            tests_passed += 1
        except Exception as e:
            print(f"❌ FAILED - {e}")
            tests_failed += 1

        print()

        # ======================================================================
        # Test 4: Grant Duplicate Permission (Should fail)
        # ======================================================================
        print("Test 4: Grant Duplicate Permission - Should fail")
        print("-" * 70)

        try:
            # Try to grant permission again
            try:
                permission_manager.grant_permission(
                    guide_id=guide_id,
                    user_id=viewer_id,
                    granted_by=owner_id,
                    access_level="viewer",
                )
                print(f"❌ FAILED - Should have raised DuplicateKeyError")
                tests_failed += 1
            except Exception as e:
                if "duplicate" in str(e).lower() or "E11000" in str(e):
                    print(f"✅ PASSED - Duplicate permission correctly rejected")
                    tests_passed += 1
                else:
                    raise e
        except Exception as e:
            print(f"❌ FAILED - {e}")
            tests_failed += 1

        print()

        # ======================================================================
        # Test 5: Grant Permission to Second User
        # ======================================================================
        print("Test 5: Grant Permission to Second User")
        print("-" * 70)

        try:
            permission2 = permission_manager.grant_permission(
                guide_id=guide_id,
                user_id=viewer2_id,
                granted_by=owner_id,
                access_level="viewer",
            )

            assert permission2["user_id"] == viewer2_id

            print(f"✅ PASSED - Second permission granted: {permission2['permission_id']}")
            tests_passed += 1
        except Exception as e:
            print(f"❌ FAILED - {e}")
            tests_failed += 1

        print()

        # ======================================================================
        # Test 6: List Permissions (Should return 2)
        # ======================================================================
        print("Test 6: List Permissions - Should return 2")
        print("-" * 70)

        try:
            permissions = permission_manager.list_permissions(guide_id=guide_id)

            assert len(permissions) == 2
            user_ids = [p["user_id"] for p in permissions]
            assert viewer_id in user_ids
            assert viewer2_id in user_ids

            print(f"✅ PASSED - Found {len(permissions)} permissions")
            for p in permissions:
                print(f"   - {p['user_id']}: {p['access_level']}")
            tests_passed += 1
        except Exception as e:
            print(f"❌ FAILED - {e}")
            tests_failed += 1

        print()

        # ======================================================================
        # Test 7: List Permissions with Pagination
        # ======================================================================
        print("Test 7: List Permissions with Pagination (limit=1)")
        print("-" * 70)

        try:
            permissions_page1 = permission_manager.list_permissions(
                guide_id=guide_id, skip=0, limit=1
            )
            permissions_page2 = permission_manager.list_permissions(
                guide_id=guide_id, skip=1, limit=1
            )

            assert len(permissions_page1) == 1
            assert len(permissions_page2) == 1
            assert permissions_page1[0]["user_id"] != permissions_page2[0]["user_id"]

            print(f"✅ PASSED - Pagination works correctly")
            print(f"   Page 1: {permissions_page1[0]['user_id']}")
            print(f"   Page 2: {permissions_page2[0]['user_id']}")
            tests_passed += 1
        except Exception as e:
            print(f"❌ FAILED - {e}")
            tests_failed += 1

        print()

        # ======================================================================
        # Test 8: Count Permissions
        # ======================================================================
        print("Test 8: Count Permissions")
        print("-" * 70)

        try:
            count = permission_manager.count_permissions(guide_id=guide_id)

            assert count == 2

            print(f"✅ PASSED - Count: {count}")
            tests_passed += 1
        except Exception as e:
            print(f"❌ FAILED - {e}")
            tests_failed += 1

        print()

        # ======================================================================
        # Test 9: Revoke Permission
        # ======================================================================
        print("Test 9: Revoke Permission")
        print("-" * 70)

        try:
            success = permission_manager.revoke_permission(
                guide_id=guide_id, user_id=viewer_id
            )

            assert success is True

            # Verify permission removed
            has_permission = permission_manager.check_permission(
                guide_id=guide_id, user_id=viewer_id
            )
            assert has_permission is None

            print(f"✅ PASSED - Permission revoked successfully")
            tests_passed += 1
        except Exception as e:
            print(f"❌ FAILED - {e}")
            tests_failed += 1

        print()

        # ======================================================================
        # Test 10: List Permissions After Revoke (Should return 1)
        # ======================================================================
        print("Test 10: List Permissions After Revoke")
        print("-" * 70)

        try:
            permissions = permission_manager.list_permissions(guide_id=guide_id)

            assert len(permissions) == 1
            assert permissions[0]["user_id"] == viewer2_id

            print(f"✅ PASSED - Only 1 permission remains: {viewer2_id}")
            tests_passed += 1
        except Exception as e:
            print(f"❌ FAILED - {e}")
            tests_failed += 1

        print()

        # ======================================================================
        # Test 11: Create Invitation (Email-based)
        # ======================================================================
        print("Test 11: Create Invitation by Email")
        print("-" * 70)

        try:
            invitation = permission_manager.create_invitation(
                guide_id=guide_id,
                email="test@example.com",
                granted_by=owner_id,
                access_level="viewer",
                expires_at=datetime.utcnow() + timedelta(days=7),
                message="Check out this guide!",
            )

            assert invitation is not None, "Invitation should not be None"
            assert invitation["invited_email"] == "test@example.com", f"Email mismatch: {invitation['invited_email']}"
            assert invitation["invitation_accepted"] is False, f"Should not be accepted yet: {invitation['invitation_accepted']}"
            assert invitation["invitation_token"] is not None, "Token should not be None"
            assert len(invitation["invitation_token"]) == 43, f"Token length should be 43: {len(invitation['invitation_token'])}"  # URL-safe token

            print(f"✅ PASSED - Invitation created")
            print(f"   Email: {invitation['invited_email']}")
            print(f"   Token: {invitation['invitation_token'][:8]}...")
            print(f"   Message: {invitation.get('invitation_message', 'None')}")
            tests_passed += 1
        except AssertionError as e:
            print(f"❌ FAILED - Assertion: {e}")
            tests_failed += 1
        except Exception as e:
            print(f"❌ FAILED - {e}")
            tests_failed += 1

        print()

        # ======================================================================
        # Test 12: List Permissions with Pending Invitations
        # ======================================================================
        print("Test 12: List Permissions with Pending Invitations")
        print("-" * 70)

        try:
            # Without pending
            permissions_accepted = permission_manager.list_permissions(
                guide_id=guide_id, include_pending=False
            )

            # With pending
            permissions_all = permission_manager.list_permissions(
                guide_id=guide_id, include_pending=True
            )

            assert len(permissions_accepted) == 1  # viewer2 only
            assert len(permissions_all) == 2  # viewer2 + pending invitation

            print(f"✅ PASSED")
            print(f"   Accepted only: {len(permissions_accepted)}")
            print(f"   Including pending: {len(permissions_all)}")
            tests_passed += 1
        except Exception as e:
            print(f"❌ FAILED - {e}")
            tests_failed += 1

        print()

    finally:
        # Cleanup
        print("🧹 Cleanup: Removing test data...")
        if guide_id:
            # Delete permissions first (cascade)
            deleted_perms = permission_manager.delete_permissions_by_guide(guide_id)
            print(f"   Deleted {deleted_perms} permissions")

            # Delete guide
            guide_manager.delete_guide(guide_id)
            print(f"   Deleted guide: {guide_id}")

    # Summary
    print("\n" + "=" * 70)
    print("TEST RESULTS SUMMARY")
    print("=" * 70)
    print(f"✅ Tests Passed:  {tests_passed}/12")
    print(f"❌ Tests Failed:  {tests_failed}/12")
    print(f"📊 Success Rate:  {tests_passed/12*100:.1f}%")
    print("=" * 70 + "\n")

    if tests_failed == 0:
        print("🎉 ALL TESTS PASSED! Phase 4 is ready for production.\n")
        return True
    else:
        print(f"⚠️  {tests_failed} test(s) failed. Please fix before deploying.\n")
        return False


if __name__ == "__main__":
    success = test_permissions_api()
    sys.exit(0 if success else 1)
