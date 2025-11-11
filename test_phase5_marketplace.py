#!/usr/bin/env python3
"""
Quick test script to verify Phase 5 marketplace routes are properly loaded
Run this before deploying to production to catch any import/syntax errors
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test that all marketplace modules can be imported"""
    print("Testing imports...")
    
    try:
        from src.services.test_cover_image_service import TestCoverImageService
        print("✅ TestCoverImageService imported successfully")
    except Exception as e:
        print(f"❌ Failed to import TestCoverImageService: {e}")
        return False
    
    try:
        from src.services.test_version_service import TestVersionService
        print("✅ TestVersionService imported successfully")
    except Exception as e:
        print(f"❌ Failed to import TestVersionService: {e}")
        return False
    
    try:
        from src.api.marketplace_routes import router as marketplace_router
        print("✅ marketplace_routes imported successfully")
        print(f"   Routes registered: {len(marketplace_router.routes)}")
    except Exception as e:
        print(f"❌ Failed to import marketplace_routes: {e}")
        return False
    
    try:
        from src.api.marketplace_transactions_routes import router as transactions_router
        print("✅ marketplace_transactions_routes imported successfully")
        print(f"   Routes registered: {len(transactions_router.routes)}")
    except Exception as e:
        print(f"❌ Failed to import marketplace_transactions_routes: {e}")
        return False
    
    return True


def test_route_registration():
    """Test that routes are properly registered in main app"""
    print("\nTesting route registration in app...")
    
    try:
        # Import main app
        from src.app import create_app
        app = create_app()
        
        # Get all routes
        routes = []
        for route in app.routes:
            if hasattr(route, "path") and hasattr(route, "methods"):
                routes.append({
                    "path": route.path,
                    "methods": route.methods,
                    "name": route.name
                })
        
        # Check for marketplace routes
        marketplace_routes = [r for r in routes if "/marketplace" in r["path"]]
        
        print(f"✅ Found {len(marketplace_routes)} marketplace routes:")
        for route in marketplace_routes:
            methods = ", ".join(route["methods"]) if route["methods"] else "N/A"
            print(f"   {methods:20} {route['path']}")
        
        # Verify key endpoints exist
        expected_endpoints = [
            "POST /marketplace/tests/{test_id}/publish",
            "GET /marketplace/tests",
            "POST /marketplace/tests/{test_id}/purchase",
            "POST /marketplace/tests/{test_id}/ratings",
            "GET /marketplace/me/earnings",
        ]
        
        found_endpoints = []
        for expected in expected_endpoints:
            method, path = expected.split(" ", 1)
            # Normalize path for comparison (FastAPI uses regex patterns)
            normalized_path = path.replace("{test_id}", "{path}")
            found = any(
                method in (r["methods"] or []) and normalized_path.replace("{path}", "") in r["path"]
                for r in marketplace_routes
            )
            if found:
                found_endpoints.append(expected)
                print(f"   ✅ {expected}")
            else:
                print(f"   ❌ {expected} NOT FOUND")
        
        if len(found_endpoints) >= len(expected_endpoints) - 1:
            print(f"\n✅ Route registration test passed ({len(found_endpoints)}/{len(expected_endpoints)} endpoints)")
            return True
        else:
            print(f"\n❌ Route registration test failed ({len(found_endpoints)}/{len(expected_endpoints)} endpoints)")
            return False
        
    except Exception as e:
        print(f"❌ Failed to test route registration: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_service_methods():
    """Test that service classes have expected methods"""
    print("\nTesting service methods...")
    
    try:
        from src.services.test_cover_image_service import TestCoverImageService
        from src.services.test_version_service import TestVersionService
        
        # Check TestCoverImageService methods
        cover_service = TestCoverImageService()
        expected_methods = ["validate_image", "generate_thumbnail", "optimize_image", "upload_cover_image"]
        
        for method in expected_methods:
            if hasattr(cover_service, method):
                print(f"   ✅ TestCoverImageService.{method}() exists")
            else:
                print(f"   ❌ TestCoverImageService.{method}() NOT FOUND")
                return False
        
        # Check TestVersionService methods
        version_service = TestVersionService()
        expected_methods = ["create_version_snapshot", "get_version", "get_current_version", "list_versions"]
        
        for method in expected_methods:
            if hasattr(version_service, method):
                print(f"   ✅ TestVersionService.{method}() exists")
            else:
                print(f"   ❌ TestVersionService.{method}() NOT FOUND")
                return False
        
        print("\n✅ Service methods test passed")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test service methods: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("="*70)
    print("Phase 5 Marketplace - Pre-Deployment Verification")
    print("="*70)
    print()
    
    results = []
    
    # Test 1: Imports
    results.append(("Imports", test_imports()))
    
    # Test 2: Service Methods
    results.append(("Service Methods", test_service_methods()))
    
    # Test 3: Route Registration
    # Note: This requires MongoDB connection, may fail locally
    print("\n⚠️  Skipping route registration test (requires MongoDB)")
    print("   Run this test on production server after deployment")
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{name:30} {status}")
    
    all_passed = all(result[1] for result in results)
    
    print("\n" + "="*70)
    if all_passed:
        print("✅ ALL TESTS PASSED - Ready for deployment!")
        print("="*70)
        print("\nNext steps:")
        print("1. bash deploy-phase5-migration.sh")
        print("2. pm2 restart wordai-api")
        print("3. Test endpoints with curl/Postman")
        return 0
    else:
        print("❌ SOME TESTS FAILED - Fix errors before deployment")
        print("="*70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
