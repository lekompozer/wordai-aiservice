"""
AI configuration for document generation service
"""

from src.services.ai_service import get_ai_service


# Simple AI client wrapper for document generation
class DocumentAIClient:
    def __init__(self):
        self.ai_service = get_ai_service()

    """
AI configuration for document generation service
"""


import os
from src.services.ai_service import get_ai_service

# Try to import existing AI providers
try:
    from src.services.ai_chat_service import AIChatService, AIProvider

    HAS_AI_PROVIDERS = True
except ImportError:
    HAS_AI_PROVIDERS = False


# Simple AI client wrapper for document generation
class DocumentAIClient:
    def __init__(self):
        self.ai_service = get_ai_service()
        self.chat_service = None

        # Initialize AI chat service if available
        if HAS_AI_PROVIDERS:
            try:
                self.chat_service = AIChatService()
            except Exception as e:
                print(f"Warning: Could not initialize AI chat service: {e}")

    async def generate_text(
        self, prompt: str, max_tokens: int = 2000, temperature: float = 0.3
    ) -> dict:
        """Generate text content using AI service"""
        try:
            # Try to use existing AI providers first
            if self.chat_service and HAS_AI_PROVIDERS:
                # Use Gemini for document generation (good for structured content)
                try:
                    provider = AIProvider.GEMINI_FLASH
                    response = await self.chat_service.generate_response(
                        prompt=prompt,
                        provider=provider,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    )

                    return {
                        "content": response.get("content", ""),
                        "tokens_used": response.get("usage", {}).get("total_tokens", 0),
                        "model": "gemini-flash",
                        "provider": "gemini",
                    }
                except Exception as e:
                    print(f"AI generation error with Gemini: {e}")

            # Fallback to template-based generation
            return await self._generate_fallback_content(prompt, max_tokens)

        except Exception as e:
            return {"content": f"Error generating content: {str(e)}", "error": True}

    async def _generate_fallback_content(self, prompt: str, max_tokens: int) -> dict:
        """Generate fallback content using templates"""

        # Extract document type from prompt
        doc_type = "document"
        if "báo giá" in prompt.lower() or "quote" in prompt.lower():
            doc_type = "quote"
        elif "hợp đồng" in prompt.lower() or "contract" in prompt.lower():
            doc_type = "contract"
        elif "phụ lục" in prompt.lower() or "appendix" in prompt.lower():
            doc_type = "appendix"

        # Generate structured content based on type
        if doc_type == "quote":
            content = self._generate_quote_content()
        elif doc_type == "contract":
            content = self._generate_contract_content()
        elif doc_type == "appendix":
            content = self._generate_appendix_content()
        else:
            content = self._generate_generic_content()

        return {
            "content": content,
            "tokens_used": len(content.split()),
            "model": "template-fallback",
            "provider": "internal",
        }

    def _generate_quote_content(self) -> str:
        """Generate professional quote content"""
        return """
        <div style="margin: 20px 0;">
            <p>Kính gửi Quý khách hàng,</p>
            <p>Căn cứ vào yêu cầu của Quý khách hàng, chúng tôi xin gửi đến Quý khách hàng bảng báo giá chi tiết như sau:</p>

            <h4>ĐIỀU KIỆN BÁO GIÁ:</h4>
            <ul>
                <li>Giá đã bao gồm VAT 10%</li>
                <li>Thời gian giao hàng: Theo thỏa thuận</li>
                <li>Điều kiện thanh toán: Theo hợp đồng</li>
                <li>Bảo hành sản phẩm: Theo quy định của nhà sản xuất</li>
            </ul>

            <p>Chúng tôi cam kết cung cấp sản phẩm chính hãng, chất lượng cao với giá cả cạnh tranh nhất.</p>
            <p>Mọi thắc mắc xin vui lòng liên hệ với chúng tôi để được tư vấn chi tiết.</p>

            <p>Trân trọng cảm ơn!</p>
        </div>
        """

    def _generate_contract_content(self) -> str:
        """Generate professional contract content"""
        return """
        <div style="margin: 20px 0;">
            <p>Căn cứ Bộ luật Dân sự số 91/2015/QH13 ngày 24/11/2015;</p>
            <p>Căn cứ Luật Thương mại số 36/2005/QH11 ngày 14/06/2005;</p>
            <p>Căn cứ nhu cầu và khả năng của các bên;</p>

            <p><strong>Hai bên cùng thỏa thuận ký kết hợp đồng với các điều khoản sau:</strong></p>

            <h4>ĐIỀU 1: TRÁCH NHIỆM CỦA BÊN A</h4>
            <ul>
                <li>Cung cấp đầy đủ, đúng chất lượng, số lượng hàng hóa/dịch vụ theo đúng thỏa thuận</li>
                <li>Giao hàng đúng thời hạn, địa điểm đã thỏa thuận</li>
                <li>Bảo hành sản phẩm theo quy định</li>
                <li>Hướng dẫn sử dụng và hỗ trợ kỹ thuật khi cần thiết</li>
            </ul>

            <h4>ĐIỀU 2: TRÁCH NHIỆM CỦA BÊN B</h4>
            <ul>
                <li>Thanh toán đầy đủ, đúng hạn theo thỏa thuận</li>
                <li>Tiếp nhận hàng hóa đúng thời hạn</li>
                <li>Kiểm tra và thông báo cho Bên A về chất lượng hàng hóa</li>
                <li>Cung cấp đầy đủ thông tin cần thiết cho việc thực hiện hợp đồng</li>
            </ul>

            <p>Hợp đồng này có hiệu lực kể từ ngày ký và thực hiện theo đúng cam kết của các bên.</p>
        </div>
        """

    def _generate_appendix_content(self) -> str:
        """Generate professional appendix content"""
        return """
        <div style="margin: 20px 0;">
            <p>Căn cứ vào hợp đồng gốc đã ký kết;</p>
            <p>Căn cứ vào nhu cầu thực tế phát sinh;</p>
            <p>Sau khi thỏa thuận, hai bên đồng ý bổ sung/thay đổi các nội dung sau:</p>

            <h4>NỘI DUNG BỔ SUNG/THAY ĐỔI:</h4>
            <p>Các thay đổi được thực hiện nhằm đáp ứng tốt hơn nhu cầu thực tế và đảm bảo lợi ích cho cả hai bên.</p>

            <h4>HIỆU LỰC:</h4>
            <ul>
                <li>Phụ lục này là một phần không tách rời của hợp đồng gốc</li>
                <li>Có hiệu lực kể từ ngày ký</li>
                <li>Các điều khoản khác của hợp đồng gốc vẫn giữ nguyên hiệu lực</li>
                <li>Trong trường hợp có mâu thuẫn, phụ lục này được ưu tiên áp dụng</li>
            </ul>

            <p>Phụ lục được lập thành 02 bản có giá trị pháp lý như nhau, mỗi bên giữ 01 bản.</p>
        </div>
        """

    def _generate_generic_content(self) -> str:
        """Generate generic professional content"""
        return """
        <div style="margin: 20px 0;">
            <p>Nội dung tài liệu được tạo tự động với sự hỗ trợ của AI.</p>
            <p>Tài liệu này tuân thủ các quy định pháp luật hiện hành và được thiết kế để đáp ứng nhu cầu kinh doanh chuyên nghiệp.</p>

            <h4>LƯU Ý QUAN TRỌNG:</h4>
            <ul>
                <li>Tài liệu này được tạo tự động và cần được xem xét kỹ lưỡng trước khi sử dụng</li>
                <li>Nên tham khảo ý kiến chuyên gia pháp lý khi cần thiết</li>
                <li>Đảm bảo tuân thủ các quy định pháp luật liên quan</li>
            </ul>
        </div>
        """


def get_ai_client():
    """Get AI client instance for document generation"""
    return DocumentAIClient()


def get_ai_client():
    """Get AI client instance for document generation"""
    return DocumentAIClient()
