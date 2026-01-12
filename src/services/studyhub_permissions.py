"""
StudyHub Permission System
Handles enrollment-based access control for StudyHub content
"""

from typing import Optional, Literal
from bson import ObjectId
from fastapi import HTTPException

from src.database.db_manager import DBManager


class StudyHubPermissions:
    """Permission checker for StudyHub content access"""

    def __init__(self):
        self.db_manager = DBManager()
        self.db = self.db_manager.db

    async def check_subject_owner(self, user_id: str, subject_id: str) -> bool:
        """
        Check if user is the owner of subject

        Args:
            user_id: User ID to check
            subject_id: Subject ID

        Returns:
            True if owner, raises HTTPException if not
        """
        subject = self.db.studyhub_subjects.find_one(
            {"_id": ObjectId(subject_id), "owner_id": user_id}
        )

        if not subject:
            raise HTTPException(
                status_code=403, detail="Only subject owner can perform this action"
            )

        return True

    async def check_content_access(
        self,
        user_id: str,
        content_id: str,
        allow_preview: bool = True,
    ) -> Literal[True, "preview_only"]:
        """
        Check if user has access to content

        Access rules:
        1. Owner always has access
        2. Preview content accessible if allow_preview=True
        3. Enrolled users have access to non-preview content
        4. Others denied

        Args:
            user_id: User ID requesting access
            content_id: Content ID to access
            allow_preview: Allow preview content access

        Returns:
            True for full access, "preview_only" for limited access

        Raises:
            HTTPException if access denied
        """
        # Get content
        content = self.db.studyhub_module_contents.find_one(
            {"_id": ObjectId(content_id)}
        )

        if not content:
            raise HTTPException(status_code=404, detail="Content not found")

        # Get subject through module
        module = self.db.studyhub_modules.find_one({"_id": content["module_id"]})
        if not module:
            raise HTTPException(status_code=404, detail="Module not found")

        subject = self.db.studyhub_subjects.find_one({"_id": module["subject_id"]})
        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found")

        # Check 1: Owner always has access
        if subject["owner_id"] == user_id:
            return True

        # Check 2: Preview content
        if content.get("is_preview", False) and allow_preview:
            return "preview_only"

        # Check 3: Subject must be published to marketplace
        if not subject.get("is_public_marketplace", False):
            raise HTTPException(status_code=404, detail="Subject not available")

        # Check 4: Must have active enrollment
        enrollment = self.db.studyhub_enrollments.find_one(
            {
                "user_id": user_id,
                "subject_id": subject["_id"],
                "status": "active",
            }
        )

        if not enrollment:
            raise HTTPException(
                status_code=403,
                detail="Enrollment required. Please purchase this subject to access content.",
            )

        return True

    async def check_module_owner(self, user_id: str, module_id: str) -> bool:
        """
        Check if user owns the subject containing this module

        Args:
            user_id: User ID to check
            module_id: Module ID

        Returns:
            True if owner, raises HTTPException if not
        """
        module = self.db.studyhub_modules.find_one({"_id": ObjectId(module_id)})

        if not module:
            raise HTTPException(status_code=404, detail="Module not found")

        return await self.check_subject_owner(user_id, str(module["subject_id"]))

    async def get_subject_from_content(self, content_id: str) -> dict:
        """
        Get subject from content ID

        Args:
            content_id: Content ID

        Returns:
            Subject document
        """
        content = self.db.studyhub_module_contents.find_one(
            {"_id": ObjectId(content_id)}
        )
        if not content:
            raise HTTPException(status_code=404, detail="Content not found")

        module = self.db.studyhub_modules.find_one({"_id": content["module_id"]})
        if not module:
            raise HTTPException(status_code=404, detail="Module not found")

        subject = self.db.studyhub_subjects.find_one({"_id": module["subject_id"]})
        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found")

        return subject

    async def update_content_studyhub_context(
        self,
        collection_name: str,
        content_id: str,
        subject_id: str,
        module_id: str,
        enabled: bool = True,
        is_preview: bool = False,
    ):
        """
        Update studyhub_context field in original content collection

        Args:
            collection_name: Collection name (online_documents, online_tests, online_books)
            content_id: Content ID in original collection
            subject_id: Subject ID
            module_id: Module ID
            enabled: Enable StudyHub access
            is_preview: Mark as preview content
        """
        subject = self.db.studyhub_subjects.find_one({"_id": ObjectId(subject_id)})

        mode = (
            "marketplace" if subject.get("is_public_marketplace", False) else "private"
        )

        update_data = {
            "studyhub_context.enabled": enabled,
            "studyhub_context.mode": mode,
            "studyhub_context.subject_id": ObjectId(subject_id),
            "studyhub_context.module_id": ObjectId(module_id),
            "studyhub_context.requires_enrollment": not is_preview,
            "studyhub_context.is_preview": is_preview,
        }

        if not enabled:
            # Remove studyhub_context when unlinking
            update_data = {"$unset": {"studyhub_context": ""}}
        else:
            update_data = {"$set": update_data}

        self.db[collection_name].update_one({"_id": ObjectId(content_id)}, update_data)

    async def publish_subject_to_marketplace(self, subject_id: str):
        """
        Update all content permissions when subject is published to marketplace

        Args:
            subject_id: Subject ID being published
        """
        # Get all modules in subject
        modules = list(
            self.db.studyhub_modules.find({"subject_id": ObjectId(subject_id)})
        )

        for module in modules:
            # Get all contents in module
            contents = list(
                self.db.studyhub_module_contents.find({"module_id": module["_id"]})
            )

            for content in contents:
                # Map content type to collection
                collection_map = {
                    "document": "online_documents",
                    "test": "online_tests",
                    "book": "online_books",
                    "file": "studyhub_files",
                }

                collection_name = collection_map.get(content["content_type"])
                if not collection_name:
                    continue

                # Get reference ID
                ref_id = content["data"].get(f"{content['content_type']}_id")
                if not ref_id:
                    continue

                # Update to marketplace mode
                self.db[collection_name].update_one(
                    {"_id": ObjectId(ref_id)},
                    {
                        "$set": {
                            "studyhub_context.mode": "marketplace",
                            "studyhub_context.requires_enrollment": not content.get(
                                "is_preview", False
                            ),
                        }
                    },
                )
