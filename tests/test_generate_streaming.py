import os
import sys
from pathlib import Path

# Thêm thư mục gốc vào sys.path
sys.path.append(str(Path(__file__).parent))

from src.rag.chatbot import Chatbot
from src.rag.vector_store import Document

def test_generate_response_streaming():
    print("\n===== TEST TẠO PROMPT TRONG generate_response_streaming =====")
    
    # Tạo instance chatbot
    chatbot = Chatbot()
    
    # 1. Kiểm tra vector store trống
    print(f"1. Số documents trong vector store ban đầu: {len(chatbot.vector_store.documents)}")
    
    # 2. Thêm dữ liệu mẫu vào vector store để test
    print("2. Thêm dữ liệu mẫu vào vector store...")
    sample_docs = [
        Document(
            content="Thông tin về vay tín chấp VPBank: Lãi suất 13-18%/năm, thời hạn tối đa 60 tháng. Điều kiện: thu nhập tối thiểu 8 triệu/tháng, công việc ổn định 6 tháng trở lên. Với lương 50 triệu/tháng, khách hàng có thể vay tới 500-600 triệu đồng.",
            metadata={
                "source": "vpbank_loan_info.txt",
                "page": "1",
                "chunk_index": "0"
            }
        ),
        Document(
            content="Khoản vay 400 triệu trong 48 tháng tại VPBank có mức trả góp khoảng 11.2-11.8 triệu/tháng tùy vào lãi suất chính xác được duyệt. Khách hàng cần chuẩn bị CMND/CCCD, sao kê lương 3 tháng gần nhất, và hợp đồng lao động.",
            metadata={
                "source": "vpbank_loan_calculation.txt",
                "page": "1",
                "chunk_index": "0"
            }
        )
    ]
    
    # Thêm vào vector store bằng cách an toàn
    try:
        # Phương thức 1: Nếu có add_documents(), sử dụng nó
        if hasattr(chatbot.vector_store, 'add_documents') and callable(chatbot.vector_store.add_documents):
            print("   Sử dụng add_documents()...")
            chatbot.vector_store.add_documents(sample_docs)
        # Phương thức 2: Thêm trực tiếp vào list documents
        else:
            print("   Thêm trực tiếp vào documents list...")
            if not hasattr(chatbot.vector_store, 'documents'):
                chatbot.vector_store.documents = []
            chatbot.vector_store.documents.extend(sample_docs)
            
        # Không gọi build_index để tránh lỗi với mock
        print(f"   Đã thêm {len(sample_docs)} documents vào vector store")
        print(f"   Tổng số documents hiện tại: {len(chatbot.vector_store.documents)}")
    except Exception as e:
        print(f"   ⚠️ Lỗi khi thêm documents: {str(e)}")
        print("   ⚠️ Tiếp tục test với vector store trống")
    
    # Lưu lại phương thức gốc để monkey patch
    original_api_call = chatbot._call_deepseek_api_streaming
    
    # Biến để lưu prompt được tạo ra
    captured_prompt = None
    
    # 3. Thay thế _call_deepseek_api_streaming để bắt prompt
    def mock_api_call(prompt):
        nonlocal captured_prompt
        captured_prompt = prompt
        print(f"3. Đã bắt được prompt độ dài {len(prompt)} ký tự")
        # Trả về kết quả giả
        yield "Đây là phản hồi giả định từ API"
    
    # Gán phương thức mock
    chatbot._call_deepseek_api_streaming = mock_api_call
    
    try:
        # 4. Gọi hàm cần test
        question = "Tôi muốn vay tín chấp 400 triệu tại ngân hàng VP Bank, lương tôi đang 50 triệu 1 tháng có được không? Vay trong vòng 48 tháng thì hàng tháng trả bao nhiêu?"
        print(f"4. Gọi generate_response_streaming với câu hỏi: '{question[:50]}...'")
        
        generator = chatbot.generate_response_streaming(question)
        
        # Lấy kết quả từ generator
        response = []
        for chunk in generator:
            response.append(chunk)
        
        # 5. Kiểm tra kết quả
        print("\n===== KẾT QUẢ =====")
        print(f"5.1. Đã tạo prompt thành công: {captured_prompt is not None}")
        
        if captured_prompt:
            print(f"5.2. Độ dài prompt: {len(captured_prompt)} ký tự")
            print(f"5.3. Prompt có chứa VP Bank: {'VP Bank' in captured_prompt}")
            print(f"5.4. Prompt có chứa '400 triệu': {'400 triệu' in captured_prompt}")
            print(f"5.5. Prompt có format RAG đúng: {'DỮ LIỆU:' in captured_prompt and 'CÂU HỎI:' in captured_prompt}")
            
            print("\n5.6. Phần đầu prompt:")
            print("-------------------")
            print(captured_prompt[:300] + "...")
            print("-------------------")
            
            print("\n5.7. Phần cuối prompt:")
            print("-------------------")
            print("..." + captured_prompt[-300:])
            print("-------------------")
        
        print(f"\n5.8. Response từ API giả: {''.join(response)}")
        
    finally:
        # Khôi phục phương thức gốc
        chatbot._call_deepseek_api_streaming = original_api_call
    
    print("\n===== KẾT THÚC TEST =====")

if __name__ == "__main__":
    test_generate_response_streaming()