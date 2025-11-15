# Frontend API Specifications - Online Books System

**Base URL**: `https://wordai.com/api/v1`

**Authentication**: Firebase JWT token in `Authorization: Bearer <token>` header (except Public APIs)

---

## 📚 Phase 2: Book Management APIs

### 1. Create Book
**Endpoint**: `POST /books`
**Authentication**: Required

**Request Body**:
```json
{
  "title": "string (1-200 chars, required)",
  "slug": "string (alphanumeric + hyphens, required)",
  "description": "string (max 1000 chars, optional)",
  "visibility": "public | private | unlisted (default: public)",
  "icon": "string (emoji, optional)",
  "color": "string (#RRGGBB format, optional)",
  "enable_toc": "boolean (default: true)",
  "enable_search": "boolean (default: true)",
  "enable_feedback": "boolean (default: true)",
  "custom_domain": "string (optional)",
  "cover_image_url": "string (optional)",
  "logo_url": "string (optional)",
  "favicon_url": "string (optional)"
}
```

**Response 201**:
```json
{
  "book_id": "string",
  "user_id": "string",
  "title": "string",
  "slug": "string",
  "description": "string",
  "visibility": "string",
  "is_indexed": "boolean",
  "custom_domain": "string",
  "cover_image_url": "string",
  "logo_url": "string",
  "favicon_url": "string",
  "icon": "string",
  "color": "string",
  "enable_toc": "boolean",
  "enable_search": "boolean",
  "enable_feedback": "boolean",
  "created_at": "ISO 8601 datetime",
  "updated_at": "ISO 8601 datetime"
}
```

**Errors**:
- `409 Conflict`: Slug already exists for this user
- `422 Unprocessable Entity`: Validation error
- `401 Unauthorized`: Missing or invalid token

---

### 2. List User's Books
**Endpoint**: `GET /books`
**Authentication**: Required

**Query Parameters**:
- `skip`: integer (default: 0, pagination offset)
- `limit`: integer (default: 50, max: 100)
- `visibility`: string (filter: "public" | "private" | "unlisted", optional)

**Response 200**:
```json
{
  "books": [
    {
      "book_id": "string",
      "user_id": "string",
      "title": "string",
      "slug": "string",
      "description": "string",
      "visibility": "string",
      "icon": "string",
      "color": "string",
      "created_at": "ISO 8601 datetime",
      "updated_at": "ISO 8601 datetime"
    }
  ],
  "total": "integer",
  "skip": "integer",
  "limit": "integer"
}
```

**Errors**:
- `401 Unauthorized`: Missing or invalid token

---

### 3. Get Book by ID
**Endpoint**: `GET /books/{book_id}`
**Authentication**: Required

**Path Parameters**:
- `book_id`: string (required)

**Response 200**:
```json
{
  "book_id": "string",
  "user_id": "string",
  "title": "string",
  "slug": "string",
  "description": "string",
  "visibility": "string",
  "is_indexed": "boolean",
  "custom_domain": "string",
  "cover_image_url": "string",
  "logo_url": "string",
  "favicon_url": "string",
  "icon": "string",
  "color": "string",
  "enable_toc": "boolean",
  "enable_search": "boolean",
  "enable_feedback": "boolean",
  "created_at": "ISO 8601 datetime",
  "updated_at": "ISO 8601 datetime"
}
```

**Errors**:
- `404 Not Found`: Book not found
- `403 Forbidden`: User is not the owner
- `401 Unauthorized`: Missing or invalid token

---

### 4. Update Book
**Endpoint**: `PATCH /books/{book_id}`
**Authentication**: Required

**Path Parameters**:
- `book_id`: string (required)

**Request Body** (all fields optional):
```json
{
  "title": "string (1-200 chars)",
  "slug": "string (alphanumeric + hyphens)",
  "description": "string (max 1000 chars)",
  "visibility": "public | private | unlisted",
  "icon": "string",
  "color": "string",
  "enable_toc": "boolean",
  "enable_search": "boolean",
  "enable_feedback": "boolean",
  "custom_domain": "string",
  "cover_image_url": "string",
  "logo_url": "string",
  "favicon_url": "string"
}
```

