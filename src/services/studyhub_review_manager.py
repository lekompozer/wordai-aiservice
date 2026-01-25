"""
Service layer for StudyHub Reviews & Ratings
Handles business logic for course reviews
"""

from typing import Optional, Dict, Any
from datetime import datetime
from bson import ObjectId
from fastapi import HTTPException


class StudyHubReviewManager:
    """Manager for review operations"""

    def __init__(self, db):
        self.db = db
        self.reviews_collection = db["studyhub_reviews"]
        self.subjects_collection = db["studyhub_subjects"]
        self.enrollments_collection = db["studyhub_enrollments"]
        self.users_collection = db["users"]

    async def get_course_reviews(
        self,
        course_id: str,
        sort_by: str = "helpful",
        rating_filter: Optional[int] = None,
        skip: int = 0,
        limit: int = 20,
        current_user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get reviews for a course with summary statistics

        Args:
            course_id: Course (subject) ObjectId
            sort_by: Sort order (helpful/recent/rating_high/rating_low)
            rating_filter: Optional filter by rating (1-5)
            skip: Pagination offset
            limit: Items per page
            current_user_id: Optional user ID to check if they marked reviews helpful

        Returns:
            Dictionary with reviews list, summary stats, and pagination info
        """
        # Verify course exists
        course = await self.subjects_collection.find_one({"_id": ObjectId(course_id)})
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")

        # Build query
        query = {"course_id": ObjectId(course_id)}
        if rating_filter:
            query["rating"] = rating_filter

        # Determine sort order
        if sort_by == "recent":
            sort = [("created_at", -1)]
        elif sort_by == "rating_high":
            sort = [("rating", -1), ("created_at", -1)]
        elif sort_by == "rating_low":
            sort = [("rating", 1), ("created_at", -1)]
        else:  # helpful (default)
            sort = [("helpful_count", -1), ("created_at", -1)]

        # Execute query
        cursor = self.reviews_collection.find(query).sort(sort).skip(skip).limit(limit)
        reviews_raw = await cursor.to_list(length=limit)
        total = await self.reviews_collection.count_documents(query)

        # Enrich with author info and check if current user marked helpful
        reviews = []
        for review in reviews_raw:
            user = await self.users_collection.find_one({"uid": review["user_id"]})

            is_helpful = False
            if current_user_id:
                is_helpful = current_user_id in review.get("helpful_by", [])

            reviews.append(
                {
                    "id": str(review["_id"]),
                    "rating": review["rating"],
                    "title": review["title"],
                    "content": review["content"],
                    "author": {
                        "id": review["user_id"],
                        "name": (
                            user.get("displayName", "Unknown User")
                            if user
                            else "Unknown User"
                        ),
                        "avatar": user.get("photoURL") if user else None,
                    },
                    "helpful_count": review.get("helpful_count", 0),
                    "is_helpful": is_helpful,
                    "verified_enrollment": review.get("verified_enrollment", False),
                    "created_at": review["created_at"],
                    "updated_at": review.get("updated_at", review["created_at"]),
                }
            )

        # Calculate summary statistics
        summary = await self._calculate_review_summary(course_id)

        return {
            "reviews": reviews,
            "total": total,
            "skip": skip,
            "limit": limit,
            "summary": summary,
        }

    async def _calculate_review_summary(self, course_id: str) -> Dict[str, Any]:
        """Calculate review summary statistics"""
        pipeline = [
            {"$match": {"course_id": ObjectId(course_id)}},
            {"$group": {"_id": "$rating", "count": {"$sum": 1}}},
        ]

        results = await self.reviews_collection.aggregate(pipeline).to_list(length=None)

        # Build rating distribution
        rating_distribution = {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0}
        total_reviews = 0
        total_rating = 0

        for result in results:
            rating_str = str(result["_id"])
            count = result["count"]
            rating_distribution[rating_str] = count
            total_reviews += count
            total_rating += result["_id"] * count

        avg_rating = total_rating / total_reviews if total_reviews > 0 else 0.0

        return {
            "avg_rating": round(avg_rating, 2),
            "total_reviews": total_reviews,
            "rating_distribution": rating_distribution,
        }

    async def add_review(
        self, course_id: str, rating: int, title: str, content: str, user_id: str
    ) -> Dict[str, Any]:
        """
        Add a review for a course

        Args:
            course_id: Course ObjectId
            rating: Rating (1-5)
            title: Review title
            content: Review content
            user_id: User ID

        Returns:
            Created review document
        """
        # Verify course exists
        course = await self.subjects_collection.find_one({"_id": ObjectId(course_id)})
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")

        # Check if user already reviewed this course
        existing_review = await self.reviews_collection.find_one(
            {"course_id": ObjectId(course_id), "user_id": user_id}
        )
        if existing_review:
            raise HTTPException(
                status_code=400,
                detail="You have already reviewed this course. Use update endpoint to modify your review.",
            )

        # Get user info
        user = await self.users_collection.find_one({"uid": user_id})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Check if user completed the course (verified enrollment)
        enrollment = await self.enrollments_collection.find_one(
            {"subject_id": course_id, "student_id": user_id}
        )

        # Get progress to check completion
        verified_enrollment = False
        if enrollment:
            # Check if progress is 100% or has completed all modules
            progress = enrollment.get("progress", 0)
            verified_enrollment = progress >= 100

        # Create review document
        now = datetime.utcnow()
        review_doc = {
            "course_id": ObjectId(course_id),
            "user_id": user_id,
            "user_name": user.get("displayName", "Unknown User"),
            "user_avatar": user.get("photoURL"),
            "rating": rating,
            "title": title,
            "content": content,
            "helpful_count": 0,
            "helpful_by": [],
            "verified_enrollment": verified_enrollment,
            "created_at": now,
            "updated_at": now,
        }

        result = await self.reviews_collection.insert_one(review_doc)
        review_doc["_id"] = result.inserted_id

        # Update course avg_rating
        await self._update_course_rating(course_id)

        return {
            "id": str(review_doc["_id"]),
            "rating": review_doc["rating"],
            "title": review_doc["title"],
            "content": review_doc["content"],
            "author": {
                "id": user_id,
                "name": review_doc["user_name"],
                "avatar": review_doc["user_avatar"],
            },
            "helpful_count": 0,
            "is_helpful": False,
            "verified_enrollment": verified_enrollment,
            "created_at": review_doc["created_at"],
            "updated_at": review_doc["updated_at"],
        }

    async def _update_course_rating(self, course_id: str):
        """Update course's avg_rating based on all reviews"""
        summary = await self._calculate_review_summary(course_id)

        await self.subjects_collection.update_one(
            {"_id": ObjectId(course_id)},
            {
                "$set": {
                    "avg_rating": summary["avg_rating"],
                    "total_reviews": summary["total_reviews"],
                }
            },
        )

    async def toggle_helpful(self, review_id: str, user_id: str) -> Dict[str, Any]:
        """
        Toggle helpful status on a review

        Args:
            review_id: Review ObjectId
            user_id: User ID

        Returns:
            Dictionary with is_helpful status and new helpful_count
        """
        review = await self.reviews_collection.find_one({"_id": ObjectId(review_id)})
        if not review:
            raise HTTPException(status_code=404, detail="Review not found")

        helpful_by = review.get("helpful_by", [])
        is_helpful = user_id in helpful_by

        if is_helpful:
            # Remove from helpful
            await self.reviews_collection.update_one(
                {"_id": ObjectId(review_id)},
                {"$pull": {"helpful_by": user_id}, "$inc": {"helpful_count": -1}},
            )
            new_is_helpful = False
            new_count = review.get("helpful_count", 0) - 1
        else:
            # Add to helpful
            await self.reviews_collection.update_one(
                {"_id": ObjectId(review_id)},
                {"$addToSet": {"helpful_by": user_id}, "$inc": {"helpful_count": 1}},
            )
            new_is_helpful = True
            new_count = review.get("helpful_count", 0) + 1

        return {"is_helpful": new_is_helpful, "helpful_count": max(0, new_count)}

    async def delete_review(
        self, review_id: str, user_id: str, is_admin: bool = False
    ) -> Dict[str, str]:
        """
        Delete a review

        Args:
            review_id: Review ObjectId
            user_id: User ID (must be review author or admin)
            is_admin: Whether user has admin privileges

        Returns:
            Success message
        """
        review = await self.reviews_collection.find_one({"_id": ObjectId(review_id)})
        if not review:
            raise HTTPException(status_code=404, detail="Review not found")

        # Check authorization
        if review["user_id"] != user_id and not is_admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to delete this review"
            )

        course_id = str(review["course_id"])

        # Delete review
        await self.reviews_collection.delete_one({"_id": ObjectId(review_id)})

        # Update course avg_rating
        await self._update_course_rating(course_id)

        return {"message": "Review deleted successfully"}
