import os
import sys
from pathlib import Path

# Thêm thư mục gốc vào sys.path
sys.path.append(str(Path(__file__).parent))

from src.rag.chatbot import Chatbot

def test_streaming_flow():
    print("\n===== BẮT ĐẦU KIỂM TRA STREAMING FLOW =====")
    chatbot = Chatbot()
    
    # 1. Test tạo prompt từ câu hỏi
    question = "Tôi muốn vay tín chấp 400 triệu tại ngân hàng VP Bank, lương tôi đang 50 triệu 1 tháng có được không? Vay trong vòng 48 tháng thì hàng tháng trả bao nhiêu?"
    
    # Lưu phương thức gốc để monkey patch
    original_call_api = chatbot._call_deepseek_api_streaming
    
    # Biến để theo dõi các bước
    prompt_received = None
    api_called = False
    
    # 2. Monkey patch để bắt prompt được gửi đến API
    def mock_call_api(prompt):
        nonlocal prompt_received, api_called
        print("\n===== KIỂM TRA PROMPT ĐƯỢC GỬI ĐẾN API =====")
        prompt_received = prompt
        api_called = True
        print(f"Độ dài prompt: {len(prompt)} ký tự")
        print(f"Preview prompt: {prompt[:300]}...\n...{prompt[-300:]}")
        
        print("\n===== GIẢ LẬP RESPONSE TỪ DEEPSEEK API =====")
        # Giả lập response từ deepseek API
        yield "Dựa trên thông tin từ VP Bank, "
        yield "với mức lương 50 triệu đồng/tháng, bạn hoàn toàn có thể vay tín chấp 400 triệu đồng. "
        yield "Thông thường, VP Bank yêu cầu thu nhập tối thiểu từ 8-10 triệu/tháng để xét duyệt khoản vay. "
        yield "Với khoản vay 400 triệu trong 48 tháng, ước tính mỗi tháng bạn sẽ phải trả khoảng 11-12 triệu đồng "
        yield "(tùy thuộc vào lãi suất chính xác tại thời điểm vay). "
        yield "Bạn có nhu cầu vay với mục đích gì để tôi tư vấn thêm không?"
        
    # Thay thế phương thức gốc
    chatbot._call_deepseek_api_streaming = mock_call_api
    
    try:
        print("\n===== BẮT ĐẦU GỌI generate_response_streaming =====")
        # 3. Gọi phương thức cần test
        streaming_generator = chatbot.generate_response_streaming(question)
        
        print("\n===== KẾT QUẢ TỪ STREAMING =====")
        # 4. Thu thập response
        full_response = ""
        for i, chunk in enumerate(streaming_generator):
            print(f"Chunk #{i+1}: {chunk}")
            full_response += chunk
            
        # 5. Kiểm tra kết quả
        print("\n===== KẾT QUẢ KIỂM TRA =====")
        print(f"1. Đã gửi prompt đến API: {api_called}")
        print(f"2. Prompt có nội dung hợp lệ: {prompt_received is not None and 'VP Bank' in prompt_received}")
        print(f"3. Đã nhận được response: {len(full_response) > 0}")
        print(f"4. Response đầy đủ: {full_response}")
        
    finally:
        # Khôi phục lại phương thức gốc
        chatbot._call_deepseek_api_streaming = original_call_api
        
    print("\n===== KẾT THÚC KIỂM TRA =====")

if __name__ == "__main__":
    test_streaming_flow()