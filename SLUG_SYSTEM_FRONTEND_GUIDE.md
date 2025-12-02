# 🔗 Test Slug System - Frontend Integration Guide

## 📋 Tổng Quan

Hệ thống slug đã được implement để tạo URL thân thiện với SEO cho các bài test trong marketplace. **Backend tự động generate slug** từ title, frontend chỉ cần sử dụng slug đã có.

---

## ✅ Những Gì Đã Thay Đổi (Backend)

### 1. **Auto-Generate Slug Khi Publish Test**
- Khi publish test lên marketplace, backend tự động tạo slug từ title
- Slug được tạo an toàn với tiếng Việt (có dấu → không dấu)
- Tự động đảm bảo unique bằng cách thêm số suffix nếu trùng
- VD: "Đánh Giá Kỹ Năng Mềm" → `danh-gia-ky-nang-mem`

### 2. **Auto-Regenerate Slug Khi Update Title**
- Khi update marketplace config và thay đổi title, slug tự động được tạo lại
- Nếu title không đổi, slug giữ nguyên
- Đảm bảo slug luôn phản ánh đúng title hiện tại

### 3. **Meta Description Tự Động**
- Backend tự động tạo meta description (max 160 ký tự) từ description
- Được cắt ngắn một cách thông minh tại dấu câu cuối cùng
- Thêm "..." nếu bị cắt

---

## 🆕 Endpoints Mới

### 1. **GET /marketplace/tests/by-slug/{slug}**
Lấy thông tin chi tiết test bằng slug thay vì test_id

**Request:**
```
GET /api/v1/marketplace/tests/by-slug/danh-gia-ky-nang-mem
Authorization: Bearer <token>
```

**Response:**
```json
{
  "test_id": "692e983006a09e9ff6537c1c",
  "slug": "danh-gia-ky-nang-mem",
  "meta_description": "Bạn có biết: 85% thành công trong sự nghiệp được quyết định bởi kỹ năng mềm...",
  "title": "Đánh Giá Kỹ Năng Mềm Của Bạn",
  "description": "...",
  "has_purchased": true,
  "is_creator": false,
  "questions": [...],
  "creator": {
    "uid": "...",
    "display_name": "WordAI Team"
  },
  ...
}
```

**Use Cases:**
- Khi user truy cập URL có slug: `/online-test?testSlug=danh-gia-ky-nang-mem`
- Fetch test detail để hiển thị
- SEO-friendly URL, tốt cho Google indexing

---

### 2. **GET /tests/check-slug/{slug}**
Kiểm tra slug có khả dụng không (optional - nếu cần custom slug feature sau này)

**Request:**
```
GET /api/v1/tests/check-slug/danh-gia-ky-nang-mem?exclude_test_id=692e983006a09e9ff6537c1c
```

**Response - Nếu slug đã tồn tại:**
```json
{
  "available": false,
  "slug": "danh-gia-ky-nang-mem",
  "test_id": "692e983006a09e9ff6537c1c",
  "title": "Đánh Giá Kỹ Năng Mềm Của Bạn",
  "suggestions": [
    "danh-gia-ky-nang-mem-2",
    "danh-gia-ky-nang-mem-3",
    "danh-gia-ky-nang-mem-4"
  ],
  "message": "Slug 'danh-gia-ky-nang-mem' đã được sử dụng"
}
```

**Response - Nếu slug available:**
```json
{
  "available": true,
  "slug": "danh-gia-ky-nang-mem",
  "message": "Slug 'danh-gia-ky-nang-mem' có thể sử dụng"
}
```

---

## 📊 Endpoints Đã Được Cập Nhật

### 1. **GET /marketplace/tests/browse**
Giờ trả về thêm `slug` và `meta_description` trong mỗi test card:

```json
{
  "tests": [
    {
      "test_id": "692e983006a09e9ff6537c1c",
      "slug": "danh-gia-ky-nang-mem",
      "meta_description": "Bạn có biết: 85% thành công trong sự nghiệp...",
      "title": "Đánh Giá Kỹ Năng Mềm Của Bạn",
      "description": "...",
      "cover_image_url": "...",
      "price_points": 0,
      ...
    }
  ]
}
```

