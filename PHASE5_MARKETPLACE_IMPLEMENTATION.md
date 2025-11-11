# Online Test Marketplace - Phase 5 Implementation Summary

## ✅ Implementation Status: READY FOR TESTING

### 📋 Overview
Implemented a full marketplace system where test creators can publish tests for points (80% creator revenue, 20% platform fee). Features include cover images, versioning, ratings/comments, and earnings management.

---

## 🗄️ Database Schema (6 Collections)

### 1. **online_tests** (Updated)
Added `marketplace_config` subdocument:
```javascript
{
  marketplace_config: {
    is_public: Boolean,              // Published status
    price_points: Number,            // 0 = free, no upper limit
    cover_image_url: String,         // Required 800x600+ image
    thumbnail_url: String,           // Auto-generated 300x200
    description: String,             // Max 2000 chars
    category: String,                // Optional category
    tags: [String],                  // Max 10 tags for search
    total_purchases: Number,         // Purchase count
    total_revenue: Number,           // Creator earnings (80%)
    avg_rating: Number,              // 0-5 stars
    rating_count: Number,            // Total ratings
    current_version: String,         // v1, v2, v3...
    published_at: Date,              // First publish timestamp
    updated_at: Date                 // Last update timestamp
  }
}
```

### 2. **test_versions** (New)
Stores snapshots of test content at publish time:
```javascript
{
  version_id: String,               // UUID
  test_id: String,                  // Reference to online_tests
  version_number: String,           // v1, v2, v3...
  snapshot: {
    title: String,
    questions: Array,               // Full question data
    time_limit: Number,
    settings: Object
  },
  is_current: Boolean,              // Latest version flag
  published_by: String,             // Creator UID
  published_at: Date,
  stats: {
    purchases: Number,              // Purchases on this version
    avg_rating: Number
  }
}
```

### 3. **test_purchases** (New)
Records all test purchases:
```javascript
{
  purchase_id: String,              // UUID
  test_id: String,                  // Reference to online_tests
  buyer_id: String,                 // User UID
  creator_id: String,               // Test creator UID
  price_paid: Number,               // Total points paid
  creator_earnings: Number,         // 80% of price_paid
  platform_fee: Number,             // 20% of price_paid
  version_purchased: String,        // v1, v2, v3...
  purchased_at: Date
}
```

### 4. **test_ratings** (New)
User ratings and comments:
```javascript
{
  rating_id: String,                // UUID
  test_id: String,                  // Reference to online_tests
  user_id: String,                  // Rater UID (must have purchased)
  rating: Number,                   // 1-5 stars
  comment: String,                  // Optional, max 1000 chars
  created_at: Date,
  updated_at: Date                  // For edit support
}
```

### 5. **user_points** (Existing)
User point balances (for purchases and transfers):
```javascript
{
  user_id: String,                  // User UID
  balance: Number,                  // Current points
  updated_at: Date
}
```

### 6. **point_transactions** (Existing)
All point movements:
```javascript
{
  transaction_id: String,           // UUID or prefixed ID
  user_id: String,                  // User or "PLATFORM"
  amount: Number,                   // Positive or negative
  transaction_type: String,         // "test_purchase", "test_sale_earnings", etc.
  description: String,
  metadata: Object,                 // Additional context
  created_at: Date
}
```

---

## 🔧 Services Implemented

### 1. **TestCoverImageService** (`src/services/test_cover_image_service.py`)
- ✅ Validates cover images (min 800x600, max 5MB, JPG/PNG)
- ✅ Generates thumbnails (300x200) automatically
- ✅ Optimizes images (JPEG quality 85%)
- ✅ Uploads to R2 storage with public URLs
- ✅ Unique filenames: `test-covers/{test_id}/{uuid}_{original_name}`

**Key Methods:**
- `validate_image()` - Check dimensions, size, format
- `generate_thumbnail()` - Create 300x200 thumbnail
- `optimize_image()` - Compress to JPEG quality 85%
- `upload_cover_image()` - Full pipeline with R2 upload

