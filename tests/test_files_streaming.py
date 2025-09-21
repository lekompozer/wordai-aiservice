import requests
import json
import base64
import time

BASE_URL = "http://localhost:8000"  # Hoặc localhost nếu test local
USER_ID = "test_user_files_" + str(int(time.time()))

def create_test_files():
    """Tạo test files với nội dung khác nhau"""
    
    # File 1: Thông tin lãi suất
    laisuat_content = """
    BẢNG LÃI SUẤT TIẾT KIỆM VIETCOMBANK 2025
    
    Kỳ hạn 6 tháng: 4.2%/năm
    Kỳ hạn 12 tháng: 4.8%/năm  
    Kỳ hạn 18 tháng: 5.0%/năm
    Kỳ hạn 24 tháng: 5.1%/năm
    
    Ưu đãi:
    - Khách hàng VIP: +0.2%/năm
    - Gửi từ 500 triệu: +0.1%/năm
    """
    
    # File 2: So sánh ngân hàng
    sosanh_content = """
    SO SÁNH LÃI SUẤT CÁC NGÂN HÀNG 2025
    
    VIETCOMBANK:
    - 12 tháng: 4.8%/năm
    - 24 tháng: 5.1%/năm
    
    ACB:
    - 12 tháng: 5.0%/năm
    - 24 tháng: 5.3%/năm
    
    TECHCOMBANK:
    - 12 tháng: 4.9%/năm
    - 24 tháng: 5.2%/năm
    
    KẾT LUẬN: ACB có lãi suất cao nhất
    """
    
    # File 3: Điều kiện và phí
    phidichvu_content = """
    PHÍ DỊCH VỤ NGÂN HÀNG 2025
    
    VIETCOMBANK:
    - Phí mở tài khoản: 100,000 VND
    - Phí duy trì tài khoản: 20,000 VND/tháng
    - Phí chuyển khoản online: 5,500 VND
    - Phí rút tiền ATM: 3,300 VND/giao dịch
    
    ĐIỀU KIỆN:
    - Số dư tối thiểu: 500,000 VND
    - Gửi tiết kiệm tối thiểu: 1,000,000 VND
    """
    
    return [
        {
            "content": base64.b64encode(laisuat_content.encode('utf-8')).decode('utf-8'),
            "content_type": "text/plain",
            "filename": "laisuat_vietcombank.txt",
            "size": len(laisuat_content)
        },
        {
            "content": base64.b64encode(sosanh_content.encode('utf-8')).decode('utf-8'),
            "content_type": "text/plain", 
            "filename": "sosanh_ngan_hang.txt",
            "size": len(sosanh_content)
        },
        {
            "content": base64.b64encode(phidichvu_content.encode('utf-8')).decode('utf-8'),
            "content_type": "text/plain",
            "filename": "phi_dich_vu.txt", 
            "size": len(phidichvu_content)
        }
    ]

def test_streaming_question(question, files_data, question_number):
    """Test một câu hỏi streaming với files"""
    
    print(f"\n{'='*60}")
    print(f"CÂU HỎI {question_number}: {question}")
    print(f"{'='*60}")
    print(f"Files gửi kèm: {[f['filename'] for f in files_data]}")
    print(f"User ID: {USER_ID}")
    print("\n" + "-"*50)
    print("PHẢN HỒI STREAMING:")
    print("-"*50)
    
    # Chuẩn bị request data
    request_data = {
        "question": question,
        "userId": USER_ID,
        "files": files_data
    }
    
    # Gọi endpoint streaming
    try:
        response = requests.post(
            f"{BASE_URL}/chat-with-files-stream",
            json=request_data,
            stream=True,
            timeout=120
        )
        
        if response.status_code != 200:
            print(f"Error: HTTP {response.status_code}")
            print(response.text)
            return
        
        full_response = ""
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    try:
                        data = json.loads(line[6:])
                        if "chunk" in data:
                            chunk = data["chunk"]
                            print(chunk, end="", flush=True)
                            full_response += chunk
                        elif "done" in data:
                            print(f"\n\n{'-'*50}")
                            print("✅ HOÀN THÀNH")
                            print(f"Độ dài phản hồi: {len(full_response)} ký tự")
                            print(f"{'-'*50}")
                            break
                        elif "error" in data:
                            print(f"\n❌ LỖI: {data['error']}")
                            break
                    except json.JSONDecodeError as e:
                        print(f"\n⚠️ JSON decode error: {e}")
                        continue
                        
    except requests.exceptions.Timeout:
        print("\n❌ TIMEOUT: Server không phản hồi trong 120 giây")
    except requests.exceptions.ConnectionError:
        print(f"\n❌ CONNECTION ERROR: Không thể kết nối tới {BASE_URL}")
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")

