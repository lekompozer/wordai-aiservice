# AI Services API Documentation

## 📖 Tổng quan

Tài liệu này mô tả các API endpoints của hệ thống AI Services, bao gồm:
- **Chat Services**: Các API cho tính năng chat và xử lý tài liệu
- **Loan Assessment**: API thẩm định hồ sơ vay ngân hàng
- **OCR Services**: API nhận dạng ký tự quang học (CCCD)
- **AI Sales Agent**: API tư vấn vay thông minh với NLU/NLG

---

## 🔗 Base URLs

- **Production**: `https://ai.aimoney.io.vn`
- **Development**: `http://localhost:8000`

---

## 📋 Authentication

Hệ thống sử dụng API keys được cấu hình trong environment variables:
- `DEEPSEEK_API_KEY`: Cho DeepSeek AI
- `CHATGPT_API_KEY`: Cho ChatGPT/OpenAI

---

## 🤖 Chat Services

### 1. Basic Chat (Non-streaming)

**Endpoint**: `POST /chat`

**Mô tả**: API chat cơ bản trả về response một lần

**Request Body**:
```json
{
  "question": "Lãi suất vay mua nhà hiện tại như thế nào?",
  "session_id": "session_123",
  "userId": "user_456",
  "tone": "professional"
}
```

**Response**:
```json
{
  "response": "Lãi suất vay mua nhà hiện tại dao động từ 8.5% - 12% tùy thuộc vào...",
  "session_id": "session_123",
  "timestamp": "2025-07-11T10:30:00"
}
```

**Tham số**:
- `question` (string, required): Câu hỏi của người dùng
- `session_id` (string, optional): ID phiên chat
- `userId` (string, optional): ID người dùng
- `tone` (string, optional): Tone điều chỉnh (professional, friendly, formal)

---

### 2. Streaming Chat

**Endpoint**: `POST /chat-stream`

**Mô tả**: API chat streaming trả về response theo từng chunk

**Request Body**:
```json
{
  "question": "Tôi muốn vay 500 triệu mua nhà, điều kiện như thế nào?",
  "session_id": "session_123",
  "userId": "user_456",
  "deviceId": "device_789"
}
```

**Response**: Server-Sent Events (SSE)
```
data: {"chunk": "[Theo dữ liệu ứng dụng] "}
data: {"chunk": "Để vay 500 triệu"}
data: {"chunk": " mua nhà, bạn cần"}
data: {"chunk": " đáp ứng các điều kiện..."}
data: {"done": true}
```

**Headers**:
- `Content-Type`: `text/event-stream`
- `Cache-Control`: `no-cache`

---

### 3. Chat with Files (Streaming)

**Endpoint**: `POST /chat-with-files-stream`

**Mô tả**: API chat với khả năng xử lý tài liệu đính kèm

**Request Body**:
```json
{
  "question": "Phân tích tài liệu này cho tôi",
  "files": ["base64_encoded_file_1", "base64_encoded_file_2"],
  "file_names": ["document1.pdf", "document2.docx"],
  "file_types": ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
  "session_id": "session_123",
  "userId": "user_456",
  "tone": "analytical"
}
```

**Response**: Server-Sent Events (SSE)
```
data: {"content": "Dựa trên tài liệu bạn cung cấp..."}
data: {"content": " Tôi thấy rằng..."}
data: {"done": true, "processed_files": ["document1.pdf"], "total_files": 2}
```

**Supported File Types**:
- PDF documents
- Word documents (.docx)
- Text files (.txt)
- Images (for OCR processing)

---

### 4. Clear Chat History

**Endpoint**: `POST /clear-history`

**Mô tả**: Xóa lịch sử chat của một session

**Request Body**:
```json
{
  "session_id": "session_123",
  "userId": "user_456"
}
```

**Response**:
```json
{
  "message": "History cleared successfully",
  "session_id": "session_123",
  "timestamp": "2025-07-11T10:30:00"
}
```

---

### 5. Get AI Providers

**Endpoint**: `GET /ai-providers`

**Mô tả**: Lấy danh sách các AI providers có sẵn

**Response**:
```json
{
  "available_providers": ["deepseek", "chatgpt"],
  "current_provider": "deepseek",
  "timestamp": "2025-07-11T10:30:00"
}
```

---

## 🏦 Loan Assessment Services

### 1. Loan Credit Assessment

**Endpoint**: `POST /api/loan/assessment`

