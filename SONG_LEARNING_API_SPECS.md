# Song Learning API - Technical Specifications

**Last Updated:** February 12, 2026
**API Version:** v1
**Base URL:** `https://wordai.pro/api/v1/songs`

---

## Table of Contents

1. [Authentication](#authentication)
2. [Playlist Management APIs](#playlist-management-apis)
3. [Admin Song Management APIs](#admin-song-management-apis)
4. [Error Codes](#error-codes)
5. [Rate Limiting](#rate-limiting)

---

## Authentication

### Firebase Authentication Required

All endpoints require Firebase ID token in request headers:

```
Authorization: Bearer <firebase_id_token>
```

**Getting Firebase Token:**
- Frontend must obtain token from Firebase Auth
- Token expires after 1 hour
- Refresh token before expiry

**User Identification:**
- `user_id` extracted from Firebase token claims (`uid`)
- `email` extracted from token claims for admin verification

---

## Playlist Management APIs

### 1. Get User Playlists

**Endpoint:** `GET /api/v1/songs/playlists`

**Description:** Retrieve all playlists created by the authenticated user.

**Authentication:** Required (Firebase token)

**Query Parameters:** None

**Response:** `200 OK`

**Response Schema:**
```
Array of PlaylistListResponse:
  - playlist_id: string (UUID)
  - name: string
  - description: string | null
  - song_count: number
  - is_public: boolean
  - created_at: datetime (ISO 8601)
  - updated_at: datetime (ISO 8601)
```

**Error Responses:**
- `401 Unauthorized` - Missing or invalid Firebase token

**Business Rules:**
- Returns empty array if user has no playlists
- Sorted by creation date (newest first)
- Only returns playlists owned by authenticated user

---

### 2. Create New Playlist

**Endpoint:** `POST /api/v1/songs/playlists`

**Description:** Create a new empty playlist for the authenticated user.

**Authentication:** Required (Firebase token)

**Request Body:**
```
CreatePlaylistRequest:
  - name: string (required, 1-100 chars)
  - description: string | null (optional, max 500 chars)
  - is_public: boolean (optional, default: false)
```

**Response:** `201 Created`

**Response Schema:**
```
PlaylistResponse:
  - playlist_id: string (UUID)
  - user_id: string
  - name: string
  - description: string | null
  - songs: array (empty on creation)
  - song_count: number (0 on creation)
  - is_public: boolean
  - created_at: datetime
  - updated_at: datetime
```

**Error Responses:**
- `401 Unauthorized` - Missing or invalid Firebase token
- `422 Unprocessable Entity` - Validation errors (name too short/long)

**Business Rules:**
- Playlist created with empty song list
- `playlist_id` auto-generated (UUID v4)
- `created_at` and `updated_at` set to current time

---

### 3. Get Playlist Details

**Endpoint:** `GET /api/v1/songs/playlists/{playlist_id}`

**Description:** Get full playlist details including all songs with complete metadata.

**Authentication:** Required (Firebase token)

**Path Parameters:**
- `playlist_id`: string (UUID)

**Response:** `200 OK`

**Response Schema:**
```
PlaylistResponse:
  - playlist_id: string
  - user_id: string
  - name: string
  - description: string | null
  - songs: array of SongListItem
    - song_id: string
    - title: string
    - artist: string
    - category: string
    - youtube_id: string
    - view_count: number
    - word_count: number
    - difficulties_available: array of string ["easy", "medium", "hard"]
  - song_count: number
  - is_public: boolean
  - created_at: datetime
  - updated_at: datetime
```

**Error Responses:**
- `401 Unauthorized` - Missing or invalid Firebase token
- `403 Forbidden` - Playlist is private and user is not owner
- `404 Not Found` - Playlist does not exist

**Business Rules:**
- User can view own playlists (private or public)
- User can view other users' public playlists
- Songs returned in order they were added to playlist
- Includes full song metadata and available difficulty levels

---

### 4. Update Playlist

**Endpoint:** `PUT /api/v1/songs/playlists/{playlist_id}`

**Description:** Update playlist name, description, or visibility.

**Authentication:** Required (Firebase token)

**Path Parameters:**
- `playlist_id`: string (UUID)

**Request Body:**
```
UpdatePlaylistRequest (all fields optional):
  - name: string (1-100 chars)
  - description: string | null (max 500 chars)
  - is_public: boolean
```

**Response:** `200 OK`

**Response Schema:**
```
PlaylistResponse (same as Get Playlist Details)
```

**Error Responses:**
- `401 Unauthorized` - Missing or invalid Firebase token
- `403 Forbidden` - User is not playlist owner
- `404 Not Found` - Playlist does not exist
- `422 Unprocessable Entity` - Validation errors

**Business Rules:**
- Only playlist owner can update
- At least one field must be provided
- `updated_at` timestamp updated automatically
- Returns full playlist details with songs after update

---

### 5. Delete Playlist

**Endpoint:** `DELETE /api/v1/songs/playlists/{playlist_id}`

**Description:** Permanently delete a playlist.

**Authentication:** Required (Firebase token)

**Path Parameters:**
- `playlist_id`: string (UUID)

**Response:** `204 No Content`

**Error Responses:**
- `401 Unauthorized` - Missing or invalid Firebase token
- `403 Forbidden` - User is not playlist owner
- `404 Not Found` - Playlist does not exist

**Business Rules:**
- Only playlist owner can delete
- Deletion is permanent (no undo)
- Does NOT delete songs from database (only playlist record)
- No response body on success

---

### 6. Add Song to Playlist

**Endpoint:** `POST /api/v1/songs/playlists/{playlist_id}/songs`

**Description:** Add a song to an existing playlist.

**Authentication:** Required (Firebase token)

**Path Parameters:**
- `playlist_id`: string (UUID)

**Request Body:**
```
AddSongToPlaylistRequest:
  - song_id: string (required)
```

**Response:** `200 OK`

**Response Schema:**
```
PlaylistResponse (same as Get Playlist Details)
```

**Error Responses:**
- `401 Unauthorized` - Missing or invalid Firebase token
- `403 Forbidden` - User is not playlist owner
- `404 Not Found` - Playlist or song does not exist
- `400 Bad Request` - Song already in playlist

**Business Rules:**
- Only playlist owner can add songs
- Song must exist in database
- Duplicate songs not allowed (returns 400)
- `updated_at` timestamp updated automatically
- Returns full playlist details with songs after addition

---

### 7. Remove Song from Playlist

**Endpoint:** `DELETE /api/v1/songs/playlists/{playlist_id}/songs/{song_id}`

**Description:** Remove a song from playlist.

**Authentication:** Required (Firebase token)

**Path Parameters:**
- `playlist_id`: string (UUID)
- `song_id`: string

**Response:** `200 OK`

**Response Schema:**
```
PlaylistResponse (same as Get Playlist Details)
```

**Error Responses:**
- `401 Unauthorized` - Missing or invalid Firebase token
- `403 Forbidden` - User is not playlist owner
- `404 Not Found` - Playlist does not exist

**Business Rules:**
- Only playlist owner can remove songs
- Silent success if song not in playlist
- `updated_at` timestamp updated automatically
- Returns full playlist details with songs after removal

---

## Admin Song Management APIs

**Admin Access:** Only `tienhoi.lh@gmail.com` can access these endpoints.

### 8. Create New Song

**Endpoint:** `POST /api/v1/songs/admin/songs`

**Description:** Add a new song to the database.

**Authentication:** Required (Admin only - tienhoi.lh@gmail.com)

**Request Body:**
```
AdminCreateSongRequest:
  - song_id: string (required, unique ID)
  - title: string (required, 1-200 chars)
  - artist: string (required, 1-200 chars)
  - category: string (default: "Uncategorized", max 100 chars)
  - english_lyrics: string (required)
  - vietnamese_lyrics: string (required)
  - youtube_url: string (required)
  - youtube_id: string (required)
  - view_count: number (default: 0, >= 0)
  - source_url: string (required)
  - word_count: number (default: 0, >= 0)
  - has_profanity: boolean (default: false)
```

**Response:** `201 Created`

**Response Schema:**
```
SongDetailResponse:
  - song_id: string
  - title: string
  - artist: string
  - category: string
  - english_lyrics: string
  - vietnamese_lyrics: string
  - youtube_url: string
  - youtube_id: string
  - view_count: number
  - source_url: string
  - is_processed: boolean
  - has_profanity: boolean
  - word_count: number
  - crawled_at: datetime
  - created_at: datetime
  - updated_at: datetime
  - difficulties_available: array (empty on creation)
  - has_gaps: boolean (false on creation)
```

**Error Responses:**
- `401 Unauthorized` - Missing or invalid Firebase token
- `403 Forbidden` - User is not admin
- `400 Bad Request` - Song ID already exists
- `422 Unprocessable Entity` - Validation errors

**Business Rules:**
- Admin access only (email check)
- `song_id` must be unique
- `is_processed` automatically set to false (gaps not generated)
- Timestamps auto-generated
- Song created without gap exercises (admin must run gap generation separately)

---

### 9. Get Song Details (Admin)

**Endpoint:** `GET /api/v1/songs/admin/songs/{song_id}`

**Description:** Get complete song information including all fields for editing.

**Authentication:** Required (Admin only - tienhoi.lh@gmail.com)

**Path Parameters:**
- `song_id`: string

**Response:** `200 OK`

**Response Schema:**
```
SongDetailResponse (same as Create New Song response)
```

**Error Responses:**
- `401 Unauthorized` - Missing or invalid Firebase token
- `403 Forbidden` - User is not admin
- `404 Not Found` - Song does not exist

**Business Rules:**
- Admin access only
- Returns full song details including lyrics
- Shows available difficulty levels from gap exercises
- Use this to populate edit form

---

### 10. Update Song

**Endpoint:** `PUT /api/v1/songs/admin/songs/{song_id}`

**Description:** Update song information in the database.

**Authentication:** Required (Admin only - tienhoi.lh@gmail.com)

**Path Parameters:**
- `song_id`: string

**Request Body:**
```
AdminUpdateSongRequest (all fields optional):
  - title: string (1-200 chars)
  - artist: string (1-200 chars)
  - category: string (max 100 chars)
  - english_lyrics: string
  - vietnamese_lyrics: string
  - youtube_url: string
  - youtube_id: string
  - view_count: number (>= 0)
  - source_url: string
  - word_count: number (>= 0)
  - has_profanity: boolean
```

**Response:** `200 OK`

**Response Schema:**
```
SongDetailResponse (same as Get Song Details)
```

**Error Responses:**
- `401 Unauthorized` - Missing or invalid Firebase token
- `403 Forbidden` - User is not admin
- `404 Not Found` - Song does not exist
- `422 Unprocessable Entity` - Validation errors

**Business Rules:**
- Admin access only
- At least one field must be provided
- `updated_at` timestamp updated automatically
- Updating lyrics does NOT regenerate gaps (admin must do manually)
- Returns full updated song details

---

### 11. Delete Song

**Endpoint:** `DELETE /api/v1/songs/admin/songs/{song_id}`

**Description:** Permanently delete song and all related data.

**Authentication:** Required (Admin only - tienhoi.lh@gmail.com)

**Path Parameters:**
- `song_id`: string

**Response:** `204 No Content`

**Error Responses:**
- `401 Unauthorized` - Missing or invalid Firebase token
- `403 Forbidden` - User is not admin
- `404 Not Found` - Song does not exist

**Business Rules:**
- Admin access only
- Deletion is permanent (no undo)
- **Cascading deletes:**
  - All gap exercises for this song (3 difficulty levels)
  - All user progress records for this song
  - Removes song from all user playlists
- No response body on success

**⚠️ WARNING:** This is a destructive operation. All user data related to this song will be lost.

---

## Error Codes

### Standard HTTP Status Codes

| Code | Meaning | When It Occurs |
|------|---------|----------------|
| `200` | OK | Request successful |
| `201` | Created | Resource created successfully |
| `204` | No Content | Delete successful (no response body) |
| `400` | Bad Request | Invalid request data or business rule violation |
| `401` | Unauthorized | Missing or invalid Firebase token |
| `403` | Forbidden | Valid token but insufficient permissions |
| `404` | Not Found | Resource does not exist |
| `422` | Unprocessable Entity | Validation errors in request body |
| `500` | Internal Server Error | Server error (contact support) |

### Error Response Format

All error responses (except 204) return JSON:

```json
{
  "detail": "Error message describing what went wrong"
}
```

### Common Error Scenarios

**401 Unauthorized:**
- Missing `Authorization` header
- Invalid Firebase token format
- Expired Firebase token
- Token from wrong Firebase project

**403 Forbidden:**
- Trying to access admin endpoint without admin email
- Trying to modify another user's playlist
- Trying to view private playlist of another user

**404 Not Found:**
- Playlist ID does not exist
- Song ID does not exist
- Song not in database when adding to playlist

**400 Bad Request:**
- Song already exists in playlist (duplicate)
- Song ID already exists when creating new song

**422 Unprocessable Entity:**
- Playlist name too short (<1 char) or too long (>100 chars)
- Song title/artist too long
- Negative view_count or word_count
- Required fields missing

---

## Rate Limiting

### Current Limits

**No rate limiting implemented yet.**

### Future Considerations

Recommended rate limits for production:

- **Playlist operations:** 100 requests/minute per user
- **Admin operations:** 500 requests/minute (admin only)
- **Song browsing:** Handled by existing caching (30min for hot, 5min for recent)

### Rate Limit Response

When implemented, will return:

```
429 Too Many Requests
{
  "detail": "Rate limit exceeded. Try again in X seconds."
}
```

---

## Database Collections

### `user_song_playlists`

**Schema:**
```javascript
{
  playlist_id: "UUID",
  user_id: "firebase_uid",
  name: "Playlist Name",
  description: "Optional description",
  song_ids: ["song_id_1", "song_id_2", ...],
  is_public: false,
  created_at: ISODate("2026-02-12T10:00:00Z"),
  updated_at: ISODate("2026-02-12T10:00:00Z")
}
```

**Indexes:**
- `user_id` (for user playlist queries)
- `playlist_id` (unique, for lookup)

---

## Frontend Integration Notes

### Authentication Flow

1. User signs in with Firebase Auth
2. Frontend obtains ID token: `firebase.auth().currentUser.getIdToken()`
3. Include token in all API requests: `Authorization: Bearer ${token}`
4. Refresh token before expiry (1 hour)

### Playlist Management UX

**Recommended flow:**
1. Display "My Playlists" page: Call `GET /playlists`
2. Show "Create Playlist" button: Opens modal/form
3. User creates playlist: Call `POST /playlists`
4. View playlist details: Call `GET /playlists/{id}`
5. Add song: Show "Add to Playlist" button on song cards
6. Remove song: Show "Remove" button in playlist view
7. Edit playlist: Show "Edit" button (name/description only)
8. Delete playlist: Show "Delete" button with confirmation

### Admin Panel UX

**Only visible for admin user (tienhoi.lh@gmail.com):**

**Add New Song Form:**
- All fields visible and editable
- Required fields marked with asterisk
- YouTube URL and ID fields (extract ID from URL automatically)
- Lyrics textareas (large, multi-line)
- Category dropdown (predefined categories)
- Profanity checkbox
- "Create Song" button → Call `POST /admin/songs`

**Edit Song Form:**
- Load existing data: Call `GET /admin/songs/{id}`
- Pre-fill all fields with current values
- Allow editing any field
- "Save Changes" button → Call `PUT /admin/songs/{id}`
- "Delete Song" button → Confirmation modal → Call `DELETE /admin/songs/{id}`

**Important Notes:**
- Gap generation NOT automatic (separate process)
- After creating/editing song, show note: "Remember to run gap generation for this song"
- Display `is_processed` flag to show if gaps exist
- Show `difficulties_available` to indicate which levels are ready

---

## Changelog

### February 12, 2026

**Added:**
- Playlist management endpoints (7 endpoints)
- Admin song management endpoints (4 endpoints)
- Authentication documentation
- Error codes reference
- Frontend integration notes

---

## Support

For API questions or issues:
- **Admin:** tienhoi.lh@gmail.com
- **API Docs:** https://wordai.pro/api/v1/docs (Swagger UI)
