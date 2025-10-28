# So sánh nhanh: Anthropic Direct vs OpenRouter

## 🎯 TL;DR (Too Long; Didn't Read)

| Tiêu chí | Anthropic Direct | OpenRouter | Winner |
|----------|-----------------|------------|--------|
| **Chi phí RAG/Document** | $6,007/tháng | $26,037/tháng | ✅ Anthropic (-77%) |
| **Chi phí chat thường** | $18/1M tokens | $19.80-21.60/1M | ✅ Anthropic |
| **Prompt Caching** | ✅ Có (90% rẻ hơn) | ❌ Không | ✅ Anthropic |
| **Latency** | Thấp (~500ms) | Cao (~700-1000ms) | ✅ Anthropic |
| **Vision API** | ✅ Full support | ⚠️ Limited | ✅ Anthropic |
| **Rate Limit** | 4000 RPM | 200-1000 RPM | ✅ Anthropic |
| **Setup phức tạp** | Vừa (thêm 1 key) | Dễ (1 key tất cả) | ✅ OpenRouter |
| **Multi-model** | ❌ Không | ✅ Có | ✅ OpenRouter |
| **Billing tập trung** | ❌ Riêng lẻ | ✅ Tập trung | ✅ OpenRouter |

**🏆 Khuyến nghị: ANTHROPIC DIRECT**
- Phù hợp: Production, RAG/Document processing, High traffic
- Lý do: Tiết kiệm 77% chi phí, hiệu suất cao, tính năng đầy đủ

---

## 💰 Chi phí thực tế

### Scenario 1: Chat đơn giản (10M tokens/tháng)
```
Anthropic Direct: $180
OpenRouter:       $198-216
Chênh lệch:       -$18-36 (10%)
→ Không đáng kể
```

### Scenario 2: Document RAG (100 users, 5 docs/user/ngày)
```
Anthropic Direct: $6,007/tháng  (với caching)
OpenRouter:       $26,037/tháng (không cache)
Chênh lệch:       -$20,030 (77%)
→ CHÊNH LỆCH LỚN! 🔥
```

### Scenario 3: Heavy PDF processing (1000 docs/ngày)
```
Anthropic Direct: $2,000/tháng  (với caching)
OpenRouter:       $8,700/tháng  (không cache)
Chênh lệch:       -$6,700 (77%)
→ Tiết kiệm đáng kể!
```

---

## ⚡ Performance

### Latency (trung bình)
```
Anthropic Direct:
  - First token: 300-500ms
  - Total response: 1-3s

OpenRouter:
  - First token: 500-800ms (+300ms overhead)
  - Total response: 2-4s

→ Anthropic nhanh hơn 30-40%
```

### Rate Limits
```
Anthropic Direct (Tier 1):
  - 4,000 RPM (requests/minute)
  - 400,000 TPM (tokens/minute)
  - Có thể upgrade lên Tier 4: 80,000 RPM

OpenRouter (Free):
  - 200 RPM
  - 10 req/10s

OpenRouter (Paid):
  - 1,000 RPM
  - Still lower than Direct

→ Anthropic cao gấp 4-20 lần
```

---

## 🔥 Prompt Caching - Game Changer

### Cách hoạt động:
```python
# Anthropic Direct - Cache context dài
response = await client.messages.create(
    model="claude-sonnet-4-20241022",
    max_tokens=1024,
    system=[
        {
            "type": "text",
            "text": f"Document content: {pdf_text_50k_tokens}",
            "cache_control": {"type": "ephemeral"}  # ← Cache this!
        }
    ],
    messages=[{"role": "user", "content": "Summarize page 5"}]
)
```

### Tiết kiệm:
```
Context: 50K tokens

Lần 1 (cache write):
  - Cost: 50K × $3.75/1M = $0.1875

Lần 2-10 (cache read):
  - Cost: 50K × $0.30/1M = $0.015
  - Tiết kiệm: $0.1725 (92%)

Total 10 requests:
  - Với cache: $0.1875 + (9 × $0.015) = $0.3225
  - Không cache: 10 × $0.15 = $1.50
  - Tiết kiệm: $1.1775 (78%)
```

**OpenRouter: KHÔNG hỗ trợ caching → Mất hết tiết kiệm này!**

---

## 📊 Use Case Matrix

| Use Case | Recommended | Lý do |
|----------|-------------|-------|
| **Chat với PDF/Documents** | ✅ Anthropic Direct | Prompt caching tiết kiệm 77% |
| **RAG system** | ✅ Anthropic Direct | Context dài, nhiều requests |
| **Production API** | ✅ Anthropic Direct | Rate limit cao, latency thấp |
| **Prototype/Testing** | ✅ OpenRouter | Dễ setup, test nhiều model |
| **Multi-model app** | ✅ OpenRouter | GPT-4 + Claude + Llama |
| **Budget < $500/tháng** | ⚖️ Either | Chênh lệch không lớn |
| **Traffic > 1M tokens/ngày** | ✅ Anthropic Direct | Chi phí chênh lệch lớn |

