# Slide Sharing System - Technical Specifications

## Overview

WordAI hỗ trợ **2 loại sharing** cho slide presentations:

1. **Edit Share** - Chia sẻ quyền chỉnh sửa với người dùng cụ thể
2. **Presentation Share** - Chia sẻ public/private để xem presentation

---

## System 1: Edit Share (Collaborative Editing)

### Use Case
- Chia sẻ document để cùng chỉnh sửa
- Phân quyền `view` (chỉ xem) hoặc `edit` (chỉnh sửa)
- Share với user cụ thể (qua email/user_id)
- Không public, chỉ user được mời mới truy cập

### User Flow

#### Owner (Người chia sẻ)
1. Mở document trong editor
2. Click "Share" button → Open share dialog
3. Chọn permission level:
   - **View**: Chỉ xem, không sửa
   - **Edit**: Có thể chỉnh sửa content
4. Nhập email người nhận
5. System gửi link share qua email/notification

#### Invited User (Người được mời)
1. Nhận link share: `https://wordai.pro/edit/{share_id}`
2. Click link → Redirect to editor
3. Nếu có password: Nhập password
4. Document mở trong editor mode:
   - **View permission**: Read-only mode, không có edit tools
   - **Edit permission**: Full editor với save/undo/redo

### Key Features
- ✅ Content HTML đầy đủ (với overlay elements)
- ✅ Slide backgrounds
- ✅ Subtitles (nếu có)
- ✅ Audio files (nếu có)
- ✅ Password protection
- ✅ Expiration date (1-90 days)
- ✅ Analytics tracking

### Share URL Format
```
View mode:  https://wordai.pro/edit/{share_id}?mode=view
Edit mode:  https://wordai.pro/edit/{share_id}?mode=edit
```

**Lưu ý:** URL ngắn gọn, dễ nhớ. `share_id` là UUID random.

---

## System 2: Presentation Share (Public Viewing)

### Use Case
- Chia sẻ presentation để present/view
- Public link (ai cũng xem được) hoặc password-protected
- Fullscreen presentation mode
- Có audio narration & subtitles (nếu đã generate)

### User Flow

#### Owner (Người chia sẻ)
1. Mở presentation
2. Click "Share Presentation" → Open share dialog
3. Chọn share type:
   - **Presentation**: Fullscreen slide show mode
   - **View**: Preview mode (như viewer)
4. Tùy chọn:
   - ✅ Include audio (nếu có)
   - ✅ Include subtitles (chọn ngôn ngữ)
   - ✅ Allow download PDF
   - ✅ Password protection
   - ✅ Expiration date
5. Copy link share

#### Viewer (Người xem)
1. Nhận link: `https://wordai.pro/p/{share_id}` (presentation mode)
2. Click link → Mở presentation viewer
3. Nếu có password: Nhập password
4. Presentation hiển thị:
   - Slides với animations
   - Audio narration (auto-play hoặc manual)
   - Subtitles overlay (nếu có)
   - Navigation controls (next/prev slide)
   - Progress bar
   - Download PDF button (nếu được phép)

### Key Features
- ✅ Content HTML + slide backgrounds
- ✅ Multi-language subtitles (chọn ngôn ngữ)
- ✅ Audio narration với slide timestamps
- ✅ Password protection
- ✅ Analytics (views, unique visitors, slide engagement)
- ✅ Download PDF

### Share URL Format
```
Presentation mode: https://wordai.pro/p/{share_id}
View mode:         https://wordai.pro/s/{share_id}
```

**Lưu ý:** URL cực ngắn (`/p/` và `/s/`), dễ share qua SMS/social media.

---

## API Endpoints Reference

### 1. Create Share Link

**Endpoint:** `POST /api/slides/shares/create`

**Auth:** Required (Firebase token)

**Request:**
```json
{
  "document_id": "slide_doc_abc123",
  "share_type": "presentation",  // "presentation" | "view"
  "permission": "view",           // "view" | "edit"
  "password": "secret123",        // Optional
  "expires_in_days": 7,           // 1-90
  "allow_download": false,
  "include_audio": true,
  "include_subtitles": true,
  "subtitle_language": "vi"       // Optional, default: latest version
}
```

**Response:**
```json
{
  "success": true,
  "share_id": "share_xyz123abc",
  "share_url": "https://wordai.pro/p/share_xyz123abc",
  "share_type": "presentation",
  "permission": "view",
  "password_protected": true,
  "expires_at": "2025-12-31T23:59:59Z",
  "created_at": "2025-12-24T10:00:00Z",
  "includes": {
    "audio": true,
    "subtitles": true,
    "backgrounds": true
  }
}
```

