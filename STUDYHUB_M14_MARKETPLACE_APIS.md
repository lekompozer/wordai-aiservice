# StudyHub M1.4: Marketplace APIs

## Tổng quan

M1.4 cung cấp **12 APIs** cho việc khám phá, duyệt, tìm kiếm subjects trong marketplace công khai, tương tự như Community Books.

**Pattern**: Read-only marketplace (không có POST endpoints) - người dùng chỉ browse và discover subjects.

---

## APIs Marketplace

### 1. Search & Filter Subjects 🔍
**GET** `/api/studyhub/marketplace/subjects/search`

**Mục đích**: Tìm kiếm và lọc subjects trong marketplace

**Query Parameters**:
```
q: string (optional) - Search keyword (title or creator name)
category: string (optional) - Filter by category
tags: string (optional) - Comma-separated tags
level: string (optional) - beginner/intermediate/advanced
sort_by: string - updated/views/rating/newest (default: updated)
skip: integer - Pagination offset (default: 0)
limit: integer - Items per page (max: 100, default: 20)
```

**Response Model**:
```json
{
  "subjects": [
    {
      "id": "subject_id",
      "title": "Subject Title",
      "description": "Subject description",
      "cover_image_url": "https://...",
      "owner": {
        "user_id": "creator_id",
        "display_name": "Creator Name",
        "avatar_url": "https://..."
      },
      "category": "Programming",
      "tags": ["Python", "Machine Learning"],
      "level": "intermediate",
      "stats": {
        "total_modules": 10,
        "total_learners": 234,
        "total_views": 1234,
        "average_rating": 4.5,
        "completion_rate": 0.78
      },
      "last_updated_at": "2026-01-08T10:00:00Z",
      "created_at": "2025-12-01T10:00:00Z"
    }
  ],
  "total": 156,
  "skip": 0,
  "limit": 20
}
```

**Business Logic**:
- Full-text search trên `title` và `owner.display_name`
- Chỉ hiển thị subjects có `is_public_marketplace=true` và `status=published`
- Sort options:
  - `updated`: last_updated_at DESC
  - `views`: total_views DESC
  - `rating`: average_rating DESC
  - `newest`: created_at DESC

---

### 2. Latest Subjects 🆕
**GET** `/api/studyhub/marketplace/subjects/latest`

**Mục đích**: Hiển thị subjects mới cập nhật (2x10 grid)

**Query Parameters**:
```
category: string (optional)
tags: string (optional) - Comma-separated
skip: integer (default: 0)
limit: integer (default: 20)
```

**Response Model**: Giống Search API

**Business Logic**:
- Sort by `last_updated_at DESC`
- Default limit: 20 (2 columns x 10 rows grid)

---

### 3. Top Subjects 🏆
**GET** `/api/studyhub/marketplace/subjects/top`

**Mục đích**: Top 10 subjects được xem/học nhiều nhất

**Query Parameters**:
```
category: string (optional)
tags: string (optional)
limit: integer (default: 10, max: 50)
```

**Response Model**: Giống Search API

**Business Logic**:
- Sort by `total_views DESC` hoặc `total_learners DESC`
- Default limit: 10

---

### 4. Featured Subjects of Week ⭐
**GET** `/api/studyhub/marketplace/subjects/featured-week`

**Mục đích**: 3 subjects nổi bật trong tuần

**Query Parameters**: None

**Response Model**:
```json
{
  "featured_subjects": [
    {
      "id": "subject_id",
      "title": "Featured Subject",
      "cover_image_url": "https://...",
      "owner": {...},
      "stats": {...},
      "reason": "most_viewed_week" // hoặc "most_enrolled_week"
    }
  ]
}
```

**Business Logic**:
- **2 subjects** có views cao nhất trong 7 ngày qua
- **1 subject** có enrollments nhiều nhất trong 7 ngày qua
- Tracking: Cần collection `studyhub_subject_views` để track daily views

---

### 5. Trending Today 🔥
**GET** `/api/studyhub/marketplace/subjects/trending-today`

