# StudyHub API Technical Specifications (Frontend)

## Overview

This document provides detailed API specifications for the **StudyHub** learning platform. All endpoints require Firebase Authentication unless specified otherwise.

**Base URL**: `https://api.wordai.pro`

**Authentication**: Bearer token in `Authorization` header
```
Authorization: Bearer <firebase_id_token>
```

---

## Milestone 1.1: Subject Core APIs

### Subject Management

#### 1. Create Subject

**Endpoint**: `POST /api/studyhub/subjects`

**Authentication**: Required

**Request Body**:
```json
{
  "title": "Introduction to Python Programming",
  "description": "Learn Python from scratch with hands-on projects",
  "visibility": "private"
}
```

**Field Specifications**:
- `title` (string, required): Subject title, 1-200 characters
- `description` (string, optional): Subject description, max 2000 characters
- `visibility` (string, optional): `"public"` or `"private"`, default: `"private"`

**Response** (`201 Created`):
```json
{
  "_id": "507f1f77bcf86cd799439011",
  "owner_id": "firebase_user_id_123",
  "title": "Introduction to Python Programming",
  "description": "Learn Python from scratch with hands-on projects",
  "cover_image_url": null,
  "status": "draft",
  "visibility": "private",
  "metadata": {
    "total_modules": 0,
    "total_learners": 0,
    "avg_rating": 0.0,
    "tags": []
  },
  "created_at": "2026-01-08T10:30:00Z",
  "updated_at": "2026-01-08T10:30:00Z",
  "is_enrolled": false,
  "is_owner": true
}
```

**Status Codes**:
- `201`: Subject created successfully
- `400`: Invalid request data
- `401`: Unauthorized
- `500`: Server error

---

#### 2. Get Subject Details

**Endpoint**: `GET /api/studyhub/subjects/{subject_id}`

**Authentication**: Optional (required for private subjects)

**Query Parameters**:
- `include_stats` (boolean, optional): Include updated metadata statistics, default: `false`

**Example**: `GET /api/studyhub/subjects/507f1f77bcf86cd799439011?include_stats=true`

**Response** (`200 OK`):
```json
{
  "_id": "507f1f77bcf86cd799439011",
  "owner_id": "firebase_user_id_123",
  "title": "Introduction to Python Programming",
  "description": "Learn Python from scratch with hands-on projects",
  "cover_image_url": "https://cdn.wordai.pro/studyhub/covers/507f1f77bcf86cd799439011.jpg",
  "status": "published",
  "visibility": "public",
  "metadata": {
    "total_modules": 5,
    "total_learners": 142,
    "avg_rating": 4.7,
    "tags": ["python", "programming", "beginner"]
  },
  "created_at": "2026-01-08T10:30:00Z",
  "updated_at": "2026-01-08T14:20:00Z",
  "is_enrolled": true,
  "is_owner": false
}
```

**Visibility Rules**:
- Public subjects: Anyone can view
- Private subjects: Only owner and enrolled learners can view

**Status Codes**:
- `200`: Success
- `404`: Subject not found or no access
- `500`: Server error

---

#### 3. Update Subject

**Endpoint**: `PUT /api/studyhub/subjects/{subject_id}`

**Authentication**: Required (owner only)

**Request Body**:
```json
{
  "title": "Advanced Python Programming",
  "description": "Updated description",
  "visibility": "public"
}
```

**Field Specifications**:
- All fields are optional
- Only provided fields will be updated
- Same validation rules as Create Subject

**Response** (`200 OK`):
```json
{
  "_id": "507f1f77bcf86cd799439011",
  "owner_id": "firebase_user_id_123",
  "title": "Advanced Python Programming",
  "description": "Updated description",
  "cover_image_url": "https://cdn.wordai.pro/studyhub/covers/507f1f77bcf86cd799439011.jpg",
  "status": "draft",
  "visibility": "public",
  "metadata": {
    "total_modules": 0,
    "total_learners": 0,
    "avg_rating": 0.0,
    "tags": []
  },
  "created_at": "2026-01-08T10:30:00Z",
  "updated_at": "2026-01-08T15:45:00Z",
  "is_enrolled": false,
  "is_owner": true
}
```

**Status Codes**:
- `200`: Subject updated successfully
- `400`: Invalid request data
- `401`: Unauthorized
- `404`: Subject not found or not owner
- `500`: Server error

---

#### 4. Delete Subject

**Endpoint**: `DELETE /api/studyhub/subjects/{subject_id}`

**Authentication**: Required (owner only)

