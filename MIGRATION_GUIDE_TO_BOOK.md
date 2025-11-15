# Migration Plan: Guide → Book Terminology Change

**Date**: November 15, 2025
**Impact**: Database collections, API endpoints, models, documentation

---

## 📋 Overview

Thay đổi terminology từ "Guide" sang "Book" để phù hợp với hệ thống Online Books:
- **Guide** → **Book**
- **User Guide** → **Online Book**
- **Chapter** → **Chapter** (giữ nguyên)
- **Guide Permission** → **Book Permission**

---

## 🗄️ Database Changes

### Collections to Rename:

1. **`user_guides`** → **`online_books`**
   - Giữ nguyên tất cả fields
   - Update indexes với tên mới

2. **`guide_chapters`** → **`book_chapters`**
   - Field `guide_id` → `book_id`
   - Giữ nguyên các fields khác

3. **`guide_permissions`** → **`book_permissions`**
   - Field `guide_id` → `book_id`
   - Giữ nguyên các fields khác

### Migration Script:
```javascript
// MongoDB migration commands
db.user_guides.renameCollection("online_books");
db.guide_chapters.renameCollection("book_chapters");
db.guide_permissions.renameCollection("book_permissions");

// Update field names in book_chapters
db.book_chapters.updateMany(
  {},
  { $rename: { "guide_id": "book_id" } }
);

// Update field names in book_permissions
db.book_permissions.updateMany(
  {},
  { $rename: { "guide_id": "book_id" } }
);

// Update indexes
db.book_chapters.dropIndex("guide_chapters_order");
db.book_chapters.createIndex(
  [{ "book_id": 1 }, { "order_index": 1 }],
  { name: "book_chapters_order" }
);
```

---

## 🔌 API Endpoint Changes

### Phase 2: Book Management (was Guide Management)
- `POST /guides` → `POST /books`
- `GET /guides` → `GET /books`
- `GET /guides/{guide_id}` → `GET /books/{book_id}`
- `PATCH /guides/{guide_id}` → `PATCH /books/{book_id}`
- `DELETE /guides/{guide_id}` → `DELETE /books/{book_id}`

### Phase 3: Chapter Management
- `POST /guides/{guide_id}/chapters` → `POST /books/{book_id}/chapters`
- `GET /guides/{guide_id}/chapters` → `GET /books/{book_id}/chapters`
- `PATCH /guides/{guide_id}/chapters/{chapter_id}` → `PATCH /books/{book_id}/chapters/{chapter_id}`
- `DELETE /guides/{guide_id}/chapters/{chapter_id}` → `DELETE /books/{book_id}/chapters/{chapter_id}`
- `POST /guides/{guide_id}/chapters/reorder` → `POST /books/{book_id}/chapters/reorder`

### Phase 4: Book Permissions (was Guide Permissions)
- `POST /guides/{guide_id}/permissions/users` → `POST /books/{book_id}/permissions/users`
- `GET /guides/{guide_id}/permissions/users` → `GET /books/{book_id}/permissions/users`
- `DELETE /guides/{guide_id}/permissions/users/{user_id}` → `DELETE /books/{book_id}/permissions/users/{user_id}`
- `POST /guides/{guide_id}/permissions/invite` → `POST /books/{book_id}/permissions/invite`

### Phase 5: Public View
- `GET /public/guides/{slug}` → `GET /public/books/{slug}`
- `GET /public/guides/{slug}/chapters/{chapter_slug}` → `GET /public/books/{slug}/chapters/{chapter_slug}`
- `POST /public/guides/{slug}/views` → `POST /public/books/{slug}/views`
- `GET /guides/by-domain/{domain}` → `GET /books/by-domain/{domain}`

---

## 📦 Code Files to Update

### Python Files:

1. **Models**:
   - `src/models/user_guide_models.py` → `src/models/online_book_models.py`
   - `src/models/guide_chapter_models.py` → `src/models/book_chapter_models.py`
   - `src/models/guide_permission_models.py` → `src/models/book_permission_models.py`
   - `src/models/public_guide_models.py` → `src/models/public_book_models.py`

