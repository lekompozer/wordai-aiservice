# StudyHub - Phân Tích Phase & API Requirements

## PHASE 1: MVP CORE (Quý 1)

### Mục tiêu
Nền tảng học tập cơ bản với cấu trúc Subject đơn giản

### Tính năng chi tiết

#### 1.1. Quản lý Subject (Môn học)
- Tạo/Chỉnh sửa Subject với tiêu đề, mô tả, hình ảnh cover
- Chia Subject thành Modules/Chapters
- Thêm học liệu cơ bản (File từ PDF upload - Document A4-Slides)
- Xóa/Ẩn Subject
- Quản lý quyền truy cập (Public/Private)

#### 1.2. Đăng ký & Theo dõi
- Học viên đăng ký Subject
- Hủy đăng ký
- Hiển thị progress bar cơ bản
- Đánh dấu bài đã học (complete/incomplete)
- Lưu vị trí học gần nhất

#### 1.3. Dashboard cá nhân
- Danh sách Subject đang học
- Tiến độ tổng quan
- Lịch sử học tập gần đây
- Subject được đề xuất

### API Requirements - Phase 1: **~25-30 APIs**

#### Subject Management (8-10 APIs)
1. POST `/api/studyhub/subjects` - Tạo Subject mới
2. GET `/api/studyhub/subjects/{subject_id}` - Lấy thông tin Subject
3. PUT `/api/studyhub/subjects/{subject_id}` - Cập nhật Subject
4. DELETE `/api/studyhub/subjects/{subject_id}` - Xóa Subject
5. GET `/api/studyhub/subjects` - Danh sách Subject (filter, search, pagination)
6. GET `/api/studyhub/subjects/owner/{user_id}` - Subject của Owner
7. POST `/api/studyhub/subjects/{subject_id}/publish` - Publish Subject
8. POST `/api/studyhub/subjects/{subject_id}/unpublish` - Unpublish Subject
9. POST `/api/studyhub/subjects/{subject_id}/cover` - Upload cover image
10. GET `/api/studyhub/subjects/{subject_id}/stats` - Thống kê Subject

#### Module/Chapter Management (5-6 APIs)
11. POST `/api/studyhub/subjects/{subject_id}/modules` - Tạo Module
12. PUT `/api/studyhub/modules/{module_id}` - Cập nhật Module
13. DELETE `/api/studyhub/modules/{module_id}` - Xóa Module
14. POST `/api/studyhub/modules/{module_id}/reorder` - Sắp xếp lại thứ tự
15. GET `/api/studyhub/subjects/{subject_id}/modules` - Lấy danh sách Modules
16. POST `/api/studyhub/modules/{module_id}/content` - Thêm content vào Module

#### Enrollment & Progress (6-8 APIs)
17. POST `/api/studyhub/subjects/{subject_id}/enroll` - Đăng ký Subject
18. DELETE `/api/studyhub/subjects/{subject_id}/enroll` - Hủy đăng ký
19. GET `/api/studyhub/enrollments` - Danh sách Subject đã đăng ký
20. GET `/api/studyhub/subjects/{subject_id}/progress` - Tiến độ học tập
21. POST `/api/studyhub/progress/mark-complete` - Đánh dấu hoàn thành
22. POST `/api/studyhub/progress/mark-incomplete` - Đánh dấu chưa hoàn thành
23. PUT `/api/studyhub/progress/last-position` - Lưu vị trí học
24. GET `/api/studyhub/subjects/{subject_id}/learners` - Danh sách học viên

#### Dashboard & Discovery (5-6 APIs)
25. GET `/api/studyhub/dashboard/overview` - Tổng quan Dashboard
26. GET `/api/studyhub/dashboard/recent-activity` - Hoạt động gần đây
27. GET `/api/studyhub/subjects/recommended` - Subject đề xuất
28. GET `/api/studyhub/subjects/trending` - Subject trending
29. GET `/api/studyhub/dashboard/stats` - Thống kê cá nhân
30. GET `/api/studyhub/search` - Tìm kiếm Subject

---

## PHASE 2: CONTENT ECOSYSTEM (Quý 2)

### Mục tiêu
Tích hợp đầy đủ hệ sinh thái nội dung WordAI