**Query Parameters**:
- `confirm` (boolean, optional): Required if subject has learners, default: `false`

**Example**: `DELETE /api/studyhub/subjects/507f1f77bcf86cd799439011?confirm=true`

**Response** (`200 OK`):
```json
{
  "success": true,
  "message": "Subject archived successfully. 5 learners affected.",
  "subject_id": "507f1f77bcf86cd799439011"
}
```

**Notes**:
- This is a **soft delete** - changes status to `"archived"`
- If subject has learners and `confirm=false`, returns error:

```json
{
  "detail": "Subject has 5 learners. Set confirm=true to proceed."
}
```

**Status Codes**:
- `200`: Subject deleted successfully
- `400`: Confirmation required
- `401`: Unauthorized
- `404`: Subject not found or not owner
- `500`: Server error

---

#### 5. List Subjects

**Endpoint**: `GET /api/studyhub/subjects`

**Authentication**: Optional

**Query Parameters**:
- `status` (string, optional): Filter by status - `"draft"`, `"published"`, `"archived"`
- `visibility` (string, optional): Filter by visibility - `"public"`, `"private"`
- `owner_id` (string, optional): Filter by owner user ID
- `page` (integer, optional): Page number, default: `1`, min: `1`
- `limit` (integer, optional): Items per page, default: `20`, min: `1`, max: `100`
- `sort` (string, optional): Sort field - `"created_at"`, `"updated_at"`, `"title"`, default: `"created_at"`

**Example**: `GET /api/studyhub/subjects?status=published&visibility=public&page=1&limit=20&sort=created_at`

**Response** (`200 OK`):
```json
{
  "subjects": [
    {
      "_id": "507f1f77bcf86cd799439011",
      "owner_id": "firebase_user_id_123",
      "title": "Introduction to Python Programming",
      "description": "Learn Python from scratch",
      "cover_image_url": "https://cdn.wordai.pro/studyhub/covers/507f1f77bcf86cd799439011.jpg",
      "status": "published",
      "visibility": "public",
      "metadata": {
        "total_modules": 5,
        "total_learners": 142,
        "avg_rating": 4.7,
        "tags": ["python", "programming"]
      },
      "created_at": "2026-01-08T10:30:00Z",
      "updated_at": "2026-01-08T14:20:00Z",
      "is_enrolled": true,
      "is_owner": false
    }
  ],
  "total": 47,
  "page": 1,
  "limit": 20,
  "has_more": true
}
```

**Visibility Logic**:
- Unauthenticated users: Only see published public subjects
- Authenticated users: See published public subjects + own subjects + enrolled subjects

**Status Codes**:
- `200`: Success
- `400`: Invalid query parameters
- `500`: Server error

---

#### 6. Get Owner's Subjects

**Endpoint**: `GET /api/studyhub/subjects/owner/{user_id}`

**Authentication**: Optional

**Path Parameters**:
- `user_id` (string, required): Owner's Firebase user ID

**Query Parameters**:
- `page` (integer, optional): Page number, default: `1`
- `limit` (integer, optional): Items per page, default: `20`, max: `100`

**Example**: `GET /api/studyhub/subjects/owner/firebase_user_id_123?page=1&limit=10`

**Response** (`200 OK`):
```json
{
  "subjects": [
    {
      "_id": "507f1f77bcf86cd799439011",
      "owner_id": "firebase_user_id_123",
      "title": "Introduction to Python Programming",
      "description": "Learn Python from scratch",
      "cover_image_url": "https://cdn.wordai.pro/studyhub/covers/507f1f77bcf86cd799439011.jpg",
      "status": "published",
      "visibility": "public",
      "metadata": {
        "total_modules": 5,
        "total_learners": 142,
        "avg_rating": 4.7,
        "tags": ["python", "programming"]
      },
      "created_at": "2026-01-08T10:30:00Z",
      "updated_at": "2026-01-08T14:20:00Z",
      "is_enrolled": false,
      "is_owner": true
    }
  ],
  "total": 12,
  "page": 1,
  "limit": 10,
  "has_more": true
}
```

**Visibility Logic**:
- Viewing own profile: See all subjects (public + private)
- Viewing other's profile: Only see published public subjects

**Status Codes**:
- `200`: Success
- `400`: Invalid user ID
- `500`: Server error

---

#### 7. Upload Cover Image

**Endpoint**: `POST /api/studyhub/subjects/{subject_id}/cover`

**Authentication**: Required (owner only)

**Content-Type**: `multipart/form-data`

**Request Body**:
- `file` (file, required): Image file (JPEG, PNG, WebP)

