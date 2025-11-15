# 🔍 API Endpoint Gap Analysis - User Guide Feature

> **Analysis Date:** November 15, 2025  
> **Purpose:** Compare required endpoints from frontend docs vs implemented backend APIs

---

## 📊 COMPARISON TABLE

| Category | Endpoint | Frontend Docs | Backend Status | Phase | Notes |
|----------|----------|---------------|----------------|-------|-------|
| **Guide Management** | POST /api/v1/guides | ✅ Required | ✅ **Implemented** | Phase 2 | Create guide |
| | GET /api/v1/guides | ✅ Required | ✅ **Implemented** | Phase 2 | List guides with pagination |
| | GET /api/v1/guides/{guide_id} | ✅ Required | ✅ **Implemented** | Phase 2 | Get guide details |
| | PATCH /api/v1/guides/{guide_id} | ✅ Required | ✅ **Implemented** | Phase 2 | Update guide |
| | DELETE /api/v1/guides/{guide_id} | ✅ Required | ✅ **Implemented** | Phase 2 | Delete guide |
| | POST /api/v1/guides/{guide_id}/publish | ⚠️ Required | ❌ **MISSING** | - | Publish/unpublish toggle |
| **Chapter Management** | POST /api/v1/guides/{guide_id}/chapters | ✅ Required | ✅ **Implemented** | Phase 3 | Add chapter |
| | GET /api/v1/guides/{guide_id}/chapters | ✅ Required | ✅ **Implemented** | Phase 3 | Get chapters tree |
| | PATCH /api/v1/guides/{guide_id}/chapters/{chapter_id} | ✅ Required | ✅ **Implemented** | Phase 3 | Update chapter |
| | DELETE /api/v1/guides/{guide_id}/chapters/{chapter_id} | ✅ Required | ✅ **Implemented** | Phase 3 | Remove chapter |
| | POST /api/v1/guides/{guide_id}/chapters/reorder | ✅ Required | ✅ **Implemented** | Phase 3 | Bulk reorder |
| **Public View** | GET /api/v1/public/guides/{slug} | ⚠️ Required | ❌ **MISSING** | Phase 5 | Get public guide + chapters (NO AUTH) |
| | GET /api/v1/public/guides/{slug}/chapters/{chapter_slug} | ⚠️ Required | ❌ **MISSING** | Phase 5 | Get chapter content (NO AUTH) |
| | POST /api/v1/public/guides/{slug}/views | ⚠️ Optional | ❌ **MISSING** | Phase 5 | Track view count analytics |
| **Custom Domain** | POST /api/v1/guides/{guide_id}/domain | ⚠️ Required | ❌ **MISSING** | Phase 6 | Add custom domain (Vercel API) |
| | POST /api/v1/guides/{guide_id}/domain/verify | ⚠️ Required | ❌ **MISSING** | Phase 6 | Verify DNS records |
| | DELETE /api/v1/guides/{guide_id}/domain | ⚠️ Required | ❌ **MISSING** | Phase 6 | Remove custom domain |
| **Permissions** | POST /api/v1/guides/{guide_id}/permissions/users | ⚠️ Optional | ❌ **MISSING** | Phase 4 | Grant user permission |
| | GET /api/v1/guides/{guide_id}/permissions/users | ⚠️ Optional | ❌ **MISSING** | Phase 4 | List permissions |
| | DELETE /api/v1/guides/{guide_id}/permissions/users/{user_id} | ⚠️ Optional | ❌ **MISSING** | Phase 4 | Revoke permission |
| | POST /api/v1/guides/{guide_id}/permissions/invite | ⚠️ Optional | ❌ **MISSING** | Phase 4 | Email invitation |
| **Analytics** | GET /api/v1/guides/{guide_id}/analytics | ⚠️ Optional | ❌ **MISSING** | - | Guide analytics dashboard |
| | GET /api/v1/guides/{guide_id}/analytics/domain | ⚠️ Optional | ❌ **MISSING** | - | Custom domain performance |
| **Helper Endpoints** | GET /api/v1/guides/by-domain/{domain} | ⚠️ Required | ❌ **MISSING** | Phase 5 | For Next.js middleware routing |

