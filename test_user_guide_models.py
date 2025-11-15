"""
Test Pydantic Models for User Guide System
Phase 1: Model validation tests
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.models.user_guide_models import GuideCreate, GuideUpdate, GuideVisibility
from src.models.guide_chapter_models import (
    ChapterCreate,
    ChapterUpdate,
    ChapterReorderBulk,
)
from src.models.guide_permission_models import (
    PermissionCreate,
    PermissionInvite,
    AccessLevel,
)
from pydantic import ValidationError


def test_guide_models():
    """Test Guide models"""
    print("\n" + "=" * 60)
    print("📘 Testing Guide Models")
    print("=" * 60)

    # Test valid guide creation
    print("\n✅ Test 1: Valid guide creation")
    try:
        guide = GuideCreate(
            title="Getting Started Guide",
            description="Complete beginner guide",
            slug="getting-started-guide",
            visibility=GuideVisibility.PUBLIC,
            is_published=False,
            primary_color="#4F46E5",
        )
        print(f"   ✅ Created guide: {guide.title}")
        print(f"   - Slug: {guide.slug}")
        print(f"   - Visibility: {guide.visibility}")
    except ValidationError as e:
        print(f"   ❌ Validation failed: {e}")
        return False

    # Test invalid slug (uppercase)
    print("\n✅ Test 2: Invalid slug validation (uppercase)")
    try:
        invalid_guide = GuideCreate(
            title="Test Guide",
            slug="Invalid-Slug",  # Should fail
            visibility=GuideVisibility.PUBLIC,
        )
        print(f"   ❌ Should have failed validation!")
        return False
    except ValidationError as e:
        print(f"   ✅ Correctly rejected invalid slug")

    # Test invalid slug (special characters)
    print("\n✅ Test 3: Invalid slug validation (special chars)")
    try:
        invalid_guide = GuideCreate(
            title="Test Guide",
            slug="test_guide@123",  # Should fail
            visibility=GuideVisibility.PUBLIC,
        )
        print(f"   ❌ Should have failed validation!")
        return False
    except ValidationError as e:
        print(f"   ✅ Correctly rejected invalid slug")

    # Test guide update
    print("\n✅ Test 4: Guide update model")
    try:
        update = GuideUpdate(title="Updated Title", visibility=GuideVisibility.PRIVATE)
        print(f"   ✅ Update model valid")
    except ValidationError as e:
        print(f"   ❌ Validation failed: {e}")
        return False

    return True


def test_chapter_models():
    """Test Chapter models"""
    print("\n" + "=" * 60)
    print("📄 Testing Chapter Models")
    print("=" * 60)

    # Test valid chapter creation
    print("\n✅ Test 1: Valid chapter creation")
    try:
        chapter = ChapterCreate(
            document_id="doc_123",
            order=1,
            slug="introduction",
            title="Introduction",
            icon="📘",
        )
        print(f"   ✅ Created chapter: {chapter.title}")
        print(f"   - Slug: {chapter.slug}")
        print(f"   - Order: {chapter.order}")
    except ValidationError as e:
        print(f"   ❌ Validation failed: {e}")
        return False

    # Test invalid slug
    print("\n✅ Test 2: Invalid chapter slug")
    try:
        invalid_chapter = ChapterCreate(
            document_id="doc_123",
            order=1,
            slug="Introduction",  # Uppercase - should fail
            title="Introduction",
        )
        print(f"   ❌ Should have failed validation!")
        return False
    except ValidationError as e:
        print(f"   ✅ Correctly rejected invalid slug")

    # Test chapter update
    print("\n✅ Test 3: Chapter update model")
    try:
        update = ChapterUpdate(order=2, title="Updated Title", is_visible=False)
        print(f"   ✅ Update model valid")
    except ValidationError as e:
        print(f"   ❌ Validation failed: {e}")
        return False

    # Test bulk reorder
    print("\n✅ Test 4: Bulk reorder model")
    try:
        reorder = ChapterReorderBulk(
            chapters=[
                {"chapter_id": "ch1", "order": 1, "parent_chapter_id": None},
                {"chapter_id": "ch2", "order": 2, "parent_chapter_id": "ch1"},
            ]
        )
        print(f"   ✅ Bulk reorder model valid ({len(reorder.chapters)} chapters)")
    except ValidationError as e:
        print(f"   ❌ Validation failed: {e}")
        return False

    return True


def test_permission_models():
    """Test Permission models"""
    print("\n" + "=" * 60)
    print("🔐 Testing Permission Models")
    print("=" * 60)

    # Test permission create
    print("\n✅ Test 1: Grant permission")
    try:
        permission = PermissionCreate(
            user_id="firebase_uid_123", access_level=AccessLevel.VIEWER
        )
        print(f"   ✅ Permission model valid")
        print(f"   - Access level: {permission.access_level}")
    except ValidationError as e:
        print(f"   ❌ Validation failed: {e}")
        return False

    # Test email invitation
    print("\n✅ Test 2: Email invitation")
    try:
        invite = PermissionInvite(
            email="user@example.com",
            access_level=AccessLevel.VIEWER,
            message="Join our guide!",
        )
        print(f"   ✅ Invitation model valid")
        print(f"   - Email: {invite.email}")
    except ValidationError as e:
        print(f"   ❌ Validation failed: {e}")
        return False

    # Test invalid email
    print("\n✅ Test 3: Invalid email")
    try:
        invalid_invite = PermissionInvite(
            email="not-an-email", access_level=AccessLevel.VIEWER  # Should fail
        )
        print(f"   ❌ Should have failed validation!")
        return False
    except ValidationError as e:
        print(f"   ✅ Correctly rejected invalid email")

    return True


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("🧪 User Guide Models - Validation Tests")
    print("=" * 60)

    results = []

    # Test guides
    results.append(("Guide Models", test_guide_models()))

    # Test chapters
    results.append(("Chapter Models", test_chapter_models()))

    # Test permissions
    results.append(("Permission Models", test_permission_models()))

    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)

    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")

    all_passed = all(result[1] for result in results)

    print("\n" + "=" * 60)
    if all_passed:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed")
    print("=" * 60)

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