**Response 200**:
```json
{
  "book_id": "string",
  "user_id": "string",
  "title": "string",
  "slug": "string",
  "description": "string",
  "visibility": "string",
  "is_indexed": "boolean",
  "custom_domain": "string",
  "cover_image_url": "string",
  "logo_url": "string",
  "favicon_url": "string",
  "icon": "string",
  "color": "string",
  "enable_toc": "boolean",
  "enable_search": "boolean",
  "enable_feedback": "boolean",
  "created_at": "ISO 8601 datetime",
  "updated_at": "ISO 8601 datetime"
}
```

**Errors**:
- `404 Not Found`: Book not found
- `403 Forbidden`: User is not the owner
- `409 Conflict`: Slug already exists
- `422 Unprocessable Entity`: Validation error
- `401 Unauthorized`: Missing or invalid token

---

### 5. Delete Book
**Endpoint**: `DELETE /books/{book_id}`
**Authentication**: Required

**Path Parameters**:
- `book_id`: string (required)

**Response 200**:
```json
{
  "message": "Book deleted successfully",
  "book_id": "string"
}
```

**Errors**:
- `404 Not Found`: Book not found
- `403 Forbidden`: User is not the owner
- `401 Unauthorized`: Missing or invalid token

---

## 📖 Phase 3: Chapter Management APIs

### 6. Create Chapter
**Endpoint**: `POST /books/{book_id}/chapters`
**Authentication**: Required

**Path Parameters**:
- `book_id`: string (required)

**Request Body**:
```json
{
  "title": "string (1-200 chars, required)",
  "slug": "string (alphanumeric + hyphens, required)",
  "document_id": "string (required)",
  "parent_id": "string (parent chapter ID for nesting, optional)",
  "order_index": "integer (display order, default: 0)",
  "is_published": "boolean (default: true)"
}
```

**Response 201**:
```json
{
  "chapter_id": "string",
  "book_id": "string",
  "title": "string",
  "slug": "string",
  "document_id": "string",
  "parent_id": "string",
  "order_index": "integer",
  "depth": "integer",
  "is_published": "boolean",
  "created_at": "ISO 8601 datetime",
  "updated_at": "ISO 8601 datetime"
}
```

**Errors**:
- `404 Not Found`: Book not found
- `403 Forbidden`: User is not the book owner
- `409 Conflict`: Slug already exists in this book
- `400 Bad Request`: Max nesting depth exceeded (3 levels max)
- `422 Unprocessable Entity`: Validation error
- `401 Unauthorized`: Missing or invalid token

---

### 7. List Chapters
**Endpoint**: `GET /books/{book_id}/chapters`
**Authentication**: Required

**Path Parameters**:
- `book_id`: string (required)

**Query Parameters**:
- `include_unpublished`: boolean (default: false)

**Response 200**:
```json
{
  "chapters": [
    {
      "chapter_id": "string",
      "book_id": "string",
      "title": "string",
      "slug": "string",
      "document_id": "string",
      "parent_id": "string",
      "order_index": "integer",
      "depth": "integer",
      "is_published": "boolean",
      "created_at": "ISO 8601 datetime",
      "updated_at": "ISO 8601 datetime"
    }
  ],
  "total": "integer"
}
```

**Errors**:
- `404 Not Found`: Book not found
- `403 Forbidden`: User is not the book owner
- `401 Unauthorized`: Missing or invalid token

---

### 8. Update Chapter
**Endpoint**: `PATCH /books/{book_id}/chapters/{chapter_id}`
**Authentication**: Required

**Path Parameters**:
- `book_id`: string (required)
- `chapter_id`: string (required)

**Request Body** (all fields optional):
```json
{
  "title": "string (1-200 chars)",
  "slug": "string (alphanumeric + hyphens)",
  "parent_id": "string",
  "order_index": "integer",
  "is_published": "boolean"
}
```

**Response 200**:
```json
{
  "chapter_id": "string",
  "book_id": "string",
  "title": "string",
  "slug": "string",
  "document_id": "string",
  "parent_id": "string",
  "order_index": "integer",
  "depth": "integer",
  "is_published": "boolean",
  "created_at": "ISO 8601 datetime",
  "updated_at": "ISO 8601 datetime"
}
```

**Errors**:
- `404 Not Found`: Book or chapter not found
- `403 Forbidden`: User is not the book owner
- `409 Conflict`: Slug already exists
- `400 Bad Request`: Max nesting depth exceeded
- `422 Unprocessable Entity`: Validation error
- `401 Unauthorized`: Missing or invalid token

---

