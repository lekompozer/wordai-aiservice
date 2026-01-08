# StudyHub - Lộ Trình Triển Khai Phase 1 & 2

## Tổng quan chiến lược

Phase 1 và Phase 2 được chia thành **6 Milestones** có thể triển khai độc lập:
- **Milestone 1.1**: Subject Core (Foundation)
- **Milestone 1.2**: Module & Content Basic
- **Milestone 1.3**: Enrollment & Progress
- **Milestone 2.1**: Advanced Content Integration
- **Milestone 2.2**: Monetization System
- **Milestone 2.3**: Analytics & Optimization

---

## PHASE 1: MVP CORE

### Milestone 1.1: Subject Core (Sprint 1 - 2 weeks)

**Mục tiêu**: Tạo nền tảng quản lý Subject cơ bản

**Database Schema**:
```
subjects:
  - _id: ObjectId
  - owner_id: ObjectId (ref: users)
  - title: String (required, max 200)
  - description: String (max 2000)
  - cover_image_url: String
  - status: String (draft/published/archived)
  - visibility: String (public/private)
  - created_at: DateTime
  - updated_at: DateTime
  - metadata:
      - total_modules: Number
      - total_learners: Number
      - avg_rating: Number
      - tags: Array<String>
```

**APIs - Total: 8**

1. **POST** `/api/studyhub/subjects`
   - Tạo Subject mới
   - Body: `{ title, description, visibility }`
   - Response: Subject object với status "draft"

2. **GET** `/api/studyhub/subjects/{subject_id}`
   - Lấy thông tin chi tiết Subject
   - Query: `include_stats=true/false`
   - Response: Subject + metadata

3. **PUT** `/api/studyhub/subjects/{subject_id}`
   - Cập nhật Subject
   - Body: `{ title?, description?, visibility? }`
   - Chỉ owner mới được update

4. **DELETE** `/api/studyhub/subjects/{subject_id}`
   - Soft delete (chuyển sang archived)
   - Kiểm tra: Nếu có learners → yêu cầu confirm
   - Response: Success message

5. **GET** `/api/studyhub/subjects`
   - Danh sách Subject với filter
   - Query: `status, visibility, owner_id, page, limit, sort`
   - Response: Paginated list

6. **GET** `/api/studyhub/subjects/owner/{user_id}`
   - Subject của owner cụ thể
   - Public subjects + owned subjects nếu là chính user
   - Response: List subjects

7. **POST** `/api/studyhub/subjects/{subject_id}/cover`
   - Upload cover image
   - Body: FormData với file
   - Xử lý: Upload to CDN, resize, optimize
   - Response: `{ cover_image_url }`

8. **POST** `/api/studyhub/subjects/{subject_id}/publish`
   - Publish subject (draft → published)
   - Validation: Phải có ít nhất 1 module
   - Response: Updated subject

**Dependencies**:
- User authentication service
- File upload service
- CDN storage

**Testing Priority**:
- CRUD operations
- Permission checks (owner-only actions)
- File upload validation

---

### Milestone 1.2: Module & Content Basic (Sprint 2 - 2 weeks)

**Mục tiêu**: Xây dựng cấu trúc Module và content cơ bản

**Database Schema**:
```
modules:
  - _id: ObjectId
  - subject_id: ObjectId (ref: subjects)
  - title: String (required)
  - description: String
  - order_index: Number
  - created_at: DateTime
  - updated_at: DateTime

module_contents:
  - _id: ObjectId
  - module_id: ObjectId (ref: modules)
  - content_type: String (document/link/video)
  - title: String
  - order_index: Number
  - data:
      - document_url: String (for PDF/A4)
      - link_url: String
      - video_url: String
      - duration_seconds: Number
  - created_at: DateTime
```

**APIs - Total: 8**

9. **POST** `/api/studyhub/subjects/{subject_id}/modules`
   - Tạo Module trong Subject
   - Body: `{ title, description }`
   - Auto assign order_index (last + 1)
   - Response: Module object

10. **GET** `/api/studyhub/subjects/{subject_id}/modules`
    - Lấy danh sách Modules
    - Sorted by order_index
    - Include content count
    - Response: Array of modules

11. **PUT** `/api/studyhub/modules/{module_id}`
    - Cập nhật Module
    - Body: `{ title?, description? }`
    - Kiểm tra owner permission
    - Response: Updated module

12. **DELETE** `/api/studyhub/modules/{module_id}`
    - Xóa Module
    - Cascade delete: Xóa tất cả contents
    - Re-index các modules còn lại
    - Response: Success

