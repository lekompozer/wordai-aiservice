# Marketplace Filters Enhancement

## Tổng Quan
Cải thiện các endpoint marketplace với:
1. ✅ Filter theo **language** (ngôn ngữ test)
2. ✅ Cải thiện filter theo **category** (case-insensitive)
3. ✅ Validation **search minimum 4 ký tự**

---

## 1. Browse Marketplace Tests
**Endpoint:** `GET /api/v1/marketplace/tests`

### Query Parameters
```typescript
{
  // Existing filters
  category?: string;          // Filter by category (case-insensitive)
  tag?: string;              // Filter by tag
  min_price?: number;        // Minimum price (points)
  max_price?: number;        // Maximum price (points)
  sort_by?: 'newest' | 'oldest' | 'popular' | 'top_rated' | 'price_low' | 'price_high';
  page?: number;             // Page number (default: 1)
  page_size?: number;        // Items per page (default: 20, max: 100)
  
  // ✅ NEW
  language?: string;         // Filter by test language ('vi', 'en', 'ja', 'ko', 'zh-cn', etc.)
  search?: string;           // Search in title/description (minimum 4 characters)
}
```

### Improvements
1. **Language Filter:**
   - Field: `test_language`
   - Case-insensitive matching
   - Examples: `vi`, `en`, `ja`, `ko`, `zh-cn`, `zh-tw`, `th`, `id`, `ms`

2. **Category Filter:**
   - Changed from exact match to case-insensitive regex
   - Before: `"category": "Academic"` only
   - After: `"category": "academic"` or `"Category": "ACADEMIC"` all work

3. **Search Validation:**
   - Minimum 4 characters required
   - Trims whitespace before searching
   - FastAPI automatically validates via `Query(min_length=4)`

### Response
```json
{
  "success": true,
  "data": {
    "tests": [
      {
        "test_id": "...",
        "slug": "...",
        "title": "...",
        "test_language": "vi",  // ✅ NEW: Language included in response
        "category": "Academic",
        "tags": ["math", "calculus"],
        "price_points": 100,
        "total_purchases": 50,
        "avg_rating": 4.5,
        // ... other fields
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total_items": 45,
      "total_pages": 3,
      "has_next": true,
      "has_prev": false
    }
  }
}
```

### Usage Examples

**Filter by Vietnamese tests only:**
```bash
GET /api/v1/marketplace/tests?language=vi
```

**Filter by English academic tests:**
```bash
GET /api/v1/marketplace/tests?language=en&category=academic
```

**Search with minimum 4 chars:**
```bash
# ✅ Valid (4+ chars)
GET /api/v1/marketplace/tests?search=math

# ❌ Invalid (< 4 chars) - Returns validation error
GET /api/v1/marketplace/tests?search=mat
```

**Combined filters:**
```bash
GET /api/v1/marketplace/tests?language=vi&category=academic&search=toán&sort_by=popular
```

---

## 2. Leaderboard Tests
**Endpoint:** `GET /api/v1/marketplace/leaderboard/tests`

### Query Parameters
```typescript
{
  category?: string;         // Filter by category (case-insensitive)
  language?: string;         // ✅ NEW: Filter by test language
  period?: '7d' | '30d' | '90d' | 'all';  // Time period (default: '30d')
}
```

### Response
```json
{
  "success": true,
  "data": {
    "period": "30d",
    "category": "all",
    "language": "vi",  // ✅ NEW: Language filter applied
    "updated_at": "2025-12-03T10:00:00Z",
    "top_tests": [
      {
        "rank": 1,
        "test_id": "...",
        "slug": "...",
        "title": "...",
        "test_language": "vi",  // ✅ NEW: Language in response
        "category": "Academic",
        "stats": {
          "total_completions": 1500,
          "total_purchases": 300,
          "average_rating": 4.8,
          "rating_count": 150
        },
        // ... other fields
      }
    ]
  }
}
```

### Usage Examples

**Top Vietnamese tests in last 30 days:**
```bash
GET /api/v1/marketplace/leaderboard/tests?language=vi&period=30d
```

**Top English academic tests all time:**
```bash
GET /api/v1/marketplace/leaderboard/tests?language=en&category=academic&period=all
```

---

## 3. Implementation Details

### Database Fields
- `test_language`: String field containing language code (e.g., "vi", "en", "ja")
- `marketplace_config.category`: String field for test category