### 2. **TestVersionService** (`src/services/test_version_service.py`)
- ✅ Creates version snapshots on publish/update
- ✅ Auto-increments version numbers (v1 → v2 → v3...)
- ✅ Marks latest version as current
- ✅ Tracks version history with statistics
- ✅ Supports version comparison

**Key Methods:**
- `create_version_snapshot()` - Snapshot test content + auto-increment
- `get_version()` - Retrieve specific version
- `get_current_version()` - Get latest version
- `list_versions()` - Version history
- `update_version_stats()` - Update purchase/rating stats
- `compare_versions()` - Diff between versions

### 3. **R2Client Updates** (`src/storage/r2_client.py`)
- ✅ Added `upload_file_from_bytes()` - Upload in-memory data
- ✅ Added `_upload_bytes_sync()` - Synchronous bytes upload helper
- ✅ Supports direct bytes upload for generated thumbnails

---

## 🌐 API Endpoints (13 Total)

### Marketplace Management (6 endpoints)
**File:** `src/api/marketplace_routes.py`

#### 1. **POST** `/marketplace/tests/{test_id}/publish`
Publish test to marketplace with cover image.
- **Auth:** Required (creator only)
- **Body:** Form data with cover image file
  - `price_points: int` (≥0)
  - `description: str` (10-2000 chars)
  - `category: str` (optional)
  - `tags: str` (comma-separated, max 10)
  - `cover_image: file` (required, 800x600+, max 5MB)
- **Response:** Test published with version number
- **Side Effects:**
  - Creates version snapshot (v1, v2, v3...)
  - Uploads cover + thumbnail to R2
  - Sets marketplace_config.is_public = true

#### 2. **PATCH** `/marketplace/tests/{test_id}/config`
Update marketplace configuration (price, description, tags).
- **Auth:** Required (creator only)
- **Body:** JSON
  ```json
  {
    "price_points": 100,           // Optional
    "description": "New desc",     // Optional
    "category": "Science",         // Optional
    "tags": ["physics", "grade-10"] // Optional
  }
  ```
- **Note:** Does NOT create new version

#### 3. **POST** `/marketplace/tests/{test_id}/unpublish`
Hide test from marketplace (soft delete).
- **Auth:** Required (creator only)
- **Response:** Sets is_public = false
- **Note:** Preserves purchase history and versions

#### 4. **GET** `/marketplace/tests`
Browse marketplace with filters and sorting.
- **Auth:** Optional (for `has_purchased` flag)
- **Query Params:**
  - `category: str` - Filter by category
  - `tag: str` - Filter by single tag
  - `min_price: int` - Min price points
  - `max_price: int` - Max price points
  - `sort_by: str` - newest|oldest|popular|top_rated|price_low|price_high
  - `search: str` - Search in title/description
  - `page: int` (default 1)
  - `page_size: int` (default 20, max 100)
- **Response:** Paginated test list with creator info

#### 5. **GET** `/marketplace/tests/{test_id}`
Get detailed test view.
- **Auth:** Optional
- **Response:**
  - Full marketplace info
  - Sample questions (first 3) if not purchased/creator
  - Full questions if purchased or creator
  - Purchase status + date

#### 6. **GET** `/marketplace/me/earnings`
Get creator's total earnings from all tests.
- **Auth:** Required
- **Response:**
  ```json
  {
    "total_earnings": 12000,
    "test_count": 5,
    "tests": [
      {
        "test_id": "...",
        "title": "Math Quiz",
        "total_revenue": 8000,
        "total_purchases": 100,
        "avg_rating": 4.5
      }
    ]
  }
  ```

---

### Marketplace Transactions (7 endpoints)
**File:** `src/api/marketplace_transactions_routes.py`

#### 7. **POST** `/marketplace/tests/{test_id}/purchase`
Purchase a test (80/20 revenue split).
- **Auth:** Required
- **Body:** Empty
- **Logic:**
  1. Validates test is published
  2. Checks user is not creator
  3. Checks not already purchased
  4. Deducts points from buyer
  5. **80%** to creator's marketplace earnings
  6. **20%** to platform
  7. Creates purchase record
  8. Records 3 point transactions (buyer, creator, platform)
