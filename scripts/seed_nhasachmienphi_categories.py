#!/usr/bin/env python3
"""
Seed categories from nhasachmienphi.com to WordAI database
Usage: python seed_nhasachmienphi_categories.py
"""

from src.database.db_manager import DBManager
from datetime import datetime


def seed_categories():
    """Seed all 33 categories to book_categories collection"""

    db_manager = DBManager()
    db = db_manager.db

    categories = [
        {
            "category_id": "am-thuc-nau-an",
            "name_vi": "Ẩm thực - Nấu ăn",
            "name_en": "Cooking",
            "parent": "lifestyle",
        },
        {
            "category_id": "co-tich-than-thoai",
            "name_vi": "Cổ Tích - Thần Thoại",
            "name_en": "Fairy Tales",
            "parent": "lifestyle",
        },
        {
            "category_id": "cong-nghe-thong-tin",
            "name_vi": "Công Nghệ Thông Tin",
            "name_en": "Information Technology",
            "parent": "it",
        },
        {
            "category_id": "hoc-ngoai-ngu",
            "name_vi": "Học Ngoại Ngữ",
            "name_en": "Language Learning",
            "parent": "languages",
        },
        {
            "category_id": "hoi-ky-tuy-but",
            "name_vi": "Hồi Ký - Tuỳ Bút",
            "name_en": "Memoir - Essays",
            "parent": "lifestyle",
        },
        {
            "category_id": "huyen-bi-gia-tuong",
            "name_vi": "Huyền bí - Giả Tưởng",
            "name_en": "Mystery - Fantasy",
            "parent": "lifestyle",
        },
        {
            "category_id": "khoa-hoc-ky-thuat",
            "name_vi": "Khoa Học - Kỹ Thuật",
            "name_en": "Science - Engineering",
            "parent": "science",
        },
        {
            "category_id": "kiem-hiep-tien-hiep",
            "name_vi": "Kiếm Hiệp - Tiên Hiệp",
            "name_en": "Martial Arts - Cultivation",
            "parent": "lifestyle",
        },
        {
            "category_id": "kien-truc-xay-dung",
            "name_vi": "Kiến Trúc - Xây Dựng",
            "name_en": "Architecture - Construction",
            "parent": "science",
        },
        {
            "category_id": "kinh-te-quan-ly",
            "name_vi": "Kinh Tế - Quản Lý",
            "name_en": "Economics - Management",
            "parent": "business",
        },
        {
            "category_id": "lich-su-chinh-tri",
            "name_vi": "Lịch Sử - Chính Trị",
            "name_en": "History - Politics",
            "parent": "academics",
        },
        {
            "category_id": "marketing-ban-hang",
            "name_vi": "Marketing - Bán hàng",
            "name_en": "Marketing - Sales",
            "parent": "business",
        },
        {
            "category_id": "nong-lam-ngu",
            "name_vi": "Nông - Lâm - Ngư",
            "name_en": "Agriculture - Forestry - Fishery",
            "parent": "science",
        },
        {
            "category_id": "phieu-luu-mao-hiem",
            "name_vi": "Phiêu Lưu - Mạo Hiểm",
            "name_en": "Adventure",
            "parent": "lifestyle",
        },
        {
            "category_id": "sach-giao-khoa",
            "name_vi": "Sách Giáo Khoa",
            "name_en": "Textbooks",
            "parent": "academics",
        },
        {
            "category_id": "sach-noi-mien-phi",
            "name_vi": "Sách nói miễn phí",
            "name_en": "Free Audiobooks",
            "parent": "lifestyle",
        },
        {
            "category_id": "tam-ly-ky-nang-song",
            "name_vi": "Tâm Lý - Kỹ Năng Sống",
            "name_en": "Psychology - Life Skills",
            "parent": "personal-dev",
        },
        {
            "category_id": "the-thao-nghe-thuat",
            "name_vi": "Thể Thao - Nghệ Thuật",
            "name_en": "Sports - Arts",
            "parent": "lifestyle",
        },
        {
            "category_id": "tho-hay",
            "name_vi": "Thơ Hay",
            "name_en": "Poetry",
            "parent": "lifestyle",
        },
        {
            "category_id": "thu-vien-phap-luat",
            "name_vi": "Thư Viện Pháp Luật",
            "name_en": "Law Library",
            "parent": "academics",
        },
        {
            "category_id": "tieu-thuyet-phuong-tay",
            "name_vi": "Tiểu Thuyết Phương Tây",
            "name_en": "Western Novels",
            "parent": "lifestyle",
        },
        {
            "category_id": "tieu-thuyet-trung-quoc",
            "name_vi": "Tiểu Thuyết Trung Quốc",
            "name_en": "Chinese Novels",
            "parent": "lifestyle",
        },
        {
            "category_id": "triet-hoc",
            "name_vi": "Triết Học",
            "name_en": "Philosophy",
            "parent": "academics",
        },
        {
            "category_id": "trinh-tham-hinh-su",
            "name_vi": "Trinh Thám - Hình Sự",
            "name_en": "Detective - Crime",
            "parent": "lifestyle",
        },
        {
            "category_id": "truyen-cuoi-tieu-lam",
            "name_vi": "Truyện Cười - Tiếu Lâm",
            "name_en": "Comedy - Jokes",
            "parent": "lifestyle",
        },
        {
            "category_id": "truyen-ma-kinh-di",
            "name_vi": "Truyện Ma - Truyện Kinh Dị",
            "name_en": "Horror Stories",
            "parent": "lifestyle",
        },
        {
            "category_id": "truyen-ngan-ngon-tinh",
            "name_vi": "Truyện Ngắn - Ngôn Tình",
            "name_en": "Short Stories - Romance",
            "parent": "lifestyle",
        },
        {
            "category_id": "truyen-teen-tuoi-hoc-tro",
            "name_vi": "Truyện Teen - Tuổi Học Trò",
            "name_en": "Teen Stories",
            "parent": "lifestyle",
        },
        {
            "category_id": "truyen-tranh",
            "name_vi": "Truyện Tranh",
            "name_en": "Comics",
            "parent": "lifestyle",
        },
        {
            "category_id": "tu-vi-phong-thuy",
            "name_vi": "Tử Vi - Phong Thủy",
            "name_en": "Astrology - Feng Shui",
            "parent": "lifestyle",
        },
        {
            "category_id": "van-hoa-ton-giao",
            "name_vi": "Văn Hóa - Tôn Giáo",
            "name_en": "Culture - Religion",
            "parent": "lifestyle",
        },
        {
            "category_id": "van-hoc-viet-nam",
            "name_vi": "Văn Học Việt Nam",
            "name_en": "Vietnamese Literature",
            "parent": "lifestyle",
        },
        {
            "category_id": "y-hoc-suc-khoe",
            "name_vi": "Y Học - Sức Khỏe",
            "name_en": "Medicine - Health",
            "parent": "science",
        },
    ]

    print("🗂️  Seeding nhasachmienphi.com categories...")
    print(f"Total categories: {len(categories)}")

    inserted = 0
    skipped = 0

    for cat in categories:
        # Check if already exists
        existing = db.book_categories.find_one({"category_id": cat["category_id"]})

        if existing:
            print(f"  ⏭️  Skip: {cat['name_vi']} (already exists)")
            skipped += 1
        else:
            # Insert new category
            doc = {
                **cat,
                "icon": "📚",  # Default icon
                "description_vi": f"Danh mục {cat['name_vi']}",
                "description_en": cat["name_en"],
                "order_index": inserted,
                "is_active": True,
                "book_count": 0,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
            db.book_categories.insert_one(doc)
            print(f"  ✅ Added: {cat['name_vi']}")
            inserted += 1

    print(f"\n✅ Seeding completed!")
    print(f"   Inserted: {inserted}")
    print(f"   Skipped: {skipped}")
    print(f"   Total: {inserted + skipped}")


if __name__ == "__main__":
    seed_categories()