**Mục đích**: 5 subjects trending hôm nay (24h)

**Query Parameters**: None

**Response Model**:
```json
{
  "trending_subjects": [
    {
      "id": "subject_id",
      "title": "Trending Subject",
      "cover_image_url": "https://...",
      "owner": {...},
      "stats": {...},
      "views_today": 156
    }
  ]
}
```

**Business Logic**:
- Lấy subjects có `views_today` cao nhất
- Cần field `views_today` trong `studyhub_subjects`
- Reset daily counter mỗi ngày

---

### 6. Featured Creators 👥
**GET** `/api/studyhub/marketplace/creators/featured`

**Mục đích**: 10 creators nổi bật (homepage slider)

**Query Parameters**: None

**Response Model**:
```json
{
  "featured_creators": [
    {
      "user_id": "creator_id",
      "display_name": "Creator Name",
      "avatar_url": "https://...",
      "bio": "Creator bio...",
      "stats": {
        "total_subjects": 15,
        "total_students": 2345,
        "total_reads": 12345,
        "average_rating": 4.7
      },
      "top_subject": {
        "id": "subject_id",
        "title": "Top Subject",
        "cover_image_url": "https://..."
      },
      "reason": "most_reads" // hoặc "best_reviews" hoặc "top_subject"
    }
  ]
}
```

**Business Logic**:
- **3 creators** có tổng views cao nhất (sum of all subjects)
- **3 creators** có ratings tốt nhất (avg rating + review count)
- **4 creators** có subject views cao nhất (max views của 1 subject)
- Sử dụng MongoDB aggregation pipeline

---

### 7. Popular Tags 🏷️
**GET** `/api/studyhub/marketplace/tags/popular`

**Mục đích**: 25 tags phổ biến nhất

**Query Parameters**: None

**Response Model**:
```json
{
  "popular_tags": [
    {
      "tag": "Python",
      "count": 45
    },
    {
      "tag": "Machine Learning",
      "count": 38
    }
  ]
}
```

**Business Logic**:
- Aggregate từ field `tags` trong `studyhub_subjects`
- Sort by count DESC
- Limit 25

---

### 8. Popular Categories 📁
**GET** `/api/studyhub/marketplace/categories/popular`

**Mục đích**: Danh sách categories với số lượng subjects

**Query Parameters**: None

**Response Model**:
```json
{
  "categories": [
    {
      "name": "Programming",
      "count": 123,
      "icon": "💻",
      "description": "Learn programming languages"
    },
    {
      "name": "Business",
      "count": 87,
      "icon": "💼",
      "description": "Business and entrepreneurship"
    }
  ]
}
```

**Business Logic**:
- Aggregate từ field `category` trong `studyhub_subjects`
- Sort by count DESC
- Return all categories

---

### 9. Subject Public View 👁️
**GET** `/api/studyhub/marketplace/subjects/{subject_id}`

**Mục đích**: Xem chi tiết subject trong marketplace (track views)

**Path Parameters**:
```
subject_id: string
```

**Response Model**:
```json
{
  "id": "subject_id",
  "title": "Subject Title",
  "description": "Full description...",
  "cover_image_url": "https://...",
  "owner": {
    "user_id": "creator_id",
    "display_name": "Creator Name",
    "avatar_url": "https://...",
    "bio": "Creator bio"
  },
  "category": "Programming",
  "tags": ["Python", "ML"],
  "level": "intermediate",
  "modules": [
    {
      "id": "module_id",
      "title": "Module 1",
      "description": "Module desc",
      "order_index": 1,
      "content_count": 5,
      "is_preview": true
    }
  ],
  "stats": {
    "total_modules": 10,
    "total_contents": 45,
    "total_learners": 234,
    "total_views": 1234,
    "average_rating": 4.5,
    "completion_rate": 0.78,
    "estimated_duration_hours": 20
  },
  "pricing": {
    "is_free": true,
    "price": 0
  },
  "created_at": "2025-12-01T10:00:00Z",
  "last_updated_at": "2026-01-08T10:00:00Z"
}
```