### 9. Delete Chapter
**Endpoint**: `DELETE /books/{book_id}/chapters/{chapter_id}`
**Authentication**: Required

**Path Parameters**:
- `book_id`: string (required)
- `chapter_id`: string (required)

**Response 200**:
```json
{
  "message": "Chapter deleted successfully",
  "chapter_id": "string",
  "book_id": "string"
}
```

**Errors**:
- `404 Not Found`: Book or chapter not found
- `403 Forbidden`: User is not the book owner
- `401 Unauthorized`: Missing or invalid token

---

### 10. Reorder Chapters (Bulk)
**Endpoint**: `POST /books/{book_id}/chapters/reorder`
**Authentication**: Required

**Path Parameters**:
- `book_id`: string (required)

**Request Body**:
```json
{
  "updates": [
    {
      "chapter_id": "string (required)",
      "parent_id": "string (optional, null for root)",
      "order_index": "integer (default: 0)"
    }
  ]
}
```

**Response 200**:
```json
{
  "message": "Chapters reordered successfully",
  "updated_count": "integer",
  "chapters": [
    {
      "chapter_id": "string",
      "book_id": "string",
      "title": "string",
      "slug": "string",
      "parent_id": "string",
      "order_index": "integer",
      "depth": "integer",
      "updated_at": "ISO 8601 datetime"
    }
  ]
}
```

**Errors**:
- `404 Not Found`: Book not found
- `403 Forbidden`: User is not the book owner
- `400 Bad Request`: Invalid reorder operation
- `422 Unprocessable Entity`: Validation error
- `401 Unauthorized`: Missing or invalid token

---

## 🔐 Phase 4: User Permissions APIs

### 11. Grant Permission
**Endpoint**: `POST /books/{book_id}/permissions/users`
**Authentication**: Required (Owner only)

**Path Parameters**:
- `book_id`: string (required)

**Request Body**:
```json
{
  "user_id": "string (Firebase UID, required)",
  "access_level": "viewer | editor (default: viewer)",
  "expires_at": "ISO 8601 datetime (optional)"
}
```

**Response 201**:
```json
{
  "permission_id": "string",
  "book_id": "string",
  "user_id": "string",
  "granted_by": "string",
  "access_level": "string",
  "status": "active",
  "expires_at": "ISO 8601 datetime",
  "created_at": "ISO 8601 datetime",
  "updated_at": "ISO 8601 datetime"
}
```

**Errors**:
- `404 Not Found`: Book not found
- `403 Forbidden`: User is not the book owner
- `409 Conflict`: Permission already exists for this user
- `422 Unprocessable Entity`: Validation error
- `401 Unauthorized`: Missing or invalid token

---

### 12. List Permissions
**Endpoint**: `GET /books/{book_id}/permissions/users`
**Authentication**: Required (Owner only)

**Path Parameters**:
- `book_id`: string (required)

**Query Parameters**:
- `skip`: integer (default: 0)
- `limit`: integer (default: 50, max: 100)
- `status`: string (filter: "active" | "pending" | "expired", optional)

**Response 200**:
```json
{
  "permissions": [
    {
      "permission_id": "string",
      "user_id": "string",
      "access_level": "string",
      "status": "string",
      "expires_at": "ISO 8601 datetime",
      "created_at": "ISO 8601 datetime"
    }
  ],
  "total": "integer",
  "skip": "integer",
  "limit": "integer"
}
```

**Errors**:
- `404 Not Found`: Book not found
- `403 Forbidden`: User is not the book owner
- `401 Unauthorized`: Missing or invalid token

---

### 13. Revoke Permission
**Endpoint**: `DELETE /books/{book_id}/permissions/users/{permission_user_id}`
**Authentication**: Required (Owner only)

**Path Parameters**:
- `book_id`: string (required)
- `permission_user_id`: string (user ID to revoke, required)

**Response 200**:
```json
{
  "message": "Permission revoked successfully",
  "revoked": {
    "book_id": "string",
    "user_id": "string",
    "revoked_by": "string"
  }
}
```

**Errors**:
- `404 Not Found`: Book or permission not found
- `403 Forbidden`: User is not the book owner
- `401 Unauthorized`: Missing or invalid token

---

### 14. Invite User by Email
**Endpoint**: `POST /books/{book_id}/permissions/invite`
**Authentication**: Required (Owner only)

