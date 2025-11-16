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
  "visibility": "public | private | unlisted (default: private)",
  "icon": "string (emoji, optional)",
  "color": "string (#RRGGBB format, optional)",
  "enable_toc": "boolean (default: true)",
  "enable_search": "boolean (default: true)",
  "enable_feedback": "boolean (default: true)",
  "custom_domain": "string (optional)",
  "cover_image_url": "string (optional, use /upload-image/presigned-url to upload)",
  "logo_url": "string (optional, use /upload-image/presigned-url to upload)",
  "favicon_url": "string (optional, use /upload-image/presigned-url to upload)"
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

**Note**: To upload images (cover, logo, favicon), first use `POST /books/upload-image/presigned-url` to get upload URL, then update book with the returned file_url.

---

### 1a. Upload Book Images (Cover, Logo, Favicon)
**Endpoint**: `POST /books/upload-image/presigned-url`
**Authentication**: Required

**Description**: Generate presigned URL for uploading book images (cover, logo, favicon) directly to R2 storage.

**Request Body**:
```json
{
  "filename": "my-book-cover.jpg",  // Required, max 255 chars
  "content_type": "image/jpeg",  // Required: image/jpeg, image/png, image/webp, image/svg+xml, image/gif
  "image_type": "cover",  // Required: "cover" | "logo" | "favicon"
  "file_size_mb": 2.5  // Required, max 10MB
}
```

**Response 200**:
```json
{
  "success": true,
  "presigned_url": "https://r2.cloudflare.com/...",  // Use PUT request to upload
  "file_url": "https://cdn.wordai.pro/book-covers/...",  // Use this in book update
  "image_type": "cover",
  "file_size_mb": 2.5,
  "expires_in": 300  // Seconds (5 minutes)
}
```



**Image Types**:
- `cover`: Book cover image (recommended: 1200x630px for og:image)
- `logo`: Book logo (recommended: 512x512px square)
- `favicon`: Book favicon (recommended: 32x32px or 64x64px)

**Constraints**:
- Max file size: 10MB per image
- Allowed formats: JPEG, PNG, WebP, SVG, GIF
- URL expires in 5 minutes

**Errors**:
- `400 Bad Request`: Invalid content_type or image_type
- `422 Unprocessable Entity`: Validation error (file too large, etc.)
- `500 Internal Server Error`: R2 service error

---

### 1b. Delete Book Image (Cover, Logo, Favicon)
**Endpoint**: `DELETE /books/{book_id}/delete-image/{image_type}`
**Authentication**: Required

**Description**: Delete book image (cover, logo, or favicon). Clears the image URL from database.

**Path Parameters**:
- `book_id`: string (required)
- `image_type`: string (required) - "cover" | "logo" | "favicon"

**Response 200**:
```json
{
  "success": true,
  "message": "Successfully deleted cover image",
  "image_type": "cover",
  "book_id": "string",
  "deleted_url": "https://cdn.wordai.pro/book-covers/..."
}
```

**Response 200** (if no image to delete):
```json
{
  "success": true,
  "message": "No cover image to delete",
  "image_type": "cover",
  "book_id": "string"
}
```

**Use Cases**:
- User wants to change image → Delete old one first, then upload new one
- User wants to remove image completely
- Cleaning up before uploading new version

**Errors**:
- `400 Bad Request`: Invalid image_type
- `404 Not Found`: Book not found or not owned by user
- `500 Internal Server Error`: Delete failed

**Example Usage**:
```javascript
// Delete cover image before uploading new one
await fetch('/api/v1/books/{book_id}/delete-image/cover', {
  method: 'DELETE',
  headers: { 'Authorization': 'Bearer <token>' }
})

// Then upload new cover
const response = await fetch('/api/v1/books/upload-image/presigned-url', {
  method: 'POST',
  body: JSON.stringify({
    filename: 'new-cover.jpg',
    content_type: 'image/jpeg',
    image_type: 'cover',
    file_size_mb: 1.2
  })
})
```

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

**Description**: Publish a book to the community marketplace. Must include author information (existing author_id OR new author details).

