"""
Seed 4 new programming language categories + topics into MongoDB.

Categories: java, c-cpp, rust, go
Usage: ./copy-and-run.sh seed_categories_topics_new_langs.py --bg --deps
"""

import sys
import os

sys.path.insert(0, "/app")

from datetime import datetime, timezone
from pymongo import MongoClient

# ── DB connection ──────────────────────────────────────────────────
MONGO_URI = os.getenv(
    "MONGODB_URI",
    "mongodb://ai_service_user:ai_service_2025_secure_password@localhost:27017/ai_service_db?authSource=admin",
)
client = MongoClient(MONGO_URI)
db = client["ai_service_db"]

now = datetime.now(timezone.utc)


def upsert_category(cat: dict):
    doc = {
        **cat,
        "is_active": True,
        "topic_count": 0,
        "knowledge_count": 0,
        "created_at": now,
        "updated_at": now,
    }
    result = db.learning_categories.update_one(
        {"id": cat["id"]}, {"$setOnInsert": doc}, upsert=True
    )
    action = "inserted" if result.upserted_id else "already exists"
    print(f"  Category [{cat['id']}] {action}")


def upsert_topic(topic: dict):
    doc = {
        **topic,
        "is_active": True,
        "is_published": True,
        "source_type": "wordai_team",
        "knowledge_count": 0,
        "template_count": 0,
        "exercise_count": 0,
        "prerequisites": topic.get("prerequisites", []),
        "learning_outcomes": topic.get("learning_outcomes", []),
        "tags": topic.get("tags", []),
        "metadata": {},
        "created_at": now,
        "updated_at": now,
    }
    result = db.learning_topics.update_one(
        {"id": topic["id"]}, {"$setOnInsert": doc}, upsert=True
    )
    action = "inserted" if result.upserted_id else "already exists"
    print(f"    Topic [{topic['id']}] {action}")


# ══════════════════════════════════════════════════════════════════
# CATEGORIES
# ══════════════════════════════════════════════════════════════════
CATEGORIES = [
    {
        "id": "java",
        "name": "Java",
        "description": "Ngôn ngữ lập trình hướng đối tượng mạnh mẽ, dùng trong enterprise, Android và backend.",
        "icon": "☕",
        "order": 7,
    },
    {
        "id": "c-cpp",
        "name": "C / C++",
        "description": "Ngôn ngữ lập trình hệ thống, hiệu năng cao, nền tảng cho hệ điều hành và embedded.",
        "icon": "⚙️",
        "order": 8,
    },
    {
        "id": "rust",
        "name": "Rust",
        "description": "Ngôn ngữ lập trình systems an toàn bộ nhớ, không cần GC, tốc độ ngang C/C++.",
        "icon": "🦀",
        "order": 9,
    },
    {
        "id": "go",
        "name": "Go (Golang)",
        "description": "Ngôn ngữ compiled hiện đại của Google, concurrency built-in, lý tưởng cho microservices.",
        "icon": "🐹",
        "order": 10,
    },
]

