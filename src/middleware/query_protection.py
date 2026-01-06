"""
Database Query Protection Middleware

Enforces query limits to prevent:
- Memory exhaustion from loading unlimited records
- DoS attacks via large result sets
- Database overload from scanning millions of documents
- Cost overruns from excessive data transfer

Usage:
    from src.middleware.query_protection import protect_query, paginate

    # Simple limit
    results = protect_query(db.reviews, {"book_id": id}, limit=100)

    # With pagination
    response = paginate(db.reviews, {"book_id": id}, page=1, per_page=50)
"""

from typing import Any, Dict, List, Optional
from pymongo.collection import Collection
from pymongo.cursor import Cursor

# ============================================================================
# CONSTANTS
# ============================================================================

# Absolute maximum - prevent loading millions of records
MAX_QUERY_LIMIT = 1000

# Default limits by resource type
DEFAULT_LIMITS = {
    "reviews": 100,  # Book/author reviews
    "ratings": 500,  # Test ratings
    "chapters": 1000,  # Book chapters (some books are long)
    "tests": 50,  # User's test library
    "purchases": 100,  # Purchase history
    "attempts": 100,  # Test attempts
    "comments": 100,  # Comments/discussions
    "followers": 500,  # Follower lists
    "notifications": 100,  # User notifications
    "default": 100,  # Fallback for everything else
}

# Pagination defaults
DEFAULT_PAGE = 1
DEFAULT_PER_PAGE = 50
MAX_PER_PAGE = 100


# ============================================================================
# QUERY PROTECTION FUNCTIONS
# ============================================================================


def protect_query(
    collection: Collection,
    filter_dict: Dict[str, Any],
    limit: Optional[int] = None,
    resource_type: str = "default",
    sort: Optional[List[tuple]] = None,
) -> List[Dict[str, Any]]:
    """
    Execute MongoDB query with enforced limit

    Args:
        collection: MongoDB collection
        filter_dict: Query filter
        limit: Custom limit (optional)
        resource_type: Type of resource (reviews/ratings/etc)
        sort: Sort specification [(field, direction), ...]

    Returns:
        List of documents (never exceeds MAX_QUERY_LIMIT)

    Example:
        # Load max 100 reviews
        reviews = protect_query(
            db.author_reviews,
            {"author_id": author_id},
            resource_type="reviews"
        )

        # Custom limit
        recent_tests = protect_query(
            db.online_tests,
            {"creator_id": user_id},
            limit=20,
            sort=[("created_at", -1)]
        )
    """
    # Determine limit
    if limit is None:
        limit = DEFAULT_LIMITS.get(resource_type, DEFAULT_LIMITS["default"])

    # Enforce maximum
    if limit > MAX_QUERY_LIMIT:
        limit = MAX_QUERY_LIMIT

    # Build cursor
    cursor = collection.find(filter_dict)

    # Apply sort if specified
    if sort:
        cursor = cursor.sort(sort)

    # Apply limit and return
    return list(cursor.limit(limit))


def paginate(
    collection: Collection,
    filter_dict: Dict[str, Any],
    page: int = DEFAULT_PAGE,
    per_page: int = DEFAULT_PER_PAGE,
    sort: Optional[List[tuple]] = None,
    count_total: bool = True,
) -> Dict[str, Any]:
    """
    Paginate MongoDB query results

    Args:
        collection: MongoDB collection
        filter_dict: Query filter
        page: Page number (1-indexed)
        per_page: Items per page (max 100)
        sort: Sort specification [(field, direction), ...]
        count_total: Whether to count total documents (expensive for large collections)

    Returns:
        {
            "data": [...],           # Documents for this page
            "page": 1,               # Current page
            "per_page": 50,          # Items per page
            "total": 1234,           # Total matching documents (if count_total=True)
            "pages": 25,             # Total pages (if count_total=True)
            "has_next": true,        # Whether next page exists
            "has_prev": false,       # Whether previous page exists
        }

    Example:
        result = paginate(
            db.book_reviews,
            {"book_id": book_id},
            page=2,
            per_page=50,
            sort=[("created_at", -1)]
        )

        reviews = result["data"]
        total_pages = result["pages"]
    """
    # Validate pagination params
    page = max(1, page)  # Ensure page >= 1
    per_page = min(per_page, MAX_PER_PAGE)  # Cap at 100
    per_page = max(1, per_page)  # Ensure per_page >= 1

    # Calculate skip
    skip = (page - 1) * per_page

    # Build cursor
    cursor = collection.find(filter_dict)

    # Apply sort if specified
    if sort:
        cursor = cursor.sort(sort)

    # Get data for this page
    data = list(cursor.skip(skip).limit(per_page))

    # Build response
    response = {
        "data": data,
        "page": page,
        "per_page": per_page,
        "has_prev": page > 1,
    }

    # Count total (expensive - only do if requested)
    if count_total:
        total = collection.count_documents(filter_dict)
        pages = (total + per_page - 1) // per_page  # Ceiling division

        response["total"] = total
        response["pages"] = pages
        response["has_next"] = page < pages
    else:
        # Estimate if there's a next page by fetching one extra document
        has_next = (
            len(list(collection.find(filter_dict).skip(skip + per_page).limit(1))) > 0
        )
        response["has_next"] = has_next

    return response