2. **Services**:
   - `src/services/user_guide_manager.py` → `src/services/online_book_manager.py`
   - `src/services/guide_chapter_manager.py` → `src/services/book_chapter_manager.py`
   - `src/services/guide_permission_manager.py` → `src/services/book_permission_manager.py`

3. **Routes**:
   - `src/api/user_guide_routes.py` → `src/api/online_book_routes.py`
   - Update router prefix: `/api/v1/guides` → `/api/v1/books`

4. **Tests**:
   - `test_permissions_api.py` → Update all variable names
   - `test_public_view_api.py` → Update all variable names

### Documentation Files:

1. **API Specs**:
   - `FRONTEND_API_SPECS.md` → Update all endpoints

2. **Phase Docs**:
   - `PHASE4_USER_PERMISSIONS_API.md` → Update terminology
   - `PHASE5_PUBLIC_VIEW_API.md` → Update terminology

3. **Tracking Docs**:
   - `GITBOOK_BACKEND_IMPLEMENTATION_PLAN.md` → Rename to `ONLINEBOOK_BACKEND_IMPLEMENTATION_PLAN.md`
   - `ENDPOINT_GAP_ANALYSIS.md` → Update all endpoints

---

## 🔄 Migration Steps (Execute in Order)

### Step 1: Backup Database
```bash
mongodump --db ai_service_db --out /backup/pre-book-migration
```

### Step 2: Run MongoDB Migrations
```bash
mongo ai_service_db < migration_guide_to_book.js
```

### Step 3: Update Python Code
- Rename files
- Find & replace all occurrences:
  - `guide_id` → `book_id`
  - `Guide` → `Book`
  - `guide` → `book` (variable names)
  - `user_guides` → `online_books`
  - `guide_chapters` → `book_chapters`
  - `guide_permissions` → `book_permissions`

### Step 4: Update Documentation
- All API docs
- README files
- Phase documentation

### Step 5: Run Tests
```bash
python test_permissions_api.py
python test_public_view_api.py
```

### Step 6: Deploy to Production
```bash
git add -A
git commit -m "refactor: Rename Guide → Book terminology (Online Books system)"
git push origin main
./deploy-compose-with-rollback.sh
```

---

## ⚠️ Breaking Changes

**CRITICAL**: This is a BREAKING CHANGE for frontend!

### Frontend Must Update:
1. All API endpoint URLs (`/guides` → `/books`)
2. Request/response field names (`guide_id` → `book_id`)
3. TypeScript interfaces
4. UI text ("Guide" → "Book")

### Backward Compatibility:
❌ **NO backward compatibility** - frontend MUST update simultaneously

### Recommended Approach:
1. Create feature flag: `USE_BOOK_TERMINOLOGY`
2. Support both endpoints temporarily:
   - `/guides/*` (deprecated, redirects to `/books/*`)
   - `/books/*` (new endpoints)
3. Remove old endpoints after frontend migration (2 weeks grace period)

---

## 📊 Estimated Effort

- Database migration: 10 minutes
- Code refactoring: 2-3 hours
- Testing: 1 hour
- Documentation: 1 hour
- Deployment: 30 minutes

**Total**: ~5 hours

---

## ✅ Verification Checklist

- [ ] Database collections renamed
- [ ] All indexes updated
- [ ] Python files renamed and updated
- [ ] API endpoints working with new paths
- [ ] Tests passing (100%)
- [ ] Documentation updated
- [ ] Frontend notified of breaking changes
- [ ] Production deployment successful
- [ ] Health check passing

---

## 🔜 Next Phase After Migration

**Phase 6: Enhanced Book System**
- Point system integration
- View permissions (public/one-time/forever/download)
- Reward points for book owners (80% revenue share)
- PDF download functionality
- Chapter-based document storage

**Status**: Ready to implement after terminology migration
