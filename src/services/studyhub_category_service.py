"""
StudyHub Category & Course Service

Handles:
- Category operations
- Category subject CRUD
- Course publishing & management
- Course enrollment
- Progress tracking
- Statistics & aggregations
"""

import re
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from pymongo import DESCENDING, ASCENDING
from pymongo.errors import DuplicateKeyError

from src.database.db_manager import DBManager
from src.models.studyhub_category_models import (
    CategoryID,
    CourseLevel,
    PriceType,
    CourseStatus,
    CourseVisibility,
    SortOption,
    Category,
    CategorySubject,
    Course,
    CourseEnrollment,
    CategoryStats,
    CourseStats,
    CourseProgress,
    CourseInstructor,
    CourseModule,
    TopInstructor,
)


class StudyHubCategoryService:
    """Service for StudyHub category & course operations"""

    def __init__(self):
        self.db_manager = DBManager()
        self.db = self.db_manager.db

        # Collections
        self.categories = self.db["studyhub_categories"]
        self.category_subjects = self.db["studyhub_category_subjects"]
        self.courses = self.db["studyhub_courses"]
        self.enrollments = self.db["studyhub_course_enrollments"]
        self.subjects = self.db["studyhub_subjects"]
        self.modules = self.db["studyhub_modules"]

    # ========================================================================
    # Category Operations
    # ========================================================================

    def get_all_categories(self) -> List[Dict[str, Any]]:
        """Get all categories with statistics"""
        categories = list(
            self.categories.find({"is_active": True}).sort("order_index", ASCENDING)
        )

        result = []
        for cat in categories:
            # Get stats
            stats = self._get_category_stats(cat["category_id"])
            cat["stats"] = stats
            result.append(cat)

        return result

    def get_category_detail(self, category_id: str) -> Optional[Dict[str, Any]]:
        """Get category with detailed stats and top subjects"""
        category = self.categories.find_one(
            {"category_id": category_id, "is_active": True}
        )
        if not category:
            return None

        # Stats
        stats = self._get_category_stats(category_id)

        # Top subjects
        top_subjects = list(
            self.category_subjects.find(
                {"category_id": category_id, "approved": True, "is_active": True}
            )
            .sort("total_learners", DESCENDING)
            .limit(10)
        )

        return {"category": category, "stats": stats, "top_subjects": top_subjects}

    def _get_category_stats(self, category_id: str) -> Dict[str, Any]:
        """Calculate category statistics"""
        # Subject count
        subject_count = self.category_subjects.count_documents(
            {"category_id": category_id, "approved": True, "is_active": True}
        )

        # Course count
        course_count = self.courses.count_documents(
            {
                "category_id": category_id,
                "status": CourseStatus.APPROVED,
                "visibility": CourseVisibility.PUBLIC,
            }
        )

        # Total learners & enrollments
        pipeline = [
            {
                "$match": {
                    "category_id": category_id,
                    "status": CourseStatus.APPROVED,
                    "visibility": CourseVisibility.PUBLIC,
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total_enrollments": {"$sum": "$stats.enrollment_count"},
                    "total_completions": {"$sum": "$stats.completion_count"},
                    "avg_rating": {"$avg": "$stats.average_rating"},
                    "total_hours": {"$sum": "$estimated_duration_hours"},
                }
            },
        ]

        result = list(self.courses.aggregate(pipeline))

        if result:
            stats = result[0]
            return {
                "subject_count": subject_count,
                "course_count": course_count,
                "total_learners": stats.get(
                    "total_enrollments", 0
                ),  # Unique learners would need different calc
                "total_enrollments": stats.get("total_enrollments", 0),
                "average_rating": round(stats.get("avg_rating", 0), 2),
                "total_content_hours": stats.get("total_hours", 0),
            }

        return {
            "subject_count": subject_count,
            "course_count": course_count,
            "total_learners": 0,
            "total_enrollments": 0,
            "average_rating": 0.0,
            "total_content_hours": 0,
        }

    def get_category_top_instructors(
        self, category_id: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get top instructors in category"""
        pipeline = [
            {
                "$match": {
                    "category_id": category_id,
                    "status": CourseStatus.APPROVED,
                    "visibility": CourseVisibility.PUBLIC,
                }
            },
            {
                "$group": {
                    "_id": "$user_id",
                    "course_count": {"$sum": 1},
                    "total_learners": {"$sum": "$stats.enrollment_count"},
                    "avg_rating": {"$avg": "$stats.average_rating"},
                }
            },
            {"$sort": {"total_learners": -1}},
            {"$limit": limit},
        ]

        results = list(self.courses.aggregate(pipeline))

        # Get user details from Firebase or user service
        # For now return with user_id
        return [
            {
                "user_id": r["_id"],
                "course_count": r["course_count"],
                "total_learners": r["total_learners"],
                "average_rating": round(r["avg_rating"], 2),
            }
            for r in results
        ]

    # ========================================================================
    # Category Subject Operations
    # ========================================================================

    def create_category_subject(
        self,
        category_id: str,
        subject_name_en: str,
        subject_name_vi: str,
        description_en: Optional[str],
        description_vi: Optional[str],
        created_by: str,  # "admin" or "user"
        creator_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create category subject"""
        # Generate slug
        slug = self._generate_slug(subject_name_en)

        # Check duplicate
        existing = self.category_subjects.find_one(
            {"category_id": category_id, "slug": slug}
        )

        if existing:
            raise ValueError(
                f"Subject with slug '{slug}' already exists in this category"
            )

        # Create subject
        now = datetime.now(timezone.utc)
        subject = {
            "category_id": category_id,
            "subject_name_en": subject_name_en,
            "subject_name_vi": subject_name_vi,
            "description_en": description_en,
            "description_vi": description_vi,
            "slug": slug,
            "created_by": created_by,
            "creator_id": creator_id,
            "approved": created_by == "admin",  # Auto-approve admin subjects
            "is_active": True,
            "course_count": 0,
            "total_learners": 0,
            "created_at": now,
            "updated_at": now,
        }

        result = self.category_subjects.insert_one(subject)
        subject["_id"] = result.inserted_id

        return subject

    def get_category_subjects(
        self,
        category_id: str,
        page: int = 1,
        limit: int = 20,
        sort: str = "popular",
        approved_only: bool = True,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Get subjects in category"""
        query = {"category_id": category_id, "is_active": True}

        if approved_only:
            query["approved"] = True

        # Sort
        if sort == "popular":
            sort_field = ("total_learners", DESCENDING)
        elif sort == "newest":
            sort_field = ("created_at", DESCENDING)
        else:  # name
            sort_field = ("subject_name_en", ASCENDING)

        total = self.category_subjects.count_documents(query)

        subjects = list(
            self.category_subjects.find(query)
            .sort(*sort_field)
            .skip((page - 1) * limit)
            .limit(limit)
        )

        return subjects, total

    def search_category_subjects(
        self, query: str, page: int = 1, limit: int = 20
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Search subjects across all categories"""
        search_filter = {
            "$or": [
                {"subject_name_en": {"$regex": query, "$options": "i"}},
                {"subject_name_vi": {"$regex": query, "$options": "i"}},
                {"description_en": {"$regex": query, "$options": "i"}},
                {"description_vi": {"$regex": query, "$options": "i"}},
            ],
            "approved": True,
            "is_active": True,
        }

        total = self.category_subjects.count_documents(search_filter)

        subjects = list(
            self.category_subjects.find(search_filter)
            .sort("total_learners", DESCENDING)
            .skip((page - 1) * limit)
            .limit(limit)
        )

        return subjects, total

    def _generate_slug(self, text: str) -> str:
        """Generate URL-friendly slug"""
        # Convert to lowercase
        slug = text.lower()
        # Replace spaces and special chars with hyphens
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"[-\s]+", "-", slug)
        # Remove leading/trailing hyphens
        slug = slug.strip("-")
        return slug

    # ========================================================================
    # Course Publishing
    # ========================================================================

    def publish_subject_as_course(
        self, subject_id: str, user_id: str, request_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Publish user's subject as course"""
        # 1. Check source subject exists and user owns it
        source_subject = self.subjects.find_one(
            {"_id": ObjectId(subject_id), "user_id": user_id}
        )

        if not source_subject:
            raise ValueError("Subject not found or you don't have permission")

        # 2. Check if already published
        existing_course = self.courses.find_one({"source_subject_id": subject_id})
        if existing_course:
            raise ValueError("This subject is already published as a course")

        # 3. Get or create category subject
        category_subject_id = request_data.get("category_subject_id")

        if not category_subject_id:
            # Create new category subject (needs approval)
            cat_subject = self.create_category_subject(
                category_id=request_data["category_id"],
                subject_name_en=request_data["new_subject_name_en"],
                subject_name_vi=request_data["new_subject_name_vi"],
                description_en=request_data.get("new_subject_description_en"),
                description_vi=request_data.get("new_subject_description_vi"),
                created_by="user",
                creator_id=user_id,
            )
            category_subject_id = str(cat_subject["_id"])
        else:
            # Validate category subject exists
            cat_subject = self.category_subjects.find_one(
                {"_id": ObjectId(category_subject_id)}
            )
            if not cat_subject:
                raise ValueError("Category subject not found")

        # 4. Get modules count
        modules = list(self.modules.find({"subject_id": ObjectId(subject_id)}))
        module_count = len(modules)
        total_content_count = sum(len(m.get("contents", [])) for m in modules)

        # 5. Create course
        now = datetime.now(timezone.utc)
        course = {
            "category_id": request_data["category_id"],
            "category_subject_id": category_subject_id,
            "source_subject_id": subject_id,
            "user_id": user_id,
            "title": request_data["title"],
            "description": request_data["description"],
            "cover_image_url": request_data.get("cover_image_url"),
            "language": request_data.get("language", "vi"),
            "level": request_data.get("level", CourseLevel.BEGINNER),
            "price_type": request_data.get("price_type", PriceType.FREE),
            "price_points": request_data.get("price_points", 0),
            "original_price_points": request_data.get("price_points", 0),
            "discount_percentage": 0,
            "module_count": module_count,
            "total_content_count": total_content_count,
            "estimated_duration_hours": module_count * 2,  # Rough estimate
            "stats": {
                "enrollment_count": 0,
                "completion_count": 0,
                "completion_rate": 0.0,
                "average_rating": 0.0,
                "rating_count": 0,
                "view_count": 0,
            },
            "status": CourseStatus.PENDING,
            "visibility": CourseVisibility.PRIVATE,
            "published_at": now,
            "approved_at": None,
            "approved_by": None,
            "rejection_reason": None,
            "tags": request_data.get("tags", []),
            "what_you_will_learn": request_data.get("what_you_will_learn", []),
            "requirements": request_data.get("requirements", []),
            "target_audience": request_data.get("target_audience", []),
            "last_synced_at": now,
            "sync_status": "up-to-date",
            "sync_available": False,
            "created_at": now,
            "updated_at": now,
        }

        result = self.courses.insert_one(course)
        course["_id"] = result.inserted_id

        return course

    # ========================================================================
    # Course Management
    # ========================================================================

    def get_course_detail(
        self, course_id: str, user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get course details with full context"""
        course = self.courses.find_one({"_id": ObjectId(course_id)})
        if not course:
            return None

        # Get category
        category = self.categories.find_one({"category_id": course["category_id"]})

        # Get category subject
        cat_subject = self.category_subjects.find_one(
            {"_id": ObjectId(course["category_subject_id"])}
        )

        # Get modules from source subject
        modules = list(
            self.modules.find(
                {"subject_id": ObjectId(course["source_subject_id"])}
            ).sort("order_index", ASCENDING)
        )

        module_summaries = [
            {
                "module_id": str(m["_id"]),
                "title": m["title"],
                "content_count": len(m.get("contents", [])),
                "order_index": m.get("order_index", 0),
            }
            for m in modules
        ]

        # Get instructor info (simplified, would need user service)
        instructor = {
            "user_id": course["user_id"],
            "display_name": "Instructor",  # Fetch from user service
            "profile_image": None,
        }

        # Check enrollment
        is_enrolled = False
        enrollment_id = None

        if user_id:
            enrollment = self.enrollments.find_one(
                {"course_id": str(course["_id"]), "user_id": user_id}
            )

            if enrollment:
                is_enrolled = True
                enrollment_id = str(enrollment["_id"])

        # Can enroll check
        can_enroll = not is_enrolled and course["status"] == CourseStatus.APPROVED

        return {
            "course": course,
            "category": category,
            "category_subject": cat_subject,
            "instructor": instructor,
            "modules": module_summaries,
            "is_enrolled": is_enrolled,
            "can_enroll": can_enroll,
            "enrollment_id": enrollment_id,
        }

    def get_courses(
        self,
        filters: Dict[str, Any],
        sort: str = "popular",
        page: int = 1,
        limit: int = 20,
        user_id: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Get courses with filters"""
        query = {"status": CourseStatus.APPROVED, "visibility": CourseVisibility.PUBLIC}

        # Apply filters
        if filters.get("category_id"):
            query["category_id"] = filters["category_id"]

        if filters.get("category_subject_id"):
            query["category_subject_id"] = filters["category_subject_id"]

        if filters.get("level"):
            query["level"] = filters["level"]

        if filters.get("price_type"):
            query["price_type"] = filters["price_type"]

        if filters.get("language"):
            query["language"] = filters["language"]

        if filters.get("min_rating"):
            query["stats.average_rating"] = {"$gte": filters["min_rating"]}

        if filters.get("free_only"):
            query["price_type"] = PriceType.FREE

        # Sort
        sort_field = self._get_sort_field(sort)

        total = self.courses.count_documents(query)

        courses = list(
            self.courses.find(query)
            .sort(*sort_field)
            .skip((page - 1) * limit)
            .limit(limit)
        )

        return courses, total

    def get_user_courses(
        self, user_id: str, status: Optional[str] = None, page: int = 1, limit: int = 20
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Get user's published courses"""
        query = {"user_id": user_id}

        if status:
            query["status"] = status

        total = self.courses.count_documents(query)

        courses = list(
            self.courses.find(query)
            .sort("created_at", DESCENDING)
            .skip((page - 1) * limit)
            .limit(limit)
        )

        return courses, total

    def update_course(
        self, course_id: str, user_id: str, updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update course (owner only, goes back to pending if approved)"""
        course = self.courses.find_one({"_id": ObjectId(course_id), "user_id": user_id})
        if not course:
            raise ValueError("Course not found or you don't have permission")

        # If course was approved, set back to pending
        if course["status"] == CourseStatus.APPROVED:
            updates["status"] = CourseStatus.PENDING
            updates["approved_at"] = None
            updates["approved_by"] = None

        updates["updated_at"] = datetime.now(timezone.utc)

        self.courses.update_one({"_id": ObjectId(course_id)}, {"$set": updates})

        updated_course = self.courses.find_one({"_id": ObjectId(course_id)})
        if not updated_course:
            raise ValueError("Course not found after update")

        return updated_course

    def archive_course(self, course_id: str, user_id: str) -> bool:
        """Archive course (owner only)"""
        result = self.courses.update_one(
            {"_id": ObjectId(course_id), "user_id": user_id},
            {
                "$set": {
                    "status": CourseStatus.ARCHIVED,
                    "visibility": CourseVisibility.PRIVATE,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )

        return result.modified_count > 0

    def _get_sort_field(self, sort: str) -> Tuple[str, int]:
        """Get MongoDB sort field"""
        if sort == "popular":
            return ("stats.enrollment_count", DESCENDING)
        elif sort == "newest":
            return ("published_at", DESCENDING)
        elif sort == "highest-rated":
            return ("stats.average_rating", DESCENDING)
        elif sort == "trending":
            return ("stats.view_count", DESCENDING)  # Would need better trending calc
        else:
            return ("created_at", DESCENDING)

    # ========================================================================
    # Search & Community
    # ========================================================================

    def search_courses(
        self,
        query: str,
        filters: Dict[str, Any],
        sort: str = "popular",
        page: int = 1,
        limit: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Search courses"""
        search_filter = {
            "$or": [
                {"title": {"$regex": query, "$options": "i"}},
                {"description": {"$regex": query, "$options": "i"}},
                {"tags": {"$in": [query]}},  # Exact tag match
            ],
            "status": CourseStatus.APPROVED,
            "visibility": CourseVisibility.PUBLIC,
        }

        # Apply additional filters
        if filters.get("category_id"):
            search_filter["category_id"] = filters["category_id"]

        if filters.get("level"):
            search_filter["level"] = filters["level"]

        if filters.get("price_type"):
            search_filter["price_type"] = filters["price_type"]

        if filters.get("language"):
            search_filter["language"] = filters["language"]

        if filters.get("min_rating"):
            search_filter["stats.average_rating"] = {"$gte": filters["min_rating"]}

        sort_field = self._get_sort_field(sort)

        total = self.courses.count_documents(search_filter)

        courses = list(
            self.courses.find(search_filter)
            .sort(*sort_field)
            .skip((page - 1) * limit)
            .limit(limit)
        )

        return courses, total

    def get_top_courses(self, limit: int = 8) -> List[Dict[str, Any]]:
        """Get top courses across all categories"""
        return list(
            self.courses.find(
                {"status": CourseStatus.APPROVED, "visibility": CourseVisibility.PUBLIC}
            )
            .sort("stats.enrollment_count", DESCENDING)
            .limit(limit)
        )

    def get_trending_courses(self, limit: int = 8) -> List[Dict[str, Any]]:
        """Get trending courses (simplified version)"""
        # Would need better trending algorithm with time-based metrics
        # For now: recent + high activity
        return list(
            self.courses.find(
                {
                    "status": CourseStatus.APPROVED,
                    "visibility": CourseVisibility.PUBLIC,
                    "published_at": {
                        "$gte": datetime.now(timezone.utc) - timedelta(days=30)
                    },
                }
            )
            .sort(
                [
                    ("stats.enrollment_count", DESCENDING),
                    ("stats.view_count", DESCENDING),
                ]
            )
            .limit(limit)
        )

    # ========================================================================
    # Enrollment & Progress
    # ========================================================================

    def enroll_in_course(self, course_id: str, user_id: str) -> Dict[str, Any]:
        """Enroll user in course"""
        # Check course exists and is available
        course = self.courses.find_one(
            {
                "_id": ObjectId(course_id),
                "status": CourseStatus.APPROVED,
                "visibility": CourseVisibility.PUBLIC,
            }
        )

        if not course:
            raise ValueError("Course not found or not available")

        # Check already enrolled
        existing = self.enrollments.find_one(
            {"course_id": course_id, "user_id": user_id}
        )

        if existing:
            return existing

        # Create enrollment
        now = datetime.now(timezone.utc)
        enrollment = {
            "course_id": course_id,
            "user_id": user_id,
            "completed_modules": [],
            "current_module_id": None,
            "progress_percentage": 0.0,
            "completed": False,
            "completed_at": None,
            "certificate_issued": False,
            "certificate_id": None,
            "enrolled_at": now,
            "last_accessed_at": now,
            "total_time_spent_minutes": 0,
            "rating": None,
            "review": None,
            "rated_at": None,
        }

        result = self.enrollments.insert_one(enrollment)
        enrollment["_id"] = result.inserted_id

        # Update course enrollment count
        self.courses.update_one(
            {"_id": ObjectId(course_id)}, {"$inc": {"stats.enrollment_count": 1}}
        )

        return enrollment

    def get_user_enrollments(
        self, user_id: str, page: int = 1, limit: int = 20
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Get user's enrolled courses with progress"""
        total = self.enrollments.count_documents({"user_id": user_id})

        enrollments = list(
            self.enrollments.find({"user_id": user_id})
            .sort("last_accessed_at", DESCENDING)
            .skip((page - 1) * limit)
            .limit(limit)
        )

        # Enrich with course data
        result = []
        for enrollment in enrollments:
            course = self.courses.find_one({"_id": ObjectId(enrollment["course_id"])})
            if course:
                course["progress"] = {
                    "completed_modules": len(enrollment["completed_modules"]),
                    "total_modules": course["module_count"],
                    "progress_percentage": enrollment["progress_percentage"],
                    "current_module_id": enrollment.get("current_module_id"),
                    "last_accessed_at": enrollment["last_accessed_at"],
                }
                course["enrollment"] = enrollment
                result.append(course)

        return result, total

    def update_progress(
        self, enrollment_id: str, user_id: str, module_id: str, completed: bool = True
    ) -> Dict[str, Any]:
        """Update course progress"""
        enrollment = self.enrollments.find_one(
            {"_id": ObjectId(enrollment_id), "user_id": user_id}
        )

        if not enrollment:
            raise ValueError("Enrollment not found")

        # Update completed modules
        completed_modules = enrollment.get("completed_modules", [])

        if completed and module_id not in completed_modules:
            completed_modules.append(module_id)
        elif not completed and module_id in completed_modules:
            completed_modules.remove(module_id)

        # Get course to calculate percentage
        course = self.courses.find_one({"_id": ObjectId(enrollment["course_id"])})
        if not course:
            raise ValueError("Course not found")

        total_modules = course["module_count"]
        progress_percentage = (
            (len(completed_modules) / total_modules * 100) if total_modules > 0 else 0
        )

        # Check completion
        is_completed = progress_percentage >= 100

        updates = {
            "completed_modules": completed_modules,
            "current_module_id": module_id,
            "progress_percentage": progress_percentage,
            "last_accessed_at": datetime.now(timezone.utc),
            "completed": is_completed,
        }

        if is_completed and not enrollment.get("completed"):
            updates["completed_at"] = datetime.now(timezone.utc)
            # Update course completion count
            self.courses.update_one(
                {"_id": ObjectId(enrollment["course_id"])},
                {"$inc": {"stats.completion_count": 1}},
            )

        self.enrollments.update_one({"_id": ObjectId(enrollment_id)}, {"$set": updates})

        updated_enrollment = self.enrollments.find_one({"_id": ObjectId(enrollment_id)})
        if not updated_enrollment:
            raise ValueError("Enrollment not found after update")

        return updated_enrollment

    def rate_course(
        self,
        enrollment_id: str,
        user_id: str,
        rating: int,
        review: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Rate a course"""
        enrollment = self.enrollments.find_one(
            {"_id": ObjectId(enrollment_id), "user_id": user_id}
        )

        if not enrollment:
            raise ValueError("Enrollment not found")

        # Update enrollment rating
        old_rating = enrollment.get("rating")

        self.enrollments.update_one(
            {"_id": ObjectId(enrollment_id)},
            {
                "$set": {
                    "rating": rating,
                    "review": review,
                    "rated_at": datetime.now(timezone.utc),
                }
            },
        )

        # Update course average rating
        course_id = enrollment["course_id"]
        course = self.courses.find_one({"_id": ObjectId(course_id)})

        # Recalculate average
        all_ratings = list(
            self.enrollments.find({"course_id": course_id, "rating": {"$ne": None}})
        )

        if all_ratings:
            avg_rating = sum(e["rating"] for e in all_ratings) / len(all_ratings)
            rating_count = len(all_ratings)

            self.courses.update_one(
                {"_id": ObjectId(course_id)},
                {
                    "$set": {
                        "stats.average_rating": round(avg_rating, 2),
                        "stats.rating_count": rating_count,
                    }
                },
            )

        updated_enrollment = self.enrollments.find_one({"_id": ObjectId(enrollment_id)})
        if not updated_enrollment:
            raise ValueError("Enrollment not found after rating")

        return updated_enrollment
