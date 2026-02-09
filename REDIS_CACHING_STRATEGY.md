# Redis Caching Strategy - Community Books System

**Document Version:** 1.0
**Date:** February 9, 2026
**Target:** Optimize Community Books endpoints to load under 500ms

---

## 📊 Executive Summary

**Current Problem:**
- Community homepage loads 7-8 heavy MongoDB aggregation queries simultaneously
- Each user F5 triggers full database scans (sort, group, count operations)
- With thousands of books, database will reach breaking point
- Current response time: ~2-5 seconds (unacceptable)

**Solution:**
- Implement Redis server-side caching
- Separate Global Data (same for all users) vs User Data (per-user)
- Background jobs to pre-compute and update cache
- Target response time: **< 500ms** (10x improvement)

---

## 🔍 Bottleneck Analysis

### Current Endpoints (From `/api/v1/community/` and `/api/v1/book-categories/`)

#### 0. **GET /book-categories/** - All Categories Tree with Book Counts
**Query Pattern:**
```python
# For 11 parent categories → 33 child categories:
for parent in PARENT_CATEGORIES:  # 11 iterations
    for child in parent.children:  # ~3 children per parent
        count = db.online_books.count_documents({
            "community_config.category": child.name,
            "community_config.is_public": True,
            "deleted_at": None
        })
# Total: 33 count queries per request
```

**Bottlenecks:**
- ❌ **33 Count Queries:** One per child category (serial execution)
- ❌ **No Index on category field:** Full collection scan for each count
- ❌ **Runs on every page load:** Category sidebar/navigation
- ⏱️ **Estimated Time:** 500-800ms per request

**Cache Strategy:** ✅ **GLOBAL CACHE** (TTL: 10-15 minutes)

---

#### 0.1. **GET /book-categories/parent/{id}** - Top 5 Books per Parent Category
**Query Pattern:**
```python
# Example: parent_id = "business"
# Query all books in children: "Kinh Tế - Quản Lý", "Marketing - Bán hàng", "Tâm Lý - Kỹ Năng Sống"
db.online_books.find({
    "community_config.category": {"$in": child_categories},  # 3-5 categories
    "community_config.is_public": True,
    "deleted_at": None
}).sort("community_config.total_views", -1).limit(5)

# + For each of 5 books:
#   - db.book_authors.find_one() × authors_count
#   - Get access_config data
```

**Bottlenecks:**
- ❌ **$in Query:** Queries multiple categories (slow without index)
- ❌ **N+1 Author Lookups:** 5 books × 2 authors = 10 extra queries
- ❌ **Repeated per Category:** 11 parent categories = 11 requests on homepage
- ⏱️ **Estimated Time:** 300-500ms per parent category request

**Cache Strategy:** ✅ **GLOBAL CACHE per parent** (TTL: 15-30 minutes)
- Cache key: `books:top:category:{parent_id}` (11 keys total)

---

#### 0.2. **GET /book-categories/child/{slug}** - Books in Specific Child Category
**Query Pattern:**
```python
# Example: child_slug = "kinh-te-quan-ly"
db.online_books.find({
    "community_config.category": "Kinh Tế - Quản Lý",
    "community_config.is_public": True,
    "deleted_at": None
}).sort(sort_field, -1).skip(skip).limit(20)

# + N+1 queries for authors
```

**Bottlenecks:**
- ❌ **Category Filtering:** Needs index on community_config.category
- ❌ **N+1 Problem:** Same as other list endpoints
- ⏱️ **Estimated Time:** 400-700ms per request

**Cache Strategy:** ✅ Partial cache (common category + sort combinations)

---

#### 1. **GET /books/search** - Search & Filter Books
**Query Pattern:**
```python
db.online_books.find(query).sort(field, -1).skip(skip).limit(limit)
# + For each book:
#   - db.book_authors.find_one() × authors_count
#   - db.book_chapters.find().sort().limit(2)
#   - db.book_chapters.count_documents()
```

**Bottlenecks:**
- ❌ **N+1 Query Problem:** For 20 books with 2 authors each = 40+ author queries
- ❌ **Multiple Sorts:** Sort books + sort chapters per book
- ❌ **Count Operations:** Chapter count for each book
- ⏱️ **Estimated Time:** 800-1500ms per request

