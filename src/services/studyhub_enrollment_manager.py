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
                "user_id": ObjectId(user_id),
                "subject_id": ObjectId(subject_id),
                "status": {"$ne": "dropped"},
            }
        )
        if existing:
            raise HTTPException(status_code=400, detail="Already enrolled in subject")

        # Create enrollment
        now = datetime.now(timezone.utc)
        enrollment_doc = {
            "user_id": ObjectId(user_id),
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
                "user_id": ObjectId(user_id),
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
        query = {"user_id": ObjectId(user_id)}
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
        # Check enrollment
        enrollment = self.db.studyhub_enrollments.find_one(
            {
                "user_id": ObjectId(user_id),
                "subject_id": ObjectId(subject_id),
                "status": {"$ne": "dropped"},
            }
        )
        if not enrollment:
            raise HTTPException(status_code=404, detail="Not enrolled in this subject")

        # Get subject
        subject = self.db.studyhub_subjects.find_one(
            {"_id": ObjectId(subject_id), "deleted_at": None}
        )
        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found")

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
                    "user_id": ObjectId(user_id),
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
                )
            )

        # Overall progress
        overall_progress = (
            completed_contents / total_contents if total_contents > 0 else 0.0
        )

        # Get last position
        last_position = enrollment.get("last_position")

        return SubjectProgressResponse(
            subject_id=subject_id,
            subject_title=subject["title"],
            enrollment_status=enrollment["status"],
            overall_progress=overall_progress,
            total_modules=total_modules,
            completed_modules=completed_modules,
            total_contents=total_contents,
            completed_contents=completed_contents,
            last_position=last_position,
            modules_progress=modules_progress,
            enrolled_at=enrollment["enrolled_at"],
            last_accessed_at=enrollment.get("last_accessed_at"),
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
                "user_id": ObjectId(user_id),
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
                "user_id": ObjectId(user_id),
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
                    "user_id": ObjectId(user_id),
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
                    "user_id": ObjectId(user_id),
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
                        "user_id": ObjectId(user_id),
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
                "user_id": ObjectId(user_id),
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
                    "user_id": ObjectId(user_id),
                    "subject_id": ObjectId(subject_id),
                    "module_id": ObjectId(module_id),
                    "content_id": ObjectId(content_id),
                }
            )
        elif module_id:
            # Delete all content progress in module
            self.db.studyhub_learning_progress.delete_many(
                {
                    "user_id": ObjectId(user_id),
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
                "user_id": ObjectId(user_id),
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
            self.db.studyhub_enrollments.find(
                {"user_id": ObjectId(user_id), "status": "active"}
            )
        )

        # Get completed enrollments
        completed_count = self.db.studyhub_enrollments.count_documents(
            {"user_id": ObjectId(user_id), "status": "completed"}
        )

        # Get total learning time (estimate based on content completion)
        total_completed_contents = self.db.studyhub_learning_progress.count_documents(
            {"user_id": ObjectId(user_id), "status": "completed"}
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
                {"user_id": ObjectId(user_id), "status": "completed"}
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
                "user_id": ObjectId(user_id),
                "subject_id": ObjectId(subject_id),
                "status": "completed",
            }
        )

        return completed_contents / total_contents
