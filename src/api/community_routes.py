"""
Community Books Routes
Public endpoints for browsing community books
"""

from fastapi import APIRouter, Query, HTTPException, status
from typing import Optional, List, Dict, Any
from datetime import datetime
from src.database import db
from pydantic import BaseModel, Field

router = APIRouter(prefix="/community", tags=["Community Books"])


# ============================================================================
# RESPONSE MODELS
# ============================================================================


class CommunityBookItem(BaseModel):
    """Community book item"""

    book_id: str
    title: str
    slug: str
    cover_url: Optional[str] = None
    authors: List[str] = []  # List of author_ids
    author_names: List[str] = []  # Display names
    category: Optional[str] = None
    tags: List[str] = []
    total_views: int = 0
    average_rating: float = 0.0
    total_chapters: int = 0
    last_updated: Optional[datetime] = None


class FeaturedAuthorItem(BaseModel):
    """Featured author for homepage"""

    author_id: str
    name: str
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    total_books: int = 0
    total_reads: int = 0
    average_rating: float = 0.0
    total_followers: int = 0


class PopularTagItem(BaseModel):
    """Popular tag with book count"""

    tag: str
    books_count: int


class CommunityBooksResponse(BaseModel):
    """Community books list response"""

    books: List[CommunityBookItem]
    total: int
    skip: int
    limit: int


class FeaturedAuthorsResponse(BaseModel):
    """Featured authors response"""

    authors: List[FeaturedAuthorItem]
    total: int = 10


class PopularTagsResponse(BaseModel):
    """Popular tags response"""

    tags: List[PopularTagItem]
    total: int


# ============================================================================
# SEARCH & FILTER BOOKS
# ============================================================================


