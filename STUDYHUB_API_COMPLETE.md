# StudyHub Complete API Specifications - Phase 1 MVP

## Overview

Complete API documentation for StudyHub learning platform Phase 1 (38 APIs).

**Base URL**: `https://api.wordai.pro`
**Authentication**: Firebase Bearer token (except marketplace endpoints)

---

## M1.1: Subject Core (8 APIs)

See [STUDYHUB_API_SPECS.md](STUDYHUB_API_SPECS.md) for detailed M1.1 specifications.

---

## M1.2: Module & Content Management (8 APIs)

### API-9: Create Module

**POST** `/api/studyhub/subjects/{subject_id}/modules`

**Auth**: Required (Owner only)

**Request**:
- `title` (string, required, max 200)
- `description` (string, optional, max 1000)

**Response**: Module object with auto-assigned order_index

---

### API-10: Get Modules List

**GET** `/api/studyhub/subjects/{subject_id}/modules`

**Auth**: Required

**Response**: Array of modules sorted by order_index

---

### API-11: Update Module

**PUT** `/api/studyhub/modules/{module_id}`

**Auth**: Required (Owner only)

**Request**:
- `title` (string, optional)
- `description` (string, optional)

**Response**: Updated module object

---

### API-12: Delete Module

**DELETE** `/api/studyhub/modules/{module_id}`

**Auth**: Required (Owner only)

**Behavior**: Soft delete (cascade to module_contents), re-indexes remaining modules

**Response**: Success message

---

### API-13: Reorder Module

**POST** `/api/studyhub/modules/{module_id}/reorder`

**Auth**: Required (Owner only)

**Request**:
- `new_order_index` (integer, required)

**Response**: Success message

---

### API-14: Add Content to Module

**POST** `/api/studyhub/modules/{module_id}/content`

**Auth**: Required (Owner only)

**Request**:
- `title` (string, required, max 200)
- `content_type` (string, required): document/link/video/book/test/slides
- `content_url` (string, optional)
- `content_text` (string, optional)
- `reference_id` (string, optional): For book/test/slides references
- `reference_type` (string, optional): book_online/test_online/ai_slide

**Response**: Content object with auto-assigned order_index

---

### API-15: Get Module Contents

**GET** `/api/studyhub/modules/{module_id}/content`

**Auth**: Required

**Response**: Array of contents sorted by order_index

---

### API-16: Delete Content

**DELETE** `/api/studyhub/modules/{module_id}/content/{content_id}`

**Auth**: Required (Owner only)

**Behavior**: Soft delete, re-indexes remaining contents

**Response**: Success message

---

## M1.3: Enrollment & Progress (10 APIs)

### API-17: Enroll in Subject

**POST** `/api/studyhub/subjects/{subject_id}/enroll`

**Auth**: Required

**Validation**:
- Subject must be published
- Cannot enroll twice (active/completed)

**Response**: Enrollment object with status "active"

---

### API-18: Unenroll from Subject

**DELETE** `/api/studyhub/subjects/{subject_id}/enroll`

**Auth**: Required

**Behavior**: Marks enrollment as "dropped", preserves progress data

**Response**: Success message

---

### API-19: Get My Enrollments

**GET** `/api/studyhub/enrollments`

**Auth**: Required

**Query Parameters**:
- `status` (optional): active/completed/dropped

**Response**: 
- Array of enrollments with subject info
- Each includes progress_percentage

---

### API-20: Get Subject Progress

**GET** `/api/studyhub/subjects/{subject_id}/progress`

**Auth**: Required

**Response**:
- Subject title, enrollment status
- Overall progress percentage (0-1)
- Total modules/contents count
- Completed modules/contents count
- Last learning position (module_id, content_id)
- Module-by-module progress breakdown
- Timestamps (enrolled_at, last_accessed_at)

---

### API-21: Mark as Complete

**POST** `/api/studyhub/progress/mark-complete`

**Auth**: Required

**Request**:
- `subject_id` (string, required)
- `module_id` (string, optional)
- `content_id` (string, optional)

**Behavior**:
- If content_id: marks single content complete
- If only module_id: marks all contents in module complete
- Auto-completes subject when 100% done

**Response**: Success message

---

### API-22: Mark as Incomplete

**POST** `/api/studyhub/progress/mark-incomplete`

**Auth**: Required

**Request**: Same as API-21

**Behavior**:
- Removes completion status
- Reverts subject to active if was completed

**Response**: Success message

---

### API-23: Save Last Position

**PUT** `/api/studyhub/progress/last-position`

**Auth**: Required

**Request**:
- `subject_id` (string, required)
- `module_id` (string, required)
- `content_id` (string, required)

**Behavior**: Saves position for "Continue Learning" feature

**Response**: Success message

---

### API-24: Get Subject Learners

**GET** `/api/studyhub/subjects/{subject_id}/learners`

**Auth**: Required (Owner only)

**Response**:
- Array of learners with user info
- Each includes progress percentage
- Sorted by enrolled_at DESC

