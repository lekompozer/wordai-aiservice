"""
Generate 150 Community Subjects - 10 categories × 15 subjects each
Auto-generates seed data for StudyHub marketplace

Run: python generate_community_subjects_seed.py > setup_community_subjects.py
"""

SUBJECTS_DATA = {
    # 💻 Công nghệ thông tin (IT) - 15 subjects
    "it": [
        ("python-programming", "Python Programming", "Lập trình Python", "🐍"),
        (
            "javascript-programming",
            "JavaScript Programming",
            "Lập trình JavaScript",
            "📜",
        ),
        ("react-development", "React Development", "Phát triển React", "⚛️"),
        ("nodejs-development", "Node.js Development", "Phát triển Node.js", "🟢"),
        ("web-development", "Web Development", "Phát triển Web", "🌐"),
        ("data-science", "Data Science", "Khoa học Dữ liệu", "📊"),
        (
            "mobile-app-development",
            "Mobile App Development",
            "Phát triển Ứng dụng Di động",
            "📱",
        ),
        ("database-design", "Database Design", "Thiết kế Cơ sở Dữ liệu", "🗄️"),
        ("cloud-computing", "Cloud Computing", "Điện toán Đám mây", "☁️"),
        ("devops", "DevOps", "DevOps", "🔧"),
        ("cybersecurity", "Cybersecurity", "An ninh Mạng", "🔒"),
        (
            "artificial-intelligence",
            "Artificial Intelligence",
            "Trí tuệ Nhân tạo",
            "🤖",
        ),
        ("blockchain", "Blockchain Development", "Phát triển Blockchain", "⛓️"),
        ("game-development", "Game Development", "Phát triển Game", "🎮"),
        ("software-testing", "Software Testing", "Kiểm thử Phần mềm", "✅"),
    ],
    # 💼 Kinh doanh (BUSINESS) - 15 subjects
    "business": [
        ("marketing-fundamentals", "Marketing Fundamentals", "Cơ bản Marketing", "📊"),
        ("digital-marketing", "Digital Marketing", "Marketing Số", "💻"),
        ("entrepreneurship", "Entrepreneurship", "Khởi nghiệp", "🚀"),
        ("project-management", "Project Management", "Quản lý Dự án", "📋"),
        ("business-strategy", "Business Strategy", "Chiến lược Kinh doanh", "🎯"),
        ("sales-skills", "Sales Skills", "Kỹ năng Bán hàng", "💼"),
        ("customer-service", "Customer Service", "Dịch vụ Khách hàng", "🤝"),
        ("ecommerce", "E-Commerce", "Thương mại Điện tử", "🛒"),
        (
            "social-media-marketing",
            "Social Media Marketing",
            "Marketing Mạng Xã hội",
            "📱",
        ),
        ("content-marketing", "Content Marketing", "Marketing Nội dung", "✍️"),
        ("brand-management", "Brand Management", "Quản lý Thương hiệu", "🏷️"),
        ("business-analytics", "Business Analytics", "Phân tích Kinh doanh", "📈"),
        (
            "supply-chain-management",
            "Supply Chain Management",
            "Quản lý Chuỗi Cung ứng",
            "🚚",
        ),
        ("human-resources", "Human Resources", "Quản trị Nhân sự", "👥"),
        ("leadership", "Leadership", "Kỹ năng Lãnh đạo", "👔"),
    ],
    # 💰 Tài chính (FINANCE) - 15 subjects
    "finance": [
        ("personal-finance", "Personal Finance", "Tài chính Cá nhân", "💵"),
        ("investing", "Investing", "Đầu tư", "📈"),
        ("stock-market", "Stock Market", "Thị trường Chứng khoán", "📊"),
        ("cryptocurrency", "Cryptocurrency", "Tiền điện tử", "₿"),
        ("accounting", "Accounting", "Kế toán", "🧮"),
        ("financial-analysis", "Financial Analysis", "Phân tích Tài chính", "💹"),
        ("forex-trading", "Forex Trading", "Giao dịch Forex", "💱"),
        ("real-estate-investing", "Real Estate Investing", "Đầu tư Bất động sản", "🏠"),
        ("retirement-planning", "Retirement Planning", "Kế hoạch Hưu trí", "🏖️"),
        ("tax-planning", "Tax Planning", "Kế hoạch Thuế", "📝"),
        ("financial-modeling", "Financial Modeling", "Mô hình Tài chính", "🔢"),
        ("wealth-management", "Wealth Management", "Quản lý Tài sản", "💎"),
        ("insurance", "Insurance", "Bảo hiểm", "🛡️"),
        ("banking", "Banking", "Ngân hàng", "🏦"),
        ("economics", "Economics", "Kinh tế học", "📚"),
    ],
    # 🎓 Chứng chỉ (CERTIFICATE) - 15 subjects
    "certificate": [
        ("pmp-certification", "PMP Certification", "Chứng chỉ PMP", "📜"),
        ("aws-certification", "AWS Certification", "Chứng chỉ AWS", "☁️"),
        (
            "google-analytics",
            "Google Analytics Certification",
            "Chứng chỉ Google Analytics",
            "📊",
        ),
        ("cissp", "CISSP Certification", "Chứng chỉ CISSP", "🔒"),
        ("comptia", "CompTIA Certification", "Chứng chỉ CompTIA", "💻"),
        (
            "microsoft-certification",
            "Microsoft Certification",
            "Chứng chỉ Microsoft",
            "🪟",
        ),
        ("scrum-master", "Scrum Master Certification", "Chứng chỉ Scrum Master", "🏃"),
        ("six-sigma", "Six Sigma Certification", "Chứng chỉ Six Sigma", "📈"),
        ("cpa", "CPA Certification", "Chứng chỉ CPA", "🧮"),
        ("cfa", "CFA Certification", "Chứng chỉ CFA", "📊"),
        ("itil", "ITIL Certification", "Chứng chỉ ITIL", "🔧"),
        ("cisco", "Cisco Certification", "Chứng chỉ Cisco", "🌐"),
        ("oracle-certification", "Oracle Certification", "Chứng chỉ Oracle", "🗄️"),
        ("google-cloud", "Google Cloud Certification", "Chứng chỉ Google Cloud", "☁️"),
        ("azure-certification", "Azure Certification", "Chứng chỉ Azure", "🔷"),
    ],
    # 🌍 Ngôn ngữ (LANGUAGE) - 15 subjects
    "language": [
        ("english-speaking", "English Speaking", "Giao tiếp Tiếng Anh", "🗣️"),
        ("ielts-preparation", "IELTS Preparation", "Luyện thi IELTS", "📚"),
        ("toeic-preparation", "TOEIC Preparation", "Luyện thi TOEIC", "📝"),
        ("toefl-preparation", "TOEFL Preparation", "Luyện thi TOEFL", "📖"),
        ("chinese-language", "Chinese Language", "Tiếng Trung", "🇨🇳"),
        ("japanese-language", "Japanese Language", "Tiếng Nhật", "🇯🇵"),
        ("korean-language", "Korean Language", "Tiếng Hàn", "🇰🇷"),
        ("french-language", "French Language", "Tiếng Pháp", "🇫🇷"),
        ("german-language", "German Language", "Tiếng Đức", "🇩🇪"),
        ("spanish-language", "Spanish Language", "Tiếng Tây Ban Nha", "🇪🇸"),
        ("english-grammar", "English Grammar", "Ngữ pháp Tiếng Anh", "📖"),
        ("business-english", "Business English", "Tiếng Anh Thương mại", "💼"),
        ("english-writing", "English Writing", "Viết Tiếng Anh", "✍️"),
        ("pronunciation", "Pronunciation", "Phát âm", "🎤"),
        ("vocabulary-building", "Vocabulary Building", "Xây dựng Từ vựng", "📚"),
    ],
    # 🌱 Phát triển bản thân (PERSONAL DEVELOPMENT) - 15 subjects
    "personal-development": [
        ("time-management", "Time Management", "Quản lý Thời gian", "⏰"),
        ("productivity", "Productivity", "Năng suất", "⚡"),
        ("goal-setting", "Goal Setting", "Đặt mục tiêu", "🎯"),
        ("mindfulness", "Mindfulness", "Chánh niệm", "🧘"),
        ("meditation", "Meditation", "Thiền", "🧘‍♂️"),
        ("public-speaking", "Public Speaking", "Nói trước Công chúng", "🎤"),
        ("confidence-building", "Confidence Building", "Xây dựng Tự tin", "💪"),
        ("critical-thinking", "Critical Thinking", "Tư duy Phản biện", "🤔"),
        ("emotional-intelligence", "Emotional Intelligence", "Trí tuệ Cảm xúc", "❤️"),
        ("stress-management", "Stress Management", "Quản lý Căng thẳng", "😌"),
        ("memory-improvement", "Memory Improvement", "Cải thiện Trí nhớ", "🧠"),
        ("speed-reading", "Speed Reading", "Đọc nhanh", "📖"),
        ("creativity", "Creativity", "Sáng tạo", "💡"),
        ("motivation", "Motivation", "Động lực", "🔥"),
        ("self-discipline", "Self-Discipline", "Kỷ luật Bản thân", "🎖️"),
    ],
    # 🎨 Lối sống (LIFESTYLE) - 15 subjects
    "lifestyle": [
        ("graphic-design", "Graphic Design", "Thiết kế Đồ họa", "🎨"),
        ("photography", "Photography", "Nhiếp ảnh", "📷"),
        ("video-editing", "Video Editing", "Dựng Video", "🎬"),
        ("music-production", "Music Production", "Sản xuất Âm nhạc", "🎵"),
        ("cooking", "Cooking", "Nấu ăn", "🍳"),
        ("fitness", "Fitness", "Thể dục", "💪"),
        ("yoga", "Yoga", "Yoga", "🧘"),
        ("nutrition", "Nutrition", "Dinh dưỡng", "🥗"),
        ("interior-design", "Interior Design", "Thiết kế Nội thất", "🏠"),
        ("fashion-design", "Fashion Design", "Thiết kế Thời trang", "👗"),
        ("gardening", "Gardening", "Làm vườn", "🌱"),
        ("travel-planning", "Travel Planning", "Lập kế hoạch Du lịch", "✈️"),
        ("pet-care", "Pet Care", "Chăm sóc Thú cưng", "🐕"),
        ("home-organization", "Home Organization", "Tổ chức Nhà cửa", "🏡"),
        ("sustainable-living", "Sustainable Living", "Sống Bền vững", "♻️"),
    ],
    # 📚 Học thuật (ACADEMICS) - 15 subjects
    "academics": [
        ("toan-12", "Toán 12", "Toán học lớp 12", "📐"),
        ("vat-ly-12", "Vật lý 12", "Vật lý lớp 12", "⚗️"),
        ("hoa-hoc-12", "Hóa học 12", "Hóa học lớp 12", "🧪"),
        ("tieng-anh-12", "Tiếng Anh 12", "Tiếng Anh lớp 12", "🇬🇧"),
        ("van-hoc-12", "Văn học 12", "Văn học lớp 12", "📖"),
        ("lich-su-12", "Lịch sử 12", "Lịch sử lớp 12", "📜"),
        ("dia-ly-12", "Địa lý 12", "Địa lý lớp 12", "🌍"),
        ("sinh-hoc-12", "Sinh học 12", "Sinh học lớp 12", "🔬"),
        ("gdcd-12", "GDCD 12", "Giáo dục Công dân lớp 12", "⚖️"),
        ("sat-preparation", "SAT Preparation", "Luyện thi SAT", "📝"),
        ("act-preparation", "ACT Preparation", "Luyện thi ACT", "📚"),
        ("gre-preparation", "GRE Preparation", "Luyện thi GRE", "🎓"),
        ("gmat-preparation", "GMAT Preparation", "Luyện thi GMAT", "📊"),
        ("college-admission", "College Admission", "Tuyển sinh Đại học", "🏫"),
        ("essay-writing", "Essay Writing", "Viết Luận", "✍️"),
    ],
    # 🔬 Khoa học (SCIENCE) - 15 subjects
    "science": [
        ("physics", "Physics", "Vật lý", "⚛️"),
        ("chemistry", "Chemistry", "Hóa học", "🧪"),
        ("biology", "Biology", "Sinh học", "🔬"),
        ("astronomy", "Astronomy", "Thiên văn học", "🌌"),
        ("geology", "Geology", "Địa chất học", "🪨"),
        ("environmental-science", "Environmental Science", "Khoa học Môi trường", "🌍"),
        ("marine-biology", "Marine Biology", "Sinh học Biển", "🌊"),
        ("botany", "Botany", "Thực vật học", "🌿"),
        ("zoology", "Zoology", "Động vật học", "🦁"),
        ("genetics", "Genetics", "Di truyền học", "🧬"),
        ("neuroscience", "Neuroscience", "Khoa học Thần kinh", "🧠"),
        ("psychology", "Psychology", "Tâm lý học", "🧠"),
        ("anatomy", "Anatomy", "Giải phẫu học", "🫁"),
        ("microbiology", "Microbiology", "Vi sinh vật học", "🦠"),
        ("biochemistry", "Biochemistry", "Hóa sinh", "⚗️"),
    ],
    # 🛠️ Kỹ năng (SKILLS) - 15 subjects
    "skills": [
        ("excel-skills", "Excel Skills", "Kỹ năng Excel", "📊"),
        ("powerpoint", "PowerPoint", "PowerPoint", "📽️"),
        ("word-processing", "Word Processing", "Soạn thảo Văn bản", "📝"),
        ("typing-speed", "Typing Speed", "Tốc độ Đánh máy", "⌨️"),
        ("data-entry", "Data Entry", "Nhập liệu", "💻"),
        ("customer-support", "Customer Support", "Hỗ trợ Khách hàng", "🎧"),
        ("negotiation", "Negotiation", "Đàm phán", "🤝"),
        ("conflict-resolution", "Conflict Resolution", "Giải quyết Xung đột", "⚖️"),
        ("teamwork", "Teamwork", "Làm việc Nhóm", "👥"),
        ("problem-solving", "Problem Solving", "Giải quyết Vấn đề", "🧩"),
        ("decision-making", "Decision Making", "Ra quyết định", "🎯"),
        ("networking", "Networking", "Xây dựng Mạng lưới", "🌐"),
        ("communication-skills", "Communication Skills", "Kỹ năng Giao tiếp", "💬"),
        ("presentation-skills", "Presentation Skills", "Kỹ năng Thuyết trình", "🎤"),
        ("writing-skills", "Writing Skills", "Kỹ năng Viết", "✍️"),
    ],
}