---

### 2. Get Share Info (Public)

**Endpoint:** `GET /api/slides/shares/{share_id}`

**Auth:** Not required

**Response:**
```json
{
  "share_id": "share_xyz123",
  "share_type": "presentation",
  "permission": "view",
  "password_protected": true,
  "expired": false,
  "expires_at": "2025-12-31T23:59:59Z",
  "title": "Q4 Sales Report",
  "total_slides": 15,
  "allow_download": false,
  "includes": {
    "audio": true,
    "subtitles": true,
    "backgrounds": true
  }
}
```

---

### 3. Verify Password

**Endpoint:** `POST /api/slides/shares/{share_id}/verify-password`

**Auth:** Not required

**Request:**
```json
{
  "password": "secret123"
}
```

**Response:**
```json
{
  "success": true,
  "valid": true,
  "access_token": "temp_token_abc123"
}
```

**Lưu ý:** `access_token` dùng để gọi `/content` endpoint.

---

### 4. Get Share Content (Full Data)

**Endpoint:** `GET /api/slides/shares/{share_id}/content?access_token={token}`

**Auth:** Not required (nhưng cần access_token nếu password-protected)

**Response:**
```json
{
  "success": true,
  "slides": [
    {
      "slide_number": 1,
      "html_content": "<div class=\"slide-page\">...</div>",
      "notes": null
    }
  ],
  "slide_backgrounds": [
    {
      "type": "gradient",
      "colors": ["#1e3a8a", "#3b82f6"]
    }
  ],
  "subtitles": {
    "language": "vi",
    "version": 1,
    "slides": [
      {
        "slide_index": 0,
        "slide_duration": 15.5,
        "subtitles": [
          {
            "subtitle_index": 0,
            "start_time": 0.0,
            "end_time": 3.5,
            "text": "Chào mừng đến với bài thuyết trình"
          }
        ]
      }
    ]
  },
  "audio_files": [
    {
      "_id": "audio_123",
      "audio_url": "https://static.wordai.pro/narration/.../merged.wav",
      "audio_type": "merged_presentation",
      "slide_timestamps": [
        {
          "slide_index": 0,
          "start_time": 0.0,
          "end_time": 15.5
        }
      ]
    }
  ],
  "title": "Q4 Sales Report",
  "total_slides": 15,
  "permission": "view"
}
```

**Lưu ý:**
- `audio_url` là public CDN URL (R2), không cần auth
- Images trong slides cũng là public URLs
- Frontend render trực tiếp, không cần convert

---

### 5. List User Shares

**Endpoint:** `GET /api/slides/shares/`

**Auth:** Required

**Response:**
```json
{
  "success": true,
  "shares": [
    {
      "share_id": "share_xyz123",
      "document_id": "slide_doc_abc",
      "document_title": "Q4 Sales Report",
      "share_type": "presentation",
      "permission": "view",
      "password_protected": true,
      "allow_download": false,
      "includes": {
        "audio": true,
        "subtitles": true,
        "backgrounds": true
      },
      "total_views": 150,
      "unique_viewers": 45,
      "created_at": "2025-12-24T10:00:00Z",
      "expires_at": "2025-12-31T23:59:59Z",
      "is_active": true,
      "revoked": false
    }
  ],
  "total": 5
}
```

---

### 6. Get Share Analytics

**Endpoint:** `GET /api/slides/shares/{share_id}/analytics`

**Auth:** Required (owner only)

**Response:**
```json
{
  "share_id": "share_xyz123",
  "total_views": 150,
  "unique_viewers": 45,
  "average_duration_seconds": 180.5,
  "most_viewed_slides": [
    {"slide_number": 1, "views": 150},
    {"slide_number": 3, "views": 120}
  ],
  "device_breakdown": {
    "desktop": 100,
    "mobile": 40,
    "tablet": 10
  },
  "views_over_time": [
    {"date": "2025-12-24", "views": 50},
    {"date": "2025-12-25", "views": 100}
  ],
  "created_at": "2025-12-24T10:00:00Z",
  "expires_at": "2025-12-31T23:59:59Z",
  "is_active": true
}
```

---

### 7. Revoke/Delete Share

**Endpoint:** `DELETE /api/slides/shares/{share_id}`

**Auth:** Required (owner only)

**Response:**
```json
{
  "success": true,
  "message": "Share link has been revoked successfully"
}
```

**Lưu ý:** Link sẽ trả về 410 Gone khi bị revoke.

---

### 8. Track View Analytics

**Endpoint:** `POST /api/slides/shares/{share_id}/track-view`