**Path Parameters**:
- `book_id`: string (required)

**Request Body**:
```json
{
  "email": "string (email address, required)",
  "access_level": "viewer | editor (default: viewer)",
  "expires_at": "ISO 8601 datetime (optional)",
  "message": "string (personal message, max 500 chars, optional)"
}
```

**Response 201**:
```json
{
  "invitation": {
    "permission_id": "string",
    "book_id": "string",
    "invited_email": "string",
    "access_level": "string",
    "status": "pending",
    "invitation_token": "string (43 chars)",
    "invitation_message": "string",
    "expires_at": "ISO 8601 datetime",
    "created_at": "ISO 8601 datetime"
  },
  "email_sent": "boolean",
  "message": "string"
}
```

**Errors**:
- `404 Not Found`: Book not found
- `403 Forbidden`: User is not the book owner
- `400 Bad Request`: Invalid email address
- `422 Unprocessable Entity`: Validation error
- `401 Unauthorized`: Missing or invalid token

---

## 🌐 Phase 5: Public View APIs (NO AUTH)

### 15. Get Public Book
**Endpoint**: `GET /public/books/{slug}`
**Authentication**: None (Public access)

**Path Parameters**:
- `slug`: string (book slug, required)

**Response 200**:
```json
{
  "book_id": "string",
  "title": "string",
  "slug": "string",
  "description": "string",
  "visibility": "string",
  "custom_domain": "string",
  "is_indexed": "boolean",
  "cover_image_url": "string",
  "logo_url": "string",
  "favicon_url": "string",
  "author": {
    "user_id": "string",
    "display_name": "string",
    "avatar_url": "string"
  },
  "chapters": [
    {
      "chapter_id": "string",
      "title": "string",
      "slug": "string",
      "order": "integer",
      "description": "string",
      "icon": "string"
    }
  ],
  "stats": {
    "total_chapters": "integer",
    "total_views": "integer",
    "last_updated": "ISO 8601 datetime"
  },
  "seo": {
    "title": "string",
    "description": "string",
    "og_image": "string",
    "og_url": "string",
    "twitter_card": "string"
  },
  "branding": {
    "primary_color": "string",
    "font_family": "string",
    "custom_css": "string"
  },
  "created_at": "ISO 8601 datetime",
  "updated_at": "ISO 8601 datetime"
}
```

**Errors**:
- `404 Not Found`: Book not found
- `403 Forbidden`: Book is private (not accessible publicly)

---

### 16. Get Public Chapter
**Endpoint**: `GET /public/books/{book_slug}/chapters/{chapter_slug}`
**Authentication**: None (Public access)

**Path Parameters**:
- `book_slug`: string (book slug, required)
- `chapter_slug`: string (chapter slug, required)

**Response 200**:
```json
{
  "chapter_id": "string",
  "book_id": "string",
  "title": "string",
  "slug": "string",
  "order": "integer",
  "description": "string",
  "icon": "string",
  "content": {
    "type": "doc",
    "content": []
  },
  "book_info": {
    "book_id": "string",
    "title": "string",
    "slug": "string",
    "logo_url": "string",
    "custom_domain": "string"
  },
  "navigation": {
    "previous": {
      "chapter_id": "string",
      "title": "string",
      "slug": "string"
    },
    "next": {
      "chapter_id": "string",
      "title": "string",
      "slug": "string"
    }
  },
  "seo": {
    "title": "string",
    "description": "string",
    "og_image": "string",
    "og_url": "string",
    "twitter_card": "string"
  },
  "created_at": "ISO 8601 datetime",
  "updated_at": "ISO 8601 datetime"
}
```

**Errors**:
- `404 Not Found`: Book or chapter not found
- `403 Forbidden`: Book is private

---

### 17. Track View Analytics
**Endpoint**: `POST /public/books/{slug}/views`
**Authentication**: None (Public access)

**Path Parameters**:
- `slug`: string (book slug, required)

**Request Body**:
```json
{
  "chapter_slug": "string (optional)",
  "referrer": "string (optional)",
  "user_agent": "string (optional)",
  "session_id": "string (optional)"
}
```

**Response 200**:
```json
{
  "success": "boolean",
  "view_id": "string",
  "book_views": "integer",
  "chapter_views": "integer"
}
```

**Errors**:
- `404 Not Found`: Book not found
- `429 Too Many Requests`: Rate limit exceeded (10 req/min per IP)

