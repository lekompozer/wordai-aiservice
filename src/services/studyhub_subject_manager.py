"""
StudyHub Subject Manager Service
Business logic for subject management
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from bson import ObjectId
import boto3
import os
from io import BytesIO
from PIL import Image

from src.models.studyhub_models import (
    SubjectResponse,
    SubjectListResponse,
    SubjectMetadata,
    SubjectStatus,
    SubjectVisibility,
)

logger = logging.getLogger("chatbot")


class StudyHubSubjectManager:
    """Manager for StudyHub subject operations"""
    
    def __init__(self, db, user_id: Optional[str] = None):
        """
        Initialize manager
        
        Args:
            db: MongoDB database instance
            user_id: Current user ID (optional for public access)
        """
        self.db = db
        self.user_id = user_id
        self.subjects = db["studyhub_subjects"]
        self.modules = db["studyhub_modules"]
        self.enrollments = db["studyhub_enrollments"]
        
        # S3/CDN config for cover images
        self.s3_client = None
        self.bucket_name = os.getenv("AWS_S3_BUCKET_NAME")
        if self.bucket_name:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                region_name=os.getenv("AWS_REGION", "us-east-1")
            )
    
    def _to_object_id(self, id_str: str) -> ObjectId:
        """Convert string to ObjectId"""
        try:
            return ObjectId(id_str)
        except Exception:
            raise ValueError(f"Invalid ObjectId: {id_str}")
    
    def _serialize_subject(self, subject: Dict, include_user_context: bool = True) -> Dict:
        """Serialize subject document to response format"""
        if not subject:
            return None
        
        result = {
            "_id": str(subject["_id"]),
            "owner_id": subject["owner_id"],
            "title": subject["title"],
            "description": subject.get("description"),
            "cover_image_url": subject.get("cover_image_url"),
            "status": subject["status"],
            "visibility": subject["visibility"],
            "metadata": subject.get("metadata", {
                "total_modules": 0,
                "total_learners": 0,
                "avg_rating": 0.0,
                "tags": []
            }),
            "created_at": subject["created_at"],
            "updated_at": subject["updated_at"],
        }
        
        if include_user_context and self.user_id:
            # Check if user is enrolled
            enrollment = self.enrollments.find_one({
                "subject_id": subject["_id"],
                "user_id": self.user_id,
                "status": {"$ne": "dropped"}
            })
            result["is_enrolled"] = enrollment is not None
            result["is_owner"] = subject["owner_id"] == self.user_id
        else:
            result["is_enrolled"] = False
            result["is_owner"] = False
        
        return result
    
    async def create_subject(
        self,
        title: str,
        description: Optional[str] = None,
        visibility: str = "private",
    ) -> SubjectResponse:
        """
        Create a new subject
        
        Args:
            title: Subject title
            description: Subject description
            visibility: public or private
            
        Returns:
            SubjectResponse
        """
        if not self.user_id:
            raise ValueError("User must be authenticated to create subject")
        
        now = datetime.now(timezone.utc)
        
        subject_doc = {
            "owner_id": self.user_id,
            "title": title,
            "description": description,
            "cover_image_url": None,
            "status": SubjectStatus.DRAFT.value,
            "visibility": visibility,
            "metadata": {
                "total_modules": 0,
                "total_learners": 0,
                "avg_rating": 0.0,
                "tags": []
            },
            "created_at": now,
            "updated_at": now,
        }
        
        result = self.subjects.insert_one(subject_doc)
        subject_doc["_id"] = result.inserted_id
        
        logger.info(f"Created subject {result.inserted_id} by user {self.user_id}")
        
        return SubjectResponse(**self._serialize_subject(subject_doc))
    
    async def get_subject(
        self,
        subject_id: str,
        include_stats: bool = False,
    ) -> Optional[SubjectResponse]:
        """
        Get subject by ID
        
        Args:
            subject_id: Subject ID
            include_stats: Include updated metadata
            
        Returns:
            SubjectResponse or None
        """
        subject = self.subjects.find_one({"_id": self._to_object_id(subject_id)})
        
        if not subject:
            return None
        
        # Check visibility permissions
        if subject["visibility"] == SubjectVisibility.PRIVATE.value:
            if not self.user_id or subject["owner_id"] != self.user_id:
                # Check if user is enrolled
                if not self.user_id:
                    return None
                enrollment = self.enrollments.find_one({
                    "subject_id": subject["_id"],
                    "user_id": self.user_id,
                    "status": {"$ne": "dropped"}
                })
                if not enrollment:
                    return None
        
        # Update stats if requested
        if include_stats:
            module_count = self.modules.count_documents({"subject_id": subject["_id"]})
            learner_count = self.enrollments.count_documents({
                "subject_id": subject["_id"],
                "status": {"$ne": "dropped"}
            })
            
            subject["metadata"]["total_modules"] = module_count
            subject["metadata"]["total_learners"] = learner_count
        
        return SubjectResponse(**self._serialize_subject(subject))
    
    async def update_subject(
        self,
        subject_id: str,
        updates: Dict[str, Any],
    ) -> Optional[SubjectResponse]:
        """
        Update subject
        
        Args:
            subject_id: Subject ID
            updates: Fields to update
            
        Returns:
            Updated SubjectResponse or None
        """
        if not self.user_id:
            raise ValueError("User must be authenticated")
        
        subject = self.subjects.find_one({
            "_id": self._to_object_id(subject_id),
            "owner_id": self.user_id,
        })
        
        if not subject:
            return None
        
        # Prepare updates
        update_data = {k: v for k, v in updates.items() if v is not None}
        update_data["updated_at"] = datetime.now(timezone.utc)
        
        # Update subject
        self.subjects.update_one(
            {"_id": subject["_id"]},
            {"$set": update_data}
        )
        
        # Fetch updated subject
        updated_subject = self.subjects.find_one({"_id": subject["_id"]})
        
        logger.info(f"Updated subject {subject_id} by user {self.user_id}")
        
        return SubjectResponse(**self._serialize_subject(updated_subject))
    
    async def delete_subject(
        self,
        subject_id: str,
        confirm: bool = False,
    ) -> Dict[str, Any]:
        """
        Delete subject (soft delete)
        
        Args:
            subject_id: Subject ID
            confirm: Confirm deletion if has learners
            
        Returns:
            Dict with success status and message
        """
        if not self.user_id:
            raise ValueError("User must be authenticated")
        
        subject = self.subjects.find_one({
            "_id": self._to_object_id(subject_id),
            "owner_id": self.user_id,
        })
        
        if not subject:
            return {"success": False}
        
        # Check learners
        learner_count = self.enrollments.count_documents({
            "subject_id": subject["_id"],
            "status": {"$ne": "dropped"}
        })
        
        if learner_count > 0 and not confirm:
            return {
                "success": False,
                "requires_confirmation": True,
                "learner_count": learner_count,
            }
        
        # Soft delete
        self.subjects.update_one(
            {"_id": subject["_id"]},
            {
                "$set": {
                    "status": SubjectStatus.ARCHIVED.value,
                    "updated_at": datetime.now(timezone.utc),
                }
            }
        )
        
        logger.info(f"Archived subject {subject_id} by user {self.user_id}")
        
        return {
            "success": True,
            "message": f"Subject archived successfully. {learner_count} learners affected.",
        }
    
    async def list_subjects(
        self,
        status_filter: Optional[str] = None,
        visibility: Optional[str] = None,
        owner_id: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
        sort: str = "created_at",
    ) -> SubjectListResponse:
        """
        List subjects with filters
        
        Args:
            status_filter: Filter by status
            visibility: Filter by visibility
            owner_id: Filter by owner
            page: Page number
            limit: Items per page
            sort: Sort field
            
        Returns:
            SubjectListResponse
        """
        query = {}
        
        # Build query
        if status_filter:
            query["status"] = status_filter
        
        if visibility:
            query["visibility"] = visibility
        
        if owner_id:
            query["owner_id"] = owner_id
        
        # If not owner, only show published public subjects or enrolled subjects
        if not owner_id or (owner_id != self.user_id):
            if not self.user_id:
                query["visibility"] = SubjectVisibility.PUBLIC.value
                query["status"] = SubjectStatus.PUBLISHED.value
            else:
                # Show public published OR owned subjects OR enrolled subjects
                enrolled_subject_ids = [
                    e["subject_id"] for e in self.enrollments.find({
                        "user_id": self.user_id,
                        "status": {"$ne": "dropped"}
                    })
                ]
                query["$or"] = [
                    {"visibility": SubjectVisibility.PUBLIC.value, "status": SubjectStatus.PUBLISHED.value},
                    {"owner_id": self.user_id},
                    {"_id": {"$in": enrolled_subject_ids}},
                ]
        
        # Count total
        total = self.subjects.count_documents(query)
        
        # Get paginated results
        skip = (page - 1) * limit
        sort_field = sort if sort in ["created_at", "updated_at", "title"] else "created_at"
        sort_direction = -1 if sort_field != "title" else 1
        
        subjects = list(self.subjects.find(query)
                       .sort(sort_field, sort_direction)
                       .skip(skip)
                       .limit(limit))
        
        return SubjectListResponse(
            subjects=[SubjectResponse(**self._serialize_subject(s)) for s in subjects],
            total=total,
            page=page,
            limit=limit,
            has_more=(skip + limit) < total,
        )
    
    async def get_owner_subjects(
        self,
        owner_id: str,
        is_owner: bool = False,
        page: int = 1,
        limit: int = 20,
    ) -> SubjectListResponse:
        """
        Get subjects of specific owner
        
        Args:
            owner_id: Owner user ID
            is_owner: If viewer is the owner
            page: Page number
            limit: Items per page
            
        Returns:
            SubjectListResponse
        """
        query = {"owner_id": owner_id}
        
        # If not owner, only show published public subjects
        if not is_owner:
            query["visibility"] = SubjectVisibility.PUBLIC.value
            query["status"] = SubjectStatus.PUBLISHED.value
        
        total = self.subjects.count_documents(query)
        skip = (page - 1) * limit
        
        subjects = list(self.subjects.find(query)
                       .sort("created_at", -1)
                       .skip(skip)
                       .limit(limit))
        
        return SubjectListResponse(
            subjects=[SubjectResponse(**self._serialize_subject(s)) for s in subjects],
            total=total,
            page=page,
            limit=limit,
            has_more=(skip + limit) < total,
        )
    
    async def upload_cover(
        self,
        subject_id: str,
        file_content: bytes,
        filename: str,
        content_type: str,
    ) -> Optional[str]:
        """
        Upload cover image
        
        Args:
            subject_id: Subject ID
            file_content: File bytes
            filename: Original filename
            content_type: MIME type
            
        Returns:
            Cover image URL or None
        """
        if not self.user_id:
            raise ValueError("User must be authenticated")
        
        subject = self.subjects.find_one({
            "_id": self._to_object_id(subject_id),
            "owner_id": self.user_id,
        })
        
        if not subject:
            return None
        
        # Process image
        image = Image.open(BytesIO(file_content))
        
        # Resize to max 1200x800 maintaining aspect ratio
        max_size = (1200, 800)
        image.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # Convert to RGB if needed
        if image.mode in ('RGBA', 'P'):
            image = image.convert('RGB')
        
        # Save optimized image
        output = BytesIO()
        image.save(output, format='JPEG', quality=85, optimize=True)
        output.seek(0)
        
        # Upload to S3 if configured, otherwise use local storage
        if self.s3_client and self.bucket_name:
            key = f"studyhub/covers/{subject_id}.jpg"
            self.s3_client.upload_fileobj(
                output,
                self.bucket_name,
                key,
                ExtraArgs={'ContentType': 'image/jpeg', 'ACL': 'public-read'}
            )
            cover_url = f"https://{self.bucket_name}.s3.amazonaws.com/{key}"
        else:
            # Fallback: Save locally (for development)
            os.makedirs("uploads/studyhub/covers", exist_ok=True)
            local_path = f"uploads/studyhub/covers/{subject_id}.jpg"
            with open(local_path, 'wb') as f:
                f.write(output.read())
            cover_url = f"/uploads/studyhub/covers/{subject_id}.jpg"
        
        # Update subject
        self.subjects.update_one(
            {"_id": subject["_id"]},
            {
                "$set": {
                    "cover_image_url": cover_url,
                    "updated_at": datetime.now(timezone.utc),
                }
            }
        )
        
        logger.info(f"Uploaded cover for subject {subject_id}")
        
        return cover_url
    
    async def publish_subject(self, subject_id: str) -> Optional[SubjectResponse]:
        """
        Publish subject
        
        Args:
            subject_id: Subject ID
            
        Returns:
            Updated SubjectResponse or None
            
        Raises:
            ValueError: If validation fails
        """
        if not self.user_id:
            raise ValueError("User must be authenticated")
        
        subject = self.subjects.find_one({
            "_id": self._to_object_id(subject_id),
            "owner_id": self.user_id,
        })
        
        if not subject:
            return None
        
        # Validation: Must have at least 1 module
        module_count = self.modules.count_documents({"subject_id": subject["_id"]})
        if module_count == 0:
            raise ValueError("Cannot publish subject without at least 1 module")
        
        # Update status
        self.subjects.update_one(
            {"_id": subject["_id"]},
            {
                "$set": {
                    "status": SubjectStatus.PUBLISHED.value,
                    "updated_at": datetime.now(timezone.utc),
                }
            }
        )
        
        updated_subject = self.subjects.find_one({"_id": subject["_id"]})
        
        logger.info(f"Published subject {subject_id} by user {self.user_id}")
        
        return SubjectResponse(**self._serialize_subject(updated_subject))