- **Response:** Purchase confirmation with earnings breakdown

#### 8. **POST** `/marketplace/tests/{test_id}/ratings`
Rate and comment on a test.
- **Auth:** Required
- **Body:** JSON
  ```json
  {
    "rating": 5,               // 1-5 stars
    "comment": "Great test!"   // Optional, max 1000 chars
  }
  ```
- **Validation:**
  - Must have purchased test
  - Cannot rate own test
- **Logic:**
  - Creates or updates rating
  - Recalculates test's avg_rating

#### 9. **GET** `/marketplace/tests/{test_id}/ratings`
Get test ratings with pagination.
- **Auth:** Not required
- **Query Params:**
  - `sort_by: str` - newest|oldest|highest|lowest
  - `page: int` (default 1)
  - `page_size: int` (default 20, max 100)
- **Response:** Paginated ratings with user names

#### 10. **GET** `/marketplace/me/earnings`
View creator's marketplace earnings.
- **Auth:** Required
- **Response:** Total earnings across all published tests

#### 11. **POST** `/marketplace/me/earnings/transfer`
Transfer marketplace earnings to point wallet.
- **Auth:** Required
- **Body:** JSON
  ```json
  {
    "amount_points": 5000
  }
  ```
- **Logic:**
  1. Validates sufficient earnings
  2. Deducts from test revenues (proportionally)
  3. Adds to user's point wallet
  4. Records transaction
- **Use Case:** Withdraw earnings to spend or cash out

---

## 💰 Revenue Model

### 80/20 Split on Every Purchase
```
Example: Test costs 100 points
├─ Buyer pays: 100 points (deducted from wallet)
├─ Creator earns: 80 points (added to marketplace earnings)
└─ Platform fee: 20 points (to PLATFORM account)
```

### Point Transactions Created
```javascript
// 1. Buyer deduction
{
  transaction_id: "purchase_{uuid}_buyer",
  user_id: "buyer_uid",
  amount: -100,
  transaction_type: "test_purchase"
}

// 2. Creator earnings (marketplace, NOT wallet yet)
{
  transaction_id: "purchase_{uuid}_creator",
  user_id: "creator_uid",
  amount: 80,
  transaction_type: "test_sale_earnings",
  metadata: {
    revenue_share: "80%",
    buyer_id: "buyer_uid"
  }
}

// 3. Platform fee
{
  transaction_id: "purchase_{uuid}_platform",
  user_id: "PLATFORM",
  amount: 20,
  transaction_type: "platform_fee",
  metadata: {
    revenue_share: "20%"
  }
}
```

### Earnings Flow
1. **Sale:** Earnings accumulate in `marketplace_config.total_revenue` (NOT in wallet)
2. **Transfer:** Creator manually transfers to wallet via `/marketplace/me/earnings/transfer`
3. **Withdraw:** Creator can then cash out via Phase 6 (Point Redemption)

---

## 🎨 Cover Image Requirements

### Upload Constraints
- **Min Resolution:** 800x600 pixels
- **Max File Size:** 5 MB
- **Formats:** JPEG, PNG
- **Aspect Ratio:** Any (recommended 4:3 or 16:9)

### Processing Pipeline
```
1. Validate format, size, dimensions
2. Optimize original (JPEG quality 85%)
3. Generate thumbnail (300x200, letterbox)
4. Upload both to R2 storage
5. Return public URLs
```

### Storage Paths
```
R2 Bucket: {R2_BUCKET_NAME}
├─ test-covers/{test_id}/{uuid}_original.jpg
└─ test-covers/{test_id}/{uuid}_thumb.jpg
```

---

## 📦 Versioning System

### How It Works
- **v1:** First publish
- **v2:** Update test content and re-publish
- **v3:** Update again...