**Mô tả**: API thẩm định hồ sơ vay ngân hàng với DeepSeek Reasoning

**Request Body**:
```json
{
  "applicationId": "APP_20250711_001",
  "loanAmount": 500000000,
  "loanTerm": "15 năm",
  "interestRate": 8.5,
  "fullName": "Nguyễn Văn A",
  "monthlyIncome": 30000000,
  "primaryIncomeSource": "Lương",
  "companyName": "Công ty ABC",
  "jobTitle": "Kỹ sư phần mềm",
  "workExperience": 5,
  "collateralValue": 800000000,
  "monthlyDebtPayment": 5000000,
  "otherIncomeAmount": 2000000,
  "dependents": 2,
  "maritalStatus": "Đã kết hôn",
  "email": "nguyen.van.a@email.com",
  "phoneNumber": "0901234567",
  "phoneCountryCode": "+84"
}
```

**Response**:
```json
{
  "success": true,
  "applicationId": "APP_20250711_001",
  "assessmentId": "assessment_1720684200000",
  "status": "APPROVED",
  "confidence": 0.85,
  "creditScore": 750,
  "reasoning": "Khách hàng có thu nhập ổn định...",
  "riskFactors": [
    "DTI ratio cao (45%)",
    "Thời gian làm việc ngắn"
  ],
  "recommendations": [
    "Yêu cầu bảo lãnh bổ sung",
    "Giảm số tiền vay xuống 450 triệu"
  ],
  "approvedAmount": 450000000,
  "interestRate": 9.2,
  "monthlyPayment": 4250000,
  "loanToValue": 0.65,
  "debtToIncome": 0.42,
  "conditions": [
    "Cung cấp bảng lương 6 tháng gần nhất",
    "Bảo hiểm khoản vay"
  ],
  "collateralValuation": {
    "estimatedValue": 800000000,
    "ltvRatio": 0.65,
    "riskAssessment": "LOW"
  },
  "financialAnalysis": {
    "totalMonthlyIncome": 32000000,
    "estimatedMonthlyPayment": 4250000,
    "remainingIncome": 22750000,
    "debtServiceCoverage": 3.2
  },
  "processingDetails": {
    "assessmentId": "assessment_1720684200000",
    "processingTime": 2.45,
    "reasoningDuration": 1.8,
    "modelUsed": "deepseek-reasoning"
  }
}
```

**Các trường bắt buộc**:
- `applicationId`: ID đơn vay
- `loanAmount`: Số tiền vay (VNĐ)
- `monthlyIncome`: Thu nhập hàng tháng (VNĐ)

**Các chỉ số đánh giá**:
- **DTI Ratio**: Tỷ lệ nợ/thu nhập (≤40% tốt, >50% rủi ro)
- **LTV Ratio**: Tỷ lệ vay/giá trị tài sản (≤70% tốt, >80% rủi ro)
- **Credit Score**: Điểm tín dụng (300-850)
- **Debt Service Coverage**: Khả năng thanh toán nợ (>1.25x recommended)

---

## 🆔 OCR Services

### 1. CCCD OCR Processing

**Endpoint**: `POST /api/ocr/cccd`

**Mô tả**: API nhận dạng thông tin từ Căn cước công dân (CCCD) Việt Nam

**Request Body**:
```json
{
  "image": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEA...",
  "extract_mode": "full"
}
```

**Response**:
```json
{
  "success": true,
  "extracted_data": {
    "id_number": "001234567890",
    "full_name": "NGUYỄN VĂN A",
    "date_of_birth": "01/01/1990",
    "gender": "Nam",
    "nationality": "Việt Nam",
    "place_of_origin": "Hà Nội",
    "place_of_residence": "123 Đường ABC, Phường XYZ, Quận 1, TP.HCM",
    "issue_date": "01/01/2021",
    "expiry_date": "01/01/2031",
    "issuing_authority": "Cục Cảnh sát quản lý hành chính về trật tự xã hội"
  },
  "confidence_scores": {
    "id_number": 0.98,
    "full_name": 0.95,
    "date_of_birth": 0.97,
    "overall": 0.96
  },
  "processing_time": 1.23,
  "model_used": "gpt-4-vision",
  "image_quality": "HIGH"
}
```

**Tham số**:
- `image` (string, required): Ảnh CCCD được encode base64
- `extract_mode` (string, optional): "full" hoặc "basic"

