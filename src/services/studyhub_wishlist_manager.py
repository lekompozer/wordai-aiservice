"""
Service layer for StudyHub Wishlist
Handles business logic for course wishlists
"""

from typing import Dict, Any
from datetime import datetime
from bson import ObjectId
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError


class StudyHubWishlistManager:
    """Manager for wishlist operations"""

    def __init__(self, db):
        self.db = db
        self.wishlist_collection = db["studyhub_wishlist"]
        self.subjects_collection = db["studyhub_subjects"]
        self.users_collection = db["users"]

    async def add_to_wishlist(self, course_id: str, user_id: str) -> Dict[str, Any]:
        """
        Add a course to user's wishlist

        Args:
            course_id: Course ObjectId
            user_id: User ID

        Returns:
            Success message with course_id and timestamp

        Raises:
            404: Course not found
            400: Already in wishlist
        """
        # Verify course exists and is public
        course = await self.subjects_collection.find_one({"_id": ObjectId(course_id)})
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")

        if not course.get("is_public_marketplace"):
            raise HTTPException(
                status_code=400, detail="Cannot add private course to wishlist"
            )

        # Add to wishlist (unique constraint will prevent duplicates)
        now = datetime.utcnow()
        wishlist_doc = {
            "user_id": user_id,
            "course_id": ObjectId(course_id),
            "added_at": now,
        }

        try:
            await self.wishlist_collection.insert_one(wishlist_doc)
        except DuplicateKeyError:
            raise HTTPException(
                status_code=400, detail="Course is already in your wishlist"
            )

        return {
            "message": "Course added to wishlist successfully",
            "course_id": course_id,
            "added_at": now,
        }

    async def get_wishlist(
        self, user_id: str, skip: int = 0, limit: int = 20
    ) -> Dict[str, Any]:
        """
        Get user's wishlist with course details

        Args:
            user_id: User ID
            skip: Pagination offset
            limit: Items per page

        Returns:
            Dictionary with courses list and pagination info
        """
        # Get wishlist items
        cursor = (
            self.wishlist_collection.find({"user_id": user_id})
            .sort("added_at", -1)
            .skip(skip)
            .limit(limit)
        )

        wishlist_items = await cursor.to_list(length=limit)
        total = await self.wishlist_collection.count_documents({"user_id": user_id})

        # Enrich with course details
        courses = []
        for item in wishlist_items:
            course = await self.subjects_collection.find_one({"_id": item["course_id"]})

            if not course:
                # Course was deleted, skip
                continue

            # Get creator info
            creator = await self.users_collection.find_one({"uid": course["owner_id"]})

            courses.append(
                {
                    "id": str(course["_id"]),
                    "title": course["title"],
                    "description": course.get("description"),
                    "cover_image_url": course.get("cover_image_url"),
                    "creator_id": course["owner_id"],
                    "creator_name": (
                        creator.get("displayName", "Unknown") if creator else "Unknown"
                    ),
                    "creator_avatar": creator.get("photoURL") if creator else None,
                    "rating": course.get("avg_rating", 0.0),
                    "students_count": course.get("total_learners", 0),
                    "total_modules": course.get("total_modules", 0),
                    "level": course.get("level", "beginner"),
                    "category": course.get("category", ""),
                    "tags": course.get("tags", []),
                    "is_free": course.get("is_free", True),
                    "price": course.get("price"),
                    "added_at": item["added_at"],
                }
            )

        return {"courses": courses, "total": total, "skip": skip, "limit": limit}

    async def remove_from_wishlist(
        self, course_id: str, user_id: str
    ) -> Dict[str, str]:
        """
        Remove a course from user's wishlist

        Args:
            course_id: Course ObjectId
            user_id: User ID

        Returns:
            Success message

        Raises:
            404: Course not in wishlist
        """
        result = await self.wishlist_collection.delete_one(
            {"user_id": user_id, "course_id": ObjectId(course_id)}
        )

        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Course not found in wishlist")

        return {
            "message": "Course removed from wishlist successfully",
            "course_id": course_id,
        }

    async def check_wishlist(self, course_id: str, user_id: str) -> Dict[str, Any]:
        """
        Check if a course is in user's wishlist

        Args:
            course_id: Course ObjectId
            user_id: User ID

        Returns:
            Dictionary with is_wishlisted status
        """
        wishlist_item = await self.wishlist_collection.find_one(
            {"user_id": user_id, "course_id": ObjectId(course_id)}
        )

        return {"is_wishlisted": wishlist_item is not None, "course_id": course_id}