---

## 🚨 CRITICAL MISSING ENDPOINTS

### 1️⃣ **POST /api/v1/guides/{guide_id}/publish** ⚠️
**Priority:** HIGH (MVP)  
**Frontend Need:** Toggle publish/unpublish button in UI  
**Current Workaround:** Use PATCH /api/v1/guides/{guide_id} to update `is_published` field  

**Recommendation:**
```python
@router.post("/{guide_id}/publish", response_model=GuideResponse)
async def toggle_publish(
    guide_id: str,
    publish_data: PublishToggle,  # { is_published: bool }
    current_user: Dict = Depends(get_current_user)
):
    """Toggle guide publish status"""
    # Update is_published field
    # Update last_published_at timestamp
    # Return updated guide
```

**Analysis:** Not critical if frontend can use PATCH endpoint. Can be added later for convenience.

---

### 2️⃣ **GET /api/v1/public/guides/{slug}** 🔴
**Priority:** CRITICAL (MVP)  
**Frontend Need:** Public guide homepage (NO AUTH)  
**Impact:** Blocks public sharing feature completely  

**Recommendation:** Implement in **Phase 5** (Public View API)

```python
@router.get("/public/guides/{slug}")
async def get_public_guide(slug: str):
    """
    Get public guide with chapters tree (NO AUTH REQUIRED)
    
    Returns:
    - Guide metadata (title, description, color, logo)
    - Chapters tree structure
    - First chapter slug (for redirect)
    """
```

---

### 3️⃣ **GET /api/v1/public/guides/{slug}/chapters/{chapter_slug}** 🔴
**Priority:** CRITICAL (MVP)  
**Frontend Need:** Display chapter content publicly  
**Impact:** Blocks public guide viewing completely  

**Recommendation:** Implement in **Phase 5**

```python
@router.get("/public/guides/{slug}/chapters/{chapter_slug}")
async def get_public_chapter(slug: str, chapter_slug: str):
    """
    Get chapter content (NO AUTH REQUIRED)
    
    Returns:
    - Chapter metadata (title, icon)
    - Document content (HTML)
    - Next/previous chapter navigation
    """
```

---

### 4️⃣ **GET /api/v1/guides/by-domain/{domain}** 🔴
**Priority:** CRITICAL for custom domain feature  
**Frontend Need:** Next.js middleware URL rewriting  
**Impact:** Blocks custom domain feature  

**Recommendation:** Implement in **Phase 6** (Custom Domain)

```python
@router.get("/by-domain/{domain}")
async def get_guide_by_domain(domain: str):
    """
    Lookup guide by custom domain (for middleware)
    
    Used by Next.js middleware to rewrite URLs:
    docs.company.com/intro → /guides/{slug}/intro
    """
```

---

## ✅ IMPLEMENTED ENDPOINTS (Phase 2 & 3)

### Phase 2: Guide Management (5/6 endpoints) ✅

| Endpoint | Method | Status | Functionality |
|----------|--------|--------|---------------|
| `/api/v1/guides` | POST | ✅ Done | Create guide with validation |
| `/api/v1/guides` | GET | ✅ Done | List guides (pagination, filtering) |
| `/api/v1/guides/{guide_id}` | GET | ✅ Done | Get guide details (owner or shared) |
| `/api/v1/guides/{guide_id}` | PATCH | ✅ Done | Update guide metadata |
| `/api/v1/guides/{guide_id}` | DELETE | ✅ Done | Delete guide (cascade chapters) |
| `/api/v1/guides/{guide_id}/publish` | POST | ❌ Missing | Publish toggle (can use PATCH) |

---

### Phase 3: Chapter Management (5/5 endpoints) ✅