# ══════════════════════════════════════════════════════════════════
# TOPICS — JAVA
# ══════════════════════════════════════════════════════════════════
JAVA_TOPICS = [
    {
        "id": "java-01-basics",
        "category_id": "java",
        "name": "Java Cơ Bản",
        "description": "Cú pháp, kiểu dữ liệu, biến, toán tử, vòng lặp và mảng trong Java.",
        "level": "beginner",
        "order": 1,
        "icon": "☕",
        "estimated_hours": 8,
        "tags": ["java", "basics", "syntax"],
        "learning_outcomes": [
            "Hiểu cú pháp Java cơ bản",
            "Khai báo biến và kiểu dữ liệu",
            "Sử dụng vòng lặp và điều kiện",
        ],
    },
    {
        "id": "java-02-oop",
        "category_id": "java",
        "name": "Lập Trình Hướng Đối Tượng (OOP)",
        "description": "Class, object, inheritance, polymorphism, encapsulation, abstraction trong Java.",
        "level": "beginner",
        "order": 2,
        "icon": "🏗️",
        "estimated_hours": 12,
        "tags": ["java", "oop", "class", "inheritance"],
        "learning_outcomes": [
            "Tạo class và object",
            "Áp dụng 4 tính chất OOP",
            "Interface và abstract class",
        ],
    },
    {
        "id": "java-03-collections",
        "category_id": "java",
        "name": "Java Collections Framework",
        "description": "List, Set, Map, Queue, Iterator và các thuật toán xử lý collection.",
        "level": "intermediate",
        "order": 3,
        "icon": "📦",
        "estimated_hours": 10,
        "tags": ["java", "collections", "arraylist", "hashmap"],
        "learning_outcomes": [
            "Chọn cấu trúc dữ liệu phù hợp",
            "Sử dụng ArrayList, HashMap, LinkedList",
            "Iterator và Stream API",
        ],
    },
    {
        "id": "java-04-exceptions",
        "category_id": "java",
        "name": "Xử Lý Ngoại Lệ (Exceptions)",
        "description": "try-catch-finally, checked/unchecked exceptions, custom exceptions, logging.",
        "level": "intermediate",
        "order": 4,
        "icon": "⚠️",
        "estimated_hours": 6,
        "tags": ["java", "exceptions", "error-handling"],
        "learning_outcomes": [
            "Bắt và xử lý exception",
            "Tạo custom exception",
            "Best practices error handling",
        ],
    },
    {
        "id": "java-05-generics",
        "category_id": "java",
        "name": "Generics & Type Safety",
        "description": "Generic classes, methods, bounded wildcards và type erasure trong Java.",
        "level": "intermediate",
        "order": 5,
        "icon": "🔧",
        "estimated_hours": 8,
        "tags": ["java", "generics", "type-safety"],
        "learning_outcomes": [
            "Viết generic class và method",
            "Hiểu wildcard ? extends / ? super",
            "Type erasure hoạt động như thế nào",
        ],
    },
    {
        "id": "java-06-streams",
        "category_id": "java",
        "name": "Stream API & Lambda",
        "description": "Functional programming với Java: lambda, method reference, Stream, Optional.",
        "level": "intermediate",
        "order": 6,
        "icon": "🌊",
        "estimated_hours": 10,
        "tags": ["java", "stream", "lambda", "functional"],
        "learning_outcomes": [
            "Viết lambda expression",
            "Xử lý collection với Stream",
            "map, filter, reduce, collect",
        ],
    },
    {
        "id": "java-07-concurrency",
        "category_id": "java",
        "name": "Multithreading & Concurrency",
        "description": "Thread, Runnable, synchronized, ExecutorService, CompletableFuture.",
        "level": "advanced",
        "order": 7,
        "icon": "⚡",
        "estimated_hours": 14,
        "tags": ["java", "threads", "concurrency", "async"],
        "learning_outcomes": [
            "Tạo và quản lý thread",
            "Tránh race condition",
            "Dùng ExecutorService hiệu quả",
        ],
    },
    {
        "id": "java-08-io-files",
        "category_id": "java",
        "name": "I/O & File Processing",
        "description": "File I/O, NIO.2, Serialization, đọc/ghi CSV/JSON, Path API.",
        "level": "intermediate",
        "order": 8,
        "icon": "📁",
        "estimated_hours": 8,
        "tags": ["java", "io", "files", "nio"],
        "learning_outcomes": [
            "Đọc ghi file văn bản và binary",
            "Dùng Path và Files API",
            "Serialize/deserialize object",
        ],
    },
    {
        "id": "java-09-jdbc",
        "category_id": "java",
        "name": "JDBC & Database",
        "description": "Kết nối database với JDBC, PreparedStatement, transactions, connection pool.",
        "level": "intermediate",
        "order": 9,
        "icon": "🗄️",
        "estimated_hours": 10,
        "tags": ["java", "jdbc", "database", "sql"],
        "learning_outcomes": [
            "Kết nối MySQL/PostgreSQL",
            "Thực thi CRUD với JDBC",
            "Transaction và connection pool",
        ],
    },
    {
        "id": "java-10-spring-core",
        "category_id": "java",
        "name": "Spring Framework Core",
        "description": "IoC container, Dependency Injection, Bean lifecycle, Spring annotations.",
        "level": "advanced",
        "order": 10,
        "icon": "🌱",
        "estimated_hours": 16,
        "tags": ["java", "spring", "di", "ioc"],
        "learning_outcomes": [
            "Cấu hình Spring với annotations",
            "Dependency Injection patterns",
            "Bean scopes và lifecycle",
        ],
    },
    {
        "id": "java-11-spring-boot",
        "category_id": "java",
        "name": "Spring Boot REST API",
        "description": "Xây dựng REST API với Spring Boot: controllers, services, repositories, JPA.",
        "level": "advanced",
        "order": 11,
        "icon": "🚀",
        "estimated_hours": 20,
        "tags": ["java", "spring-boot", "rest-api", "jpa"],
        "learning_outcomes": [
            "Tạo REST endpoints",
            "Spring Data JPA CRUD",
            "Validation, error handling, pagination",
        ],
    },
    {
        "id": "java-12-spring-security",
        "category_id": "java",
        "name": "Spring Security & JWT",
        "description": "Authentication, authorization, JWT tokens, OAuth2 với Spring Security.",
        "level": "advanced",
        "order": 12,
        "icon": "🔐",
        "estimated_hours": 12,
        "tags": ["java", "security", "jwt", "oauth2"],
        "learning_outcomes": [
            "Cấu hình authentication",
            "JWT token generation/validation",
            "Role-based access control",
        ],
    },
    {
        "id": "java-13-microservices",
        "category_id": "java",
        "name": "Microservices với Spring Cloud",
        "description": "Service discovery, API gateway, config server, circuit breaker với Spring Cloud.",
        "level": "expert",
        "order": 13,
        "icon": "☁️",
        "estimated_hours": 20,
        "tags": ["java", "microservices", "spring-cloud", "eureka"],
        "learning_outcomes": [
            "Service discovery với Eureka",
            "API Gateway pattern",
            "Circuit breaker với Resilience4j",
        ],
    },
    {
        "id": "java-14-testing",
        "category_id": "java",
        "name": "Testing với JUnit & Mockito",
        "description": "Unit test, integration test, TDD, Mockito, AssertJ, test coverage.",
        "level": "intermediate",
        "order": 14,
        "icon": "🧪",
        "estimated_hours": 10,
        "tags": ["java", "testing", "junit", "mockito", "tdd"],
        "learning_outcomes": [
            "Viết unit test với JUnit 5",
            "Mock dependencies với Mockito",
            "Test coverage và TDD workflow",
        ],
    },
    {
        "id": "java-15-design-patterns",
        "category_id": "java",
        "name": "Design Patterns trong Java",
        "description": "GoF design patterns: Singleton, Factory, Builder, Observer, Strategy, Decorator.",
        "level": "advanced",
        "order": 15,
        "icon": "🎨",
        "estimated_hours": 14,
        "tags": ["java", "design-patterns", "solid", "refactoring"],
        "learning_outcomes": [
            "Áp dụng creational patterns",
            "Structural patterns",
            "Behavioral patterns in real code",
        ],
    },
]

