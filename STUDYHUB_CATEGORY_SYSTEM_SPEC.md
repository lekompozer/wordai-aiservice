# StudyHub Category & Course System - Technical Specification

**Last Updated:** January 15, 2026

## System Architecture

### Hierarchy

```
Category (10 fixed)
  └── CategorySubject (user can create)
      └── Course (user publishes their subject)
          └── Modules (from user's subject)
```

### Core Concepts

1. **Category**: Fixed 10 categories (IT, Business, Finance, etc.)
2. **CategorySubject**: Subject definitions within a category (e.g., "Python Programming" in IT category)
3. **Course**: A published user subject mapped to a CategorySubject
4. **Modules**: Content modules from the user's original subject

---

## Database Collections

### 1. `studyhub_categories` (Fixed Data)

```javascript
{
  _id: ObjectId,
  category_id: "it",  // Unique slug
  name_en: "Information Technology",
  name_vi: "Công nghệ thông tin",
  icon: "Code",
  description_en: "Programming, Software Development, IT",
  description_vi: "Lập trình, Phát triển phần mềm, CNTT",
  order_index: 1,
  is_active: true
}
```

**10 Fixed Categories:**
- `it` - Information Technology / Công nghệ thông tin
- `business` - Business / Kinh doanh
- `finance` - Finance / Tài chính
- `certificates` - Certificates / Chứng chỉ
- `languages` - Languages / Ngôn ngữ
- `personal-dev` - Personal Development / Phát triển bản thân
- `lifestyle` - Lifestyle / Lối sống
- `academics` - Academics / Học thuật
- `science` - Science / Khoa học
- `skill` - Skills / Kỹ năng

### 2. `studyhub_category_subjects` (User can create)

```javascript
{
  _id: ObjectId,
  category_id: "it",
  subject_name_en: "Python Programming",
  subject_name_vi: "Lập trình Python",
  description_en: "Learn Python programming language",
  description_vi: "Học ngôn ngữ lập trình Python",
  slug: "python-programming",  // Unique within category
  created_by: "admin" | "user",
  creator_id: "firebase_uid",  // If created_by="user"
  approved: true,  // Admin approval required
  is_active: true,
  course_count: 15,  // Number of courses in this subject
  total_learners: 1250,  // Total across all courses
  created_at: DateTime,
  updated_at: DateTime
}
```

**Unique Index**: `{category_id: 1, slug: 1}`

### 3. `studyhub_courses` (User publishes subject)

```javascript
{
  _id: ObjectId,

  // Category & Subject
  category_id: "it",
  category_subject_id: ObjectId("..."),

  // Source (User's original subject)
  source_subject_id: ObjectId("..."),  // From studyhub_subjects
  user_id: "firebase_uid",

  // Course Info
  title: "Python Programming - Complete Guide",
  description: "Learn Python from scratch to advanced",
  cover_image_url: "https://...",
  language: "vi",  // Course language
  level: "beginner" | "intermediate" | "advanced",

  // Pricing
  price_type: "free" | "paid",
  price_points: 0,
  original_price_points: 0,
  discount_percentage: 0,

  // Modules (copied from source subject)
  module_count: 10,
  total_content_count: 45,
  estimated_duration_hours: 20,

  // Stats
  enrollment_count: 142,
  completion_count: 89,
  completion_rate: 62.68,  // %
  average_rating: 4.7,
  rating_count: 56,
  view_count: 1250,

  // Status
  status: "draft" | "pending" | "approved" | "rejected" | "archived",
  visibility: "public" | "private",
  published_at: DateTime,
  approved_at: DateTime,
  approved_by: "admin_uid",
  rejection_reason: "...",

  // Metadata
  tags: ["python", "programming", "beginner"],
  what_you_will_learn: [
    "Python basics",
    "OOP in Python",
    "Web development with Django"
  ],
  requirements: ["Computer", "Internet"],
  target_audience: ["Beginners", "Students"],

  // Timestamps
  created_at: DateTime,
  updated_at: DateTime,
  last_synced_at: DateTime  // Last sync from source subject
}
```

**Indexes:**
- `{category_id: 1, status: 1, visibility: 1}`
- `{category_subject_id: 1, status: 1}`
- `{source_subject_id: 1}` - Unique (one course per source subject)
- `{user_id: 1, status: 1}`
- `{status: 1, published_at: -1}`

