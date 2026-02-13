"""
HARD-CODED 600 CONVERSATIONS DATA - COMPACT VERSION
30 Topics × 20 Conversations = 600 total
No duplication, no parsing - just arrays!
"""

# 30 Topics with metadata
TOPICS = [
    # BEGINNER (Topics 1-10)
    {
        "level": "beginner",
        "number": 1,
        "slug": "greetings_introductions",
        "en": "Greetings & Introductions",
        "vi": "Chào hỏi & Giới thiệu",
    },
    {
        "level": "beginner",
        "number": 2,
        "slug": "daily_routines",
        "en": "Daily Routines",
        "vi": "Thói quen hàng ngày",
    },
    {
        "level": "beginner",
        "number": 3,
        "slug": "family_friends",
        "en": "Family & Friends",
        "vi": "Gia đình & Bạn bè",
    },
    {
        "level": "beginner",
        "number": 4,
        "slug": "food_drinks",
        "en": "Food & Drinks",
        "vi": "Đồ ăn & Thức uống",
    },
    {
        "level": "beginner",
        "number": 5,
        "slug": "shopping",
        "en": "Shopping",
        "vi": "Mua sắm",
    },
    {
        "level": "beginner",
        "number": 6,
        "slug": "weather_seasons",
        "en": "Weather & Seasons",
        "vi": "Thời tiết & Mùa",
    },
    {
        "level": "beginner",
        "number": 7,
        "slug": "transportation",
        "en": "Transportation",
        "vi": "Phương tiện di chuyển",
    },
    {
        "level": "beginner",
        "number": 8,
        "slug": "time_dates",
        "en": "Time & Dates",
        "vi": "Thời gian & Ngày tháng",
    },
    {
        "level": "beginner",
        "number": 9,
        "slug": "colors_numbers",
        "en": "Colors & Numbers",
        "vi": "Màu sắc & Số",
    },
    {
        "level": "beginner",
        "number": 10,
        "slug": "hobbies_interests",
        "en": "Hobbies & Interests",
        "vi": "Sở thích & Quan tâm",
    },
    # INTERMEDIATE (Topics 11-20)
    {
        "level": "intermediate",
        "number": 11,
        "slug": "work_office",
        "en": "Work & Office",
        "vi": "Công việc & Văn phòng",
    },
    {
        "level": "intermediate",
        "number": 12,
        "slug": "education_learning",
        "en": "Education & Learning",
        "vi": "Giáo dục & Học tập",
    },
    {
        "level": "intermediate",
        "number": 13,
        "slug": "health_fitness",
        "en": "Health & Fitness",
        "vi": "Sức khỏe & Thể dục",
    },
    {
        "level": "intermediate",
        "number": 14,
        "slug": "travel_vacation",
        "en": "Travel & Vacation",
        "vi": "Du lịch & Nghỉ mát",
    },
    {
        "level": "intermediate",
        "number": 15,
        "slug": "technology",
        "en": "Technology",
        "vi": "Công nghệ",
    },
    {
        "level": "intermediate",
        "number": 16,
        "slug": "entertainment",
        "en": "Entertainment",
        "vi": "Giải trí",
    },
    {
        "level": "intermediate",
        "number": 17,
        "slug": "sports",
        "en": "Sports",
        "vi": "Thể thao",
    },
    {
        "level": "intermediate",
        "number": 18,
        "slug": "home_living",
        "en": "Home & Living",
        "vi": "Nhà ở & Cuộc sống",
    },
    {
        "level": "intermediate",
        "number": 19,
        "slug": "environment",
        "en": "Environment",
        "vi": "Môi trường",
    },
    {
        "level": "intermediate",
        "number": 20,
        "slug": "culture_customs",
        "en": "Culture & Customs",
        "vi": "Văn hóa & Phong tục",
    },
    # ADVANCED (Topics 21-30)
    {
        "level": "advanced",
        "number": 21,
        "slug": "business_economics",
        "en": "Business & Economics",
        "vi": "Kinh doanh & Kinh tế",
    },
    {
        "level": "advanced",
        "number": 22,
        "slug": "politics_society",
        "en": "Politics & Society",
        "vi": "Chính trị & Xã hội",
    },
    {
        "level": "advanced",
        "number": 23,
        "slug": "science_research",
        "en": "Science & Research",
        "vi": "Khoa học & Nghiên cứu",
    },
    {
        "level": "advanced",
        "number": 24,
        "slug": "arts_literature",
        "en": "Arts & Literature",
        "vi": "Nghệ thuật & Văn học",
    },
    {
        "level": "advanced",
        "number": 25,
        "slug": "philosophy_ethics",
        "en": "Philosophy & Ethics",
        "vi": "Triết học & Đạo đức",
    },
    {
        "level": "advanced",
        "number": 26,
        "slug": "global_issues",
        "en": "Global Issues",
        "vi": "Vấn đề toàn cầu",
    },
    {
        "level": "advanced",
        "number": 27,
        "slug": "innovation",
        "en": "Innovation",
        "vi": "Đổi mới sáng tạo",
    },
    {
        "level": "advanced",
        "number": 28,
        "slug": "psychology",
        "en": "Psychology",
        "vi": "Tâm lý học",
    },
    {
        "level": "advanced",
        "number": 29,
        "slug": "history",
        "en": "History",
        "vi": "Lịch sử",
    },
    {
        "level": "advanced",
        "number": 30,
        "slug": "future_trends",
        "en": "Future & Trends",
        "vi": "Tương lai & Xu hướng",
    },
]