**File Requirements**:
- Allowed types: `image/jpeg`, `image/png`, `image/webp`
- Max size: 5MB
- Will be automatically resized to max 1200x800 (maintains aspect ratio)
- Converted to JPEG format with 85% quality

**Example (JavaScript)**:
```javascript
const formData = new FormData();
formData.append('file', imageFile);

fetch('/api/studyhub/subjects/507f1f77bcf86cd799439011/cover', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${firebaseToken}`
  },
  body: formData
});
```

**Response** (`200 OK`):
```json
{
  "cover_image_url": "https://cdn.wordai.pro/studyhub/covers/507f1f77bcf86cd799439011.jpg",
  "subject_id": "507f1f77bcf86cd799439011"
}
```

**Status Codes**:
- `200`: Cover uploaded successfully
- `400`: Invalid file type or size
- `401`: Unauthorized
- `404`: Subject not found or not owner
- `500`: Server error

---

#### 8. Publish Subject

**Endpoint**: `POST /api/studyhub/subjects/{subject_id}/publish`

**Authentication**: Required (owner only)

**Request Body**: None

**Response** (`200 OK`):
```json
{
  "_id": "507f1f77bcf86cd799439011",
  "owner_id": "firebase_user_id_123",
  "title": "Introduction to Python Programming",
  "description": "Learn Python from scratch",
  "cover_image_url": "https://cdn.wordai.pro/studyhub/covers/507f1f77bcf86cd799439011.jpg",
  "status": "published",
  "visibility": "public",
  "metadata": {
    "total_modules": 5,
    "total_learners": 0,
    "avg_rating": 0.0,
    "tags": []
  },
  "created_at": "2026-01-08T10:30:00Z",
  "updated_at": "2026-01-08T16:00:00Z",
  "is_enrolled": false,
  "is_owner": true
}
```

**Validation**:
- Subject must have at least 1 module
- If validation fails, returns:

```json
{
  "detail": "Cannot publish subject without at least 1 module"
}
```

**Status Codes**:
- `200`: Subject published successfully
- `400`: Validation failed (no modules)
- `401`: Unauthorized
- `404`: Subject not found or not owner
- `500`: Server error

---

## Data Models

### Subject Status Enum
- `draft`: Subject is being edited, not visible to public
- `published`: Subject is live and visible based on visibility setting
- `archived`: Subject is deleted (soft delete)

### Subject Visibility Enum
- `public`: Anyone can view (if published)
- `private`: Only owner and enrolled learners can view

### Subject Metadata Object
```typescript
{
  total_modules: number;      // Count of modules
  total_learners: number;     // Count of enrolled learners (active)
  avg_rating: number;         // Average rating (0-5)
  tags: string[];            // Tags for search/categorization
}
```

---

## Error Handling

All endpoints follow standard error response format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

### Common Error Codes

- `400 Bad Request`: Invalid input data, validation failed
- `401 Unauthorized`: Missing or invalid authentication token
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found or no access
- `500 Internal Server Error`: Server-side error

---

## Rate Limiting

- Authenticated users: 1000 requests per minute
- Unauthenticated users: 100 requests per minute
- Cover upload: 10 uploads per minute per user

---

## Notes for Frontend Implementation

### Authentication
Use Firebase ID Token for all authenticated requests:
```javascript
const token = await firebase.auth().currentUser.getIdToken();
const headers = {
  'Authorization': `Bearer ${token}`,
  'Content-Type': 'application/json'
};
```

### Image Upload
Use FormData for multipart/form-data:
```javascript
const formData = new FormData();
formData.append('file', imageFile);
// Don't set Content-Type header - browser will set it automatically
```

### Pagination
Calculate total pages:
```javascript
const totalPages = Math.ceil(response.total / response.limit);
const hasNextPage = response.has_more;
```

### Error Handling
```javascript
try {
  const response = await fetch('/api/studyhub/subjects', {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail);
  }
  
  const data = await response.json();
  // Handle success
} catch (error) {
  // Handle error
  console.error(error.message);
}
```

---

## Future Phases

This document will be updated as new milestones are implemented:
- **Phase 1.2**: Module & Content Management APIs
- **Phase 1.3**: Enrollment & Progress Tracking APIs
- **Phase 1.4**: Discovery & Search APIs
- **Phase 2.1**: Content Integration (Books, Tests, Slides)
- **Phase 2.2**: Monetization APIs
- **Phase 2.3**: Analytics APIs

---

**Document Version**: 1.0  
**Last Updated**: January 8, 2026  
**Milestone**: 1.1 (Subject Core)
