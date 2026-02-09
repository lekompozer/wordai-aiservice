"""
Book Categories API Routes
Public endpoints for browsing book categories and books by category
"""

from fastapi import APIRouter, Query, HTTPException, status, Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from src.database.db_manager import DBManager
from src.cache.redis_client import get_cache_client
from src.constants.book_categories import (
    PARENT_CATEGORIES,
    CHILD_CATEGORIES,
    get_categories_tree,
    get_parent_category,
)
from pydantic import BaseModel, Field

router = APIRouter(prefix="/book-categories", tags=["Book Categories"])

# Initialize DB connection
db_manager = DBManager()
db = db_manager.db

# Initialize cache client
cache_client = get_cache_client()


# ============================================================================
# RESPONSE MODELS
# ============================================================================


class ChildCategoryItem(BaseModel):
    """Child category with book count"""

    name: str
    slug: str
    parent: str
    books_count: int = 0


class ParentCategoryItem(BaseModel):
    """Parent category with children"""

    id: str
    name: str
    name_vi: str
    icon: str
    order: int
    children: List[ChildCategoryItem]
    total_books: int = 0


class CategoriesResponse(BaseModel):
    """All categories tree response"""

    categories: List[ParentCategoryItem]
    total_parents: int
    total_children: int
    total_books: int


class BookItem(BaseModel):
    """Book item in category"""

    book_id: str
    title: str
    slug: str
    description: Optional[str] = None
    cover_url: Optional[str] = None
    authors: List[str] = []
    author_names: List[str] = []
    child_category: str
    parent_category: str
    tags: List[str] = []
    difficulty_level: Optional[str] = None
    total_views: int = 0
    total_chapters: int = 0
    total_purchases: int = 0
    average_rating: float = 0.0
    rating_count: int = 0
    access_points: Dict[str, int] = {}  # one_time, forever
    published_at: Optional[datetime] = None


class CategoryBooksResponse(BaseModel):
    """Books in a category"""

    books: List[BookItem]
    category_name: str
    category_type: str  # "parent" or "child"
    total: int
    skip: int
    limit: int


# ============================================================================
# ENDPOINTS
# ============================================================================


@router.get(
    "/",
    response_model=CategoriesResponse,
    summary="Get all book categories (parent + children)",
)
async def get_all_categories():
    """
    **Get full category tree with book counts**

    Returns:
    - 11 parent categories
    - 33 child categories
    - Book count for each category

    **Public endpoint** - No authentication required
    **Cached:** 10 minutes (Redis)
    """
    try:
        # Try cache first
        cache_key = "categories:tree:all"
        cached_data = await cache_client.get(cache_key)

        if cached_data:
            # Return cached data as Pydantic models
            categories = [
                ParentCategoryItem(**cat) for cat in cached_data["categories"]
            ]
            return CategoriesResponse(
                categories=categories,
                total_parents=cached_data["total_parents"],
                total_children=cached_data["total_children"],
                total_books=cached_data["total_books"],
            )

        # Cache miss - compute from database
        tree = get_categories_tree()

        categories = []
        total_books_all = 0

        for parent_id, data in tree.items():
            parent_info = data["info"]
            children_data = data["children"]

            # Count books for each child category
            children_with_counts = []
            parent_total_books = 0

            for child in children_data:
                # Count books in this child category
                count = db.online_books.count_documents(
                    {
                        "community_config.category": child["name"],
                        "community_config.is_public": True,
                        "deleted_at": None,
                    }
                )

                children_with_counts.append(
                    ChildCategoryItem(
                        name=child["name"],
                        slug=child["slug"],
                        parent=child["parent"],
                        books_count=count,
                    )
                )

                parent_total_books += count

            total_books_all += parent_total_books

            categories.append(
                ParentCategoryItem(
                    id=parent_info["id"],
                    name=parent_info["name"],
                    name_vi=parent_info["name_vi"],
                    icon=parent_info["icon"],
                    order=parent_info["order"],
                    children=children_with_counts,
                    total_books=parent_total_books,
                )
            )

        # Sort by order
        categories.sort(key=lambda x: x.order)

        result = CategoriesResponse(
            categories=categories,
            total_parents=len(PARENT_CATEGORIES),
            total_children=len(CHILD_CATEGORIES),
            total_books=total_books_all,
        )

        # Cache for 15 minutes
        cache_data = {
            "categories": [cat.dict() for cat in categories],
            "total_parents": result.total_parents,
            "total_children": result.total_children,
            "total_books": result.total_books,
        }
        await cache_client.set(cache_key, cache_data, ttl=900)

        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get categories: {str(e)}",
        )