### Filter Logic
```python
# Language filter (exact match, lowercase)
if language:
    query["test_language"] = language.lower()

# Category filter (case-insensitive regex)
if category:
    query["marketplace_config.category"] = {"$regex": f"^{category}$", "$options": "i"}

# Search validation (min 4 chars)
if search and len(search.strip()) >= 4:
    query["$or"] = [
        {"title": {"$regex": search.strip(), "$options": "i"}},
        {"marketplace_config.description": {"$regex": search.strip(), "$options": "i"}},
    ]
```

---

## 4. Supported Languages
- `vi` - Tiếng Việt
- `en` - English
- `ja` - 日本語 (Japanese)
- `ko` - 한국어 (Korean)
- `zh-cn` - 简体中文 (Simplified Chinese)
- `zh-tw` - 繁體中文 (Traditional Chinese)
- `th` - ไทย (Thai)
- `id` - Bahasa Indonesia
- `ms` - Bahasa Melayu
- `km` - ភាសាខ្មែរ (Khmer)
- `lo` - ພາສາລາວ (Lao)
- `hi` - हिन्दी (Hindi)
- `pt` - Português
- `ru` - Русский
- `fr` - Français
- `de` - Deutsch
- `es` - Español

---

## 5. Frontend Integration Guide

### Filter by Language
```typescript
// Fetch Vietnamese tests
const response = await fetch('/api/v1/marketplace/tests?language=vi');

// Fetch Japanese tests
const response = await fetch('/api/v1/marketplace/tests?language=ja');
```

### Search with Validation
```typescript
const searchTerm = userInput.trim();

// Only call API if 4+ characters
if (searchTerm.length >= 4) {
  const response = await fetch(
    `/api/v1/marketplace/tests?search=${encodeURIComponent(searchTerm)}`
  );
} else {
  // Show message: "Nhập tối thiểu 4 ký tự để tìm kiếm"
}
```

### Combined Filters
```typescript
const params = new URLSearchParams({
  language: 'vi',
  category: 'academic',
  search: 'toán học',
  sort_by: 'popular',
  page: '1',
  page_size: '20'
});

const response = await fetch(`/api/v1/marketplace/tests?${params}`);
```

### UI Components

**Language Selector:**
```tsx
<select name="language">
  <option value="">Tất cả ngôn ngữ</option>
  <option value="vi">🇻🇳 Tiếng Việt</option>
  <option value="en">🇬🇧 English</option>
  <option value="ja">🇯🇵 日本語</option>
  <option value="ko">🇰🇷 한국어</option>
  <option value="zh-cn">🇨🇳 简体中文</option>
  <!-- ... other languages -->
</select>
```

**Search Input with Validation:**
```tsx
<input
  type="text"
  minLength={4}
  placeholder="Tìm kiếm test (tối thiểu 4 ký tự)"
  onChange={(e) => {
    const value = e.target.value.trim();
    if (value.length >= 4) {
      // Debounce and call API
      debouncedSearch(value);
    }
  }}
/>
```

---

## 6. Error Handling

### Search Too Short
```json
{
  "detail": [
    {
      "loc": ["query", "search"],
      "msg": "ensure this value has at least 4 characters",
      "type": "value_error.any_str.min_length",
      "ctx": {"limit_value": 4}
    }
  ]
}
```

**Frontend should:**
- Show inline error: "Vui lòng nhập tối thiểu 4 ký tự"
- Disable search button if < 4 chars
- Only call API when validation passes

---

## 7. Testing Checklist

### Browse Tests
- [ ] Filter by single language (vi, en, ja)
- [ ] Filter by category (case variations: "Academic", "academic", "ACADEMIC")
- [ ] Search with exactly 4 characters
- [ ] Search with < 4 characters (should fail validation)
- [ ] Search with whitespace only (should not search)
- [ ] Combined: language + category + search
- [ ] Pagination with filters
- [ ] Sort with filters

### Leaderboard Tests
- [ ] Filter by language
- [ ] Filter by category (case-insensitive)
- [ ] Combined: language + category + period
- [ ] Verify test_language in response

### Edge Cases
- [ ] Unknown language code (returns empty list)
- [ ] Mixed case category ("AcAdEmIc" should work)
- [ ] Search with special characters
- [ ] Empty filters (returns all public tests)

---

## Summary

**Changes Made:**
1. ✅ Added `language` query parameter to browse and leaderboard endpoints
2. ✅ Improved `category` filter to be case-insensitive
3. ✅ Added `min_length=4` validation to search parameter
4. ✅ Added `test_language` to response objects
5. ✅ Updated docstrings with new filter descriptions

**Benefits:**
- Users can filter marketplace by test language
- Category matching is more flexible (case-insensitive)
- Search validation prevents unnecessary API calls
- Better UX with clear filter options

**Ready for deployment!** 🚀
