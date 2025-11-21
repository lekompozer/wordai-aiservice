"""
Book Review Routes
Endpoints for book reviews and likes

Endpoints:
- POST /{book_id}/reviews - Create a review
- GET /{book_id}/reviews - List reviews
- DELETE /{book_id}/reviews/{review_id} - Delete a review
- POST /{book_id}/reviews/{review_id}/like - Like/unlike a review
- POST /{book_id}/reviews/image/presigned-url - Get presigned URL for review image
"""

from fastapi import APIRouter, HTTPException, Depends, Query, status
from typing import Optional, Dict, Any
from datetime import datetime
import logging
import uuid

from src.database.db_manager import DBManager
from src.middleware.firebase_auth import get_current_user
from src.models.book_review_models import (
    BookReviewCreate,
    BookReviewResponse,
    BookReviewListResponse,
)

router = APIRouter(prefix="/books", tags=["Book Reviews"])
logger = logging.getLogger(__name__)

# Initialize DB
db_manager = DBManager()
db = db_manager.db


@router.post(
    "/{book_id}/reviews",
    response_model=BookReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create book review",
)
async def create_book_review(
    book_id: str,
    review_data: BookReviewCreate,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Create a review for a book**

    - Each user can only review a book once
    - Review includes text, optional image, and rating (1-5 stars)
    - User cannot review their own book
    - Only users who have access to the book can review it

    **Authentication required**

    **Request Body:**
    ```json
    {
        "text": "Great book! Very helpful content...",
        "image_url": "https://cdn.example.com/review-screenshot.jpg",
        "rating": 5,
        "reviewer_name": "John Doe",
        "reviewer_avatar_url": "https://avatar.url"
    }
    ```

    **Returns:**
    - 201: Review created successfully
    - 403: Cannot review own book or no access
    - 404: Book not found
    - 409: Already reviewed this book
    """
    try:
        user_id = user["uid"]

        # Check book exists
        book = db.online_books.find_one(
            {"book_id": book_id, "deleted_at": None}
        )
        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found",
            )

        # Cannot review own book
        if book.get("user_id") == user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot review your own book",
            )

        # Check if user already reviewed this book
        existing = db.book_reviews.find_one(
            {
                "book_id": book_id,
                "reviewer_user_id": user_id,
            }
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You have already reviewed this book",
            )

        # Create review
        review_id = f"review_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow()

        # Get reviewer info: use custom name/avatar if provided, otherwise fallback to Firebase
        reviewer_name = review_data.reviewer_name or user.get(
            "name", user.get("email", "Anonymous")
        )
        reviewer_avatar = review_data.reviewer_avatar_url or user.get("picture")

        review_doc = {
            "review_id": review_id,
            "book_id": book_id,
            "reviewer_user_id": user_id,
            "reviewer_name": reviewer_name,  # Store in DB
            "reviewer_avatar_url": reviewer_avatar,  # Store in DB
            "text": review_data.text,
            "image_url": review_data.image_url,
            "rating": review_data.rating,
            "likes_count": 0,
            "created_at": now,
            "updated_at": now,
        }

        db.book_reviews.insert_one(review_doc)

        # Update book's average rating and review count
        all_reviews = list(db.book_reviews.find({"book_id": book_id}))
        average_rating = sum(r.get("rating", 0) for r in all_reviews) / len(all_reviews)
        
        db.online_books.update_one(
            {"book_id": book_id},
            {
                "$set": {
                    "community_config.average_rating": round(average_rating, 1),
                    "community_config.rating_count": len(all_reviews),
                }
            },
        )

        logger.info(f"✅ User {user_id} created review for book {book_id}")

        return BookReviewResponse(
            review_id=review_id,
            book_id=book_id,
            reviewer_user_id=user_id,
            reviewer_name=reviewer_name,
            reviewer_avatar_url=reviewer_avatar,
            text=review_data.text,
            image_url=review_data.image_url,
            rating=review_data.rating,
            likes_count=0,
            is_liked_by_current_user=False,
            created_at=now,
            updated_at=now,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to create book review: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create review",
        )


@router.post(
    "/{book_id}/reviews/image/presigned-url",
    summary="Generate presigned URL for review image upload",
)
async def get_review_image_presigned_url(
    book_id: str,
    filename: str = Query(..., description="Image filename (e.g., screenshot.jpg)"),
    content_type: str = Query(..., description="MIME type (e.g., image/jpeg)"),
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Generate presigned URL for review image upload**

    Upload image to include in book review (optional).

    **Supported Image Types:**
    - JPEG (image/jpeg)
    - PNG (image/png)
    - WebP (image/webp)
    - AVIF (image/avif)

    **Flow:**
    1. Call this endpoint to get presigned URL
    2. Upload image directly to presigned URL (PUT request)
    3. Use the file_url in review creation

    **Image Constraints:**
    - Max file size: 5MB
    - Recommended: Screenshots, examples, or relevant images

    **Returns:**
    ```json
    {
        "success": true,
        "presigned_url": "https://...",
        "file_url": "https://cdn.wordai.pro/book-review-images/...",
        "expires_in": 300
    }
    ```
    """
    from src.services.r2_storage_service import get_r2_service

    user_id = user["uid"]

    logger.info(
        f"📸 Generating presigned URL for book review image: {filename} - User: {user_id}"
    )

    try:
        # Validate content type
        allowed_types = ["image/jpeg", "image/png", "image/webp", "image/avif"]
        if content_type not in allowed_types:
            logger.warning(f"❌ Invalid content type '{content_type}' for review image")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid content type '{content_type}'. Allowed types: {', '.join(allowed_types)}",
            )

        # Validate filename extension
        valid_extensions = [".jpg", ".jpeg", ".png", ".webp", ".avif"]
        if not any(filename.lower().endswith(ext) for ext in valid_extensions):
            logger.warning(
                f"❌ Invalid filename extension '{filename}' for review image"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid filename extension. File must end with: {', '.join(valid_extensions)}",
            )

        # Get R2 service
        r2_service = get_r2_service()

        # Generate presigned URL for review images folder
        result = r2_service.generate_presigned_upload_url(
            filename=filename,
            content_type=content_type,
            folder="book-review-images",  # Separate folder for book review images
        )

        logger.info(
            f"✅ Generated presigned URL for book review image: {result['file_url']}"
        )

        return {
            "success": True,
            "presigned_url": result["presigned_url"],
            "file_url": result["file_url"],
            "expires_in": result["expires_in"],
        }

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"❌ R2 configuration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Image upload service not configured properly: {str(e)}",
        )
    except Exception as e:
        logger.error(f"❌ Failed to generate presigned URL: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate presigned URL: {str(e)}",
        )


