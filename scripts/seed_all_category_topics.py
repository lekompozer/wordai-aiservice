"""
Seed all Learning System topics for all categories
Based on category_topic.md documentation
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.database.db_manager import DBManager

DRY_RUN = False  # Set to True to preview changes without executing


def seed_topics():
    """Seed all topics for Python, JavaScript, HTML/CSS, SQL, Software Architecture, and AI"""

    print("=" * 80)
    print("SEEDING ALL CATEGORY TOPICS")
    print("=" * 80)

    if DRY_RUN:
        print("\n⚠️  DRY RUN MODE - No changes will be made")
        print("Set DRY_RUN = False to execute seeding\n")

    db_manager = DBManager()
    db = db_manager.db

    # All topics organized by category
    all_topics = {
        "python": [
            # Existing Lớp 10-12 topics (1-17) already exist, add practical topics
            {
                "id": "python-thuc-chien-automation",
                "name": "Thực chiến - Tự động hóa (Automation)",
                "level": "practical",
                "grade": "university",
                "order": 18,
            },
            {
                "id": "python-thuc-chien-phan-tich-du-lieu",
                "name": "Thực chiến - Phân tích dữ liệu (Pandas/Numpy)",
                "level": "practical",
                "grade": "university",
                "order": 19,
            },
            {
                "id": "python-thuc-chien-web-backend",
                "name": "Thực chiến - Web Backend (Flask/FastAPI)",
                "level": "practical",
                "grade": "university",
                "order": 20,
            },
            {
                "id": "python-thuc-chien-crawl-data",
                "name": "Thực chiến - Cào dữ liệu Web (Scrapy/Selenium)",
                "level": "practical",
                "grade": "university",
                "order": 21,
            },
        ],
        "javascript": [
            # JavaScript Core (1-10)
            {
                "id": "js-core-01",
                "name": "JS 01: Nhập môn & Console",
                "level": "beginner",
                "grade": "highschool",
                "order": 1,
            },
            {
                "id": "js-core-02",
                "name": "JS 02: Biến (Let/Const) & Kiểu dữ liệu",
                "level": "beginner",
                "grade": "highschool",
                "order": 2,
            },
            {
                "id": "js-core-03",
                "name": "JS 03: Toán tử & Ép kiểu",
                "level": "beginner",
                "grade": "highschool",
                "order": 3,
            },
            {
                "id": "js-core-04",
                "name": "JS 04: Cấu trúc điều kiện (If/Switch)",
                "level": "beginner",
                "grade": "highschool",
                "order": 4,
            },
            {
                "id": "js-core-05",
                "name": "JS 05: Các loại Vòng lặp",
                "level": "beginner",
                "grade": "highschool",
                "order": 5,
            },
            {
                "id": "js-core-06",
                "name": "JS 06: Hàm (Function) cơ bản",
                "level": "beginner",
                "grade": "highschool",
                "order": 6,
            },
            {
                "id": "js-core-07",
                "name": "JS 07: Làm việc với Chuỗi (String)",
                "level": "beginner",
                "grade": "highschool",
                "order": 7,
            },
            {
                "id": "js-core-08",
                "name": "JS 08: Mảng (Array) & Các phương thức cơ bản",
                "level": "beginner",
                "grade": "highschool",
                "order": 8,
            },
            {
                "id": "js-core-09",
                "name": "JS 09: Đối tượng (Object) căn bản",
                "level": "beginner",
                "grade": "highschool",
                "order": 9,
            },
            {
                "id": "js-core-10",
                "name": "JS 10: DOM & Sự kiện (Click, Change)",
                "level": "intermediate",
                "grade": "highschool",
                "order": 10,
            },
            # JavaScript Advanced & ES6+ (11-20)
            {
                "id": "js-adv-01",
                "name": "JS Adv: Scope, Hoisting & Closure",
                "level": "advanced",
                "grade": "university",
                "order": 11,
            },
            {
                "id": "js-adv-02",
                "name": "JS Adv: Từ khóa this & Bind/Call/Apply",
                "level": "advanced",
                "grade": "university",
                "order": 12,
            },
            {
                "id": "js-adv-03",
                "name": "JS Adv: ES6+ Arrow Function & Template String",
                "level": "advanced",
                "grade": "university",
                "order": 13,
            },
            {
                "id": "js-adv-04",
                "name": "JS Adv: Destructuring & Spread Operator",
                "level": "advanced",
                "grade": "university",
                "order": 14,
            },
            {
                "id": "js-adv-05",
                "name": "JS Adv: Array Methods nâng cao (Map/Filter/Reduce)",
                "level": "advanced",
                "grade": "university",
                "order": 15,
            },
            {
                "id": "js-adv-06",
                "name": "JS Adv: Callback Hell & Promise",
                "level": "advanced",
                "grade": "university",
                "order": 16,
            },
            {
                "id": "js-adv-07",
                "name": "JS Adv: Async / Await (Xử lý bất đồng bộ)",
                "level": "advanced",
                "grade": "university",
                "order": 17,
            },
            {
                "id": "js-adv-08",
                "name": "JS Adv: Modules (Import/Export)",
                "level": "advanced",
                "grade": "university",
                "order": 18,
            },
            {
                "id": "js-adv-09",
                "name": "JS Adv: LocalStorage & SessionStorage",
                "level": "advanced",
                "grade": "university",
                "order": 19,
            },
            {
                "id": "js-adv-10",
                "name": "JS Adv: Fetch API & JSON",
                "level": "advanced",
                "grade": "university",
                "order": 20,
            },
            # React.js Framework (21-28)
            {
                "id": "react-01",
                "name": "React 01: JSX & Components",
                "level": "framework",
                "grade": "university",
                "order": 21,
            },
            {
                "id": "react-02",
                "name": "React 02: Props & State (useState)",
                "level": "framework",
                "grade": "university",
                "order": 22,
            },
            {
                "id": "react-03",
                "name": "React 03: Xử lý sự kiện trong React",
                "level": "framework",
                "grade": "university",
                "order": 23,
            },
            {
                "id": "react-04",
                "name": "React 04: Lifecycle & useEffect",
                "level": "framework",
                "grade": "university",
                "order": 24,
            },
            {
                "id": "react-05",
                "name": "React 05: Làm việc với Form",
                "level": "framework",
                "grade": "university",
                "order": 25,
            },
            {
                "id": "react-06",
                "name": "React 06: Routing (React Router)",
                "level": "framework",
                "grade": "university",
                "order": 26,
            },
            {
                "id": "react-07",
                "name": "React 07: Quản lý State (Context API / Redux)",
                "level": "framework",
                "grade": "university",
                "order": 27,
            },
            {
                "id": "react-08",
                "name": "React 08: Gọi API trong React",
                "level": "framework",
                "grade": "university",
                "order": 28,
            },
            # Node.js & Express Backend (29-33)
            {
                "id": "node-01",
                "name": "NodeJS 01: Runtime & Modules",
                "level": "backend",
                "grade": "university",
                "order": 29,
            },
            {
                "id": "node-02",
                "name": "NodeJS 02: ExpressJS Framework cơ bản",
                "level": "backend",
                "grade": "university",
                "order": 30,
            },
            {
                "id": "node-03",
                "name": "NodeJS 03: Thiết kế RESTful API",
                "level": "backend",
                "grade": "university",
                "order": 31,
            },
            {
                "id": "node-04",
                "name": "NodeJS 04: Kết nối Database (MongoDB/SQL)",
                "level": "backend",
                "grade": "university",
                "order": 32,
            },
            {
                "id": "node-05",
                "name": "NodeJS 05: Authentication (JWT)",
                "level": "backend",
                "grade": "university",
                "order": 33,
            },
            # React Native Mobile (34-38)
            {
                "id": "rn-01",
                "name": "Mobile 01: View, Text & Style",
                "level": "mobile",
                "grade": "university",
                "order": 34,
            },
            {
                "id": "rn-02",
                "name": "Mobile 02: Flexbox & Layout Mobile",
                "level": "mobile",
                "grade": "university",
                "order": 35,
            },
            {
                "id": "rn-03",
                "name": "Mobile 03: ScrollView & FlatList",
                "level": "mobile",
                "grade": "university",
                "order": 36,
            },
            {
                "id": "rn-04",
                "name": "Mobile 04: Navigation (Chuyển màn hình)",
                "level": "mobile",
                "grade": "university",
                "order": 37,
            },
            {
                "id": "rn-05",
                "name": "Mobile 05: Truy cập Native (Camera/Vị trí)",
                "level": "mobile",
                "grade": "university",
                "order": 38,
            },
            # TypeScript Bonus (39-40)
            {
                "id": "ts-01",
                "name": "TypeScript: Type cơ bản & Interface",
                "level": "advanced",
                "grade": "university",
                "order": 39,
            },
            {
                "id": "ts-02",
                "name": "TypeScript: Generics & Utility Types",
                "level": "advanced",
                "grade": "university",
                "order": 40,
            },
        ],
        "html-css": [
            # HTML5 Core & Semantic (1-7)
            {
                "id": "html-01",
                "name": "HTML 01: Cấu trúc trang & Các thẻ văn bản",
                "level": "beginner",
                "grade": "highschool",
                "order": 1,
            },
            {
                "id": "html-02",
                "name": "HTML 02: Danh sách (List) & Liên kết (Link)",
                "level": "beginner",
                "grade": "highschool",
                "order": 2,
            },
            {
                "id": "html-03",
                "name": "HTML 03: Hình ảnh & Multimedia (Audio/Video)",
                "level": "beginner",
                "grade": "highschool",
                "order": 3,
            },
            {
                "id": "html-04",
                "name": "HTML 04: Bảng (Table) & Semantic Tags (Header/Footer)",
                "level": "beginner",
                "grade": "highschool",
                "order": 4,
            },
            {
                "id": "html-05",
                "name": "HTML 05: Form & Input Validation",
                "level": "intermediate",
                "grade": "highschool",
                "order": 5,
            },
            {
                "id": "html-06",
                "name": "HTML 06: Meta Tags & SEO Basics",
                "level": "intermediate",
                "grade": "highschool",
                "order": 6,
            },
            {
                "id": "html-07",
                "name": "HTML 07: Accessibility (A11y) - Web cho mọi người",
                "level": "advanced",
                "grade": "university",
                "order": 7,
            },
            # CSS Base & Typography (8-13)
            {
                "id": "css-01",
                "name": "CSS 01: Cú pháp, ID & Class Selectors",
                "level": "beginner",
                "grade": "highschool",
                "order": 8,
            },
            {
                "id": "css-02",
                "name": "CSS 02: Màu sắc (HEX/RGB) & Background",
                "level": "beginner",
                "grade": "highschool",
                "order": 9,
            },
            {
                "id": "css-03",
                "name": "CSS 03: Typography & Fonts",
                "level": "beginner",
                "grade": "highschool",
                "order": 10,
            },
            {
                "id": "css-04",
                "name": "CSS 04: Box Model (Margin - Border - Padding)",
                "level": "beginner",
                "grade": "highschool",
                "order": 11,
            },
            {
                "id": "css-05",
                "name": "CSS 05: Độ ưu tiên (Specificity) & Kế thừa",
                "level": "intermediate",
                "grade": "highschool",
                "order": 12,
            },
            {
                "id": "css-06",
                "name": "CSS 06: Đơn vị đo (px, rem, em, %, vh/vw)",
                "level": "intermediate",
                "grade": "highschool",
                "order": 13,
            },
            # Modern Layout (14-18)
            {
                "id": "layout-01",
                "name": "Layout 01: Display & Position (Relative/Absolute)",
                "level": "intermediate",
                "grade": "highschool",
                "order": 14,
            },
            {
                "id": "layout-02",
                "name": "Layout 02: Flexbox căn bản (Container & Item)",
                "level": "intermediate",
                "grade": "highschool",
                "order": 15,
            },
            {
                "id": "layout-03",
                "name": "Layout 03: Flexbox nâng cao & Thực hành Menu",
                "level": "intermediate",
                "grade": "highschool",
                "order": 16,
            },
            {
                "id": "layout-04",
                "name": "Layout 04: CSS Grid - Dàn trang lưới 2 chiều",
                "level": "advanced",
                "grade": "university",
                "order": 17,
            },
            {
                "id": "layout-05",
                "name": "Layout 05: Grid Area & Responsive Grid",
                "level": "advanced",
                "grade": "university",
                "order": 18,
            },
            # Responsive & Effects (19-23)
            {
                "id": "resp-01",
                "name": "Responsive 01: Media Queries & Breakpoints",
                "level": "intermediate",
                "grade": "university",
                "order": 19,
            },
            {
                "id": "resp-02",
                "name": "Responsive 02: Mobile-First Strategy",
                "level": "advanced",
                "grade": "university",
                "order": 20,
            },
            {
                "id": "effect-01",
                "name": "Effect 01: Transform & Transition (Chuyển động mượt)",
                "level": "intermediate",
                "grade": "university",
                "order": 21,
            },
            {
                "id": "effect-02",
                "name": "Effect 02: Keyframes & Animation phức tạp",
                "level": "advanced",
                "grade": "university",
                "order": 22,
            },
            {
                "id": "effect-03",
                "name": "Effect 03: Pseudo-elements (::before/::after)",
                "level": "advanced",
                "grade": "university",
                "order": 23,
            },
            # CSS Preprocessors & Frameworks (24-28)
            {
                "id": "tools-01",
                "name": "SASS/SCSS: Biến & Nesting",
                "level": "professional",
                "grade": "university",
                "order": 24,
            },
            {
                "id": "tools-02",
                "name": "BEM: Quy tắc đặt tên Class chuẩn",
                "level": "professional",
                "grade": "university",
                "order": 25,
            },
            {
                "id": "tools-03",
                "name": "Tailwind CSS 01: Utility-first Concept",
                "level": "professional",
                "grade": "university",
                "order": 26,
            },
            {
                "id": "tools-04",
                "name": "Tailwind CSS 02: Layout & Config",
                "level": "professional",
                "grade": "university",
                "order": 27,
            },
            {
                "id": "tools-05",
                "name": "Project: Clone giao diện Shopee/Facebook",
                "level": "practical",
                "grade": "university",
                "order": 28,
            },
        ],
        "sql": [
            # SQL Query Basics (1-5)
            {
                "id": "sql-01",
                "name": "SQL 01: Tổng quan Database & Table",
                "level": "beginner",
                "grade": "highschool",
                "order": 1,
            },
            {
                "id": "sql-02",
                "name": "SQL 02: SELECT & WHERE (Lọc dữ liệu)",
                "level": "beginner",
                "grade": "highschool",
                "order": 2,
            },
            {
                "id": "sql-03",
                "name": "SQL 03: Các toán tử (AND, OR, NOT, IN, LIKE)",
                "level": "beginner",
                "grade": "highschool",
                "order": 3,
            },
            {
                "id": "sql-04",
                "name": "SQL 04: Sắp xếp (ORDER BY) & Giới hạn (LIMIT)",
                "level": "beginner",
                "grade": "highschool",
                "order": 4,
            },
            {
                "id": "sql-05",
                "name": "SQL 05: Xử lý NULL (IS NULL, COALESCE)",
                "level": "intermediate",
                "grade": "highschool",
                "order": 5,
            },
            # Data Manipulation (6-9)
            {
                "id": "dml-01",
                "name": "DML 01: INSERT (Thêm dữ liệu mới)",
                "level": "beginner",
                "grade": "highschool",
                "order": 6,
            },
            {
                "id": "dml-02",
                "name": "DML 02: UPDATE (Cập nhật an toàn)",
                "level": "beginner",
                "grade": "highschool",
                "order": 7,
            },
            {
                "id": "dml-03",
                "name": "DML 03: DELETE & TRUNCATE (Xóa dữ liệu)",
                "level": "beginner",
                "grade": "highschool",
                "order": 8,
            },
            {
                "id": "dml-04",
                "name": "DML 04: Transaction (BEGIN, COMMIT, ROLLBACK)",
                "level": "advanced",
                "grade": "university",
                "order": 9,
            },
            # Aggregation & Grouping (10-13)
            {
                "id": "agg-01",
                "name": "AGG 01: Hàm gộp (COUNT, SUM, AVG, MIN, MAX)",
                "level": "intermediate",
                "grade": "highschool",
                "order": 10,
            },
            {
                "id": "agg-02",
                "name": "AGG 02: GROUP BY (Nhóm dữ liệu)",
                "level": "intermediate",
                "grade": "highschool",
                "order": 11,
            },
            {
                "id": "agg-03",
                "name": "AGG 03: HAVING (Lọc sau khi nhóm)",
                "level": "intermediate",
                "grade": "highschool",
                "order": 12,
            },
            {
                "id": "agg-04",
                "name": "AGG 04: Các hàm xử lý Chuỗi & Ngày tháng",
                "level": "intermediate",
                "grade": "university",
                "order": 13,
            },
            # Joins & Unions (14-18)
            {
                "id": "join-01",
                "name": "JOIN 01: Lý thuyết Khóa chính (PK) & Khóa ngoại (FK)",
                "level": "intermediate",
                "grade": "university",
                "order": 14,
            },
            {
                "id": "join-02",
                "name": "JOIN 02: INNER JOIN (Giao nhau)",
                "level": "intermediate",
                "grade": "university",
                "order": 15,
            },
            {
                "id": "join-03",
                "name": "JOIN 03: LEFT / RIGHT JOIN",
                "level": "intermediate",
                "grade": "university",
                "order": 16,
            },
            {
                "id": "join-04",
                "name": "JOIN 04: FULL JOIN & CROSS JOIN",
                "level": "advanced",
                "grade": "university",
                "order": 17,
            },
            {
                "id": "join-05",
                "name": "JOIN 05: UNION & UNION ALL (Gộp kết quả)",
                "level": "advanced",
                "grade": "university",
                "order": 18,
            },
            # Advanced SQL & Design (19-24)
            {
                "id": "adv-01",
                "name": "ADV 01: Subqueries (Truy vấn lồng)",
                "level": "advanced",
                "grade": "university",
                "order": 19,
            },
            {
                "id": "adv-02",
                "name": "ADV 02: CTE (Common Table Expressions - WITH)",
                "level": "advanced",
                "grade": "university",
                "order": 20,
            },
            {
                "id": "adv-03",
                "name": "ADV 03: Window Functions (RANK, ROW_NUMBER, OVER)",
                "level": "expert",
                "grade": "university",
                "order": 21,
            },
            {
                "id": "adv-04",
                "name": "ADV 04: Views (Bảng ảo)",
                "level": "expert",
                "grade": "university",
                "order": 22,
            },
            {
                "id": "adv-05",
                "name": "ADV 05: Indexing (Tối ưu tốc độ truy vấn)",
                "level": "expert",
                "grade": "university",
                "order": 23,
            },
            {
                "id": "adv-06",
                "name": "ADV 06: Stored Procedures & Triggers (Khái niệm)",
                "level": "expert",
                "grade": "university",
                "order": 24,
            },
            # Database Design & Normalization (25-28)
            {
                "id": "ddl-01",
                "name": "Design 01: CREATE / ALTER / DROP Table",
                "level": "intermediate",
                "grade": "university",
                "order": 25,
            },
            {
                "id": "ddl-02",
                "name": "Design 02: Constraints (NOT NULL, UNIQUE, CHECK)",
                "level": "intermediate",
                "grade": "university",
                "order": 26,
            },
            {
                "id": "ddl-03",
                "name": "Design 03: Chuẩn hóa dữ liệu (1NF, 2NF, 3NF)",
                "level": "professional",
                "grade": "university",
                "order": 27,
            },
            {
                "id": "ddl-04",
                "name": "Design 04: ER Diagram (Vẽ sơ đồ thực thể)",
                "level": "professional",
                "grade": "university",
                "order": 28,
            },
        ],
        "software-architecture": [
            # Architectural Patterns (1-5)
            {
                "id": "sa-01",
                "name": "SA 01: Monolith vs Microservices (Ưu/Nhược điểm)",
                "level": "beginner",
                "grade": "university",
                "order": 1,
            },
            {
                "id": "sa-02",
                "name": "SA 02: Layered Architecture (3-Tier: Presentation, Logic, Data)",
                "level": "beginner",
                "grade": "university",
                "order": 2,
            },
            {
                "id": "sa-03",
                "name": "SA 03: Event-Driven Architecture (EDA)",
                "level": "intermediate",
                "grade": "university",
                "order": 3,
            },
            {
                "id": "sa-04",
                "name": "SA 04: Serverless Architecture (AWS Lambda/Cloud Function)",
                "level": "intermediate",
                "grade": "university",
                "order": 4,
            },
            {
                "id": "sa-05",
                "name": "SA 05: Hexagonal / Clean Architecture",
                "level": "advanced",
                "grade": "university",
                "order": 5,
            },
            # Web & Mobile Application Architecture (6-9)
            {
                "id": "sa-web-01",
                "name": "Web 01: CSR vs SSR vs SSG (React/Next.js Rendering)",
                "level": "intermediate",
                "grade": "university",
                "order": 6,
            },
            {
                "id": "sa-web-02",
                "name": "Web 02: State Management Patterns (Redux/Context)",
                "level": "intermediate",
                "grade": "university",
                "order": 7,
            },
            {
                "id": "sa-mobile-01",
                "name": "Mobile 01: Native vs Cross-platform (Flutter/React Native)",
                "level": "intermediate",
                "grade": "university",
                "order": 8,
            },
            {
                "id": "sa-mobile-02",
                "name": "Mobile 02: Offline-First Architecture (Sync Data)",
                "level": "advanced",
                "grade": "university",
                "order": 9,
            },
            # Backend & API Design (10-14)
            {
                "id": "sa-api-01",
                "name": "API 01: RESTful API Design Standards",
                "level": "intermediate",
                "grade": "university",
                "order": 10,
            },
            {
                "id": "sa-api-02",
                "name": "API 02: GraphQL vs REST (Khi nào dùng gì?)",
                "level": "intermediate",
                "grade": "university",
                "order": 11,
            },
            {
                "id": "sa-api-03",
                "name": "API 03: WebSockets & Real-time Communication",
                "level": "advanced",
                "grade": "university",
                "order": 12,
            },
            {
                "id": "sa-auth-01",
                "name": "Security 01: Authentication (OAuth2, JWT, SSO)",
                "level": "advanced",
                "grade": "university",
                "order": 13,
            },
            {
                "id": "sa-auth-02",
                "name": "Security 02: Authorization (RBAC/ABAC)",
                "level": "advanced",
                "grade": "university",
                "order": 14,
            },
            # Database & Data Strategy (15-18)
            {
                "id": "sa-data-01",
                "name": "Data 01: SQL vs NoSQL (Postgres vs MongoDB)",
                "level": "intermediate",
                "grade": "university",
                "order": 15,
            },
            {
                "id": "sa-data-02",
                "name": "Data 02: Caching Strategy (Redis/Memcached)",
                "level": "advanced",
                "grade": "university",
                "order": 16,
            },
            {
                "id": "sa-data-03",
                "name": "Data 03: Database Replication & Sharding (Scaling)",
                "level": "expert",
                "grade": "university",
                "order": 17,
            },
            {
                "id": "sa-data-04",
                "name": "Data 04: Message Queues (RabbitMQ/Kafka)",
                "level": "expert",
                "grade": "university",
                "order": 18,
            },
            # Infrastructure & DevOps (19-24)
            {
                "id": "sa-ops-01",
                "name": "Ops 01: Docker & Containerization (Cơ bản)",
                "level": "practical",
                "grade": "university",
                "order": 19,
            },
            {
                "id": "sa-ops-02",
                "name": "Ops 02: Kubernetes (K8s) Overview",
                "level": "practical",
                "grade": "university",
                "order": 20,
            },
            {
                "id": "sa-ops-03",
                "name": "Ops 03: CI/CD Pipelines (GitHub Actions/Jenkins)",
                "level": "practical",
                "grade": "university",
                "order": 21,
            },
            {
                "id": "sa-ops-04",
                "name": "Ops 04: Load Balancing (Nginx/HAProxy)",
                "level": "practical",
                "grade": "university",
                "order": 22,
            },
            {
                "id": "sa-ops-05",
                "name": "Ops 05: CDN & Static Content Delivery",
                "level": "practical",
                "grade": "university",
                "order": 23,
            },
            {
                "id": "sa-ops-06",
                "name": "Ops 06: SaaS Architecture (Multi-tenancy)",
                "level": "expert",
                "grade": "university",
                "order": 24,
            },
        ],
        "ai": [
            # Foundations (1-3)
            {
                "id": "ai-base-01",
                "name": "AI 01: Đại số tuyến tính & Xác suất thống kê (Cơ bản)",
                "level": "beginner",
                "grade": "university",
                "order": 1,
            },
            {
                "id": "ai-base-02",
                "name": "AI 02: Python for Data (Numpy, Pandas Visualization)",
                "level": "beginner",
                "grade": "university",
                "order": 2,
            },
            {
                "id": "ai-base-03",
                "name": "AI 03: Data Preprocessing (Làm sạch dữ liệu)",
                "level": "intermediate",
                "grade": "university",
                "order": 3,
            },
            # Machine Learning (4-7)
            {
                "id": "ai-ml-01",
                "name": "ML 01: Supervised Learning (Hồi quy, Phân loại)",
                "level": "intermediate",
                "grade": "university",
                "order": 4,
            },
            {
                "id": "ai-ml-02",
                "name": "ML 02: Unsupervised Learning (Clustering/K-Means)",
                "level": "intermediate",
                "grade": "university",
                "order": 5,
            },
            {
                "id": "ai-ml-03",
                "name": "ML 03: Scikit-learn Framework",
                "level": "intermediate",
                "grade": "university",
                "order": 6,
            },
            {
                "id": "ai-ml-04",
                "name": "ML 04: Đánh giá Model (Accuracy, Precision, Recall, F1)",
                "level": "intermediate",
                "grade": "university",
                "order": 7,
            },
            # Deep Learning (8-11)
            {
                "id": "ai-dl-01",
                "name": "DL 01: Neural Networks & Backpropagation",
                "level": "advanced",
                "grade": "university",
                "order": 8,
            },
            {
                "id": "ai-dl-02",
                "name": "DL 02: PyTorch / TensorFlow Basics",
                "level": "advanced",
                "grade": "university",
                "order": 9,
            },
            {
                "id": "ai-dl-03",
                "name": "DL 03: CNN (Computer Vision - Xử lý ảnh)",
                "level": "advanced",
                "grade": "university",
                "order": 10,
            },
            {
                "id": "ai-dl-04",
                "name": "DL 04: RNN & LSTM (Xử lý chuỗi thời gian)",
                "level": "advanced",
                "grade": "university",
                "order": 11,
            },
            # Generative AI & LLMs (12-15)
            {
                "id": "ai-gen-01",
                "name": "GenAI 01: Transformers Architecture (Attention is all you need)",
                "level": "expert",
                "grade": "university",
                "order": 12,
            },
            {
                "id": "ai-gen-02",
                "name": "GenAI 02: LLMs Overview (GPT, Llama, Claude)",
                "level": "expert",
                "grade": "university",
                "order": 13,
            },
            {
                "id": "ai-gen-03",
                "name": "GenAI 03: Prompt Engineering nâng cao",
                "level": "expert",
                "grade": "university",
                "order": 14,
            },
            {
                "id": "ai-gen-04",
                "name": "GenAI 04: Hugging Face & Pre-trained Models",
                "level": "practical",
                "grade": "university",
                "order": 15,
            },
            # RAG & Fine-tuning (16-20)
            {
                "id": "ai-rag-01",
                "name": "RAG 01: Vector Database (Pinecone, ChromaDB)",
                "level": "practical",
                "grade": "university",
                "order": 16,
            },
            {
                "id": "ai-rag-02",
                "name": "RAG 02: Embeddings & Semantic Search",
                "level": "practical",
                "grade": "university",
                "order": 17,
            },
            {
                "id": "ai-rag-03",
                "name": "RAG 03: LangChain / LlamaIndex Framework",
                "level": "practical",
                "grade": "university",
                "order": 18,
            },
            {
                "id": "ai-rag-04",
                "name": "Fine-tune 01: Concepts (Full vs PEFT/LoRA)",
                "level": "expert",
                "grade": "university",
                "order": 19,
            },
            {
                "id": "ai-rag-05",
                "name": "Fine-tune 02: Quy trình Fine-tuning Llama trên Google Colab",
                "level": "expert",
                "grade": "university",
                "order": 20,
            },
            # MLOps & Deployment (21-23)
            {
                "id": "ai-ops-01",
                "name": "MLOps 01: Đóng gói Model với Docker",
                "level": "practical",
                "grade": "university",
                "order": 21,
            },
            {
                "id": "ai-ops-02",
                "name": "MLOps 02: Serving Model qua API (FastAPI)",
                "level": "practical",
                "grade": "university",
                "order": 22,
            },
            {
                "id": "ai-ops-03",
                "name": "MLOps 03: Monitoring & Drift Detection (Theo dõi Model)",
                "level": "expert",
                "grade": "university",
                "order": 23,
            },
        ],
    }

    stats = {
        "total": 0,
        "created": 0,
        "skipped": 0,
        "errors": 0,
    }

    # Insert topics for each category
    for category_id, topics in all_topics.items():
        print(f"\n{'='*80}")
        print(f"Category: {category_id.upper()}")
        print(f"{'='*80}")

        for topic_data in topics:
            topic_id = topic_data["id"]

            # Check if topic already exists
            existing = db.learning_topics.find_one({"id": topic_id})

            if existing:
                print(f"⏭️  Skipped (exists): {topic_data['name']}")
                stats["skipped"] += 1
                continue

            # Create topic
            try:
                now = datetime.utcnow()

                topic = {
                    "id": topic_id,
                    "category_id": category_id,
                    "name": topic_data["name"],
                    "description": f"Học {topic_data['name']}",
                    "level": topic_data["level"],
                    "grade": topic_data.get("grade", "university"),
                    "order": topic_data["order"],
                    "icon": "📘",
                    "color": "#3B82F6",
                    "estimated_hours": 2,
                    "prerequisites": [],
                    "learning_outcomes": [],
                    "metadata": {
                        "difficulty": topic_data["level"],
                        "version": "1.0",
                    },
                    "is_published": True,
                    "created_at": now,
                    "updated_at": now,
                }

                if not DRY_RUN:
                    db.learning_topics.insert_one(topic)

                print(f"✅ Created: {topic_data['name']}")
                stats["created"] += 1
                stats["total"] += 1

            except Exception as e:
                print(f"❌ Error creating {topic_data['name']}: {str(e)}")
                stats["errors"] += 1

    # Print summary
    print("\n" + "=" * 80)
    print("SEEDING SUMMARY")
    print("=" * 80)
    print(f"Total topics processed: {stats['total']}")
    print(f"Created: {stats['created']}")
    print(f"Skipped (exists): {stats['skipped']}")
    print(f"Errors: {stats['errors']}")
    print("=" * 80)

    if DRY_RUN:
        print("\n⚠️  DRY RUN COMPLETE - No changes were made")
        print("Set DRY_RUN = False to execute seeding")
    else:
        print("\n✅ SEEDING COMPLETE")


if __name__ == "__main__":
    try:
        seed_topics()
    except KeyboardInterrupt:
        print("\n\n⚠️  Seeding interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Seeding failed: {str(e)}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
