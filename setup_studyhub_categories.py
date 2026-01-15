"""
Seed StudyHub Categories and Create Indexes

Sets up:
- 10 fixed categories with bilingual names
- Required database indexes for performance
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from datetime import datetime, timezone
from src.database.db_manager import DBManager


# 10 Fixed Categories
CATEGORIES = [
    {
        "category_id": "it",
        "name_en": "Information Technology",
        "name_vi": "Công nghệ thông tin",
        "icon": "Code",
        "description_en": "Programming, Software Development, IT Infrastructure",
        "description_vi": "Lập trình, Phát triển phần mềm, Hạ tầng CNTT",
        "order_index": 1,
    },
    {
        "category_id": "business",
        "name_en": "Business",
        "name_vi": "Kinh doanh",
        "icon": "Briefcase",
        "description_en": "Business Management, Entrepreneurship, Marketing",
        "description_vi": "Quản trị kinh doanh, Khởi nghiệp, Marketing",
        "order_index": 2,
    },
    {
        "category_id": "finance",
        "name_en": "Finance",
        "name_vi": "Tài chính",
        "icon": "DollarSign",
        "description_en": "Finance, Accounting, Investment, Trading",
        "description_vi": "Tài chính, Kế toán, Đầu tư, Giao dịch",
        "order_index": 3,
    },
    {
        "category_id": "certificates",
        "name_en": "Certificates",
        "name_vi": "Chứng chỉ",
        "icon": "Award",
        "description_en": "Professional Certifications, Exam Preparation",
        "description_vi": "Chứng chỉ nghề nghiệp, Luyện thi chứng chỉ",
        "order_index": 4,
    },
    {
        "category_id": "languages",
        "name_en": "Languages",
        "name_vi": "Ngôn ngữ",
        "icon": "Languages",
        "description_en": "English, Chinese, Japanese, Korean, and more",
        "description_vi": "Tiếng Anh, Tiếng Trung, Tiếng Nhật, Tiếng Hàn,...",
        "order_index": 5,
    },
    {
        "category_id": "personal-dev",
        "name_en": "Personal Development",
        "name_vi": "Phát triển bản thân",
        "icon": "TrendingUp",
        "description_en": "Productivity, Leadership, Communication, Self-improvement",
        "description_vi": "Năng suất, Lãnh đạo, Giao tiếp, Cải thiện bản thân",
        "order_index": 6,
    },
    {
        "category_id": "lifestyle",
        "name_en": "Lifestyle",
        "name_vi": "Lối sống",
        "icon": "Heart",
        "description_en": "Health, Fitness, Cooking, Arts, Hobbies",
        "description_vi": "Sức khỏe, Thể hình, Nấu ăn, Nghệ thuật, Sở thích",
        "order_index": 7,
    },
    {
        "category_id": "academics",
        "name_en": "Academics",
        "name_vi": "Học thuật",
        "icon": "GraduationCap",
        "description_en": "Math, Physics, Chemistry, Literature, History",
        "description_vi": "Toán học, Vật lý, Hóa học, Văn học, Lịch sử",
        "order_index": 8,
    },
    {
        "category_id": "science",
        "name_en": "Science",
        "name_vi": "Khoa học",
        "icon": "Flask",
        "description_en": "Natural Sciences, Engineering, Research",
        "description_vi": "Khoa học tự nhiên, Kỹ thuật, Nghiên cứu",
        "order_index": 9,
    },
    {
        "category_id": "skill",
        "name_en": "Skills",
        "name_vi": "Kỹ năng",
        "icon": "Tool",
        "description_en": "Practical Skills, Crafts, Technical Skills",
        "description_vi": "Kỹ năng thực hành, Thủ công, Kỹ năng kỹ thuật",
        "order_index": 10,
    },
]


def seed_categories():
    """Seed categories (idempotent)"""
    print("=== Seeding StudyHub Categories ===\n")

    db_manager = DBManager()
    db = db_manager.db
    categories = db["studyhub_categories"]

    for cat_data in CATEGORIES:
        # Check if exists
        existing = categories.find_one({"category_id": cat_data["category_id"]})

        if existing:
            print(f"✓ Category '{cat_data['name_en']}' already exists")
            continue

        # Insert
        cat_doc = {**cat_data, "is_active": True}

        categories.insert_one(cat_doc)
        print(f"✓ Created category '{cat_data['name_en']}'")

    print(f"\nTotal categories: {categories.count_documents({})}")


def create_indexes():
    """Create all required indexes"""
    print("\n=== Creating Database Indexes ===\n")

    db_manager = DBManager()
    db = db_manager.db

    # 1. studyhub_categories
    print("1. studyhub_categories:")
    categories = db["studyhub_categories"]

    categories.create_index("category_id", unique=True)
    print("   - category_id (unique)")

    categories.create_index([("is_active", 1), ("order_index", 1)])
    print("   - is_active + order_index")

    # 2. studyhub_category_subjects
    print("\n2. studyhub_category_subjects:")
    subjects = db["studyhub_category_subjects"]

    subjects.create_index([("category_id", 1), ("slug", 1)], unique=True)
    print("   - category_id + slug (unique)")

    subjects.create_index([("category_id", 1), ("approved", 1), ("is_active", 1)])
    print("   - category_id + approved + is_active")

    subjects.create_index([("approved", 1), ("total_learners", -1)])
    print("   - approved + total_learners")

    subjects.create_index([("approved", 1), ("created_at", -1)])
    print("   - approved + created_at")

    # Text search on subjects
    subjects.create_index(
        [
            ("subject_name_en", "text"),
            ("subject_name_vi", "text"),
            ("description_en", "text"),
            ("description_vi", "text"),
        ]
    )
    print("   - text search (name + description)")

    # 3. studyhub_courses
    print("\n3. studyhub_courses:")
    courses = db["studyhub_courses"]

    courses.create_index("source_subject_id", unique=True)
    print("   - source_subject_id (unique)")

    courses.create_index([("category_id", 1), ("status", 1), ("visibility", 1)])
    print("   - category_id + status + visibility")

    courses.create_index([("category_subject_id", 1), ("status", 1)])
    print("   - category_subject_id + status")

    courses.create_index([("user_id", 1), ("status", 1)])
    print("   - user_id + status")

    courses.create_index([("status", 1), ("published_at", -1)])
    print("   - status + published_at")

    courses.create_index(
        [("status", 1), ("visibility", 1), ("stats.enrollment_count", -1)]
    )
    print("   - status + visibility + enrollment_count")

    courses.create_index(
        [("status", 1), ("visibility", 1), ("stats.average_rating", -1)]
    )
    print("   - status + visibility + average_rating")

    # Text search on courses
    courses.create_index([("title", "text"), ("description", "text"), ("tags", "text")])
    print("   - text search (title + description + tags)")

    # 4. studyhub_course_enrollments
    print("\n4. studyhub_course_enrollments:")
    enrollments = db["studyhub_course_enrollments"]

    enrollments.create_index([("course_id", 1), ("user_id", 1)], unique=True)
    print("   - course_id + user_id (unique)")

    enrollments.create_index([("user_id", 1), ("enrolled_at", -1)])
    print("   - user_id + enrolled_at")

    enrollments.create_index([("user_id", 1), ("last_accessed_at", -1)])
    print("   - user_id + last_accessed_at")

    enrollments.create_index([("course_id", 1), ("completed", 1)])
    print("   - course_id + completed")

    enrollments.create_index([("course_id", 1), ("rating", 1)])
    print("   - course_id + rating")

    print("\n✓ All indexes created successfully!")


def verify_setup():
    """Verify setup"""
    print("\n=== Verification ===\n")

    db_manager = DBManager()
    db = db_manager.db

    # Count categories
    cat_count = db["studyhub_categories"].count_documents({})
    print(f"Categories: {cat_count}/10")

    # List categories
    categories = list(db["studyhub_categories"].find({}).sort("order_index", 1))
    for cat in categories:
        print(f"  - {cat['name_en']} ({cat['category_id']})")

    # Check indexes
    print("\nIndexes created:")
    collections = [
        "studyhub_categories",
        "studyhub_category_subjects",
        "studyhub_courses",
        "studyhub_course_enrollments",
    ]

    for coll_name in collections:
        indexes = list(db[coll_name].list_indexes())
        print(f"\n{coll_name}: {len(indexes)} indexes")
        for idx in indexes:
            print(f"  - {idx['name']}")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("StudyHub Category System - Database Setup")
    print("=" * 60 + "\n")

    try:
        # 1. Seed categories
        seed_categories()

        # 2. Create indexes
        create_indexes()

        # 3. Verify
        verify_setup()

        print("\n" + "=" * 60)
        print("✓ Setup completed successfully!")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"\n✗ Error during setup: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
