#!/usr/bin/env python3
"""
Update slide backgrounds for doc_06de72fea3d7
- Extract slide 8 background
- Apply to slides 9, 10, 11, 12
"""

import re
from src.database.db_manager import DBManager


def extract_slide_background(slide_html: str) -> str:
    """Extract background style from slide HTML"""
    # Match background: ... in style attribute
    match = re.search(r"background:\s*([^;]+);", slide_html)
    if match:
        return match.group(1)
    return None


def update_slide_background(slide_html: str, new_background: str) -> str:
    """Replace background in slide HTML"""
    # Replace existing background
    updated = re.sub(
        r"background:\s*[^;]+;", f"background: {new_background};", slide_html
    )
    return updated


def main():
    # Connect to database
    db_manager = DBManager()
    db = db_manager.db

    # Get document
    doc = db.documents.find_one({"document_id": "doc_06de72fea3d7"})
    if not doc:
        print("❌ Document not found")
        return

    html = doc["content_html"]
    print(f"✅ Found document: {doc['title']}")

    # Split into slides
    slides = re.split(r'(<div class="slide" data-slide-index=")', html)

    # Reconstruct slides with indices
    slide_htmls = {}
    for i in range(1, len(slides), 2):
        slide_content = slides[i] + slides[i + 1]
        # Extract index
        idx_match = re.search(r'data-slide-index="(\d+)"', slide_content)
        if idx_match:
            idx = int(idx_match.group(1))
            slide_htmls[idx] = slide_content

    print(f"📊 Total slides: {len(slide_htmls)}")

    # Get slide 8 background
    if 7 not in slide_htmls:
        print("❌ Slide 8 (index 7) not found")
        return

    slide_8_bg = extract_slide_background(slide_htmls[7])
    if not slide_8_bg:
        print("❌ No background found in slide 8")
        return

    print(f"\n🎨 Slide 8 background:")
    print(f"   {slide_8_bg}")

    # Apply to slides 9, 10, 11, 12
    target_indices = [8, 9, 10, 11]  # 0-indexed
    updated_count = 0

    for idx in target_indices:
        if idx in slide_htmls:
            old_bg = extract_slide_background(slide_htmls[idx])
            print(f"\n📝 Slide {idx+1} (index {idx}):")
            print(f"   Old: {old_bg}")
            print(f"   New: {slide_8_bg}")

            slide_htmls[idx] = update_slide_background(slide_htmls[idx], slide_8_bg)
            updated_count += 1

    # Reconstruct HTML
    new_html_parts = []
    for idx in sorted(slide_htmls.keys()):
        if idx == 0:
            new_html_parts.append(slide_htmls[idx])
        else:
            # Remove the opening tag part since it's already in the split
            new_html_parts.append(
                '<div class="slide" data-slide-index="' + slide_htmls[idx]
            )

    new_html = "".join(new_html_parts)

    # Update database
    result = db.documents.update_one(
        {"document_id": "doc_06de72fea3d7"}, {"$set": {"content_html": new_html}}
    )

    print(f"\n✅ Updated {updated_count} slides")
    print(f"✅ Database updated: {result.modified_count} document")


if __name__ == "__main__":
    main()