**Cache Strategy:** ✅ Partial cache (search results by common filters)

---

#### 2. **GET /authors/featured** - 10 Featured Authors
**Query Pattern:**
```python
# Pipeline 1: Top 3 by total reads
db.online_books.aggregate([unwind, group, sort, limit])
# + For each author:
#   - db.book_authors.find_one()
#   - db.online_books.count_documents()
#   - db.author_reviews.aggregate() # average rating
#   - db.author_follows.count_documents()

# Pipeline 2: Top 3 by 5-star reviews
db.author_reviews.aggregate([match, group, sort])
# + Same per-author queries as above

# Pipeline 3: Top 4 from highest-viewed books
db.online_books.find().sort().limit(20)
# + Same per-author queries
```

**Bottlenecks:**
- ❌ **3 Heavy Aggregations:** Group by author, sum views, count reviews
- ❌ **Multiple Sub-queries:** ~10 authors × 4 queries each = 40+ queries
- ❌ **Duplicate Calculation:** Same aggregations run every request
- ⏱️ **Estimated Time:** 1200-2000ms per request

**Cache Strategy:** ✅ **GLOBAL CACHE** (TTL: 24 hours)

---

#### 3. **GET /books/latest** - Latest Updated Books (2×10 grid)
**Query Pattern:**
```python
db.online_books.find(query).sort("last_chapter_updated_at", -1).limit(20)
# + Same N+1 problem as /search
```

**Bottlenecks:**
- ❌ **Full Collection Sort:** Sort all public books by timestamp
- ❌ **N+1 Queries:** 20 books × (authors + chapters + counts)
- ⏱️ **Estimated Time:** 600-1000ms per request

**Cache Strategy:** ✅ **GLOBAL CACHE** (TTL: 5-10 minutes)

---

#### 4. **GET /books/top** - Top 10 Most Viewed Books
**Query Pattern:**
```python
db.online_books.find(query).sort("total_views", -1).limit(10)
# + N+1 queries for authors/chapters
```

**Bottlenecks:**
- ❌ **Sort by Views:** Full collection scan if no index
- ❌ **N+1 Queries:** Same as above
- ⏱️ **Estimated Time:** 500-800ms per request

**Cache Strategy:** ✅ **GLOBAL CACHE** (TTL: 1 hour)

---

#### 5. **GET /books/featured-week** - 3 Featured Books of Week
**Query Pattern:**
```python
# Pipeline 1: Top 2 by views last 7 days
db.book_view_sessions.aggregate([
    match(date_range),
    group_by(book_id),
    sort_by(views_count),
    limit(2)
])

# Pipeline 2: Top 1 by purchases last 7 days
db.book_purchases.aggregate([
    match(date_range),
    group_by(book_id),
    sort_by(purchase_count),
    limit(10)
])

# + For each book: Same N+1 queries
```

**Bottlenecks:**
- ❌ **Time-Range Aggregations:** Scan 7 days of view sessions
- ❌ **Two Heavy Pipelines:** Group millions of view records
- ❌ **Date Filtering:** No index on `viewed_at` + `purchased_at`
- ⏱️ **Estimated Time:** 1500-3000ms per request (CRITICAL)

**Cache Strategy:** ✅ **GLOBAL CACHE** (TTL: 30-60 minutes)

---

#### 6. **GET /books/trending-today** - 5 Trending Books Today
**Query Pattern:**
```python
db.book_view_sessions.aggregate([
    match(today_range),  # 00:00-23:59 UTC
    group_by(book_id),
    sort_by(views_today),
    limit(5)
])
# + N+1 queries for book details
```

**Bottlenecks:**
- ❌ **Daily Aggregation:** Scans all today's view sessions (thousands)
- ❌ **No Index:** `viewed_at` field likely unindexed
- ❌ **Runs Every Request:** Recalculates same data repeatedly
- ⏱️ **Estimated Time:** 1000-2000ms per request

**Cache Strategy:** ✅ **GLOBAL CACHE** (TTL: 15 minutes)

---

#### 7. **GET /tags/popular** - 25 Most Popular Tags
**Query Pattern:**
```python
db.online_books.aggregate([
    match(is_public),
    unwind(tags),
    group_by(tag),
    sort_by(books_count),
    limit(25)
])
```

