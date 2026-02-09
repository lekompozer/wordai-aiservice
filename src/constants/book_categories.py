"""
Book Categories Structure for WordAI
11 Parent Categories → 33 Child Categories

Used by:
- Category crawler (nhasachmienphi.com)
- Community routes API
- Frontend category navigation
"""

from typing import Dict, List

# ============================================================================
# PARENT CATEGORIES (11 total)
# ============================================================================

PARENT_CATEGORIES = [
    {
        "id": "education",
        "name": "Education",
        "name_vi": "Giáo dục",
        "icon": "GraduationCap",
        "order": 1,
    },
    {
        "id": "business",
        "name": "Business",
        "name_vi": "Kinh doanh",
        "icon": "Briefcase",
        "order": 2,
    },
    {
        "id": "technology",
        "name": "Technology",
        "name_vi": "Công nghệ",
        "icon": "Code",
        "order": 3,
    },
    {
        "id": "health",
        "name": "Health",
        "name_vi": "Sức khỏe",
        "icon": "Heart",
        "order": 4,
    },
    {
        "id": "lifestyle",
        "name": "Lifestyle",
        "name_vi": "Lối sống",
        "icon": "Sparkles",
        "order": 5,
    },
    {
        "id": "entertainment",
        "name": "Entertainment",
        "name_vi": "Giải trí",
        "icon": "Film",
        "order": 6,
    },
    {
        "id": "literature-art",
        "name": "Literature & Art",
        "name_vi": "Văn học & Nghệ thuật",
        "icon": "BookOpen",
        "order": 7,
    },
    {
        "id": "children-stories",
        "name": "Children Stories",
        "name_vi": "Truyện thiếu nhi",
        "icon": "Baby",
        "order": 8,
    },
    {
        "id": "comics",
        "name": "Comics",
        "name_vi": "Truyện tranh",
        "icon": "Book",
        "order": 9,
    },
    {
        "id": "audiobooks",
        "name": "Audiobooks",
        "name_vi": "Sách nói",
        "icon": "Headphones",
        "order": 10,
    },
    {
        "id": "other",
        "name": "Other",
        "name_vi": "Khác",
        "icon": "MoreHorizontal",
        "order": 11,
    },
]

# ============================================================================
# CHILD CATEGORIES (33 total)
# ============================================================================