**Auth:** Not required

**Request:**
```json
{
  "slide_number": 3,
  "duration_seconds": 15,
  "device_type": "desktop",
  "user_agent": "Mozilla/5.0..."
}
```

**Response:**
```json
{
  "success": true,
  "message": "View tracked successfully"
}
```

---

## Presentation Sharing System (Alternative)

**Endpoint:** `GET /api/presentations/public/presentations/{public_token}`

**Dùng cho:** Multi-language narration system (system 2)

**Khác biệt:**
- Collection: `presentation_sharing` (thay vì `slide_shares`)
- Token format: `pub_token_xyz` (thay vì `share_xyz`)
- Có subtitle versioning & multi-language
- Audio timestamps sync với slides

**URL Format:**
```
https://wordai.pro/present/{public_token}
```

---

## Share URL Design Best Practices

### ✅ Recommendations

**Edit Share:**
```
https://wordai.pro/edit/{share_id}           // Ngắn gọn, rõ ràng
https://wordai.pro/e/{share_id}              // Siêu ngắn (optional)
```

**Presentation Share:**
```
https://wordai.pro/p/{share_id}              // Presentation mode (recommended)
https://wordai.pro/s/{share_id}              // Slide view mode
https://wordai.pro/present/{share_id}        // Explicit (dài hơn)
```

**Public Token (Multi-language):**
```
https://wordai.pro/present/{public_token}    // Có language selector
```

### URL Parameters

**View mode với options:**
```
https://wordai.pro/p/{share_id}?lang=en&autoplay=true
https://wordai.pro/p/{share_id}?slide=5
```

**Edit mode với restrictions:**
```
https://wordai.pro/edit/{share_id}?readonly=true
```

---

## Security Considerations

### Password Protection
- Password được hash với SHA256
- Access token (temporary) có TTL 24h
- Token stored in session/localStorage

### Expiration
- Automatic cleanup sau khi expired
- Status check before serving content
- 410 Gone response cho expired links

### Analytics Privacy
- Visitor fingerprint: `SHA256(IP + User-Agent)` (16 chars)
- Không lưu IP thực
- Aggregate data only (không track individual)

---

## Frontend Implementation Notes

### Presentation Viewer
```
Load:    GET /shares/{id}/content
Play:    Audio từ audio_url (public CDN)
Display: Subtitles overlay theo timestamps
Track:   POST /shares/{id}/track-view mỗi slide
```

### Edit Viewer (Permission = edit)
```
Load:    GET /shares/{id}/content
Save:    PUT /documents/{id} (nếu có quyền edit)
Lock:    WebSocket real-time collaboration (future)
```

---

## Database Schema

### Collection: `slide_shares`
```json
{
  "_id": ObjectId,
  "share_id": "share_xyz123",
  "document_id": "slide_doc_abc",
  "owner_id": "user_firebase_uid",
  "share_type": "presentation",
  "permission": "view",
  "password_hash": "sha256...",
  "include_audio": true,
  "include_subtitles": true,
  "subtitle_language": "vi",
  "created_at": ISODate,
  "expires_at": ISODate,
  "revoked": false,
  "view_count": 150,
  "unique_viewers": ["fingerprint1", "fingerprint2"],
  "analytics": {
    "views_by_slide": {"1": 150, "3": 120},
    "views_by_date": {"2025-12-24": 50}
  }
}
```

### Collection: `presentation_sharing`
```json
{
  "_id": ObjectId,
  "public_token": "pub_token_xyz",
  "presentation_id": "slide_doc_abc",
  "user_id": "firebase_uid",
  "is_public": true,
  "sharing_settings": {
    "include_audio": true,
    "include_subtitles": true,
    "allowed_languages": ["vi", "en"],
    "default_language": "vi"
  }
}
```

---

## Error Codes

| Code | Error | Description |
|------|-------|-------------|
| 404 | Share not found | Invalid share_id |
| 401 | Unauthorized | Password required |
| 410 | Gone | Link expired or revoked |
| 403 | Forbidden | No permission to access |
| 400 | Bad request | Invalid parameters |

---

## Future Enhancements

### Planned Features
- [ ] Real-time collaboration (WebSocket)
- [ ] Comment threads on slides
- [ ] Version history for shared edits
- [ ] Share via QR code
- [ ] Embed code for iframe
- [ ] Custom branding (logo, colors)
- [ ] Download tracking (who downloaded PDF)
- [ ] Viewer insights (which slides got most attention)

---

**Document Version:** 1.0
**Last Updated:** December 30, 2025
**Author:** WordAI Backend Team