**Request Body**:
```json
{
  // AUTHOR (Required - choose one of two scenarios below)
  // Scenario A: Use existing author
  "author_id": "@john_doe",  // Existing author @username

  // Scenario B: Create new author (requires author_id + author_name)
  "author_id": "@new_author",  // User-provided @username (must be available)
  "author_name": "Display Name",  // Required for new author
  "author_bio": "Bio text",  // Optional for new author
  "author_avatar_url": "https://...",  // Optional for new author

  // BOOK VISIBILITY & PRICING
  "visibility": "public | point_based",  // Required
  "access_config": {  // Required if visibility = "point_based"
    "one_time_view_points": 10,
    "forever_view_points": 50,
    "download_pdf_points": 20,
    "is_one_time_enabled": true,
    "is_forever_enabled": true,
    "is_download_enabled": true
  },

  // COMMUNITY METADATA
  "category": "string (required, e.g., 'Programming', 'Business')",
  "tags": ["string", "string"],  // Required, 1-10 tags
  "difficulty_level": "beginner | intermediate | advanced | expert",
  "short_description": "string (10-200 chars)",
  "cover_image_url": "string (optional)"
}
```

**Response 200**:
```json
{
  "book_id": "string",
  "visibility": "public",
  "author_id": "@john_doe",
  "access_config": {
    "one_time_view_points": 10,
    "forever_view_points": 50,
    "download_pdf_points": 20
  },
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
  },
  "stats": {
    "total_revenue_points": 0,
    "owner_reward_points": 0,
    "system_fee_points": 0
  }
}
```

**Errors**:
- `404 Not Found`: Book not found or not owned by user
- `400 Bad Request`: Missing required fields (author_id or author_id + author_name)
- `409 Conflict`: Author ID already taken (when creating new author)
- `403 Forbidden`: Author exists but not owned by you

**Important Notes**:
1. Always call `GET /authors/check/{author_id}` first to verify @username availability
2. When creating new author: both `author_id` and `author_name` are required
3. Author ID format: `@[a-z0-9_]{3,30}` (lowercase, alphanumeric + underscore, 3-30 chars)

---

### 3. Unpublish Book from Community
**Endpoint**: `PATCH /books/{book_id}/unpublish-community`
**Authentication**: Required

**Description**: Remove book from community marketplace. Resets visibility to private and clears author association.

**Path Parameters**:
- `book_id`: string (required)