---

## API Endpoints

### Category Management

#### 1. GET `/api/studyhub/categories`
List all categories with stats

**Response:**
```json
{
  "categories": [
    {
      "category_id": "it",
      "name_en": "Information Technology",
      "name_vi": "Công nghệ thông tin",
      "icon": "Code",
      "subject_count": 45,
      "course_count": 152,
      "total_learners": 12500,
      "order_index": 1
    }
  ]
}
```

#### 2. GET `/api/studyhub/categories/{category_id}`
Get category details with top subjects

**Response:**
```json
{
  "category_id": "it",
  "name_en": "Information Technology",
  "name_vi": "Công nghệ thông tin",
  "description_en": "...",
  "stats": {
    "subject_count": 45,
    "course_count": 152,
    "total_learners": 12500,
    "avg_rating": 4.6
  },
  "top_subjects": [
    {
      "_id": "...",
      "subject_name_en": "Python Programming",
      "course_count": 15,
      "total_learners": 1250
    }
  ]
}
```

### Category Subject Management

#### 3. GET `/api/studyhub/categories/{category_id}/subjects`
List subjects in category

**Query Params:**
- `page`, `limit`
- `sort`: `popular`, `newest`, `name`

#### 4. POST `/api/studyhub/categories/{category_id}/subjects`
Create new subject in category (user or admin)

**Request:**
```json
{
  "subject_name_en": "Python Programming",
  "subject_name_vi": "Lập trình Python",
  "description_en": "...",
  "description_vi": "..."
}
```

**Rules:**
- User can create but needs admin approval
- Slug auto-generated from subject_name_en
- Check duplicate within category

#### 5. GET `/api/studyhub/category-subjects/search?q={query}`
Search subjects across all categories

### Course Management

#### 6. POST `/api/studyhub/subjects/{subject_id}/publish-course`
Publish user's subject as course

**Request:**
```json
{
  "category_id": "it",
  "category_subject_id": "...",  // Or null to create new
  "new_subject_name_en": "Python Programming",  // If creating new
  "new_subject_name_vi": "Lập trình Python",
  "title": "Python - Complete Guide",
  "description": "...",
  "price_type": "free",
  "price_points": 0,
  "level": "beginner",
  "language": "vi",
  "tags": ["python", "programming"],
  "what_you_will_learn": [],
  "requirements": [],
  "target_audience": []
}
```

**Process:**
1. Check user owns source subject
2. If `category_subject_id` is null:
   - Create new CategorySubject (pending approval)
3. Create Course (status: pending)
4. Copy modules from source subject
5. Send for admin approval

**Response:**
```json
{
  "course_id": "...",
  "status": "pending",
  "message": "Course submitted for approval"
}
```

#### 7. GET `/api/studyhub/courses/{course_id}`
Get course details

**Response:**
```json
{
  "course_id": "...",
  "category": {
    "category_id": "it",
    "name_en": "Information Technology"
  },
  "category_subject": {
    "subject_name_en": "Python Programming"
  },
  "title": "Python - Complete Guide",
  "instructor": {
    "user_id": "...",
    "display_name": "John Doe",
    "profile_image": "..."
  },
  "stats": {
    "enrollment_count": 142,
    "average_rating": 4.7,
    "rating_count": 56
  },
  "modules": [
    {
      "module_id": "...",
      "title": "Introduction",
      "content_count": 5,
      "order_index": 1
    }
  ],
  "is_enrolled": false,
  "can_enroll": true
}
```

#### 8. GET `/api/studyhub/courses`
List courses with filters

**Query Params:**
- `category_id`: Filter by category
- `category_subject_id`: Filter by subject
- `level`: beginner/intermediate/advanced
- `price_type`: free/paid
- `language`: vi/en
- `sort`: `popular`, `newest`, `highest-rated`, `trending`
- `page`, `limit`

#### 9. GET `/api/studyhub/my-courses`
User's published courses (Auth required)

**Query Params:**
- `status`: draft/pending/approved/rejected
- `page`, `limit`

#### 10. PUT `/api/studyhub/courses/{course_id}`
Update course (owner only, goes back to pending if approved)