13. **POST** `/api/studyhub/modules/{module_id}/reorder`
    - Sắp xếp lại thứ tự modules
    - Body: `{ new_order_index }`
    - Update order của modules khác
    - Response: Updated module list

14. **POST** `/api/studyhub/modules/{module_id}/content`
    - Thêm content vào Module
    - Body: `{ content_type, title, data }`
    - Support: document, link, video
    - Response: Content object

15. **GET** `/api/studyhub/modules/{module_id}/content`
    - Lấy tất cả content của Module
    - Sorted by order_index
    - Response: Array of contents

16. **DELETE** `/api/studyhub/modules/{module_id}/content/{content_id}`
    - Xóa content
    - Re-index contents còn lại
    - Response: Success

**Business Logic**:
- Khi xóa Module → cascade xóa contents
- Order_index auto increment
- Validation content_type

**Testing Priority**:
- Module ordering
- Content CRUD
- Cascade deletes

---

### Milestone 1.3: Enrollment & Progress (Sprint 3 - 2 weeks)

**Mục tiêu**: Học viên đăng ký và tracking tiến độ

**Database Schema**:
```
enrollments:
  - _id: ObjectId
  - subject_id: ObjectId (ref: subjects)
  - user_id: ObjectId (ref: users)
  - enrolled_at: DateTime
  - status: String (active/completed/dropped)
  - progress:
      - completed_modules: Array<ObjectId>
      - completed_contents: Array<ObjectId>
      - last_accessed_module: ObjectId
      - last_accessed_at: DateTime
      - completion_percentage: Number
  - certificate_issued: Boolean
  - certificate_id: ObjectId (nullable)

learning_progress:
  - _id: ObjectId
  - user_id: ObjectId
  - subject_id: ObjectId
  - module_id: ObjectId
  - content_id: ObjectId (nullable)
  - status: String (not_started/in_progress/completed)
  - time_spent_seconds: Number
  - last_position: Object (video timestamp, page number, etc)
  - completed_at: DateTime (nullable)
  - updated_at: DateTime
```

**APIs - Total: 10**

17. **POST** `/api/studyhub/subjects/{subject_id}/enroll`
    - Đăng ký Subject
    - Validation: Subject must be published
    - Create enrollment record
    - Response: Enrollment object

18. **DELETE** `/api/studyhub/subjects/{subject_id}/enroll`
    - Hủy đăng ký (unenroll)
    - Update status → dropped
    - Keep progress data for analytics
    - Response: Success

19. **GET** `/api/studyhub/enrollments`
    - Danh sách Subject đã đăng ký
    - Query: `status=active/completed, page, limit`
    - Include progress percentage
    - Response: Paginated enrollments

20. **GET** `/api/studyhub/subjects/{subject_id}/progress`
    - Tiến độ học tập của user
    - Include: completed modules, contents, percentage
    - Next suggested content
    - Response: Progress object

21. **POST** `/api/studyhub/progress/mark-complete`
    - Đánh dấu hoàn thành module/content
    - Body: `{ module_id, content_id? }`
    - Update enrollment progress
    - Check if Subject completed
    - Response: Updated progress

22. **POST** `/api/studyhub/progress/mark-incomplete`
    - Đánh dấu chưa hoàn thành
    - Body: `{ module_id, content_id? }`
    - Rollback progress
    - Response: Updated progress

23. **PUT** `/api/studyhub/progress/last-position`
    - Lưu vị trí học hiện tại
    - Body: `{ module_id, content_id?, position }`
    - Use case: Video timestamp, PDF page
    - Response: Success

24. **GET** `/api/studyhub/subjects/{subject_id}/learners`
    - Danh sách học viên (Owner only)
    - Query: `status, sort_by=progress/enrolled_at, page, limit`
    - Include progress stats
    - Response: Paginated learners

25. **GET** `/api/studyhub/dashboard/overview`
    - Tổng quan Dashboard cá nhân
    - Stats: Total subjects, completion rate, streak
    - Recent activity
    - Response: Dashboard data

26. **GET** `/api/studyhub/dashboard/recent-activity`
    - Hoạt động học tập gần đây
    - Last 10 items: completed content, enrolled subjects
    - Response: Activity timeline

**Business Logic**:
- Auto calculate completion_percentage
- Trigger certificate khi 100%
- Track learning streak
- Update subject's total_learners

**Testing Priority**:
- Progress calculation accuracy
- Concurrent enrollments
- Performance với large datasets

---

### Milestone 1.4: Discovery & Search (Sprint 4 - 1 week)