@router.get(
    "/{book_id}/reviews",
    response_model=BookReviewListResponse,
    summary="List book reviews (public)",
)
async def list_book_reviews(
    book_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    sort: str = Query("likes", description="Sort by: likes, newest, rating"),
    user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """
    **List reviews for a book**

    - Public endpoint (no authentication required)
    - If authenticated, includes is_liked_by_current_user
    - Sort by: likes (most liked), newest, rating (highest first)

    **Query Parameters:**
    - skip: Pagination offset (default: 0)
    - limit: Items per page (1-100, default: 20)
    - sort: Sort method (likes, newest, rating)

    **Returns:**
    ```json
    {
        "reviews": [...],
        "total": 42,
        "skip": 0,
        "limit": 20,
        "average_rating": 4.5,
        "total_reviews": 42
    }
    ```
    """
    try:
        # Check book exists
        book = db.online_books.find_one(
            {"book_id": book_id, "deleted_at": None}
        )
        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found",
            )

        # Determine sort order
        if sort == "likes":
            sort_field = [("likes_count", -1), ("created_at", -1)]
        elif sort == "rating":
            sort_field = [("rating", -1), ("created_at", -1)]
        else:  # newest
            sort_field = [("created_at", -1)]

        # Get reviews
        total = db.book_reviews.count_documents({"book_id": book_id})
        reviews_cursor = (
            db.book_reviews.find({"book_id": book_id})
            .sort(sort_field)
            .skip(skip)
            .limit(limit)
        )

        # Build response
        reviews = []
        user_id = user["uid"] if user else None
        user_likes = set()

        # Get user's likes if authenticated
        if user_id:
            likes = db.book_review_likes.find({"user_id": user_id})
            user_likes = {like["review_id"] for like in likes}

        for review_doc in reviews_cursor:
            # Get reviewer info from review document (stored during creation)
            reviewer_name = review_doc.get("reviewer_name", "Anonymous")
            reviewer_avatar = review_doc.get("reviewer_avatar_url")

            reviews.append(
                BookReviewResponse(
                    review_id=review_doc["review_id"],
                    book_id=review_doc["book_id"],
                    reviewer_user_id=review_doc["reviewer_user_id"],
                    reviewer_name=reviewer_name,
                    reviewer_avatar_url=reviewer_avatar,
                    text=review_doc["text"],
                    image_url=review_doc.get("image_url"),
                    rating=review_doc["rating"],
                    likes_count=review_doc.get("likes_count", 0),
                    is_liked_by_current_user=review_doc["review_id"] in user_likes,
                    created_at=review_doc["created_at"],
                    updated_at=review_doc["updated_at"],
                )
            )

        # Calculate average rating
        all_reviews = list(db.book_reviews.find({"book_id": book_id}))
        average_rating = (
            sum(r.get("rating", 0) for r in all_reviews) / len(all_reviews)
            if all_reviews
            else 0.0
        )

        logger.info(f"📚 Listed {len(reviews)} reviews for book {book_id}")

        return BookReviewListResponse(
            reviews=reviews,
            total=total,
            skip=skip,
            limit=limit,
            average_rating=round(average_rating, 1),
            total_reviews=total,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to list book reviews: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list reviews",
        )