**Sử dụng:**
- Hiển thị test cards với slug
- Tạo link đến test detail: `/online-test?testSlug=${test.slug}`
- Thêm meta description vào SEO tags

---

### 2. **GET /marketplace/leaderboard**
Giờ trả về thêm `slug` và `meta_description` trong top tests:

```json
{
  "top_tests": [
    {
      "rank": 1,
      "test_id": "692e983006a09e9ff6537c1c",
      "slug": "danh-gia-ky-nang-mem",
      "meta_description": "Bạn có biết: 85% thành công...",
      "title": "Đánh Giá Kỹ Năng Mềm Của Bạn",
      "stats": {
        "total_completions": 1250,
        "average_rating": 4.8
      },
      ...
    }
  ]
}
```

---

## 🎯 Frontend Implementation Tasks

### ✅ Phase 1: URL Structure Update

**Hiện tại:**
```
/online-test?view=public&testId=692e983006a09e9ff6537c1c
```

**Mới (SEO-friendly):**
```
/online-test?view=community&testSlug=danh-gia-ky-nang-mem
```

**Changes needed:**
1. Update tất cả links tạo URL cho test detail
2. Đổi từ `testId` → `testSlug` parameter
3. Đổi từ `view=public` → `view=community` (optional, nhưng semantic hơn)

---

### ✅ Phase 2: API Calls Update

**Browse/Leaderboard Pages:**
- Response giờ có `slug` field
- Sử dụng `slug` thay vì `test_id` khi tạo links
- Store `meta_description` để dùng cho SEO tags

**Test Detail Page:**
- Check URL params: nếu có `testSlug` → gọi GET by-slug endpoint
- Fallback: nếu có `testId` → vẫn gọi GET by-ID (backward compatibility)
- Parse slug từ URL: `const testSlug = searchParams.get('testSlug')`

---

### ✅ Phase 3: SEO Meta Tags

Thêm meta tags cho test detail pages:

**Title Tag:**
```html
<title>{test.title} | WordAI Marketplace</title>
```

**Meta Description:**
```html
<meta name="description" content={test.meta_description} />
```