---

### 18. Get Book by Custom Domain
**Endpoint**: `GET /books/by-domain/{domain}`
**Authentication**: None (Public access)

**Path Parameters**:
- `domain`: string (custom domain, required)

**Response 200**:
```json
{
  "book_id": "string",
  "slug": "string",
  "title": "string",
  "custom_domain": "string",
  "visibility": "string",
  "is_active": "boolean"
}
```

**Errors**:
- `404 Not Found`: No book found for domain

---

## 💎 Phase 6: Point System, Community Books & Document Integration

### Point System Overview
Users can set point-based access for their books:
- **One-time view**: Pay points to view once (temporary access)
- **Forever view**: Pay points for permanent view access
- **Download PDF**: Pay points to download PDF export

Revenue split: 80% to owner, 20% to system (same as Online Tests)

### 1. Create Book with Point Pricing
**Endpoint**: `POST /books`
**Authentication**: Required

**Request Body** (added fields):
```json
{
  "title": "string (required)",
  "slug": "string (required)",
  "visibility": "point_based",  // NEW: Added to existing enum
  "access_config": {  // NEW: Required if visibility = "point_based"
    "one_time_view_points": 10,
    "forever_view_points": 50,
    "download_pdf_points": 20,
    "is_one_time_enabled": true,
    "is_forever_enabled": true,
    "is_download_enabled": true
  }
}
```

**Response 201**:
```json
{
  "book_id": "string",
  "title": "string",
  "visibility": "point_based",
  "access_config": {
    "one_time_view_points": 10,
    "forever_view_points": 50,
    "download_pdf_points": 20,
    "is_one_time_enabled": true,
    "is_forever_enabled": true,
    "is_download_enabled": true
  },
  "community_config": {
    "is_public": false,
    "total_purchases": 0,
    "total_views": 0
  },
  "stats": {
    "total_revenue_points": 0,
    "owner_reward_points": 0,
    "system_fee_points": 0
  }
}
```

---

### 2. Publish Book to Community Marketplace
**Endpoint**: `POST /books/{book_id}/publish-community`
**Authentication**: Required

**Request Body**:
```json
{
  "category": "string (required, e.g., 'Programming', 'Business')",
  "tags": ["string", "string"],  // Required, max 5 tags
  "difficulty_level": "beginner | intermediate | advanced",
  "short_description": "string (max 500 chars)",
  "cover_image_url": "string (optional)"
}
```

**Response 200**:
```json
{
  "book_id": "string",
  "community_config": {
    "is_public": true,
    "category": "Programming",
    "tags": ["python", "tutorial"],
    "difficulty_level": "intermediate",
    "short_description": "Learn Python in 30 days",
    "cover_image_url": "https://...",
    "published_at": "ISO 8601 datetime",
    "total_purchases": 0,
    "total_views": 0,
    "average_rating": 0.0,
    "rating_count": 0
  }
}
```

**Errors**:
- `404 Not Found`: Book not found or not owned by user
- `400 Bad Request`: Failed to publish

---

### 3. Unpublish Book from Community
**Endpoint**: `PATCH /books/{book_id}/unpublish-community`
**Authentication**: Required

**Path Parameters**:
- `book_id`: string (required)

**Response 200**:
```json
{
  "book_id": "string",
  "community_config": {
    "is_public": false
  }
}
```

**Errors**:
- `404 Not Found`: Book not found or not owned by user

---

### 4. Browse Community Books (Public Marketplace)
**Endpoint**: `GET /books/community/books`
**Authentication**: NOT required (public)

**Query Parameters**:
- `category`: string (optional, filter by category)
- `tags`: string (optional, comma-separated tags, e.g., "python,tutorial")
- `difficulty`: string (optional, "beginner" | "intermediate" | "advanced")
- `sort_by`: string (optional, "popular" | "newest" | "rating", default: "popular")
- `page`: integer (default: 1, min: 1)
- `limit`: integer (default: 20, min: 1, max: 100)