**Supported Image Formats**:
- JPEG, PNG, WebP
- Kích thước tối đa: 10MB
- Độ phân giải khuyến nghị: ≥1024x768

---

### 2. Test OCR URL

**Endpoint**: `POST /test-ocr-url`

**Mô tả**: API test OCR với URL ảnh

**Request Body**:
```json
{
  "image_url": "https://example.com/cccd-image.jpg"
}
```

---

## 🤖 AI Sales Agent Services

### 1. Process User Input

**Endpoint**: `POST /ai-sales-agent/process`

**Mô tả**: API xử lý đầu vào người dùng trong quy trình tư vấn vay thông minh

**Request Body**:
```json
{
  "sessionId": "loan_session_123",
  "userMessage": "Tôi muốn vay 500 triệu để mua nhà"
}
```

**Response**:
```json
{
  "sessionId": "loan_session_123",
  "response": "Cảm ơn anh đã quan tâm đến sản phẩm vay mua nhà. Với số tiền 500 triệu, chúng tôi có thể hỗ trợ anh. Cho tôi xin thông tin về loại hình vay anh mong muốn?",
  "currentStep": "STEP_1_2",
  "extractedFields": {
    "loanAmount": 500000000
  },
  "isCompleted": false,
  "nextStep": "STEP_1_2",
  "missingFields": ["loanType"],
  "confidence": 0.92
}
```

**Quy trình 13 bước**:
1. **Step 1.1**: Số tiền vay
2. **Step 1.2**: Loại hình vay
3. **Step 2.1**: Thông tin cá nhân
4. **Step 2.2**: Số người phụ thuộc
5. **Step 3.1**: Loại tài sản đảm bảo
6. **Step 3.2**: Giá trị tài sản
7. **Step 4.1**: Nguồn thu nhập chính
8. **Step 4.2**: Thông tin công việc
9. **Step 4.3**: Tài sản khác
10. **Step 5.1**: Có nợ hiện tại không
11. **Step 5.2**: Chi tiết nợ (nếu có)
12. **Step 6**: Xác nhận thông tin tổng hợp
13. **Step 7**: Thẩm định hồ sơ vay tự động

---

### 2. Get Session Info

**Endpoint**: `GET /ai-sales-agent/session/{session_id}`

**Mô tả**: Lấy thông tin về phiên tư vấn

**Response**:
```json
{
  "sessionId": "loan_session_123",
  "currentStep": "STEP_2_1",
  "extractedFields": {
    "loanAmount": 500000000,
    "loanType": "Thế chấp"
  },
  "isCompleted": false,
  "createdAt": "2025-07-11T10:00:00",
  "updatedAt": "2025-07-11T10:15:00",
  "messageCount": 6
}
```

---

### 3. Get Conversation History

**Endpoint**: `GET /ai-sales-agent/session/{session_id}/history`

**Mô tả**: Lấy lịch sử hội thoại đầy đủ

**Response**:
```json
{
  "sessionId": "loan_session_123",
  "history": [
    {
      "timestamp": "2025-07-11T10:00:00",
      "role": "assistant",
      "message": "Xin chào! Tôi là AI Assistant...",
      "step": "STEP_1_1"
    },
    {
      "timestamp": "2025-07-11T10:01:00",
      "role": "user",
      "message": "Tôi muốn vay 500 triệu",
      "step": "STEP_1_1"
    }
  ],
  "currentStep": "STEP_2_1",
  "isCompleted": false
}
```

---

### 4. Reset Session

**Endpoint**: `POST /ai-sales-agent/session/{session_id}/reset`

**Mô tả**: Reset phiên tư vấn để bắt đầu lại

**Response**:
```json
{
  "sessionId": "loan_session_123",
  "message": "Xin chào! Tôi là AI Assistant của ngân hàng...",
  "currentStep": "STEP_1_1",
  "status": "reset_complete"
}
```

---

### 6. Confirmation Summary

**Endpoint**: `POST /ai-sales-agent/process` (Step 6)

**Mô tả**: Hiển thị tổng hợp thông tin để người dùng xác nhận trước khi thẩm định

**Request Body**:
```json
{
  "sessionId": "loan_session_123",
  "userMessage": "Xác nhận" 
}
```