**Open Graph Tags:**
```html
<meta property="og:title" content={test.title} />
<meta property="og:description" content={test.meta_description} />
<meta property="og:url" content={`https://wordai.vn/online-test?testSlug=${test.slug}`} />
<meta property="og:image" content={test.cover_image_url} />
```

**Twitter Card:**
```html
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content={test.title} />
<meta name="twitter:description" content={test.meta_description} />
<meta name="twitter:image" content={test.cover_image_url} />
```

---

### ✅ Phase 4: Backward Compatibility

**Quan trọng:** Hỗ trợ cả 2 loại URL:

**New format (priority):**
```
/online-test?testSlug=danh-gia-ky-nang-mem
```

**Old format (fallback):**
```
/online-test?testId=692e983006a09e9ff6537c1c
```

**Logic:**
```
if (testSlug) {
  // Call GET /marketplace/tests/by-slug/{slug}
  fetchTestBySlug(testSlug)
} else if (testId) {
  // Call GET /marketplace/tests/{test_id} (existing endpoint)
  fetchTestById(testId)
} else {
  // Show 404
}
```

---

## 🚫 Những Gì Frontend KHÔNG Cần Làm

### ❌ Không cần generate slug
- Backend tự động tạo slug từ title khi publish
- Backend tự động regenerate khi update title
- Frontend chỉ cần **sử dụng** slug có sẵn từ API response

### ❌ Không cần validate slug uniqueness
- Backend đã handle uniqueness với counter suffix
- Endpoint check-slug chỉ để dùng sau này nếu có tính năng custom slug

### ❌ Không cần xử lý Vietnamese characters
- Backend đã convert tiếng Việt sang ASCII an toàn
- VD: "Đánh Giá" → "danh-gia", "Kỹ Năng" → "ky-nang"

---

## 📝 Migration Notes

### Database Status
✅ Migration đã chạy thành công:
- 15 published tests đã có slug và meta_description
- Database index đã được tạo cho field `slug`
- Tất cả tests mới sẽ tự động có slug khi publish

### Test Data Examples

| Test Title | Generated Slug | Status |
|-----------|----------------|--------|
| Đánh Giá Kỹ Năng Mềm Của Bạn | `danh-gia-ky-nang-mem-cua-ban` | ✅ |
| Kiểm tra IQ tổng quát | `kiem-tra-iq-tong-quat-cho-moi-lua-tuoi` | ✅ |
| IELTS Reading Passage | `ielts-reading-passage-traffic-congestion-in-modern-cities` | ✅ |
| Bài test Holland Code | `bai-test-holland-code-mien-phi-chuan-quoc-te-2025` | ✅ |

---

## 🎨 UI/UX Recommendations

### 1. **Test Cards (Browse/Leaderboard)**
- Copy link button: Copy slug URL to clipboard
- Share buttons: Use slug URLs for social sharing
- Display slug dưới title (optional, for power users)

### 2. **Test Detail Page**
- Show clean URL in browser address bar
- Add "Share" button with slug URL
- Include meta tags for rich social previews

### 3. **Search Results**
- Use slug URLs in search result links
- Highlight keywords in meta_description excerpt

---

## 🔍 SEO Benefits

### Before:
```
URL: /online-test?testId=692e983006a09e9ff6537c1c
Title: Online Test
Meta: (generic description)
```

❌ Not SEO-friendly
❌ Hard to remember
❌ Not shareable

### After:
```
URL: /online-test?testSlug=danh-gia-ky-nang-mem
Title: Đánh Giá Kỹ Năng Mềm Của Bạn | WordAI
Meta: Bạn có biết: 85% thành công trong sự nghiệp được quyết định bởi kỹ năng mềm...
```

✅ SEO-friendly keywords in URL
✅ Readable and memorable
✅ Better click-through rate
✅ Rich social media previews
✅ Improved Google indexing

---

## 🧪 Testing Checklist

### Backend Testing (✅ Done)
- [x] Slug generation works for Vietnamese text
- [x] Slug uniqueness enforced with counter
- [x] Meta description truncated at 160 chars
- [x] GET by-slug endpoint returns correct data
- [x] Browse/leaderboard include slug fields
- [x] Migration script ran successfully

### Frontend Testing (To Do)
- [ ] Old URLs (testId) still work
- [ ] New URLs (testSlug) work correctly
- [ ] Share links use slug format
- [ ] Meta tags display correctly
- [ ] Social media previews work
- [ ] 404 page for invalid slugs
- [ ] URL updates when navigating

---

## 📚 Related Documentation

- **Full Implementation Plan:** `SLUG_IMPLEMENTATION_PLAN.md`
- **Slug Generator Source:** `src/utils/slug_generator.py`
- **Backend Endpoints:** `src/api/marketplace_routes.py`, `src/api/test_marketplace_routes.py`
- **Migration Script:** `migrate_add_test_slugs.py`

---

## 💡 Future Enhancements

### Potential Features (Not Implemented Yet)
1. **Custom Slug Editor:** Allow creators to customize slug (using check-slug endpoint)
2. **Slug History:** Track slug changes for redirects
3. **Canonical URLs:** Implement 301 redirects from old URLs to slug URLs
4. **Slug Analytics:** Track which slugs get most clicks

---

## 🆘 Support & Questions

Nếu có vấn đề về slug system:
1. Check backend logs: Slug generation có thành công?
2. Verify database: Test có field `slug` và `meta_description`?
3. Test endpoints: GET by-slug trả về đúng data?
4. Check URL params: `testSlug` có được parse đúng?

---

**Last Updated:** December 2, 2025
**Backend Version:** v1.0 (Slug System Completed)
**Status:** ✅ Ready for Frontend Integration
