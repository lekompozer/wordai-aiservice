# Community Books API - Technical Specifications

## Overview

Complete API system for public book discovery and community browsing. Includes search, featured authors, latest books, top books, and popular tags.

**Base URL:** `/api/v1/community`
**Authentication:** None (public endpoints)

---

## 1. Search & Filter Books

**Endpoint:** `GET /api/v1/community/books/search`

**Description:** Search and filter community books by title, author name, category, and tags.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `q` | string | No | Search by book title or author name (case-insensitive) |
| `category` | string | No | Filter by exact category |
| `tags` | string | No | Filter by tags (comma-separated) |
| `skip` | integer | No | Pagination offset (default: 0) |
| `limit` | integer | No | Items per page (default: 20, max: 100) |
| `sort_by` | string | No | Sort order: `updated`, `views`, `rating`, `newest` (default: `updated`) |

**Sort Options:**
- `updated` - Latest chapter update (community_config.last_chapter_updated_at)
- `views` - Most viewed (community_config.total_views)
- `rating` - Highest rated (community_config.average_rating)
- `newest` - Recently published (community_config.published_at)

**Response Schema:**

```javascript
{
  "books": [
    {
      "book_id": "string",
      "title": "string",
      "slug": "string",
      "cover_url": "string",  // Can be null
      "authors": ["@username"],  // Array of author_ids
      "author_names": ["Display Name"],  // Array of display names
      "category": "Fiction",  // Can be null
      "tags": ["fantasy", "adventure"],  // Array of strings
      "total_views": 1520,
      "average_rating": 4.5,
      "total_chapters": 25,
      "last_updated": "2024-01-15T10:30:00Z"  // ISO 8601, can be null
    }
  ],
  "total": 150,  // Total matching books
  "skip": 0,
  "limit": 20
}
```

**Database Query:**
- Collection: `online_books`
- Filter: `community_config.is_public = true` AND `deleted_at = null`
- Search: `$or` on `title` and `authors` fields with regex
- Tags: `$in` operator on `community_config.tags` array

**Example Requests:**

```
GET /api/v1/community/books/search?q=fantasy
GET /api/v1/community/books/search?category=Fiction&tags=romance,drama
GET /api/v1/community/books/search?sort_by=views&limit=50
```

---

## 2. Featured Authors

**Endpoint:** `GET /api/v1/community/authors/featured`

**Description:** Get 10 featured authors for homepage slider with diverse selection criteria.

**Query Parameters:** None

**Selection Algorithm:**

1. **3 authors by total reads:**
   - Aggregate sum of `community_config.total_views` across all public books per author
   - Sort descending
   - Take top 3

2. **3 authors by best reviews:**
   - Count 5-star reviews per author
   - Sort by count descending
   - Take next 3 unique authors

3. **4 authors by top book views:**
   - Get top 20 books by `community_config.total_views`
   - Extract authors from those books
   - Take next 4 unique authors

**Deduplication:** Ensures 10 unique authors across all criteria.

**Response Schema:**

```javascript
{
  "authors": [
    {
      "author_id": "@username",
      "name": "Display Name",
      "avatar_url": "https://...",  // Can be null
      "bio": "Short bio text...",  // Can be null, max 500 chars
      "total_books": 12,  // Public books count
      "total_reads": 45000,  // Sum of all book views
      "average_rating": 4.8,  // From author reviews
      "total_followers": 1250
    }
  ],
  "total": 10  // Always 10 or fewer
}
```

**Database Operations:**
- **Aggregation 1:** `db.online_books.aggregate()` - Group by authors, sum total_views
- **Aggregation 2:** `db.author_reviews.aggregate()` - Group by author_id, count rating=5
- **Query 3:** `db.online_books.find()` - Top books by views
- **Lookups:** Join with `book_authors` and `author_follows` collections

**Performance Notes:**
- Uses 3 separate aggregations with deduplication
- May take 200-500ms for large datasets
- Consider caching for 5-10 minutes

---

## 3. Latest Books

**Endpoint:** `GET /api/v1/community/books/latest`

**Description:** Get latest updated books for 2-column x 10-row grid layout.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `category` | string | No | Filter by category |
| `tags` | string | No | Filter by tags (comma-separated) |
| `skip` | integer | No | Pagination offset (default: 0) |
| `limit` | integer | No | Items per page (default: 20, max: 100) |

**Sorting:** Always sorted by `community_config.last_chapter_updated_at` descending.

**Response Schema:**