**Response - Step 6 Summary**:
```json
{
  "sessionId": "loan_session_123",
  "response": "📋 **XÁC NHẬN THÔNG TIN HỒ SƠ VAY**\n\n**1️⃣ THÔNG TIN KHOẢN VAY**\n• Số tiền vay: 500,000,000 VNĐ\n• Thời hạn: 15 năm\n• Mục đích: Mua nhà\n• Hình thức: Thế chấp\n\n**2️⃣ THÔNG TIN CÁ NHÂN**\n• Họ tên: Nguyễn Văn A\n• Giới tính: Nam\n• Năm sinh: 1990\n• SĐT: 0901234567\n• Email: nguyen.van.a@email.com\n• Tình trạng hôn nhân: Đã kết hôn\n• Số người phụ thuộc: 2\n\n**3️⃣ TÀI SẢN ĐẢM BẢO**\n• Loại tài sản: Bất động sản\n• Mô tả: Căn hộ chung cư\n• Giá trị ước tính: 800,000,000 VNĐ\n\n**4️⃣ THÔNG TIN TÀI CHÍNH**\n• Thu nhập hàng tháng: 30,000,000 VNĐ\n• Nguồn thu nhập: Lương\n• Công ty: Công ty ABC\n• Chức vụ: Kỹ sư phần mềm\n• Kinh nghiệm: 5 năm\n• Thu nhập khác: 2,000,000 VNĐ\n\n**5️⃣ THÔNG TIN NỢ**\n• Có nợ hiện tại: Có\n• Tổng dư nợ: 50,000,000 VNĐ\n• Trả nợ hàng tháng: 5,000,000 VNĐ\n\n---\n⚠️ **Vui lòng kiểm tra kỹ thông tin trên.**\n\nTrả lời:\n- **\"Xác nhận\"** - nếu thông tin chính xác\n- **\"Sửa [field]: [giá trị mới]\"** - để chỉnh sửa\n  Ví dụ: \"Sửa thu nhập: 35 triệu\"",
  "currentStep": "STEP_6",
  "extractedFields": {
    "loanAmount": 500000000,
    "loanTerm": "15 năm",
    "loanPurpose": "Mua nhà",
    "loanType": "Thế chấp",
    "fullName": "Nguyễn Văn A",
    "gender": "Nam",
    "birthYear": 1990,
    "phoneNumber": "0901234567",
    "email": "nguyen.van.a@email.com",
    "maritalStatus": "Đã kết hôn",
    "dependents": 2,
    "collateralType": "Bất động sản",
    "collateralInfo": "Căn hộ chung cư",
    "collateralValue": 800000000,
    "monthlyIncome": 30000000,
    "primaryIncomeSource": "Lương",
    "companyName": "Công ty ABC",
    "jobTitle": "Kỹ sư phần mềm",
    "workExperience": 5,
    "otherIncomeAmount": 2000000,
    "hasExistingDebt": true,
    "totalDebtAmount": 50000000,
    "monthlyDebtPayment": 5000000
  },
  "isCompleted": false,
  "nextStep": "STEP_7",
  "missingFields": ["userConfirmation"],
  "confidence": 1.0,
  "actions": [
    "Xác nhận - để tiếp tục thẩm định",
    "Sửa [tên field]: [giá trị mới] - để chỉnh sửa"
  ]
}
```

**Editing Commands**:
- `"Sửa lương: 35 triệu"` → Cập nhật monthlyIncome = 35000000
- `"Sửa tên: Nguyễn Thị B"` → Cập nhật fullName = "Nguyễn Thị B"
- `"Sửa tài sản: 1 tỷ"` → Cập nhật collateralValue = 1000000000

---

### 7. Loan Assessment Processing

**Endpoint**: `POST /ai-sales-agent/process` (Step 7)

**Mô tả**: Thực hiện thẩm định hồ sơ vay tự động sau khi user xác nhận

**Request Body**:
```json
{
  "sessionId": "loan_session_123",
  "userMessage": "Xác nhận"
}
```

