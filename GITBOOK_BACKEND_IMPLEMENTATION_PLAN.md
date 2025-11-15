# GitBook User Guide - Backend Implementation Plan

## 📋 Overview

Kế hoạch implement backend cho tính năng **User Guide (GitBook-style)** chia theo 6 phases.

**Mục tiêu:**
- Tạo hệ thống User Guide với chapters nested
- Hỗ trợ public/private/unlisted visibility
- **User permissions** cho private guides (whitelist users)
- Public view không cần auth
- Owner có full control

**Tech Stack:**
- FastAPI (Python)
- MongoDB (PyMongo)
- Redis (caching)
- Pydantic (validation)

---

## 📊 Implementation Phases

### ✅ Phase 1: Database Schema & Models (Week 1)

**Mục tiêu:** Thiết lập database collections, indexes và Pydantic models

**Deliverables:**
- [x] Tạo MongoDB collections: `user_guides`, `guide_chapters`, `guide_permissions`
- [x] Setup indexes cho performance (19 indexes total)
- [x] Pydantic models cho request/response validation
- [x] Database manager methods (CRUD operations)

**Status:** � Completed

**Estimated Time:** 5-7 days

**Actual Time:** 1 day (2025-11-15)

**Dependencies:** None

**Detail Document:** `PHASE1_DATABASE_MODELS.md` ✅

**Completed Files:**
- ✅ `src/models/user_guide_models.py` - Guide models
- ✅ `src/models/guide_chapter_models.py` - Chapter models
- ✅ `src/models/guide_permission_models.py` - Permission models
- ✅ `src/services/user_guide_manager.py` - Guide CRUD operations
- ✅ `src/services/guide_chapter_manager.py` - Chapter operations
- ✅ `src/services/guide_permission_manager.py` - Permission operations
- ✅ `initialize_user_guides.py` - Database setup script
- ✅ `test_user_guide_models.py` - Model validation tests

**Database Collections Created:**
- ✅ `user_guides` - 6 indexes
- ✅ `guide_chapters` - 6 indexes  
- ✅ `guide_permissions` - 7 indexes

**Test Results:**
- ✅ All model validation tests passed
- ✅ All collections and indexes created successfully

---

### ✅ Phase 2: Guide Management API (Week 2)

**Mục tiêu:** API endpoints để tạo và quản lý User Guides

**Deliverables:**
- [ ] `POST /api/v1/guides` - Create guide
- [ ] `GET /api/v1/guides` - List user's guides (pagination, filters)
- [ ] `GET /api/v1/guides/{guide_id}` - Get guide details
- [ ] `PATCH /api/v1/guides/{guide_id}` - Update guide metadata
- [ ] `DELETE /api/v1/guides/{guide_id}` - Delete guide
- [ ] Auth middleware integration
- [ ] Owner permission checks

**Status:** 🟡 Not Started

**Estimated Time:** 5-7 days

**Dependencies:** Phase 1

**Detail Document:** `PHASE2_GUIDE_MANAGEMENT_API.md` (sẽ tạo khi implement)

---

### ✅ Phase 3: Chapter Management API (Week 3)

**Mục tiêu:** API endpoints để quản lý chapters và nested structure

**Deliverables:**
- [ ] `POST /api/v1/guides/{guide_id}/chapters` - Add chapter
- [ ] `GET /api/v1/guides/{guide_id}/chapters` - Get chapters tree
- [ ] `PATCH /api/v1/guides/{guide_id}/chapters/{chapter_id}` - Update chapter
- [ ] `DELETE /api/v1/guides/{guide_id}/chapters/{chapter_id}` - Remove chapter
- [ ] `POST /api/v1/guides/{guide_id}/chapters/reorder` - Bulk reorder
- [ ] Tree structure builder algorithm
- [ ] Validate max nesting depth (3 levels)

**Status:** 🟡 Not Started

**Estimated Time:** 5-7 days

**Dependencies:** Phase 1, Phase 2

**Detail Document:** `PHASE3_CHAPTER_MANAGEMENT_API.md` (sẽ tạo khi implement)

---

### ✅ Phase 4: User Permissions System (Week 4)

**Mục tiêu:** Quản lý quyền truy cập cho private guides

**Deliverables:**
- [ ] `POST /api/v1/guides/{guide_id}/permissions/users` - Add user permission
- [ ] `GET /api/v1/guides/{guide_id}/permissions/users` - List allowed users
- [ ] `DELETE /api/v1/guides/{guide_id}/permissions/users/{user_id}` - Remove user
- [ ] `POST /api/v1/guides/{guide_id}/permissions/invite` - Invite user by email
- [ ] Permission check middleware
- [ ] Email invitation system (optional)
- [ ] Access roles: `viewer` | `editor` (future)