# Conversations - just index + titles (no duplication!)
CONVERSATIONS = [
    # Topic 1: Greetings & Introductions
    [
        [1, "Hello, How Are You?", "Xin chào, Bạn khỏe không?"],
        [2, "Nice to Meet You", "Rất vui được gặp bạn"],
        [3, "What's Your Name?", "Tên bạn là gì?"],
        [4, "Where Are You From?", "Bạn đến từ đâu?"],
        [5, "Good Morning!", "Chào buổi sáng!"],
        [6, "See You Later", "Hẹn gặp lại"],
        [7, "How Old Are You?", "Bạn bao nhiêu tuổi?"],
        [8, "Introducing a Friend", "Giới thiệu bạn bè"],
        [9, "First Day at School", "Ngày đầu tiên đi học"],
        [10, "Meeting a Neighbor", "Gặp gỡ hàng xóm"],
        [11, "At a Party", "Tại bữa tiệc"],
        [12, "Long Time No See", "Lâu rồi không gặp"],
        [13, "Goodbye and Take Care", "Tạm biệt và giữ gìn sức khỏe"],
        [14, "Asking About Someone's Day", "Hỏi thăm ngày của ai đó"],
        [15, "Making Small Talk", "Trò chuyện phiếm"],
        [16, "Breaking the Ice", "Phá vỡ sự ngại ngùng"],
        [17, "Formal Introduction", "Giới thiệu trang trọng"],
        [18, "Casual Greeting", "Chào hỏi thân mật"],
        [19, "Saying Thank You", "Nói cảm ơn"],
        [20, "Apologizing", "Xin lỗi"],
    ],
    # Topic 2: Daily Routines
    [
        [1, "Morning Routine", "Thói quen buổi sáng"],
        [2, "Getting Ready for Work", "Chuẩn bị đi làm"],
        [3, "Breakfast Time", "Giờ ăn sáng"],
        [4, "Daily Commute", "Đi lại hàng ngày"],
        [5, "Lunch Break", "Giờ nghỉ trưa"],
        [6, "After Work", "Sau giờ làm"],
        [7, "Evening Routine", "Thói quen buổi tối"],
        [8, "Bedtime", "Giờ đi ngủ"],
        [9, "Weekend Plans", "Kế hoạch cuối tuần"],
        [10, "Doing Chores", "Làm việc nhà"],
        [11, "Exercising", "Tập thể dục"],
        [12, "Studying", "Học bài"],
        [13, "Cooking Dinner", "Nấu bữa tối"],
        [14, "Watching TV", "Xem tivi"],
        [15, "Taking a Shower", "Tắm rửa"],
        [16, "Getting Dressed", "Mặc quần áo"],
        [17, "Making the Bed", "Dọn giường"],
        [18, "Checking Emails", "Kiểm tra email"],
        [19, "Reading Before Bed", "Đọc sách trước khi ngủ"],
        [20, "Setting an Alarm", "Cài báo thức"],
    ],
    # Topic 3: Family & Friends
    [
        [1, "My Family", "Gia đình tôi"],
        [2, "My Best Friend", "Bạn thân của tôi"],
        [3, "Family Dinner", "Bữa tối gia đình"],
        [4, "Talking About Siblings", "Nói về anh chị em"],
        [5, "My Parents", "Bố mẹ tôi"],
        [6, "Playing with Friends", "Chơi với bạn bè"],
        [7, "Family Photo", "Ảnh gia đình"],
        [8, "Visiting Relatives", "Thăm họ hàng"],
        [9, "Making New Friends", "Kết bạn mới"],
        [10, "Birthday Party", "Tiệc sinh nhật"],
        [11, "Family Traditions", "Truyền thống gia đình"],
        [12, "Childhood Friends", "Bạn thời thơ ấu"],
        [13, "My Grandparents", "Ông bà tôi"],
        [14, "Friend in Need", "Bạn cần giúp đỡ"],
        [15, "Family Vacation", "Kỳ nghỉ gia đình"],
        [16, "School Friends", "Bạn học"],
        [17, "Family Reunion", "Họp mặt gia đình"],
        [18, "Best Friend Forever", "Bạn thân suốt đời"],
        [19, "Helping at Home", "Giúp việc nhà"],
        [20, "Friendship Advice", "Lời khuyên về tình bạn"],
    ],
    # Topic 4: Food & Drinks
    [
        [1, "Favorite Food", "Món ăn yêu thích"],
        [2, "At a Restaurant", "Tại nhà hàng"],
        [3, "Ordering Coffee", "Gọi cà phê"],
        [4, "Healthy Eating", "Ăn uống lành mạnh"],
        [5, "Making a Sandwich", "Làm bánh mì"],
        [6, "Fruit and Vegetables", "Hoa quả và rau"],
        [7, "Dessert Time", "Giờ tráng miệng"],
        [8, "Fast Food", "Đồ ăn nhanh"],
        [9, "Traditional Dishes", "Món ăn truyền thống"],
        [10, "Cooking Together", "Nấu ăn cùng nhau"],
        [11, "At the Bakery", "Tại tiệm bánh"],
        [12, "Trying New Food", "Thử món mới"],
        [13, "Grocery Shopping", "Mua thực phẩm"],
        [14, "Spicy Food", "Đồ ăn cay"],
        [15, "Street Food", "Ăn vặt đường phố"],
        [16, "Meal Planning", "Lên thực đơn"],
        [17, "Allergies and Diet", "Dị ứng và chế độ ăn"],
        [18, "Cooking Recipe", "Công thức nấu ăn"],
        [19, "Table Manners", "Phép lịch sự bàn ăn"],
        [20, "Food Preferences", "Sở thích ẩm thực"],
    ],
    # Topic 5: Shopping
    [
        [1, "At the Mall", "Tại trung tâm mua sắm"],
        [2, "Buying Clothes", "Mua quần áo"],
        [3, "How Much is It?", "Cái này giá bao nhiêu?"],
        [4, "Window Shopping", "Ngắm đồ"],
        [5, "Sales and Discounts", "Giảm giá"],
        [6, "Online Shopping", "Mua sắm online"],
        [7, "Trying on Clothes", "Thử quần áo"],
        [8, "Payment Methods", "Phương thức thanh toán"],
        [9, "Shopping List", "Danh sách mua sắm"],
        [10, "At the Supermarket", "Tại siêu thị"],
        [11, "Gift Shopping", "Mua quà"],
        [12, "Bargaining", "Trả giá"],
        [13, "Return and Exchange", "Đổi trả hàng"],
        [14, "Shopping for Shoes", "Mua giày"],
        [15, "Boutique Shopping", "Mua sắm cửa hàng nhỏ"],
        [16, "Electronics Store", "Cửa hàng điện tử"],
        [17, "Bookstore Visit", "Ghé hiệu sách"],
        [18, "Impulse Buying", "Mua theo cảm tính"],
        [19, "Shopping Budget", "Ngân sách mua sắm"],
        [20, "Customer Service", "Dịch vụ khách hàng"],
    ],
    # Topic 6: Weather & Seasons
    [
        [1, "What's the Weather?", "Thời tiết thế nào?"],
        [2, "Sunny Day", "Ngày nắng đẹp"],
        [3, "Rainy Season", "Mùa mưa"],
        [4, "Cold Winter", "Mùa đông lạnh"],
        [5, "Spring Flowers", "Hoa mùa xuân"],
        [6, "Summer Vacation", "Nghỉ hè"],
        [7, "Autumn Colors", "Màu sắc mùa thu"],
        [8, "Snowy Weather", "Trời có tuyết"],
        [9, "Hot and Humid", "Nóng và ẩm"],
        [10, "Weather Forecast", "Dự báo thời tiết"],
        [11, "Windy Day", "Ngày nhiều gió"],
        [12, "Cloudy Skies", "Trời nhiều mây"],
        [13, "Temperature Changes", "Thay đổi nhiệt độ"],
        [14, "Favorite Season", "Mùa yêu thích"],
        [15, "Storm Warning", "Cảnh báo bão"],
        [16, "Perfect Weather", "Thời tiết hoàn hảo"],
        [17, "Seasonal Activities", "Hoạt động theo mùa"],
        [18, "Climate Differences", "Khác biệt khí hậu"],
        [19, "Dressing for Weather", "Mặc đồ theo thời tiết"],
        [20, "Weather Small Talk", "Nói chuyện về thời tiết"],
    ],
    # Topic 7: Transportation
    [
        [1, "Taking the Bus", "Đi xe buýt"],
        [2, "At the Train Station", "Tại ga tàu"],
        [3, "Riding a Bike", "Đi xe đạp"],
        [4, "Taxi or Uber", "Taxi hoặc Uber"],
        [5, "Driving a Car", "Lái xe ô tô"],
        [6, "Subway System", "Hệ thống tàu điện ngầm"],
        [7, "Walking to School", "Đi bộ đến trường"],
        [8, "Airport Check-in", "Làm thủ tục sân bay"],
        [9, "Traffic Jam", "Tắc đường"],
        [10, "Public Transport", "Phương tiện công cộng"],
        [11, "Parking Problems", "Vấn đề đỗ xe"],
        [12, "Road Trip", "Chuyến đi đường bộ"],
        [13, "Motorcycle Ride", "Đi xe máy"],
        [14, "Ferry Crossing", "Đi phà"],
        [15, "Commute Time", "Thời gian di chuyển"],
        [16, "Transportation Apps", "Ứng dụng di chuyển"],
        [17, "Carpooling", "Đi chung xe"],
        [18, "Getting Lost", "Bị lạc đường"],
        [19, "Transportation Safety", "An toàn giao thông"],
        [20, "Future of Transport", "Tương lai giao thông"],
    ],
    # Topic 8: Time & Dates
    [
        [1, "What Time is It?", "Mấy giờ rồi?"],
        [2, "Days of the Week", "Các ngày trong tuần"],
        [3, "Months and Years", "Tháng và năm"],
        [4, "Making Appointments", "Hẹn gặp"],
        [5, "My Birthday", "Sinh nhật tôi"],
        [6, "Daily Schedule", "Lịch trình hàng ngày"],
        [7, "Being Late", "Đến muộn"],
        [8, "Public Holidays", "Ngày lễ"],
        [9, "Calendar Planning", "Lên lịch"],
        [10, "Time Zones", "Múi giờ"],
        [11, "Past and Future", "Quá khứ và tương lai"],
        [12, "Telling Time", "Xem giờ"],
        [13, "Seasons and Months", "Mùa và tháng"],
        [14, "Anniversary", "Ngày kỷ niệm"],
        [15, "Time Management", "Quản lý thời gian"],
        [16, "Punctuality", "Đúng giờ"],
        [17, "Historical Dates", "Ngày lịch sử"],
        [18, "Duration and Period", "Thời lượng và giai đoạn"],
        [19, "Deadline Pressure", "Áp lực deadline"],
        [20, "Time Expressions", "Cách diễn đạt thời gian"],
    ],
    # Topic 9: Colors & Numbers
    [
        [1, "Favorite Color", "Màu yêu thích"],
        [2, "Counting Numbers", "Đếm số"],
        [3, "Rainbow Colors", "Màu cầu vồng"],
        [4, "Big Numbers", "Số lớn"],
        [5, "Color Meanings", "Ý nghĩa màu sắc"],
        [6, "Phone Numbers", "Số điện thoại"],
        [7, "Mixing Colors", "Trộn màu"],
        [8, "Age and Numbers", "Tuổi và số"],
        [9, "Color Preferences", "Sở thích màu sắc"],
        [10, "Math Basics", "Toán cơ bản"],
        [11, "Describing Colors", "Mô tả màu sắc"],
        [12, "Prices and Money", "Giá cả và tiền"],
        [13, "Colors in Nature", "Màu sắc thiên nhiên"],
        [14, "Statistics and Numbers", "Thống kê và số liệu"],
        [15, "Color Combinations", "Phối màu"],
        [16, "Fractions and Decimals", "Phân số và số thập phân"],
        [17, "Colors and Moods", "Màu sắc và tâm trạng"],
        [18, "Measurements", "Đo lường"],
        [19, "Fashion Colors", "Màu thời trang"],
        [20, "Lucky Numbers", "Số may mắn"],
    ],
    # Topic 10: Hobbies & Interests
    [
        [1, "My Hobby", "Sở thích của tôi"],
        [2, "Playing Sports", "Chơi thể thao"],
        [3, "Reading Books", "Đọc sách"],
        [4, "Listening to Music", "Nghe nhạc"],
        [5, "Painting and Drawing", "Vẽ tranh"],
        [6, "Playing Games", "Chơi game"],
        [7, "Photography", "Nhiếp ảnh"],
        [8, "Gardening", "Làm vườn"],
        [9, "Collecting Things", "Sưu tầm đồ"],
        [10, "Dancing", "Khiêu vũ"],
        [11, "Learning Languages", "Học ngôn ngữ"],
        [12, "Playing Instruments", "Chơi nhạc cụ"],
        [13, "Outdoor Activities", "Hoạt động ngoài trời"],
        [14, "Crafts and DIY", "Thủ công và tự làm"],
        [15, "Watching Movies", "Xem phim"],
        [16, "Traveling", "Du lịch"],
        [17, "Cooking as Hobby", "Nấu ăn như sở thích"],
        [18, "Writing Stories", "Viết truyện"],
        [19, "Board Games", "Trò chơi bàn"],
        [20, "Trying New Hobbies", "Thử sở thích mới"],
    ],
    # Topic 11: Work & Office
    [
        [1, "Job Interview", "Phỏng vấn xin việc"],
        [2, "Office Routine", "Thói quen văn phòng"],
        [3, "Meeting Schedule", "Lịch họp"],
        [4, "Team Collaboration", "Làm việc nhóm"],
        [5, "Deadline Stress", "Căng thẳng deadline"],
        [6, "Coffee Break", "Giờ nghỉ cà phê"],
        [7, "Work-Life Balance", "Cân bằng công việc"],
        [8, "Performance Review", "Đánh giá hiệu suất"],
        [9, "Office Supplies", "Đồ dùng văn phòng"],
        [10, "Client Presentation", "Thuyết trình khách hàng"],
        [11, "Remote Working", "Làm việc từ xa"],
        [12, "Career Goals", "Mục tiêu nghề nghiệp"],
        [13, "Office Politics", "Chính trị văn phòng"],
        [14, "Business Trip", "Công tác"],
        [15, "Promotion Discussion", "Bàn về thăng chức"],
        [16, "Email Etiquette", "Phép lịch sự email"],
        [17, "Project Management", "Quản lý dự án"],
        [18, "Networking Event", "Sự kiện kết nối"],
        [19, "Resignation Letter", "Thư từ chức"],
        [20, "Office Culture", "Văn hóa công ty"],
    ],
    # Topic 12: Education & Learning
    [
        [1, "First Day of Class", "Ngày đầu tiên lớp học"],
        [2, "Homework Help", "Giúp bài tập"],
        [3, "Exam Preparation", "Chuẩn bị thi"],
        [4, "Study Group", "Nhóm học tập"],
        [5, "Library Visit", "Đi thư viện"],
        [6, "Teacher Meeting", "Gặp giáo viên"],
        [7, "School Subjects", "Môn học"],
        [8, "Online Learning", "Học trực tuyến"],
        [9, "Class Project", "Dự án lớp"],
        [10, "Student Exchange", "Trao đổi sinh viên"],
        [11, "Graduation Day", "Ngày tốt nghiệp"],
        [12, "Study Abroad", "Du học"],
        [13, "University Life", "Đời sống đại học"],
        [14, "Learning Methods", "Phương pháp học"],
        [15, "Academic Success", "Thành công học tập"],
        [16, "Scholarship Application", "Xin học bổng"],
        [17, "Campus Tour", "Tham quan trường"],
        [18, "Research Paper", "Bài nghiên cứu"],
        [19, "Education System", "Hệ thống giáo dục"],
        [20, "Lifelong Learning", "Học suốt đời"],
    ],
    # Topic 13: Health & Fitness
    [
        [1, "Doctor's Appointment", "Hẹn bác sĩ"],
        [2, "Gym Workout", "Tập gym"],
        [3, "Healthy Habits", "Thói quen lành mạnh"],
        [4, "Common Cold", "Cảm lạnh"],
        [5, "Running Routine", "Thói quen chạy bộ"],
        [6, "Nutrition Tips", "Lời khuyên dinh dưỡng"],
        [7, "Yoga Class", "Lớp yoga"],
        [8, "Medical Check-up", "Kiểm tra sức khỏe"],
        [9, "Mental Health", "Sức khỏe tinh thần"],
        [10, "Sports Injury", "Chấn thương thể thao"],
        [11, "Sleep Problems", "Vấn đề giấc ngủ"],
        [12, "Weight Management", "Quản lý cân nặng"],
        [13, "Pharmacy Visit", "Đi nhà thuốc"],
        [14, "Meditation Practice", "Thực hành thiền"],
        [15, "Fitness Goals", "Mục tiêu thể hình"],
        [16, "Hospital Experience", "Trải nghiệm bệnh viện"],
        [17, "Wellness Routine", "Thói quen chăm sóc"],
        [18, "Alternative Medicine", "Y học cổ truyền"],
        [19, "Marathon Training", "Luyện tập marathon"],
        [20, "Health Insurance", "Bảo hiểm y tế"],
    ],
    # Topic 14: Travel & Vacation
    [
        [1, "Planning a Trip", "Lên kế hoạch du lịch"],
        [2, "At the Hotel", "Tại khách sạn"],
        [3, "Tourist Attractions", "Điểm du lịch"],
        [4, "Packing Luggage", "Đóng gói hành lý"],
        [5, "Beach Vacation", "Nghỉ mát biển"],
        [6, "City Tour", "Tour thành phố"],
        [7, "Mountain Hiking", "Leo núi"],
        [8, "Travel Budget", "Ngân sách du lịch"],
        [9, "Cultural Experience", "Trải nghiệm văn hóa"],
        [10, "Travel Insurance", "Bảo hiểm du lịch"],
        [11, "Hostel Stay", "Ở hostel"],
        [12, "Souvenir Shopping", "Mua quà lưu niệm"],
        [13, "Adventure Travel", "Du lịch mạo hiểm"],
        [14, "Travel Photography", "Chụp ảnh du lịch"],
        [15, "Guided Tour", "Tour có hướng dẫn"],
        [16, "Backpacking Trip", "Du lịch ba lô"],
        [17, "Cruise Vacation", "Du thuyền"],
        [18, "Travel Recommendations", "Gợi ý du lịch"],
        [19, "Lost Passport", "Mất hộ chiếu"],
        [20, "Travel Stories", "Câu chuyện du lịch"],
    ],
    # Topic 15: Technology
    [
        [1, "Smartphone Features", "Tính năng smartphone"],
        [2, "Social Media", "Mạng xã hội"],
        [3, "Computer Problems", "Vấn đề máy tính"],
        [4, "Internet Connection", "Kết nối internet"],
        [5, "New App Discovery", "Khám phá app mới"],
        [6, "Tech Support", "Hỗ trợ kỹ thuật"],
        [7, "Online Security", "Bảo mật online"],
        [8, "Video Games", "Trò chơi điện tử"],
        [9, "Smart Home", "Nhà thông minh"],
        [10, "Tech Trends", "Xu hướng công nghệ"],
        [11, "Photography Apps", "App chụp ảnh"],
        [12, "Cloud Storage", "Lưu trữ đám mây"],
        [13, "E-commerce", "Thương mại điện tử"],
        [14, "Artificial Intelligence", "Trí tuệ nhân tạo"],
        [15, "Gadget Review", "Đánh giá thiết bị"],
        [16, "Digital Payment", "Thanh toán điện tử"],
        [17, "Tech Addiction", "Nghiện công nghệ"],
        [18, "Software Update", "Cập nhật phần mềm"],
        [19, "Virtual Reality", "Thực tế ảo"],
        [20, "Future Technology", "Công nghệ tương lai"],
    ],
    # Topic 16: Entertainment
    [
        [1, "Movie Night", "Tối xem phim"],
        [2, "Concert Experience", "Trải nghiệm concert"],
        [3, "TV Series Binge", "Cày phim truyền hình"],
        [4, "Theater Performance", "Biểu diễn sân khấu"],
        [5, "Music Festival", "Lễ hội âm nhạc"],
        [6, "Comedy Show", "Show hài"],
        [7, "Book Club", "Câu lạc bộ sách"],
        [8, "Podcast Listening", "Nghe podcast"],
        [9, "Art Exhibition", "Triển lãm nghệ thuật"],
        [10, "Gaming Session", "Phiên chơi game"],
        [11, "Karaoke Night", "Đêm karaoke"],
        [12, "Streaming Services", "Dịch vụ streaming"],
        [13, "Celebrity News", "Tin tức người nổi tiếng"],
        [14, "Magic Show", "Show ảo thuật"],
        [15, "Dance Performance", "Biểu diễn múa"],
        [16, "Film Review", "Đánh giá phim"],
        [17, "Museum Visit", "Thăm bảo tàng"],
        [18, "Entertainment Trends", "Xu hướng giải trí"],
        [19, "Music Recommendations", "Gợi ý nhạc"],
        [20, "Weekend Entertainment", "Giải trí cuối tuần"],
    ],
    # Topic 17: Sports
    [
        [1, "Favorite Sport", "Môn thể thao yêu thích"],
        [2, "Football Match", "Trận bóng đá"],
        [3, "Basketball Game", "Trận bóng rổ"],
        [4, "Tennis Tournament", "Giải tennis"],
        [5, "Swimming Competition", "Thi bơi"],
        [6, "Olympic Games", "Thế vận hội"],
        [7, "Team Spirit", "Tinh thần đội"],
        [8, "Sports Training", "Luyện tập thể thao"],
        [9, "Winning and Losing", "Thắng và thua"],
        [10, "Sports Equipment", "Dụng cụ thể thao"],
        [11, "Marathon Event", "Sự kiện marathon"],
        [12, "Extreme Sports", "Thể thao mạo hiểm"],
        [13, "Sports Nutrition", "Dinh dưỡng thể thao"],
        [14, "Coaching Tips", "Lời khuyên huấn luyện"],
        [15, "Stadium Experience", "Trải nghiệm sân vận động"],
        [16, "Sports Psychology", "Tâm lý thể thao"],
        [17, "Professional Athletes", "Vận động viên chuyên nghiệp"],
        [18, "Sports Betting", "Cá cược thể thao"],
        [19, "Fitness Challenge", "Thử thách thể lực"],
        [20, "Sports History", "Lịch sử thể thao"],
    ],
    # Topic 18: Home & Living
    [
        [1, "Dream House", "Ngôi nhà mơ ước"],
        [2, "Moving Day", "Ngày chuyển nhà"],
        [3, "Interior Design", "Thiết kế nội thất"],
        [4, "Home Renovation", "Sửa sang nhà"],
        [5, "Household Chores", "Việc nhà"],
        [6, "Furniture Shopping", "Mua nội thất"],
        [7, "Apartment Hunting", "Tìm căn hộ"],
        [8, "Garden Planning", "Thiết kế vườn"],
        [9, "Home Security", "An ninh nhà"],
        [10, "Utility Bills", "Hóa đơn tiện ích"],
        [11, "Neighborhood Life", "Cuộc sống khu phố"],
        [12, "Home Maintenance", "Bảo trì nhà"],
        [13, "Roommate Issues", "Vấn đề bạn cùng phòng"],
        [14, "Smart Home Setup", "Thiết lập nhà thông minh"],
        [15, "Rent or Buy", "Thuê hay mua"],
        [16, "Home Decoration", "Trang trí nhà"],
        [17, "Kitchen Organization", "Sắp xếp bếp"],
        [18, "Energy Efficiency", "Tiết kiệm năng lượng"],
        [19, "Pet-Friendly Home", "Nhà thân thiện thú cưng"],
        [20, "Minimalist Living", "Sống tối giản"],
    ],
    # Topic 19: Environment
    [
        [1, "Climate Change", "Biến đổi khí hậu"],
        [2, "Recycling Habits", "Thói quen tái chế"],
        [3, "Saving Energy", "Tiết kiệm năng lượng"],
        [4, "Plastic Pollution", "Ô nhiễm nhựa"],
        [5, "Green Living", "Sống xanh"],
        [6, "Wildlife Protection", "Bảo vệ động vật hoang dã"],
        [7, "Water Conservation", "Bảo tồn nước"],
        [8, "Air Quality", "Chất lượng không khí"],
        [9, "Sustainable Farming", "Nông nghiệp bền vững"],
        [10, "Ocean Cleanup", "Làm sạch đại dương"],
        [11, "Renewable Energy", "Năng lượng tái tạo"],
        [12, "Deforestation Issue", "Vấn đề phá rừng"],
        [13, "Zero Waste", "Không rác thải"],
        [14, "Environmental Activism", "Hoạt động môi trường"],
        [15, "Carbon Footprint", "Dấu chân carbon"],
        [16, "Eco-Friendly Products", "Sản phẩm thân thiện"],
        [17, "Endangered Species", "Loài nguy cấp"],
        [18, "Green Transportation", "Giao thông xanh"],
        [19, "Environmental Education", "Giáo dục môi trường"],
        [20, "Future of Earth", "Tương lai Trái đất"],
    ],
    # Topic 20: Culture & Customs
    [
        [1, "Cultural Differences", "Khác biệt văn hóa"],
        [2, "Traditional Festival", "Lễ hội truyền thống"],
        [3, "Wedding Customs", "Phong tục cưới"],
        [4, "Table Etiquette", "Phép tắc bàn ăn"],
        [5, "Religious Practices", "Tập tục tôn giáo"],
        [6, "National Costumes", "Trang phục dân tộc"],
        [7, "Cultural Exchange", "Trao đổi văn hóa"],
        [8, "Language Barrier", "Rào cản ngôn ngữ"],
        [9, "Traditional Music", "Âm nhạc truyền thống"],
        [10, "Cultural Heritage", "Di sản văn hóa"],
        [11, "Greeting Customs", "Phong tục chào hỏi"],
        [12, "Cultural Shock", "Sốc văn hóa"],
        [13, "Folklore Stories", "Truyện dân gian"],
        [14, "Cultural Identity", "Bản sắc văn hóa"],
        [15, "Gift Giving", "Tặng quà"],
        [16, "Superstitions", "Mê tín"],
        [17, "Cultural Adaptation", "Thích nghi văn hóa"],
        [18, "Traditional Crafts", "Thủ công truyền thống"],
        [19, "Cultural Respect", "Tôn trọng văn hóa"],
        [20, "Multicultural Society", "Xã hội đa văn hóa"],
    ],
    # Topic 21: Business & Economics
    [
        [1, "Starting a Business", "Khởi nghiệp"],
        [2, "Market Analysis", "Phân tích thị trường"],
        [3, "Investment Strategy", "Chiến lược đầu tư"],
        [4, "Business Meeting", "Họp kinh doanh"],
        [5, "Financial Planning", "Lập kế hoạch tài chính"],
        [6, "Negotiation Skills", "Kỹ năng đàm phán"],
        [7, "Economic Crisis", "Khủng hoảng kinh tế"],
        [8, "Stock Market", "Thị trường chứng khoán"],
        [9, "Business Partnership", "Hợp tác kinh doanh"],
        [10, "Marketing Campaign", "Chiến dịch marketing"],
        [11, "Sales Presentation", "Thuyết trình bán hàng"],
        [12, "Budget Management", "Quản lý ngân sách"],
        [13, "Global Trade", "Thương mại toàn cầu"],
        [14, "Business Ethics", "Đạo đức kinh doanh"],
        [15, "Economic Growth", "Tăng trưởng kinh tế"],
        [16, "Corporate Strategy", "Chiến lược doanh nghiệp"],
        [17, "Risk Management", "Quản lý rủi ro"],
        [18, "Business Innovation", "Đổi mới kinh doanh"],
        [19, "Supply Chain", "Chuỗi cung ứng"],
        [20, "Economic Policy", "Chính sách kinh tế"],
    ],
    # Topic 22: Politics & Society
    [
        [1, "Voting Rights", "Quyền bầu cử"],
        [2, "Political Debate", "Tranh luận chính trị"],
        [3, "Social Justice", "Công lý xã hội"],
        [4, "Government Policies", "Chính sách chính phủ"],
        [5, "Human Rights", "Quyền con người"],
        [6, "Election Campaign", "Chiến dịch bầu cử"],
        [7, "Social Inequality", "Bất bình đẳng xã hội"],
        [8, "Political System", "Hệ thống chính trị"],
        [9, "Civil Society", "Xã hội dân sự"],
        [10, "Public Opinion", "Dư luận"],
        [11, "Democracy Values", "Giá trị dân chủ"],
        [12, "Social Reform", "Cải cách xã hội"],
        [13, "Political Corruption", "Tham nhũng chính trị"],
        [14, "Civic Engagement", "Tham gia công dân"],
        [15, "International Relations", "Quan hệ quốc tế"],
        [16, "Social Movements", "Phong trào xã hội"],
        [17, "Political Leadership", "Lãnh đạo chính trị"],
        [18, "Public Services", "Dịch vụ công"],
        [19, "Constitutional Rights", "Quyền hiến định"],
        [20, "Society Progress", "Tiến bộ xã hội"],
    ],
    # Topic 23: Science & Research
    [
        [1, "Scientific Method", "Phương pháp khoa học"],
        [2, "Lab Experiment", "Thí nghiệm phòng lab"],
        [3, "Research Paper", "Bài nghiên cứu"],
        [4, "Space Exploration", "Khám phá không gian"],
        [5, "Medical Research", "Nghiên cứu y học"],
        [6, "Climate Science", "Khoa học khí hậu"],
        [7, "DNA Discovery", "Khám phá DNA"],
        [8, "Physics Theories", "Lý thuyết vật lý"],
        [9, "Chemical Reactions", "Phản ứng hóa học"],
        [10, "Biological Systems", "Hệ thống sinh học"],
        [11, "Scientific Breakthrough", "Đột phá khoa học"],
        [12, "Research Funding", "Tài trợ nghiên cứu"],
        [13, "Peer Review", "Bình duyệt"],
        [14, "Data Analysis", "Phân tích dữ liệu"],
        [15, "Scientific Ethics", "Đạo đức khoa học"],
        [16, "Technology Transfer", "Chuyển giao công nghệ"],
        [17, "Research Collaboration", "Hợp tác nghiên cứu"],
        [18, "Scientific Innovation", "Đổi mới khoa học"],
        [19, "Evidence-Based", "Dựa trên bằng chứng"],
        [20, "Future Science", "Khoa học tương lai"],
    ],
    # Topic 24: Arts & Literature
    [
        [1, "Famous Paintings", "Tranh nổi tiếng"],
        [2, "Classic Literature", "Văn học cổ điển"],
        [3, "Poetry Reading", "Đọc thơ"],
        [4, "Art Gallery", "Phòng tranh"],
        [5, "Literary Analysis", "Phân tích văn học"],
        [6, "Sculpture Art", "Nghệ thuật điêu khắc"],
        [7, "Modern Poetry", "Thơ hiện đại"],
        [8, "Art Movements", "Trào lưu nghệ thuật"],
        [9, "Novel Writing", "Viết tiểu thuyết"],
        [10, "Performance Art", "Nghệ thuật trình diễn"],
        [11, "Literary Criticism", "Phê bình văn học"],
        [12, "Abstract Art", "Nghệ thuật trừu tượng"],
        [13, "Creative Writing", "Viết sáng tạo"],
        [14, "Art Appreciation", "Thưởng thức nghệ thuật"],
        [15, "Literary Genres", "Thể loại văn học"],
        [16, "Street Art", "Nghệ thuật đường phố"],
        [17, "Author Interview", "Phỏng vấn tác giả"],
        [18, "Art Education", "Giáo dục nghệ thuật"],
        [19, "Literary Heritage", "Di sản văn học"],
        [20, "Contemporary Art", "Nghệ thuật đương đại"],
    ],
    # Topic 25: Philosophy & Ethics
    [
        [1, "Meaning of Life", "Ý nghĩa cuộc sống"],
        [2, "Moral Dilemmas", "Tình huống đạo đức"],
        [3, "Free Will", "Ý chí tự do"],
        [4, "Ethical Decisions", "Quyết định đạo đức"],
        [5, "Truth and Reality", "Chân lý và thực tại"],
        [6, "Justice Theory", "Lý thuyết công lý"],
        [7, "Human Nature", "Bản chất con người"],
        [8, "Philosophical Debate", "Tranh luận triết học"],
        [9, "Virtue Ethics", "Đạo đức đức hạnh"],
        [10, "Existentialism", "Chủ nghĩa hiện sinh"],
        [11, "Moral Responsibility", "Trách nhiệm đạo đức"],
        [12, "Knowledge Theory", "Lý thuyết tri thức"],
        [13, "Ethical Principles", "Nguyên tắc đạo đức"],
        [14, "Mind-Body Problem", "Vấn đề tâm-thân"],
        [15, "Happiness Philosophy", "Triết lý hạnh phúc"],
        [16, "Professional Ethics", "Đạo đức nghề nghiệp"],
        [17, "Consciousness Study", "Nghiên cứu ý thức"],
        [18, "Moral Values", "Giá trị đạo đức"],
        [19, "Ancient Philosophy", "Triết học cổ đại"],
        [20, "Applied Ethics", "Đạo đức ứng dụng"],
    ],
    # Topic 26: Global Issues
    [
        [1, "Poverty Solutions", "Giải pháp nghèo đói"],
        [2, "Refugee Crisis", "Khủng hoảng tị nạn"],
        [3, "Global Warming", "Nóng lên toàn cầu"],
        [4, "World Hunger", "Nạn đói thế giới"],
        [5, "Pandemic Response", "Ứng phó đại dịch"],
        [6, "Water Scarcity", "Khan hiếm nước"],
        [7, "Global Education", "Giáo dục toàn cầu"],
        [8, "Armed Conflicts", "Xung đột vũ trang"],
        [9, "International Aid", "Viện trợ quốc tế"],
        [10, "Gender Equality", "Bình đẳng giới"],
        [11, "Global Health", "Sức khỏe toàn cầu"],
        [12, "Migration Issues", "Vấn đề di cư"],
        [13, "Nuclear Weapons", "Vũ khí hạt nhân"],
        [14, "Global Cooperation", "Hợp tác toàn cầu"],
        [15, "Child Labor", "Lao động trẻ em"],
        [16, "Terrorism Threats", "Mối đe dọa khủng bố"],
        [17, "Global Inequality", "Bất bình đẳng toàn cầu"],
        [18, "Peace Building", "Xây dựng hòa bình"],
        [19, "Development Goals", "Mục tiêu phát triển"],
        [20, "World Unity", "Đoàn kết thế giới"],
    ],
    # Topic 27: Innovation
    [
        [1, "Creative Thinking", "Tư duy sáng tạo"],
        [2, "Product Innovation", "Đổi mới sản phẩm"],
        [3, "Startup Culture", "Văn hóa khởi nghiệp"],
        [4, "Disruptive Technology", "Công nghệ đột phá"],
        [5, "Design Thinking", "Tư duy thiết kế"],
        [6, "Innovation Process", "Quy trình đổi mới"],
        [7, "Breakthrough Ideas", "Ý tưởng đột phá"],
        [8, "Tech Innovation", "Đổi mới công nghệ"],
        [9, "Creative Problem Solving", "Giải quyết sáng tạo"],
        [10, "Innovation Management", "Quản lý đổi mới"],
        [11, "Prototype Testing", "Thử nghiệm mẫu"],
        [12, "Social Innovation", "Đổi mới xã hội"],
        [13, "Innovative Business", "Kinh doanh đổi mới"],
        [14, "Research Development", "Nghiên cứu phát triển"],
        [15, "Open Innovation", "Đổi mới mở"],
        [16, "Entrepreneurial Spirit", "Tinh thần doanh nhân"],
        [17, "Innovation Strategy", "Chiến lược đổi mới"],
        [18, "Creative Industries", "Ngành sáng tạo"],
        [19, "Innovation Ecosystem", "Hệ sinh thái đổi mới"],
        [20, "Future Innovation", "Đổi mới tương lai"],
    ],
    # Topic 28: Psychology
    [
        [1, "Human Behavior", "Hành vi con người"],
        [2, "Mental Health", "Sức khỏe tâm thần"],
        [3, "Stress Management", "Quản lý căng thẳng"],
        [4, "Personality Types", "Loại tính cách"],
        [5, "Emotional Intelligence", "Trí tuệ cảm xúc"],
        [6, "Motivation Theory", "Lý thuyết động lực"],
        [7, "Cognitive Processes", "Quá trình nhận thức"],
        [8, "Social Psychology", "Tâm lý xã hội"],
        [9, "Therapy Session", "Buổi trị liệu"],
        [10, "Psychological Research", "Nghiên cứu tâm lý"],
        [11, "Memory Studies", "Nghiên cứu trí nhớ"],
        [12, "Childhood Development", "Phát triển trẻ em"],
        [13, "Anxiety Disorders", "Rối loạn lo âu"],
        [14, "Positive Psychology", "Tâm lý tích cực"],
        [15, "Learning Psychology", "Tâm lý học tập"],
        [16, "Relationship Dynamics", "Động lực quan hệ"],
        [17, "Behavioral Change", "Thay đổi hành vi"],
        [18, "Psychological Well-being", "Hạnh phúc tâm lý"],
        [19, "Mind and Emotion", "Tâm trí và cảm xúc"],
        [20, "Applied Psychology", "Tâm lý ứng dụng"],
    ],
    # Topic 29: History
    [
        [1, "Ancient Civilizations", "Nền văn minh cổ đại"],
        [2, "World Wars", "Chiến tranh thế giới"],
        [3, "Historical Figures", "Nhân vật lịch sử"],
        [4, "Industrial Revolution", "Cách mạng công nghiệp"],
        [5, "Cultural Revolution", "Cách mạng văn hóa"],
        [6, "Colonial Period", "Thời kỳ thuộc địa"],
        [7, "Historical Events", "Sự kiện lịch sử"],
        [8, "Medieval Times", "Thời trung cổ"],
        [9, "Independence Movements", "Phong trào độc lập"],
        [10, "Historical Artifacts", "Di vật lịch sử"],
        [11, "Renaissance Era", "Thời kỳ Phục hưng"],
        [12, "Cold War", "Chiến tranh Lạnh"],
        [13, "Historical Monuments", "Di tích lịch sử"],
        [14, "Empire Building", "Xây dựng đế chế"],
        [15, "Historical Research", "Nghiên cứu lịch sử"],
        [16, "Revolution Impact", "Ảnh hưởng cách mạng"],
        [17, "Historical Timeline", "Dòng thời gian lịch sử"],
        [18, "Archaeological Finds", "Khám phá khảo cổ"],
        [19, "History Lessons", "Bài học lịch sử"],
        [20, "Historical Perspective", "Góc nhìn lịch sử"],
    ],
    # Topic 30: Future & Trends
    [
        [1, "Future Predictions", "Dự đoán tương lai"],
        [2, "Emerging Trends", "Xu hướng mới nổi"],
        [3, "Smart Cities", "Thành phố thông minh"],
        [4, "Space Colonization", "Thuộc địa không gian"],
        [5, "Artificial General Intelligence", "Trí tuệ nhân tạo tổng quát"],
        [6, "Future of Work", "Tương lai công việc"],
        [7, "Biotech Future", "Tương lai công nghệ sinh học"],
        [8, "Climate Future", "Tương lai khí hậu"],
        [9, "Next Generation", "Thế hệ tiếp theo"],
        [10, "Future Education", "Giáo dục tương lai"],
        [11, "Tech Predictions", "Dự đoán công nghệ"],
        [12, "Future Society", "Xã hội tương lai"],
        [13, "Quantum Computing", "Máy tính lượng tử"],
        [14, "Future Energy", "Năng lượng tương lai"],
        [15, "Automation Era", "Kỷ nguyên tự động"],
        [16, "Future Medicine", "Y học tương lai"],
        [17, "Digital Future", "Tương lai số"],
        [18, "Sustainable Future", "Tương lai bền vững"],
        [19, "Human Evolution", "Tiến hóa con người"],
        [20, "Tomorrow's World", "Thế giới ngày mai"],
    ],
]