### Version Snapshot Contents
```javascript
{
  version_number: "v1",
  snapshot: {
    title: "Original title",
    questions: [...],      // Full questions at publish time
    time_limit: 3600,
    settings: {...}
  },
  is_current: true,       // Only latest version = true
  published_at: "2025-01-10T..."
}
```

### Use Cases
- Users who purchased v1 can still access v1 content
- Creators can update tests without affecting old purchases
- Version history for auditing/rollback

---

## 🚀 Deployment Steps

### 1. Run Database Migration
```bash
# SSH to production server
ssh user@your-server

# Navigate to project
cd /path/to/wordai-aiservice

# Run migration
bash deploy-phase5-migration.sh
```

**What it does:**
- Adds indexes to `online_tests.marketplace_config.*`
- Creates `test_versions` collection with indexes
- Creates `test_ratings` collection with indexes
- Creates `test_purchases` collection with indexes
- Updates existing tests with empty marketplace_config

### 2. Restart FastAPI Server
```bash
# Restart with PM2 or systemd
pm2 restart wordai-api

# Or with systemd
sudo systemctl restart wordai-api
```

### 3. Verify Endpoints
Test health check:
```bash
curl https://your-domain.com/api/health
```

Test marketplace browse (should return empty initially):
```bash
curl https://your-domain.com/marketplace/tests
```

---

## 🧪 Testing Checklist

### Manual Testing Flow

#### 1. **Publish Test**
```bash
# Create form data
curl -X POST "https://your-domain.com/marketplace/tests/{test_id}/publish" \
  -H "Authorization: Bearer {token}" \
  -F "price_points=100" \
  -F "description=An amazing test about science" \
  -F "category=Science" \
  -F "tags=physics,grade-10" \
  -F "cover_image=@/path/to/cover.jpg"
```

#### 2. **Browse Marketplace**
```bash
curl "https://your-domain.com/marketplace/tests?sort_by=newest&page=1"
```

#### 3. **View Test Detail**
```bash
curl "https://your-domain.com/marketplace/tests/{test_id}"
```

#### 4. **Purchase Test**
```bash
curl -X POST "https://your-domain.com/marketplace/tests/{test_id}/purchase" \
  -H "Authorization: Bearer {buyer_token}" \
  -H "Content-Type: application/json"
```

#### 5. **Rate Test**
```bash
curl -X POST "https://your-domain.com/marketplace/tests/{test_id}/ratings" \
  -H "Authorization: Bearer {buyer_token}" \
  -H "Content-Type: application/json" \
  -d '{"rating": 5, "comment": "Excellent test!"}'
```

#### 6. **View Ratings**
```bash
curl "https://your-domain.com/marketplace/tests/{test_id}/ratings?sort_by=newest"
```

#### 7. **Check Earnings**
```bash
curl "https://your-domain.com/marketplace/me/earnings" \
  -H "Authorization: Bearer {creator_token}"
```

#### 8. **Transfer Earnings**
```bash
curl -X POST "https://your-domain.com/marketplace/me/earnings/transfer" \
  -H "Authorization: Bearer {creator_token}" \
  -H "Content-Type: application/json" \
  -d '{"amount_points": 1000}'
```

---

## 📊 Database Queries for Verification

### Check Published Tests
```javascript
db.online_tests.find({"marketplace_config.is_public": true})
```

### Check Version History
```javascript
db.test_versions.find({test_id: "TEST_ID"}).sort({published_at: -1})
```

### Check Purchase Records
```javascript
db.test_purchases.find({test_id: "TEST_ID"})
```

### Check Point Transactions
```javascript
db.point_transactions.find({
  transaction_type: {$in: ["test_purchase", "test_sale_earnings", "platform_fee"]}
}).sort({created_at: -1}).limit(10)
```

### Check Platform Revenue
```javascript
db.point_transactions.aggregate([
  {$match: {user_id: "PLATFORM", transaction_type: "platform_fee"}},
  {$group: {_id: null, total: {$sum: "$amount"}}}
])
```

---

## 🔐 Security & Authorization