# ══════════════════════════════════════════════════════════════════
# TOPICS — C/C++
# ══════════════════════════════════════════════════════════════════
CCPP_TOPICS = [
    {
        "id": "c-cpp-01-c-basics",
        "category_id": "c-cpp",
        "name": "C Cơ Bản",
        "description": "Cú pháp C, kiểu dữ liệu, biến, toán tử, câu lệnh điều kiện và vòng lặp.",
        "level": "beginner",
        "order": 1,
        "icon": "⚙️",
        "estimated_hours": 8,
        "tags": ["c", "basics", "syntax"],
        "learning_outcomes": [
            "Hiểu cú pháp C cơ bản",
            "Khai báo và sử dụng biến",
            "Vòng lặp và hàm đơn giản",
        ],
    },
    {
        "id": "c-cpp-02-pointers",
        "category_id": "c-cpp",
        "name": "Con Trỏ (Pointers) & Bộ Nhớ",
        "description": "Pointer, pointer arithmetic, NULL, dangling pointer, malloc/free, memory layout.",
        "level": "intermediate",
        "order": 2,
        "icon": "🎯",
        "estimated_hours": 12,
        "tags": ["c", "pointers", "memory", "malloc"],
        "learning_outcomes": [
            "Hiểu địa chỉ bộ nhớ",
            "Dùng pointer đúng cách",
            "Quản lý dynamic memory",
        ],
    },
    {
        "id": "c-cpp-03-arrays-strings",
        "category_id": "c-cpp",
        "name": "Mảng & Chuỗi trong C",
        "description": "Arrays, multidimensional arrays, C-strings, string functions, char pointers.",
        "level": "beginner",
        "order": 3,
        "icon": "📋",
        "estimated_hours": 8,
        "tags": ["c", "arrays", "strings"],
        "learning_outcomes": [
            "Khai báo và dùng mảng",
            "Xử lý chuỗi C-style",
            "Pointer và array relationship",
        ],
    },
    {
        "id": "c-cpp-04-structs",
        "category_id": "c-cpp",
        "name": "Struct, Union & Enum",
        "description": "Struct, nested struct, typedef, union, enum, bit fields trong C.",
        "level": "intermediate",
        "order": 4,
        "icon": "🏗️",
        "estimated_hours": 8,
        "tags": ["c", "struct", "union", "enum"],
        "learning_outcomes": [
            "Định nghĩa và dùng struct",
            "Pointer to struct",
            "Enum và typedef patterns",
        ],
    },
    {
        "id": "c-cpp-05-file-io",
        "category_id": "c-cpp",
        "name": "File I/O trong C",
        "description": "fopen, fclose, fread, fwrite, fprintf, fscanf, binary files.",
        "level": "intermediate",
        "order": 5,
        "icon": "📁",
        "estimated_hours": 6,
        "tags": ["c", "file-io", "fopen"],
        "learning_outcomes": [
            "Đọc ghi file text và binary",
            "Error handling với file",
            "Stdin/stdout redirect",
        ],
    },
    {
        "id": "c-cpp-06-cpp-basics",
        "category_id": "c-cpp",
        "name": "C++ Cơ Bản",
        "description": "C++ vs C, namespaces, references, cin/cout, string class, auto keyword.",
        "level": "beginner",
        "order": 6,
        "icon": "➕",
        "estimated_hours": 8,
        "tags": ["cpp", "basics", "references"],
        "learning_outcomes": [
            "Hiểu sự khác biệt C++ và C",
            "Dùng references thay pointer",
            "I/O với cin/cout",
        ],
    },
    {
        "id": "c-cpp-07-oop-cpp",
        "category_id": "c-cpp",
        "name": "OOP trong C++",
        "description": "Class, constructor, destructor, access specifiers, inheritance, polymorphism.",
        "level": "intermediate",
        "order": 7,
        "icon": "🏛️",
        "estimated_hours": 14,
        "tags": ["cpp", "oop", "class", "virtual"],
        "learning_outcomes": [
            "Viết class với constructor/destructor",
            "Virtual functions và polymorphism",
            "Multiple inheritance",
        ],
    },
    {
        "id": "c-cpp-08-templates",
        "category_id": "c-cpp",
        "name": "Templates & Generic Programming",
        "description": "Function templates, class templates, template specialization, variadic templates.",
        "level": "advanced",
        "order": 8,
        "icon": "🔧",
        "estimated_hours": 10,
        "tags": ["cpp", "templates", "generics"],
        "learning_outcomes": [
            "Viết function và class template",
            "Template specialization",
            "CRTP pattern",
        ],
    },
    {
        "id": "c-cpp-09-stl",
        "category_id": "c-cpp",
        "name": "STL (Standard Template Library)",
        "description": "vector, list, map, set, unordered_map, iterators, algorithms, functors.",
        "level": "intermediate",
        "order": 9,
        "icon": "📚",
        "estimated_hours": 12,
        "tags": ["cpp", "stl", "vector", "map", "algorithms"],
        "learning_outcomes": [
            "Dùng thành thạo vector, map, set",
            "STL algorithms (sort, find, transform)",
            "Custom comparators",
        ],
    },
    {
        "id": "c-cpp-10-modern-cpp",
        "category_id": "c-cpp",
        "name": "Modern C++ (C++11/14/17/20)",
        "description": "Move semantics, smart pointers, lambda, structured bindings, ranges, concepts.",
        "level": "advanced",
        "order": 10,
        "icon": "⚡",
        "estimated_hours": 16,
        "tags": ["cpp", "modern-cpp", "move-semantics", "smart-pointers"],
        "learning_outcomes": [
            "unique_ptr, shared_ptr, weak_ptr",
            "Move semantics và rvalue",
            "Lambda và std::function",
        ],
    },
    {
        "id": "c-cpp-11-memory-management",
        "category_id": "c-cpp",
        "name": "Quản Lý Bộ Nhớ Nâng Cao",
        "description": "RAII, memory pools, allocators, valgrind, address sanitizer, memory leaks.",
        "level": "advanced",
        "order": 11,
        "icon": "🧠",
        "estimated_hours": 10,
        "tags": ["cpp", "memory", "raii", "valgrind"],
        "learning_outcomes": [
            "Áp dụng RAII pattern",
            "Phát hiện memory leak",
            "Custom allocators",
        ],
    },
    {
        "id": "c-cpp-12-concurrency",
        "category_id": "c-cpp",
        "name": "Concurrency & Multithreading",
        "description": "std::thread, mutex, condition_variable, atomic, promises, futures.",
        "level": "advanced",
        "order": 12,
        "icon": "🔄",
        "estimated_hours": 14,
        "tags": ["cpp", "threads", "mutex", "atomic"],
        "learning_outcomes": [
            "Tạo và đồng bộ thread",
            "Atomic operations",
            "lock-free programming basics",
        ],
    },
    {
        "id": "c-cpp-13-systems-programming",
        "category_id": "c-cpp",
        "name": "Systems Programming",
        "description": "POSIX API, syscalls, processes, pipes, sockets, signal handling.",
        "level": "expert",
        "order": 13,
        "icon": "🖥️",
        "estimated_hours": 16,
        "tags": ["c", "systems", "posix", "syscall"],
        "learning_outcomes": [
            "Dùng POSIX APIs",
            "Fork/exec process model",
            "Socket programming cơ bản",
        ],
    },
    {
        "id": "c-cpp-14-embedded",
        "category_id": "c-cpp",
        "name": "Embedded & Bare-Metal C",
        "description": "GPIO, interrupts, UART, I2C, SPI, memory-mapped I/O, firmware programming.",
        "level": "expert",
        "order": 14,
        "icon": "🔌",
        "estimated_hours": 20,
        "tags": ["c", "embedded", "microcontroller", "firmware"],
        "learning_outcomes": [
            "Lập trình microcontroller",
            "Giao tiếp GPIO, UART",
            "Interrupt handlers",
        ],
    },
    {
        "id": "c-cpp-15-algorithms",
        "category_id": "c-cpp",
        "name": "Giải Thuật & Cấu Trúc Dữ Liệu",
        "description": "Sorting, searching, linked list, tree, graph, dynamic programming trong C/C++.",
        "level": "intermediate",
        "order": 15,
        "icon": "🧩",
        "estimated_hours": 18,
        "tags": ["cpp", "algorithms", "data-structures", "dsa"],
        "learning_outcomes": [
            "Implement cấu trúc dữ liệu cơ bản",
            "Big-O analysis",
            "Dynamic programming problems",
        ],
    },
]