| Endpoint | Method | Status | Functionality |
|----------|--------|--------|---------------|
| `/api/v1/guides/{guide_id}/chapters` | POST | ✅ Done | Create chapter with nesting |
| `/api/v1/guides/{guide_id}/chapters` | GET | ✅ Done | Get chapters tree |
| `/api/v1/guides/{guide_id}/chapters/{chapter_id}` | PATCH | ✅ Done | Update chapter |
| `/api/v1/guides/{guide_id}/chapters/{chapter_id}` | DELETE | ✅ Done | Delete chapter (cascade) |
| `/api/v1/guides/{guide_id}/chapters/reorder` | POST | ✅ Done | Bulk reorder |

**Total Implemented:** 10/10 endpoints ✅

---

## 🟡 PENDING ENDPOINTS BY PHASE

### Phase 4: User Permissions (4 endpoints) - NOT STARTED

| Endpoint | Priority | Notes |
|----------|----------|-------|
| POST /guides/{guide_id}/permissions/users | Medium | Grant user permission |
| GET /guides/{guide_id}/permissions/users | Medium | List permissions |
| DELETE /guides/{guide_id}/permissions/users/{user_id} | Medium | Revoke permission |
| POST /guides/{guide_id}/permissions/invite | Low | Email invitation |

**Why Medium Priority:**
- Only needed for collaboration features
- Not blocking MVP (single-user guides work fine)
- Can add after public sharing works

---

### Phase 5: Public View API (3 endpoints) - CRITICAL FOR MVP 🔴

| Endpoint | Priority | Notes |
|----------|----------|-------|
| GET /public/guides/{slug} | **CRITICAL** | Blocks public sharing |
| GET /public/guides/{slug}/chapters/{chapter_slug} | **CRITICAL** | Blocks public viewing |
| POST /public/guides/{slug}/views | Low | Analytics (optional) |

**Why Critical:**
- **Main value proposition:** Share guides publicly like Gitbook
- Frontend cannot display public guides without these
- Should be implemented BEFORE Phase 4 permissions

---

### Phase 6: Custom Domain (4 endpoints) - NICE TO HAVE 🟢

| Endpoint | Priority | Notes |
|----------|----------|-------|
| POST /guides/{guide_id}/domain | Low | Premium feature |
| POST /guides/{guide_id}/domain/verify | Low | DNS verification |
| DELETE /guides/{guide_id}/domain | Low | Remove domain |
| GET /guides/by-domain/{domain} | Medium | Required if custom domain implemented |

**Why Low Priority:**
- Premium feature (can be paid upgrade)
- MVP works fine with wordai.pro domain
- Complex integration (Vercel API, DNS, SSL)

---

## 📋 RECOMMENDED IMPLEMENTATION ORDER

### ✅ Already Done (50% complete)
1. ✅ **Phase 1:** Database Schema & Models (3 collections, 19 indexes)
2. ✅ **Phase 2:** Guide Management API (5 endpoints)
3. ✅ **Phase 3:** Chapter Management API (5 endpoints)

### 🎯 Next Steps (Priority Order)

#### Sprint 1: Public Viewing (1-2 weeks) 🔴
**Why First:** Unblocks frontend public guide feature (core value prop)

1. **Phase 5:** Public View API (3 endpoints)
   - ✅ GET /public/guides/{slug}
   - ✅ GET /public/guides/{slug}/chapters/{chapter_slug}
   - ⚠️ POST /public/guides/{slug}/views (optional analytics)

**Acceptance Criteria:**
- [ ] Users can share public guide links
- [ ] No authentication required for public guides
- [ ] SEO metadata included in response
- [ ] Frontend can render public pages

---

#### Sprint 2: Collaboration (1-2 weeks) 🟡
**Why Second:** Enables team features after MVP works