---

## 🛠️ Setup Difficulty

### Anthropic Direct
```bash
# 1. Install (30 seconds)
pip install anthropic

# 2. Get API key (2 minutes)
# https://console.anthropic.com/

# 3. Code (10 minutes)
from anthropic import Anthropic
client = Anthropic(api_key="sk-ant-xxx")
response = client.messages.create(...)

# Total: 15 minutes
```

### OpenRouter
```bash
# 1. Get API key (2 minutes)
# https://openrouter.ai/

# 2. Code (5 minutes) - OpenAI compatible
import openai
client = openai.OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key="sk-or-xxx"
)
response = client.chat.completions.create(...)

# Total: 7 minutes
```

**→ OpenRouter dễ hơn 1 chút, nhưng không đáng kể**

---

## 🎯 Decision Tree

```
Start
  │
  ├─ Traffic > 1M tokens/ngày?
  │   ├─ YES → Anthropic Direct (tiết kiệm 77%)
  │   └─ NO → Tiếp tục
  │
  ├─ Use case là RAG/Document?
  │   ├─ YES → Anthropic Direct (prompt caching)
  │   └─ NO → Tiếp tục
  │
  ├─ Cần nhiều model (GPT-4, Claude, Llama)?
  │   ├─ YES → OpenRouter (multi-model)
  │   └─ NO → Tiếp tục
  │
  ├─ Production app với SLA?
  │   ├─ YES → Anthropic Direct (rate limit, latency)
  │   └─ NO → OpenRouter (prototype)
```

---

## 💡 Pro Tips

### Khi dùng Anthropic Direct:
1. **Luôn bật prompt caching** cho context dài (>10K tokens)
2. **Cache document content**, không cache user query
3. **Monitor cache hit rate** trong dashboard
4. **Reuse cache** trong 5 phút (cache TTL)
5. **Batch requests** khi có thể để tối ưu cache

### Khi dùng OpenRouter:
1. **Set fallback models** để tránh downtime
2. **Monitor credits** thường xuyên
3. **Use free models** cho testing
4. **Set HTTP timeout** cao (thêm latency)
5. **Don't rely on latest features** (chậm update)

---

## 📈 ROI Calculation

### Investment:
```
Dev time: 8-16 giờ × $50/giờ = $400-800
API key setup: Free
Testing: 4 giờ × $50/giờ = $200
Total investment: $600-1000
```

### Return (hàng tháng):
```
Scenario Document Processing (100 users):
  OpenRouter:       $26,037/tháng
  Anthropic Direct: $6,007/tháng
  Savings:          $20,030/tháng

Annual savings: $240,360/năm
```

### Break-even:
```
$1000 investment / $20,030 monthly savings = 0.05 tháng
→ Hoàn vốn sau 1.5 NGÀY! 🚀
```

---

## 🎬 Next Actions

1. **[ ] Đọc full analysis**: `CLAUDE_SONNET_INTEGRATION_ANALYSIS.md`
2. **[ ] Đăng ký Anthropic account**: https://console.anthropic.com/
3. **[ ] Lấy API key**
4. **[ ] Test với 1-2 documents** (verify prompt caching)
5. **[ ] So sánh chi phí thực tế** vs Gemini
6. **[ ] Implement nếu OK**

---

## ❓ FAQ

**Q: OpenRouter có support prompt caching không?**
A: Không. Đây là feature độc quyền của Anthropic Direct API.

**Q: Có thể dùng cả 2 không?**
A: Có, nhưng không recommended. Phức tạp billing, monitoring.

**Q: Nếu chỉ cần test thử Claude thì sao?**
A: Dùng OpenRouter cho quick test, sau đó migrate sang Direct nếu OK.

**Q: Rate limit Anthropic có đủ không?**
A: 4000 RPM = 66 requests/giây. Với 100 users, mỗi user 1 req/3s = chỉ dùng 33 RPM. Dư thừa!

**Q: Latency 300ms thêm có đáng kể không?**
A: Với streaming, user thấy response sau 500-800ms. Chênh lệch 30% noticeable.

**Q: Gemini vs Claude, ai tốt hơn?**
A: Depends on use case:
- Gemini: Rẻ hơn, tích hợp Google, vision tốt
- Claude: Context dài hơn (200K), reasoning tốt, caching

**Q: Chi phí estimate có chính xác không?**
A: Scenario cụ thể của bạn sẽ khác. Nên test thực tế 1-2 tuần monitor usage.
