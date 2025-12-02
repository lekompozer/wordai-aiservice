# Test Slug Implementation Plan

## Mục tiêu
Thay đổi URL từ `testId` sang `slug` để SEO-friendly, tương tự như book system:
- Hiện tại: `https://wordai.pro/online-test?view=public&testId=692e983006a09e9ff6537c1c`
- Mục tiêu: `https://wordai.pro/online-test?view=community&testSlug=danh-gia-ky-nang-mem`

## 1. Database Schema Changes

### Thêm vào `online_tests` collection:
```javascript
{
  "slug": "danh-gia-ky-nang-mem-cua-ban",  // URL-friendly slug (unique trong marketplace)
  "meta_description": "Bạn có biết: 85% thành công trong sự nghiệp được quyết định bởi KỸ NĂNG MỀM?...",  // SEO meta (max 160 chars)
  // ... existing fields
}
```

### Index requirements:
```javascript
db.online_tests.createIndex({ "slug": 1 }, { unique: true, sparse: true })
// sparse: true vì chỉ published tests mới có slug
```

## 2. Slug Generation Logic

### Utility Function (✅ Created):
- File: `src/utils/slug_generator.py`
- Functions:
  - `generate_slug(text)` - Convert Vietnamese/English to ASCII slug
  - `generate_unique_slug(text, check_fn)` - Ensure uniqueness
  - `generate_meta_description(desc)` - Create SEO meta

### Examples:
```python
"Đánh Giá Kỹ Năng Mềm Của Bạn" → "danh-gia-ky-nang-mem-cua-ban"
"Python Programming 101" → "python-programming-101"
"Hướng dẫn React.js & Next.js" → "huong-dan-react-js-next-js"
```

## 3. Backend API Changes

### A. Publish Endpoint (Add slug generation)
**File**: `src/api/test_marketplace_routes.py`
**Endpoint**: `POST /{test_id}/marketplace/publish`

Changes needed:
```python
# Generate slug from title
from src.utils.slug_generator import generate_unique_slug, generate_meta_description

# Check if slug exists (for uniqueness)
def check_slug_exists(slug, exclude_id):
    query = {"slug": slug}
    if exclude_id:
        query["_id"] = {"$ne": ObjectId(exclude_id)}
    return mongo_service.db["online_tests"].count_documents(query) > 0

# Generate slug
slug = generate_unique_slug(
    title,
    check_slug_exists,
    exclude_id=test_id
)

# Generate meta description
meta = generate_meta_description(description, max_length=160)

# Add to marketplace_config
marketplace_config = {
    # ... existing fields
    "slug": slug,
    "meta_description": meta,
}

# Also add slug to test document root level
update_data = {
    "marketplace_config": marketplace_config,
    "slug": slug,  # Add slug to root for easy querying
    "meta_description": meta,
    # ... existing fields
}
```

### B. Update Config Endpoint (Update slug if title changes)
**File**: `src/api/test_marketplace_routes.py`
**Endpoint**: `PATCH /{test_id}/marketplace/config`

Changes needed:
```python
# If title is updated, regenerate slug
if title and title != test_doc.get("title"):
    new_slug = generate_unique_slug(
        title,
        check_slug_exists,
        exclude_id=test_id
    )
    update_data["slug"] = new_slug
    update_data["marketplace_config.slug"] = new_slug
```

### C. NEW Endpoint: Get Test by Slug
**File**: `src/api/marketplace_routes.py`
**Endpoint**: `GET /marketplace/tests/by-slug/{slug}`

```python
@router.get("/tests/by-slug/{slug}")
async def get_test_by_slug(
    slug: str,
    authorization: Optional[str] = Header(None)
):
    """
    Get marketplace test by slug (SEO-friendly URL)

    Example: /marketplace/tests/by-slug/danh-gia-ky-nang-mem
    """
    test = db.online_tests.find_one({
        "slug": slug,
        "marketplace_config.is_public": True
    })

    if not test:
        raise HTTPException(404, "Test not found")

    # Return same structure as get_marketplace_test_detail
    # ... (reuse existing logic)
```

### D. Update Browse Endpoint (Include slug in results)
**File**: `src/api/marketplace_routes.py`
**Endpoint**: `GET /marketplace/tests`

Changes needed:
```python
results.append({
    "test_id": test_id_str,
    "slug": test.get("slug"),  # ✅ ADD THIS
    "meta_description": test.get("meta_description"),  # ✅ ADD THIS
    "title": test.get("title", "Untitled"),
    # ... existing fields
})
```

### E. Update Leaderboard Endpoint (Include slug)
**File**: `src/api/marketplace_routes.py`
**Endpoint**: `GET /marketplace/leaderboard/tests`