**Response 200**:
```json
{
  "items": [
    {
      "book_id": "string",
      "title": "string",
      "slug": "string",
      "author_id": "string",
      "author_name": "string",
      "category": "Programming",
      "tags": ["python", "tutorial"],
      "difficulty_level": "intermediate",
      "short_description": "Learn Python in 30 days",
      "cover_image_url": "https://...",
      "access_config": {
        "one_time_view_points": 10,
        "forever_view_points": 50,
        "download_pdf_points": 20
      },
      "stats": {
        "total_purchases": 150,
        "total_views": 500,
        "average_rating": 4.5,
        "rating_count": 30
      },
      "published_at": "ISO 8601 datetime"
    }
  ],
  "total": 150,
  "page": 1,
  "limit": 20,
  "total_pages": 8
}
```

**Sort Options**:
- `popular`: Sorted by total_purchases + total_views (descending)
- `newest`: Sorted by published_at (newest first)
- `rating`: Sorted by average_rating + rating_count (descending)

---

### 5. Create Chapter from Document
**Endpoint**: `POST /books/{book_id}/chapters/from-document`
**Authentication**: Required

**Description**: Converts an existing document to a book chapter (no content duplication).

**Request Body**:
```json
{
  "document_id": "string (UUID, required)",
  "title": "string (required)",
  "order_index": 0,
  "parent_id": "string (optional, for nesting)",
  "icon": "📄",
  "is_published": false
}
```

**Response 201**:
```json
{
  "chapter_id": "string",
  "book_id": "string",
  "title": "string",
  "slug": "chapter-abc123",
  "icon": "📄",
  "order_index": 0,
  "parent_id": null,
  "depth": 0,
  "content_source": "document",  // "document" or "inline"
  "document_id": "string",
  "content_html": null,  // Not stored - loaded dynamically
  "content_json": null,
  "is_published": false,
  "created_at": "ISO 8601 datetime",
  "updated_at": "ISO 8601 datetime"
}
```

**Errors**:
- `404 Not Found`: Book not found or document not found
- `400 Bad Request`: Failed to create chapter

---

### 6. Get Chapter with Content (Supports Document References)
**Endpoint**: `GET /books/{book_id}/chapters/{chapter_id}/content`
**Authentication**: Required

**Description**: Gets chapter with content loaded dynamically. If chapter references a document, content is loaded from documents collection.

**Path Parameters**:
- `book_id`: string (required)
- `chapter_id`: string (required)

**Response 200**:
```json
{
  "chapter_id": "string",
  "book_id": "string",
  "title": "string",
  "content_source": "document",  // or "inline"
  "document_id": "string",  // Only if content_source = "document"
  "document_name": "My Document.txt",  // Only if content_source = "document"
  "content_html": "string (loaded from document or chapter)",
  "content_json": null,
  "is_published": true
}
```

**Errors**:
- `404 Not Found`: Book or chapter not found
- `403 Forbidden`: No access to book

---

## �📊 Common Error Response Format

All error responses follow this structure:

```json
{
  "detail": "string (error message)"
}
```

### HTTP Status Codes:
- `200 OK`: Request successful
- `201 Created`: Resource created successfully
- `400 Bad Request`: Invalid request data
- `401 Unauthorized`: Missing or invalid authentication token
- `403 Forbidden`: User lacks permission for this resource
- `404 Not Found`: Resource not found
- `409 Conflict`: Resource conflict (e.g., duplicate slug)
- `422 Unprocessable Entity`: Validation error
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

---

## 🔑 Authentication Header

For endpoints requiring authentication, include Firebase JWT:

```
Authorization: Bearer <firebase_jwt_token>
```

---

## 📝 Notes

1. **Pagination**: All list endpoints support `skip` and `limit` query parameters
2. **Date Format**: All timestamps use ISO 8601 format (`YYYY-MM-DDTHH:mm:ssZ`)
3. **Slugs**: Must be lowercase, alphanumeric with hyphens only (`^[a-z0-9-]+$`)
4. **Content**: TipTap JSON format for chapter content
5. **Rate Limiting**: Public endpoints have rate limits per IP address
6. **Visibility**:
   - `public`: Accessible to everyone, indexed by search engines
   - `unlisted`: Accessible via direct URL, NOT indexed
   - `private`: Only accessible to owner and users with permissions

---

## 🚀 Total Endpoints: 24

- **Phase 2**: 5 endpoints (Book Management)
- **Phase 3**: 5 endpoints (Chapter Management)
- **Phase 4**: 4 endpoints (User Permissions)
- **Phase 5**: 4 endpoints (Public View - NO AUTH)
- **Phase 6**: 6 endpoints (Point System, Community Books, Document Integration)

**Last Updated**: January 2025