@router.get(
    "/parent/{parent_id}",
    response_model=CategoryBooksResponse,
    summary="Get books by parent category",
)
async def get_books_by_parent_category(
    parent_id: str = Path(..., description="Parent category ID (e.g. 'business')"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    sort_by: str = Query("newest", description="Sort by: newest, views, rating"),
):
    """
    **Get all books in a parent category**

    Includes all child categories under this parent.

    Example: `parent_id=business` returns all books in:
    - Kinh Tế - Quản Lý
    - Marketing - Bán hàng
    - Tâm Lý - Kỹ Năng Sống

    **Public endpoint** - No authentication required
    """
    try:
        # Find parent category
        parent = next(
            (cat for cat in PARENT_CATEGORIES if cat["id"] == parent_id), None
        )
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Parent category '{parent_id}' not found",
            )

        # Get all child categories under this parent
        child_names = [
            child["name"] for child in CHILD_CATEGORIES if child["parent"] == parent_id
        ]

        # Build query
        query = {
            "community_config.category": {"$in": child_names},
            "community_config.is_public": True,
            "deleted_at": None,
        }

        # Sort
        sort_map = {
            "newest": ("community_config.published_at", -1),
            "views": ("community_config.total_views", -1),
            "rating": ("community_config.average_rating", -1),
        }
        sort_field, sort_order = sort_map.get(
            sort_by, ("community_config.published_at", -1)
        )

        # Count total
        total = db.online_books.count_documents(query)

        # Get books
        books_cursor = (
            db.online_books.find(query)
            .sort(sort_field, sort_order)
            .skip(skip)
            .limit(limit)
        )

        books = []
        for book in books_cursor:
            community_config = book.get("community_config", {})
            access_config = book.get("access_config", {})

            # Get author names
            author_ids = book.get("authors", [])
            author_names = []
            for author_id in author_ids:
                author = db.book_authors.find_one({"author_id": author_id.lower()})
                if author:
                    author_names.append(author.get("name", author_id))
                else:
                    author_names.append(author_id)

            # Count chapters
            chapter_count = db.book_chapters.count_documents(
                {"book_id": book["book_id"], "deleted_at": None}
            )

            books.append(
                BookItem(
                    book_id=book["book_id"],
                    title=book["title"],
                    slug=book["slug"],
                    description=book.get("description"),
                    cover_url=community_config.get("cover_image_url")
                    or book.get("cover_image_url"),
                    authors=author_ids,
                    author_names=author_names,
                    child_category=community_config.get("category", "Khác"),
                    parent_category=community_config.get("parent_category", "other"),
                    tags=community_config.get("tags", []),
                    difficulty_level=community_config.get("difficulty_level"),
                    total_views=community_config.get("total_views", 0),
                    total_chapters=chapter_count,
                    total_purchases=community_config.get("total_purchases", 0),
                    average_rating=community_config.get("average_rating", 0.0),
                    rating_count=community_config.get("rating_count", 0),
                    access_points={
                        "one_time": access_config.get("one_time_view_points", 0),
                        "forever": access_config.get("forever_view_points", 0),
                    },
                    published_at=community_config.get("published_at"),
                )
            )

        return CategoryBooksResponse(
            books=books,
            category_name=parent["name_vi"],
            category_type="parent",
            total=total,
            skip=skip,
            limit=limit,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get books: {str(e)}",
        )


