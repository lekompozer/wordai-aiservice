"""
StudyHub Community Manager - Service layer for marketplace community subjects

Handles:
- Listing/filtering community subjects
- Getting subject details with top courses
- Managing subject publishing to community
- Updating stats (total_courses, total_students)
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from bson import ObjectId
import logging

from src.database.db_manager import DBManager

logger = logging.getLogger(__name__)


class StudyHubCommunityManager:
    """Manager for StudyHub community subjects and publishing"""
    
    def __init__(self):
        self.db_manager = DBManager()
        self.db = self.db_manager.db
        self.community_subjects = self.db["community_subjects"]
        self.subjects = self.db["studyhub_subjects"]
        
    async def get_community_subjects(
        self,
        category: Optional[str] = None,
        search: Optional[str] = None,
        is_featured: Optional[bool] = None,
        sort_by: str = "display_order",
        skip: int = 0,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Get list of community subjects with filters
        
        Args:
            category: Filter by category (it, business, finance, etc.)
            search: Text search in title/title_vi
            is_featured: Filter featured subjects only
            sort_by: Sort field (display_order, total_courses, total_students)
            skip: Pagination offset
            limit: Max results
            
        Returns:
            {
                "subjects": [...],
                "total": count,
                "skip": skip,
                "limit": limit
            }
        """
        try:
            # Build filter
            filter_query: Dict[str, Any] = {}
            
            if category:
                filter_query["category"] = category
                
            if is_featured is not None:
                filter_query["is_featured"] = is_featured
                
            if search:
                # MongoDB text search
                filter_query["$text"] = {"$search": search}
            
            # Sort mapping
            sort_field_map = {
                "display_order": "display_order",
                "total_courses": "total_courses",
                "total_students": "total_students",
                "popularity": "total_students"
            }
            
            sort_field = sort_field_map.get(sort_by, "display_order")
            sort_order = -1 if sort_by in ["total_courses", "total_students", "popularity"] else 1
            
            # Count total
            total = self.community_subjects.count_documents(filter_query)
            
            # Query subjects
            cursor = self.community_subjects.find(filter_query).sort(
                sort_field, sort_order
            ).skip(skip).limit(limit)
            
            subjects = []
            for doc in cursor:
                doc["id"] = doc["_id"]  # Add id field for frontend
                subjects.append(doc)
            
            return {
                "subjects": subjects,
                "total": total,
                "skip": skip,
                "limit": limit
            }
            
        except Exception as e:
            logger.error(f"Error getting community subjects: {e}")
            raise
            
    async def get_community_subject_detail(self, slug: str) -> Optional[Dict[str, Any]]:
        """
        Get community subject detail with top 3 courses preview
        
        Args:
            slug: Community subject slug
            
        Returns:
            {
                "id": "python-programming",
                "slug": "python-programming",
                "title": "Python Programming",
                "total_courses": 25,
                "top_courses": [...]  # Top 3 courses by total_students
            }
        """
        try:
            # Get subject
            subject = self.community_subjects.find_one({"slug": slug})
            if not subject:
                return None
                
            subject["id"] = subject["_id"]
            
            # Get top 3 published courses in this subject
            top_courses_cursor = self.subjects.find({
                "community_subject_id": slug,
                "marketplace_status": "published"
            }).sort("total_students", -1).limit(3)
            
            top_courses = []
            for course in top_courses_cursor:
                top_courses.append({
                    "id": str(course["_id"]),
                    "title": course["title"],
                    "thumbnail_url": course.get("thumbnail_url", ""),
                    "creator_name": course.get("creator_name", "Unknown"),
                    "total_students": course.get("total_students", 0),
                    "average_rating": course.get("average_rating", 0.0),
                    "total_reviews": course.get("total_reviews", 0),
                })
                
            subject["top_courses"] = top_courses
            
            return subject
            
        except Exception as e:
            logger.error(f"Error getting subject detail for {slug}: {e}")
            raise
            
    async def get_courses_in_subject(
        self,
        slug: str,
        sort_by: str = "popularity",
        skip: int = 0,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Get all published courses in a community subject
        
        Args:
            slug: Community subject slug
            sort_by: Sort by (popularity, rating, newest)
            skip: Pagination offset
            limit: Max results
            
        Returns:
            {
                "courses": [...],
                "total": count,
                "skip": skip,
                "limit": limit
            }
        """
        try:
            # Verify subject exists
            subject = self.community_subjects.find_one({"slug": slug})
            if not subject:
                raise ValueError(f"Community subject not found: {slug}")
            
            filter_query = {
                "community_subject_id": slug,
                "marketplace_status": "published"
            }
            
            # Sort mapping
            sort_field_map = {
                "popularity": ("total_students", -1),
                "rating": ("average_rating", -1),
                "newest": ("marketplace_published_at", -1),
                "oldest": ("marketplace_published_at", 1),
            }
            
            sort_field, sort_order = sort_field_map.get(sort_by, ("total_students", -1))
            
            # Count total
            total = self.subjects.count_documents(filter_query)
            
            # Query courses
            cursor = self.subjects.find(filter_query).sort(
                sort_field, sort_order
            ).skip(skip).limit(limit)
            
            courses = []
            for doc in cursor:
                courses.append({
                    "id": str(doc["_id"]),
                    "title": doc["title"],
                    "description": doc.get("description", ""),
                    "thumbnail_url": doc.get("thumbnail_url", ""),
                    "creator_id": doc.get("creator_id", ""),
                    "creator_name": doc.get("creator_name", "Unknown"),
                    "total_students": doc.get("total_students", 0),
                    "average_rating": doc.get("average_rating", 0.0),
                    "total_reviews": doc.get("total_reviews", 0),
                    "price": doc.get("price", 0),
                    "currency": doc.get("currency", "VND"),
                    "organization": doc.get("organization", ""),
                    "is_verified_organization": doc.get("is_verified_organization", False),
                    "marketplace_published_at": doc.get("marketplace_published_at"),
                })
            
            return {
                "courses": courses,
                "total": total,
                "skip": skip,
                "limit": limit,
                "community_subject": {
                    "id": subject["_id"],
                    "slug": subject["slug"],
                    "title": subject["title"],
                    "title_vi": subject["title_vi"],
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting courses in subject {slug}: {e}")
            raise
            
    async def publish_subject_to_community(
        self,
        subject_id: str,
        community_subject_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Publish a subject (course) to community marketplace
        
        Args:
            subject_id: StudyHub subject ID
            community_subject_id: Community subject slug to publish to
            user_id: Creator user ID (for ownership verification)
            
        Returns:
            Updated subject document
        """
        try:
            # Verify subject exists and user owns it
            subject = self.subjects.find_one({
                "_id": ObjectId(subject_id),
                "creator_id": user_id
            })
            
            if not subject:
                raise ValueError("Subject not found or you don't have permission")
                
            # Check if already published
            if subject.get("marketplace_status") == "published":
                raise ValueError("Subject is already published to community")
                
            # Verify community subject exists
            community_subject = self.community_subjects.find_one({"_id": community_subject_id})
            if not community_subject:
                raise ValueError(f"Community subject not found: {community_subject_id}")
            
            # Update subject to published
            now = datetime.utcnow()
            update_result = self.subjects.update_one(
                {"_id": ObjectId(subject_id)},
                {
                    "$set": {
                        "community_subject_id": community_subject_id,
                        "marketplace_status": "published",
                        "marketplace_published_at": now,
                        "updated_at": now
                    }
                }
            )
            
            if update_result.modified_count == 0:
                raise ValueError("Failed to publish subject")
            
            # Increment community subject total_courses
            self.community_subjects.update_one(
                {"_id": community_subject_id},
                {
                    "$inc": {"total_courses": 1},
                    "$set": {"updated_at": now}
                }
            )
            
            # Return updated subject
            updated_subject = self.subjects.find_one({"_id": ObjectId(subject_id)})
            updated_subject["id"] = str(updated_subject["_id"])
            
            logger.info(f"✅ Published subject {subject_id} to community {community_subject_id}")
            
            return updated_subject
            
        except Exception as e:
            logger.error(f"Error publishing subject {subject_id}: {e}")
            raise
            
    async def unpublish_subject(self, subject_id: str, user_id: str) -> Dict[str, Any]:
        """
        Unpublish a subject from community marketplace
        
        Args:
            subject_id: StudyHub subject ID
            user_id: Creator user ID (for ownership verification)
            
        Returns:
            Updated subject document
        """
        try:
            # Verify subject exists, user owns it, and it's published
            subject = self.subjects.find_one({
                "_id": ObjectId(subject_id),
                "creator_id": user_id,
                "marketplace_status": "published"
            })
            
            if not subject:
                raise ValueError("Subject not found, not published, or you don't have permission")
            
            community_subject_id = subject.get("community_subject_id")
            
            # Update subject to unpublished
            now = datetime.utcnow()
            update_result = self.subjects.update_one(
                {"_id": ObjectId(subject_id)},
                {
                    "$set": {
                        "marketplace_status": "draft",
                        "updated_at": now
                    },
                    "$unset": {
                        "marketplace_published_at": ""
                    }
                }
            )
            
            if update_result.modified_count == 0:
                raise ValueError("Failed to unpublish subject")
            
            # Decrement community subject total_courses
            if community_subject_id:
                self.community_subjects.update_one(
                    {"_id": community_subject_id},
                    {
                        "$inc": {"total_courses": -1},
                        "$set": {"updated_at": now}
                    }
                )
            
            # Return updated subject
            updated_subject = self.subjects.find_one({"_id": ObjectId(subject_id)})
            updated_subject["id"] = str(updated_subject["_id"])
            
            logger.info(f"✅ Unpublished subject {subject_id} from community")
            
            return updated_subject
            
        except Exception as e:
            logger.error(f"Error unpublishing subject {subject_id}: {e}")
            raise
            
    async def update_marketplace_info(
        self,
        subject_id: str,
        user_id: str,
        organization: Optional[str] = None,
        is_verified_organization: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Update marketplace-specific information for a subject
        
        Args:
            subject_id: StudyHub subject ID
            user_id: Creator user ID (for ownership verification)
            organization: Organization/company name
            is_verified_organization: Whether organization is verified
            
        Returns:
            Updated subject document
        """
        try:
            # Verify subject exists and user owns it
            subject = self.subjects.find_one({
                "_id": ObjectId(subject_id),
                "creator_id": user_id
            })
            
            if not subject:
                raise ValueError("Subject not found or you don't have permission")
            
            # Build update fields
            update_fields: Dict[str, Any] = {
                "updated_at": datetime.utcnow()
            }
            
            if organization is not None:
                update_fields["organization"] = organization
                
            if is_verified_organization is not None:
                update_fields["is_verified_organization"] = is_verified_organization
            
            # Update subject
            update_result = self.subjects.update_one(
                {"_id": ObjectId(subject_id)},
                {"$set": update_fields}
            )
            
            if update_result.modified_count == 0:
                # No changes made (fields already had these values)
                pass
            
            # Return updated subject
            updated_subject = self.subjects.find_one({"_id": ObjectId(subject_id)})
            updated_subject["id"] = str(updated_subject["_id"])
            
            logger.info(f"✅ Updated marketplace info for subject {subject_id}")
            
            return updated_subject
            
        except Exception as e:
            logger.error(f"Error updating marketplace info for {subject_id}: {e}")
            raise
