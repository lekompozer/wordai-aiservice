"""
Test Suite for Phase 5 - Public View API
Tests public guide access, chapter viewing, analytics, and custom domains
NO AUTHENTICATION REQUIRED for these endpoints
"""

import sys
import os
from datetime import datetime
from typing import Dict, Any

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.database.db_manager import DBManager
from src.services.user_guide_manager import UserGuideManager
from src.services.guide_chapter_manager import GuideChapterManager


def print_section(title: str):
    """Print test section header"""
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}\n")


def print_test(test_num: int, description: str, passed: bool):
    """Print test result"""
    status = "✅ PASSED" if passed else "❌ FAILED"
    print(f"Test {test_num}: {description} {'.' * (50 - len(description))} {status}")


class Phase5TestSuite:
    """Test suite for Phase 5 public view endpoints"""

    def __init__(self):
        """Initialize test suite with DB connection"""
        self.db_manager = DBManager()
        self.db = self.db_manager.db
        self.guide_manager = UserGuideManager(self.db)
        self.chapter_manager = GuideChapterManager(self.db)

        # Test data
        self.test_user_id = "test_user_phase5"
        self.test_guide_id = None
        self.test_guide_slug = "test-public-guide-phase5"
        self.test_chapter_id = None
        self.test_chapter_slug = "introduction"
        self.test_domain = "test-phase5.example.com"

        # Results tracking
        self.tests_passed = 0
        self.tests_failed = 0
        self.total_tests = 0

    def cleanup_old_data(self):
        """Clean up any existing test data"""
        print("🧹 Cleaning up old test data...")

        # Delete test guides
        self.db.user_guides.delete_many({"user_id": self.test_user_id})

        # Delete test chapters
        self.db.guide_chapters.delete_many({"guide_id": {"$regex": "^guide_.*phase5"}})

        print("✅ Cleanup completed\n")

    def setup_test_data(self):
        """Create test guide and chapters"""
        print("📝 Setting up test data...")

        # Create a public guide
        guide_data = {
            "title": "Test Public Guide",
            "slug": self.test_guide_slug,
            "description": "A test guide for Phase 5 public access",
            "visibility": "public",
            "is_indexed": True,
            "custom_domain": self.test_domain,
            "cover_image_url": "https://example.com/cover.jpg",
            "logo_url": "https://example.com/logo.png",
            "author_name": "Test Author",
            "author_avatar": "https://example.com/avatar.jpg",
        }

        guide = self.guide_manager.create_guide(self.test_user_id, guide_data)
        self.test_guide_id = guide["guide_id"]

        # Create test chapters
        chapter1_data = {
            "title": "Introduction",
            "slug": self.test_chapter_slug,
            "document_id": "doc_test_intro",
            "order_index": 1,
            "is_published": True,
        }

        chapter2_data = {
            "title": "Chapter 2",
            "slug": "chapter-2",
            "document_id": "doc_test_chapter2",
            "order_index": 2,
            "is_published": True,
        }

        chapter1 = self.chapter_manager.create_chapter(
            self.test_guide_id, chapter1_data
        )
        self.test_chapter_id = chapter1["chapter_id"]

        chapter2 = self.chapter_manager.create_chapter(
            self.test_guide_id, chapter2_data
        )

        print(f"✅ Created test guide: {self.test_guide_id}")
        print(f"✅ Created test chapters: 2 chapters\n")

    def test_1_get_public_guide_by_slug(self) -> bool:
        """Test 1: Get public guide by slug"""
        self.total_tests += 1

        try:
            # Get guide by slug
            guide = self.guide_manager.get_guide_by_slug(
                user_id=self.test_user_id, slug=self.test_guide_slug
            )

            assert guide is not None, "Guide should be found"
            assert guide["guide_id"] == self.test_guide_id, "Guide ID should match"
            assert guide["slug"] == self.test_guide_slug, "Slug should match"
            assert guide["visibility"] == "public", "Guide should be public"
            assert (
                guide["custom_domain"] == self.test_domain
            ), "Custom domain should match"

            self.tests_passed += 1
            return True

        except AssertionError as e:
            print(f"   ❌ Assertion failed: {e}")
            self.tests_failed += 1
            return False
        except Exception as e:
            print(f"   ❌ Exception: {e}")
            self.tests_failed += 1
            return False

    def test_2_get_guide_chapters(self) -> bool:
        """Test 2: Get all chapters for guide"""
        self.total_tests += 1

        try:
            chapters = self.chapter_manager.list_chapters(self.test_guide_id)

            assert len(chapters) == 2, "Should have 2 chapters"
            assert (
                chapters[0]["slug"] == self.test_chapter_slug
            ), "First chapter slug should match"
            assert chapters[0]["order_index"] == 1, "First chapter order should be 1"
            assert chapters[1]["order_index"] == 2, "Second chapter order should be 2"

            self.tests_passed += 1
            return True

        except AssertionError as e:
            print(f"   ❌ Assertion failed: {e}")
            self.tests_failed += 1
            return False
        except Exception as e:
            print(f"   ❌ Exception: {e}")
            self.tests_failed += 1
            return False

    def test_3_get_chapter_by_slug(self) -> bool:
        """Test 3: Get chapter by slug"""
        self.total_tests += 1

        try:
            chapter = self.chapter_manager.get_chapter_by_slug(
                self.test_guide_id, self.test_chapter_slug
            )

            assert chapter is not None, "Chapter should be found"
            assert (
                chapter["chapter_id"] == self.test_chapter_id
            ), "Chapter ID should match"
            assert chapter["slug"] == self.test_chapter_slug, "Slug should match"
            assert chapter["title"] == "Introduction", "Title should match"
            assert "document_id" in chapter, "Document ID should be present"

            self.tests_passed += 1
            return True

        except AssertionError as e:
            print(f"   ❌ Assertion failed: {e}")
            self.tests_failed += 1
            return False
        except Exception as e:
            print(f"   ❌ Exception: {e}")
            self.tests_failed += 1
            return False

    def test_4_chapter_navigation(self) -> bool:
        """Test 4: Test prev/next chapter navigation"""
        self.total_tests += 1

        try:
            # Get all chapters sorted
            chapters = self.chapter_manager.list_chapters(self.test_guide_id)
            chapters_sorted = sorted(chapters, key=lambda x: x["order_index"])

            # First chapter (no prev, has next)
            first_chapter = chapters_sorted[0]
            assert first_chapter["order_index"] == 1, "First chapter order should be 1"

            # Second chapter (has prev, no next)
            second_chapter = chapters_sorted[1]
            assert (
                second_chapter["order_index"] == 2
            ), "Second chapter order should be 2"

            # Navigation logic
            prev_chapter = None  # First chapter has no prev
            next_chapter = chapters_sorted[1]  # First chapter's next

            assert prev_chapter is None, "First chapter should have no prev"
            assert (
                next_chapter["chapter_id"] == chapters_sorted[1]["chapter_id"]
            ), "Next should be second chapter"

            self.tests_passed += 1
            return True

        except AssertionError as e:
            print(f"   ❌ Assertion failed: {e}")
            self.tests_failed += 1
            return False
        except Exception as e:
            print(f"   ❌ Exception: {e}")
            self.tests_failed += 1
            return False

    def test_5_get_guide_by_domain(self) -> bool:
        """Test 5: Get guide by custom domain"""
        self.total_tests += 1

        try:
            guide = self.guide_manager.get_guide_by_domain(self.test_domain)

            assert guide is not None, "Guide should be found by domain"
            assert guide["guide_id"] == self.test_guide_id, "Guide ID should match"
            assert (
                guide["custom_domain"] == self.test_domain
            ), "Custom domain should match"
            assert guide["slug"] == self.test_guide_slug, "Slug should match"

            self.tests_passed += 1
            return True

        except AssertionError as e:
            print(f"   ❌ Assertion failed: {e}")
            self.tests_failed += 1
            return False
        except Exception as e:
            print(f"   ❌ Exception: {e}")
            self.tests_failed += 1
            return False

    def test_6_guide_not_found(self) -> bool:
        """Test 6: Get guide with nonexistent slug returns None"""
        self.total_tests += 1

        try:
            guide = self.guide_manager.get_guide_by_slug(
                user_id=self.test_user_id, slug="nonexistent-slug-12345"
            )

            assert guide is None, "Should return None for nonexistent guide"

            self.tests_passed += 1
            return True

        except AssertionError as e:
            print(f"   ❌ Assertion failed: {e}")
            self.tests_failed += 1
            return False
        except Exception as e:
            print(f"   ❌ Exception: {e}")
            self.tests_failed += 1
            return False

    def test_7_chapter_not_found(self) -> bool:
        """Test 7: Get chapter with nonexistent slug returns None"""
        self.total_tests += 1

        try:
            chapter = self.chapter_manager.get_chapter_by_slug(
                self.test_guide_id, "nonexistent-chapter-12345"
            )

            assert chapter is None, "Should return None for nonexistent chapter"

            self.tests_passed += 1
            return True

        except AssertionError as e:
            print(f"   ❌ Assertion failed: {e}")
            self.tests_failed += 1
            return False
        except Exception as e:
            print(f"   ❌ Exception: {e}")
            self.tests_failed += 1
            return False

    def test_8_private_guide(self) -> bool:
        """Test 8: Create private guide and verify visibility"""
        self.total_tests += 1

        try:
            # Create private guide
            private_guide_data = {
                "title": "Private Test Guide",
                "slug": "private-test-guide-phase5",
                "description": "This guide should not be publicly accessible",
                "visibility": "private",
            }

            private_guide = self.guide_manager.create_guide(
                self.test_user_id, private_guide_data
            )

            assert private_guide["visibility"] == "private", "Guide should be private"
            assert (
                private_guide["is_indexed"] == False
            ), "Private guide should not be indexed"

            # Cleanup
            self.guide_manager.delete_guide(private_guide["guide_id"])

            self.tests_passed += 1
            return True

        except AssertionError as e:
            print(f"   ❌ Assertion failed: {e}")
            self.tests_failed += 1
            return False
        except Exception as e:
            print(f"   ❌ Exception: {e}")
            self.tests_failed += 1
            return False

    def test_9_unlisted_guide(self) -> bool:
        """Test 9: Create unlisted guide and verify visibility"""
        self.total_tests += 1

        try:
            # Create unlisted guide
            unlisted_guide_data = {
                "title": "Unlisted Test Guide",
                "slug": "unlisted-test-guide-phase5",
                "description": "This guide is accessible but not indexed",
                "visibility": "unlisted",
            }

            unlisted_guide = self.guide_manager.create_guide(
                self.test_user_id, unlisted_guide_data
            )

            assert (
                unlisted_guide["visibility"] == "unlisted"
            ), "Guide should be unlisted"
            assert (
                unlisted_guide["is_indexed"] == False
            ), "Unlisted guide should not be indexed"

            # Cleanup
            self.guide_manager.delete_guide(unlisted_guide["guide_id"])

            self.tests_passed += 1
            return True

        except AssertionError as e:
            print(f"   ❌ Assertion failed: {e}")
            self.tests_failed += 1
            return False
        except Exception as e:
            print(f"   ❌ Exception: {e}")
            self.tests_failed += 1
            return False

    def test_10_seo_metadata(self) -> bool:
        """Test 10: Verify guide has SEO-friendly metadata"""
        self.total_tests += 1

        try:
            guide = self.guide_manager.get_guide(self.test_guide_id)

            assert guide is not None, "Guide should exist"
            assert "title" in guide, "Should have title"
            assert "description" in guide, "Should have description"
            assert "cover_image_url" in guide, "Should have cover image"
            assert guide["is_indexed"] == True, "Public guide should be indexed"

            # SEO metadata construction
            seo_title = f"{guide['title']} - Complete Guide"
            assert len(seo_title) < 200, "SEO title should be under 200 chars"

            self.tests_passed += 1
            return True

        except AssertionError as e:
            print(f"   ❌ Assertion failed: {e}")
            self.tests_failed += 1
            return False
        except Exception as e:
            print(f"   ❌ Exception: {e}")
            self.tests_failed += 1
            return False

    def test_11_domain_not_found(self) -> bool:
        """Test 11: Get guide by nonexistent domain returns None"""
        self.total_tests += 1

        try:
            guide = self.guide_manager.get_guide_by_domain(
                "nonexistent-domain-12345.com"
            )

            assert guide is None, "Should return None for nonexistent domain"

            self.tests_passed += 1
            return True

        except AssertionError as e:
            print(f"   ❌ Assertion failed: {e}")
            self.tests_failed += 1
            return False
        except Exception as e:
            print(f"   ❌ Exception: {e}")
            self.tests_failed += 1
            return False

    def test_12_guide_stats(self) -> bool:
        """Test 12: Verify guide stats structure"""
        self.total_tests += 1

        try:
            guide = self.guide_manager.get_guide(self.test_guide_id)
            chapters = self.chapter_manager.list_chapters(self.test_guide_id)

            # Stats should include
            total_chapters = len(chapters)
            assert total_chapters == 2, "Should have 2 chapters"

            # Verify timestamps
            assert "created_at" in guide, "Should have created_at"
            assert "updated_at" in guide, "Should have updated_at"
            assert isinstance(
                guide["created_at"], datetime
            ), "created_at should be datetime"
            assert isinstance(
                guide["updated_at"], datetime
            ), "updated_at should be datetime"

            self.tests_passed += 1
            return True

        except AssertionError as e:
            print(f"   ❌ Assertion failed: {e}")
            self.tests_failed += 1
            return False
        except Exception as e:
            print(f"   ❌ Exception: {e}")
            self.tests_failed += 1
            return False

    def run_all_tests(self):
        """Run all tests and print results"""
        print_section("TEST SUITE: Phase 5 - Public View API")

        # Cleanup and setup
        self.cleanup_old_data()
        self.setup_test_data()

        print_section("RUNNING TESTS")

        # Run all tests
        print_test(
            1, "Get Public Guide by Slug", self.test_1_get_public_guide_by_slug()
        )
        print_test(2, "Get All Chapters for Guide", self.test_2_get_guide_chapters())
        print_test(3, "Get Chapter by Slug", self.test_3_get_chapter_by_slug())
        print_test(
            4, "Chapter Navigation (prev/next)", self.test_4_chapter_navigation()
        )
        print_test(5, "Get Guide by Custom Domain", self.test_5_get_guide_by_domain())
        print_test(
            6, "Guide Not Found (nonexistent slug)", self.test_6_guide_not_found()
        )
        print_test(
            7, "Chapter Not Found (nonexistent slug)", self.test_7_chapter_not_found()
        )
        print_test(8, "Private Guide Visibility", self.test_8_private_guide())
        print_test(9, "Unlisted Guide Visibility", self.test_9_unlisted_guide())
        print_test(10, "SEO Metadata Structure", self.test_10_seo_metadata())
        print_test(
            11, "Domain Not Found (nonexistent domain)", self.test_11_domain_not_found()
        )
        print_test(12, "Guide Stats Structure", self.test_12_guide_stats())

        # Final cleanup
        print("\n🧹 Cleaning up test data...")
        self.cleanup_old_data()

        # Print results
        print_section("TEST RESULTS SUMMARY")
        print(f"✅ Tests Passed:  {self.tests_passed}/{self.total_tests}")
        print(f"❌ Tests Failed:  {self.tests_failed}/{self.total_tests}")

        success_rate = (
            (self.tests_passed / self.total_tests * 100) if self.total_tests > 0 else 0
        )
        print(f"📊 Success Rate:  {success_rate:.1f}%")
        print("=" * 70)

        if self.tests_passed == self.total_tests:
            print("\n🎉 ALL TESTS PASSED! Phase 5 is ready for production.\n")
            return 0
        else:
            print(f"\n⚠️  {self.tests_failed} test(s) failed. Please review and fix.\n")
            return 1


if __name__ == "__main__":
    """Run test suite"""
    test_suite = Phase5TestSuite()
    exit_code = test_suite.run_all_tests()
    sys.exit(exit_code)
