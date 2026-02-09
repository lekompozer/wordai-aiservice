"""
Script to classify books in "Khác" category based on title patterns
"""

import json
import re
from src.constants.book_categories import CHILD_CATEGORIES


def get_parent_for_child(child_name):
    """Get parent category for a child category name"""
    for child in CHILD_CATEGORIES:
        if child["name"] == child_name:
            return child["parent"]
    return "other"


def classify_by_title(title):
    """Classify book based on title patterns - FOCUS on top 3 categories"""
    title_lower = title.lower()

    # === PRIORITY 1: TÂM LÝ - KỸ NĂNG SỐNG ===
    tam_ly_keywords = [
        "tâm lý",
        "kỹ năng",
        "phát triển bản thân",
        "thành công",
        "tư duy",
        "chinh phục",
        "đắc nhân tâm",
        "nghệ thuật sống",
        "hạnh phúc",
        "tự tin",
        "giao tiếp",
        "lãnh đạo",
        "quản trị bản thân",
        "sống tích cực",
        "động lực",
        "thay đổi",
        "khởi nghiệp",
        # NEW keywords
        "bài học",
        "bí quyết",
        "vấn đề",
        "giải pháp",
        "phương pháp",
        "cách",
        "bí mật",
        "chìa khóa",
        "nguyên tắc",
        # Additional keywords
        "tài chính",
        "đàm phán",
        "văn minh",
        "dạy bạn",
        "thương lượng",
        "định vị",
        "tiêu tiền",
        "phải học",
        "nghệ thuật",
        "việc cần làm",
        "bạn nghĩ",
        "nghĩ lớn",
        "diễn thuyết",
        "bất kỳ ai",
        "cho bạn",
        "giải tỏa stress",
    ]
    if any(word in title_lower for word in tam_ly_keywords):
        return "Tâm Lý - Kỹ Năng Sống", "business"

    # === PRIORITY 2: ẨM THỰC - NẤU ĂN ===
    am_thuc_keywords = [
        "ẩm thực",
        "nấu ăn",
        "món ăn",
        "công thức",
        "dạy nấu",
        "bếp",
        "đầu bếp",
        "nhà hàng",
        "food",
        "recipe",
        "chế biến",
        "ngon",
        "cà phê",
        "bánh",
        "canh",
        "súp",
        "cơm",
    ]
    if any(word in title_lower for word in am_thuc_keywords):
        return "Ẩm thực - Nấu ăn", "lifestyle"

    # === TRIẾT HỌC (check before default) ===
    if "triết" in title_lower:
        return "Triết Học", "education"

    # === LỊCH SỬ - CHÍNH TRỊ (check before default) ===
    if any(
        word in title_lower
        for word in [
            "lịch sử",
            "danh nhân",
            "sử",
            "chiến tranh",
            "sự thật",
            "Tiên sinh",
            "chân dung",
            "Đại Truyện",
            "Binh Thư",
            "Mưu Trí",
            "Cuộc dời",
            "Dư Luận",
            "Thế giới",
            "Chính Trị",
            "Mưu Trí",
            "Thương lượng",
            "Ngàn năm",
            "chế độ",
            "Sài Gòn",
            "Điệp viên",
            "Truyền thuyết",
            "Tuyển tập",
            "Bách khoa",
            "Năm",
            "Quyền lực",
            "Sử ký",
            "lược sử",
            "Kỷ nguyên",
            "Bàn về",
            "Quyền lực",
            "Chinh phạt",
            "Văn Minh",
            "Bác Hồ",
            "Danh Nhân",
            "phong trào",
            "Nam Kỳ",
            "Bắc Kinh",
            "Trung Quốc",
            "sử",
            "việt nam",
        ]
    ):
        return "Lịch Sử - Chính Trị", "other"

    # === PRIORITY 3: TIỂU THUYẾT PHƯƠNG TÂY (DEFAULT) ===
    # Tất cả còn lại đều là Tiểu Thuyết Phương Tây
    return "Tiểu Thuyết Phương Tây", "literature-art"


def main():
    # Load books
    with open("khac_books.json", "r", encoding="utf-8") as f:
        books = json.load(f)

    print(f"Total books to classify: {len(books)}")

    # Classify each book
    classified_books = []
    category_counts = {}

    for book in books:
        title = book["title"]
        new_child, new_parent = classify_by_title(title)

        # Count
        key = f"{new_parent} > {new_child}"
        category_counts[key] = category_counts.get(key, 0) + 1

        # Add classification
        classified_books.append(
            {
                "_id": book["_id"],
                "title": title,
                "url": book["metadata"]["source_url"],
                "old_category": book["community_config"]["category"],
                "old_parent": book["community_config"]["parent_category"],
                "new_category": new_child,
                "new_parent": new_parent,
            }
        )

    # Save classified books
    with open("khac_books_classified.json", "w", encoding="utf-8") as f:
        json.dump(classified_books, f, ensure_ascii=False, indent=2)

    # Print summary
    print("\n=== CLASSIFICATION SUMMARY ===")

    # Highlight top 3 priority categories
    priority_cats = [
        "business > Tâm Lý - Kỹ Năng Sống",
        "lifestyle > Ẩm thực - Nấu ăn",
        "literature-art > Tiểu Thuyết Phương Tây",
    ]

    print("\n🎯 TOP 3 PRIORITY CATEGORIES:")
    for cat in priority_cats:
        count = category_counts.get(cat, 0)
        print(f"  {cat:50} : {count:4} books")

    print("\n📊 ALL CATEGORIES:")
    for category, count in sorted(category_counts.items(), key=lambda x: -x[1]):
        print(f"  {category:50} : {count:4} books")

    # Show samples for each category
    print("\n=== SAMPLES BY CATEGORY ===")
    for category in sorted(set(category_counts.keys())):
        samples = [
            b
            for b in classified_books
            if f"{b['new_parent']} > {b['new_category']}" == category
        ][:3]
        print(f"\n{category}:")
        for s in samples:
            print(f"  - {s['title']}")

    print(f"\n✅ Saved to: khac_books_classified.json")
    print("Review the file, then run update script to upload to production.")


if __name__ == "__main__":
    main()