**Mục tiêu**: Tìm kiếm và khám phá Subject

**APIs - Total: 4**

27. **GET** `/api/studyhub/subjects/recommended`
    - Subject đề xuất cho user
    - Algorithm: Based on enrolled subjects, tags, ratings
    - Query: `limit=10`
    - Response: Array of subjects

28. **GET** `/api/studyhub/subjects/trending`
    - Subject trending (nhiều người học nhất)
    - Time range: 7 days
    - Query: `limit=20`
    - Response: Array with stats

29. **GET** `/api/studyhub/search`
    - Tìm kiếm Subject
    - Query: `q (keyword), tags, owner_id, page, limit`
    - Full-text search: title, description
    - Response: Search results

30. **GET** `/api/studyhub/subjects/{subject_id}/stats`
    - Thống kê chi tiết Subject (Owner only)
    - Stats: Total learners, completion rate, avg time
    - Chart data: enrollments over time
    - Response: Stats object

**Backend Requirements**:
- Text search index on MongoDB
- Caching for trending/recommended
- Analytics tracking

---

## PHASE 2: CONTENT ECOSYSTEM

### Milestone 2.1: Advanced Content Integration (Sprint 5 - 3 weeks)

**Mục tiêu**: Tích hợp Books, Tests, Slides vào Module

**Database Schema**:
```
module_contents (Extended):
  - content_type: String (book/test/slides/document/link/video)
  - reference_id: ObjectId (Book/Test/Slide ID)
  - reference_type: String (book_online/test_online/ai_slide)
  - is_required: Boolean
  - passing_score: Number (for tests)
  - metadata:
      - book_chapters: Array (nếu là book)
      - test_duration: Number (nếu là test)
      - slide_count: Number (nếu là slides)
```

**APIs - Total: 14**

31. **POST** `/api/studyhub/modules/{module_id}/books`
    - Gán Book vào Module
    - Body: `{ book_id, is_required, selected_chapters? }`
    - Validation: Book exists và user có quyền
    - Response: Module content object

32. **DELETE** `/api/studyhub/modules/{module_id}/books/{book_id}`
    - Xóa Book khỏi Module
    - Soft delete: Keep progress data
    - Response: Success

33. **POST** `/api/studyhub/modules/{module_id}/tests`
    - Gán Test vào Module
    - Body: `{ test_id, is_required, passing_score }`
    - Validation: Test exists và có quyền
    - Response: Module content object

34. **DELETE** `/api/studyhub/modules/{module_id}/tests/{test_id}`
    - Xóa Test khỏi Module
    - Keep test results for analytics
    - Response: Success

35. **POST** `/api/studyhub/modules/{module_id}/slides`
    - Gán AI Slides vào Module
    - Body: `{ slide_id, is_required }`
    - Include subtitle + audio info
    - Response: Module content object

36. **DELETE** `/api/studyhub/modules/{module_id}/slides/{slide_id}`
    - Xóa Slides khỏi Module
    - Response: Success

37. **GET** `/api/studyhub/modules/{module_id}/content`
    - Lấy tất cả content (upgraded)
    - Include full metadata cho Books/Tests/Slides
    - Populate reference data
    - Response: Enhanced content list

38. **PUT** `/api/studyhub/modules/{module_id}/content/reorder`
    - Sắp xếp lại content
    - Body: `{ content_ids: Array<ObjectId> }`
    - Update order_index for all
    - Response: Reordered list

39. **GET** `/api/studyhub/content/{content_id}/preview`
    - Preview content trước khi enroll
    - Return: Metadata, thumbnail, sample
    - Free content: Full access
    - Response: Preview data

40. **GET** `/api/studyhub/books/available`
    - Books có thể gán vào Module
    - Filter: owned books + community books
    - Query: `q, page, limit`
    - Response: Available books

41. **GET** `/api/studyhub/tests/available`
    - Tests có thể gán vào Module
    - Filter: owned + community tests
    - Query: `q, type, page, limit`
    - Response: Available tests

42. **GET** `/api/studyhub/slides/available`
    - Slides có thể gán vào Module
    - Filter: owned AI slides
    - Query: `q, page, limit`
    - Response: Available slides

43. **PUT** `/api/studyhub/content/{content_id}/requirements`
    - Cập nhật yêu cầu content
    - Body: `{ is_required, passing_score?, min_time_spent? }`
    - Response: Updated content

44. **GET** `/api/studyhub/subjects/{subject_id}/content-summary`
    - Tổng hợp content trong Subject
    - Group by type: books, tests, slides, documents
    - Response: Content summary

