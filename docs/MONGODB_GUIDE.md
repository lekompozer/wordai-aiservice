# 📋 Hướng dẫn quản lý MongoDB Collection `companies`

## 🔌 Kết nối MongoDB

```bash
# Connect với Docker MongoDB container
docker exec -it mongodb mongosh "mongodb://ai_service_user:ai_service_2025_secure_password@localhost:27017/ai_service_db?authSource=admin"

# Hoặc nếu chạy MongoDB trực tiếp
mongosh "mongodb://ai_service_user:ai_service_2025_secure_password@localhost:27017/ai_service_db?authSource=admin"
```

## 🔍 Kiểm tra dữ liệu hiện tại

```javascript
// 1. Kiểm tra databases
show dbs

// 2. Chọn database ai_service_db (từ .env)
use ai_service_db

// 3. Kiểm tra collections
show collections

// 4. Kiểm tra collection companies (QUAN TRỌNG - collection mới thống nhất)
db.companies.find().limit(5).pretty()

// 5. Count tổng số companies
db.companies.countDocuments()

// 6. Tìm company cụ thể theo company_id
db.companies.findOne({"company_id": "golden_dragon_restaurant"})

// 7. Liệt kê tất cả companies với thông tin cơ bản
db.companies.find({}, {
    "company_id": 1,
    "company_name": 1,
    "industry": 1,
    "metadata.email": 1,
    "metadata.phone": 1
}).limit(10).pretty()

// 8. Kiểm tra company có FAQs và Scenarios
db.companies.find({
    "metadata.faqs": {$exists: true, $ne: []},
    "metadata.scenarios": {$exists: true, $ne: []}
}, {
    "company_id": 1,
    "company_name": 1,
    "metadata.faqs": 1,
    "metadata.scenarios": 1
}).pretty()
```

## 📝 Thêm dữ liệu mẫu cho AI Chat

### 1. Tạo company hoàn chỉnh với FAQs và Scenarios:

```javascript
db.companies.insertOne({
    "company_id": "golden_dragon_restaurant",
    "company_name": "Golden Dragon Restaurant",
    "industry": "RESTAURANT",
    "languages": ["vi"],
    "qdrant_collection": "multi_company_data",
    "data_sources": {},
    "ai_config": {},
    "industry_config": {},
    "business_hours": null,
    "contact_info": null,
    "created_at": new Date(),
    "updated_at": new Date(),
    "metadata": {
        "description": "Nhà hàng chuyên phục vụ các món ăn Việt Nam truyền thống với hương vị đậm đà",
        "email": "contact@goldendragon.vn",
        "phone": "+84901234567",
        "website": "https://goldendragon.vn",
        "location": {
            "country": "Vietnam",
            "city": "Ho Chi Minh City",
            "address": "123 Nguyen Hue Street, District 1"
        },
        "social_links": {
            "facebook": "https://facebook.com/goldendragon",
            "instagram": "https://instagram.com/goldendragon"
        },
        "faqs": [
            {
                "question": "Nhà hàng có phục vụ món chay không?",
                "answer": "Có, chúng tôi có nhiều món chay ngon như đậu hũ xào lăn, canh chua chay, cơm chiên chay, gỏi cuốn chay."
            },
            {
                "question": "Giờ mở cửa của nhà hàng?",
                "answer": "Chúng tôi mở cửa từ 10:00 sáng đến 22:00 tối, 7 ngày trong tuần. Chủ nhật có thể đóng cửa sớm hơn."
            },
            {
                "question": "Có phục vụ delivery không?",
                "answer": "Có, chúng tôi giao hàng trong bán kính 5km với phí ship chỉ 15k. Đơn hàng trên 200k được miễn phí ship."
            },
            {
                "question": "Có chỗ đậu xe không?",
                "answer": "Có, chúng tôi có bãi đậu xe miễn phí cho khách hàng ở phía sau nhà hàng."
            },
            {
                "question": "Món nào được yêu thích nhất?",
                "answer": "Phở bò đặc biệt, bún bò Huế và bánh mì thịt nướng là những món được khách hàng yêu thích nhất."
            }
        ],
        "scenarios": [
            {
                "name": "Đặt bàn",
                "description": "Hướng dẫn khách hàng đặt bàn qua điện thoại (+84901234567) hoặc Facebook. Cần thông tin: số người, thời gian, yêu cầu đặc biệt."
            },
            {
                "name": "Khiếu nại món ăn",
                "description": "Xin lỗi khách hàng, lắng nghe vấn đề, đề xuất đổi món hoặc hoàn tiền. Ghi nhận để cải thiện chất lượng."
            },
            {
                "name": "Tư vấn món ăn",
                "description": "Hỏi về sở thích (cay/không cay, thịt/chay), số người ăn, ngân sách để tư vấn combo phù hợp."
            },
            {
                "name": "Hỏi về giá cả",
                "description": "Cung cấp giá menu chính xác. Phở: 45k-65k, Bún bò: 50k, Bánh mì: 25k-35k, Cơm tấm: 40k-60k."
            }
        ]
    }
})
```

### 2. Thêm company khác (ví dụ Tech Company):