**Bottlenecks:**
- ❌ **Unwind Array:** Expands every book's tags array
- ❌ **Group Operation:** Counts books per tag
- ❌ **Full Collection Scan:** Processes all public books
- ⏱️ **Estimated Time:** 400-800ms per request

**Cache Strategy:** ✅ **GLOBAL CACHE** (TTL: 24 hours)

---

## 🎯 Redis Caching Architecture

### A. Global Cache Keys (Same for ALL users)

| Endpoint | Redis Key | TTL | Update Strategy | Priority |
|----------|-----------|-----|-----------------|----------|
| **Category Tree** | `categories:tree:all` | 15 min | Invalidate on new book | 🔴 CRITICAL |
| **Top Books per Category** | `books:top:category:{parent_id}` | 30 min | Cronjob every 30m | 🔴 CRITICAL |
| **Trending Today** | `books:trending:today` | 15 min | Cronjob every 30m | 🔴 CRITICAL |
| **Featured Week** | `books:trending:week` | 60 min | Cronjob every 120m | 🔴 CRITICAL |
| **Latest Books** | `books:newest:all` | 20 min | Invalidate on new book | 🟡 HIGH |
| **Top Books** | `books:top:all` | 1 hour | Cronjob hourly | 🟡 HIGH |
| **Featured Authors** | `authors:featured` | 24 hours | Cronjob daily | 🟢 MEDIUM |
| **Popular Tags** | `tags:popular` | 24 hours | Cronjob daily | 🟢 MEDIUM |
| **Search Results** | `books:search:{hash}` | 10 min | Passive cache | 🟢 MEDIUM |
| **Child Category Books** | `books:child:{slug}:{sort}:{page}` | 10 min | Passive cache | 🟢 MEDIUM |

**Category Cache Keys (11 parent categories):**
```python
# Top 5 books per parent category (for homepage sliders)
"books:top:category:education"    # 5 books
"books:top:category:business"     # 5 books
"books:top:category:technology"   # 5 books
"books:top:category:health"       # 5 books
"books:top:category:lifestyle"    # 5 books
# ... 11 total keys
```

**Hash Key Example for Search:**
```python
# /books/search?category=business&sort_by=views&limit=20
cache_key = f"books:search:{hashlib.md5('category=business&sort_by=views&limit=20'.encode()).hexdigest()}"
```

---

### B. User-Specific Cache Keys (Per User)

| Data Type | Redis Key | TTL | Invalidation Trigger |
|-----------|-----------|-----|----------------------|
| **My Saved Books** | `user:{user_id}:saved_books` | 1 hour | On save/unsave action |
| **My Reading History** | `user:{user_id}:history` | 1 hour | On view book |
| **My Purchases** | `user:{user_id}:purchases` | 1 day | On purchase |

---

## 🛠️ Implementation Plan

### Phase 1: Critical Endpoints (Week 1) 🔴

**Priority:** Fix slowest endpoints first

```python
# 1. Trending Today (Most expensive)
@router.get("/books/trending-today")
async def get_trending_books_today():
    cache_key = "books:trending:today"

    # Try cache first
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    # Cache miss - compute
    books = compute_trending_today()

    # Store in cache (15 min TTL)
    await redis_client.setex(cache_key, 900, json.dumps(books))
    return books
```

**Endpoints:**
1. ✅ `/books/trending-today` (15 min cache)
2. ✅ `/books/featured-week` (30 min cache)
3. ✅ `/book-categories/` (10 min cache) - **Category tree with counts**

---

### Phase 2: Category & High-Traffic Endpoints (Week 2) 🟡

**New: Category Caching**
```python
# 1. Category Tree (33 count queries → 1 Redis lookup)
@router.get("/book-categories/")
async def get_all_categories():
    cache_key = "categories:tree:all"
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    # Cache miss - compute all 33 counts
    tree = build_category_tree_with_counts()
    await redis_client.setex(cache_key, 600, json.dumps(tree))  # 10 min
    return tree

# 2. Top 5 Books per Parent Category (11 separate caches)
@router.get("/book-categories/parent/{parent_id}")
async def get_top_books_by_parent(parent_id: str):
    cache_key = f"books:top:category:{parent_id}"
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    # Cache miss - query top 5 books
    books = get_top_5_books_for_category(parent_id)
    await redis_client.setex(cache_key, 1800, json.dumps(books))  # 30 min
    return books
```