Same as Search & Filter Books endpoint (see section 1).

**Database Query:**
- Collection: `online_books`
- Filter: `community_config.is_public = true` AND `deleted_at = null`
- Sort: `community_config.last_chapter_updated_at DESC`
- Optional filters: category, tags

**UI Recommendation:**
- Default limit: 20 books
- Display in 2 columns x 10 rows grid
- Infinite scroll or pagination

**Example Requests:**

```
GET /api/v1/community/books/latest
GET /api/v1/community/books/latest?category=Fiction&limit=40
GET /api/v1/community/books/latest?tags=fantasy,adventure&skip=20
```

---

## 4. Top Books

**Endpoint:** `GET /api/v1/community/books/top`

**Description:** Get top most viewed books.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `category` | string | No | Filter by category |
| `tags` | string | No | Filter by tags (comma-separated) |
| `limit` | integer | No | Items to return (default: 10, max: 50) |

**Sorting:** Always sorted by `community_config.total_views` descending.

**Response Schema:**

Same as Search & Filter Books endpoint (see section 1).

**Database Query:**
- Collection: `online_books`
- Filter: `community_config.is_public = true` AND `deleted_at = null`
- Sort: `community_config.total_views DESC`
- Optional filters: category, tags

**UI Recommendation:**
- Default: 10 books
- Display as vertical list or horizontal carousel
- Show view count prominently

**Example Requests:**

```
GET /api/v1/community/books/top
GET /api/v1/community/books/top?limit=20
GET /api/v1/community/books/top?category=Romance&limit=15
```

---

## 5. Popular Tags

**Endpoint:** `GET /api/v1/community/tags/popular`

**Description:** Get 25 most popular tags sorted by book count.

**Query Parameters:** None

**Response Schema:**

```javascript
{
  "tags": [
    {
      "tag": "fantasy",
      "books_count": 245
    },
    {
      "tag": "romance",
      "books_count": 189
    }
  ],
  "total": 25  // Number of tags returned (max 25)
}
```

**Database Operation:**
- Aggregation: `db.online_books.aggregate()`
- Steps:
  1. Match public books
  2. Unwind `community_config.tags` array
  3. Group by tag, count books
  4. Sort by count descending
  5. Limit to 25

**UI Recommendation:**
- Display as tag cloud with font sizes based on books_count
- Or horizontal scrollable list
- Make tags clickable to filter books

**Example Request:**

```
GET /api/v1/community/tags/popular
```

---

## Database Schema Reference

### online_books Collection

```javascript
{
  "book_id": "string",
  "title": "string",
  "slug": "string",
  "cover_url": "string",
  "authors": ["@username"],  // Array of author_ids
  "deleted_at": null,
  "community_config": {
    "is_public": true,  // REQUIRED: Must be true for community
    "category": "Fiction",
    "tags": ["fantasy", "adventure"],
    "total_views": 1520,
    "average_rating": 4.5,
    "total_chapters": 25,
    "published_at": ISODate("2024-01-01T00:00:00Z"),
    "last_chapter_updated_at": ISODate("2024-01-15T10:30:00Z")
  }
}
```

### book_authors Collection

```javascript
{
  "author_id": "@username",  // Lowercase, with @ prefix
  "user_id": "firebase_uid",
  "name": "Display Name",
  "avatar_url": "https://...",
  "bio": "Short bio text (max 500 chars)"
}
```

### author_reviews Collection

```javascript
{
  "review_id": "string",
  "author_id": "@username",
  "reviewer_user_id": "firebase_uid",
  "rating": 5,  // 1-5
  "text": "Review text",
  "created_at": ISODate()
}
```

### author_follows Collection

```javascript
{
  "author_id": "@username",
  "follower_user_id": "firebase_uid",
  "followed_at": ISODate()
}
```

---

## Error Responses

All endpoints return consistent error format:

```javascript
{
  "detail": "Error message describing what went wrong"
}
```

**Status Codes:**
- `200` - Success
- `400` - Invalid parameters (e.g., limit > 100)
- `500` - Internal server error (database issues, etc.)

---

## Performance Considerations

### Caching Recommendations

1. **Featured Authors:** Cache for 5-10 minutes (slow aggregation)
2. **Popular Tags:** Cache for 30 minutes (infrequent changes)
3. **Latest/Top Books:** Cache for 1-2 minutes (frequent updates)
4. **Search Results:** No caching (user-specific queries)

### Database Indexes

Required indexes on `online_books`:

```javascript
// For public books filter
db.online_books.createIndex({"community_config.is_public": 1, "deleted_at": 1})

// For latest books sort
db.online_books.createIndex({"community_config.last_chapter_updated_at": -1})

// For top books sort
db.online_books.createIndex({"community_config.total_views": -1})

// For tag aggregation
db.online_books.createIndex({"community_config.tags": 1})

// For text search
db.online_books.createIndex({title: "text", authors: 1})
```

### Rate Limiting

Recommended limits:
- **Featured Authors:** 10 requests/minute per IP
- **Search:** 60 requests/minute per IP
- **Latest/Top Books:** 30 requests/minute per IP
- **Popular Tags:** 10 requests/minute per IP

---

## Integration Examples

### Frontend Display Flow

**1. Homepage:**
```
GET /api/v1/community/authors/featured  // Slider
GET /api/v1/community/books/latest?limit=20  // Grid
GET /api/v1/community/books/top?limit=10  // Sidebar
GET /api/v1/community/tags/popular  // Tag cloud
```

**2. Search Page:**
```
// Initial load
GET /api/v1/community/books/search?skip=0&limit=20

// User types "fantasy"
GET /api/v1/community/books/search?q=fantasy&skip=0&limit=20

// User selects category "Fiction"
GET /api/v1/community/books/search?q=fantasy&category=Fiction&skip=0&limit=20

// User scrolls down (pagination)
GET /api/v1/community/books/search?q=fantasy&category=Fiction&skip=20&limit=20
```

**3. Category Page:**
```
GET /api/v1/community/books/search?category=Fiction&sort_by=rating&limit=50
```

**4. Tag Page:**
```
GET /api/v1/community/books/search?tags=fantasy,adventure&sort_by=views
```

---

## Testing Checklist

### Search & Filter
- [ ] Empty query returns all public books
- [ ] Search by title works (case-insensitive)
- [ ] Search by author name works
- [ ] Category filter returns correct books
- [ ] Tags filter with comma-separated values works
- [ ] Multiple filters combine correctly (AND logic)
- [ ] Pagination works (skip/limit)
- [ ] All sort options work correctly
- [ ] Invalid sort_by returns default (updated)

### Featured Authors
- [ ] Returns exactly 10 unique authors
- [ ] No duplicate authors across 3 criteria
- [ ] Authors have correct total_reads (sum of book views)
- [ ] Authors have correct average_rating (from reviews)
- [ ] Authors have correct total_followers
- [ ] Returns fewer than 10 if insufficient authors exist

### Latest Books
- [ ] Returns books sorted by last_chapter_updated_at
- [ ] Category filter works
- [ ] Tags filter works
- [ ] Pagination works
- [ ] Default limit is 20

### Top Books
- [ ] Returns books sorted by total_views descending
- [ ] Category filter works
- [ ] Tags filter works
- [ ] Default limit is 10
- [ ] Max limit enforced (50)

### Popular Tags
- [ ] Returns 25 tags maximum
- [ ] Tags sorted by books_count descending
- [ ] Tags with same count maintain stable order
- [ ] Empty tags not included
- [ ] Returns fewer than 25 if insufficient tags exist

---

## Deployment Notes

**Environment:** Production WordAI service
**Commit:** e1faded
**Files:**
- `src/api/community_routes.py` - Main API implementation
- `src/app.py` - Router registration

**Deployment Command:**
```bash
./deploy.sh
```

**Verification:**
```bash
curl https://wordai.tech/api/v1/community/books/search?limit=5
curl https://wordai.tech/api/v1/community/authors/featured
curl https://wordai.tech/api/v1/community/books/latest?limit=10
curl https://wordai.tech/api/v1/community/books/top?limit=5
curl https://wordai.tech/api/v1/community/tags/popular
```

---

## Migration Notes

**No database migration required.** All endpoints use existing collections and fields:
- `online_books` with `community_config`
- `book_authors`
- `author_reviews`
- `author_follows`

**New indexes recommended** (see Performance Considerations section).

---

## Support & Maintenance

**Code Location:** `src/api/community_routes.py` (725 lines)
**Dependencies:**
- FastAPI
- PyMongo
- Pydantic

**Monitoring:**
- Track response times for featured authors (may be slow)
- Monitor cache hit rates
- Track search query patterns for optimization

**Future Enhancements:**
- Full-text search with MongoDB Atlas Search
- Relevance scoring for search results
- User-specific recommendations
- Trending books (views in last 7 days)
- Category popularity rankings
