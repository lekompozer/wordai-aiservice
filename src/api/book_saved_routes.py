"""
Saved Books Routes - User's bookmarked/saved books

Endpoints:
- POST /saved-books - Save a book
- GET /saved-books - List my saved books (with filters)
- DELETE /saved-books/{book_id} - Remove saved book
"""

from fastapi import APIRouter, HTTPException, Depends, Query, status
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

from src.database.db_manager import DBManager
from src.middleware.firebase_auth import get_current_user
from src.models.saved_book_models import (
    SaveBookRequest,
    SaveBookResponse,
    SavedBookItem,
    SavedBooksResponse,
    UnsaveBookResponse,
)

router = APIRouter(prefix="/saved-books", tags=["Saved Books"])
logger = logging.getLogger(__name__)

# Initialize DB
db_manager = DBManager()
db = db_manager.db


@router.post("", response_model=SaveBookResponse, status_code=status.HTTP_201_CREATED)
async def save_book(
    request: SaveBookRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Save/bookmark a book for later reading

    **Authentication:** Required

    **Request Body:**
    - book_id: Book ID to save

    **Returns:**
    - 201: Book saved successfully
    - 404: Book not found or not published
    - 409: Book already saved
    """
    try:
        user_id = current_user["uid"]
        book_id = request.book_id

        logger.info(f"💾 User {user_id} saving book {book_id}")

        # 1. Check if book exists and is published to community
        book = db.online_books.find_one(
            {
                "book_id": book_id,
                "community_config.is_public": True,
            }
        )

        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found or not available in community",
            )

        # 2. Check if already saved
        existing = db.saved_books.find_one(
            {"user_id": user_id, "book_id": book_id, "deleted_at": None}
        )

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Book already saved",
            )

        # 3. Save the book
        saved_at = datetime.utcnow()
        save_doc = {
            "user_id": user_id,
            "book_id": book_id,
            "saved_at": saved_at,
            "deleted_at": None,
        }

        db.saved_books.insert_one(save_doc)

        # 4. Increment book's save count
        db.online_books.update_one(
            {"book_id": book_id},
            {"$inc": {"community_config.total_saves": 1}},
        )

        logger.info(f"✅ User {user_id} saved book {book_id}")

        return SaveBookResponse(
            success=True,
            message=f"Book '{book['title']}' saved successfully",
            book_id=book_id,
            saved_at=saved_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to save book: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save book: {str(e)}",
        )


@router.get("", response_model=SavedBooksResponse)
async def list_saved_books(
    category: Optional[str] = Query(None, description="Filter by category"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    List user's saved books with optional filters

    **Authentication:** Required

    **Query Parameters:**
    - category: Filter by book category
    - tags: Filter by tags (comma-separated, e.g., "python,ai,tutorial")
    - skip: Pagination offset (default: 0)
    - limit: Items per page (default: 20, max: 100)

    **Returns:**
    - 200: List of saved books with metadata
    """
    try:
        user_id = current_user["uid"]

        logger.info(
            f"📚 User {user_id} listing saved books (category={category}, tags={tags})"
        )

        # 1. Get user's saved book IDs
        saved_docs = list(
            db.saved_books.find(
                {"user_id": user_id, "deleted_at": None},
                {"book_id": 1, "saved_at": 1},
            ).sort("saved_at", -1)
        )

        if not saved_docs:
            return SavedBooksResponse(books=[], total=0, skip=skip, limit=limit)

        book_ids = [doc["book_id"] for doc in saved_docs]
        saved_at_map = {doc["book_id"]: doc["saved_at"] for doc in saved_docs}

        # 2. Build book query with filters
        book_query = {
            "book_id": {"$in": book_ids},
            "community_config.is_public": True,
            "is_published": True,
            "deleted_at": None,
        }

        # Apply category filter
        if category:
            book_query["community_config.category"] = category

        # Apply tags filter
        if tags:
            tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
            if tag_list:
                book_query["community_config.tags"] = {"$in": tag_list}

        # 3. Get total count
        total = db.online_books.count_documents(book_query)

        # 4. Get books with pagination
        books_cursor = db.online_books.find(book_query).skip(skip).limit(limit)

        # 5. Build response
        saved_books = []
        for book in books_cursor:
            # Get author info
            author_id = None
            author_name = None
            author_avatar = None

            if "author_id" in book:
                author = db.book_authors.find_one({"author_id": book["author_id"]})
                if author:
                    author_id = author["author_id"]
                    author_name = author.get("name")
                    author_avatar = author.get("avatar_url")

            saved_books.append(
                SavedBookItem(
                    book_id=book["book_id"],
                    title=book["title"],
                    slug=book["slug"],
                    cover_image_url=book.get("cover_image_url"),
                    category=book.get("community_config", {}).get("category"),
                    tags=book.get("community_config", {}).get("tags", []),
                    author_id=author_id,
                    author_name=author_name,
                    author_avatar=author_avatar,
                    total_views=book.get("community_config", {}).get("total_views", 0),
                    total_saves=book.get("community_config", {}).get("total_saves", 0),
                    average_rating=book.get("community_config", {}).get(
                        "average_rating", 0.0
                    ),
                    saved_at=saved_at_map[book["book_id"]],
                    published_at=book.get("community_config", {}).get("published_at"),
                )
            )

        # Build filters info
        filters = {}
        if category:
            filters["category"] = category
        if tags:
            filters["tags"] = tag_list

        logger.info(f"✅ Returning {len(saved_books)} saved books (total: {total})")

        return SavedBooksResponse(
            books=saved_books,
            total=total,
            skip=skip,
            limit=limit,
            filters=filters,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to list saved books: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list saved books: {str(e)}",
        )


@router.delete("/{book_id}", response_model=UnsaveBookResponse)
async def unsave_book(
    book_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Remove a book from saved list

    **Authentication:** Required

    **Path Parameters:**
    - book_id: Book ID to remove from saved list

    **Returns:**
    - 200: Book removed from saved list
    - 404: Book not in saved list
    """
    try:
        user_id = current_user["uid"]

        logger.info(f"🗑️ User {user_id} removing saved book {book_id}")

        # 1. Check if book is saved
        saved_doc = db.saved_books.find_one(
            {"user_id": user_id, "book_id": book_id, "deleted_at": None}
        )

        if not saved_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found in saved list",
            )

        # 2. Soft delete the saved record
        db.saved_books.update_one(
            {"user_id": user_id, "book_id": book_id},
            {"$set": {"deleted_at": datetime.utcnow()}},
        )

        # 3. Decrement book's save count
        db.online_books.update_one(
            {"book_id": book_id},
            {"$inc": {"community_config.total_saves": -1}},
        )

        logger.info(f"✅ User {user_id} removed saved book {book_id}")

        return UnsaveBookResponse(
            success=True,
            message="Book removed from saved list",
            book_id=book_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to remove saved book: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove saved book: {str(e)}",
        )


@router.get("/check/{book_id}")
async def check_book_saved(
    book_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Check if user has saved a book

    **Authentication:** Required

    **Path Parameters:**
    - book_id: Book ID to check

    **Returns:**
    - 200: Check result with is_saved status
    """
    try:
        user_id = current_user["uid"]

        logger.info(f"🔍 User {user_id} checking if book {book_id} is saved")

        # Check if book is saved
        saved_doc = db.saved_books.find_one(
            {"user_id": user_id, "book_id": book_id, "deleted_at": None}
        )

        is_saved = saved_doc is not None
        saved_at = saved_doc.get("saved_at") if saved_doc else None

        logger.info(f"✅ Book {book_id} saved status: {is_saved}")

        return {
            "book_id": book_id,
            "is_saved": is_saved,
            "saved_at": saved_at,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to check saved status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check saved status: {str(e)}",
        )