```javascript
db.companies.insertOne({
    "company_id": "tech_solutions_vn",
    "company_name": "Tech Solutions Vietnam",
    "industry": "TECHNOLOGY",
    "languages": ["vi", "en"],
    "qdrant_collection": "multi_company_data",
    "data_sources": {},
    "ai_config": {},
    "industry_config": {},
    "business_hours": null,
    "contact_info": null,
    "created_at": new Date(),
    "updated_at": new Date(),
    "metadata": {
        "description": "Công ty phát triển phần mềm và giải pháp công nghệ cho doanh nghiệp",
        "email": "info@techsolutions.vn",
        "phone": "+84287654321",
        "website": "https://techsolutions.vn",
        "location": {
            "country": "Vietnam",
            "city": "Ho Chi Minh City",
            "address": "456 Le Loi Street, District 3"
        },
        "social_links": {
            "linkedin": "https://linkedin.com/company/techsolutions",
            "facebook": "https://facebook.com/techsolutionsvn"
        },
        "faqs": [
            {
                "question": "Công ty có phát triển app mobile không?",
                "answer": "Có, chúng tôi phát triển app iOS và Android native, cũng như React Native và Flutter."
            },
            {
                "question": "Thời gian phát triển một website thường là bao lâu?",
                "answer": "Tùy vào độ phức tạp: Website đơn giản 2-4 tuần, Website phức tạp 6-12 tuần, E-commerce 8-16 tuần."
            },
            {
                "question": "Có hỗ trợ maintenance sau khi bàn giao không?",
                "answer": "Có, chúng tôi cung cấp gói bảo trì 6-12 tháng với fix bug miễn phí và update bảo mật."
            }
        ],
        "scenarios": [
            {
                "name": "Tư vấn dự án",
                "description": "Thu thập yêu cầu khách hàng, phân tích và đưa ra giải pháp kỹ thuật phù hợp với ngân sách."
            },
            {
                "name": "Báo giá dự án",
                "description": "Dựa vào scope work để tính toán thời gian, nhân lực và đưa ra mức giá hợp lý."
            }
        ]
    }
})
```

## 🔄 Cập nhật dữ liệu hiện có

### 1. Thêm FAQs cho company hiện có:

```javascript
db.companies.updateOne(
    {"company_id": "golden_dragon_restaurant"},
    {
        $push: {
            "metadata.faqs": {
                $each: [
                    {
                        "question": "Có phục vụ tiệc sinh nhật không?",
                        "answer": "Có, chúng tôi có gói tiệc sinh nhật với bánh kem và trang trí đặc biệt."
                    }
                ]
            }
        },
        $set: {"updated_at": new Date()}
    }
)
```

### 2. Thêm Scenarios cho company hiện có:

```javascript
db.companies.updateOne(
    {"company_id": "golden_dragon_restaurant"},
    {
        $push: {
            "metadata.scenarios": {
                $each: [
                    {
                        "name": "Xử lý peak time",
                        "description": "Khi quá đông khách, hướng dẫn chờ đợi và gợi ý thời gian phù hợp hơn."
                    }
                ]
            }
        },
        $set: {"updated_at": new Date()}
    }
)
```

### 3. Cập nhật metadata cơ bản:

```javascript
db.companies.updateOne(
    {"company_id": "golden_dragon_restaurant"},
    {
        $set: {
            "metadata.description": "Nhà hàng Việt Nam chính hiệu với 20 năm kinh nghiệm",
            "metadata.phone": "+84901234568",
            "updated_at": new Date()
        }
    }
)
```

## 🔍 Kiểm tra AI Chat đọc được dữ liệu

### 1. Xem dữ liệu mà AI sẽ đọc:

```javascript
// Kiểm tra format dữ liệu cho AI Chat
db.companies.findOne(
    {"company_id": "golden_dragon_restaurant"},
    {
        "company_id": 1,
        "company_name": 1,
        "industry": 1,
        "metadata": 1
    }
).metadata
```

### 2. Kiểm tra FAQs format:

```javascript
db.companies.aggregate([
    {$match: {"company_id": "golden_dragon_restaurant"}},
    {$project: {
        "company_name": 1,
        "faq_count": {$size: "$metadata.faqs"},
        "scenario_count": {$size: "$metadata.scenarios"},
        "faqs": "$metadata.faqs"
    }}
])
```

## 🗑️ Xóa dữ liệu (nếu cần)

```javascript
// Xóa company hoàn toàn
db.companies.deleteOne({"company_id": "company_can_xoa"})

// Xóa chỉ FAQs
db.companies.updateOne(
    {"company_id": "golden_dragon_restaurant"},
    {$unset: {"metadata.faqs": ""}}
)

// Xóa chỉ Scenarios
db.companies.updateOne(
    {"company_id": "golden_dragon_restaurant"},
    {$unset: {"metadata.scenarios": ""}}
)

// Xóa tất cả companies (NGUY HIỂM!)
// db.companies.deleteMany({})
```

## 📊 Kiểm tra Collection cũ (nếu còn tồn tại)

```javascript
// Kiểm tra collection company_context cũ (có thể xóa)
db.company_context.find().limit(5)

// Nếu muốn migrate dữ liệu từ collection cũ
db.company_context.find().forEach(function(doc) {
    print("Old document:", doc.company_id);
    // Code để migrate sang companies collection
});

// Xóa collection cũ sau khi migrate xong
// db.company_context.drop()
```

## ✅ Test AI Chat với company data

Sau khi thêm dữ liệu, hãy test qua API:

```bash
# Test API để xem AI có đọc được company context không
curl -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Nhà hàng có phục vụ món chay không?",
    "company_id": "golden_dragon_restaurant"
  }'
```

---

## 📝 Lưu ý quan trọng:

1. **Collection name**: Chỉ dùng `companies` (không dùng `company_context` nữa)
2. **Structure**: FAQs và Scenarios nằm trong `metadata.faqs` và `metadata.scenarios`
3. **AI Chat**: Sẽ tự động đọc tất cả thông tin từ collection `companies`
4. **Backup**: Luôn backup dữ liệu trước khi thay đổi lớn
