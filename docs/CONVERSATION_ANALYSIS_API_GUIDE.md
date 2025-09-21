# Conversation Analysis API Documentation

## Tổng Quan

API phân tích cuộc trò chuyện được tách riêng từ unified chat routes để dễ quản lý và sử dụng **Google Gemini** làm AI Provider chuyên biệt cho phân tích business intelligence và remarketing insights.

## 🎯 Mục Tiêu Tách API

### Trước khi tách:
- ❌ Endpoints phân tích nằm chung với chat API
- ❌ Sử dụng cùng AI provider với chat (DeepSeek)
- ❌ Khó quản lý và maintain riêng biệt
- ❌ Thiếu tính chuyên biệt cho analysis tasks

### Sau khi tách:
- ✅ **API riêng biệt**: `/api/conversation/*` 
- ✅ **Google Gemini**: AI Provider chuyên biệt cho analysis
- ✅ **Dễ maintain**: Code tách biệt, responsibility rõ ràng
- ✅ **Scalable**: Có thể phát triển independent features
- ✅ **Specialized**: Tối ưu cho business intelligence tasks

## 📋 Endpoints Mới

### 1. POST `/api/conversation/analyze`

**Mục đích:** Phân tích chuyên sâu cuộc trò chuyện cho remarketing và business insights

**Headers:**
```
Content-Type: application/json
X-Company-Id: {company_id}
```

**Request Body:**
```json
{
  "session_id": "session_123",
  "conversation_id": "conv_456",  // Optional, alternative to session_id
  "company_id": "company_001"     // Optional if provided in header
}
```

**Response:**
```json
{
  "session_id": "session_123",
  "conversation_id": "conv_456",
  "company_id": "company_001",
  "ai_provider": "google_gemini",
  "analyzed_at": "2025-07-25T10:30:00Z",
  "analysis": {
    "primary_intent": "SALES_INQUIRY",
    "intent_confidence": 0.92,
    "intent_evolution": [
      {
        "turn": 1,
        "intent": "INFORMATION",
        "confidence": 0.8,
        "message_preview": "Tôi muốn biết về..."
      },
      {
        "turn": 3,
        "intent": "SALES_INQUIRY", 
        "confidence": 0.9,
        "message_preview": "Giá bao nhiều?"
      }
    ],
    "customer_satisfaction": "HIGH",
    "satisfaction_indicators": [
      "Khách hàng cảm ơn nhiều lần",
      "Hỏi thêm thông tin chi tiết"
    ],
    "conversation_outcome": "INTERESTED",
    "outcome_reasoning": "Khách hàng đã hỏi giá và yêu cầu thông tin liên hệ",
    "customer_pain_points": [
      "Lo lắng về giá cả",
      "Cần tư vấn về sản phẩm phù hợp"
    ],
    "products_mentioned": [
      "Gói vay mua nhà",
      "Bảo hiểm xe ô tô"
    ],
    "key_requirements": [
      "Lãi suất thấp",
      "Thủ tục nhanh gọn"
    ],
    "unresolved_issues": [
      "Chưa rõ điều kiện vay cụ thể",
      "Chưa có thông tin về phí dịch vụ"
    ],
    "remarketing_opportunities": [
      {
        "type": "EMAIL_CAMPAIGN",
        "priority": "HIGH",
        "suggestion": "Gửi email ưu đãi lãi suất đặc biệt",
        "timing": "24H",
        "target_products": ["Gói vay mua nhà"],
        "personalization": "Nhắc đến yêu cầu lãi suất thấp"
      },
      {
        "type": "PHONE_FOLLOWUP",
        "priority": "MEDIUM", 
        "suggestion": "Gọi điện tư vấn chi tiết",
        "timing": "WEEK",
        "talking_points": ["Điều kiện vay", "Phí dịch vụ"]
      }
    ],
    "improvement_suggestions": [
      {
        "category": "PRODUCT_INFO",
        "issue": "Thiếu thông tin chi tiết về phí dịch vụ",
        "solution": "Bổ sung bảng phí chi tiết",
        "priority": "HIGH"
      }
    ],
    "next_actions": [
      "Gửi email follow-up trong 24h",
      "Chuẩn bị tài liệu điều kiện vay chi tiết"
    ],
    "conversation_sentiment": {
      "overall": "POSITIVE",
      "customer_tone": "FRIENDLY",
      "engagement_level": "HIGH"
    },
    "business_value": {
      "potential_revenue": "HIGH",
      "conversion_probability": 0.75,
      "customer_lifetime_value": "HIGH"
    },
    "ai_performance": {
      "response_relevance": 0.85,
      "response_helpfulness": 0.80,
      "response_speed": "GOOD",
      "missed_opportunities": [
        "Không đề xuất sản phẩm bổ sung"
      ],
      "strengths": [
        "Trả lời chính xác các câu hỏi"
      ]
    },
    "summary": "Khách hàng quan tâm đến gói vay mua nhà...",
    "analysis_metadata": {
      "ai_provider": "google_gemini",
      "analysis_timestamp": "2025-07-25T10:30:00Z",
      "total_messages": 10,
      "user_messages_count": 5,
      "ai_messages_count": 5,
      "analyzer_version": "2.0_gemini"
    }
  },
  "conversation_stats": {
    "duration_seconds": 450,
    "message_count": 10,
    "average_response_time": 2.3
  }
}
```