**Response - Step 7 Assessment**:
```json
{
  "sessionId": "loan_session_123",
  "response": "🎉 **THẨM ĐỊNH HỒ SƠ HOÀN TẤT**\n\n✅ **KẾT QUẢ: CHẤP THUẬN**\n\n📊 **CHI TIẾT ĐÁNH GIÁ:**\n• Điểm tín dụng: 750/850 (Tốt)\n• Tỷ lệ DTI: 42% (Chấp nhận được)\n• Tỷ lệ LTV: 65% (An toàn)\n• Độ tin cậy: 85%\n\n💰 **ĐIỀU KIỆN VAY:**\n• Số tiền được duyệt: 450,000,000 VNĐ\n• Lãi suất: 9.2%/năm\n• Kỳ hạn: 15 năm\n• Trả góp hàng tháng: 4,250,000 VNĐ\n\n⚠️ **YÊU CẦU BỔ SUNG:**\n• Cung cấp bảng lương 6 tháng gần nhất\n• Bảo hiểm khoản vay\n• Thẩm định giá tài sản chính thức\n\n📞 **BƯỚC TIẾP THEO:**\nNhân viên tư vấn sẽ liên hệ trong 24h để hướng dẫn hoàn thiện hồ sơ.\n\nMã hồ sơ: **APP_20250711_001**",
  "currentStep": "STEP_7",
  "extractedFields": {
    "loanAmount": 500000000,
    "loanType": "Thế chấp",
    "assessmentResult": {
      "status": "APPROVED",
      "confidence": 0.85,
      "creditScore": 750,
      "approvedAmount": 450000000,
      "interestRate": 9.2,
      "monthlyPayment": 4250000,
      "loanToValue": 0.65,
      "debtToIncome": 0.42,
      "conditions": [
        "Cung cấp bảng lương 6 tháng gần nhất",
        "Bảo hiểm khoản vay",
        "Thẩm định giá tài sản chính thức"
      ],
      "applicationId": "APP_20250711_001"
    }
  },
  "isCompleted": true,
  "nextStep": null,
  "missingFields": [],
  "confidence": 0.85
}
```

**Assessment API Call Structure**:

Khi user xác nhận ở Step 6, hệ thống sẽ tự động gọi API assessment:

```bash
POST /api/loan/assessment
Content-Type: application/json

{
  "applicationId": "APP_20250711_001",
  "loanAmount": 500000000,
  "loanTerm": "15 năm",
  "interestRate": 8.5,
  "fullName": "Nguyễn Văn A",
  "monthlyIncome": 30000000,
  "primaryIncomeSource": "Lương",
  "companyName": "Công ty ABC",
  "jobTitle": "Kỹ sư phần mềm",
  "workExperience": 5,
  "collateralValue": 800000000,
  "monthlyDebtPayment": 5000000,
  "otherIncomeAmount": 2000000,
  "dependents": 2,
  "maritalStatus": "Đã kết hôn",
  "email": "nguyen.van.a@email.com",
  "phoneNumber": "0901234567",
  "phoneCountryCode": "+84"
}
```

**Assessment Flow**:
1. **Step 6**: Hiển thị summary → User xác nhận hoặc sửa
2. **Data Preparation**: Convert extracted_fields → assessment API format
3. **API Call**: POST /api/loan/assessment với dữ liệu đã chuẩn bị
4. **Step 7**: Hiển thị kết quả thẩm định đẹp mắt cho user

**Error Handling**:
```json
{
  "sessionId": "loan_session_123",
  "response": "❌ **LỖI THẨM ĐỊNH**\n\nHệ thống tạm thời gặp sự cố. Vui lòng thử lại sau ít phút.\n\nMã lỗi: ASSESSMENT_SERVICE_ERROR",
  "currentStep": "STEP_6", 
  "error": "Assessment service temporarily unavailable",
  "isCompleted": false
}
```

---

### 8. Health Check

**Endpoint**: `GET /ai-sales-agent/health`

**Mô tả**: Kiểm tra tình trạng hoạt động của AI Sales Agent

**Response**:
```json
{
  "status": "healthy",
  "service": "AI Sales Agent",
  "timestamp": "2025-07-11T10:30:00",
  "active_sessions": 45
}
```

---

## 📊 Error Handling

### Cấu trúc lỗi chung

```json
{
  "success": false,
  "error": "Mô tả lỗi",
  "error_code": "VALIDATION_ERROR",
  "timestamp": "2025-07-11T10:30:00",
  "processing_time": 0.15
}
```

### Các mã lỗi phổ biến

| Mã lỗi | HTTP Status | Mô tả |
|---------|-------------|--------|
| `VALIDATION_ERROR` | 400 | Dữ liệu đầu vào không hợp lệ |
| `API_KEY_MISSING` | 401 | Thiếu API key |
| `SESSION_NOT_FOUND` | 404 | Không tìm thấy session |
| `AI_SERVICE_ERROR` | 500 | Lỗi từ dịch vụ AI |
| `PROCESSING_TIMEOUT` | 504 | Timeout xử lý |