@router.delete(
    "/{book_id}/reviews/{review_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete book review",
)
async def delete_book_review(
    book_id: str,
    review_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Delete a review**

    - Book owner can delete any review on their book
    - Review author can delete their own review

    **Authentication required**

    **Returns:**
    - 204: Review deleted successfully
    - 403: No permission to delete
    - 404: Review not found
    """
    try:
        user_id = user["uid"]

        # Get review
        review = db.book_reviews.find_one(
            {
                "review_id": review_id,
                "book_id": book_id,
            }
        )
        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review not found",
            )

        # Check permission
        book = db.online_books.find_one({"book_id": book_id})
        is_owner = book.get("user_id") == user_id
        is_reviewer = review["reviewer_user_id"] == user_id

        if not (is_owner or is_reviewer):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to delete this review",
            )

        # Delete review
        db.book_reviews.delete_one({"review_id": review_id})

        # Delete all likes for this review
        db.book_review_likes.delete_many({"review_id": review_id})

        # Update book's average rating and review count
        all_reviews = list(db.book_reviews.find({"book_id": book_id}))
        if all_reviews:
            average_rating = sum(r.get("rating", 0) for r in all_reviews) / len(all_reviews)
        else:
            average_rating = 0.0
        
        db.online_books.update_one(
            {"book_id": book_id},
            {
                "$set": {
                    "community_config.average_rating": round(average_rating, 1),
                    "community_config.rating_count": len(all_reviews),
                }
            },
        )

        logger.info(f"✅ Deleted review {review_id} by user {user_id}")

        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete book review: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete review",
        )


@router.post(
    "/{book_id}/reviews/{review_id}/like",
    status_code=status.HTTP_200_OK,
    summary="Like/unlike a review",
)
async def toggle_review_like(
    book_id: str,
    review_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Toggle like on a review**

    - If not liked → add like
    - If already liked → remove like
    - Each user can only like once per review

    **Authentication required**

    **Returns:**
    ```json
    {
        "success": true,
        "is_liked": true,
        "likes_count": 42
    }
    ```
    """
    try:
        user_id = user["uid"]

        # Check review exists
        review = db.book_reviews.find_one(
            {
                "review_id": review_id,
                "book_id": book_id,
            }
        )
        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review not found",
            )

        # Check if already liked
        existing_like = db.book_review_likes.find_one(
            {
                "review_id": review_id,
                "user_id": user_id,
            }
        )

        if existing_like:
            # Unlike
            db.book_review_likes.delete_one(
                {
                    "review_id": review_id,
                    "user_id": user_id,
                }
            )
            db.book_reviews.update_one(
                {"review_id": review_id},
                {"$inc": {"likes_count": -1}},
            )
            is_liked = False
            logger.info(f"👎 User {user_id} unliked review {review_id}")
        else:
            # Like
            db.book_review_likes.insert_one(
                {
                    "review_id": review_id,
                    "user_id": user_id,
                    "liked_at": datetime.utcnow(),
                }
            )
            db.book_reviews.update_one(
                {"review_id": review_id},
                {"$inc": {"likes_count": 1}},
            )
            is_liked = True
            logger.info(f"👍 User {user_id} liked review {review_id}")

        # Get updated likes count
        updated_review = db.book_reviews.find_one({"review_id": review_id})
        likes_count = updated_review.get("likes_count", 0)

        return {
            "success": True,
            "is_liked": is_liked,
            "likes_count": likes_count,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to toggle like: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to toggle like",
        )