### 2. GET `/api/conversation/{conversation_id}/summary`

**Mục đích:** Tóm tắt nhanh cuộc trò chuyện không cần phân tích sâu

**Headers:**
```
X-Company-Id: {company_id}
```

**Response:**
```json
{
  "conversation_id": "conv_456",
  "session_id": "session_123", 
  "company_id": "company_001",
  "status": "ACTIVE",
  "message_count": 10,
  "user_messages": 5,
  "ai_messages": 5,
  "created_at": "2025-07-25T10:00:00Z",
  "last_activity": "2025-07-25T10:30:00Z",
  "duration_seconds": 1800,
  "last_message_preview": "Cảm ơn bạn. Tôi sẽ cân nhắc...",
  "quick_stats": {
    "avg_response_length": 150.5,
    "conversation_length": 10,
    "has_images": false,
    "languages_detected": ["VIETNAMESE"],
    "intents_detected": ["INFORMATION", "SALES_INQUIRY"]
  }
}
```

### 3. GET `/api/conversation/list`

**Mục đích:** Liệt kê tất cả cuộc trò chuyện của công ty

**Headers:**
```
X-Company-Id: {company_id}
```

**Query Parameters:**
- `limit` (int, default=50): Số lượng cuộc trò chuyện trả về
- `offset` (int, default=0): Vị trí bắt đầu (pagination)

**Response:**
```json
{
  "conversations": [
    {
      "conversation_id": "conv_456",
      "session_id": "session_123",
      "message_count": 10,
      "user_messages": 5,
      "created_at": "2025-07-25T10:00:00Z",
      "last_activity": "2025-07-25T10:30:00Z",
      "last_message_preview": "Cảm ơn bạn...",
      "status": "ACTIVE"
    }
  ],
  "total": 150,
  "limit": 50,
  "offset": 0,
  "has_more": true
}
```

## 🤖 Google Gemini Integration

### Tại Sao Chọn Gemini?

1. **Specialized for Analysis**: Gemini excels at structured analysis tasks
2. **JSON Output**: Reliable JSON generation for business intelligence
3. **Multi-language**: Excellent Vietnamese and English support
4. **Cost-effective**: Competitive pricing for analysis workloads
5. **Safety Filters**: Built-in content safety for business use

### Gemini Provider Features

```python
from src.providers.gemini_provider import GeminiProvider

# Initialize
gemini = GeminiProvider()

# Check availability
if gemini.enabled:
    # Get completion
    response = await gemini.get_completion(
        prompt="Analyze this conversation...",
        max_tokens=4000,
        temperature=0.3
    )
    
    # Specialized conversation analysis
    analysis = await gemini.analyze_conversation(
        conversation_text="...",
        analysis_type="comprehensive"
    )
```

### Configuration

**Environment Variables:**
```bash
# Required
GEMINI_API_KEY=your_gemini_api_key_here

# Optional
GEMINI_MODEL=gemini-1.5-pro  # Default: gemini-1.5-pro
```

**Config File:** `config/config.py`
```python
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
```

## 📁 File Structure