---

## 🔧 Configuration

### Environment Variables

```bash
# AI API Keys
DEEPSEEK_API_KEY=your_deepseek_api_key
CHATGPT_API_KEY=your_chatgpt_api_key

# Server Configuration
PORT=8000
DEBUG=true

# Database (Redis for sessions)
REDIS_URL=redis://localhost:6379

# Logging
LOG_LEVEL=INFO
```

---

## 📈 Rate Limits

| Endpoint | Giới hạn | Thời gian |
|----------|----------|-----------|
| `/chat` | 100 requests | 1 phút |
| `/chat-stream` | 50 requests | 1 phút |
| `/api/loan/assessment` | 20 requests | 1 phút |
| `/api/ocr/cccd` | 30 requests | 1 phút |
| `/ai-sales-agent/*` | 200 requests | 1 phút |

---

## 🚀 Examples

### Quy trình hoàn chỉnh AI Sales Agent (13 bước)

```bash
# 1. Bắt đầu conversation
curl -X POST "http://localhost:8000/ai-sales-agent/process" \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "test_session",
    "userMessage": "Tôi muốn vay tiền mua nhà"
  }'

# 2. Tiếp tục với thông tin số tiền (Step 1.1)
curl -X POST "http://localhost:8000/ai-sales-agent/process" \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "test_session",
    "userMessage": "500 triệu"
  }'

# 3. Chọn loại vay (Step 1.2)
curl -X POST "http://localhost:8000/ai-sales-agent/process" \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "test_session", 
    "userMessage": "Thế chấp"
  }'

# 4. Thông tin cá nhân (Step 2.1)
curl -X POST "http://localhost:8000/ai-sales-agent/process" \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "test_session",
    "userMessage": "Tôi tên Nguyễn Văn A, nam, sinh năm 1990, SĐT 0901234567"
  }'

# 5. Số người phụ thuộc (Step 2.2)
curl -X POST "http://localhost:8000/ai-sales-agent/process" \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "test_session",
    "userMessage": "Tôi đã kết hôn và có 2 người phụ thuộc"
  }'

# ... Steps 3.1-5.2 (collateral, financial, debt info) ...

# 12. Xác nhận thông tin (Step 6)
curl -X POST "http://localhost:8000/ai-sales-agent/process" \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "test_session",
    "userMessage": "Xác nhận"
  }'

# 13. Thẩm định hồ sơ tự động (Step 7)
# → Hệ thống tự động gọi /api/loan/assessment và trả về kết quả đẹp mắt
```

### Ví dụ chỉnh sửa thông tin ở Step 6

```bash
# Sửa thu nhập
curl -X POST "http://localhost:8000/ai-sales-agent/process" \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "test_session",
    "userMessage": "Sửa thu nhập: 35 triệu"
  }'

# Sửa giá trị tài sản
curl -X POST "http://localhost:8000/ai-sales-agent/process" \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "test_session",
    "userMessage": "Sửa tài sản: 1 tỷ"
  }'

# Sau khi sửa xong, xác nhận lại
curl -X POST "http://localhost:8000/ai-sales-agent/process" \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "test_session",
    "userMessage": "Xác nhận"
  }'
```

### Streaming Chat với file

```javascript
const eventSource = new EventSource('/chat-with-files-stream', {
  method: 'POST',
  body: JSON.stringify({
    question: "Phân tích báo cáo tài chính này",
    files: ["base64_encoded_pdf"],
    file_names: ["financial_report.pdf"],
    session_id: "chat_123"
  })
});

eventSource.onmessage = function(event) {
  const data = JSON.parse(event.data);
  if (data.content) {
    console.log(data.content);
  }
  if (data.done) {
    eventSource.close();
  }
};
```

---

## 🔄 Backend Integration Guide

### Data Mapping cho Assessment API

Khi user xác nhận thông tin ở Step 6, backend cần chuẩn bị dữ liệu để gọi `/api/loan/assessment`:

```python
def prepare_assessment_data(extracted_fields: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert AI Sales Agent extracted fields to Loan Assessment API format
    """
    
    # Generate unique application ID
    application_id = f"APP_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Map fields with defaults
    assessment_data = {
        # Required fields
        "applicationId": application_id,
        "loanAmount": extracted_fields.get("loanAmount", 0),
        "monthlyIncome": extracted_fields.get("monthlyIncome", 0),
        
        # Loan details
        "loanTerm": extracted_fields.get("loanTerm", "15 năm"),
        "interestRate": 8.5,  # Default rate, có thể lấy từ config
        "loanPurpose": extracted_fields.get("loanPurpose", ""),
        
        # Personal info
        "fullName": extracted_fields.get("fullName", ""),
        "gender": extracted_fields.get("gender", ""),
        "birthYear": extracted_fields.get("birthYear", 0),
        "maritalStatus": extracted_fields.get("maritalStatus", ""),
        "dependents": extracted_fields.get("dependents", 0),
        
        # Contact info
        "email": extracted_fields.get("email", ""),
        "phoneNumber": extracted_fields.get("phoneNumber", ""),
        "phoneCountryCode": "+84",
        
        # Financial info
        "primaryIncomeSource": extracted_fields.get("primaryIncomeSource", ""),
        "companyName": extracted_fields.get("companyName", ""),
        "jobTitle": extracted_fields.get("jobTitle", ""),
        "workExperience": extracted_fields.get("workExperience", 0),
        "otherIncomeAmount": extracted_fields.get("otherIncomeAmount", 0),
        
        # Banking info
        "bankName": extracted_fields.get("bankName", ""),
        "bankAccount": extracted_fields.get("bankAccount", ""),
        
        # Collateral info
        "collateralType": extracted_fields.get("collateralType", ""),
        "collateralValue": extracted_fields.get("collateralValue", 0),
        "collateralDescription": extracted_fields.get("collateralInfo", ""),
        
        # Debt info
        "hasExistingDebt": extracted_fields.get("hasExistingDebt", False),
        "totalDebtAmount": extracted_fields.get("totalDebtAmount", 0),
        "monthlyDebtPayment": extracted_fields.get("monthlyDebtPayment", 0),
        "debtDetails": extracted_fields.get("debtDetails", []),
        
        # Additional info
        "additionalAssets": extracted_fields.get("additionalAssets", []),
        "monthlyExpenses": extracted_fields.get("monthlyExpenses", 0)
    }
    
    return assessment_data

# Example usage in AI Sales Agent
async def process_step_7_assessment(session_id: str, extracted_fields: Dict[str, Any]):
    """
    Process Step 7 - Call assessment API and format result
    """
    
    try:
        # 1. Prepare data for assessment API
        assessment_data = prepare_assessment_data(extracted_fields)
        
        # 2. Call assessment API
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:8000/api/loan/assessment",
                json=assessment_data,
                timeout=30.0
            )
            response.raise_for_status()
            assessment_result = response.json()
        
        # 3. Format result for display
        if assessment_result["success"]:
            formatted_response = format_assessment_success(assessment_result)
        else:
            formatted_response = format_assessment_error(assessment_result)
        
        # 4. Update session with result
        session_data = {
            "currentStep": "STEP_7",
            "isCompleted": True,
            "assessmentResult": assessment_result,
            "applicationId": assessment_data["applicationId"]
        }
        
        return {
            "response": formatted_response,
            "session_data": session_data
        }
        
    except Exception as e:
        return {
            "response": f"❌ **LỖI THẨM ĐỊNH**\n\nHệ thống tạm thời gặp sự cố: {str(e)}\n\nVui lòng thử lại sau ít phút.",
            "session_data": {
                "currentStep": "STEP_6",  # Back to confirmation
                "error": str(e)
            }
        }

def format_assessment_success(result: Dict[str, Any]) -> str:
    """Format successful assessment result for display"""
    
    status_emoji = {
        "APPROVED": "✅",
        "CONDITIONAL": "⚠️", 
        "REJECTED": "❌"
    }
    
    status_text = {
        "APPROVED": "CHẤP THUẬN",
        "CONDITIONAL": "CHẤP THUẬN CÓ ĐIỀU KIỆN",
        "REJECTED": "TỪ CHỐI"
    }
    
    emoji = status_emoji.get(result["status"], "📋")
    status = status_text.get(result["status"], result["status"])
    
    response = f"""🎉 **THẨM ĐỊNH HỒ SƠ HOÀN TẤT**

{emoji} **KẾT QUẢ: {status}**

📊 **CHI TIẾT ĐÁNH GIÁ:**
• Điểm tín dụng: {result.get('creditScore', 'N/A')}/850
• Tỷ lệ DTI: {result.get('debtToIncome', 0)*100:.0f}%
• Tỷ lệ LTV: {result.get('loanToValue', 0)*100:.0f}%
• Độ tin cậy: {result.get('confidence', 0)*100:.0f}%

💰 **ĐIỀU KIỆN VAY:**
• Số tiền được duyệt: {result.get('approvedAmount', 0):,} VNĐ
• Lãi suất: {result.get('interestRate', 0)}%/năm
• Trả góp hàng tháng: {result.get('monthlyPayment', 0):,} VNĐ"""

    # Add conditions if any
    if result.get("conditions"):
        response += f"\n\n⚠️ **YÊU CẦU BỔ SUNG:**"
        for condition in result["conditions"]:
            response += f"\n• {condition}"
    
    # Add reasoning if available
    if result.get("reasoning"):
        response += f"\n\n💡 **NHẬN XÉT:**\n{result['reasoning']}"
    
    response += f"\n\n📞 **BƯỚC TIẾP THEO:**\nNhân viên tư vấn sẽ liên hệ trong 24h để hướng dẫn hoàn thiện hồ sơ.\n\nMã hồ sơ: **{result.get('applicationId', 'N/A')}**"
    
    return response
```