**Business Logic**:
- Track view: Increment `total_views` và `views_today`
- Chỉ hiển thị nếu `is_public_marketplace=true`
- Show preview modules (first 2 modules hoặc modules có `is_preview=true`)

---

### 10. Related Subjects 🔗
**GET** `/api/studyhub/marketplace/subjects/{subject_id}/related`

**Mục đích**: Subjects liên quan (same category/tags)

**Path Parameters**:
```
subject_id: string
```

**Query Parameters**:
```
limit: integer (default: 5, max: 20)
```

**Response Model**:
```json
{
  "related_subjects": [
    {
      "id": "subject_id",
      "title": "Related Subject",
      "cover_image_url": "https://...",
      "owner": {...},
      "stats": {...},
      "similarity_score": 0.85
    }
  ]
}
```

**Business Logic**:
- Tìm subjects có `category` giống
- Hoặc có ít nhất 2 tags trùng khớp
- Sort by similarity score DESC
- Exclude subject hiện tại

---

### 11. Creator Profile 👤
**GET** `/api/studyhub/marketplace/creators/{creator_id}/profile`

**Mục đích**: Xem profile creator trong marketplace

**Path Parameters**:
```
creator_id: string (user_id)
```

**Response Model**:
```json
{
  "user_id": "creator_id",
  "display_name": "Creator Name",
  "avatar_url": "https://...",
  "bio": "Creator bio...",
  "website": "https://...",
  "social_links": {
    "twitter": "...",
    "github": "..."
  },
  "stats": {
    "total_subjects": 15,
    "total_students": 2345,
    "total_views": 12345,
    "average_rating": 4.7,
    "total_reviews": 234
  },
  "featured_subjects": [
    {
      "id": "subject_id",
      "title": "Top Subject",
      "cover_image_url": "https://...",
      "stats": {...}
    }
  ],
  "joined_at": "2024-06-15T10:00:00Z"
}
```

**Business Logic**:
- Aggregate stats từ tất cả public subjects của creator
- Featured subjects: Top 3 subjects by views/enrollments

---

### 12. Creator Subjects 📚
**GET** `/api/studyhub/marketplace/creators/{creator_id}/subjects`

**Mục đích**: Danh sách tất cả subjects của creator

**Path Parameters**:
```
creator_id: string
```

**Query Parameters**:
```
skip: integer (default: 0)
limit: integer (default: 20)
sort_by: string - views/rating/newest (default: views)
```

**Response Model**: Giống Search API

**Business Logic**:
- Chỉ hiển thị public subjects của creator
- Sort theo query parameter

---

## Database Schema Changes

### studyhub_subjects (Extended)

Cần thêm các fields cho marketplace:

```javascript
{
  // ... existing fields ...

  // Marketplace metadata
  is_public_marketplace: Boolean, // true nếu hiển thị trên marketplace
  category: String, // "Programming", "Business", etc.
  tags: [String], // ["Python", "Machine Learning"]
  level: String, // "beginner", "intermediate", "advanced"

  // Stats
  total_views: Number, // Tổng lượt xem (all time)
  views_today: Number, // Lượt xem hôm nay (reset daily)
  views_this_week: Number, // Lượt xem tuần này (reset weekly)

  // Timing
  last_updated_at: DateTime, // Cập nhật khi có module/content mới
}
```

### New Collection: studyhub_subject_views

Track chi tiết views theo ngày:

```javascript
{
  _id: ObjectId,
  subject_id: ObjectId,
  date: DateTime, // Ngày (00:00:00)
  views_count: Number,
  unique_users: [ObjectId], // Track unique viewers
}
```

**Indexes**:
```javascript
db.studyhub_subject_views.createIndex({ subject_id: 1, date: -1 })
db.studyhub_subject_views.createIndex({ date: -1 })
```

---

## MongoDB Indexes for Marketplace