CHILD_CATEGORIES = [
    # Education (7 children)
    {"name": "Sách Giáo Khoa", "parent": "education", "slug": "sach-giao-khoa"},
    {"name": "Học Ngoại Ngữ", "parent": "education", "slug": "hoc-ngoai-ngu"},
    {"name": "Khoa Học - Kỹ Thuật", "parent": "education", "slug": "khoa-hoc-ky-thuat"},
    {
        "name": "Kiến Trúc - Xây Dựng",
        "parent": "education",
        "slug": "kien-truc-xay-dung",
    },
    {"name": "Nông - Lâm - Ngư", "parent": "education", "slug": "nong-lam-ngu"},
    {"name": "Thư Viện Pháp Luật", "parent": "education", "slug": "thu-vien-phap-luat"},
    {"name": "Triết Học", "parent": "education", "slug": "triet-hoc"},
    # Business (3 children)
    {"name": "Kinh Tế - Quản Lý", "parent": "business", "slug": "kinh-te-quan-ly"},
    {
        "name": "Marketing - Bán hàng",
        "parent": "business",
        "slug": "marketing-ban-hang",
    },
    {
        "name": "Tâm Lý - Kỹ Năng Sống",
        "parent": "business",
        "slug": "tam-ly-ky-nang-song",
    },
    # Technology (1 child)
    {
        "name": "Công Nghệ Thông Tin",
        "parent": "technology",
        "slug": "cong-nghe-thong-tin",
    },
    # Health (1 child)
    {"name": "Y Học - Sức Khỏe", "parent": "health", "slug": "y-hoc-suc-khoe"},
    # Lifestyle (4 children)
    {"name": "Ẩm thực - Nấu ăn", "parent": "lifestyle", "slug": "am-thuc-nau-an"},
    {
        "name": "Thể Thao - Nghệ Thuật",
        "parent": "lifestyle",
        "slug": "the-thao-nghe-thuat",
    },
    {"name": "Tử Vi - Phong Thủy", "parent": "lifestyle", "slug": "tu-vi-phong-thuy"},
    {
        "name": "Văn Hóa - Tôn Giáo",
        "parent": "lifestyle",
        "slug": "van-hoa-ton-giao",
    },
    # Entertainment (4 children)
    {
        "name": "Truyện Cười - Tiếu Lâm",
        "parent": "entertainment",
        "slug": "truyen-cuoi-tieu-lam",
    },
    {
        "name": "Phiêu Lưu - Mạo Hiểm",
        "parent": "entertainment",
        "slug": "phieu-luu-mao-hiem",
    },
    {
        "name": "Trinh Thám - Hình Sự",
        "parent": "entertainment",
        "slug": "trinh-tham-hinh-su",
    },
    {
        "name": "Truyện Ma - Truyện Kinh Dị",
        "parent": "entertainment",
        "slug": "truyen-ma-truyen-kinh-di",
    },
    # Literature & Art (7 children)
    {
        "name": "Văn Học Việt Nam",
        "parent": "literature-art",
        "slug": "van-hoc-viet-nam",
    },
    {
        "name": "Tiểu Thuyết Phương Tây",
        "parent": "literature-art",
        "slug": "tieu-thuyet-phuong-tay",
    },
    {
        "name": "Tiểu Thuyết Trung Quốc",
        "parent": "literature-art",
        "slug": "tieu-thuyet-trung-quoc",
    },
    {
        "name": "Truyện Ngắn - Ngôn Tình",
        "parent": "literature-art",
        "slug": "truyen-ngan-ngon-tinh",
    },
    {
        "name": "Kiếm Hiệp - Tiên Hiệp",
        "parent": "literature-art",
        "slug": "kiem-hiep-tien-hiep",
    },
    {"name": "Hồi Ký - Tuỳ Bút", "parent": "literature-art", "slug": "hoi-ky-tuy-but"},
    {"name": "Thơ Hay", "parent": "literature-art", "slug": "tho-hay"},
    # Children Stories (3 children)
    {
        "name": "Cổ Tích - Thần Thoại",
        "parent": "children-stories",
        "slug": "co-tich-than-thoai",
    },
    {
        "name": "Truyên Teen - Tuổi Học Trò",
        "parent": "children-stories",
        "slug": "truyen-teen-tuoi-hoc-tro",
    },
    {
        "name": "Huyền bí - Giả Tưởng",
        "parent": "children-stories",
        "slug": "huyen-bi-gia-tuong",
    },
    # Comics (1 child)
    {"name": "Truyện Tranh", "parent": "comics", "slug": "truyen-tranh"},
    # Audiobooks (1 child)
    {"name": "Sách nói miễn phí", "parent": "audiobooks", "slug": "sach-noi-mien-phi"},
    # Other (1 child)
    {"name": "Lịch Sử - Chính Trị", "parent": "other", "slug": "lich-su-chinh-tri"},
]

# ============================================================================
# MAPPING: NHASACHMIENPHI → WORDAI CHILD CATEGORIES
# ============================================================================