---

### API-25: Dashboard Overview

**GET** `/api/studyhub/dashboard/overview`

**Auth**: Required

**Response**:
- Active subjects count
- Completed subjects count
- Total learning hours (estimated)
- Recent subjects preview (5 subjects)

---

### API-26: Recent Activity

**GET** `/api/studyhub/dashboard/recent-activity`

**Auth**: Required

**Query Parameters**:
- `limit` (integer, default 20, max 100)

**Response**:
- Activity timeline items
- Each includes: type, subject, module, content, timestamp
- Sorted by timestamp DESC

---

## M1.4: Marketplace & Discovery (12 APIs)

**Note**: All marketplace endpoints are PUBLIC (no authentication required)

### API-27: Search & Filter Subjects

**GET** `/api/studyhub/marketplace/subjects/search`

**Auth**: None (Public)

**Query Parameters**:
- `q` (string, optional): Search by title or creator name
- `category` (string, optional): Filter by category
- `tags` (string, optional): Comma-separated tags
- `level` (string, optional): beginner/intermediate/advanced
- `sort_by` (string, default "updated"): updated/views/rating/newest
- `skip` (integer, default 0)
- `limit` (integer, default 20, max 100)

**Response**:
- Array of marketplace subject items
- Each includes: id, title, description, cover, owner info, category, tags, level, stats
- Total count for pagination

---

### API-28: Latest Subjects

**GET** `/api/studyhub/marketplace/subjects/latest`

**Auth**: None (Public)

**Query Parameters**:
- `category` (string, optional)
- `tags` (string, optional)
- `skip` (integer, default 0)
- `limit` (integer, default 20)

**Response**: Same as API-27, sorted by last_updated_at DESC

---

### API-29: Top Subjects

**GET** `/api/studyhub/marketplace/subjects/top`

**Auth**: None (Public)

**Query Parameters**:
- `category` (string, optional)
- `tags` (string, optional)
- `limit` (integer, default 10, max 50)

**Response**: Same as API-27, sorted by total_views DESC

---

### API-30: Featured Subjects of Week

**GET** `/api/studyhub/marketplace/subjects/featured-week`

**Auth**: None (Public)

**Response**:
- 3 featured subjects
- Selection: 2 most viewed + 1 most enrolled in last 7 days
- Each includes reason: "most_viewed_week" or "most_enrolled_week"

---

### API-31: Trending Today

**GET** `/api/studyhub/marketplace/subjects/trending-today`

**Auth**: None (Public)

**Response**:
- 5 trending subjects
- Based on views in last 24 hours
- Each includes views_today count

---

### API-32: Featured Creators

**GET** `/api/studyhub/marketplace/creators/featured`

**Auth**: None (Public)

**Response**:
- 10 featured creators
- Selection criteria:
  - 3 by total reads (sum of all subject views)
  - 3 by best ratings (average rating across subjects)
  - 4 by top subject views
- Each includes: user_id, name, avatar, bio, stats, top_subject, reason

**Creator Stats**:
- total_subjects
- total_students
- total_reads
- average_rating
- total_reviews

---

### API-33: Popular Tags

**GET** `/api/studyhub/marketplace/tags/popular`

**Auth**: None (Public)

**Response**:
- 25 most popular tags
- Each includes: tag name, subject count
- Sorted by count DESC

---

### API-34: Popular Categories

**GET** `/api/studyhub/marketplace/categories/popular`

**Auth**: None (Public)

**Response**:
- All categories with subject counts
- Each includes: name, count, icon, description
- Sorted by count DESC

---

### API-35: Public Subject View

**GET** `/api/studyhub/marketplace/subjects/{subject_id}`

**Auth**: None (Public)

**Behavior**: Tracks view count (increments total_views, views_today, views_this_week)

**Response**:
- Complete subject information
- Owner profile (user_id, name, avatar, bio)
- Category, tags, level
- Module previews (first 2 modules)
- Stats (modules, contents, learners, views, rating, completion_rate, estimated_hours)
- Pricing info (is_free, price)
- Timestamps

---

### API-36: Related Subjects

**GET** `/api/studyhub/marketplace/subjects/{subject_id}/related`

**Auth**: None (Public)

**Query Parameters**:
- `limit` (integer, default 5, max 20)

**Response**:
- Array of related subjects
- Match criteria: same category OR matching tags
- Sorted by relevance and views

---

### API-37: Creator Profile

**GET** `/api/studyhub/marketplace/creators/{creator_id}/profile`

**Auth**: None (Public)

**Response**:
- Creator info: user_id, name, avatar, bio, website, social_links
- Creator stats (aggregated from all public subjects)
- Featured subjects (top 3 by views)
- joined_at timestamp

---

### API-38: Creator Subjects

**GET** `/api/studyhub/marketplace/creators/{creator_id}/subjects`

**Auth**: None (Public)

**Query Parameters**:
- `skip` (integer, default 0)
- `limit` (integer, default 20)
- `sort_by` (string, default "views"): views/rating/newest