#### 11. DELETE `/api/studyhub/courses/{course_id}`
Archive course (owner only)

### Community Homepage

#### 12. GET `/api/studyhub/community/top-courses`
Top courses across all categories

**Query Params:**
- `limit`: default 8

**Sort by:** `enrollment_count DESC`

#### 13. GET `/api/studyhub/community/trending-courses`
Trending courses (high engagement recently)

**Algorithm:**
```javascript
trending_score =
  (enrollments_last_7d * 5) +
  (ratings_last_7d * 3) +
  (views_last_7d * 1)
```

#### 14. GET `/api/studyhub/community/search?q={query}`
Search courses

**Search fields:** `title`, `description`, `tags`

**Filters:** `category_id`, `level`, `price_type`, `language`

#### 15. GET `/api/studyhub/community/enrolled-courses`
User's enrolled courses (Auth required)

**Response includes progress:**
```json
{
  "courses": [
    {
      "course_id": "...",
      "title": "...",
      "progress": {
        "completed_modules": 3,
        "total_modules": 10,
        "progress_percentage": 30,
        "last_accessed_at": "..."
      }
    }
  ]
}
```

### Category Page

#### 16. GET `/api/studyhub/categories/{category_id}/stats`
Get category statistics

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
      "user_id": "...",
      "display_name": "...",
      "course_count": 5,
      "total_learners": 850
    }
  ]
}
```

#### 17. GET `/api/studyhub/categories/{category_id}/courses`
List courses in category (same as #8 but filtered)

---

## Enrollment & Progress Tracking

### Collection: `studyhub_course_enrollments`

```javascript
{
  _id: ObjectId,
  course_id: ObjectId,
  user_id: "firebase_uid",

  // Progress
  completed_modules: [ObjectId(...)],
  current_module_id: ObjectId,
  progress_percentage: 30,

  // Completion
  completed: false,
  completed_at: null,
  certificate_issued: false,
  certificate_id: null,

  // Activity
  enrolled_at: DateTime,
  last_accessed_at: DateTime,
  total_time_spent_minutes: 120,

  // Rating
  rating: 5,
  review: "Great course!",
  rated_at: DateTime
}
```

**Indexes:**
- `{course_id: 1, user_id: 1}` - Unique
- `{user_id: 1, enrolled_at: -1}`

---

## Admin Approval Workflow

### For Category Subjects

1. User creates subject → `approved: false`
2. Admin reviews → Approve/Reject
3. If approved → `approved: true`, visible to users
4. No edit/delete by users, only admin

### For Courses

1. User publishes → `status: "pending"`
2. Admin reviews course + modules
3. Admin approves → `status: "approved"`, `visibility: "public"`
4. If rejected → `status: "rejected"`, `rejection_reason: "..."`
5. User edits approved course → Back to `pending`

---

## Sync from Source Subject

When user updates their original subject, we need sync logic:

```javascript
// Check if course needs sync
if (source_subject.updated_at > course.last_synced_at) {
  // Modules added/removed/reordered → Need manual review
  // Content updated → Auto-sync or flag for review

  course.sync_status = "outdated";
  course.sync_available = true;
}
```

**Sync API:**
```
POST /api/studyhub/courses/{course_id}/sync-from-source
```

---

## Business Rules

1. **One Course Per Source Subject**: User can only publish each subject once
2. **Category Subject Uniqueness**: Slug must be unique within category
3. **Approval Required**: Both category subjects and courses need admin approval
4. **Pricing**: Free courses always free, paid can change price (but needs re-approval)
5. **Enrollment**: Once enrolled, always has access (even if course archived)
6. **Progress**: Tracked at module level, percentage calculated from completed modules

---

## Migration Plan

### Phase 1: Category System
- Create categories collection (fixed 10)
- Create category_subjects collection
- Seed initial subjects (admin-created)

### Phase 2: Course System
- Create courses collection
- Create enrollments collection
- Build publish workflow

### Phase 3: Community Pages
- Implement top/trending/search
- Build category page with stats
- Add enrollment tracking

### Phase 4: Sync & Admin
- Build admin approval UI
- Implement sync from source
- Add moderation tools

---

**Status:** Design Complete
**Next Step:** Implementation Phase 1