**Integration Points**:
- Books Online API: `/api/books/{book_id}`
- Tests Online API: `/api/tests/{test_id}`
- AI Slides API: `/api/slides/{slide_id}`

**Business Logic**:
- Validate user has access to Book/Test/Slide
- Track completion cho từng content type
- Required content must be completed

**Testing Priority**:
- Cross-service integration
- Permission validation
- Content reference integrity

---

### Milestone 2.2: Monetization System (Sprint 6 - 2 weeks)

**Mục tiêu**: Thu phí Subject bằng Point, revenue sharing

**Database Schema**:
```
subject_pricing:
  - _id: ObjectId
  - subject_id: ObjectId (ref: subjects)
  - price_points: Number
  - is_free: Boolean
  - discount_active: Boolean
  - discount:
      - code: String
      - percentage: Number
      - valid_from: DateTime
      - valid_to: DateTime
      - usage_limit: Number
      - used_count: Number
  - created_at: DateTime
  - updated_at: DateTime

subject_purchases:
  - _id: ObjectId
  - subject_id: ObjectId
  - buyer_id: ObjectId
  - seller_id: ObjectId (subject owner)
  - price_paid: Number
  - discount_code: String (nullable)
  - platform_fee: Number (20%)
  - seller_revenue: Number (80%)
  - transaction_id: String
  - purchased_at: DateTime
  - status: String (completed/refunded)

revenue_records:
  - _id: ObjectId
  - user_id: ObjectId
  - transaction_type: String (sale/refund/withdrawal)
  - amount: Number
  - subject_id: ObjectId
  - purchase_id: ObjectId
  - created_at: DateTime
```

**APIs - Total: 10**

45. **PUT** `/api/studyhub/subjects/{subject_id}/pricing`
    - Thiết lập giá Subject
    - Body: `{ price_points, is_free }`
    - Validation: Owner only
    - Response: Pricing object

46. **POST** `/api/studyhub/subjects/{subject_id}/purchase`
    - Mua Subject bằng Points
    - Body: `{ discount_code? }`
    - Process:
      1. Check user points
      2. Apply discount
      3. Deduct points
      4. Calculate revenue share (80/20)
      5. Create enrollment
    - Response: Purchase + Enrollment

47. **GET** `/api/studyhub/purchases/history`
    - Lịch sử mua Subject
    - Query: `page, limit, sort=newest`
    - Response: Purchase history

48. **GET** `/api/studyhub/revenue/owner`
    - Doanh thu của Owner
    - Stats: Total revenue, pending, withdrawn
    - Filter by date range
    - Response: Revenue summary

49. **GET** `/api/studyhub/revenue/transactions`
    - Chi tiết giao dịch
    - Query: `type, subject_id, page, limit`
    - Include: sales, refunds
    - Response: Transaction list

50. **POST** `/api/studyhub/subjects/{subject_id}/discount`
    - Tạo mã giảm giá
    - Body: `{ code, percentage, valid_from, valid_to, usage_limit }`
    - Response: Discount object

51. **DELETE** `/api/studyhub/discounts/{discount_id}`
    - Xóa/Vô hiệu hóa discount
    - Response: Success

52. **POST** `/api/studyhub/subjects/{subject_id}/free-access`
    - Cấp quyền miễn phí cho user
    - Body: `{ user_ids: Array<ObjectId> }`
    - Use case: Scholarship, promotion
    - Response: Success with granted users

53. **GET** `/api/studyhub/subjects/{subject_id}/sales-stats`
    - Thống kê bán hàng (Owner only)
    - Stats: Total sales, revenue chart, top buyers
    - Response: Sales analytics

54. **POST** `/api/studyhub/refund/{purchase_id}`
    - Hoàn tiền (Admin/Owner only)
    - Process:
      1. Refund points to buyer
      2. Deduct from seller revenue
      3. Remove enrollment
    - Response: Refund confirmation

**Payment Flow**:
1. User clicks "Buy Subject"
2. Check points balance
3. Apply discount if provided
4. Deduct points from user
5. Add 80% to seller pending revenue
6. Add 20% to platform revenue
7. Create enrollment record
8. Send notifications

**Business Logic**:
- Revenue share: 80% seller, 20% platform
- Discount validation
- Refund window: 7 days
- Point transaction atomic

**Testing Priority**:
- Payment transaction integrity
- Revenue calculation
- Concurrent purchases
- Refund flow

---

### Milestone 2.3: Analytics & Optimization (Sprint 7 - 1 week)