**Endpoints:**
4. ✅ `/book-categories/parent/{id}` - Top 5 per category (11 cache keys)
5. ✅ `/books/latest` (20 min cache)
6. ✅ `/books/top` (1 hour cache)
7. ✅ `/books/search` (10 min cache with query hash)

---

### Phase 3: Static Data (Week 3) 🟢

**Endpoints:**
8. ✅ `/authors/featured` (24 hour cache)
9. ✅ `/tags/popular` (24 hour cache)

---

### Phase 4: Background Jobs (Week 4) 🚀

**Cronjob Worker:** Pre-compute and update cache

```python
# worker/cache_updater.py
async def update_trending_cache():
    """Runs every 15 minutes"""
    books = compute_trending_today_from_db()
    await redis_client.setex("books:trending:today", 900, json.dumps(books))

async def update_featured_cache():
    """Runs every 30 minutes"""
    books = compute_featured_week_from_db()
    await redis_client.setex("books:trending:week", 1800, json.dumps(books))

async def update_category_caches():
    """Runs every 30 minutes - Update all category caches"""
    # 1. Update category tree
    tree = build_category_tree_with_counts()
    await redis_client.setex("categories:tree:all", 600, json.dumps(tree))

    # 2. Update top 5 books for each of 11 parent categories
    for parent_id in ["education", "business", "technology", ...]:
        books = get_top_5_books_for_category(parent_id)
        await redis_client.setex(f"books:top:category:{parent_id}", 1800, json.dumps(books))
```

**Benefits:**
- ✅ Cache always warm (100% cache hit rate)
- ✅ Users never wait for slow queries
- ✅ Response time: **< 10ms** (Redis lookup only)
- ✅ Category navigation instant (no 33 count queries)

---

## 📈 Performance Impact Estimates

| Endpoint | Current | After Cache | Improvement |
|----------|---------|-------------|-------------|
| **Category Tree** | 600ms (33 counts) | **10ms** | **60x faster** |
| **Top 5 per Category** | 400ms | **10ms** | **40x faster** |
| Trending Today | 1500ms | **10ms** | **150x faster** |
| Featured Week | 2000ms | **10ms** | **200x faster** |
| Latest Books | 800ms | **10ms** | **80x faster** |
| Top Books | 600ms | **10ms** | **60x faster** |
| Featured Authors | 1200ms | **10ms** | **120x faster** |
| Popular Tags | 500ms | **10ms** | **50x faster** |

**Homepage Load Analysis:**

**Before Caching:**
```
Category Tree:        600ms (33 MongoDB count queries)
Top 5 × 11 categories: 4400ms (11 requests × 400ms each)
Trending Today:       1500ms
Featured Authors:     1200ms
Popular Tags:         500ms
──────────────────────────────
TOTAL (parallel):     ~2500ms (bottleneck: Top 5 categories if loaded sequentially)
```

**After Caching:**
```
Category Tree:        10ms (Redis lookup)
Top 5 × 11 categories: 110ms (11 requests × 10ms each, or 10ms if batched)
Trending Today:       10ms
Featured Authors:     10ms
Popular Tags:         10ms
──────────────────────────────
TOTAL:                ~50ms (95% improvement!)
```

**Overall Page Load:**
- Before: 2-5 seconds (unacceptable)
- After: **< 100ms** (excellent UX)

---

## 🗂️ MongoDB Indexes Required

**CRITICAL:** Cache only reduces load. First request (cache miss) still hits DB.

### Required Indexes

