# StudyHub Category & Course System - Complete API Documentation

**Status:** Implemented ✅
**Version:** 2.0.0
**Date:** January 15, 2026

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [API Endpoints](#api-endpoints)
   - [Categories](#categories)
   - [Category Subjects](#category-subjects)
   - [Courses](#courses)
   - [Enrollment & Progress](#enrollment--progress)
   - [Community Homepage](#community-homepage)
4. [Database Collections](#database-collections)
5. [Models & Schemas](#models--schemas)
6. [Business Logic](#business-logic)
7. [Examples](#examples)

---

## Overview

The Category & Course System enables:

1. **Fixed 10 Categories** - IT, Business, Finance, Certificates, Languages, Personal Development, Lifestyle, Academics, Science, Skills
2. **User-Created Subjects** - Users can create subjects within categories (with admin approval)
3. **Course Publishing** - Users publish their private subjects as public courses
4. **Community Discovery** - Search, filter, browse top/trending courses
5. **Enrollment & Progress** - Track learning progress, ratings, completion

---

## Architecture

```
Category (10 fixed)
  └── CategorySubject (user-creatable, admin-approved)
      └── Course (user's published subject)
          └── Modules (copied from source subject)
              └── Contents (linked from source)
```

### Key Concepts

- **Category**: Fixed list of 10 top-level categories
- **CategorySubject**: Subject definitions within a category (e.g., "Python Programming" in IT)
- **Course**: A published user subject mapped to a CategorySubject
- **Source Subject**: The user's original private subject (from studyhub_subjects)
- **Enrollment**: User enrollment in a course with progress tracking

---

## API Endpoints

### Categories

#### 1. List All Categories

```http
GET /api/studyhub/categories
```

**Response:**
```json
{
  "categories": [
    {
      "category_id": "it",
      "name_en": "Information Technology",
      "name_vi": "Công nghệ thông tin",
      "icon": "Code",
      "description_en": "Programming, Software Development, IT Infrastructure",
      "description_vi": "Lập trình, Phát triển phần mềm, Hạ tầng CNTT",
      "order_index": 1,
      "is_active": true,
      "stats": {
        "subject_count": 45,
        "course_count": 152,
        "total_learners": 12500,
        "total_enrollments": 15600,
        "average_rating": 4.6,
        "total_content_hours": 1250
      }
    }
  ]
}
```

#### 2. Get Category Details

```http
GET /api/studyhub/categories/{category_id}
```

**Parameters:**
- `category_id`: One of 10 fixed categories (it, business, finance, etc.)

**Response:**
```json
{
  "category": { /* category object */ },
  "stats": { /* category stats */ },
  "top_subjects": [
    {
      "_id": "507f1f77bcf86cd799439011",
      "category_id": "it",
      "subject_name_en": "Python Programming",
      "subject_name_vi": "Lập trình Python",
      "slug": "python-programming",
      "course_count": 15,
      "total_learners": 1250,
      "approved": true
    }
  ]
}
```

#### 3. Get Category Statistics

```http
GET /api/studyhub/categories/{category_id}/stats
```

**Response:**
```json
{
  "category_id": "it",
  "stats": {
    "subject_count": 45,
    "course_count": 152,
    "total_learners": 12500,
    "total_enrollments": 15600,
    "average_rating": 4.6,
    "total_content_hours": 1250
  },
  "top_instructors": [
    {
      "user_id": "firebase_uid",
      "display_name": "John Doe",
      "profile_image": "https://...",
      "course_count": 5,
      "total_learners": 850,
      "average_rating": 4.8
    }
  ]
}
```

---

### Category Subjects

#### 4. List Subjects in Category

```http
GET /api/studyhub/categories/{category_id}/subjects?page=1&limit=20&sort=popular
```

**Query Parameters:**
- `page` (int): Page number (default: 1)
- `limit` (int): Items per page (default: 20, max: 100)
- `sort` (string): Sort by `popular`, `newest`, or `name` (default: popular)

**Response:**
```json
{
  "subjects": [
    {
      "_id": "...",
      "category_id": "it",
      "subject_name_en": "Python Programming",
      "subject_name_vi": "Lập trình Python",
      "description_en": "Learn Python from scratch",
      "description_vi": "Học Python từ đầu",
      "slug": "python-programming",
      "created_by": "user",
      "creator_id": "firebase_uid",
      "approved": true,
      "course_count": 15,
      "total_learners": 1250,
      "created_at": "2026-01-15T10:00:00Z",
      "updated_at": "2026-01-15T10:00:00Z"
    }
  ],
  "total": 45,
  "page": 1,
  "limit": 20,
  "total_pages": 3
}
```

#### 5. Create Category Subject

```http
POST /api/studyhub/categories/{category_id}/subjects
Authorization: Bearer {firebase_token}
```

**Request Body:**
```json
{
  "subject_name_en": "Python Programming",
  "subject_name_vi": "Lập trình Python",
  "description_en": "Learn Python from basics to advanced",
  "description_vi": "Học Python từ cơ bản đến nâng cao"
}
```

**Response:**
```json
{
  "subject": {
    "_id": "...",
    "category_id": "it",
    "subject_name_en": "Python Programming",
    "subject_name_vi": "Lập trình Python",
    "slug": "python-programming",
    "created_by": "user",
    "creator_id": "firebase_uid",
    "approved": false,  // Needs admin approval
    "course_count": 0,
    "total_learners": 0
  }
}
```

**Business Rules:**
- Slug auto-generated from `subject_name_en`
- Must be unique within category
- User-created subjects need admin approval
- Admin-created subjects auto-approved

#### 6. Search Category Subjects

```http
GET /api/studyhub/category-subjects/search?q=python&page=1&limit=20
```

**Query Parameters:**
- `q` (string, required): Search query (min 2 chars)
- `page`, `limit`: Pagination

**Searches In:**
- `subject_name_en`
- `subject_name_vi`
- `description_en`
- `description_vi`

---

### Courses

#### 7. Publish Subject as Course

```http
POST /api/studyhub/subjects/{subject_id}/publish-course
Authorization: Bearer {firebase_token}
```

**Request Body:**
```json
{
  "category_id": "it",
  "category_subject_id": "507f1f77bcf86cd799439011",  // Or null to create new

  // If category_subject_id is null:
  "new_subject_name_en": "Advanced Python",
  "new_subject_name_vi": "Python Nâng cao",
  "new_subject_description_en": "...",
  "new_subject_description_vi": "...",

  // Course details
  "title": "Python Programming - Complete Guide 2026",
  "description": "Master Python from basics to advanced topics...",
  "cover_image_url": "https://...",
  "level": "beginner",  // beginner | intermediate | advanced
  "language": "vi",

  // Pricing
  "price_type": "free",  // free | paid
  "price_points": 0,

  // Metadata
  "tags": ["python", "programming", "beginner"],
  "what_you_will_learn": [
    "Python basics and syntax",
    "Object-Oriented Programming",
    "Web development with Django"
  ],
  "requirements": [
    "Computer with internet",
    "Basic computer skills"
  ],
  "target_audience": [
    "Beginners",
    "Students",
    "Career switchers"
  ]
}
```

**Response:**
```json
{
  "course_id": "507f1f77bcf86cd799439011",
  "status": "pending",
  "message": "Course submitted for approval"
}
```

**Business Rules:**
- Must own the source subject
- Cannot publish same subject twice
- Course status: `pending` (needs admin approval)
- If creating new category subject, it also needs approval
- Modules copied from source subject
- Free courses cannot have price > 0
- Paid courses must have price > 0

#### 8. Get Course Details

```http
GET /api/studyhub/courses/{course_id}
Authorization: Bearer {firebase_token} (optional)
```

**Response:**
```json
{
  "course": {
    "_id": "...",
    "category_id": "it",
    "category_subject_id": "...",
    "source_subject_id": "...",
    "user_id": "firebase_uid",
    "title": "Python Programming - Complete Guide",
    "description": "Master Python...",
    "cover_image_url": "https://...",
    "language": "vi",
    "level": "beginner",
    "price_type": "free",
    "price_points": 0,
    "module_count": 10,
    "total_content_count": 45,
    "estimated_duration_hours": 20,
    "stats": {
      "enrollment_count": 142,
      "completion_count": 89,
      "completion_rate": 62.68,
      "average_rating": 4.7,
      "rating_count": 56,
      "view_count": 1250
    },
    "status": "approved",
    "visibility": "public",
    "published_at": "2026-01-10T00:00:00Z",
    "tags": ["python", "programming"],
    "what_you_will_learn": [...],
    "requirements": [...],
    "target_audience": [...]
  },
  "category": { /* category object */ },
  "category_subject": { /* subject object */ },
  "instructor": {
    "user_id": "...",
    "display_name": "John Doe",
    "profile_image": "https://..."
  },
  "modules": [
    {
      "module_id": "...",
      "title": "Introduction to Python",
      "content_count": 5,
      "order_index": 1
    }
  ],
  "is_enrolled": false,
  "can_enroll": true,
  "enrollment_id": null
}
```

#### 9. List Courses

```http
GET /api/studyhub/courses?category_id=it&level=beginner&sort=popular&page=1&limit=20
```

**Query Parameters:**
- `category_id` (string): Filter by category
- `category_subject_id` (string): Filter by subject
- `level` (string): beginner | intermediate | advanced
- `price_type` (string): free | paid
- `language` (string): Course language (vi | en)
- `min_rating` (float): Minimum rating (0-5)
- `free_only` (boolean): Show only free courses
- `sort` (string): popular | newest | highest-rated | trending
- `page`, `limit`: Pagination

**Response:**
```json
{
  "courses": [ /* array of course objects */ ],
  "total": 152,
  "page": 1,
  "limit": 20,
  "total_pages": 8
}
```

#### 10. Get Category Courses

```http
GET /api/studyhub/categories/{category_id}/courses?level=beginner&sort=popular
```

Same as `/courses` but auto-filtered by category.

#### 11. Get My Published Courses

```http
GET /api/studyhub/my-courses?status=approved&page=1&limit=20
Authorization: Bearer {firebase_token}
```

**Query Parameters:**
- `status` (string): draft | pending | approved | rejected | archived
- `page`, `limit`: Pagination

**Response:**
```json
{
  "courses": [ /* user's published courses */ ],
  "total": 5,
  "page": 1,
  "limit": 20,
  "total_pages": 1
}
```

#### 12. Update Course

```http
PUT /api/studyhub/courses/{course_id}
Authorization: Bearer {firebase_token}
```

**Request Body:**
```json
{
  "title": "Updated title",
  "description": "Updated description",
  "level": "intermediate",
  "price_type": "paid",
  "price_points": 5000,
  "tags": ["python", "advanced"]
}
```

**Business Rules:**
- Only course owner can update
- If course is approved, goes back to `pending` status
- Requires re-approval

#### 13. Archive Course

```http
DELETE /api/studyhub/courses/{course_id}
Authorization: Bearer {firebase_token}
```

**Response:**
```json
{
  "message": "Course archived successfully"
}
```

**Business Rules:**
- Sets status to `archived`
- Sets visibility to `private`
- Enrolled users keep access

---

### Enrollment & Progress

#### 14. Enroll in Course

```http
POST /api/studyhub/courses/{course_id}/enroll
Authorization: Bearer {firebase_token}
```

**Response:**
```json
{
  "enrollment_id": "...",
  "course_id": "...",
  "enrolled_at": "2026-01-15T12:00:00Z",
  "message": "Successfully enrolled in course"
}
```

**Business Rules:**
- Course must be approved and public
- Cannot enroll twice
- Increments course enrollment count

#### 15. Get Enrolled Courses

```http
GET /api/studyhub/community/enrolled-courses?page=1&limit=20
Authorization: Bearer {firebase_token}
```

**Response:**
```json
{
  "courses": [
    {
      /* course object */,
      "progress": {
        "completed_modules": 3,
        "total_modules": 10,
        "progress_percentage": 30.0,
        "current_module_id": "...",
        "last_accessed_at": "2026-01-15T12:00:00Z"
      },
      "enrollment": {
        "_id": "...",
        "enrolled_at": "2026-01-10T00:00:00Z",
        "completed": false,
        "rating": null
      }
    }
  ],
  "total": 5,
  "page": 1,
  "limit": 20
}
```

#### 16. Update Progress

```http
PUT /api/studyhub/enrollments/{enrollment_id}/progress
Authorization: Bearer {firebase_token}
```

**Request Body:**
```json
{
  "module_id": "507f1f77bcf86cd799439011",
  "completed": true
}
```

**Response:**
```json
{
  "enrollment_id": "...",
  "progress_percentage": 40.0,
  "completed": false,
  "message": "Progress updated successfully"
}
```

**Business Logic:**
- Auto-calculates progress percentage
- Marks course as completed when 100%
- Increments course completion count on first completion
- Updates last accessed time

#### 17. Rate Course

```http
POST /api/studyhub/enrollments/{enrollment_id}/rate
Authorization: Bearer {firebase_token}
```

**Request Body:**
```json
{
  "rating": 5,
  "review": "Excellent course! Learned a lot."
}
```

**Response:**
```json
{
  "enrollment_id": "...",
  "rating": 5,
  "message": "Rating submitted successfully"
}
```

**Business Logic:**
- Must be enrolled
- Rating 1-5 stars
- Updates course average rating
- Increments rating count

---

### Community Homepage

#### 18. Top Courses

```http
GET /api/studyhub/community/top-courses?limit=8
```

**Query Parameters:**
- `limit` (int): Number of courses (default: 8, max: 50)

**Sort:** By enrollment count (DESC)

**Response:**
```json
{
  "courses": [ /* array of course objects */ ],
  "total": 8
}
```

#### 19. Trending Courses

```http
GET /api/studyhub/community/trending-courses?limit=8
```

**Criteria:**
- Published in last 30 days
- High enrollment and view count

**Response:**
```json
{
  "courses": [ /* array of course objects */ ],
  "total": 8
}
```

#### 20. Search Courses

```http
GET /api/studyhub/community/search?q=python&category_id=it&level=beginner&sort=popular
```

**Query Parameters:**
- `q` (string, required): Search query (min 2 chars)
- `category_id`, `level`, `price_type`, `language`, `min_rating`: Filters
- `sort`: popular | newest | highest-rated | trending
- `page`, `limit`: Pagination

**Searches In:**
- Title
- Description
- Tags (exact match)

**Response:**
```json
{
  "courses": [ /* matching courses */ ],
  "total": 45,
  "page": 1,
  "limit": 20,
  "total_pages": 3
}
```

---

## Database Collections

### 1. `studyhub_categories`

```javascript
{
  _id: ObjectId,
  category_id: "it",  // Unique slug
  name_en: "Information Technology",
  name_vi: "Công nghệ thông tin",
  icon: "Code",
  description_en: "...",
  description_vi: "...",
  order_index: 1,
  is_active: true
}
```

**Indexes:**
- `category_id` (unique)
- `{is_active: 1, order_index: 1}`

### 2. `studyhub_category_subjects`

```javascript
{
  _id: ObjectId,
  category_id: "it",
  subject_name_en: "Python Programming",
  subject_name_vi: "Lập trình Python",
  description_en: "...",
  description_vi: "...",
  slug: "python-programming",
  created_by: "user",  // "admin" | "user"
  creator_id: "firebase_uid",
  approved: false,
  is_active: true,
  course_count: 0,
  total_learners: 0,
  created_at: DateTime,
  updated_at: DateTime
}
```

**Indexes:**
- `{category_id: 1, slug: 1}` (unique)
- `{category_id: 1, approved: 1, is_active: 1}`
- `{approved: 1, total_learners: -1}`
- Text search: `subject_name_en`, `subject_name_vi`, `description_en`, `description_vi`

### 3. `studyhub_courses`

```javascript
{
  _id: ObjectId,
  category_id: "it",
  category_subject_id: ObjectId,
  source_subject_id: ObjectId,  // From studyhub_subjects
  user_id: "firebase_uid",

  title: "Python Programming - Complete Guide",
  description: "...",
  cover_image_url: "https://...",
  language: "vi",
  level: "beginner",

  price_type: "free",
  price_points: 0,
  original_price_points: 0,
  discount_percentage: 0,

  module_count: 10,
  total_content_count: 45,
  estimated_duration_hours: 20,

  stats: {
    enrollment_count: 142,
    completion_count: 89,
    completion_rate: 62.68,
    average_rating: 4.7,
    rating_count: 56,
    view_count: 1250
  },

  status: "approved",  // draft | pending | approved | rejected | archived
  visibility: "public",  // public | private
  published_at: DateTime,
  approved_at: DateTime,
  approved_by: "admin_uid",
  rejection_reason: null,

  tags: ["python", "programming"],
  what_you_will_learn: [...],
  requirements: [...],
  target_audience: [...],

  last_synced_at: DateTime,
  sync_status: "up-to-date",
  sync_available: false,

  created_at: DateTime,
  updated_at: DateTime
}
```

**Indexes:**
- `source_subject_id` (unique - one course per subject)
- `{category_id: 1, status: 1, visibility: 1}`
- `{category_subject_id: 1, status: 1}`
- `{user_id: 1, status: 1}`
- `{status: 1, published_at: -1}`
- `{status: 1, visibility: 1, stats.enrollment_count: -1}`
- `{status: 1, visibility: 1, stats.average_rating: -1}`
- Text search: `title`, `description`, `tags`

### 4. `studyhub_course_enrollments`

```javascript
{
  _id: ObjectId,
  course_id: ObjectId,
  user_id: "firebase_uid",

  completed_modules: [ObjectId, ...],
  current_module_id: ObjectId,
  progress_percentage: 30.0,

  completed: false,
  completed_at: null,
  certificate_issued: false,
  certificate_id: null,

  enrolled_at: DateTime,
  last_accessed_at: DateTime,
  total_time_spent_minutes: 120,

  rating: 5,
  review: "Great course!",
  rated_at: DateTime
}
```

**Indexes:**
- `{course_id: 1, user_id: 1}` (unique - one enrollment per user per course)
- `{user_id: 1, enrolled_at: -1}`
- `{user_id: 1, last_accessed_at: -1}`
- `{course_id: 1, completed: 1}`
- `{course_id: 1, rating: 1}`

---

## Models & Schemas

All models defined in `src/models/studyhub_category_models.py`:

- **Enums**: CategoryID, CourseLevel, PriceType, CourseStatus, CourseVisibility, SortOption
- **Category**: Category, CategoryStats, CategoryWithStats
- **CategorySubject**: CategorySubject, CreateCategorySubjectRequest
- **Course**: Course, PublishCourseRequest, UpdateCourseRequest, CourseStats, CourseModule
- **Enrollment**: CourseEnrollment, CourseProgress, EnrollCourseRequest, UpdateProgressRequest, RateCourseRequest
- **Community**: TopCoursesResponse, TrendingCoursesResponse, SearchCoursesRequest

---

## Business Logic

### Course Publishing Workflow

1. User creates private subject (studyhub_subjects)
2. User clicks "Publish to Community"
3. User selects:
   - Category (10 fixed)
   - Existing category subject OR create new (needs approval)
4. User fills course details (title, description, pricing, etc.)
5. System:
   - Validates ownership
   - Creates/validates category subject
   - Creates course (status: pending)
   - Copies module structure from source subject
6. Admin reviews and approves/rejects
7. If approved → Course visible in community

### Approval Workflow

**Category Subjects:**
- User-created → `approved: false`
- Admin reviews → Approve/Reject
- If approved → `approved: true`, visible to users

**Courses:**
- User publishes → `status: "pending"`
- Admin reviews course + modules
- Approve → `status: "approved"`, `visibility: "public"`
- Reject → `status: "rejected"`, `rejection_reason: "..."`
- If user edits approved course → Back to `pending`

### Progress Tracking

- Enrollment tracks `completed_modules` array
- Progress percentage = `(completed / total) * 100`
- Last accessed updated on every progress update
- Course marked completed when progress = 100%
- Completion count incremented once per user

### Rating System

- Users can rate 1-5 stars
- Optional review text
- Average rating recalculated on each new rating
- Rating count incremented

---

## Examples

### Example 1: Browse IT Courses

```bash
# 1. Get IT category
curl https://wordai.asia/api/studyhub/categories/it

# 2. List courses in IT
curl "https://wordai.asia/api/studyhub/categories/it/courses?sort=popular&limit=20"

# 3. Search for Python courses
curl "https://wordai.asia/api/studyhub/community/search?q=python&category_id=it"
```

### Example 2: Publish a Course

```bash
# 1. Create private subject first (existing API)
# 2. Publish to community
curl -X POST https://wordai.asia/api/studyhub/subjects/{subject_id}/publish-course \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "category_id": "it",
    "category_subject_id": null,
    "new_subject_name_en": "Advanced Python",
    "new_subject_name_vi": "Python Nâng cao",
    "title": "Advanced Python Techniques",
    "description": "Master advanced Python concepts...",
    "level": "advanced",
    "price_type": "free",
    "tags": ["python", "advanced"]
  }'
```

### Example 3: Enroll and Track Progress

```bash
# 1. Enroll in course
curl -X POST https://wordai.asia/api/studyhub/courses/{course_id}/enroll \
  -H "Authorization: Bearer {token}"

# 2. Get enrolled courses
curl https://wordai.asia/api/studyhub/community/enrolled-courses \
  -H "Authorization: Bearer {token}"

# 3. Update progress
curl -X PUT https://wordai.asia/api/studyhub/enrollments/{enrollment_id}/progress \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "module_id": "...",
    "completed": true
  }'

# 4. Rate course
curl -X POST https://wordai.asia/api/studyhub/enrollments/{enrollment_id}/rate \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "rating": 5,
    "review": "Excellent course!"
  }'
```

---

## Setup & Deployment

### Database Setup

```bash
# Run locally first
python3 setup_studyhub_categories.py

# Deploy to production
./deploy-studyhub-categories.sh
```

### What Gets Created

1. **10 Categories** - Seeded in `studyhub_categories`
2. **Indexes** - All required indexes for performance
3. **API Routes** - 20+ endpoints registered
4. **Models** - Complete Pydantic models
5. **Service Layer** - Business logic

---

## Testing Checklist

- [ ] Categories list with stats
- [ ] Category detail with top subjects
- [ ] Create category subject (user)
- [ ] Search category subjects
- [ ] Publish subject as course
- [ ] Course detail with enrollment status
- [ ] List courses with filters
- [ ] My published courses
- [ ] Update course
- [ ] Archive course
- [ ] Enroll in course
- [ ] Get enrolled courses with progress
- [ ] Update progress
- [ ] Rate course
- [ ] Top courses
- [ ] Trending courses
- [ ] Search courses

---

**Documentation Status:** Complete ✅
**Implementation Status:** Ready for testing ✅
**Next Steps:** Deploy and test all endpoints ✅