### Tính năng chi tiết

#### 2.1. Tích hợp học liệu nâng cao
- Gán Books Online từ kho sách cá nhân/community
- Gán Tests Online từ hệ thống kiểm tra (Private/Community)
- Tích hợp AI Slides với subtitle + audio
- Quản lý thứ tự và cấu trúc học liệu hỗn hợp
- Preview và metadata cho từng loại học liệu

#### 2.2. Monetization v1
- Thiết lập giá Subject bằng Point
- Hệ thống thanh toán cơ bản
- Revenue share 80/20 (Owner/Platform)
- Lịch sử giao dịch
- Thống kê doanh thu cho Owner
- Quản lý giá khuyến mãi

### API Requirements - Phase 2: **~20-25 APIs**

#### Content Integration (10-12 APIs)
31. POST `/api/studyhub/modules/{module_id}/books` - Gán Book vào Module
32. DELETE `/api/studyhub/modules/{module_id}/books/{book_id}` - Xóa Book
33. POST `/api/studyhub/modules/{module_id}/tests` - Gán Test vào Module
34. DELETE `/api/studyhub/modules/{module_id}/tests/{test_id}` - Xóa Test
35. POST `/api/studyhub/modules/{module_id}/slides` - Gán Slide vào Module
36. DELETE `/api/studyhub/modules/{module_id}/slides/{slide_id}` - Xóa Slide
37. GET `/api/studyhub/modules/{module_id}/content` - Lấy tất cả content
38. PUT `/api/studyhub/modules/{module_id}/content/reorder` - Sắp xếp content
39. GET `/api/studyhub/content/{content_id}/preview` - Preview content
40. GET `/api/studyhub/books/available` - Books có thể gán
41. GET `/api/studyhub/tests/available` - Tests có thể gán
42. GET `/api/studyhub/slides/available` - Slides có thể gán

#### Monetization (8-10 APIs)
43. PUT `/api/studyhub/subjects/{subject_id}/pricing` - Thiết lập giá
44. POST `/api/studyhub/subjects/{subject_id}/purchase` - Mua Subject
45. GET `/api/studyhub/purchases/history` - Lịch sử mua
46. GET `/api/studyhub/revenue/owner` - Doanh thu của Owner
47. GET `/api/studyhub/revenue/transactions` - Chi tiết giao dịch
48. POST `/api/studyhub/subjects/{subject_id}/discount` - Tạo mã giảm giá
49. DELETE `/api/studyhub/discounts/{discount_id}` - Xóa giảm giá
50. POST `/api/studyhub/subjects/{subject_id}/free-access` - Cấp quyền free
51. GET `/api/studyhub/subjects/{subject_id}/sales-stats` - Thống kê bán hàng
52. POST `/api/studyhub/refund/{purchase_id}` - Hoàn tiền

#### Analytics (2-3 APIs)
53. GET `/api/studyhub/analytics/content-performance` - Hiệu quả content
54. GET `/api/studyhub/analytics/learner-engagement` - Engagement học viên
55. GET `/api/studyhub/analytics/revenue-report` - Báo cáo doanh thu

---

## PHASE 3: COMMUNITY & ENGAGEMENT (Quý 3)

### Mục tiêu
Xây dựng cộng đồng học tập tương tác

### Tính năng chi tiết

#### 3.1. Hệ thống cộng đồng
- Forum thảo luận theo Module/Subject
- Hệ thống upvote, downvote, bình luận
- Q&A với Owner (marked as answered)
- Tag và tìm kiếm discussions
- Pin important posts
- Moderation tools

#### 3.2. Study Groups
- Tạo nhóm học tập công khai/riêng tư
- Mời thành viên, approve requests
- Chat nhóm real-time
- Chia sẻ tài liệu trong nhóm
- Đặt mục tiêu học tập chung
- Theo dõi tiến độ nhóm

#### 3.3. Gamification & Recognition
- Hệ thống Badge thành tích
- Leaderboards (Subject, Platform)
- Points & Streaks
- Certificate hoàn thành Subject
- Achievement milestones

#### 3.4. Thông báo thông minh
- Nhắc nhở học tập (scheduled)
- Cập nhật từ Owner (new content, announcements)
- Hoạt động nhóm (mentions, replies)
- Achievement notifications
- Deadline reminders