```javascript
// 1. Community books - views sorting
db.online_books.createIndex({
    "community_config.is_public": 1,
    "community_config.total_views": -1,
    "deleted_at": 1
});

// 2. Community books - latest updates
db.online_books.createIndex({
    "community_config.is_public": 1,
    "community_config.last_chapter_updated_at": -1,
    "deleted_at": 1
});

// 3. Community books - by category
db.online_books.createIndex({
    "community_config.is_public": 1,
    "community_config.category": 1,
    "deleted_at": 1
});

// 4. Community books - by tags
db.online_books.createIndex({
    "community_config.is_public": 1,
    "community_config.tags": 1,
    "deleted_at": 1
});

// 5. View sessions - trending analysis
db.book_view_sessions.createIndex({
    "viewed_at": -1,
    "book_id": 1
});

// 6. Purchases - featured analysis
db.book_purchases.createIndex({
    "purchased_at": -1,
    "book_id": 1
});

// 7. Authors - lookup
db.book_authors.createIndex({
    "author_id": 1
});

// 8. Chapters - per book
db.book_chapters.createIndex({
    "book_id": 1,
    "deleted_at": 1,
    "updated_at": -1
});
```

---

## 🔄 Cache Invalidation Strategy

### Write-Through Pattern

**When book is updated:**
```python
# Update database
db.online_books.update_one({...})

# Invalidate related caches
await redis_client.delete("books:newest:all")
await redis_client.delete("books:top:all")
await redis_client.delete(f"books:search:*")  # Delete all search caches
```

**When new chapter is added:**
```python
# Update database
db.book_chapters.insert_one({...})

# Invalidate latest books cache
await redis_client.delete("books:newest:all")
```

---

## 📦 Redis Data Structures

### Book List Cache (JSON String)

```json
{
  "books": [
    {
      "book_id": "abc123",
      "title": "Sample Book",
      "cover_url": "https://...",
      "authors": ["author1"],
      "author_names": ["John Doe"],
      "total_views": 5000,
      "total_chapters": 25,
      "recent_chapters": [...]
    }
  ],
  "total": 100,
  "cached_at": "2026-02-09T10:00:00Z",
  "ttl": 900
}
```

---

## � Docker & Infrastructure Setup

### Redis Container Configuration

**Recommended Approach:** ✅ **Separate Redis Docker Container**

**Why Separate Container?**
1. ✅ **Isolation:** Redis crashes won't affect main app
2. ✅ **Resource Control:** Limit RAM/CPU specifically for cache
3. ✅ **Scalability:** Easy to upgrade Redis version or add Redis Cluster
4. ✅ **Monitoring:** Dedicated metrics for cache performance
5. ✅ **Backup/Recovery:** Independent persistence configuration

**Docker Compose Configuration:**
```yaml
services:
  # Existing services...
  ai-chatbot-rag:
    image: lekompozer/wordai-aiservice:latest
    container_name: ai-chatbot-rag
    # ... existing config

  # NEW: Redis Cache Service
  redis-cache:
    image: redis:7-alpine
    container_name: redis-cache
    restart: unless-stopped
    command: redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru
    ports:
      - "6380:6379"  # Different port from redis-server (6379)
    volumes:
      - redis-cache-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
        reservations:
          memory: 256M
          cpus: '0.25'

volumes:
  redis-cache-data:
    driver: local
```

**Connection in Python:**
```python
# src/cache/redis_client.py
import redis.asyncio as redis

class RedisCacheClient:
    def __init__(self):
        self.client = redis.from_url(
            "redis://redis-cache:6379/0",  # Different from job queue Redis
            encoding="utf-8",
            decode_responses=True
        )
```

---

### RAM Requirements Analysis

#### Current System (Production Server: 8GB RAM)
```
Total RAM: 7.8GB
├─ ai-chatbot-rag: 1.9GB (main app)
├─ mongodb: 210MB
├─ redis-server: 5MB (job queue only)
├─ nginx: 5MB
├─ payment-service: 40MB
├─ Workers (10 containers): ~3.6GB (STOPPED during crawl)
└─ Available: ~1.5GB (with workers stopped)
```

#### Redis Cache RAM Calculation

**Cache Data Size Estimates:**

| Cache Type | Items | Size per Item | Total Size |
|------------|-------|---------------|------------|
| **Category Tree** | 1 key | 20KB (33 categories × 600B) | 20KB |
| **Top 5 per Category** | 11 keys | 15KB (5 books × 3KB) | 165KB |
| **Trending Today** | 1 key | 15KB (5 books) | 15KB |
| **Featured Week** | 1 key | 9KB (3 books) | 9KB |
| **Latest Books** | 1 key | 60KB (20 books) | 60KB |
| **Top Books** | 1 key | 30KB (10 books) | 30KB |
| **Featured Authors** | 1 key | 30KB (10 authors) | 30KB |
| **Popular Tags** | 1 key | 5KB (25 tags) | 5KB |
| **Search Results Cache** | ~100 keys | 60KB avg | 6MB |
| **User Caches** | ~1000 users × 3 keys | 10KB avg | 30MB |
| **Overhead (Redis)** | - | - | 50MB |

