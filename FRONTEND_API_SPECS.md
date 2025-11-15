# Frontend API Specifications - User Guide System

**Base URL**: `https://wordai.com/api/v1`

**Authentication**: Firebase JWT token in `Authorization: Bearer <token>` header (except Public APIs)

---

## 📚 Phase 2: Guide Management APIs

### 1. Create Guide
**Endpoint**: `POST /guides`
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
  "guide_id": "string",
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

### 2. List User's Guides
**Endpoint**: `GET /guides`
**Authentication**: Required

**Query Parameters**:
- `skip`: integer (default: 0, pagination offset)
- `limit`: integer (default: 50, max: 100)
- `visibility`: string (filter: "public" | "private" | "unlisted", optional)

**Response 200**:
```json
{
  "guides": [
    {
      "guide_id": "string",
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

### 3. Get Guide by ID
**Endpoint**: `GET /guides/{guide_id}`
**Authentication**: Required

**Path Parameters**:
- `guide_id`: string (required)

**Response 200**:
```json
{
  "guide_id": "string",
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
- `404 Not Found`: Guide not found
- `403 Forbidden`: User is not the owner
- `401 Unauthorized`: Missing or invalid token

---

### 4. Update Guide
**Endpoint**: `PATCH /guides/{guide_id}`
**Authentication**: Required

**Path Parameters**:
- `guide_id`: string (required)

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
  "guide_id": "string",
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
- `404 Not Found`: Guide not found
- `403 Forbidden`: User is not the owner
- `409 Conflict`: Slug already exists
- `422 Unprocessable Entity`: Validation error
- `401 Unauthorized`: Missing or invalid token

---

### 5. Delete Guide
**Endpoint**: `DELETE /guides/{guide_id}`
**Authentication**: Required

**Path Parameters**:
- `guide_id`: string (required)

**Response 200**:
```json
{
  "message": "Guide deleted successfully",
  "guide_id": "string"
}
```

**Errors**:
- `404 Not Found`: Guide not found
- `403 Forbidden`: User is not the owner
- `401 Unauthorized`: Missing or invalid token

---

## 📖 Phase 3: Chapter Management APIs

### 6. Create Chapter
**Endpoint**: `POST /guides/{guide_id}/chapters`
**Authentication**: Required

**Path Parameters**:
- `guide_id`: string (required)

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
  "guide_id": "string",
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
- `404 Not Found`: Guide not found
- `403 Forbidden`: User is not the guide owner
- `409 Conflict`: Slug already exists in this guide
- `400 Bad Request`: Max nesting depth exceeded (3 levels max)
- `422 Unprocessable Entity`: Validation error
- `401 Unauthorized`: Missing or invalid token

---

### 7. List Chapters
**Endpoint**: `GET /guides/{guide_id}/chapters`
**Authentication**: Required

**Path Parameters**:
- `guide_id`: string (required)

**Query Parameters**:
- `include_unpublished`: boolean (default: false)

**Response 200**:
```json
{
  "chapters": [
    {
      "chapter_id": "string",
      "guide_id": "string",
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
- `404 Not Found`: Guide not found
- `403 Forbidden`: User is not the guide owner
- `401 Unauthorized`: Missing or invalid token

---

### 8. Update Chapter
**Endpoint**: `PATCH /guides/{guide_id}/chapters/{chapter_id}`
**Authentication**: Required

**Path Parameters**:
- `guide_id`: string (required)
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
  "guide_id": "string",
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
- `404 Not Found`: Guide or chapter not found
- `403 Forbidden`: User is not the guide owner
- `409 Conflict`: Slug already exists
- `400 Bad Request`: Max nesting depth exceeded
- `422 Unprocessable Entity`: Validation error
- `401 Unauthorized`: Missing or invalid token

---

### 9. Delete Chapter
**Endpoint**: `DELETE /guides/{guide_id}/chapters/{chapter_id}`
**Authentication**: Required

**Path Parameters**:
- `guide_id`: string (required)
- `chapter_id`: string (required)

**Response 200**:
```json
{
  "message": "Chapter deleted successfully",
  "chapter_id": "string",
  "guide_id": "string"
}
```

**Errors**:
- `404 Not Found`: Guide or chapter not found
- `403 Forbidden`: User is not the guide owner
- `401 Unauthorized`: Missing or invalid token

---

### 10. Reorder Chapters (Bulk)
**Endpoint**: `POST /guides/{guide_id}/chapters/reorder`
**Authentication**: Required

**Path Parameters**:
- `guide_id`: string (required)

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
      "guide_id": "string",
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
- `404 Not Found`: Guide not found
- `403 Forbidden`: User is not the guide owner
- `400 Bad Request`: Invalid reorder operation
- `422 Unprocessable Entity`: Validation error
- `401 Unauthorized`: Missing or invalid token

---

## 🔐 Phase 4: User Permissions APIs

### 11. Grant Permission
**Endpoint**: `POST /guides/{guide_id}/permissions/users`
**Authentication**: Required (Owner only)

**Path Parameters**:
- `guide_id`: string (required)

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
  "guide_id": "string",
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
- `404 Not Found`: Guide not found
- `403 Forbidden`: User is not the guide owner
- `409 Conflict`: Permission already exists for this user
- `422 Unprocessable Entity`: Validation error
- `401 Unauthorized`: Missing or invalid token

---

### 12. List Permissions
**Endpoint**: `GET /guides/{guide_id}/permissions/users`
**Authentication**: Required (Owner only)

**Path Parameters**:
- `guide_id`: string (required)

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
- `404 Not Found`: Guide not found
- `403 Forbidden`: User is not the guide owner
- `401 Unauthorized`: Missing or invalid token

---

### 13. Revoke Permission
**Endpoint**: `DELETE /guides/{guide_id}/permissions/users/{permission_user_id}`
**Authentication**: Required (Owner only)

**Path Parameters**:
- `guide_id`: string (required)
- `permission_user_id`: string (user ID to revoke, required)

**Response 200**:
```json
{
  "message": "Permission revoked successfully",
  "revoked": {
    "guide_id": "string",
    "user_id": "string",
    "revoked_by": "string"
  }
}
```

**Errors**:
- `404 Not Found`: Guide or permission not found
- `403 Forbidden`: User is not the guide owner
- `401 Unauthorized`: Missing or invalid token

---

### 14. Invite User by Email
**Endpoint**: `POST /guides/{guide_id}/permissions/invite`
**Authentication**: Required (Owner only)

**Path Parameters**:
- `guide_id`: string (required)

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
    "guide_id": "string",
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
- `404 Not Found`: Guide not found
- `403 Forbidden`: User is not the guide owner
- `400 Bad Request`: Invalid email address
- `422 Unprocessable Entity`: Validation error
- `401 Unauthorized`: Missing or invalid token

---

## 🌐 Phase 5: Public View APIs (NO AUTH)

### 15. Get Public Guide
**Endpoint**: `GET /public/guides/{slug}`
**Authentication**: None (Public access)

**Path Parameters**:
- `slug`: string (guide slug, required)

**Response 200**:
```json
{
  "guide_id": "string",
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
- `404 Not Found`: Guide not found
- `403 Forbidden`: Guide is private (not accessible publicly)

---

### 16. Get Public Chapter
**Endpoint**: `GET /public/guides/{guide_slug}/chapters/{chapter_slug}`
**Authentication**: None (Public access)

**Path Parameters**:
- `guide_slug`: string (guide slug, required)
- `chapter_slug`: string (chapter slug, required)

**Response 200**:
```json
{
  "chapter_id": "string",
  "guide_id": "string",
  "title": "string",
  "slug": "string",
  "order": "integer",
  "description": "string",
  "icon": "string",
  "content": {
    "type": "doc",
    "content": []
  },
  "guide_info": {
    "guide_id": "string",
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
- `404 Not Found`: Guide or chapter not found
- `403 Forbidden`: Guide is private

---

### 17. Track View Analytics
**Endpoint**: `POST /public/guides/{slug}/views`
**Authentication**: None (Public access)

**Path Parameters**:
- `slug`: string (guide slug, required)

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
  "guide_views": "integer",
  "chapter_views": "integer"
}
```

**Errors**:
- `404 Not Found`: Guide not found
- `429 Too Many Requests`: Rate limit exceeded (10 req/min per IP)

---

### 18. Get Guide by Custom Domain
**Endpoint**: `GET /guides/by-domain/{domain}`
**Authentication**: None (Public access)

**Path Parameters**:
- `domain`: string (custom domain, required)

**Response 200**:
```json
{
  "guide_id": "string",
  "slug": "string",
  "title": "string",
  "custom_domain": "string",
  "visibility": "string",
  "is_active": "boolean"
}
```

**Errors**:
- `404 Not Found`: No guide found for domain

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

---

## 🚀 Total Endpoints: 18

- **Phase 2**: 5 endpoints (Guide Management)
- **Phase 3**: 5 endpoints (Chapter Management)
- **Phase 4**: 4 endpoints (User Permissions)
- **Phase 5**: 4 endpoints (Public View - NO AUTH)

**Last Updated**: November 15, 2025