### API Requirements - Phase 3: **~35-40 APIs**

#### Forum & Discussions (12-15 APIs)
56. POST `/api/studyhub/subjects/{subject_id}/discussions` - Tạo discussion
57. GET `/api/studyhub/subjects/{subject_id}/discussions` - Danh sách discussions
58. GET `/api/studyhub/discussions/{discussion_id}` - Chi tiết discussion
59. PUT `/api/studyhub/discussions/{discussion_id}` - Cập nhật discussion
60. DELETE `/api/studyhub/discussions/{discussion_id}` - Xóa discussion
61. POST `/api/studyhub/discussions/{discussion_id}/replies` - Reply
62. POST `/api/studyhub/discussions/{discussion_id}/upvote` - Upvote
63. DELETE `/api/studyhub/discussions/{discussion_id}/upvote` - Remove upvote
64. POST `/api/studyhub/discussions/{discussion_id}/pin` - Pin discussion
65. POST `/api/studyhub/discussions/{discussion_id}/mark-answered` - Mark as answered
66. GET `/api/studyhub/discussions/search` - Tìm kiếm discussions
67. POST `/api/studyhub/discussions/{discussion_id}/report` - Báo cáo vi phạm
68. POST `/api/studyhub/discussions/{discussion_id}/moderate` - Moderation
69. GET `/api/studyhub/discussions/my-posts` - Bài viết của tôi
70. GET `/api/studyhub/discussions/following` - Discussions đang theo dõi

#### Study Groups (10-12 APIs)
71. POST `/api/studyhub/groups` - Tạo Study Group
72. GET `/api/studyhub/groups/{group_id}` - Chi tiết Group
73. PUT `/api/studyhub/groups/{group_id}` - Cập nhật Group
74. DELETE `/api/studyhub/groups/{group_id}` - Xóa Group
75. POST `/api/studyhub/groups/{group_id}/join` - Tham gia Group
76. DELETE `/api/studyhub/groups/{group_id}/leave` - Rời Group
77. POST `/api/studyhub/groups/{group_id}/invite` - Mời thành viên
78. POST `/api/studyhub/groups/{group_id}/approve` - Duyệt yêu cầu
79. POST `/api/studyhub/groups/{group_id}/messages` - Gửi message
80. GET `/api/studyhub/groups/{group_id}/messages` - Lấy messages
81. POST `/api/studyhub/groups/{group_id}/goals` - Đặt mục tiêu
82. GET `/api/studyhub/groups/{group_id}/progress` - Tiến độ nhóm

#### Gamification (8-10 APIs)
83. GET `/api/studyhub/badges` - Danh sách Badges
84. GET `/api/studyhub/users/{user_id}/badges` - Badges của user
85. GET `/api/studyhub/leaderboard/subject/{subject_id}` - Leaderboard Subject
86. GET `/api/studyhub/leaderboard/platform` - Leaderboard Platform
87. GET `/api/studyhub/users/{user_id}/achievements` - Achievements
88. POST `/api/studyhub/subjects/{subject_id}/certificate` - Tạo Certificate
89. GET `/api/studyhub/certificates/{certificate_id}` - Xem Certificate
90. GET `/api/studyhub/users/{user_id}/certificates` - Certificates của user
91. GET `/api/studyhub/users/{user_id}/streaks` - Streaks
92. GET `/api/studyhub/users/{user_id}/points-history` - Lịch sử Points

#### Notifications (5-6 APIs)
93. GET `/api/studyhub/notifications` - Danh sách thông báo
94. PUT `/api/studyhub/notifications/{notification_id}/read` - Đánh dấu đã đọc
95. PUT `/api/studyhub/notifications/read-all` - Đánh dấu tất cả đã đọc
96. DELETE `/api/studyhub/notifications/{notification_id}` - Xóa thông báo
97. PUT `/api/studyhub/notification-settings` - Cài đặt thông báo
98. GET `/api/studyhub/notification-settings` - Lấy cài đặt thông báo

---

## PHASE 4: PROGRAMS & INSTITUTIONS (Quý 4)

### Mục tiêu
Mở rộng thành nền tảng giáo dục đa cấp độ

### Tính năng chi tiết