def get_all_conversations():
    """
    Build and return all 600 conversations with full metadata
    Combines TOPICS + CONVERSATIONS arrays
    """
    result = []
    for topic_idx, topic in enumerate(TOPICS):
        if topic_idx >= len(CONVERSATIONS):
            break

        for conv_data in CONVERSATIONS[topic_idx]:
            idx, title_en, title_vi = conv_data
            result.append(
                {
                    "level": topic["level"],
                    "topic_number": topic["number"],
                    "topic_slug": topic["slug"],
                    "topic_en": topic["en"],
                    "topic_vi": topic["vi"],
                    "conversation_index": idx,
                    "title_en": title_en,
                    "title_vi": title_vi,
                }
            )

    return result


def get_conversation_by_index(global_index: int):
    """
    Get conversation by global index (1-600)

    Args:
        global_index: 1-based index (1 to 600)
    """
    all_convs = get_all_conversations()
    if 1 <= global_index <= len(all_convs):
        return all_convs[global_index - 1]
    return None


def get_conversations_by_topic(topic_number: int):
    """
    Get all 20 conversations for a specific topic

    Args:
        topic_number: 1-30
    """
    if topic_number < 1 or topic_number > 30:
        return []

    topic_idx = topic_number - 1
    if topic_idx >= len(TOPICS) or topic_idx >= len(CONVERSATIONS):
        return []

    topic = TOPICS[topic_idx]
    convs = CONVERSATIONS[topic_idx]

    result = []
    for idx, title_en, title_vi in convs:
        result.append(
            {
                "level": topic["level"],
                "topic_number": topic["number"],
                "topic_slug": topic["slug"],
                "topic_en": topic["en"],
                "topic_vi": topic["vi"],
                "conversation_index": idx,
                "title_en": title_en,
                "title_vi": title_vi,
            }
        )

    return result