**Mục tiêu**: Analytics cho Owner và Platform

**APIs - Total: 4**

55. **GET** `/api/studyhub/analytics/content-performance`
    - Hiệu quả từng content
    - Metrics: Completion rate, avg time, dropoff points
    - Query: `subject_id, date_range`
    - Response: Performance data

56. **GET** `/api/studyhub/analytics/learner-engagement`
    - Mức độ tương tác học viên
    - Metrics: Active days, streak, session duration
    - Segment by: subject, module
    - Response: Engagement metrics

57. **GET** `/api/studyhub/analytics/revenue-report`
    - Báo cáo doanh thu chi tiết
    - Break down: By subject, by month, by source
    - Export format: JSON/CSV
    - Response: Revenue report

58. **GET** `/api/studyhub/dashboard/stats`
    - Thống kê Dashboard cá nhân
    - Stats: Learning time, points earned, certificates
    - Response: Personal stats

**Analytics Events to Track**:
- Content viewed
- Content completed
- Time spent per content
- Drop-off points
- Purchase events
- Enrollment events

---

## TỔNG KẾT PHASE 1 & 2

### Số lượng APIs theo Milestone:

| Milestone | Sprint | APIs | Features |
|-----------|--------|------|----------|
| **1.1** Subject Core | 1 | 8 | CRUD Subject, Cover upload |
| **1.2** Module & Content | 2 | 8 | Module management, Basic content |
| **1.3** Enrollment & Progress | 3 | 10 | Enroll, Progress tracking |
| **1.4** Discovery | 4 | 4 | Search, Recommendations |
| **2.1** Content Integration | 5 | 14 | Books, Tests, Slides |
| **2.2** Monetization | 6 | 10 | Pricing, Purchase, Revenue |
| **2.3** Analytics | 7 | 4 | Performance analytics |
| **TỔNG** | 7 sprints | **58 APIs** | - |

### Timeline:
- **Phase 1**: 7 tuần (4 sprints)
- **Phase 2**: 6 tuần (3 sprints)
- **Tổng**: ~13 tuần (3.5 tháng)

### Thứ tự ưu tiên triển khai:

**MUST HAVE (Launch blockers)**:
1. Subject Core (M1.1)
2. Module & Content (M1.2)
3. Enrollment & Progress (M1.3)

**SHOULD HAVE (MVP complete)**:
4. Discovery (M1.4)
5. Content Integration (M2.1)

**NICE TO HAVE (Monetization ready)**:
6. Monetization (M2.2)
7. Analytics (M2.3)

### Dependencies Map:

```
M1.1 (Subject Core)
  ↓
M1.2 (Module & Content)
  ↓
M1.3 (Enrollment & Progress)
  ↓
M1.4 (Discovery) ← Can be parallel with M2.1
  ↓
M2.1 (Content Integration)
  ↓
M2.2 (Monetization)
  ↓
M2.3 (Analytics)
```

### Parallel Development Opportunities:

**After M1.3 completes**:
- M1.4 (Discovery) + M2.1 (Content Integration) có thể chạy song song
- Analytics (M2.3) có thể bắt đầu prototype từ M1.3

**Team Structure Suggestion**:
- **Team A (Backend)**: API development
- **Team B (Frontend)**: UI/UX implementation
- **Team C (Integration)**: External service integration

### Risk & Mitigation:

**High Risk**:
1. Content Integration (M2.1) - Phụ thuộc external APIs
   - Mitigation: Mock services, API contracts trước

2. Monetization (M2.2) - Point transaction critical
   - Mitigation: Extensive testing, rollback plan

**Medium Risk**:
1. Progress Calculation - Performance với large datasets
   - Mitigation: Indexing, caching strategy

2. Search & Discovery - Accuracy & performance
   - Mitigation: Elasticsearch or MongoDB Atlas Search

### Next Steps:

1. **Tech Stack Finalization**
   - Choose: MongoDB Atlas Search vs Elasticsearch
   - CDN provider for media
   - Real-time updates: WebSocket or Polling

2. **API Contract Definition**
   - OpenAPI/Swagger specs
   - Error code standards
   - Response format conventions

3. **Database Design Review**
   - Indexing strategy
   - Sharding plan (nếu cần)
   - Backup strategy

4. **External Integration Planning**
   - Books Online API documentation
   - Tests Online API documentation
   - AI Slides API documentation
   - Point system integration

---

**Ngày tạo**: January 8, 2026
**Phiên bản**: 1.0
**Status**: Ready for Development Planning
**Next**: API Detailed Specification Document