**Response 200**:
```json
{
  "book_id": "string",
  "visibility": "private",
  "author_id": null,
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

### 5. Get Popular Tags
**Endpoint**: `GET /books/community/tags`
**Authentication**: NOT required (public)

**Query Parameters**:
- `limit`: integer (default: 20, min: 1, max: 100)

**Response 200**:
```json
{
  "tags": [
    {"tag": "python", "count": 150},
    {"tag": "javascript", "count": 120},
    {"tag": "tutorial", "count": 95},
    {"tag": "beginner", "count": 80}
  ],
  "total": 50
}
```

**Description**: Returns most used tags in community marketplace, sorted by book count.

---

### 6. Get Top Books
**Endpoint**: `GET /books/community/top`
**Authentication**: NOT required (public)

**Query Parameters**:
- `period`: string (optional, "week" | "month" | "all", default: "month")
- `limit`: integer (default: 10, min: 1, max: 50)

**Response 200**:
```json
{
  "books": [
    {
      "book_id": "string",
      "title": "string",
      "slug": "string",
      "author_id": "@john_doe",
      "author_name": "John Doe",
      "cover_image_url": "https://...",
      "total_views": 1500,
      "total_purchases": 250,
      "average_rating": 4.8,
      "published_at": "ISO 8601 datetime"
    }
  ],
  "period": "month",
  "total": 10
}
```

**Description**: Returns top performing books by views and purchases in specified time period.

---

### 7. Get Top Authors
**Endpoint**: `GET /books/community/top-authors`
**Authentication**: NOT required (public)

**Query Parameters**:
- `period`: string (optional, "week" | "month" | "all", default: "month")
- `limit`: integer (default: 10, min: 1, max: 50)

**Response 200**:
```json
{
  "authors": [
    {
      "author_id": "@john_doe",
      "name": "John Doe",
      "avatar_url": "https://...",
      "total_books": 5,
      "total_followers": 120,
      "total_revenue_points": 45000,
      "average_rating": 4.7
    }
  ],
  "period": "month",
  "total": 10
}
```

**Description**: Returns top performing authors by books and revenue in specified time period.

---

### 8. Create Chapter from Document
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

### 9. Get Chapter with Content (Supports Document References)
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

## 👤 Author Management APIs (Community Books)

### Author System Overview
Authors are separate identities for publishing books to the community marketplace:
- **1 User → Many Authors**: One Firebase UID can create multiple author profiles
- **1 Author → 1 User**: Each author profile belongs to exactly one user
- **@username format**: All author IDs use @username format (e.g., @john_doe)
- **Publishing requirement**: Must select or create an author when publishing to community

### 1. Check Author ID Availability
**Endpoint**: `GET /authors/check/{author_id}`
**Authentication**: Not required (public endpoint)

**Description**: Check if an @username is available for registration.

**Path Parameters**:
- `author_id`: string (e.g., @john_doe)

**Response 200**:
```json
{
  "available": true,
  "author_id": "@john_doe"
}
```

**Use Case**: Frontend should call this endpoint when user types @username to show real-time availability status (green check ✅ or red X ❌).

---

### 2. Create Author Profile
**Endpoint**: `POST /authors`
**Authentication**: Required

**Description**: Create a new author profile with a unique @username.

**Request Body**:
```json
{
  "author_id": "@john_doe",  // Required, must be unique, format: @[a-z0-9_]{3,30}
  "name": "John Doe",  // Required, display name (2-100 chars)
  "bio": "Software engineer and technical writer",  // Optional (max 500 chars)
  "avatar_url": "https://...",  // Optional
  "website_url": "https://johndoe.com",  // Optional
  "social_links": {  // Optional
    "twitter": "https://twitter.com/johndoe",
    "github": "https://github.com/johndoe",
    "linkedin": "https://linkedin.com/in/johndoe"
  }
}
```

**Response 201**:
```json
{
  "author_id": "@john_doe",
  "user_id": "firebase_uid_123",
  "name": "John Doe",
  "bio": "Software engineer and technical writer",
  "avatar_url": "https://...",
  "website_url": "https://johndoe.com",
  "social_links": {
    "twitter": "https://twitter.com/johndoe",
    "github": "https://github.com/johndoe"
  },
  "books": [],
  "total_books": 0,
  "total_followers": 0,
  "total_revenue_points": 0,
  "created_at": "ISO 8601 datetime",
  "updated_at": "ISO 8601 datetime"
}
```

**Errors**:
- `409 Conflict`: Author ID already taken
- `400 Bad Request`: Invalid author_id format (must be @lowercase_alphanumeric_underscore, 3-30 chars)

---

### 3. List My Authors
**Endpoint**: `GET /authors/my-authors`
**Authentication**: Required

**Description**: List all author profiles created by the current user.

**Query Parameters**:
- `skip`: integer (default: 0)
- `limit`: integer (default: 20, max: 100)

**Response 200**:
```json
{
  "authors": [
    {
      "author_id": "@john_doe",
      "name": "John Doe",
      "avatar_url": "https://...",
      "total_books": 5,
      "total_followers": 120,
      "created_at": "ISO 8601 datetime"
    },
    {
      "author_id": "@jane_tech",
      "name": "Jane Smith",
      "avatar_url": "https://...",
      "total_books": 3,
      "total_followers": 85,
      "created_at": "ISO 8601 datetime"
    }
  ],
  "total": 2,
  "skip": 0,
  "limit": 20
}
```

---

### 4. Get Author Profile (Public)
**Endpoint**: `GET /authors/{author_id}`
**Authentication**: Not required (public endpoint)

**Description**: Get public author profile with book list.

**Path Parameters**:
- `author_id`: string (e.g., @john_doe)

**Response 200**:
```json
{
  "author_id": "@john_doe",
  "name": "John Doe",
  "bio": "Software engineer and technical writer",
  "avatar_url": "https://...",
  "website_url": "https://johndoe.com",
  "social_links": {
    "twitter": "https://twitter.com/johndoe",
    "github": "https://github.com/johndoe"
  },
  "books": [
    {
      "book_id": "uuid-123",
      "title": "Python Advanced Guide",
      "cover_image_url": "https://...",
      "category": "Programming",
      "difficulty_level": "advanced",
      "total_purchases": 150,
      "average_rating": 4.5
    }
  ],
  "total_books": 5,
  "total_followers": 120,
  "total_revenue_points": 45000,
  "created_at": "ISO 8601 datetime"
}
```

**Errors**:
- `404 Not Found`: Author not found

---

### 5. Update Author Profile
**Endpoint**: `PATCH /authors/{author_id}`
**Authentication**: Required

**Description**: Update author profile (only owner can update).

**Path Parameters**:
- `author_id`: string (e.g., @john_doe)

**Request Body** (all fields optional):
```json
{
  "name": "John Doe Jr.",
  "bio": "Updated bio",
  "avatar_url": "https://...",
  "website_url": "https://johndoe.dev",
  "social_links": {
    "twitter": "https://twitter.com/johndoe",
    "github": "https://github.com/johndoe"
  }
}
```

**Response 200**:
```json
{
  "author_id": "@john_doe",
  "name": "John Doe Jr.",
  "bio": "Updated bio",
  "avatar_url": "https://...",
  "website_url": "https://johndoe.dev",
  "social_links": {
    "twitter": "https://twitter.com/johndoe",
    "github": "https://github.com/johndoe"
  },
  "total_books": 5,
  "total_followers": 120,
  "updated_at": "ISO 8601 datetime"
}
```

**Errors**:
- `404 Not Found`: Author not found
- `403 Forbidden`: You don't own this author profile

---

### 6. Delete Author Profile
**Endpoint**: `DELETE /authors/{author_id}`
**Authentication**: Required

**Description**: Delete author profile (only if no published books).

**Path Parameters**:
- `author_id`: string (e.g., @john_doe)

**Response 200**:
```json
{
  "message": "Author deleted successfully",
  "author_id": "@john_doe"
}
```

**Errors**:
- `404 Not Found`: Author not found
- `403 Forbidden`: You don't own this author profile
- `400 Bad Request`: Cannot delete author with published books (unpublish books first)

---

### 7. Browse All Authors (Public)
**Endpoint**: `GET /authors`
**Authentication**: Not required (public endpoint)

**Description**: Browse and search all authors in the community.

**Query Parameters**:
- `search`: string (optional, text search in name and bio)
- `skip`: integer (default: 0)
- `limit`: integer (default: 20, max: 100)

**Response 200**:
```json
{
  "authors": [
    {
      "author_id": "@john_doe",
      "name": "John Doe",
      "avatar_url": "https://...",
      "bio": "Software engineer...",
      "total_books": 5,
      "total_followers": 120,
      "average_rating": 4.5
    }
  ],
  "total": 50,
  "skip": 0,
  "limit": 20
}
```

---

### Publishing Flow with Authors

#### Scenario 1: Publishing with Existing Author
```json
POST /books/{book_id}/publish-community