def validate_data():
    """
    Validate 600 conversations structure
    """
    print(f"📊 Topics defined: {len(TOPICS)}")
    print(f"📊 Conversation arrays: {len(CONVERSATIONS)}")

    if len(TOPICS) != 30:
        print(f"❌ ERROR: Expected 30 topics, got {len(TOPICS)}")
        return False

    total_convs = sum(len(c) for c in CONVERSATIONS)
    print(f"📊 Total conversations: {total_convs}")

    if total_convs != 600:
        print(f"❌ ERROR: Expected 600, got {total_convs}")
        return False

    # Validate each topic
    all_valid = True
    for i, (topic, convs) in enumerate(zip(TOPICS, CONVERSATIONS)):
        if len(convs) != 20:
            print(f"❌ Topic {i+1} ({topic['en']}): Expected 20, got {len(convs)}")
            all_valid = False
        else:
            # Check indices 1-20
            indices = {c[0] for c in convs}
            if indices != set(range(1, 21)):
                print(f"❌ Topic {i+1}: Invalid indices {indices}")
                all_valid = False
            else:
                print(f"✅ Topic {i+1} ({topic['en']}): 20 conversations")

    if all_valid:
        print("\n✅ ALL VALIDATION PASSED!")
    else:
        print("\n❌ VALIDATION FAILED!")

    return all_valid


if __name__ == "__main__":
    validate_data()

    print("\n" + "=" * 70)
    print("SAMPLE - Topic 1:")
    print("=" * 70)
    for conv in get_conversations_by_topic(1)[:5]:
        print(f"  [{conv['conversation_index']:02d}] {conv['title_en']}")