**Total Cache Size:** ~37MB (conservatively estimate **50-100MB** with growth)

**Recommended RAM Allocation:**

```
Redis Cache Container:
├─ Cache Data: ~100MB (current)
├─ Growth Buffer: +200MB (for 10,000+ books)
├─ Redis Overhead: +50MB
├─ Safety Margin: +150MB
└─ TOTAL: 512MB (recommended)
```

**Memory Policy:** `allkeys-lru` (Least Recently Used eviction)
- When RAM limit reached, Redis automatically evicts oldest cached data
- Ensures cache never crashes due to OOM
- Most popular data always stays in memory

---

### Production Server Impact

**Current State (Workers Stopped):**
```
Available RAM: 5.2GB (after stopping 10 workers)
```

**After Adding Redis Cache (512MB):**
```
Total RAM: 7.8GB
├─ ai-chatbot-rag: 1.9GB
├─ mongodb: 210MB
├─ redis-server: 5MB (jobs)
├─ redis-cache: 512MB ⬅️ NEW
├─ nginx: 5MB
├─ payment-service: 40MB
├─ System: ~300MB
└─ Available: ~4.6GB (enough for 7-8 crawlers)
```

**Verdict:** ✅ **Safe to deploy** - Still have 4.6GB for crawlers

---

### Alternative: Share Existing Redis?

**Current `redis-server` container:**
- Purpose: Job queue (test generation, slide narration, etc.)
- Usage: ~5MB RAM (very light)
- DB: Database 0 (job status hashes)

**Could we reuse it?** 🟡 **Yes, but NOT recommended**

**Pros:**
- ✅ No extra container
- ✅ Save ~10MB RAM overhead

**Cons:**
- ❌ **Single Point of Failure:** Cache + jobs share same Redis
- ❌ **No Resource Limits:** Cache could starve job queue
- ❌ **Monitoring Confusion:** Can't separate cache vs job metrics
- ❌ **Eviction Risk:** allkeys-lru could evict job status data

**Recommendation:** 🔴 **Use separate container** (costs only 512MB, worth the isolation)

---

### Redis Cluster (Future Scaling)

**When to consider Redis Cluster?**
- ❌ **Not needed now** (< 1000 books)
- ✅ **Consider at 10,000+ books** (cache > 1GB)
- ✅ **Consider for 100+ concurrent users** (high read load)

**Benefits of Cluster:**
- Distributed RAM (multiple nodes)
- High availability (automatic failover)
- Read replicas (scale read throughput)

**Cost:** 3-5 Redis nodes × 512MB = 1.5-2.5GB RAM

---

## �🚦 Success Metrics

**Before Redis (Current):**
- ❌ Page load: 2-5 seconds
- ❌ Database queries per page: 50-100+
- ❌ Database CPU: 60-80%
- ❌ User experience: Poor (high bounce rate)

**After Redis (Target):**
- ✅ Page load: **< 500ms**
- ✅ Database queries per page: **0-5** (cache hits)
- ✅ Database CPU: **< 20%**
- ✅ User experience: Excellent (instant loads)

---

## 📝 Implementation Checklist

### Week 1: Setup & Critical Endpoints
- [ ] Install Redis container in docker-compose
### Week 1: Setup & Critical Endpoints
- [ ] **Setup Redis Container**
  - [ ] Add `redis-cache` service to docker-compose.yml
  - [ ] Configure: 512MB RAM limit, allkeys-lru policy
  - [ ] Expose port 6380 (separate from job queue Redis on 6379)
  - [ ] Test connection from main app
- [ ] Create Redis client wrapper (`src/cache/redis_client.py`)
- [ ] Add MongoDB indexes:
  - [ ] `community_config.category` (for category filtering)
  - [ ] `community_config.parent_category` (for parent category queries)
  - [ ] `viewed_at` on book_view_sessions (for trending)
  - [ ] `purchased_at` on book_purchases (for featured)