@router.get(
    "/parent/{parent_id}/top",
    response_model=CategoryBooksResponse,
    summary="Get top 5 books by parent category (CACHED)",
)
async def get_top_books_by_parent_category(
    parent_id: str = Path(..., description="Parent category ID (e.g. 'business')"),
):
    """
    **Get TOP 5 books in a parent category**

    Returns most viewed books across all child categories.

    **CACHED:** 30 minutes TTL for performance.

    **Public endpoint** - No authentication required
    """
    try:
        # Check cache first
        cache_key = f"books:top:category:{parent_id}"
        cached = await cache_client.get(cache_key)
        if cached:
            return CategoryBooksResponse(**cached)

        # Find parent category
        parent = next(
            (cat for cat in PARENT_CATEGORIES if cat["id"] == parent_id), None
        )
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Parent category '{parent_id}' not found",
            )

        # Get all child categories under this parent
        child_names = [
            child["name"] for child in CHILD_CATEGORIES if child["parent"] == parent_id
        ]

        # Build query
        query = {
            "community_config.category": {"$in": child_names},
            "community_config.is_public": True,
            "deleted_at": None,
        }

        # Get top 5 by views
        books_cursor = (
            db.online_books.find(query)
            .sort("community_config.total_views", -1)
            .limit(5)
        )

        books = []
        for book in books_cursor:
            community_config = book.get("community_config", {})
            access_config = book.get("access_config", {})

            # Get author names
            author_ids = book.get("authors", [])
            author_names = []
            for author_id in author_ids:
                author = db.book_authors.find_one({"author_id": author_id.lower()})
                if author:
                    author_names.append(author.get("name", author_id))
                else:
                    author_names.append(author_id)

            # Count chapters
            chapter_count = db.book_chapters.count_documents(
                {"book_id": book["book_id"], "deleted_at": None}
            )

            books.append(
                BookItem(
                    book_id=book["book_id"],
                    title=book["title"],
                    slug=book["slug"],
                    description=book.get("description"),
                    cover_url=community_config.get("cover_image_url")
                    or book.get("cover_image_url"),
                    authors=author_ids,
                    author_names=author_names,
                    child_category=community_config.get("category", "Khác"),
                    parent_category=community_config.get("parent_category", "other"),
                    tags=community_config.get("tags", []),
                    difficulty_level=community_config.get("difficulty_level"),
                    total_views=community_config.get("total_views", 0),
                    total_chapters=chapter_count,
                    total_purchases=community_config.get("total_purchases", 0),
                    average_rating=community_config.get("average_rating", 0.0),
                    rating_count=community_config.get("rating_count", 0),
                    access_points={
                        "one_time": access_config.get("one_time_view_points", 0),
                        "forever": access_config.get("forever_view_points", 0),
                    },
                    published_at=community_config.get("published_at"),
                )
            )

        result = CategoryBooksResponse(
            books=books,
            category_name=parent["name_vi"],
            category_type="parent",
            total=len(books),
            skip=0,
            limit=5,
        )

        # Cache for 30 minutes
        cache_data = result.dict()
        await cache_client.set(cache_key, cache_data, ttl=1800)

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get top books: {str(e)}",
        )


@router.get(
    "/child/{child_slug}",
    response_model=CategoryBooksResponse,
    summary="Get books by child category",
)
async def get_books_by_child_category(
    child_slug: str = Path(
        ..., description="Child category slug (e.g. 'kinh-te-quan-ly')"
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    sort_by: str = Query("newest", description="Sort by: newest, views, rating"),
):
    """
    **Get all books in a child category**

    Example: `child_slug=kinh-te-quan-ly` returns books in "Kinh Tế - Quản Lý"

    **Public endpoint** - No authentication required
    """
    try:
        # Find child category
        child = next(
            (cat for cat in CHILD_CATEGORIES if cat["slug"] == child_slug), None
        )
        if not child:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Child category '{child_slug}' not found",
            )

        # Build query
        query = {
            "community_config.category": child["name"],
            "community_config.is_public": True,
            "deleted_at": None,
        }

        # Sort
        sort_map = {
            "newest": ("community_config.published_at", -1),
            "views": ("community_config.total_views", -1),
            "rating": ("community_config.average_rating", -1),
        }
        sort_field, sort_order = sort_map.get(
            sort_by, ("community_config.published_at", -1)
        )

        # Count total
        total = db.online_books.count_documents(query)

        # Get books
        books_cursor = (
            db.online_books.find(query)
            .sort(sort_field, sort_order)
            .skip(skip)
            .limit(limit)
        )

        books = []
        for book in books_cursor:
            community_config = book.get("community_config", {})
            access_config = book.get("access_config", {})

            # Get author names
            author_ids = book.get("authors", [])
            author_names = []
            for author_id in author_ids:
                author = db.book_authors.find_one({"author_id": author_id.lower()})
                if author:
                    author_names.append(author.get("name", author_id))
                else:
                    author_names.append(author_id)

            # Count chapters
            chapter_count = db.book_chapters.count_documents(
                {"book_id": book["book_id"], "deleted_at": None}
            )

            books.append(
                BookItem(
                    book_id=book["book_id"],
                    title=book["title"],
                    slug=book["slug"],
                    description=book.get("description"),
                    cover_url=community_config.get("cover_image_url")
                    or book.get("cover_image_url"),
                    authors=author_ids,
                    author_names=author_names,
                    child_category=child["name"],
                    parent_category=child["parent"],
                    tags=community_config.get("tags", []),
                    difficulty_level=community_config.get("difficulty_level"),
                    total_views=community_config.get("total_views", 0),
                    total_chapters=chapter_count,
                    total_purchases=community_config.get("total_purchases", 0),
                    average_rating=community_config.get("average_rating", 0.0),
                    rating_count=community_config.get("rating_count", 0),
                    access_points={
                        "one_time": access_config.get("one_time_view_points", 0),
                        "forever": access_config.get("forever_view_points", 0),
                    },
                    published_at=community_config.get("published_at"),
                )
            )

        return CategoryBooksResponse(
            books=books,
            category_name=child["name"],
            category_type="child",
            total=total,
            skip=skip,
            limit=limit,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get books: {str(e)}",
        )