print('"""')
print("Setup Community Subjects - Seed data for StudyHub marketplace")
print("Creates standardized subject topics that creators can publish courses to")
print("")
print("Run: python setup_community_subjects.py")
print('"""')
print("")
print("from src.database.db_manager import DBManager")
print("from datetime import datetime")
print("import logging")
print("")
print("logging.basicConfig(level=logging.INFO)")
print("logger = logging.getLogger(__name__)")
print("")
print("")
print("COMMUNITY_SUBJECTS = [")

order = 0
for category, subjects in SUBJECTS_DATA.items():
    category_names = {
        "it": "💻 CÔNG NGHỆ THÔNG TIN (IT)",
        "business": "💼 KINH DOANH (BUSINESS)",
        "finance": "💰 TÀI CHÍNH (FINANCE)",
        "certificate": "🎓 CHỨNG CHỈ (CERTIFICATE)",
        "language": "🌍 NGÔN NGỮ (LANGUAGE)",
        "personal-development": "🌱 PHÁT TRIỂN BẢN THÂN (PERSONAL DEVELOPMENT)",
        "lifestyle": "🎨 LỐI SỐNG (LIFESTYLE)",
        "academics": "📚 HỌC THUẬT (ACADEMICS)",
        "science": "🔬 KHOA HỌC (SCIENCE)",
        "skills": "🛠️ KỸ NĂNG (SKILLS)",
    }

    print(f"    # ==================== {category_names[category]} ====================")

    for idx, (slug, title, title_vi, icon) in enumerate(subjects, 1):
        order += 1
        is_featured = (
            "True" if idx <= 5 else "False"
        )  # First 5 in each category are featured

        print("    {")
        print(f'        "_id": "{slug}",')
        print(f'        "slug": "{slug}",')
        print(f'        "title": "{title}",')
        print(f'        "title_vi": "{title_vi}",')
        print(f'        "description": "Learn {title.lower()}",')
        print(f'        "description_vi": "Học {title_vi}",')
        print(f'        "category": "{category}",')
        print(f'        "icon": "{icon}",')
        print(f'        "keywords": ["{slug.replace("-", " ")}", "{title.lower()}"],')
        print(f'        "meta_description": "Master {title.lower()}",')
        print(f'        "total_courses": 0,')
        print(f'        "total_students": 0,')
        print(f'        "avg_rating": 0.0,')
        print(f'        "is_featured": {is_featured},')
        print(f'        "display_order": {order},')
        print("    },")

    print("")