- [ ] **Implement Critical Caches:**
  - [ ] `/books/trending-today` (15 min TTL)
  - [ ] `/books/featured-week` (30 min TTL)
  - [ ] `/book-categories/` - Category tree (10 min TTL)
- [ ] Test cache hit/miss rates
- [ ] Monitor response times

### Week 2: Category & High-Traffic Endpoints
- [ ] **Category Caching:**
  - [ ] `/book-categories/parent/{id}` - Top 5 books per category (30 min TTL)
  - [ ] Create 11 cache keys (one per parent category)
  - [ ] Test category navigation speed
- [ ] **General List Caching:**
  - [ ] `/books/latest` (20 min TTL)
  - [ ] `/books/top` (1 hour TTL)
  - [ ] `/books/search` (10 min TTL with query hash)
- [ ] Add cache metrics to monitoring
- [ ] Test invalidation on new book publish

### Week 3: Static Data & Authors
- [ ] Implement cache for `/authors/featured` (24 hour TTL)
- [ ] Implement cache for `/tags/popular` (24 hour TTL)
- [ ] Add cache invalidation triggers:
  - [ ] On new book: Clear `books:newest:all`, `categories:tree:all`
  - [ ] On book update: Clear related category cache
  - [ ] On new chapter: Clear parent book's category cache
- [ ] Document cache invalidation patterns

### Week 4: Background Jobs & Optimization
- [ ] **Create Cronjob Worker** (`worker/cache_updater.py`)
  - [ ] Trending Today: Update every 15 minutes
  - [ ] Featured Week: Update every 30 minutes
  - [ ] Category Tree: Update every 30 minutes
  - [ ] Top 5 per Category: Update all 11 keys every 30 minutes
  - [ ] Authors/Tags: Update daily
- [ ] Add cronjob to docker-compose (or use external scheduler)
- [ ] Monitor cache hit rates (target: > 95%)
- [ ] Performance testing:
  - [ ] Simulate 100 concurrent users
  - [ ] Measure cache hit rate under load
  - [ ] Test cache eviction behavior at 512MB limit
- [ ] Optimization & fine-tuning

---

## 🎓 Best Practices

### 1. Always Set TTL
```python
# ❌ BAD - Never expires (memory leak)
await redis_client.set(key, value)

# ✅ GOOD - Auto-expires
await redis_client.setex(key, ttl_seconds, value)
```

### 2. Handle Cache Misses Gracefully
```python
cached = await redis_client.get(key)
if cached:
    return json.loads(cached)

# Fallback to database
data = fetch_from_database()

# Update cache for next time
await redis_client.setex(key, ttl, json.dumps(data))
return data
```

### 3. Use Cache Aside Pattern
- Application checks cache first
- On miss: Fetch from DB + update cache
- On hit: Return cached data directly

### 4. Category Cache Batch Update
```python
# ✅ GOOD - Update all category caches in one job
async def update_all_category_caches():
    for parent_id in PARENT_CATEGORY_IDS:
        books = await get_top_5_books(parent_id)
        await redis_client.setex(
            f"books:top:category:{parent_id}",
            1800,  # 30 min
            json.dumps(books)
        )
```

### 5. Monitor Cache Hit Rate
```python
# Target: > 95% hit rate
cache_hits / (cache_hits + cache_misses) > 0.95
```

---

## 🔗 Related Documents

- [SYSTEM_REFERENCE.md](/SYSTEM_REFERENCE.md) - Redis connection patterns
- [REDIS_STATUS_PATTERN.md](/REDIS_STATUS_PATTERN.md) - Job status caching
- [book_category_routes.py](src/api/book_category_routes.py) - Category endpoints
- [community_routes.py](src/api/community_routes.py) - All endpoints analyzed above

---

**Next Steps:**
1. Review this document with team
2. Estimate development time (2-4 weeks)
3. Start with Phase 1 (Critical endpoints)
4. Deploy incrementally and monitor

**Expected Outcome:**
- 10-200x faster response times
- 90% reduction in database load
- Improved user experience and SEO
- System ready to scale to 10,000+ books