Changes needed:
```python
{
    "$project": {
        "test_id": {"$toString": "$_id"},
        "slug": "$slug",  # ✅ ADD THIS
        "meta_description": "$meta_description",  # ✅ ADD THIS
        "title": 1,
        # ... existing fields
    }
}
```

### F. NEW Endpoint: Check Slug Availability
**File**: `src/api/test_marketplace_routes.py`
**Endpoint**: `GET /check-slug/{slug}`

```python
@router.get("/check-slug/{slug}")
async def check_test_slug_availability(
    slug: str,
    user_info: dict = Depends(require_auth)
):
    """
    Check if slug is available
    Returns suggestions if taken
    """
    exists = mongo_service.db["online_tests"].count_documents({
        "slug": slug
    }) > 0

    if not exists:
        return {"available": True, "slug": slug}

    # Generate suggestions
    from datetime import datetime
    year = datetime.now().year

    suggestions = [
        f"{slug}-2",
        f"{slug}-{year}",
        f"{slug}-v2"
    ]

    return {
        "available": False,
        "slug": slug,
        "suggestions": suggestions
    }
```

## 4. Frontend Changes

### A. URL Structure Change
```javascript
// Before
const url = `/online-test?view=public&testId=${testId}`

// After
const url = `/online-test?view=community&testSlug=${slug}`
```

### B. API Calls Update
```javascript
// Browse marketplace - use slug for link generation
tests.forEach(test => {
  const link = `/online-test?view=community&testSlug=${test.slug}`
  // or cleaner: `/tests/${test.slug}`
})

// Get test detail - fetch by slug instead of ID
const response = await fetch(`/api/v1/marketplace/tests/by-slug/${slug}`)
```

### C. SEO Meta Tags
```html
<meta name="description" content="{{ test.meta_description }}" />
<meta property="og:title" content="{{ test.title }}" />
<meta property="og:description" content="{{ test.meta_description }}" />
<meta property="og:url" content="https://wordai.pro/tests/{{ test.slug }}" />
```

## 5. Migration Strategy

### Step 1: Add slug to existing tests
```javascript
// Run migration script
db.online_tests.find({ "marketplace_config.is_public": true }).forEach(test => {
  const slug = generateSlug(test.title)
  const meta = generateMeta(test.marketplace_config.description)

  db.online_tests.updateOne(
    { _id: test._id },
    {
      $set: {
        slug: ensureUnique(slug),
        meta_description: meta
      }
    }
  )
})
```

### Step 2: Create unique index
```javascript
db.online_tests.createIndex({ "slug": 1 }, { unique: true, sparse: true })
```

### Step 3: Deploy backend changes
- Deploy slug generation in publish/update endpoints
- Deploy new `GET /by-slug/{slug}` endpoint
- Update existing GET endpoints to return slug

### Step 4: Deploy frontend changes
- Update URL generation to use slug
- Update detail page to fetch by slug
- Keep testId as fallback for old URLs

## 6. Backward Compatibility

### Support both testId and slug
```python
# Frontend can check query params
const testId = searchParams.get('testId')
const testSlug = searchParams.get('testSlug')

if (testSlug) {
  // New way: fetch by slug
  fetchTestBySlug(testSlug)
} else if (testId) {
  // Old way: fetch by ID (redirect to slug URL)
  const test = await fetchTestById(testId)
  router.replace(`/tests/${test.slug}`)
}
```

## 7. Benefits

1. **SEO Improvement**
   - Descriptive URLs: `danh-gia-ky-nang-mem` vs `692e983006a09e9ff6537c1c`
   - Better click-through rate in search results
   - Keywords in URL boost ranking

2. **User Experience**
   - Memorable URLs
   - Shareable links (look professional)
   - Clear content indication

3. **Analytics**
   - Easier to track in Google Analytics
   - Human-readable URLs in reports

## 8. Implementation Checklist

Backend:
- [✅] Create slug_generator utility
- [ ] Add slug to publish endpoint
- [ ] Add slug to update config endpoint
- [ ] Create GET by-slug endpoint
- [ ] Update browse endpoint (return slug)
- [ ] Update leaderboard endpoint (return slug)
- [ ] Create check-slug endpoint
- [ ] Run migration script for existing tests
- [ ] Create database index

Frontend:
- [ ] Update marketplace browse (use slug in links)
- [ ] Update test detail page (fetch by slug)
- [ ] Add SEO meta tags
- [ ] Add backward compatibility (testId fallback)
- [ ] Update share URLs

Testing:
- [ ] Test Vietnamese slug generation
- [ ] Test slug uniqueness validation
- [ ] Test by-slug endpoint
- [ ] Test backward compatibility
- [ ] Test SEO meta tags
