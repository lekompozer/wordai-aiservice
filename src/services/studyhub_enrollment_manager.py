"""
StudyHub Enrollment & Progress Manager
Handles enrollment and learning progress operations
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from bson import ObjectId
from fastapi import HTTPException

from src.database.db_manager import DBManager
from src.models.studyhub_models import (
    EnrollmentStatus,
    LearningStatus,
    EnrollmentResponse,
    MyEnrollmentsResponse,
    SubjectProgressResponse,
    ProgressDetailItem,
    SubjectLearnersResponse,
    SubjectLearnerItem,
    DashboardOverviewResponse,
    ActivityItem,
    RecentActivityResponse,
)


class StudyHubEnrollmentManager:
    """Manager for enrollment and progress operations"""

    def __init__(self):
        self.db_manager = DBManager()
        self.db = self.db_manager.db

    # ==================== ENROLLMENT OPERATIONS ====================

    async def enroll_subject(self, user_id: str, subject_id: str) -> EnrollmentResponse:
        """Enroll user in subject"""
        # Check if subject exists and is published
        subject = self.db.studyhub_subjects.find_one(
            {"_id": ObjectId(subject_id), "deleted_at": None}
        )
        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found")

        if subject["status"] != "published":
            raise HTTPException(
                status_code=400, detail="Cannot enroll in unpublished subject"
            )

        # Check if already enrolled
        existing = self.db.studyhub_enrollments.find_one(
            {
                "user_id": user_id,
                "subject_id": ObjectId(subject_id),
                "status": {"$ne": "dropped"},
            }
        )
        if existing:
            raise HTTPException(status_code=400, detail="Already enrolled in subject")

        # Create enrollment
        now = datetime.now(timezone.utc)
        enrollment_doc = {
            "user_id": user_id,
            "subject_id": ObjectId(subject_id),
            "status": EnrollmentStatus.ACTIVE.value,
            "enrolled_at": now,
            "last_accessed_at": now,
            "completed_at": None,
            "created_at": now,
            "updated_at": now,
        }
        result = self.db.studyhub_enrollments.insert_one(enrollment_doc)

        # Update subject metadata
        self.db.studyhub_subjects.update_one(
            {"_id": ObjectId(subject_id)},
            {
                "$inc": {"metadata.total_learners": 1},
                "$set": {"updated_at": now},
            },
        )

        # Calculate progress
        progress = await self._calculate_progress(user_id, subject_id)

        return EnrollmentResponse(
            _id=str(result.inserted_id),
            user_id=user_id,
            subject_id=subject_id,
            subject_title=subject["title"],
            status=EnrollmentStatus.ACTIVE,
            enrolled_at=now,
            last_accessed_at=now,
            completed_at=None,
            progress_percentage=progress,
        )

    async def unenroll_subject(self, user_id: str, subject_id: str) -> Dict[str, str]:
        """Unenroll from subject (mark as dropped)"""
        enrollment = self.db.studyhub_enrollments.find_one(
            {
                "user_id": user_id,
                "subject_id": ObjectId(subject_id),
                "status": {"$ne": "dropped"},
            }
        )
        if not enrollment:
            raise HTTPException(status_code=404, detail="Enrollment not found")

        # Update to dropped
        now = datetime.now(timezone.utc)
        self.db.studyhub_enrollments.update_one(
            {"_id": enrollment["_id"]},
            {"$set": {"status": "dropped", "updated_at": now}},
        )

        # Update subject metadata
        self.db.studyhub_subjects.update_one(
            {"_id": ObjectId(subject_id)},
            {
                "$inc": {"metadata.total_learners": -1},
                "$set": {"updated_at": now},
            },
        )

        return {"message": "Successfully unenrolled from subject"}

    async def get_my_enrollments(
        self, user_id: str, status: Optional[str] = None
    ) -> MyEnrollmentsResponse:
        """Get user's enrollments"""
        query = {"user_id": user_id}
        if status:
            query["status"] = status

        enrollments = list(
            self.db.studyhub_enrollments.find(query).sort("enrolled_at", -1)
        )

        enrollment_list = []
        for enrollment in enrollments:
            # Get subject
            subject = self.db.studyhub_subjects.find_one(
                {"_id": enrollment["subject_id"], "deleted_at": None}
            )
            if not subject:
                continue

            # Calculate progress
            progress = await self._calculate_progress(
                user_id, str(enrollment["subject_id"])
            )

            enrollment_list.append(
                EnrollmentResponse(
                    _id=str(enrollment["_id"]),
                    user_id=user_id,
                    subject_id=str(enrollment["subject_id"]),
                    subject_title=subject["title"],
                    status=enrollment["status"],
                    enrolled_at=enrollment["enrolled_at"],
                    last_accessed_at=enrollment.get("last_accessed_at"),
                    completed_at=enrollment.get("completed_at"),
                    progress_percentage=progress,
                )
            )

        return MyEnrollmentsResponse(
            enrollments=enrollment_list, total=len(enrollment_list)
        )

    # ==================== PROGRESS OPERATIONS ====================

    async def get_subject_progress(
        self, user_id: str, subject_id: str
    ) -> SubjectProgressResponse:
        """Get learning progress for subject"""
        # Get subject first
        subject = self.db.studyhub_subjects.find_one(
            {"_id": ObjectId(subject_id), "deleted_at": None}
        )
        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found")

        # Check if user is owner (owners can view without enrollment)
        is_owner = subject["owner_id"] == user_id

        # Check enrollment (not required for owners)
        enrollment = self.db.studyhub_enrollments.find_one(
            {
                "user_id": user_id,
                "subject_id": ObjectId(subject_id),
                "status": {"$ne": "dropped"},
            }
        )
        if not enrollment and not is_owner:
            raise HTTPException(status_code=404, detail="Not enrolled in this subject")

        # Get owner info
        owner = self.db.users.find_one({"firebase_uid": subject["owner_id"]})
        owner_name = owner.get("display_name", "Unknown") if owner else "Unknown"

        # Get metadata for rating and learners
        metadata = subject.get("metadata", {})
        avg_rating = metadata.get("avg_rating", 0.0)
        total_learners = metadata.get("total_students", 0)

        # Get modules
        modules = list(
            self.db.studyhub_modules.find(
                {"subject_id": ObjectId(subject_id), "deleted_at": None}
            ).sort("order_index", 1)
        )

        # Get progress records
        progress_records = list(
            self.db.studyhub_learning_progress.find(
                {
                    "user_id": user_id,
                    "subject_id": ObjectId(subject_id),
                }
            )
        )

        # Build progress map
        progress_map = {}
        for record in progress_records:
            key = f"{record.get('module_id')}_{record.get('content_id', '')}"
            progress_map[key] = record

        # Calculate totals
        total_modules = len(modules)
        total_contents = 0
        completed_modules = 0
        completed_contents = 0
        total_tests = 0
        total_files = 0
        modules_progress = []

        for module in modules:
            module_id = str(module["_id"])

            # Get contents
            contents = list(
                self.db.studyhub_module_contents.find(
                    {"module_id": ObjectId(module_id), "deleted_at": None}
                ).sort("order_index", 1)
            )

            total_contents += len(contents)
            module_completed = True

            # Count tests and files in this module
            module_tests = sum(1 for c in contents if c.get("content_type") == "test")
            module_files = sum(1 for c in contents if c.get("content_type") == "file")
            total_tests += module_tests
            total_files += module_files

            # Check module completion
            for content in contents:
                content_id = str(content["_id"])
                key = f"{module_id}_{content_id}"
                if key in progress_map and progress_map[key]["status"] == "completed":
                    completed_contents += 1
                else:
                    module_completed = False

            if module_completed and len(contents) > 0:
                completed_modules += 1

            # Module status
            module_key = f"{module_id}_"
            module_status = (
                LearningStatus.COMPLETED
                if module_completed and len(contents) > 0
                else (
                    LearningStatus.IN_PROGRESS
                    if any(
                        f"{module_id}_{str(c['_id'])}" in progress_map for c in contents
                    )
                    else LearningStatus.NOT_STARTED
                )
            )

            modules_progress.append(
                ProgressDetailItem(
                    id=module_id,
                    title=module["title"],
                    type="module",
                    status=module_status,
                    completed_at=(
                        progress_map[module_key]["completed_at"]
                        if module_key in progress_map
                        else None
                    ),
                    total_tests=module_tests,
                    total_files=module_files,
                )
            )

        # Overall progress
        overall_progress = (
            completed_contents / total_contents if total_contents > 0 else 0.0
        )

        # Get enrollment fields (defaults for owners without enrollment)
        if enrollment:
            last_position = enrollment.get("last_position")
            enrollment_status = enrollment["status"]
            enrolled_at = enrollment["enrolled_at"]
            last_accessed_at = enrollment.get("last_accessed_at")
        else:
            # Owner viewing their own subject (no enrollment)
            last_position = None
            enrollment_status = EnrollmentStatus.ACTIVE  # Default for owners
            enrolled_at = subject["created_at"]  # Use subject creation date
            last_accessed_at = None

        return SubjectProgressResponse(
            subject_id=subject_id,
            subject_title=subject["title"],
            subject_description=subject.get("description"),
            owner_name=owner_name,
            category=subject.get("category"),
            cover_image_url=subject.get("cover_image_url"),
            avg_rating=avg_rating,
            total_learners=total_learners,
            enrollment_status=enrollment_status,
            overall_progress=overall_progress,
            total_modules=total_modules,
            completed_modules=completed_modules,
            total_contents=total_contents,
            completed_contents=completed_contents,
            total_tests=total_tests,
            total_files=total_files,
            last_position=last_position,
            modules_progress=modules_progress,
            enrolled_at=enrolled_at,
            last_accessed_at=last_accessed_at,
        )

    async def mark_complete(
        self,
        user_id: str,
        subject_id: str,
        module_id: Optional[str] = None,
        content_id: Optional[str] = None,
    ) -> Dict[str, str]:
        """Mark content or module as complete"""
        # Check enrollment
        enrollment = self.db.studyhub_enrollments.find_one(
            {
                "user_id": user_id,
                "subject_id": ObjectId(subject_id),
                "status": {"$ne": "dropped"},
            }
        )
        if not enrollment:
            raise HTTPException(status_code=404, detail="Not enrolled in this subject")

        now = datetime.now(timezone.utc)

        if content_id:
            # Mark content as complete
            progress_doc = {
                "user_id": user_id,
                "subject_id": ObjectId(subject_id),
                "module_id": ObjectId(module_id),
                "content_id": ObjectId(content_id),
                "status": "completed",
                "completed_at": now,
                "created_at": now,
                "updated_at": now,
            }
            self.db.studyhub_learning_progress.update_one(
                {
                    "user_id": user_id,
                    "subject_id": ObjectId(subject_id),
                    "module_id": ObjectId(module_id),
                    "content_id": ObjectId(content_id),
                },
                {"$set": progress_doc},
                upsert=True,
            )
        elif module_id:
            # Mark all contents in module as complete
            contents = list(
                self.db.studyhub_module_contents.find(
                    {"module_id": ObjectId(module_id), "deleted_at": None}
                )
            )
            for content in contents:
                progress_doc = {
                    "user_id": user_id,
                    "subject_id": ObjectId(subject_id),
                    "module_id": ObjectId(module_id),
                    "content_id": content["_id"],
                    "status": "completed",
                    "completed_at": now,
                    "created_at": now,
                    "updated_at": now,
                }
                self.db.studyhub_learning_progress.update_one(
                    {
                        "user_id": user_id,
                        "subject_id": ObjectId(subject_id),
                        "module_id": ObjectId(module_id),
                        "content_id": content["_id"],
                    },
                    {"$set": progress_doc},
                    upsert=True,
                )

        # Update last accessed
        self.db.studyhub_enrollments.update_one(
            {"_id": enrollment["_id"]}, {"$set": {"last_accessed_at": now}}
        )

        # Check if subject completed
        progress = await self._calculate_progress(user_id, subject_id)
        if progress >= 1.0:
            self.db.studyhub_enrollments.update_one(
                {"_id": enrollment["_id"]},
                {"$set": {"status": "completed", "completed_at": now}},
            )

        return {"message": "Marked as complete"}

    async def mark_incomplete(
        self,
        user_id: str,
        subject_id: str,
        module_id: Optional[str] = None,
        content_id: Optional[str] = None,
    ) -> Dict[str, str]:
        """Mark content or module as incomplete"""
        # Check enrollment
        enrollment = self.db.studyhub_enrollments.find_one(
            {
                "user_id": user_id,
                "subject_id": ObjectId(subject_id),
                "status": {"$ne": "dropped"},
            }
        )
        if not enrollment:
            raise HTTPException(status_code=404, detail="Not enrolled in this subject")

        if content_id:
            # Delete progress record
            self.db.studyhub_learning_progress.delete_one(
                {
                    "user_id": user_id,
                    "subject_id": ObjectId(subject_id),
                    "module_id": ObjectId(module_id),
                    "content_id": ObjectId(content_id),
                }
            )
        elif module_id:
            # Delete all content progress in module
            self.db.studyhub_learning_progress.delete_many(
                {
                    "user_id": user_id,
                    "subject_id": ObjectId(subject_id),
                    "module_id": ObjectId(module_id),
                }
            )

        # Update enrollment status back to active if was completed
        if enrollment["status"] == "completed":
            self.db.studyhub_enrollments.update_one(
                {"_id": enrollment["_id"]}, {"$set": {"status": "active"}}
            )

        return {"message": "Marked as incomplete"}

    async def save_last_position(
        self, user_id: str, subject_id: str, module_id: str, content_id: str
    ) -> Dict[str, str]:
        """Save last learning position"""
        # Check enrollment
        enrollment = self.db.studyhub_enrollments.find_one(
            {
                "user_id": user_id,
                "subject_id": ObjectId(subject_id),
                "status": {"$ne": "dropped"},
            }
        )
        if not enrollment:
            raise HTTPException(status_code=404, detail="Not enrolled in this subject")

        # Update last position
        now = datetime.now(timezone.utc)
        self.db.studyhub_enrollments.update_one(
            {"_id": enrollment["_id"]},
            {
                "$set": {
                    "last_position": {"module_id": module_id, "content_id": content_id},
                    "last_accessed_at": now,
                }
            },
        )

        return {"message": "Position saved"}

    # ==================== AUTO-TRACKING ====================

    async def track_learning_progress(
        self,
        user_id: str,
        subject_id: str,
        module_id: str,
        content_id: str,
        content_type: str,
        tracking_data: dict,
    ) -> dict:
        """Auto-track learning progress for video/slides"""
        now = datetime.now(timezone.utc)

        # Get or create progress record
        progress = self.db.studyhub_learning_progress.find_one(
            {
                "user_id": user_id,
                "content_id": ObjectId(content_id),
            }
        )

        if not progress:
            progress = {
                "user_id": user_id,
                "subject_id": ObjectId(subject_id),
                "module_id": ObjectId(module_id),
                "content_id": ObjectId(content_id),
                "content_type": content_type,
                "status": "in_progress",
                "created_at": now,
            }

        # Update tracking data based on content type
        auto_completed = False

        if content_type == "video":
            progress["watched_percentage"] = tracking_data.get("watched_percentage", 0)
            progress["last_position"] = tracking_data.get("current_time", 0)
            progress["duration"] = tracking_data.get("duration", 0)

            # Auto-complete if >= 90%
            if (
                progress["watched_percentage"] >= 90
                and progress.get("status") != "completed"
            ):
                progress["status"] = "completed"
                progress["completed_at"] = now
                auto_completed = True

        elif content_type == "slides":
            progress["slide_index"] = tracking_data.get("current_slide", 0)
            progress["total_slides"] = tracking_data.get("total_slides", 0)

            # Auto-complete if reached last slide
            if (
                progress.get("total_slides", 0) > 0
                and progress["slide_index"] >= progress["total_slides"] - 1
                and progress.get("status") != "completed"
            ):
                progress["status"] = "completed"
                progress["completed_at"] = now
                auto_completed = True

        progress["updated_at"] = now

        # Upsert progress
        self.db.studyhub_learning_progress.update_one(
            {
                "user_id": user_id,
                "content_id": ObjectId(content_id),
            },
            {"$set": progress},
            upsert=True,
        )

        # Update enrollment last_accessed_at
        self.db.studyhub_enrollments.update_one(
            {
                "user_id": user_id,
                "subject_id": ObjectId(subject_id),
            },
            {
                "$set": {
                    "last_accessed_at": now,
                    "last_position": {
                        "module_id": module_id,
                        "content_id": content_id,
                    },
                }
            },
        )

        # Calculate module and subject progress
        module_progress = await self._calculate_module_progress(user_id, module_id)
        subject_progress = await self._calculate_progress(user_id, subject_id)

        return {
            "status": "tracked",
            "auto_completed": auto_completed,
            "progress": {
                "content_id": str(progress["content_id"]),
                "watched_percentage": progress.get("watched_percentage"),
                "last_position": progress.get("last_position"),
                "slide_index": progress.get("slide_index"),
                "total_slides": progress.get("total_slides"),
                "status": progress["status"],
                "completed_at": progress.get("completed_at"),
            },
            "module_progress": module_progress,
            "subject_progress": subject_progress,
        }

    # ==================== PRESENTATION MANAGEMENT ====================

    async def set_module_presentation(
        self, module_id: str, content_id: str, user_id: str
    ) -> dict:
        """Set primary presentation content for module (owner only)"""
        # Get module and check ownership
        module = self.db.studyhub_modules.find_one(
            {"_id": ObjectId(module_id), "deleted_at": None}
        )
        if not module:
            raise HTTPException(status_code=404, detail="Module not found")

        subject = self.db.studyhub_subjects.find_one(
            {"_id": module["subject_id"], "deleted_at": None}
        )
        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found")

        if subject["owner_id"] != user_id:
            raise HTTPException(
                status_code=403, detail="Only subject owner can set presentation"
            )

        # Verify content belongs to this module
        content = self.db.studyhub_module_contents.find_one(
            {
                "_id": ObjectId(content_id),
                "module_id": ObjectId(module_id),
                "deleted_at": None,
            }
        )
        if not content:
            raise HTTPException(
                status_code=404, detail="Content not found in this module"
            )

        # Un-set previous presentation
        self.db.studyhub_module_contents.update_many(
            {"module_id": ObjectId(module_id)}, {"$set": {"is_presentation": False}}
        )

        # Set new presentation
        self.db.studyhub_module_contents.update_one(
            {"_id": ObjectId(content_id)},
            {"$set": {"is_presentation": True, "presentation_priority": 1}},
        )

        return {
            "message": "Presentation content updated",
            "module_id": module_id,
            "presentation": {
                "content_id": str(content["_id"]),
                "content_type": content["content_type"],
                "title": content["title"],
                "url": content.get("url"),
                "is_presentation": True,
                "priority": 1,
            },
        }

    async def get_module_presentation(self, module_id: str, user_id: str) -> dict:
        """Get primary presentation content for module"""
        # Get module
        module = self.db.studyhub_modules.find_one(
            {"_id": ObjectId(module_id), "deleted_at": None}
        )
        if not module:
            raise HTTPException(status_code=404, detail="Module not found")

        # Get primary presentation
        presentation = self.db.studyhub_module_contents.find_one(
            {
                "module_id": ObjectId(module_id),
                "is_presentation": True,
                "deleted_at": None,
            }
        )

        # If no presentation set, auto-select
        if not presentation:
            presentation = await self._auto_select_presentation(module_id)

        # Get user progress on presentation
        user_progress = None
        if presentation:
            progress = self.db.studyhub_learning_progress.find_one(
                {
                    "user_id": user_id,
                    "content_id": presentation["_id"],
                }
            )
            if progress:
                user_progress = {
                    "watched_percentage": progress.get("watched_percentage"),
                    "last_position": progress.get("last_position"),
                    "slide_index": progress.get("slide_index"),
                    "total_slides": progress.get("total_slides"),
                    "status": progress.get("status"),
                    "completed_at": progress.get("completed_at"),
                }

        # Get alternative presentations
        alternatives = list(
            self.db.studyhub_module_contents.find(
                {
                    "module_id": ObjectId(module_id),
                    "content_type": {"$in": ["video", "slides", "document"]},
                    "is_presentation": {"$ne": True},
                    "deleted_at": None,
                }
            ).sort("presentation_priority", 1)
        )

        return {
            "module_id": module_id,
            "module_title": module["title"],
            "presentation": (
                {
                    "content_id": str(presentation["_id"]),
                    "content_type": presentation["content_type"],
                    "title": presentation["title"],
                    "url": presentation.get("url"),
                    "duration": presentation.get("metadata", {}).get("duration"),
                    "total_slides": presentation.get("metadata", {}).get(
                        "total_slides"
                    ),
                    "is_presentation": True,
                    "priority": 1,
                }
                if presentation
                else None
            ),
            "user_progress": user_progress,
            "alternative_presentations": [
                {
                    "content_id": str(alt["_id"]),
                    "content_type": alt["content_type"],
                    "title": alt["title"],
                    "url": alt.get("url"),
                    "priority": alt.get("presentation_priority", 99),
                }
                for alt in alternatives
            ],
        }

    async def _auto_select_presentation(self, module_id: str) -> dict | None:
        """Auto-select primary presentation (video > slides > document)"""
        priority_types = ["video", "slides", "document"]

        for content_type in priority_types:
            content = self.db.studyhub_module_contents.find_one(
                {
                    "module_id": ObjectId(module_id),
                    "content_type": content_type,
                    "deleted_at": None,
                }
            )
            if content:
                # Set as presentation
                self.db.studyhub_module_contents.update_one(
                    {"_id": content["_id"]},
                    {"$set": {"is_presentation": True, "presentation_priority": 1}},
                )
                return content

        return None

    # ==================== PROGRESS WEIGHT CONFIGURATION ====================

    async def configure_progress_weight(
        self, subject_id: str, module_weight: float, test_weight: float, user_id: str
    ) -> dict:
        """Configure subject progress weight (owner only)"""
        # Validate weights sum to 1.0
        if abs(module_weight + test_weight - 1.0) > 0.001:
            raise HTTPException(status_code=400, detail="Weights must sum to 1.0")

        # Check ownership
        subject = self.db.studyhub_subjects.find_one(
            {"_id": ObjectId(subject_id), "deleted_at": None}
        )
        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found")

        if subject["owner_id"] != user_id:
            raise HTTPException(
                status_code=403, detail="Only subject owner can configure weights"
            )

        # Update subject metadata
        now = datetime.now(timezone.utc)
        self.db.studyhub_subjects.update_one(
            {"_id": ObjectId(subject_id)},
            {
                "$set": {
                    "metadata.progress_weight": {
                        "module_weight": module_weight,
                        "test_weight": test_weight,
                        "updated_at": now,
                    },
                    "updated_at": now,
                }
            },
        )

        return {
            "subject_id": subject_id,
            "subject_title": subject["title"],
            "module_weight": module_weight,
            "test_weight": test_weight,
            "updated_at": now,
        }

    async def get_progress_weight(self, subject_id: str, user_id: str) -> dict:
        """Get subject progress weight configuration"""
        subject = self.db.studyhub_subjects.find_one(
            {"_id": ObjectId(subject_id), "deleted_at": None}
        )
        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found")

        # Get weight config or use defaults
        weight_config = subject.get("metadata", {}).get("progress_weight", {})
        module_weight = weight_config.get("module_weight", 0.7)
        test_weight = weight_config.get("test_weight", 0.3)
        updated_at = weight_config.get("updated_at", subject["created_at"])

        return {
            "subject_id": subject_id,
            "subject_title": subject["title"],
            "module_weight": module_weight,
            "test_weight": test_weight,
            "updated_at": updated_at,
        }

    async def _calculate_module_progress(self, user_id: str, module_id: str) -> float:
        """Calculate module completion percentage"""
        # Get all contents in module
        contents = list(
            self.db.studyhub_module_contents.find(
                {"module_id": ObjectId(module_id), "deleted_at": None}
            )
        )

        if not contents:
            return 0.0

        # Count completed contents
        completed = 0
        for content in contents:
            progress = self.db.studyhub_learning_progress.find_one(
                {
                    "user_id": user_id,
                    "content_id": content["_id"],
                    "status": "completed",
                }
            )
            if progress:
                completed += 1

        return completed / len(contents) if contents else 0.0

    # ==================== LEARNER MANAGEMENT ====================

    async def get_subject_learners(
        self, owner_id: str, subject_id: str
    ) -> SubjectLearnersResponse:
        """Get subject learners (owner only)"""
        # Check ownership
        subject = self.db.studyhub_subjects.find_one(
            {"_id": ObjectId(subject_id), "deleted_at": None}
        )
        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found")

        if str(subject["owner_id"]) != owner_id:
            raise HTTPException(
                status_code=403, detail="Only subject owner can view learners"
            )

        # Get enrollments
        enrollments = list(
            self.db.studyhub_enrollments.find(
                {"subject_id": ObjectId(subject_id), "status": {"$ne": "dropped"}}
            ).sort("enrolled_at", -1)
        )

        learners = []
        for enrollment in enrollments:
            user_id = str(enrollment["user_id"])

            # Get user info
            user = self.db.users.find_one({"_id": enrollment["user_id"]})

            # Calculate progress
            progress = await self._calculate_progress(user_id, subject_id)

            learners.append(
                SubjectLearnerItem(
                    user_id=user_id,
                    display_name=user.get("display_name") if user else None,
                    avatar_url=user.get("avatar_url") if user else None,
                    enrolled_at=enrollment["enrolled_at"],
                    last_accessed_at=enrollment.get("last_accessed_at"),
                    progress_percentage=progress,
                    status=enrollment["status"],
                )
            )

        return SubjectLearnersResponse(
            learners=learners, total=len(learners), subject_id=subject_id
        )

    # ==================== DASHBOARD ====================

    async def get_dashboard_overview(self, user_id: str) -> DashboardOverviewResponse:
        """Get dashboard overview"""
        # Get active enrollments
        active_enrollments = list(
            self.db.studyhub_enrollments.find({"user_id": user_id, "status": "active"})
        )

        # Get completed enrollments
        completed_count = self.db.studyhub_enrollments.count_documents(
            {"user_id": user_id, "status": "completed"}
        )

        # Get total learning time (estimate based on content completion)
        total_completed_contents = self.db.studyhub_learning_progress.count_documents(
            {"user_id": user_id, "status": "completed"}
        )
        total_hours = total_completed_contents * 0.5  # Estimate 30min per content

        # Get recent subjects
        recent_subject_ids = [e["subject_id"] for e in active_enrollments[:5]]
        recent_subjects = []
        for subject_id in recent_subject_ids:
            subject = self.db.studyhub_subjects.find_one(
                {"_id": subject_id, "deleted_at": None}
            )
            if subject:
                from src.models.studyhub_models import SubjectResponse, SubjectMetadata

                recent_subjects.append(
                    SubjectResponse(
                        _id=str(subject["_id"]),
                        owner_id=str(subject["owner_id"]),
                        title=subject["title"],
                        description=subject.get("description"),
                        cover_image_url=subject.get("cover_image_url"),
                        status=subject["status"],
                        visibility=subject["visibility"],
                        metadata=SubjectMetadata(**subject["metadata"]),
                        created_at=subject["created_at"],
                        updated_at=subject["updated_at"],
                    )
                )

        return DashboardOverviewResponse(
            active_subjects=len(active_enrollments),
            completed_subjects=completed_count,
            total_learning_hours=total_hours,
            recent_subjects=recent_subjects,
        )

    async def get_recent_activity(
        self, user_id: str, limit: int = 20
    ) -> RecentActivityResponse:
        """Get recent learning activity"""
        # Get recent progress records
        progress_records = list(
            self.db.studyhub_learning_progress.find(
                {"user_id": user_id, "status": "completed"}
            )
            .sort("completed_at", -1)
            .limit(limit)
        )

        activities = []
        for record in progress_records:
            # Get subject
            subject = self.db.studyhub_subjects.find_one(
                {"_id": record["subject_id"], "deleted_at": None}
            )
            if not subject:
                continue

            # Get module
            module = self.db.studyhub_modules.find_one(
                {"_id": record["module_id"], "deleted_at": None}
            )
            if not module:
                continue

            # Get content
            content = None
            if record.get("content_id"):
                content = self.db.studyhub_module_contents.find_one(
                    {"_id": record["content_id"], "deleted_at": None}
                )

            activities.append(
                ActivityItem(
                    type="completed_content",
                    subject_id=str(record["subject_id"]),
                    subject_title=subject["title"],
                    module_id=str(record["module_id"]),
                    module_title=module["title"],
                    content_id=(
                        str(record["content_id"]) if record.get("content_id") else None
                    ),
                    content_title=content["title"] if content else None,
                    timestamp=record["completed_at"],
                )
            )

        return RecentActivityResponse(activities=activities, total=len(activities))

    # ==================== HELPER METHODS ====================

    async def _calculate_progress(self, user_id: str, subject_id: str) -> float:
        """Calculate progress percentage for subject"""
        # Get total contents
        total_contents = self.db.studyhub_module_contents.count_documents(
            {
                "module_id": {
                    "$in": [
                        m["_id"]
                        for m in self.db.studyhub_modules.find(
                            {"subject_id": ObjectId(subject_id), "deleted_at": None}
                        )
                    ]
                },
                "deleted_at": None,
            }
        )

        if total_contents == 0:
            return 0.0

        # Get completed contents
        completed_contents = self.db.studyhub_learning_progress.count_documents(
            {
                "user_id": user_id,
                "subject_id": ObjectId(subject_id),
                "status": "completed",
            }
        )

        return completed_contents / total_contents