# ══════════════════════════════════════════════════════════════════
# TOPICS — RUST
# ══════════════════════════════════════════════════════════════════
RUST_TOPICS = [
    {
        "id": "rust-01-basics",
        "category_id": "rust",
        "name": "Rust Cơ Bản",
        "description": "Variables, primitive types, functions, control flow, cargo, hello world.",
        "level": "beginner",
        "order": 1,
        "icon": "🦀",
        "estimated_hours": 8,
        "tags": ["rust", "basics", "cargo"],
        "learning_outcomes": [
            "Cài đặt và dùng cargo",
            "Cú pháp Rust cơ bản",
            "Immutability vs mutability",
        ],
    },
    {
        "id": "rust-02-ownership",
        "category_id": "rust",
        "name": "Ownership & Borrowing",
        "description": "Rust's ownership model, borrows, references, the borrow checker.",
        "level": "beginner",
        "order": 2,
        "icon": "🔑",
        "estimated_hours": 12,
        "tags": ["rust", "ownership", "borrowing", "borrow-checker"],
        "learning_outcomes": [
            "Hiểu ownership rules",
            "Shared & mutable borrows",
            "Tại sao Rust an toàn bộ nhớ",
        ],
    },
    {
        "id": "rust-03-lifetimes",
        "category_id": "rust",
        "name": "Lifetimes",
        "description": "Lifetime annotations, lifetime elision, 'static, advanced lifetime patterns.",
        "level": "intermediate",
        "order": 3,
        "icon": "⏳",
        "estimated_hours": 10,
        "tags": ["rust", "lifetimes", "annotations"],
        "learning_outcomes": [
            "Đọc và viết lifetime annotations",
            "Lifetime trong structs và functions",
            "Common lifetime pitfalls",
        ],
    },
    {
        "id": "rust-04-structs-enums",
        "category_id": "rust",
        "name": "Structs, Enums & Pattern Matching",
        "description": "Struct methods, impl blocks, enum, Option, Result, match, if let.",
        "level": "beginner",
        "order": 4,
        "icon": "🎲",
        "estimated_hours": 10,
        "tags": ["rust", "enum", "struct", "pattern-matching"],
        "learning_outcomes": [
            "Định nghĩa và dùng structs",
            "Option<T> và Result<T,E>",
            "Pattern matching toàn diện",
        ],
    },
    {
        "id": "rust-05-traits",
        "category_id": "rust",
        "name": "Traits & Generics",
        "description": "Traits as interfaces, trait objects, generic functions, trait bounds, where clauses.",
        "level": "intermediate",
        "order": 5,
        "icon": "🎭",
        "estimated_hours": 12,
        "tags": ["rust", "traits", "generics"],
        "learning_outcomes": [
            "Định nghĩa và implement traits",
            "Generics với trait bounds",
            "Static vs dynamic dispatch",
        ],
    },
    {
        "id": "rust-06-error-handling",
        "category_id": "rust",
        "name": "Error Handling",
        "description": "Result, ? operator, thiserror, anyhow, custom error types, propagation.",
        "level": "intermediate",
        "order": 6,
        "icon": "🚨",
        "estimated_hours": 8,
        "tags": ["rust", "error-handling", "result", "thiserror"],
        "learning_outcomes": [
            "Dùng Result và ? operator",
            "Custom Error types",
            "anyhow cho application code",
        ],
    },
    {
        "id": "rust-07-collections",
        "category_id": "rust",
        "name": "Collections & Iterators",
        "description": "Vec, HashMap, HashSet, String, slices, iterators, iterator adapters, collect.",
        "level": "intermediate",
        "order": 7,
        "icon": "📦",
        "estimated_hours": 10,
        "tags": ["rust", "vec", "hashmap", "iterators"],
        "learning_outcomes": [
            "Vec, HashMap thành thạo",
            "Iterator chains với map/filter",
            "Collect vào các collection",
        ],
    },
    {
        "id": "rust-08-closures",
        "category_id": "rust",
        "name": "Closures & Functional Programming",
        "description": "Closures, Fn/FnMut/FnOnce, higher-order functions, functional patterns.",
        "level": "intermediate",
        "order": 8,
        "icon": "λ",
        "estimated_hours": 8,
        "tags": ["rust", "closures", "functional"],
        "learning_outcomes": [
            "Viết và dùng closures",
            "Fn trait variants",
            "Functional patterns trong Rust",
        ],
    },
    {
        "id": "rust-09-async",
        "category_id": "rust",
        "name": "Async / Await & Tokio",
        "description": "async fn, await, Futures, tokio runtime, async I/O, channels.",
        "level": "advanced",
        "order": 9,
        "icon": "⚡",
        "estimated_hours": 14,
        "tags": ["rust", "async", "tokio", "futures"],
        "learning_outcomes": [
            "Viết async functions",
            "Tokio task và spawn",
            "Async channels và concurrency",
        ],
    },
    {
        "id": "rust-10-smart-pointers",
        "category_id": "rust",
        "name": "Smart Pointers & Interior Mutability",
        "description": "Box, Rc, Arc, RefCell, Mutex, RwLock, Weak, memory patterns.",
        "level": "advanced",
        "order": 10,
        "icon": "🔮",
        "estimated_hours": 10,
        "tags": ["rust", "box", "rc", "arc", "refcell"],
        "learning_outcomes": [
            "Khi nào dùng Box/Rc/Arc",
            "Interior mutability với RefCell",
            "Arc<Mutex<T>> pattern",
        ],
    },
    {
        "id": "rust-11-unsafe",
        "category_id": "rust",
        "name": "Unsafe Rust",
        "description": "Raw pointers, unsafe blocks, FFI, calling C from Rust, unsafe abstractions.",
        "level": "advanced",
        "order": 11,
        "icon": "⚠️",
        "estimated_hours": 10,
        "tags": ["rust", "unsafe", "ffi", "raw-pointers"],
        "learning_outcomes": [
            "Hiểu khi nào unsafe cần thiết",
            "FFI với C libraries",
            "Viết safe abstraction over unsafe",
        ],
    },
    {
        "id": "rust-12-web-backend",
        "category_id": "rust",
        "name": "Web Backend với Axum / Actix",
        "description": "REST API với axum hoặc actix-web, middleware, authentication, sqlx, database.",
        "level": "advanced",
        "order": 12,
        "icon": "🌐",
        "estimated_hours": 16,
        "tags": ["rust", "axum", "actix", "rest-api", "sqlx"],
        "learning_outcomes": [
            "Xây dựng REST API với axum",
            "Middleware và error handling",
            "Database queries với sqlx",
        ],
    },
    {
        "id": "rust-13-systems",
        "category_id": "rust",
        "name": "Systems Programming với Rust",
        "description": "CLI tools, OS interaction, file system, processes, networking, performance.",
        "level": "expert",
        "order": 13,
        "icon": "🖥️",
        "estimated_hours": 16,
        "tags": ["rust", "systems", "cli", "performance"],
        "learning_outcomes": [
            "Xây dựng CLI tools với clap",
            "File system và process management",
            "Low-level networking",
        ],
    },
    {
        "id": "rust-14-wasm",
        "category_id": "rust",
        "name": "WebAssembly với Rust",
        "description": "wasm-bindgen, wasm-pack, Rust to WASM, calling JS from Rust, web performance.",
        "level": "advanced",
        "order": 14,
        "icon": "🕸️",
        "estimated_hours": 12,
        "tags": ["rust", "wasm", "webassembly", "wasm-pack"],
        "learning_outcomes": [
            "Compile Rust sang WASM",
            "Tích hợp với JavaScript",
            "Performance optimization",
        ],
    },
]

