# AI Sales Agent Integration Guide

## Overview

AI Sales Agent là một hệ thống hội thoại linh hoạt dành cho tư vấn vay vốn ngân hàng với khả năng hiểu tiếng Việt và thu thập dữ liệu theo độ ưu tiên.

## Components

- **AI Provider**: Trích xuất thông tin linh hoạt và tạo phản hồi
- **NLG (Natural Language Generation)**: Tạo câu hỏi và phản hồi theo ngữ cảnh  
- **API**: Các endpoint FastAPI cho quản lý hội thoại
- **Services**: Logic nghiệp vụ cốt lõi cho thẩm định vay

## API Endpoints

### 1. Natural Conversation
```
POST /api/sales-agent/chat
```
- Endpoint hội thoại tự nhiên cho tư vấn vay vốn
- Thu thập thông tin linh hoạt theo độ ưu tiên
- Tự động trích xuất dữ liệu từ câu trả lời

### 2. Loan Assessment
```
POST /api/sales-agent/assess
```
- Thẩm định vay dựa trên dữ liệu đã thu thập
- Trả về kết quả đánh giá chi tiết

### 3. Check Readiness
```
POST /api/sales-agent/check-readiness
```
- Kiểm tra mức độ sẵn sàng cho thẩm định
- Trả về phần trăm hoàn thành và các field còn thiếu

### 4. Smart Suggestions
```
GET /api/sales-agent/suggest-questions/{session_id}
```
- Gợi ý câu hỏi thông minh dựa trên dữ liệu hiện có
- Ưu tiên các field quan trọng chưa có

### 5. Session Management
```
DELETE /api/sales-agent/session/{session_id}
```
- Xóa dữ liệu session và reset hội thoại

## Setup Integration

### 1. FastAPI Integration

```python
from fastapi import FastAPI
from src.ai_sales_agent.api.routes import router as ai_sales_agent_router

# Create FastAPI app
app = FastAPI()

# Include AI Sales Agent routes with prefix
app.include_router(
    ai_sales_agent_router, 
    prefix="/api/sales-agent",
    tags=["AI Sales Agent - Loan Consultation"]
)
```

### 2. Environment Configuration

Đảm bảo có các API keys trong file `.env`:

```properties
DEEPSEEK_API_KEY=your-deepseek-api-key
CHATGPT_API_KEY=your-chatgpt-api-key
```

## Usage Examples

### Python Client Example

```python
import requests

# Test flexible conversation
session_id = "test_123"
base_url = "http://localhost:8000/api/sales-agent"

# 1. Start natural conversation
response1 = requests.post(f"{base_url}/chat", json={
    "sessionId": session_id,
    "message": "Tôi cần vay 2 tỷ để mua nhà, tên tôi là Nguyễn Văn A"
})

print("AI Response:", response1.json()["message"])
print("Extracted Data:", response1.json()["extractedData"])
print("Readiness:", response1.json()["readiness"]["percentage"], "%")

# 2. Continue naturally
response2 = requests.post(f"{base_url}/chat", json={
    "sessionId": session_id,
    "message": "Thu nhập 30 triệu/tháng, làm IT, 35 tuổi"
})

print("AI Response:", response2.json()["message"])
print("New Extracted:", response2.json()["extractedData"])

# 3. Check readiness for assessment
readiness = requests.post(f"{base_url}/check-readiness", json={
    "sessionId": session_id
})

print("Ready for assessment:", readiness.json()["ready"])
print("Missing fields:", readiness.json()["missingFields"])

# 4. Get smart suggestions
suggestions = requests.get(f"{base_url}/suggest-questions/{session_id}")
print("Suggested questions:", suggestions.json()["suggestions"])

# 5. Perform assessment if ready
if readiness.json()["ready"]:
    assessment = requests.post(f"{base_url}/assess", json={
        "sessionId": session_id
    })
    print("Assessment result:", assessment.json()["formattedMessage"])
    print("Approval status:", assessment.json()["approved"])
```

### cURL Examples

```bash
# 1. Start conversation
curl -X POST "http://localhost:8000/api/sales-agent/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "test_123",
    "message": "Tôi muốn vay 1 tỷ mua nhà"
  }'

# 2. Check readiness
curl -X POST "http://localhost:8000/api/sales-agent/check-readiness" \
  -H "Content-Type: application/json" \
  -d '{"sessionId": "test_123"}'

# 3. Get suggestions
curl -X GET "http://localhost:8000/api/sales-agent/suggest-questions/test_123"

# 4. Assess loan
curl -X POST "http://localhost:8000/api/sales-agent/assess" \
  -H "Content-Type: application/json" \
  -d '{"sessionId": "test_123"}'

# 5. Clear session
curl -X DELETE "http://localhost:8000/api/sales-agent/session/test_123"
```

## Field Priorities

Hệ thống sử dụng độ ưu tiên field để tối ưu hóa quá trình thu thập:

| Priority | Field | Description |
|----------|-------|-------------|
| 100 | fullName | Họ và tên |
| 95 | loanAmount | Số tiền vay |
| 90 | loanPurpose | Mục đích vay |
| 85 | monthlyIncome | Thu nhập hàng tháng |
| 80 | age | Tuổi |
| ... | ... | ... |

## Response Format

### Chat Response
```json
{
  "message": "Cảm ơn anh Nguyễn Văn A! Anh muốn vay 2 tỷ để mua nhà. Để tôi hỗ trợ anh tốt nhất, anh có thể cho biết thu nhập hàng tháng của anh là bao nhiêu?",
  "extractedData": {
    "fullName": "Nguyễn Văn A",
    "loanAmount": 2000000000,
    "loanPurpose": "mua nhà"
  },
  "readiness": {
    "percentage": 25,
    "ready": false,
    "missingCriticalFields": ["monthlyIncome", "age", "occupation"]
  },
  "suggestions": ["Thu nhập hàng tháng", "Nghề nghiệp", "Tuổi"]
}
```

### Assessment Response
```json
{
  "approved": true,
  "loanAmount": 2000000000,
  "interestRate": 8.5,
  "loanTerm": 240,
  "monthlyPayment": 17534000,
  "formattedMessage": "Chúc mừng! Hồ sơ vay của anh đã được phê duyệt..."
}
```

## Development Notes

### Testing
```bash
# Run interactive console test
python test_interactive_console.py

# Test specific endpoints
python -m pytest tests/test_ai_sales_agent.py
```

### Logging
- Tất cả hội thoại được log để phân tích
- Session data được lưu in-memory (khuyến nghị Redis cho production)
- Extraction confidence tracking

### Production Considerations
- Sử dụng Redis cho session storage
- Rate limiting cho API endpoints  
- Monitoring và alerting
- Data encryption cho thông tin nhạy cảm

## Version History

- **v1.0.0**: Initial flexible approach implementation
- Eliminated step-by-step mode in favor of flexible conversation
- Priority-based field extraction
- Smart question suggestions