**Status:** 🟡 Not Started

**Estimated Time:** 5-7 days

**Dependencies:** Phase 1, Phase 2

**Detail Document:** `PHASE4_USER_PERMISSIONS_API.md` (sẽ tạo khi implement)

---

### ✅ Phase 5: Public View API (Week 5)

**Mục tiêu:** API endpoints cho public access (không cần auth)

**Deliverables:**
- [ ] `GET /api/v1/public/guides/{slug}` - Get public guide info
- [ ] `GET /api/v1/public/guides/{slug}/chapters/{chapter_slug}` - Get chapter content
- [ ] `POST /api/v1/public/guides/{slug}/views` - Track analytics
- [ ] Visibility validation (public/unlisted/private)
- [ ] User permission check (for private guides)
- [ ] Redis caching layer
- [ ] SEO metadata preparation

**Status:** 🟡 Not Started

**Estimated Time:** 4-6 days

**Dependencies:** Phase 1, Phase 2, Phase 3, Phase 4

**Detail Document:** `PHASE5_PUBLIC_VIEW_API.md` (sẽ tạo khi implement)

---

### ✅ Phase 6: Integration & Optimization (Week 6)

**Mục tiêu:** Tích hợp với hệ thống hiện tại và optimize performance

**Deliverables:**
- [ ] `GET /api/documents/{document_id}/usage` - Document usage in guides
- [ ] Update `DELETE /api/documents/{document_id}` với usage check
- [ ] Redis caching cho public guides (5 min TTL)
- [ ] Analytics collection setup
- [ ] Slug uniqueness validation
- [ ] Query optimization (explain analysis)
- [ ] API testing (unit + integration tests)
- [ ] Error handling improvements
- [ ] API documentation (Swagger)

**Status:** 🟡 Not Started

**Estimated Time:** 5-7 days

**Dependencies:** Phase 1-5

**Detail Document:** `PHASE6_INTEGRATION_OPTIMIZATION.md` (sẽ tạo khi implement)

---

## 🔐 User Permissions Feature (New)

### Visibility Types

| Type | Description | Access Control |
|------|-------------|----------------|
| **Public** | Anyone can view | No auth required |
| **Unlisted** | Anyone with link can view | No auth required, not listed publicly |
| **Private** | Only allowed users can view | Auth required + permission check |

### Private Guide Permissions

**Collection:** `guide_permissions`

```javascript
{
  _id: ObjectId("..."),
  permission_id: "perm_abc123",
  guide_id: "guide_xyz789",
  user_id: "firebase_uid_of_viewer",    // User được phép xem

  // Permission details
  granted_by: "firebase_uid_of_owner",  // Owner granted permission
  access_level: "viewer",               // "viewer" | "editor" (future)

  // Invitation (optional)
  invited_email: "user@example.com",
  invitation_accepted: true,
  invited_at: ISODate("2025-11-15T10:00:00Z"),
  accepted_at: ISODate("2025-11-15T11:00:00Z"),

  // Timestamps
  created_at: ISODate("2025-11-15T10:00:00Z"),
  expires_at: null                      // null = no expiration
}
```

**Indexes:**
```javascript
db.guide_permissions.createIndex({ permission_id: 1 }, { unique: true });
db.guide_permissions.createIndex({ guide_id: 1, user_id: 1 }, { unique: true });
db.guide_permissions.createIndex({ guide_id: 1 });
db.guide_permissions.createIndex({ user_id: 1 });
db.guide_permissions.createIndex({ invited_email: 1 });
```

### Permission Check Flow

```
User requests: GET /api/v1/public/guides/my-private-guide
                    ↓
            Get guide by slug
                    ↓
         Check guide.visibility
                    ↓
    ┌───────────────┴───────────────┐
    │                               │
visibility = "public"      visibility = "private"
    │                               │
Return guide              Check user authenticated?
                                    ↓
                          ┌─────────┴─────────┐
                          │                   │
                     No auth            Has auth token
                          │                   │
                    403 Forbidden      Check permissions:
                                       - Is owner? → Allow
                                       - In guide_permissions? → Allow
                                       - Else → 403 Forbidden
```

---

## 📊 Progress Tracking

### Overall Progress: 17% (1/6 phases completed)

| Phase | Status | Progress | Start Date | End Date | Notes |
|-------|--------|----------|------------|----------|-------|
| Phase 1 | � Completed | 100% | 2025-11-15 | 2025-11-15 | All collections, indexes, models done |
| Phase 2 | 🟡 Not Started | 0% | - | - | Guide Management |
| Phase 3 | 🟡 Not Started | 0% | - | - | Chapter Management |
| Phase 4 | 🟡 Not Started | 0% | - | - | User Permissions |
| Phase 5 | 🟡 Not Started | 0% | - | - | Public View |
| Phase 6 | 🟡 Not Started | 0% | - | - | Integration |