print("]")
print("")
print("")
print("def setup_community_subjects():")
print('    """Seed community subjects collection"""')
print("    try:")
print("        db_manager = DBManager()")
print("        db = db_manager.db")
print('        collection = db["community_subjects"]')
print("")
print("        # Add timestamps")
print("        now = datetime.utcnow()")
print("        for subject in COMMUNITY_SUBJECTS:")
print('            subject["created_at"] = now')
print('            subject["updated_at"] = now')
print("")
print("        # Drop existing collection (if re-seeding)")
print("        collection.drop()")
print('        logger.info("Dropped existing community_subjects collection")')
print("")
print("        # Insert subjects")
print("        result = collection.insert_many(COMMUNITY_SUBJECTS)")
print(
    '        logger.info(f"✅ Inserted {len(result.inserted_ids)} community subjects")'
)
print("")
print("        # Create indexes")
print('        logger.info("Creating indexes...")')
print('        collection.create_index([("slug", 1)], unique=True)')
print('        collection.create_index([("category", 1)])')
print('        collection.create_index([("title", "text"), ("title_vi", "text")])')
print('        collection.create_index([("total_courses", -1)])')
print('        collection.create_index([("total_students", -1)])')
print('        collection.create_index([("is_featured", -1), ("display_order", 1)])')
print('        logger.info("✅ Created indexes for community_subjects")')
print("")
print("        # Print summary")
print('        logger.info("\\n" + "=" * 60)')
print('        logger.info("SUMMARY BY CATEGORY:")')
print('        logger.info("=" * 60)')
print('        categories = ["it", "business", "finance", "certificate", "language",')
print(
    '                     "personal-development", "lifestyle", "academics", "science", "skills"]'
)
print("        for cat in categories:")
print(
    '            count = len([s for s in COMMUNITY_SUBJECTS if s["category"] == cat])'
)
print('            logger.info(f"  {cat.upper()}: {count} subjects")')
print("")
print('        logger.info("\\n✅ Community subjects setup completed!")')
print('        logger.info(f"Total subjects: {len(COMMUNITY_SUBJECTS)}")')
print("")
print("    except Exception as e:")
print('        logger.error(f"❌ Error setting up community subjects: {e}")')
print("        raise")
print("")
print("")
print('if __name__ == "__main__":')
print("    setup_community_subjects()")