2. **Phase 4:** User Permissions System (4 endpoints)
   - ✅ POST /guides/{guide_id}/permissions/users
   - ✅ GET /guides/{guide_id}/permissions/users
   - ✅ DELETE /guides/{guide_id}/permissions/users/{user_id}
   - ⚠️ POST /guides/{guide_id}/permissions/invite (optional)

**Acceptance Criteria:**
- [ ] Guide owners can invite collaborators
- [ ] Collaborators can edit guides
- [ ] Permission levels enforced (view/edit/admin)
- [ ] Audit log tracks permission changes

---

#### Sprint 3: Custom Domain (2-3 weeks) 🟢
**Why Last:** Premium feature, not blocking core functionality

3. **Phase 6:** Custom Domain Integration (4 endpoints)
   - ✅ POST /guides/{guide_id}/domain
   - ✅ POST /guides/{guide_id}/domain/verify
   - ✅ DELETE /guides/{guide_id}/domain
   - ✅ GET /guides/by-domain/{domain}

**Acceptance Criteria:**
- [ ] Users can add custom domain
- [ ] DNS verification flow works
- [ ] SSL certificates auto-issued (Vercel)
- [ ] Next.js middleware handles routing
- [ ] Analytics track custom domain usage

---

## 🔧 TECHNICAL CONSIDERATIONS

### Workarounds for Missing Endpoints

#### 1. Publish Toggle (Missing: POST /publish)
**Current Solution:** Use PATCH endpoint
```typescript
// Frontend code
async function togglePublish(guideId: string, isPublished: boolean) {
  await fetch(`/api/v1/guides/${guideId}`, {
    method: 'PATCH',
    body: JSON.stringify({ is_published: isPublished })
  });
}
```
**Impact:** ✅ No blocker, just less semantic

---

#### 2. Public View (Missing: GET /public/guides/{slug})
**Current Solution:** None - MUST IMPLEMENT
**Impact:** 🔴 Blocks public sharing completely

**Temporary Workaround (Not Recommended):**
```typescript
// Use authenticated endpoint (requires login)
const guide = await fetch(`/api/v1/guides/${guideId}`, {
  headers: { Authorization: `Bearer ${token}` }
});
```
**Problem:** Defeats purpose of public guides (requires auth)

---

#### 3. Custom Domain Routing (Missing: GET /by-domain/{domain})
**Current Solution:** None - MUST IMPLEMENT if custom domain offered
**Impact:** 🟡 Only blocks custom domain feature

**Temporary Workaround:**
- Don't offer custom domain feature yet
- Use wordai.pro/guides/{slug} URLs only
- Add custom domain in Phase 6

---

### Database Schema Additions Needed

#### For Public View API (Phase 5)
✅ No schema changes needed - existing fields sufficient:
- `visibility: "public|private|unlisted"`
- `is_published: boolean`
- `slug: string` (unique per user)

---

#### For User Permissions (Phase 4)
✅ Already have collection: `guide_permissions`
```javascript
{
  permission_id: "perm_abc123",
  guide_id: "guide_abc123",
  user_id: "firebase_uid",
  permission_level: "view|edit|admin",
  granted_by: "owner_firebase_uid",
  granted_at: ISODate
}
```

---

#### For Custom Domain (Phase 6)
✅ Already have fields in `user_guides`:
```javascript
{
  custom_domain: "docs.company.com",
  custom_domain_verified: true,
  domain_verification: {
    type: "CNAME",
    name: "docs",
    value: "cname.vercel-dns.com"
  }
}
```

---

### New Collections Needed

#### For Analytics (Optional)
```javascript
// Collection: guide_analytics
{
  guide_id: "guide_abc123",
  date: ISODate("2025-11-15"),
  views: 1250,
  unique_visitors: 834,
  top_chapters: [
    { chapter_id: "ch1", views: 450 },
    { chapter_id: "ch2", views: 380 }
  ],
  referrers: [
    { source: "google.com", visits: 120 },
    { source: "twitter.com", visits: 45 }
  ]
}
```