def validate_pagination_params(
    page: Optional[int] = None,
    per_page: Optional[int] = None,
) -> tuple[int, int]:
    """
    Validate and sanitize pagination parameters

    Args:
        page: Page number from request
        per_page: Items per page from request

    Returns:
        Tuple of (validated_page, validated_per_page)

    Example:
        page, per_page = validate_pagination_params(
            page=request.args.get("page"),
            per_page=request.args.get("per_page")
        )
    """
    # Default values
    if page is None:
        page = DEFAULT_PAGE
    if per_page is None:
        per_page = DEFAULT_PER_PAGE

    # Validate page (must be >= 1)
    try:
        page = int(page)
        page = max(1, page)
    except (TypeError, ValueError):
        page = DEFAULT_PAGE

    # Validate per_page (1-100)
    try:
        per_page = int(per_page)
        per_page = max(1, min(per_page, MAX_PER_PAGE))
    except (TypeError, ValueError):
        per_page = DEFAULT_PER_PAGE

    return page, per_page


# ============================================================================
# QUERY MONITORING (Optional - for production debugging)
# ============================================================================


def log_slow_query(
    collection_name: str,
    filter_dict: Dict[str, Any],
    duration_ms: float,
    result_count: int,
):
    """
    Log queries that take too long or return too many results

    Call this after executing queries in production to identify performance issues.

    Args:
        collection_name: Name of MongoDB collection
        filter_dict: Query filter used
        duration_ms: Query execution time in milliseconds
        result_count: Number of documents returned
    """
    # Thresholds
    SLOW_QUERY_MS = 1000  # 1 second
    LARGE_RESULT = 500  # 500+ documents

    if duration_ms > SLOW_QUERY_MS or result_count > LARGE_RESULT:
        print(f"⚠️  SLOW QUERY DETECTED")
        print(f"   Collection: {collection_name}")
        print(f"   Filter: {filter_dict}")
        print(f"   Duration: {duration_ms}ms")
        print(f"   Results: {result_count} documents")
        print(f"   Consider adding index or pagination")


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

if __name__ == "__main__":
    """
    Example usage patterns
    """

    # Example 1: Simple query protection
    # Before:
    #   reviews = list(db.author_reviews.find({"author_id": author_id}))
    # After:
    #   reviews = protect_query(
    #       db.author_reviews,
    #       {"author_id": author_id},
    #       resource_type="reviews"
    #   )

    # Example 2: Pagination for API endpoint
    # @router.get("/books/{book_id}/reviews")
    # async def get_reviews(
    #     book_id: str,
    #     page: int = 1,
    #     per_page: int = 50
    # ):
    #     page, per_page = validate_pagination_params(page, per_page)
    #
    #     result = paginate(
    #         db.book_reviews,
    #         {"book_id": book_id},
    #         page=page,
    #         per_page=per_page,
    #         sort=[("created_at", -1)]
    #     )
    #
    #     return {
    #         "reviews": result["data"],
    #         "pagination": {
    #             "page": result["page"],
    #             "per_page": result["per_page"],
    #             "total": result["total"],
    #             "pages": result["pages"],
    #         }
    #     }

    pass