#### 4.1. Program Management
- Tạo chương trình học (Program) gồm nhiều Subject
- Cấu trúc tiên quyết (prerequisite chains)
- Lộ trình học tập định sẵn (learning paths)
- Track progress across multiple Subjects
- Program-level certificates
- Flexible vs. Sequential completion

#### 4.2. University/Organization Portal
- Trang riêng cho tổ chức giáo dục
- Quản lý sinh viên theo khóa/class
- Bulk enrollment
- Role-based access (Admin, Instructor, TA, Student)
- Organization branding
- Báo cáo tổng hợp tổ chức

#### 4.3. Advanced Certification
- Certificate có xác minh (blockchain/verifiable)
- Cấp độ chứng chỉ (Basic, Advanced, Expert)
- Integration với LinkedIn/CV platforms
- Public certificate verification portal
- Certificate templates customization

#### 4.4. Corporate Training Features
- Bulk enrollment cho teams
- Progress tracking for managers
- Custom reporting & analytics
- Compliance tracking
- Department/Team management
- Learning path assignment

### API Requirements - Phase 4: **~40-45 APIs**

#### Program Management (12-15 APIs)
99. POST `/api/studyhub/programs` - Tạo Program
100. GET `/api/studyhub/programs/{program_id}` - Chi tiết Program
101. PUT `/api/studyhub/programs/{program_id}` - Cập nhật Program
102. DELETE `/api/studyhub/programs/{program_id}` - Xóa Program
103. POST `/api/studyhub/programs/{program_id}/subjects` - Thêm Subject vào Program
104. DELETE `/api/studyhub/programs/{program_id}/subjects/{subject_id}` - Xóa Subject
105. PUT `/api/studyhub/programs/{program_id}/prerequisites` - Thiết lập prerequisites
106. GET `/api/studyhub/programs/{program_id}/learning-path` - Lộ trình học
107. POST `/api/studyhub/programs/{program_id}/enroll` - Đăng ký Program
108. GET `/api/studyhub/programs/{program_id}/progress` - Tiến độ Program
109. GET `/api/studyhub/programs` - Danh sách Programs
110. POST `/api/studyhub/programs/{program_id}/certificate` - Cấp Certificate Program
111. GET `/api/studyhub/programs/{program_id}/stats` - Thống kê Program
112. PUT `/api/studyhub/programs/{program_id}/pricing` - Thiết lập giá Program
113. POST `/api/studyhub/programs/{program_id}/publish` - Publish Program

#### Organization Portal (12-15 APIs)
114. POST `/api/studyhub/organizations` - Tạo Organization
115. GET `/api/studyhub/organizations/{org_id}` - Chi tiết Organization
116. PUT `/api/studyhub/organizations/{org_id}` - Cập nhật Organization
117. DELETE `/api/studyhub/organizations/{org_id}` - Xóa Organization
118. POST `/api/studyhub/organizations/{org_id}/members` - Thêm member
119. DELETE `/api/studyhub/organizations/{org_id}/members/{user_id}` - Xóa member
120. PUT `/api/studyhub/organizations/{org_id}/members/{user_id}/role` - Thay đổi role
121. POST `/api/studyhub/organizations/{org_id}/bulk-enroll` - Bulk enrollment
122. GET `/api/studyhub/organizations/{org_id}/students` - Danh sách sinh viên
123. POST `/api/studyhub/organizations/{org_id}/classes` - Tạo Class/Cohort
124. GET `/api/studyhub/organizations/{org_id}/classes` - Danh sách Classes
125. POST `/api/studyhub/organizations/{org_id}/branding` - Cập nhật branding
126. GET `/api/studyhub/organizations/{org_id}/analytics` - Analytics tổ chức
127. POST `/api/studyhub/organizations/{org_id}/reports` - Tạo báo cáo
128. GET `/api/studyhub/organizations/{org_id}/reports/{report_id}` - Xem báo cáo