**Priority:** LOW - Can add later for analytics dashboard

---

## 📊 SUMMARY

### Current Status
- ✅ **10/24 endpoints implemented** (42%)
- ✅ **Phase 1-3 complete** (50% of backend work)
- 🔴 **3 critical endpoints missing** (blocks public sharing)
- 🟡 **4 medium priority endpoints missing** (blocks collaboration)
- 🟢 **7 nice-to-have endpoints missing** (premium features)

### Critical Path to MVP
1. **Implement Phase 5 first** (Public View API) - 3 endpoints
   - Unblocks public guide sharing
   - Core value proposition
   - Estimated: 1 week

2. **Implement Phase 4 next** (User Permissions) - 4 endpoints
   - Enables collaboration
   - Team features
   - Estimated: 1-2 weeks

3. **Implement Phase 6 last** (Custom Domain) - 4 endpoints
   - Premium feature
   - Not blocking MVP
   - Estimated: 2-3 weeks

### Recommendation
**Start with Phase 5 (Public View API) immediately after Phase 4 completion.**

Reason: Frontend needs public endpoints to demonstrate the guide feature's main value (public documentation like Gitbook). Permissions and custom domain are enhancements, but public viewing is core functionality.

---

## 🎯 NEXT ACTION

### Option A: Implement Phase 5 (Public View API) 🔴
**Priority:** CRITICAL  
**Estimated Time:** 3-5 days  
**Blockers:** None  
**Value:** Unlocks public guide sharing (MVP feature)

**Deliverables:**
1. ✅ GET /api/v1/public/guides/{slug}
2. ✅ GET /api/v1/public/guides/{slug}/chapters/{chapter_slug}
3. ⚠️ POST /api/v1/public/guides/{slug}/views (optional)
4. ✅ Documentation (PHASE5_PUBLIC_VIEW_API.md)
5. ✅ Tests (test_public_view_api.py)

---

### Option B: Implement Phase 4 (User Permissions) 🟡
**Priority:** MEDIUM  
**Estimated Time:** 5-7 days  
**Blockers:** None  
**Value:** Enables collaboration features

**Deliverables:**
1. ✅ POST /api/v1/guides/{guide_id}/permissions/users
2. ✅ GET /api/v1/guides/{guide_id}/permissions/users
3. ✅ DELETE /api/v1/guides/{guide_id}/permissions/users/{user_id}
4. ⚠️ POST /api/v1/guides/{guide_id}/permissions/invite (optional)
5. ✅ Documentation (PHASE4_USER_PERMISSIONS_API.md)
6. ✅ Tests (test_permissions_api.py)

---

### Option C: Add Missing Helper Endpoint (Publish) ⚠️
**Priority:** LOW  
**Estimated Time:** 1 hour  
**Blockers:** None  
**Value:** Convenience (PATCH endpoint works)

**Deliverable:**
- ✅ POST /api/v1/guides/{guide_id}/publish

---

## 📝 CONCLUSION

**Current Progress:** 50% complete (Phases 1-3 done)

**Missing Critical Endpoints:** 3 endpoints blocking public guide feature

**Recommended Next Step:** 
🎯 **Implement Phase 5 (Public View API)** to unblock frontend public guide sharing

**Alternative:** 
Implement Phase 4 (User Permissions) first if collaboration features are higher priority than public sharing.

**Final MVP Order:**
1. ✅ Phase 1: Database (DONE)
2. ✅ Phase 2: Guide Management (DONE)
3. ✅ Phase 3: Chapter Management (DONE)
4. 🔴 **Phase 5: Public View API (NEXT)** ← Recommended
5. 🟡 Phase 4: User Permissions (AFTER Phase 5)
6. 🟢 Phase 6: Custom Domain (PREMIUM FEATURE)

---

**Document Version:** 1.0  
**Last Updated:** November 15, 2025  
**Status:** ✅ Ready for Phase 4/5 Implementation