```
src/
├── api/
│   ├── unified_chat_routes.py          # Chat endpoints (cleaned)
│   └── conversation_analysis_routes.py # NEW: Analysis endpoints
├── providers/
│   └── gemini_provider.py             # NEW: Gemini AI provider
└── app.py                             # Updated with new router

tests/
└── test_conversation_analysis_api.py  # NEW: Comprehensive test suite
```

## 🔄 Migration từ Old Endpoints

### Old Endpoints (Removed):
```
POST /api/unified/analyze-conversation
GET /api/unified/conversation/{conversation_id}/summary
```

### New Endpoints:
```
POST /api/conversation/analyze
GET /api/conversation/{conversation_id}/summary
GET /api/conversation/list
```

### Breaking Changes:
1. **URL Path**: `/api/unified/` → `/api/conversation/`
2. **AI Provider**: DeepSeek → Google Gemini
3. **Response Format**: Enhanced with more detailed analysis

### Migration Script:
```python
# Old usage
response = requests.post("/api/unified/analyze-conversation", ...)

# New usage  
response = requests.post("/api/conversation/analyze", ...)
```

## 🧪 Testing

### Run Tests:
```bash
# Install dependencies
pip install google-generativeai

# Run comprehensive test
python tests/test_conversation_analysis_api.py

# Or run with pytest
pytest tests/test_conversation_analysis_api.py -v
```

### Test Coverage:
- ✅ Health check
- ✅ Create test conversation
- ✅ Conversation summary
- ✅ Deep analysis with Gemini
- ✅ Conversation listing
- ✅ Error handling
- ✅ Performance metrics

## 📊 Performance Benefits

### API Separation:
- **Specialized Focus**: Each API optimized for its purpose
- **Independent Scaling**: Can scale analysis API separately
- **Better Monitoring**: Separate metrics and logging
- **Development Agility**: Teams can work independently

### Gemini Advantages:
- **Analysis Quality**: Better structured output for business intelligence
- **Response Time**: Optimized for analysis tasks (~2-4s)
- **Cost Efficiency**: Competitive pricing for analysis workloads
- **Reliability**: Consistent JSON format output

## 🚀 Future Enhancements

### Phase 1 (Current):
- ✅ Basic conversation analysis
- ✅ Remarketing insights
- ✅ Business intelligence metrics

### Phase 2 (Planned):
- 🔄 Real-time sentiment tracking
- 🔄 Customer journey mapping
- 🔄 Advanced remarketing automation
- 🔄 Multi-language analysis
- 🔄 Integration with CRM systems

### Phase 3 (Future):
- 🔄 Predictive analytics
- 🔄 Custom analysis models
- 🔄 A/B testing for conversation strategies
- 🔄 Voice conversation analysis

## 📚 Usage Examples

### Basic Analysis:
```python
import requests

response = requests.post(
    "http://localhost:8000/api/conversation/analyze",
    headers={"X-Company-Id": "company_001"},
    json={"session_id": "session_123"}
)

analysis = response.json()
intent = analysis["analysis"]["primary_intent"]
opportunities = analysis["analysis"]["remarketing_opportunities"]
```

### Batch Analysis:
```python
conversations = requests.get(
    "http://localhost:8000/api/conversation/list",
    headers={"X-Company-Id": "company_001"},
    params={"limit": 100}
).json()

for conv in conversations["conversations"]:
    if conv["status"] == "ACTIVE":
        analysis = requests.post(
            "http://localhost:8000/api/conversation/analyze",
            json={"session_id": conv["session_id"]}
        ).json()
        # Process analysis...
```

## 🎯 Business Value

### Remarketing ROI:
- **Immediate Actions**: 24H follow-up recommendations
- **Personalized Campaigns**: Based on conversation insights  
- **Conversion Tracking**: Measure effectiveness
- **Customer Lifecycle**: Understand journey stages

### Operational Insights:
- **AI Performance**: Identify improvement areas
- **Product Gaps**: Unresolved customer issues
- **Training Needs**: Common conversation patterns
- **Business Intelligence**: Data-driven decisions

---

**📞 Support:** Liên hệ team development nếu cần hỗ trợ integration hoặc customization.

**🔄 Updates:** API documentation sẽ được cập nhật thường xuyên theo phát triển tính năng.