NHASACHMIENPHI_TO_WORDAI = {
    # nhasachmienphi slug → WordAI child category name
    # Business (3 categories)
    "kinh-te-quan-ly": "Kinh Tế - Quản Lý",
    "marketing-ban-hang": "Marketing - Bán hàng",
    "tam-ly-ky-nang-song": "Tâm Lý - Kỹ Năng Sống",
    "ky-nang-song": "Tâm Lý - Kỹ Năng Sống",
    "khoi-nghiep-khoi-nghiep": "Kinh Tế - Quản Lý",  # Map to Business
    "tai-chinh-ca-nhan": "Kinh Tế - Quản Lý",  # Map to Business
    "tam-ly-hoc": "Tâm Lý - Kỹ Năng Sống",
    "nuoi-day-con": "Tâm Lý - Kỹ Năng Sống",
    # Education (5 categories)
    "hoc-ngoai-ngu": "Học Ngoại Ngữ",
    "khoa-hoc-ky-thuat": "Khoa Học - Kỹ Thuật",
    "sach-giao-khoa": "Sách Giáo Khoa",
    "kien-truc-xay-dung": "Kiến Trúc - Xây Dựng",
    "nong-lam-ngu": "Nông - Lâm - Ngư",
    "triet-hoc": "Triết Học",
    "thu-vien-phap-luat": "Thư Viện Pháp Luật",
    "phap-luat": "Thư Viện Pháp Luật",
    # Technology (1 category)
    "cong-nghe-thong-tin": "Công Nghệ Thông Tin",
    # Health (1 category)
    "y-hoc-suc-khoe": "Y Học - Sức Khỏe",
    "suc-khoe-gioi-tinh": "Y Học - Sức Khỏe",
    # Lifestyle (3 categories)
    "am-thuc-nau-an": "Ẩm thực - Nấu ăn",
    "am-thuc": "Ẩm thực - Nấu ăn",
    "the-thao-nghe-thuat": "Thể Thao - Nghệ Thuật",
    "the-thao": "Thể Thao - Nghệ Thuật",
    "nghe-thuat": "Thể Thao - Nghệ Thuật",
    "tu-vi-phong-thuy": "Tử Vi - Phong Thủy",
    # Entertainment (4 categories)
    "truyen-cuoi-tieu-lam": "Truyện Cười - Tiếu Lâm",
    "phieu-luu-mao-hiem": "Phiêu Lưu - Mạo Hiểm",
    "du-lich": "Phiêu Lưu - Mạo Hiểm",
    "trinh-tham-hinh-su": "Trinh Thám - Hình Sự",
    "truyen-ma-truyen-kinh-di": "Truyện Ma - Truyện Kinh Dị",
    # Literature & Art (8 categories)
    "van-hoc-viet-nam": "Văn Học Việt Nam",
    "tieu-thuyet-phuong-tay": "Tiểu Thuyết Phương Tây",
    "tieu-thuyet-trung-quoc": "Tiểu Thuyết Trung Quốc",
    "truyen-ngan-ngon-tinh": "Truyện Ngắn - Ngôn Tình",
    "kiem-hiep-tien-hiep": "Kiếm Hiệp - Tiên Hiệp",
    "hoi-ky-tuy-but": "Hồi Ký - Tuỳ Bút",
    "tho-hay": "Thơ Hay",
    "van-hoa-ton-giao": "Văn Hóa - Tôn Giáo",
    "ton-giao-tam-linh": "Văn Hóa - Tôn Giáo",
    # Children Stories (3 categories)
    "co-tich-than-thoai": "Cổ Tích - Thần Thoại",
    "truyen-teen-tuoi-hoc-tro": "Truyên Teen - Tuổi Học Trò",
    "thieu-nhi": "Truyên Teen - Tuổi Học Trò",
    "huyen-bi-gia-tuong": "Huyền bí - Giả Tưởng",
    # Comics (1 category)
    "truyen-tranh": "Truyện Tranh",
    # Audiobooks (1 category)
    "sach-noi-mien-phi": "Sách nói miễn phí",
    # Other (1 category)
    "lich-su-chinh-tri": "Lịch Sử - Chính Trị",
    "lich-su": "Lịch Sử - Chính Trị",
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get_parent_category(child_name: str) -> str:
    """Get parent category ID from child category name"""
    for child in CHILD_CATEGORIES:
        if child["name"] == child_name:
            return child["parent"]
    return "other"


def get_child_slug(child_name: str) -> str:
    """Get child category slug from name"""
    for child in CHILD_CATEGORIES:
        if child["name"] == child_name:
            return child["slug"]
    return child_name.lower().replace(" ", "-")


def get_categories_tree() -> Dict[str, List[Dict]]:
    """Get full category tree (parent → children)"""
    tree = {}
    for parent in PARENT_CATEGORIES:
        parent_id = parent["id"]
        tree[parent_id] = {
            "info": parent,
            "children": [
                child for child in CHILD_CATEGORIES if child["parent"] == parent_id
            ],
        }
    return tree


def map_nhasachmienphi_category(nhasach_slug: str) -> tuple[str, str]:
    """
    Map nhasachmienphi category to WordAI categories

    Returns:
        (child_category_name, parent_category_id)
    """
    child_name = NHASACHMIENPHI_TO_WORDAI.get(nhasach_slug, "Khác")
    parent_id = get_parent_category(child_name)
    return (child_name, parent_id)


# ============================================================================
# VALIDATION
# ============================================================================

if __name__ == "__main__":
    print("=== WordAI Book Categories ===\n")

    print(f"📊 Total Parent Categories: {len(PARENT_CATEGORIES)}")
    print(f"📊 Total Child Categories: {len(CHILD_CATEGORIES)}")
    print(f"📊 Total nhasachmienphi mappings: {len(NHASACHMIENPHI_TO_WORDAI)}\n")

    # Print tree structure
    tree = get_categories_tree()
    for parent_id, data in tree.items():
        parent = data["info"]
        children = data["children"]
        print(f"{parent['name_vi']} ({parent['name']}): {len(children)} children")
        for child in children:
            print(f"  - {child['name']}")
        print()