**Response**: Paginated list of creator's public subjects

---

## Common Response Models

### SubjectResponse
- `_id`: Subject ID
- `owner_id`: Creator user ID
- `title`: Subject title
- `description`: Subject description
- `cover_image_url`: Cover image URL
- `status`: draft/published/archived
- `visibility`: public/private
- `metadata`: Object with stats
- `created_at`: ISO timestamp
- `updated_at`: ISO timestamp

### MarketplaceSubjectItem
- All SubjectResponse fields
- `owner`: Owner info object (user_id, display_name, avatar_url)
- `category`: Category name
- `tags`: Array of tags
- `level`: beginner/intermediate/advanced
- `stats`: Stats object
- `last_updated_at`: ISO timestamp

### SubjectStats
- `total_modules`: Number
- `total_learners`: Number
- `total_views`: Number
- `average_rating`: Float (0-5)
- `completion_rate`: Float (0-1)

### ModuleResponse
- `_id`: Module ID
- `subject_id`: Parent subject ID
- `title`: Module title
- `description`: Module description
- `order_index`: Integer (ordering)
- `created_at`: ISO timestamp
- `updated_at`: ISO timestamp

### ModuleContentResponse
- `_id`: Content ID
- `module_id`: Parent module ID
- `title`: Content title
- `content_type`: document/link/video/book/test/slides
- `content_url`: URL (if type is link/video)
- `content_text`: Text content
- `reference_id`: Reference to book/test/slide
- `reference_type`: book_online/test_online/ai_slide
- `order_index`: Integer
- `created_at`: ISO timestamp
- `updated_at`: ISO timestamp

### EnrollmentResponse
- `_id`: Enrollment ID
- `user_id`: User ID
- `subject_id`: Subject ID
- `subject_title`: Subject title
- `status`: active/completed/dropped
- `enrolled_at`: ISO timestamp
- `last_accessed_at`: ISO timestamp
- `completed_at`: ISO timestamp (if completed)
- `progress_percentage`: Float (0-1)

---

## Error Responses

All endpoints may return these error statuses:

**400 Bad Request**: Invalid input
- Missing required fields
- Validation errors
- Business logic violations (e.g., already enrolled)

**401 Unauthorized**: Authentication required but not provided

**403 Forbidden**: User lacks permission
- Not the owner
- Subject not published

**404 Not Found**: Resource doesn't exist
- Subject not found
- Module not found
- Enrollment not found

**500 Internal Server Error**: Server-side error

**Error Response Format**:
```json
{
  "detail": "Error message description"
}
```

---

## Database Collections

### studyhub_subjects
- Primary subject data
- Marketplace fields: is_public_marketplace, category, tags, level, total_views, views_today, views_this_week

### studyhub_modules
- Module data with order_index

### studyhub_module_contents
- Content data with order_index and references

### studyhub_enrollments
- User enrollments with status tracking
- Unique constraint: (user_id, subject_id)

### studyhub_learning_progress
- Content/module completion tracking
- Linked to enrollments

---

## MongoDB Indexes

**Total: 45 indexes** across 8 collections

### studyhub_subjects (17 indexes)
- Core: owner_id, status, visibility, title+description (text)
- Compound: owner_id+created_at, status+visibility+created_at
- Marketplace: is_public_marketplace+status+last_updated_at, category, tags, level, views_today, views_this_week, total_views, avg_rating

### studyhub_enrollments (5 indexes)
- user_id, subject_id, status
- Unique: user_id+subject_id
- Compound: user_id+status

### studyhub_learning_progress (5 indexes)
- Compound: user_id+subject_id, user_id+module_id, user_id+content_id
- status, updated_at

---

## Frontend Integration Checklist

### Authentication
- [ ] Implement Firebase Auth token management
- [ ] Add token to all authenticated requests
- [ ] Handle 401 errors (token refresh)

### Subject Management (M1.1 + M1.2)
- [ ] Create/update subject forms
- [ ] Cover image upload with file picker
- [ ] Module CRUD interface
- [ ] Content management UI
- [ ] Drag-and-drop reordering

### Enrollment & Progress (M1.3)
- [ ] Enroll/unenroll buttons
- [ ] Progress bars and indicators
- [ ] "Continue Learning" resume feature
- [ ] Dashboard overview page
- [ ] Activity timeline

### Marketplace (M1.4)
- [ ] Browse/search interface
- [ ] Filter by category, tags, level
- [ ] Sort options (updated/views/rating)
- [ ] Featured subjects carousel
- [ ] Trending subjects section
- [ ] Creator profile pages
- [ ] Related subjects sidebar

### State Management
- [ ] Cache marketplace data (public)
- [ ] Real-time progress updates
- [ ] Optimistic UI updates
- [ ] Handle pagination

---

**Document Version**: 2.0
**Phase**: 1 MVP Complete
**Last Updated**: January 8, 2026
**Total APIs**: 38 (8 + 8 + 10 + 12)
**Status**: ✅ All 38 APIs implemented and deployed
