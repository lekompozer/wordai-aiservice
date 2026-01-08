"""
Create MongoDB indexes for StudyHub collections
Run this script after deploying to production
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from src.database.db_manager import DBManager
import logging

logger = logging.getLogger(__name__)


def create_studyhub_indexes():
    """Create all necessary indexes for StudyHub collections"""

    print("🔧 Creating StudyHub MongoDB indexes...")

    db_manager = DBManager()
    db = db_manager.db

    # ==================== SUBJECTS COLLECTION ====================
    print("\n📚 Creating indexes for studyhub_subjects...")

    subjects = db["studyhub_subjects"]

    # Index for owner queries
    subjects.create_index("owner_id")
    print("✅ Created index: owner_id")

    # Index for status queries
    subjects.create_index("status")
    print("✅ Created index: status")

    # Index for visibility queries
    subjects.create_index("visibility")
    print("✅ Created index: visibility")

    # Compound index for listing subjects
    subjects.create_index([("status", 1), ("visibility", 1), ("created_at", -1)])
    print("✅ Created compound index: status + visibility + created_at")

    # Compound index for owner's subjects
    subjects.create_index([("owner_id", 1), ("created_at", -1)])
    print("✅ Created compound index: owner_id + created_at")

    # Text search index for title and description
    subjects.create_index([("title", "text"), ("description", "text")])
    print("✅ Created text index: title + description")

    # Index for tags (metadata array)
    subjects.create_index("metadata.tags")
    print("✅ Created index: metadata.tags")

    # ==================== MODULES COLLECTION ====================
    print("\n📖 Creating indexes for studyhub_modules...")

    modules = db["studyhub_modules"]

    # Index for subject queries
    modules.create_index("subject_id")
    print("✅ Created index: subject_id")

    # Compound index for ordered modules
    modules.create_index([("subject_id", 1), ("order_index", 1)])
    print("✅ Created compound index: subject_id + order_index")

    # ==================== MODULE CONTENTS COLLECTION ====================
    print("\n📄 Creating indexes for studyhub_module_contents...")

    contents = db["studyhub_module_contents"]

    # Index for module queries
    contents.create_index("module_id")
    print("✅ Created index: module_id")

    # Compound index for ordered contents
    contents.create_index([("module_id", 1), ("order_index", 1)])
    print("✅ Created compound index: module_id + order_index")

    # Index for content type queries
    contents.create_index("content_type")
    print("✅ Created index: content_type")

    # Index for reference lookups (Phase 2)
    contents.create_index("reference_id")
    print("✅ Created index: reference_id")

    # ==================== ENROLLMENTS COLLECTION ====================
    print("\n🎓 Creating indexes for studyhub_enrollments...")

    enrollments = db["studyhub_enrollments"]

    # Index for user queries
    enrollments.create_index("user_id")
    print("✅ Created index: user_id")

    # Index for subject queries
    enrollments.create_index("subject_id")
    print("✅ Created index: subject_id")

    # Compound unique index to prevent duplicate enrollments
    enrollments.create_index([("user_id", 1), ("subject_id", 1)], unique=True)
    print("✅ Created unique compound index: user_id + subject_id")

    # Index for enrollment status
    enrollments.create_index("status")
    print("✅ Created index: status")

    # Compound index for active enrollments
    enrollments.create_index([("user_id", 1), ("status", 1)])
    print("✅ Created compound index: user_id + status")

    # Index for enrolled_at (sorting)
    enrollments.create_index("enrolled_at")
    print("✅ Created index: enrolled_at")

    # ==================== LEARNING PROGRESS COLLECTION ====================
    print("\n📊 Creating indexes for studyhub_learning_progress...")

    progress = db["studyhub_learning_progress"]

    # Compound index for user progress queries
    progress.create_index([("user_id", 1), ("subject_id", 1)])
    print("✅ Created compound index: user_id + subject_id")

    # Compound index for module progress
    progress.create_index([("user_id", 1), ("module_id", 1)])
    print("✅ Created compound index: user_id + module_id")

    # Compound index for content progress
    progress.create_index([("user_id", 1), ("content_id", 1)])
    print("✅ Created compound index: user_id + content_id")

    # Index for progress status
    progress.create_index("status")
    print("✅ Created index: status")

    # Index for last accessed tracking
    progress.create_index("updated_at")
    print("✅ Created index: updated_at")

    # ==================== SUBJECT PRICING COLLECTION (Phase 2) ====================
    print("\n💰 Creating indexes for studyhub_subject_pricing (Phase 2)...")

    pricing = db["studyhub_subject_pricing"]

    # Unique index for subject pricing
    pricing.create_index("subject_id", unique=True)
    print("✅ Created unique index: subject_id")

    # Index for free subjects
    pricing.create_index("is_free")
    print("✅ Created index: is_free")

    # Index for active discounts
    pricing.create_index("discount_active")
    print("✅ Created index: discount_active")

    # ==================== SUBJECT PURCHASES COLLECTION (Phase 2) ====================
    print("\n🛒 Creating indexes for studyhub_subject_purchases (Phase 2)...")

    purchases = db["studyhub_subject_purchases"]

    # Index for buyer queries
    purchases.create_index("buyer_id")
    print("✅ Created index: buyer_id")

    # Index for seller queries
    purchases.create_index("seller_id")
    print("✅ Created index: seller_id")

    # Index for subject queries
    purchases.create_index("subject_id")
    print("✅ Created index: subject_id")

    # Compound index for purchase history
    purchases.create_index([("buyer_id", 1), ("purchased_at", -1)])
    print("✅ Created compound index: buyer_id + purchased_at")

    # Index for transaction tracking
    purchases.create_index("transaction_id")
    print("✅ Created index: transaction_id")

    # Index for purchase status
    purchases.create_index("status")
    print("✅ Created index: status")

    # ==================== REVENUE RECORDS COLLECTION (Phase 2) ====================
    print("\n💵 Creating indexes for studyhub_revenue_records (Phase 2)...")

    revenue = db["studyhub_revenue_records"]

    # Compound index for user revenue queries
    revenue.create_index([("user_id", 1), ("created_at", -1)])
    print("✅ Created compound index: user_id + created_at")

    # Index for transaction type
    revenue.create_index("transaction_type")
    print("✅ Created index: transaction_type")

    # Index for subject revenue tracking
    revenue.create_index("subject_id")
    print("✅ Created index: subject_id")

    print("\n✅ All StudyHub indexes created successfully!")
    print("\n📝 Summary:")
    print("   - studyhub_subjects: 7 indexes")
    print("   - studyhub_modules: 2 indexes")
    print("   - studyhub_module_contents: 4 indexes")
    print("   - studyhub_enrollments: 5 indexes")
    print("   - studyhub_learning_progress: 5 indexes")
    print("   - studyhub_subject_pricing: 3 indexes (Phase 2)")
    print("   - studyhub_subject_purchases: 6 indexes (Phase 2)")
    print("   - studyhub_revenue_records: 3 indexes (Phase 2)")
    print("   Total: 35 indexes")


if __name__ == "__main__":
    try:
        create_studyhub_indexes()
    except Exception as e:
        logger.error(f"Error creating indexes: {e}")
        print(f"\n❌ Error: {e}")
        sys.exit(1)