{
  "author_id": "@john_doe",  // Existing author (no other author fields needed)
  "visibility": "public",
  "category": "Programming",
  "tags": ["python", "tutorial"],
  "difficulty_level": "intermediate",
  "short_description": "Learn Python basics"
}
```

#### Scenario 2: Publishing with New Author
**Step 1**: Check availability
```
GET /authors/check/@new_author
Response: {"available": true, "author_id": "@new_author"}
```

**Step 2**: Publish with new author data
```json
POST /books/{book_id}/publish-community

{
  "author_id": "@new_author",  // User-provided @username (required)
  "author_name": "New Author",  // Display name (required for new author)
  "author_bio": "Bio text",  // Optional
  "author_avatar_url": "https://...",  // Optional
  "visibility": "public",
  "category": "Programming",
  "tags": ["python"],
  "difficulty_level": "beginner",
  "short_description": "Book description"
}
```

**Backend will**:
1. Validate author_id format (@username)
2. Check if author_id is available (return 409 if taken)
3. Create new author profile automatically
4. Publish book to community with author

---

## 📊 Common Error Response Format

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
7. **Author IDs**: Must follow @username format, lowercase alphanumeric + underscore, 3-30 chars

---

## 🚀 Total Endpoints: 36

- **Phase 2**: 7 endpoints (Book Management + Image Upload/Delete)
  - Create, List, Get, Update, Delete Book
  - Upload Image (Presigned URL)
  - Delete Image
- **Phase 3**: 5 endpoints (Chapter Management)
- **Phase 4**: 4 endpoints (User Permissions)
- **Phase 5**: 4 endpoints (Public View - NO AUTH)
- **Phase 6**: 9 endpoints (Point System, Community Books, Document Integration)
  - Publish to Community
  - Browse Community Books
  - Get Popular Tags (NEW)
  - Get Top Books (NEW)
  - Get Top Authors (NEW)
  - Create Chapter from Document
  - Get Chapter with Content
  - Update Community Config
  - Update Access Prices
- **Authors**: 7 endpoints (Author Management for Community Books)

**Last Updated**: January 2025