### Frontend Display Components

```javascript
// React component for Step 7 assessment result display
const AssessmentResult = ({ assessmentData }) => {
  const getStatusColor = (status) => {
    switch(status) {
      case 'APPROVED': return 'text-green-600';
      case 'CONDITIONAL': return 'text-yellow-600';
      case 'REJECTED': return 'text-red-600';
      default: return 'text-gray-600';
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <div className="text-center mb-6">
        <h2 className="text-2xl font-bold mb-2">🎉 Thẩm định hồ sơ hoàn tất</h2>
        <div className={`text-xl font-semibold ${getStatusColor(assessmentData.status)}`}>
          {assessmentData.status === 'APPROVED' ? '✅' : 
           assessmentData.status === 'CONDITIONAL' ? '⚠️' : '❌'} 
          {assessmentData.status}
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Assessment Details */}
        <div className="bg-blue-50 rounded-lg p-4">
          <h3 className="font-semibold mb-3">📊 Chi tiết đánh giá</h3>
          <div className="space-y-2 text-sm">
            <div>Điểm tín dụng: <span className="font-medium">{assessmentData.creditScore}/850</span></div>
            <div>Tỷ lệ DTI: <span className="font-medium">{(assessmentData.debtToIncome * 100).toFixed(0)}%</span></div>
            <div>Tỷ lệ LTV: <span className="font-medium">{(assessmentData.loanToValue * 100).toFixed(0)}%</span></div>
            <div>Độ tin cậy: <span className="font-medium">{(assessmentData.confidence * 100).toFixed(0)}%</span></div>
          </div>
        </div>

        {/* Loan Terms */}
        <div className="bg-green-50 rounded-lg p-4">
          <h3 className="font-semibold mb-3">💰 Điều kiện vay</h3>
          <div className="space-y-2 text-sm">
            <div>Số tiền duyệt: <span className="font-medium">{assessmentData.approvedAmount?.toLocaleString()} VNĐ</span></div>
            <div>Lãi suất: <span className="font-medium">{assessmentData.interestRate}%/năm</span></div>
            <div>Trả góp/tháng: <span className="font-medium">{assessmentData.monthlyPayment?.toLocaleString()} VNĐ</span></div>
          </div>
        </div>
      </div>

      {/* Conditions */}
      {assessmentData.conditions && assessmentData.conditions.length > 0 && (
        <div className="mt-6 bg-yellow-50 rounded-lg p-4">
          <h3 className="font-semibold mb-3">⚠️ Yêu cầu bổ sung</h3>
          <ul className="space-y-1 text-sm">
            {assessmentData.conditions.map((condition, index) => (
              <li key={index}>• {condition}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Next Steps */}
      <div className="mt-6 bg-blue-100 rounded-lg p-4 text-center">
        <h3 className="font-semibold mb-2">📞 Bước tiếp theo</h3>
        <p className="text-sm">Nhân viên tư vấn sẽ liên hệ trong 24h để hướng dẫn hoàn thiện hồ sơ.</p>
        <p className="text-xs text-gray-600 mt-2">Mã hồ sơ: <span className="font-mono">{assessmentData.applicationId}</span></p>
      </div>
    </div>
  );
};
```
