import requests
from tenacity import retry, stop_after_attempt, wait_fixed
from config.config import DEEPSEEK_API_KEY
from src.utils.tone_adjuster import ToneAdjuster
from typing import Optional
from src.utils.logger import setup_logger
import json

logger = setup_logger()

class FallbackHandler:
    def __init__(self):
        self.api_url = "https://api.deepseek.com/v1/chat/completions"
        self.tone_adjuster = ToneAdjuster()
        self.default_response = "Xin lỗi, hiện hệ thống đang quá tải. Vui lòng thử lại sau ít phút."
        self.timeout = 20  # Tăng timeout lên 20 giây

    def get_fallback_response(self, query: str, tone: str = "neutral", context: Optional[str] = None) -> str:
        try:
            prompt = self._build_prompt(query, context)
            response = self._call_deepseek_api_with_retry(prompt)
            return self.tone_adjuster.adjust_response(response or self._get_context_response(context), tone)
        except Exception as e:
            logger.error(f"Fallback error: {str(e)}")
            return self.tone_adjuster.adjust_response(self._get_context_response(context), tone)

    def _build_prompt(self, query: str, context: Optional[str]) -> str:
        """Xây dựng prompt tối ưu"""
        if not context:
            return f"Hãy phân tích ngắn gọn về: {query}"
            
        return (
            f"Dựa trên thông tin sau:\n{context[:2000]}\n\n"
            f"Hãy trả lời ngắn gọn câu hỏi: {query}\n"
            "Chỉ sử dụng thông tin được cung cấp."
        )

    # @retry(
    #     stop=stop_after_attempt(3),
    #     wait=wait_exponential(multiplier=1, min=4, max=10),
    #     reraise=True
    # )
    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    def encode_with_retry(self, contents, batch_size=2):
        print(f"Attempting to encode {len(contents)} documents...")
        return self.model.encode(contents, batch_size=batch_size, show_progress_bar=False)
    def _call_deepseek_api_with_retry(self, prompt: str) -> Optional[str]:
        """Gọi API với cơ chế retry"""
        try:
            return self._call_deepseek_api(prompt)
        except requests.exceptions.Timeout:
            logger.warning("Timeout khi gọi Deepseek API")
            raise
        except Exception as e:
            logger.error(f"API error: {str(e)}")
            return None

    def _call_deepseek_api(self, prompt: str) -> Optional[str]:
        """Gọi Deepseek API với timeout và xử lý lỗi chi tiết"""
        try:
            headers = {
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
                "Accept-Encoding": "gzip"
            }
            payload = {
                "model": "deepseek-chat",
                "messages": [{
                    "role": "user",
                    "content": prompt[:3000]  # Giới hạn độ dài prompt
                }],
                "temperature": 0.2,
                "max_tokens": 1000  # Giảm max_tokens để tăng tốc độ
            }
            
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            return None
        except json.JSONDecodeError:
            logger.error("Invalid JSON response")
            return None

    def _get_context_response(self, context: Optional[str]) -> str:
        """Tạo response từ context nếu có"""
        if context:
            return f"Dựa trên thông tin hiện có:\n{context[:1000]}...\n\n(Vui lòng yêu cầu cụ thể hơn nếu cần thêm chi tiết)"
        return self.default_response