**Status Legend:**
- 🟡 Not Started
- 🔵 In Progress
- 🟢 Completed
- 🔴 Blocked

---

## 📁 File Structure (Backend)

```
src/
├── api/
│   └── user_guide_routes.py           # All guide API endpoints
├── models/
│   ├── user_guide_models.py           # Pydantic models
│   └── guide_permission_models.py     # Permission models
├── services/
│   ├── user_guide_manager.py          # Guide CRUD operations
│   ├── guide_chapter_manager.py       # Chapter operations
│   └── guide_permission_manager.py    # Permission operations
└── middleware/
    └── guide_auth.py                  # Permission check middleware
```

---

## 🧪 Testing Strategy

### Unit Tests
- [ ] Database operations (CRUD)
- [ ] Permission validation logic
- [ ] Tree structure builder
- [ ] Slug generation

### Integration Tests
- [ ] API endpoints (all phases)
- [ ] Auth flow (owner vs viewer)
- [ ] Permission checks (private guides)
- [ ] Nested chapters logic

### E2E Tests
- [ ] Create guide → Add chapters → Publish
- [ ] Invite user → Accept → View private guide
- [ ] Reorder chapters (drag & drop simulation)
- [ ] Delete document with usage check

---

## 📝 API Endpoints Summary

### Total: 18 endpoints

| Category | Endpoints | Phase |
|----------|-----------|-------|
| Guide Management | 5 endpoints | Phase 2 |
| Chapter Management | 5 endpoints | Phase 3 |
| User Permissions | 4 endpoints | Phase 4 |
| Public View | 3 endpoints | Phase 5 |
| Document Integration | 1 endpoint | Phase 6 |

**Detailed list:** See `GITBOOK_USER_GUIDE_ANALYSIS.md`

---

## 🚀 Deployment Checklist

### Before Phase 1
- [ ] Create feature branch: `feature/user-guide-backend`
- [ ] Setup development environment
- [ ] Review existing code structure

### After Each Phase
- [ ] Write phase summary document
- [ ] Commit changes with clear messages
- [ ] Update progress tracking table
- [ ] Code review (if team available)
- [ ] Merge to feature branch

### Before Production
- [ ] All phases completed
- [ ] All tests passing
- [ ] API documentation complete
- [ ] Performance testing done
- [ ] Security review
- [ ] Merge to `main` branch
- [ ] Deploy to staging
- [ ] Deploy to production

---

## 📞 Notes & Decisions

### Design Decisions

1. **MongoDB vs PostgreSQL:** MongoDB chosen for flexibility with nested structures
2. **Permissions Collection:** Separate collection for scalability (future: roles, expiration)
3. **Slug Uniqueness:** Per-user uniqueness (not global) to allow same slug for different users
4. **Max Nesting:** 3 levels to prevent UI complexity
5. **Caching:** Redis for public guides only (private guides always fresh)

### Future Enhancements (Not in scope)

- [ ] Collaboration (multiple editors)
- [ ] Version history for guides
- [ ] Comments on chapters
- [ ] Search across all public guides
- [ ] Guide templates
- [ ] Export guide to PDF/EPUB
- [ ] Custom domain for guides

---

## 🔗 Related Documents

- **Technical Analysis:** `GITBOOK_USER_GUIDE_ANALYSIS.md` - Full technical specification
- **Frontend Plan:** (To be created by frontend team)
- **Phase Details:** (Created during implementation)
  - `PHASE1_DATABASE_MODELS.md`
  - `PHASE2_GUIDE_MANAGEMENT_API.md`
  - `PHASE3_CHAPTER_MANAGEMENT_API.md`
  - `PHASE4_USER_PERMISSIONS_API.md`
  - `PHASE5_PUBLIC_VIEW_API.md`
  - `PHASE6_INTEGRATION_OPTIMIZATION.md`

---

## 📊 Timeline Overview

```
Week 1: Phase 1 (Database & Models)
Week 2: Phase 2 (Guide Management API)
Week 3: Phase 3 (Chapter Management API)
Week 4: Phase 4 (User Permissions API)
Week 5: Phase 5 (Public View API)
Week 6: Phase 6 (Integration & Optimization)
```

**Total Time:** 6 weeks (30-42 days)

**Start Date:** TBD

**Target Completion:** TBD

---

*Document version: 1.0*
*Last updated: 2025-11-15*
*Status: Planning Phase*