# ══════════════════════════════════════════════════════════════════
# TOPICS — GO
# ══════════════════════════════════════════════════════════════════
GO_TOPICS = [
    {
        "id": "go-01-basics",
        "category_id": "go",
        "name": "Go Cơ Bản",
        "description": "Cú pháp Go, kiểu dữ liệu, biến, constants, functions, packages.",
        "level": "beginner",
        "order": 1,
        "icon": "🐹",
        "estimated_hours": 8,
        "tags": ["go", "basics", "syntax"],
        "learning_outcomes": [
            "Cú pháp và cấu trúc chương trình Go",
            "Kiểu dữ liệu cơ bản",
            "Multiple return values",
        ],
    },
    {
        "id": "go-02-control-flow",
        "category_id": "go",
        "name": "Control Flow & Functions",
        "description": "if/else, switch, for loop (Go's only loop), defer, panic, recover.",
        "level": "beginner",
        "order": 2,
        "icon": "🔀",
        "estimated_hours": 6,
        "tags": ["go", "control-flow", "defer"],
        "learning_outcomes": [
            "Vòng lặp for trong Go",
            "defer/panic/recover pattern",
            "Variadic functions",
        ],
    },
    {
        "id": "go-03-structs-methods",
        "category_id": "go",
        "name": "Structs & Methods",
        "description": "Struct declaration, methods with receivers, embedded structs, tags.",
        "level": "beginner",
        "order": 3,
        "icon": "🏗️",
        "estimated_hours": 8,
        "tags": ["go", "structs", "methods"],
        "learning_outcomes": [
            "Khai báo struct và methods",
            "Pointer vs value receivers",
            "Struct embedding (composition)",
        ],
    },
    {
        "id": "go-04-interfaces",
        "category_id": "go",
        "name": "Interfaces & Polymorphism",
        "description": "Interface declaration, implicit implementation, empty interface, type assertions, type switch.",
        "level": "intermediate",
        "order": 4,
        "icon": "🎭",
        "estimated_hours": 10,
        "tags": ["go", "interfaces", "polymorphism"],
        "learning_outcomes": [
            "Định nghĩa và implement interface",
            "Duck typing trong Go",
            "Type assertion và type switch",
        ],
    },
    {
        "id": "go-05-error-handling",
        "category_id": "go",
        "name": "Error Handling",
        "description": "error interface, errors package, fmt.Errorf %w, sentinel errors, custom errors.",
        "level": "intermediate",
        "order": 5,
        "icon": "🚨",
        "estimated_hours": 6,
        "tags": ["go", "errors", "error-handling"],
        "learning_outcomes": [
            "Go error handling idioms",
            "Error wrapping với %w",
            "Custom error types",
        ],
    },
    {
        "id": "go-06-collections",
        "category_id": "go",
        "name": "Arrays, Slices & Maps",
        "description": "Arrays vs slices, make, append, copy, maps, deletion, iteration.",
        "level": "beginner",
        "order": 6,
        "icon": "📦",
        "estimated_hours": 8,
        "tags": ["go", "slices", "maps", "arrays"],
        "learning_outcomes": [
            "Slice internals và gotchas",
            "Map operations",
            "Functional patterns với slice",
        ],
    },
    {
        "id": "go-07-goroutines",
        "category_id": "go",
        "name": "Goroutines & Channels",
        "description": "go keyword, channels (buffered/unbuffered), select, WaitGroup, close.",
        "level": "intermediate",
        "order": 7,
        "icon": "⚡",
        "estimated_hours": 12,
        "tags": ["go", "goroutines", "channels", "concurrency"],
        "learning_outcomes": [
            "Spawn và synchronize goroutines",
            "Channel patterns (fan-out, pipeline)",
            "select statement",
        ],
    },
    {
        "id": "go-08-sync",
        "category_id": "go",
        "name": "Sync Package & Concurrency Patterns",
        "description": "Mutex, RWMutex, Once, Pool, WaitGroup, atomic, race detector.",
        "level": "advanced",
        "order": 8,
        "icon": "🔄",
        "estimated_hours": 10,
        "tags": ["go", "sync", "mutex", "race-condition"],
        "learning_outcomes": [
            "Tránh race conditions",
            "sync.Pool và sync.Once",
            "Dùng race detector",
        ],
    },
    {
        "id": "go-09-stdlib",
        "category_id": "go",
        "name": "Standard Library Essentials",
        "description": "fmt, io, bufio, os, filepath, json, time, net/http, strings, regexp.",
        "level": "intermediate",
        "order": 9,
        "icon": "📚",
        "estimated_hours": 10,
        "tags": ["go", "stdlib", "json", "http"],
        "learning_outcomes": [
            "JSON encode/decode",
            "File và I/O operations",
            "net/http server cơ bản",
        ],
    },
    {
        "id": "go-10-http-server",
        "category_id": "go",
        "name": "HTTP Server & Gin Framework",
        "description": "net/http, routing, middleware, Gin framework, JSON API, validation.",
        "level": "intermediate",
        "order": 10,
        "icon": "🌐",
        "estimated_hours": 12,
        "tags": ["go", "http", "gin", "rest-api"],
        "learning_outcomes": [
            "REST API với Gin",
            "Middleware pattern",
            "JSON request/response",
        ],
    },
    {
        "id": "go-11-database",
        "category_id": "go",
        "name": "Database với sqlx / GORM",
        "description": "database/sql, sqlx, GORM ORM, migrations, connection pooling, transactions.",
        "level": "intermediate",
        "order": 11,
        "icon": "🗄️",
        "estimated_hours": 12,
        "tags": ["go", "gorm", "sqlx", "database"],
        "learning_outcomes": [
            "CRUD với GORM",
            "Transactions và connection pool",
            "DB migrations",
        ],
    },
    {
        "id": "go-12-testing",
        "category_id": "go",
        "name": "Testing trong Go",
        "description": "testing package, table-driven tests, benchmarks, testify, mocking, coverage.",
        "level": "intermediate",
        "order": 12,
        "icon": "🧪",
        "estimated_hours": 8,
        "tags": ["go", "testing", "testify", "benchmarks"],
        "learning_outcomes": [
            "Table-driven tests",
            "Benchmark tests",
            "Mock interfaces",
        ],
    },
    {
        "id": "go-13-microservices",
        "category_id": "go",
        "name": "Microservices với Go",
        "description": "gRPC, Protocol Buffers, service discovery, Kubernetes deployment, observability.",
        "level": "advanced",
        "order": 13,
        "icon": "☁️",
        "estimated_hours": 18,
        "tags": ["go", "microservices", "grpc", "protobuf"],
        "learning_outcomes": [
            "gRPC service với protobuf",
            "Service-to-service communication",
            "Container deployment",
        ],
    },
    {
        "id": "go-14-cli-tools",
        "category_id": "go",
        "name": "CLI Tools với Cobra",
        "description": "cobra, viper, building CLI apps, flags & args, config files, cross-compilation.",
        "level": "intermediate",
        "order": 14,
        "icon": "🛠️",
        "estimated_hours": 8,
        "tags": ["go", "cli", "cobra", "viper"],
        "learning_outcomes": [
            "Xây dựng CLI với cobra",
            "Config với viper",
            "Cross-compile cho đa nền tảng",
        ],
    },
    {
        "id": "go-15-generics",
        "category_id": "go",
        "name": "Generics (Go 1.18+)",
        "description": "Type parameters, type constraints, generic functions, generic data structures.",
        "level": "advanced",
        "order": 15,
        "icon": "🔧",
        "estimated_hours": 8,
        "tags": ["go", "generics", "type-parameters"],
        "learning_outcomes": [
            "Viết generic functions",
            "Type constraints",
            "Generic collections",
        ],
    },
]


def main():
    print("=" * 60)
    print("Seeding categories and topics for: Java, C/C++, Rust, Go")
    print("=" * 60)

    # 1. Insert categories
    print("\n[1] Categories:")
    for cat in CATEGORIES:
        upsert_category(cat)

    # 2. Insert topics per language
    all_topics = [
        ("Java", JAVA_TOPICS),
        ("C/C++", CCPP_TOPICS),
        ("Rust", RUST_TOPICS),
        ("Go", GO_TOPICS),
    ]

    for lang_name, topics in all_topics:
        print(f"\n[2] Topics — {lang_name} ({len(topics)} topics):")
        for topic in topics:
            upsert_topic(topic)

    # 3. Summary
    print("\n" + "=" * 60)
    print("SUMMARY:")
    for cat in CATEGORIES:
        cid = cat["id"]
        topic_count = db.learning_topics.count_documents({"category_id": cid})
        cat_exists = db.learning_categories.find_one({"id": cid})
        print(f"  {cid}: category={'✅' if cat_exists else '❌'}, topics={topic_count}")
    print("=" * 60)
    print("Done!")


if __name__ == "__main__":
    main()
