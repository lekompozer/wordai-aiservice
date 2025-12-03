# Document Chat API - Provider Guide

## Supported Providers

### 1. **DeepSeek Models** ✅

#### DeepSeek Chat (V3.2)
```json
{
  "provider": "deepseek_chat"
}
```
**Hoặc dùng shorthand:**
```json
{
  "provider": "deepseek"  // ← Tự động map sang deepseek_chat
}
```

**Đặc điểm:**
- ✅ Model: DeepSeek V3.2 (December 2024)
- ✅ Fast and efficient
- ✅ 128K context window
- ❌ **KHÔNG hỗ trợ PDF/Image trực tiếp** - cần convert text trước
- 💰 **FREE:** 10 lượt/ngày (0 điểm)
- 💰 **Paid:** Theo points service

#### DeepSeek Reasoner (R1)
```json
{
  "provider": "deepseek_reasoner"
}
```
**Hoặc:**
```json
{
  "provider": "deepseek-reasoner"  // ← Tự động map sang deepseek_reasoner
}
```

**Đặc điểm:**
- ✅ Model: DeepSeek R1
- ✅ Advanced reasoning với thinking process
- ✅ 128K context window
- ❌ **KHÔNG hỗ trợ PDF/Image trực tiếp** - cần convert text trước
- 💰 **FREE:** 10 lượt/ngày (0 điểm, dùng chung quota với deepseek_chat)
- 💰 **Paid:** Theo points service

---

### 2. **Gemini Pro** ✅

```json
{
  "provider": "gemini-pro"
}
```

**Đặc điểm:**
- ✅ 1M context window
- ✅ **Hỗ trợ PDF/Image trực tiếp** 📄📷
- 💰 Points cost: Higher than DeepSeek

---

### 3. **GPT-4** ✅

```json
{
  "provider": "gpt-4"
}
```

**Đặc điểm:**
- ✅ 1M context window
- ✅ **Hỗ trợ PDF/Image trực tiếp** 📄📷
- 💰 Points cost: Higher than DeepSeek

---

### 4. **Qwen** ✅

```json
{
  "provider": "qwen"
}
```

**Đặc điểm:**
- ✅ 32K context window
- ❌ **KHÔNG hỗ trợ PDF/Image trực tiếp**
- 💰 Points cost: Similar to DeepSeek

---

## Provider Mapping (Backend Tự Động)

Backend tự động map các variant names:

| Frontend gửi | Backend nhận |
|-------------|-------------|
| `"deepseek"` | `"deepseek_chat"` ✅ |
| `"deepseek-chat"` | `"deepseek_chat"` ✅ |
| `"deepseek_chat"` | `"deepseek_chat"` ✅ |
| `"deepseek-reasoner"` | `"deepseek_reasoner"` ✅ |
| `"deepseek_reasoner"` | `"deepseek_reasoner"` ✅ |

---

## File/Attachment Support

### ✅ Direct File Upload (PDF, Images)
**Providers:** `gemini-pro`, `gpt-4`

Có thể gửi:
- PDF files
- Images (PNG, JPG, etc.)
- Documents

Backend sẽ upload trực tiếp cho AI xử lý.

### ❌ Text-Only (No Direct File)
**Providers:** `deepseek`, `deepseek_reasoner`, `qwen`

**Luồng xử lý:**
1. Backend extract text từ file (PDF → text, Image → OCR)
2. Gửi text cho AI
3. AI chỉ nhận text, không thấy file gốc

**Hạn chế:**
- Không phân tích được layout/format của PDF
- Không thấy được hình ảnh trong document
- OCR có thể sai với chữ viết tay

---

## Request Example

### Chat với DeepSeek Chat (Legacy format - Still works)
```javascript
POST /api/ai/document-chat/stream

{
  "provider": "deepseek",  // ← Tự động map sang deepseek_chat
  "user_query": "Tóm tắt nội dung file này",
  "file_id": "abc123",
  "temperature": 0.7,
  "max_tokens": 4000
}
```

### Chat với DeepSeek Reasoner (New)
```javascript
POST /api/ai/document-chat/stream

{
  "provider": "deepseek_reasoner",  // ← Reasoning mode
  "user_query": "Phân tích logic trong tài liệu này",
  "file_id": "abc123",
  "temperature": 0.7,
  "max_tokens": 4000
}
```

### Chat với Gemini (supports direct file)
```javascript
POST /api/ai/document-chat/stream

{
  "provider": "gemini-pro",  // ← Can process PDF/images directly
  "user_query": "What's in this image?",
  "file_id": "image123.png",
  "temperature": 0.7,
  "max_tokens": 4000
}
```

---

## Free Tier Limits

**Plan: FREE**
- ✅ DeepSeek (chat + reasoner): 10 lượt/ngày (dùng chung)
- 💰 Các provider khác: Dùng bonus points (2 điểm/lượt)

**Plan: PAID**
- ✅ Không giới hạn lượt
- 💰 Trừ points theo provider

---

## Points Cost (Variable Pricing)

| Provider | Cost per chat |
|----------|---------------|
| DeepSeek (chat/reasoner) | Lowest |
| Qwen | Low-Medium |
| Gemini Pro | Medium-High |
| GPT-4 | Highest |
| Claude | High |

*Exact costs: Check `points_service.get_chat_points_cost(provider)`*

---

## Frontend Implementation Guide

### 1. Provider Selector

```tsx
<select name="provider">
  <option value="deepseek">DeepSeek V3.2 (Fast) 🆓</option>
  <option value="deepseek_reasoner">DeepSeek R1 (Reasoning) 🆓</option>
  <option value="gemini-pro">Gemini Pro (Image support) 💎</option>
  <option value="gpt-4">GPT-4 (Image support) 💎</option>
  <option value="qwen">Qwen 2.5</option>
</select>
```

### 2. File Upload Warning

```tsx
{provider === 'deepseek' || provider === 'deepseek_reasoner' || provider === 'qwen' ? (
  <Alert>
    ⚠️ {provider} chỉ xử lý text. Images/PDFs sẽ được convert sang text trước.
    Dùng Gemini/GPT-4 để phân tích trực tiếp file/hình ảnh.
  </Alert>
) : null}
```

### 3. API Call

```typescript
const response = await fetch('/api/ai/document-chat/stream', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
  },
  body: JSON.stringify({
    provider: 'deepseek_reasoner',  // ✅ Works
    // provider: 'deepseek',         // ✅ Also works (maps to deepseek_chat)
    // provider: 'deepseek-reasoner', // ✅ Also works
    user_query: 'Explain this document',
    file_id: 'file123',
    temperature: 0.7,
    max_tokens: 4000
  })
});
```

---

## Summary

✅ **YES:** Frontend có thể gửi `deepseek_reasoner` hoặc `deepseek-reasoner`

❌ **NO:** DeepSeek (cả chat và reasoner) KHÔNG hỗ trợ PDF/Image trực tiếp
- Files sẽ được convert sang text trước
- Chỉ Gemini và GPT-4 hỗ trợ direct file analysis

💡 **Recommendation:**
- Dùng DeepSeek cho: Text documents, Q&A, tóm tắt (free + fast)
- Dùng Gemini/GPT-4 cho: PDF phức tạp, phân tích hình ảnh, layout analysis
