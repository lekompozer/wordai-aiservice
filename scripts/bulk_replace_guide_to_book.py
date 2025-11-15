#!/usr/bin/env python3
"""
Bulk Find & Replace Script for Guide → Book Migration
Updates all terminology in renamed files
"""

import os
import re
from pathlib import Path

# Define replacements (order matters!)
REPLACEMENTS = [
    # Class names
    ("GuideManager", "BookManager"),
    ("ChapterManager", "BookChapterManager"),
    ("PermissionManager", "BookPermissionManager"),
    
    # Model classes
    ("GuideCreate", "BookCreate"),
    ("GuideUpdate", "BookUpdate"),
    ("GuideResponse", "BookResponse"),
    ("GuideListResponse", "BookListResponse"),
    ("GuideVisibility", "BookVisibility"),
    ("PublicGuideResponse", "PublicBookResponse"),
    ("GuideDomainResponse", "BookDomainResponse"),
    ("GuideStats", "BookStats"),
    
    # Collection names (in strings)
    ('"user_guides"', '"online_books"'),
    ("'user_guides'", "'online_books'"),
    ('"guide_chapters"', '"book_chapters"'),
    ("'guide_chapters'", "'book_chapters'"),
    ('"guide_permissions"', '"book_permissions"'),
    ("'guide_permissions'", "'book_permissions'"),
    
    # Field names (in strings)
    ('"guide_id"', '"book_id"'),
    ("'guide_id'", "'book_id'"),
    
    # Variable names (be careful with these)
    ("guide_id:", "book_id:"),
    ("guide_id =", "book_id ="),
    ("guide_id,", "book_id,"),
    ("guide_id)", "book_id)"),
    (".guide_id", ".book_id"),
    ('["guide_id"]', '["book_id"]'),
    ("['guide_id']", "['book_id']"),
    
    # Router prefix
    ('router = APIRouter(prefix="/api/v1/guides"', 'router = APIRouter(prefix="/api/v1/books"'),
    
    # Comments and docstrings
    ("User Guide API", "Online Book API"),
    ("user guide", "book"),
    ("User Guides", "Online Books"),
    ("guide management", "book management"),
]

FILES_TO_UPDATE = [
    "src/api/book_routes.py",
    "src/services/book_manager.py",
    "src/services/book_chapter_manager.py",
    "src/services/book_permission_manager.py",
    "src/models/book_models.py",
    "src/models/book_chapter_models.py",
    "src/models/book_permission_models.py",
    "src/models/public_book_models.py",
]

def replace_in_file(filepath: str):
    """Apply all replacements to a file"""
    print(f"\n📝 Processing: {filepath}")
    
    if not os.path.exists(filepath):
        print(f"   ⚠️  File not found, skipping")
        return
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    replacements_made = 0
    
    for old, new in REPLACEMENTS:
        if old in content:
            count = content.count(old)
            content = content.replace(old, new)
            replacements_made += count
            if count > 0:
                print(f"   ✅ {old} → {new} ({count} occurrences)")
    
    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"   💾 Saved with {replacements_made} replacements")
    else:
        print(f"   ℹ️  No changes needed")

def main():
    print("=" * 80)
    print("🔄 Bulk Find & Replace: Guide → Book")
    print("=" * 80)
    
    for filepath in FILES_TO_UPDATE:
        replace_in_file(filepath)
    
    print("\n" + "=" * 80)
    print("✅ All files updated!")
    print("=" * 80)
    print("\n⚠️  MANUAL REVIEW REQUIRED:")
    print("   - Check for any missed occurrences")
    print("   - Verify logic still makes sense")
    print("   - Run tests to catch errors")

if __name__ == "__main__":
    main()
