"""
Community Books Routes
Public endpoints for browsing community books
"""

import logging
from fastapi import APIRouter, Query, HTTPException, status
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from src.database.db_manager import DBManager
from src.middleware.query_protection import protect_query
from src.cache.redis_client import get_cache_client
from pydantic import BaseModel, Field

router = APIRouter(prefix="/community", tags=["Community Books"])

logger = logging.getLogger("chatbot")

# Initialize DB connection
db_manager = DBManager()
db = db_manager.db

# Initialize cache client
cache_client = get_cache_client()


# ============================================================================
# RESPONSE MODELS
# ============================================================================


class RecentChapterItem(BaseModel):
    """Recent chapter summary"""

    chapter_id: str
    title: str
    updated_at: datetime


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
    recent_chapters: List[RecentChapterItem] = []  # 2 latest chapters


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


class FeaturedBookItem(BaseModel):
    """Featured book with full details"""

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
    total_purchases: int = 0  # Total purchases (all types)
    published_at: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    recent_chapters: List[RecentChapterItem] = []  # 2 latest chapters


class FeaturedBooksResponse(BaseModel):
    """Featured books response (week)"""

    books: List[FeaturedBookItem]
    total: int


class TrendingBooksResponse(BaseModel):
    """Trending books response (today)"""

    books: List[FeaturedBookItem]
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

            # Get 2 most recent chapters
            recent_chapters = []
            chapters_cursor = (
                db.book_chapters.find({"book_id": book["book_id"], "deleted_at": None})
                .sort("updated_at", -1)
                .limit(2)
            )
            for chapter in chapters_cursor:
                recent_chapters.append(
                    RecentChapterItem(
                        chapter_id=chapter["chapter_id"],
                        title=chapter["title"],
                        updated_at=chapter["updated_at"],
                    )
                )

            # Count total chapters from database
            total_chapters_count = db.book_chapters.count_documents(
                {"book_id": book["book_id"], "deleted_at": None}
            )

            books.append(
                CommunityBookItem(
                    book_id=book["book_id"],
                    title=book["title"],
                    slug=book["slug"],
                    cover_url=community_config.get("cover_image_url")
                    or book.get("cover_image_url"),
                    authors=author_ids,
                    author_names=author_names,
                    category=community_config.get("category"),
                    tags=community_config.get("tags", []),
                    total_views=community_config.get("total_views", 0),
                    average_rating=community_config.get("average_rating", 0.0),
                    total_chapters=total_chapters_count,
                    last_updated=community_config.get("last_chapter_updated_at"),
                    recent_chapters=recent_chapters,
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
        # Check cache first
        cache_key = "authors:featured"
        cached = await cache_client.get(cache_key)
        if cached:
            return FeaturedAuthorsResponse(**cached)

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

                    # Get average rating from reviews using aggregation
                    rating_stats = list(
                        db.author_reviews.aggregate(
                            [
                                {"$match": {"author_id": author_id}},
                                {
                                    "$group": {
                                        "_id": None,
                                        "average_rating": {"$avg": "$rating"},
                                    }
                                },
                            ]
                        )
                    )
                    avg_rating = (
                        rating_stats[0]["average_rating"] if rating_stats else 0.0
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

                    # Get average rating using aggregation
                    rating_stats = list(
                        db.author_reviews.aggregate(
                            [
                                {"$match": {"author_id": author_id}},
                                {
                                    "$group": {
                                        "_id": None,
                                        "average_rating": {"$avg": "$rating"},
                                    }
                                },
                            ]
                        )
                    )
                    avg_rating = (
                        rating_stats[0]["average_rating"] if rating_stats else 0.0
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

                        # Get average rating using aggregation
                        rating_stats = list(
                            db.author_reviews.aggregate(
                                [
                                    {"$match": {"author_id": author_id}},
                                    {
                                        "$group": {
                                            "_id": None,
                                            "average_rating": {"$avg": "$rating"},
                                        }
                                    },
                                ]
                            )
                        )
                        avg_rating = (
                            rating_stats[0]["average_rating"] if rating_stats else 0.0
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

        result = FeaturedAuthorsResponse(
            authors=featured_authors,
            total=len(featured_authors),
        )

        # Cache for 30 minutes
        cache_data = result.dict()
        await cache_client.set(cache_key, cache_data, ttl=1800)

        return result

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

            # Get 2 most recent chapters
            recent_chapters = []
            chapters_cursor = (
                db.book_chapters.find({"book_id": book["book_id"], "deleted_at": None})
                .sort("updated_at", -1)
                .limit(2)
            )
            for chapter in chapters_cursor:
                recent_chapters.append(
                    RecentChapterItem(
                        chapter_id=chapter["chapter_id"],
                        title=chapter["title"],
                        updated_at=chapter["updated_at"],
                    )
                )

            # Count total chapters from database
            total_chapters_count = db.book_chapters.count_documents(
                {"book_id": book["book_id"], "deleted_at": None}
            )

            books.append(
                CommunityBookItem(
                    book_id=book["book_id"],
                    title=book["title"],
                    slug=book["slug"],
                    cover_url=community_config.get("cover_image_url")
                    or book.get("cover_image_url"),
                    authors=author_ids,
                    author_names=author_names,
                    category=community_config.get("category"),
                    tags=community_config.get("tags", []),
                    total_views=community_config.get("total_views", 0),
                    average_rating=community_config.get("average_rating", 0.0),
                    total_chapters=total_chapters_count,
                    last_updated=community_config.get("last_chapter_updated_at"),
                    recent_chapters=recent_chapters,
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

            # Get 2 most recent chapters
            recent_chapters = []
            chapters_cursor = (
                db.book_chapters.find({"book_id": book["book_id"], "deleted_at": None})
                .sort("updated_at", -1)
                .limit(2)
            )
            for chapter in chapters_cursor:
                recent_chapters.append(
                    RecentChapterItem(
                        chapter_id=chapter["chapter_id"],
                        title=chapter["title"],
                        updated_at=chapter["updated_at"],
                    )
                )

            # Count total chapters from database
            total_chapters_count = db.book_chapters.count_documents(
                {"book_id": book["book_id"], "deleted_at": None}
            )

            books.append(
                CommunityBookItem(
                    book_id=book["book_id"],
                    title=book["title"],
                    slug=book["slug"],
                    cover_url=community_config.get("cover_image_url")
                    or book.get("cover_image_url"),
                    authors=author_ids,
                    author_names=author_names,
                    category=community_config.get("category"),
                    tags=community_config.get("tags", []),
                    total_views=community_config.get("total_views", 0),
                    average_rating=community_config.get("average_rating", 0.0),
                    total_chapters=total_chapters_count,
                    last_updated=community_config.get("last_chapter_updated_at"),
                    recent_chapters=recent_chapters,
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
# FEATURED BOOKS (WEEK)
# ============================================================================


@router.get(
    "/books/featured-week",
    response_model=FeaturedBooksResponse,
    summary="Get 3 featured books of the week (2 most viewed + 1 most purchased)",
)
async def get_featured_books_week():
    """
    **Get 3 featured books of the week**

    Selection criteria:
    - 2 books with highest views in the last 7 days
    - 1 book with most purchases in the last 7 days

    Returns full book details including cover, authors, chapters, stats.

    **Public endpoint** - No authentication required
    """
    try:
        # Check cache first
        cache_key = "books:featured:week"
        cached = await cache_client.get(cache_key)
        if cached:
            return FeaturedBooksResponse(**cached)

        from datetime import timedelta

        # Get date range for last 7 days
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)

        featured_books = []
        used_book_ids = set()

        # 1. Get 2 books with most views in last 7 days
        views_pipeline = [
            {"$match": {"viewed_at": {"$gte": week_ago, "$lte": now}}},
            {"$group": {"_id": "$book_id", "views_count": {"$sum": 1}}},
            {"$sort": {"views_count": -1}},
            {"$limit": 2},
        ]

        top_viewed = list(db.book_view_sessions.aggregate(views_pipeline))

        for item in top_viewed:
            book_id = item["_id"]
            if book_id in used_book_ids:
                continue

            # Get book details
            book = db.online_books.find_one(
                {
                    "book_id": book_id,
                    "community_config.is_public": True,
                    "deleted_at": None,
                }
            )

            if not book:
                continue

            community_config = book.get("community_config", {})
            stats = book.get("stats", {})

            # Get author names
            author_ids = book.get("authors", [])
            author_names = []
            for author_id in author_ids:
                author = db.book_authors.find_one({"author_id": author_id.lower()})
                if author:
                    author_names.append(author.get("name", author_id))
                else:
                    author_names.append(author_id)

            # Get 2 most recent chapters
            recent_chapters = []
            chapters_cursor = (
                db.book_chapters.find({"book_id": book_id, "deleted_at": None})
                .sort("updated_at", -1)
                .limit(2)
            )
            for chapter in chapters_cursor:
                recent_chapters.append(
                    RecentChapterItem(
                        chapter_id=chapter["chapter_id"],
                        title=chapter["title"],
                        updated_at=chapter["updated_at"],
                    )
                )

            # Calculate total purchases
            total_purchases = (
                stats.get("forever_purchases", 0)
                + stats.get("one_time_purchases", 0)
                + stats.get("pdf_downloads", 0)
            )

            # Count total chapters from database
            total_chapters_count = db.book_chapters.count_documents(
                {"book_id": book_id, "deleted_at": None}
            )

            featured_books.append(
                FeaturedBookItem(
                    book_id=book["book_id"],
                    title=book["title"],
                    slug=book["slug"],
                    cover_url=community_config.get("cover_image_url")
                    or book.get("cover_image_url"),
                    authors=author_ids,
                    author_names=author_names,
                    category=community_config.get("category"),
                    tags=community_config.get("tags", []),
                    total_views=community_config.get("total_views", 0),
                    average_rating=community_config.get("average_rating", 0.0),
                    total_chapters=total_chapters_count,
                    total_purchases=total_purchases,
                    published_at=community_config.get("published_at"),
                    last_updated=community_config.get("last_chapter_updated_at"),
                    recent_chapters=recent_chapters,
                )
            )
            used_book_ids.add(book_id)

        # 2. Get 1 book with most purchases in last 7 days
        # Query book_purchases collection for recent purchases
        purchases_pipeline = [
            {"$match": {"purchased_at": {"$gte": week_ago, "$lte": now}}},
            {"$group": {"_id": "$book_id", "purchase_count": {"$sum": 1}}},
            {"$sort": {"purchase_count": -1}},
            {"$limit": 10},  # Get more to filter out duplicates
        ]

        top_purchased = list(db.book_purchases.aggregate(purchases_pipeline))

        # Find first book not already in featured_books
        for item in top_purchased:
            book_id = item["_id"]
            if book_id in used_book_ids:
                continue

            # Get book details
            book = db.online_books.find_one(
                {
                    "book_id": book_id,
                    "community_config.is_public": True,
                    "deleted_at": None,
                }
            )

            if not book:
                continue

            community_config = book.get("community_config", {})
            stats = book.get("stats", {})

            # Get author names
            author_ids = book.get("authors", [])
            author_names = []
            for author_id in author_ids:
                author = db.book_authors.find_one({"author_id": author_id.lower()})
                if author:
                    author_names.append(author.get("name", author_id))
                else:
                    author_names.append(author_id)

            # Get 2 most recent chapters
            recent_chapters = []
            chapters_cursor = (
                db.book_chapters.find({"book_id": book_id, "deleted_at": None})
                .sort("updated_at", -1)
                .limit(2)
            )
            for chapter in chapters_cursor:
                recent_chapters.append(
                    RecentChapterItem(
                        chapter_id=chapter["chapter_id"],
                        title=chapter["title"],
                        updated_at=chapter["updated_at"],
                    )
                )

            # Calculate total purchases
            total_purchases = (
                stats.get("forever_purchases", 0)
                + stats.get("one_time_purchases", 0)
                + stats.get("pdf_downloads", 0)
            )

            # Count total chapters from database
            total_chapters_count = db.book_chapters.count_documents(
                {"book_id": book_id, "deleted_at": None}
            )

            featured_books.append(
                FeaturedBookItem(
                    book_id=book["book_id"],
                    title=book["title"],
                    slug=book["slug"],
                    cover_url=community_config.get("cover_image_url")
                    or book.get("cover_image_url"),
                    authors=author_ids,
                    author_names=author_names,
                    category=community_config.get("category"),
                    tags=community_config.get("tags", []),
                    total_views=community_config.get("total_views", 0),
                    average_rating=community_config.get("average_rating", 0.0),
                    total_chapters=total_chapters_count,
                    total_purchases=total_purchases,
                    published_at=community_config.get("published_at"),
                    last_updated=community_config.get("last_chapter_updated_at"),
                    recent_chapters=recent_chapters,
                )
            )
            used_book_ids.add(book_id)
            break  # Only need 1 book

        result = FeaturedBooksResponse(
            books=featured_books,
            total=len(featured_books),
        )

        # Cache for 30 minutes
        cache_data = result.dict()
        await cache_client.set(cache_key, cache_data, ttl=1800)

        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get featured books: {str(e)}",
        )


# ============================================================================
# TRENDING BOOKS (TODAY)
# ============================================================================


@router.get(
    "/books/trending-today",
    response_model=TrendingBooksResponse,
    summary="Get 5 trending books today (most viewed)",
)
async def get_trending_books_today():
    """
    **Get 5 trending books today (most viewed in last 24 hours)**

    Returns books with highest view count today.
    Includes full book details: cover, authors, chapters, stats.

    **CACHED:** 15 minutes TTL for near real-time data.

    **Public endpoint** - No authentication required
    """
    try:
        # Check cache first
        cache_key = "books:trending:today"
        cached = await cache_client.get(cache_key)
        if cached:
            # If cache exists but empty, fallback to featured week
            if cached.get("total", 0) == 0:
                logger.info("📊 Trending today is empty, falling back to featured week")
                featured_cache = await cache_client.get("books:featured:week")
                if featured_cache and featured_cache.get("total", 0) > 0:
                    books = featured_cache.get("books", [])[:5]
                    return TrendingBooksResponse(books=books, total=len(books))

            return TrendingBooksResponse(**cached)

        # Get today's date range (00:00 - 23:59 UTC)
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        # Get books with most views today
        pipeline = [
            {"$match": {"viewed_at": {"$gte": today_start, "$lt": today_end}}},
            {"$group": {"_id": "$book_id", "views_today": {"$sum": 1}}},
            {"$sort": {"views_today": -1}},
            {"$limit": 5},
        ]

        top_today = list(db.book_view_sessions.aggregate(pipeline))

        trending_books = []

        for item in top_today:
            book_id = item["_id"]

            # Get book details
            book = db.online_books.find_one(
                {
                    "book_id": book_id,
                    "community_config.is_public": True,
                    "deleted_at": None,
                }
            )

            if not book:
                continue

            community_config = book.get("community_config", {})
            stats = book.get("stats", {})

            # Get author names
            author_ids = book.get("authors", [])
            author_names = []
            for author_id in author_ids:
                author = db.book_authors.find_one({"author_id": author_id.lower()})
                if author:
                    author_names.append(author.get("name", author_id))
                else:
                    author_names.append(author_id)

            # Get 2 most recent chapters
            recent_chapters = []
            chapters_cursor = (
                db.book_chapters.find({"book_id": book_id, "deleted_at": None})
                .sort("updated_at", -1)
                .limit(2)
            )
            for chapter in chapters_cursor:
                recent_chapters.append(
                    RecentChapterItem(
                        chapter_id=chapter["chapter_id"],
                        title=chapter["title"],
                        updated_at=chapter["updated_at"],
                    )
                )

            # Calculate total purchases
            total_purchases = (
                stats.get("forever_purchases", 0)
                + stats.get("one_time_purchases", 0)
                + stats.get("pdf_downloads", 0)
            )

            # Count total chapters from database
            total_chapters_count = db.book_chapters.count_documents(
                {"book_id": book_id, "deleted_at": None}
            )

            trending_books.append(
                FeaturedBookItem(
                    book_id=book["book_id"],
                    title=book["title"],
                    slug=book["slug"],
                    cover_url=community_config.get("cover_image_url")
                    or book.get("cover_image_url"),
                    authors=author_ids,
                    author_names=author_names,
                    category=community_config.get("category"),
                    tags=community_config.get("tags", []),
                    total_views=community_config.get("total_views", 0),
                    average_rating=community_config.get("average_rating", 0.0),
                    total_chapters=total_chapters_count,
                    total_purchases=total_purchases,
                    published_at=community_config.get("published_at"),
                    last_updated=community_config.get("last_chapter_updated_at"),
                    recent_chapters=recent_chapters,
                )
            )

        result = TrendingBooksResponse(
            books=trending_books,
            total=len(trending_books),
        )

        # Cache for 15 minutes
        cache_data = result.dict()
        await cache_client.set(cache_key, cache_data, ttl=900)

        # If no trending books today, return featured week instead
        if len(trending_books) == 0:
            logger.info("📊 No trending books today, returning featured week")
            featured_cache = await cache_client.get("books:featured:week")
            if featured_cache and featured_cache.get("total", 0) > 0:
                books = featured_cache.get("books", [])[:5]
                return TrendingBooksResponse(books=books, total=len(books))

        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get trending books: {str(e)}",
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
        # Check cache first
        cache_key = "tags:popular"
        cached = await cache_client.get(cache_key)
        if cached:
            return PopularTagsResponse(**cached)

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

        result = PopularTagsResponse(
            tags=tags,
            total=len(tags),
        )

        # Cache for 30 minutes
        cache_data = result.dict()
        await cache_client.set(cache_key, cache_data, ttl=1800)

        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get popular tags: {str(e)}",
        )


# ============================================================================
# BOOKS BY TAG
# ============================================================================


@router.get(
    "/books/by-tag/{tag}",
    response_model=CommunityBooksResponse,
    summary="Get books by specific tag",
)
async def get_books_by_tag(
    tag: str,
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query(
        "updated",
        description="Sort by: updated, views, rating, newest",
    ),
):
    """
    **Get all books with a specific tag**

    When user clicks a tag, this endpoint shows all books with that tag.

    **Sort Options:**
    - `updated`: Latest chapter update (default)
    - `views`: Most viewed
    - `rating`: Highest rated
    - `newest`: Recently published

    **Public endpoint** - No authentication required
    """
    try:
        # Build query
        query = {
            "community_config.is_public": True,
            "community_config.tags": tag,
            "deleted_at": None,
        }

        # Sort mapping
        sort_map = {
            "updated": ("community_config.last_chapter_updated_at", -1),
            "views": ("community_config.total_views", -1),
            "rating": ("community_config.average_rating", -1),
            "newest": ("community_config.published_at", -1),
        }

        sort_field, sort_order = sort_map.get(sort_by, sort_map["updated"])

        # Get total count
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

            # Get 2 most recent chapters
            recent_chapters = []
            chapters_cursor = (
                db.book_chapters.find({"book_id": book["book_id"], "deleted_at": None})
                .sort("updated_at", -1)
                .limit(2)
            )
            for chapter in chapters_cursor:
                recent_chapters.append(
                    RecentChapterItem(
                        chapter_id=chapter["chapter_id"],
                        title=chapter["title"],
                        updated_at=chapter["updated_at"],
                    )
                )

            books.append(
                CommunityBookItem(
                    book_id=book["book_id"],
                    title=book["title"],
                    slug=book["slug"],
                    cover_url=community_config.get("cover_image_url")
                    or book.get("cover_image_url"),
                    authors=author_ids,
                    author_names=author_names,
                    category=community_config.get("category"),
                    tags=community_config.get("tags", []),
                    total_views=community_config.get("total_views", 0),
                    average_rating=community_config.get("average_rating", 0.0),
                    total_chapters=db.book_chapters.count_documents(
                        {"book_id": book["book_id"], "deleted_at": None}
                    ),
                    last_updated=community_config.get("last_chapter_updated_at"),
                    recent_chapters=recent_chapters,
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
            detail=f"Failed to get books by tag: {str(e)}",
        )