def test_chat_history_endpoint():
    """Test endpoint lấy lịch sử chat"""
    
    print(f"\n{'='*60}")
    print("KIỂM TRA LỊCH SỬ CHAT")
    print(f"{'='*60}")
    
    try:
        response = requests.get(f"{BASE_URL}/history/{USER_ID}")
        
        if response.status_code == 200:
            history = response.json()
            print(f"✅ Có {len(history.get('messages', []))} tin nhắn trong lịch sử")
            
            for i, msg in enumerate(history.get('messages', [])[-6:], 1):  # Hiển thị 6 tin nhắn cuối
                role = "🧑 USER" if msg['role'] == 'user' else "🤖 BOT"
                content = msg['content'][:100] + "..." if len(msg['content']) > 100 else msg['content']
                print(f"{i}. {role}: {content}")
        else:
            print(f"❌ Lỗi lấy lịch sử: HTTP {response.status_code}")
            
    except Exception as e:
        print(f"❌ Lỗi khi kiểm tra lịch sử: {e}")

def main():
    """Chạy test chính với 3 câu hỏi có liên quan để test lịch sử"""
    
    print("🚀 BẮT ĐẦU TEST FILES STREAMING VỚI LỊCH SỬ CHAT")
    print(f"Base URL: {BASE_URL}")
    print(f"User ID: {USER_ID}")
    
    # Tạo test files
    test_files = create_test_files()
    
    # Câu hỏi 1: Hỏi về lãi suất cơ bản
    test_streaming_question(
        question="Lãi suất tiết kiệm 12 tháng tại Vietcombank là bao nhiêu?",
        files_data=[test_files[0]],  # Chỉ gửi file lãi suất
        question_number=1
    )
    
    time.sleep(2)  # Nghỉ 2 giây để đảm bảo lưu database
    
    # Câu hỏi 2: So sánh với ngân hàng khác (có context từ câu 1)
    test_streaming_question(
        question="So với ACB và Techcombank thì ngân hàng nào tốt hơn?",
        files_data=[test_files[1]],  # Gửi file so sánh
        question_number=2
    )
    
    time.sleep(2)
    
    # Câu hỏi 3: Hỏi về phí dịch vụ (có context từ câu 1 và 2)
    test_streaming_question(
        question="Ngoài lãi suất thì còn có phí gì khác không? Tính tổng chi phí cho tôi.",
        files_data=[test_files[2]],  # Gửi file phí dịch vụ
        question_number=3
    )
    
    time.sleep(2)
    
    # Test câu hỏi 4: Không có file, chỉ dựa vào lịch sử
    test_streaming_question(
        question="Dựa trên những thông tin vừa rồi, bạn khuyên tôi nên chọn ngân hàng nào và kỳ hạn bao lâu?",
        files_data=[],  # Không gửi file, chỉ dựa vào lịch sử
        question_number=4
    )
    
    # Kiểm tra lịch sử cuối cùng
    test_chat_history_endpoint()
    
    print(f"\n🎉 HOÀN THÀNH TẤT CẢ TEST")
    print(f"📊 Đã test {4} câu hỏi với User ID: {USER_ID}")

if __name__ == "__main__":
    main()