@router.get(
    "/books/search",
    response_model=CommunityBooksResponse,
    summary="Search and filter community books",
)
async def search_community_books(
    q: Optional[str] = Query(None, description="Search by title or author name"),
    category: Optional[str] = Query(None, description="Filter by category"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    sort_by: str = Query(
        "updated", description="Sort by: updated, views, rating, newest"
    ),
):
    """
    **Search and filter community books**

    - Search by book title or author name
    - Filter by category and tags
    - Sort by: updated (latest chapter), views, rating, newest

    **Public endpoint** - No authentication required
    """
    try:
        # Build base query
        query = {
            "community_config.is_public": True,
            "deleted_at": None,
        }

        # Search by title or author name
        if q:
            # Search in title or authors array
            query["$or"] = [
                {"title": {"$regex": q, "$options": "i"}},
                {"authors": {"$regex": q, "$options": "i"}},  # Search author_id
            ]

        # Filter by category
        if category:
            query["community_config.category"] = category

        # Filter by tags
        if tags:
            tag_list = [t.strip() for t in tags.split(",") if t.strip()]
            if tag_list:
                query["community_config.tags"] = {"$in": tag_list}

        # Determine sort
        sort_map = {
            "updated": ("community_config.last_chapter_updated_at", -1),
            "views": ("community_config.total_views", -1),
            "rating": ("community_config.average_rating", -1),
            "newest": ("community_config.published_at", -1),
        }
        sort_field, sort_order = sort_map.get(
            sort_by, ("community_config.last_chapter_updated_at", -1)
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

            # Get author names
            author_ids = book.get("authors", [])
            author_names = []
            for author_id in author_ids:
                author = db.book_authors.find_one({"author_id": author_id.lower()})
                if author:
                    author_names.append(author.get("name", author_id))
                else:
                    author_names.append(author_id)

            books.append(
                CommunityBookItem(
                    book_id=book["book_id"],
                    title=book["title"],
                    slug=book["slug"],
                    cover_url=book.get("cover_url"),
                    authors=author_ids,
                    author_names=author_names,
                    category=community_config.get("category"),
                    tags=community_config.get("tags", []),
                    total_views=community_config.get("total_views", 0),
                    average_rating=community_config.get("average_rating", 0.0),
                    total_chapters=community_config.get("total_chapters", 0),
                    last_updated=community_config.get("last_chapter_updated_at"),
                )
            )

        return CommunityBooksResponse(
            books=books,
            total=total,
            skip=skip,
            limit=limit,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search books: {str(e)}",
        )


# ============================================================================
# FEATURED AUTHORS
# ============================================================================


@router.get(
    "/authors/featured",
    response_model=FeaturedAuthorsResponse,
    summary="Get 10 featured authors for homepage",
)
async def get_featured_authors():
    """
    **Get 10 featured authors (horizontal slider)**

    Selection criteria:
    - 3 authors with highest total reads (sum of all book views)
    - 3 authors with best reviews (5-star reviews + high average rating)
    - 4 authors with highest-viewed books (top book views)

    **Public endpoint** - No authentication required
    """
    try:
        featured_authors = []
        used_author_ids = set()

        # 1. Top 3 by total reads (sum of all book views)
        pipeline_reads = [
            {
                "$match": {
                    "community_config.is_public": True,
                    "deleted_at": None,
                }
            },
            {"$unwind": "$authors"},
            {
                "$group": {
                    "_id": "$authors",
                    "total_reads": {"$sum": "$community_config.total_views"},
                }
            },
            {"$sort": {"total_reads": -1}},
            {"$limit": 3},
        ]
        top_reads = list(db.online_books.aggregate(pipeline_reads))

        for item in top_reads:
            author_id = item["_id"].lower()
            if author_id not in used_author_ids:
                author = db.book_authors.find_one({"author_id": author_id})
                if author:
                    # Get author stats
                    total_books = db.online_books.count_documents(
                        {
                            "authors": author_id,
                            "community_config.is_public": True,
                            "deleted_at": None,
                        }
                    )

                    # Get average rating from reviews
                    reviews = list(db.author_reviews.find({"author_id": author_id}))
                    avg_rating = (
                        sum(r.get("rating", 0) for r in reviews) / len(reviews)
                        if reviews
                        else 0.0
                    )

                    # Get followers
                    total_followers = db.author_follows.count_documents(
                        {"author_id": author_id}
                    )

                    featured_authors.append(
                        FeaturedAuthorItem(
                            author_id=author["author_id"],
                            name=author.get("name", author_id),
                            avatar_url=author.get("avatar_url"),
                            bio=author.get("bio"),
                            total_books=total_books,
                            total_reads=item["total_reads"],
                            average_rating=round(avg_rating, 1),
                            total_followers=total_followers,
                        )
                    )
                    used_author_ids.add(author_id)

        # 2. Top 3 by best reviews (5-star reviews + high average)
        pipeline_reviews = [
            {"$match": {"rating": 5}},  # Only 5-star reviews
            {
                "$group": {
                    "_id": "$author_id",
                    "five_star_count": {"$sum": 1},
                }
            },
            {"$sort": {"five_star_count": -1}},
            {"$limit": 10},  # Get more to filter out duplicates
        ]
        top_reviews = list(db.author_reviews.aggregate(pipeline_reviews))

        review_authors_added = 0
        for item in top_reviews:
            if review_authors_added >= 3:
                break

            author_id = item["_id"].lower()
            if author_id not in used_author_ids:
                author = db.book_authors.find_one({"author_id": author_id})
                if author:
                    # Get author stats
                    total_books = db.online_books.count_documents(
                        {
                            "authors": author_id,
                            "community_config.is_public": True,
                            "deleted_at": None,
                        }
                    )

                    # Get total reads
                    pipeline_reads = [
                        {
                            "$match": {
                                "authors": author_id,
                                "community_config.is_public": True,
                                "deleted_at": None,
                            }
                        },
                        {
                            "$group": {
                                "_id": None,
                                "total_reads": {
                                    "$sum": "$community_config.total_views"
                                },
                            }
                        },
                    ]
                    reads_result = list(db.online_books.aggregate(pipeline_reads))
                    total_reads = reads_result[0]["total_reads"] if reads_result else 0

                    # Get average rating
                    all_reviews = list(db.author_reviews.find({"author_id": author_id}))
                    avg_rating = (
                        sum(r.get("rating", 0) for r in all_reviews) / len(all_reviews)
                        if all_reviews
                        else 0.0
                    )

                    # Get followers
                    total_followers = db.author_follows.count_documents(
                        {"author_id": author_id}
                    )

                    featured_authors.append(
                        FeaturedAuthorItem(
                            author_id=author["author_id"],
                            name=author.get("name", author_id),
                            avatar_url=author.get("avatar_url"),
                            bio=author.get("bio"),
                            total_books=total_books,
                            total_reads=total_reads,
                            average_rating=round(avg_rating, 1),
                            total_followers=total_followers,
                        )
                    )
                    used_author_ids.add(author_id)
                    review_authors_added += 1

        # 3. Top 4 from highest-viewed books
        top_books = (
            db.online_books.find(
                {
                    "community_config.is_public": True,
                    "deleted_at": None,
                }
            )
            .sort("community_config.total_views", -1)
            .limit(20)  # Get more to filter out duplicates
        )

        view_authors_added = 0
        for book in top_books:
            if view_authors_added >= 4:
                break

            author_ids = book.get("authors", [])
            for author_id in author_ids:
                if view_authors_added >= 4:
                    break

                author_id = author_id.lower()
                if author_id not in used_author_ids:
                    author = db.book_authors.find_one({"author_id": author_id})
                    if author:
                        # Get author stats
                        total_books = db.online_books.count_documents(
                            {
                                "authors": author_id,
                                "community_config.is_public": True,
                                "deleted_at": None,
                            }
                        )

                        # Get total reads
                        pipeline_reads = [
                            {
                                "$match": {
                                    "authors": author_id,
                                    "community_config.is_public": True,
                                    "deleted_at": None,
                                }
                            },
                            {
                                "$group": {
                                    "_id": None,
                                    "total_reads": {
                                        "$sum": "$community_config.total_views"
                                    },
                                }
                            },
                        ]
                        reads_result = list(db.online_books.aggregate(pipeline_reads))
                        total_reads = (
                            reads_result[0]["total_reads"] if reads_result else 0
                        )

                        # Get average rating
                        reviews = list(db.author_reviews.find({"author_id": author_id}))
                        avg_rating = (
                            sum(r.get("rating", 0) for r in reviews) / len(reviews)
                            if reviews
                            else 0.0
                        )

                        # Get followers
                        total_followers = db.author_follows.count_documents(
                            {"author_id": author_id}
                        )

                        featured_authors.append(
                            FeaturedAuthorItem(
                                author_id=author["author_id"],
                                name=author.get("name", author_id),
                                avatar_url=author.get("avatar_url"),
                                bio=author.get("bio"),
                                total_books=total_books,
                                total_reads=total_reads,
                                average_rating=round(avg_rating, 1),
                                total_followers=total_followers,
                            )
                        )
                        used_author_ids.add(author_id)
                        view_authors_added += 1

        return FeaturedAuthorsResponse(
            authors=featured_authors,
            total=len(featured_authors),
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get featured authors: {str(e)}",
        )


# ============================================================================
# LATEST BOOKS
# ============================================================================


@router.get(
    "/books/latest",
    response_model=CommunityBooksResponse,
    summary="Get latest updated books (2x10 grid)",
)
async def get_latest_books(
    category: Optional[str] = Query(None, description="Filter by category"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """
    **Get latest updated books (sorted by latest chapter update)**

    Default: 20 books for 2-column x 10-row grid
    Can filter by category and tags

    **Public endpoint** - No authentication required
    """
    try:
        # Build query
        query = {
            "community_config.is_public": True,
            "deleted_at": None,
        }

        # Filter by category
        if category:
            query["community_config.category"] = category

        # Filter by tags
        if tags:
            tag_list = [t.strip() for t in tags.split(",") if t.strip()]
            if tag_list:
                query["community_config.tags"] = {"$in": tag_list}

        # Count total
        total = db.online_books.count_documents(query)

        # Get books sorted by last chapter update
        books_cursor = (
            db.online_books.find(query)
            .sort("community_config.last_chapter_updated_at", -1)
            .skip(skip)
            .limit(limit)
        )

        books = []
        for book in books_cursor:
            community_config = book.get("community_config", {})

            # Get author names
            author_ids = book.get("authors", [])
            author_names = []
            for author_id in author_ids:
                author = db.book_authors.find_one({"author_id": author_id.lower()})
                if author:
                    author_names.append(author.get("name", author_id))
                else:
                    author_names.append(author_id)

            books.append(
                CommunityBookItem(
                    book_id=book["book_id"],
                    title=book["title"],
                    slug=book["slug"],
                    cover_url=book.get("cover_url"),
                    authors=author_ids,
                    author_names=author_names,
                    category=community_config.get("category"),
                    tags=community_config.get("tags", []),
                    total_views=community_config.get("total_views", 0),
                    average_rating=community_config.get("average_rating", 0.0),
                    total_chapters=community_config.get("total_chapters", 0),
                    last_updated=community_config.get("last_chapter_updated_at"),
                )
            )

        return CommunityBooksResponse(
            books=books,
            total=total,
            skip=skip,
            limit=limit,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get latest books: {str(e)}",
        )


# ============================================================================
# TOP BOOKS
# ============================================================================


@router.get(
    "/books/top",
    response_model=CommunityBooksResponse,
    summary="Get top 10 most viewed books",
)
async def get_top_books(
    category: Optional[str] = Query(None, description="Filter by category"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    limit: int = Query(10, ge=1, le=50),
):
    """
    **Get top most viewed books**

    Default: 10 books sorted by total views
    Can filter by category and tags

    **Public endpoint** - No authentication required
    """
    try:
        # Build query
        query = {
            "community_config.is_public": True,
            "deleted_at": None,
        }

        # Filter by category
        if category:
            query["community_config.category"] = category

        # Filter by tags
        if tags:
            tag_list = [t.strip() for t in tags.split(",") if t.strip()]
            if tag_list:
                query["community_config.tags"] = {"$in": tag_list}

        # Count total
        total = db.online_books.count_documents(query)

        # Get top books by views
        books_cursor = (
            db.online_books.find(query)
            .sort("community_config.total_views", -1)
            .limit(limit)
        )

        books = []
        for book in books_cursor:
            community_config = book.get("community_config", {})

            # Get author names
            author_ids = book.get("authors", [])
            author_names = []
            for author_id in author_ids:
                author = db.book_authors.find_one({"author_id": author_id.lower()})
                if author:
                    author_names.append(author.get("name", author_id))
                else:
                    author_names.append(author_id)

            books.append(
                CommunityBookItem(
                    book_id=book["book_id"],
                    title=book["title"],
                    slug=book["slug"],
                    cover_url=book.get("cover_url"),
                    authors=author_ids,
                    author_names=author_names,
                    category=community_config.get("category"),
                    tags=community_config.get("tags", []),
                    total_views=community_config.get("total_views", 0),
                    average_rating=community_config.get("average_rating", 0.0),
                    total_chapters=community_config.get("total_chapters", 0),
                    last_updated=community_config.get("last_chapter_updated_at"),
                )
            )

        return CommunityBooksResponse(
            books=books,
            total=len(books),
            skip=0,
            limit=limit,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get top books: {str(e)}",
        )


# ============================================================================
# POPULAR TAGS
# ============================================================================


@router.get(
    "/tags/popular",
    response_model=PopularTagsResponse,
    summary="Get 25 most popular tags",
)
async def get_popular_tags():
    """
    **Get 25 most popular tags (sorted by book count)**

    Returns tags with the most books

    **Public endpoint** - No authentication required
    """
    try:
        # Aggregate tags from all public books
        pipeline = [
            {
                "$match": {
                    "community_config.is_public": True,
                    "deleted_at": None,
                }
            },
            {"$unwind": "$community_config.tags"},
            {
                "$group": {
                    "_id": "$community_config.tags",
                    "books_count": {"$sum": 1},
                }
            },
            {"$sort": {"books_count": -1}},
            {"$limit": 25},
        ]

        results = list(db.online_books.aggregate(pipeline))

        tags = [
            PopularTagItem(
                tag=item["_id"],
                books_count=item["books_count"],
            )
            for item in results
        ]

        return PopularTagsResponse(
            tags=tags,
            total=len(tags),
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get popular tags: {str(e)}",
        )