#### Advanced Certification (8-10 APIs)
129. POST `/api/studyhub/certificates/issue` - Cấp Certificate
130. GET `/api/studyhub/certificates/{certificate_id}/verify` - Xác minh Certificate
131. GET `/api/studyhub/certificates/verify/{verification_code}` - Verify bằng code
132. POST `/api/studyhub/certificates/{certificate_id}/share-linkedin` - Share LinkedIn
133. GET `/api/studyhub/certificate-templates` - Danh sách templates
134. POST `/api/studyhub/certificate-templates` - Tạo template
135. PUT `/api/studyhub/certificate-templates/{template_id}` - Cập nhật template
136. GET `/api/studyhub/certificates/public/{certificate_id}` - Public verification
137. POST `/api/studyhub/certificates/{certificate_id}/revoke` - Thu hồi Certificate
138. GET `/api/studyhub/users/{user_id}/credentials` - Tất cả credentials

#### Corporate Training (8-10 APIs)
139. POST `/api/studyhub/organizations/{org_id}/teams` - Tạo Team
140. GET `/api/studyhub/organizations/{org_id}/teams` - Danh sách Teams
141. POST `/api/studyhub/teams/{team_id}/assign-learning-path` - Assign learning path
142. GET `/api/studyhub/teams/{team_id}/progress` - Tiến độ Team
143. GET `/api/studyhub/teams/{team_id}/reports` - Báo cáo Team
144. POST `/api/studyhub/organizations/{org_id}/compliance` - Thiết lập compliance
145. GET `/api/studyhub/organizations/{org_id}/compliance-status` - Tình trạng compliance
146. GET `/api/studyhub/managers/{manager_id}/team-overview` - Overview cho Manager
147. POST `/api/studyhub/organizations/{org_id}/custom-reports` - Custom reports
148. GET `/api/studyhub/organizations/{org_id}/export-data` - Export data

---

## TỔNG KẾT

### Tổng số API theo Phase:

| Phase | Số lượng API | Loại chính |
|-------|-------------|-----------|
| **Phase 1** | 25-30 | Subject, Module, Enrollment, Dashboard |
| **Phase 2** | 20-25 | Content Integration, Monetization, Analytics |
| **Phase 3** | 35-40 | Forum, Groups, Gamification, Notifications |
| **Phase 4** | 40-45 | Programs, Organizations, Certificates, Corporate |
| **TỔNG** | **~120-140 APIs** | |

### Phân loại theo Category:

#### Core Learning (Phase 1-2): ~50 APIs
- Subject Management
- Module/Content Management
- Enrollment & Progress
- Content Integration
- Monetization

#### Community & Social (Phase 3): ~35 APIs
- Discussions & Forum
- Study Groups
- Gamification
- Notifications

#### Enterprise & Advanced (Phase 4): ~40 APIs
- Program Management
- Organization Portal
- Certification
- Corporate Training

### Dependencies & Integration Points:

1. **Existing WordAI Services**:
   - Books Online API
   - Tests Online API
   - AI Slides API
   - Payment/Points API
   - User Management API

2. **External Integrations**:
   - LinkedIn Share API
   - Certificate Verification (Blockchain)
   - Real-time Chat (WebSocket)
   - Email/Push Notifications

3. **Infrastructure**:
   - File Storage (Cover images, Documents)
   - CDN (Content delivery)
   - Redis (Caching, Real-time)
   - MongoDB (Primary database)

### Ưu tiên phát triển:

**Critical Path (MVP First)**:
- Phase 1 → Phase 2 → Phase 3 → Phase 4

**Parallel Development Opportunities**:
- Monetization (Phase 2) có thể develop song song với Phase 1
- Gamification (Phase 3) có thể bắt đầu sau khi có basic progress tracking
- Certificate system có thể prototype sớm cho feedback

### Lưu ý kỹ thuật:

1. **Authentication & Authorization**:
   - Tất cả APIs cần JWT authentication
   - Role-based permissions (Owner, Learner, Admin, Instructor)
   - Organization-level access control

2. **Rate Limiting**:
   - Public APIs: 100 req/min
   - Authenticated: 1000 req/min
   - Organization: Custom limits

3. **Data Privacy**:
   - GDPR compliance
   - User data export
   - Data deletion policies

4. **Performance**:
   - Pagination for list endpoints
   - Caching strategies
   - Lazy loading for content

---

**Ngày tạo**: January 8, 2026
**Phiên bản**: 1.0
**Trạng thái**: Draft - Chờ phê duyệt & phân tích chi tiết API