### Access Control
- **Publish:** Only test creator
- **Update Config:** Only test creator
- **Unpublish:** Only test creator
- **Browse/View:** Anyone (with optional auth for `has_purchased`)
- **Purchase:** Any authenticated user (except creator)
- **Rate:** Only users who purchased (not creator)
- **View Ratings:** Anyone
- **Earnings:** Only test creator
- **Transfer Earnings:** Only test creator

### Validation Rules
1. Cannot purchase own test
2. Cannot purchase same test twice
3. Cannot rate without purchasing
4. Cannot rate own test
5. Cannot transfer more than available earnings
6. Cover image must meet size/format requirements
7. Test must have questions to publish

---

## 🐛 Known Issues & Edge Cases

### Handled
✅ **Free Tests (0 points):** Allowed, no payment flow, only increment purchase count  
✅ **Duplicate Purchases:** Blocked with 400 error  
✅ **Insufficient Points:** Checked before purchase  
✅ **Image Validation:** Enforced on upload  
✅ **Rating Updates:** Users can update their existing rating  
✅ **Version Snapshots:** Auto-created on publish  
✅ **Earnings Transfer:** Proportional deduction from multiple tests  

### To Monitor
⚠️ **R2 Storage Costs:** Monitor cover image storage usage  
⚠️ **Large Thumbnails:** 300x200 may be large for some UIs (can optimize further)  
⚠️ **Concurrent Purchases:** MongoDB handles with atomic operations  
⚠️ **Point Balance Race Conditions:** Use `$inc` for atomicity  

---

## 🔮 Phase 6 Preview (Point Redemption)

Next phase will add:
- Banking info management
- Withdrawal request submission
- Admin approval workflow
- Bank transfer tracking
- Exchange rate: **200 points = 100,000 VND**

**Files Ready:**
- `docs/ONLINE_TEST_POINT_REDEMPTION_API_PHASE6.md` (full spec)

---

## 📝 Files Created/Modified

### New Files (5)
1. `src/api/marketplace_routes.py` (660 lines)
2. `src/api/marketplace_transactions_routes.py` (650 lines)
3. `src/services/test_cover_image_service.py` (330 lines)
4. `src/services/test_version_service.py` (350 lines)
5. `migrations/phase5_marketplace_setup.py` (270 lines)
6. `deploy-phase5-migration.sh` (deployment script)

### Modified Files (2)
1. `src/app.py` - Added router imports and includes
2. `src/storage/r2_client.py` - Added `upload_file_from_bytes()` method

### Documentation (2)
1. `docs/ONLINE_TEST_MARKETPLACE_API_PHASE5.md` (2150 lines)
2. `docs/ONLINE_TEST_POINT_REDEMPTION_API_PHASE6.md` (full Phase 6 spec)

---

## ✅ Next Steps

1. **Deploy to Production:**
   ```bash
   bash deploy-phase5-migration.sh
   pm2 restart wordai-api
   ```

2. **Test All Endpoints:**
   - Create test account
   - Generate test
   - Publish with cover image
   - Browse marketplace
   - Purchase as different user
   - Rate the test
   - Transfer earnings

3. **Monitor Logs:**
   ```bash
   pm2 logs wordai-api --lines 100
   ```

4. **Frontend Integration:**
   - Build marketplace UI
   - Image upload component
   - Rating/comment section
   - Earnings dashboard

5. **Phase 6 Implementation:**
   - Banking info CRUD
   - Withdrawal requests
   - Admin approval system
   - Bank transfer tracking

---

## 📞 Support

For issues or questions:
- Check logs: `pm2 logs wordai-api`
- Review MongoDB: `db.online_tests.find({"marketplace_config.is_public": true})`
- Test endpoints with curl/Postman
- Review API docs: `docs/ONLINE_TEST_MARKETPLACE_API_PHASE5.md`

---

**Status:** ✅ **READY FOR PRODUCTION DEPLOYMENT**  
**Implementation Date:** 2025-01-10  
**Version:** Phase 5 Complete