```javascript
// studyhub_subjects indexes
db.studyhub_subjects.createIndex({
  is_public_marketplace: 1,
  status: 1,
  last_updated_at: -1
})

db.studyhub_subjects.createIndex({
  is_public_marketplace: 1,
  total_views: -1
})

db.studyhub_subjects.createIndex({
  is_public_marketplace: 1,
  average_rating: -1
})

db.studyhub_subjects.createIndex({
  category: 1,
  is_public_marketplace: 1
})

db.studyhub_subjects.createIndex({
  tags: 1,
  is_public_marketplace: 1
})

// Text search index
db.studyhub_subjects.createIndex({
  title: "text",
  description: "text"
})

// Trending indexes
db.studyhub_subjects.createIndex({
  views_today: -1,
  is_public_marketplace: 1
})

db.studyhub_subjects.createIndex({
  views_this_week: -1,
  is_public_marketplace: 1
})
```

---

## Implementation Files

### 1. Models (studyhub_models.py)

Thêm models mới:

```python
# Marketplace models
class MarketplaceSubjectItem(BaseModel):
    id: str
    title: str
    description: str
    cover_image_url: Optional[str]
    owner: OwnerInfo
    category: str
    tags: List[str]
    level: str
    stats: SubjectStats
    last_updated_at: datetime
    created_at: datetime

class MarketplaceSubjectsResponse(BaseModel):
    subjects: List[MarketplaceSubjectItem]
    total: int
    skip: int
    limit: int

class FeaturedCreatorItem(BaseModel):
    user_id: str
    display_name: str
    avatar_url: Optional[str]
    bio: Optional[str]
    stats: CreatorStats
    top_subject: Optional[SubjectPreview]
    reason: str

class PopularTagItem(BaseModel):
    tag: str
    count: int

class CategoryItem(BaseModel):
    name: str
    count: int
    icon: str
    description: str
```

### 2. Manager (studyhub_marketplace_manager.py)

```python
class StudyHubMarketplaceManager:
    def __init__(self):
        self.db_manager = DBManager()
        self.db = self.db_manager.db

    async def search_subjects(self, q, category, tags, level, sort_by, skip, limit):
        """Search and filter marketplace subjects"""
        pass

    async def get_latest_subjects(self, category, tags, skip, limit):
        """Get latest updated subjects"""
        pass

    async def get_top_subjects(self, category, tags, limit):
        """Get top viewed subjects"""
        pass

    async def get_featured_week(self):
        """Get 3 featured subjects of week"""
        pass

    async def get_trending_today(self):
        """Get 5 trending subjects today"""
        pass

    async def get_featured_creators(self):
        """Get 10 featured creators"""
        pass

    async def get_popular_tags(self):
        """Get 25 popular tags"""
        pass

    async def get_popular_categories(self):
        """Get all categories with counts"""
        pass

    async def get_subject_public_view(self, subject_id):
        """Get public subject view + track"""
        pass

    async def get_related_subjects(self, subject_id, limit):
        """Get related subjects"""
        pass

    async def get_creator_profile(self, creator_id):
        """Get creator profile"""
        pass

    async def get_creator_subjects(self, creator_id, skip, limit, sort_by):
        """Get creator's subjects"""
        pass
```

### 3. Routes (studyhub_marketplace_routes.py)

```python
from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/studyhub/marketplace", tags=["StudyHub Marketplace"])

@router.get("/subjects/search")
async def search_subjects(...):
    pass

@router.get("/subjects/latest")
async def get_latest_subjects(...):
    pass

# ... 10 more endpoints
```

---

## Testing Checklist

- [ ] Search với multi filters
- [ ] Pagination working
- [ ] Sort options working
- [ ] View tracking increments correctly
- [ ] Featured week algorithm correct
- [ ] Trending today resets daily
- [ ] Creator aggregation stats correct
- [ ] Tags aggregation correct
- [ ] Categories aggregation correct
- [ ] Related subjects similarity working
- [ ] Public subjects only (no private)
- [ ] Text search working

---

**Document Version**: 1.0
**Created**: January 8, 2026
**Pattern**: Similar to Community Books marketplace
**Total APIs**: 12 (all GET - read-only marketplace)
