import requests
import json
import time

BASE_URL = "http://localhost:8000"
USER_ID = "test_user_" + str(int(time.time()))  # tạo ID ngẫu nhiên theo thời gian

def test_chat_with_history():
    """Test tương tác qua /chat endpoint với history"""
    
    # Câu hỏi đầu tiên (không có history trước đó)
    print("\n=== Câu hỏi 1 (không có history) ===")
    response = requests.post(
        f"{BASE_URL}/chat",
        json={"question": "Lãi suất tiết kiệm tại Vietcombank là bao nhiêu?", "userId": USER_ID}
    )
    print(f"Response: {response.json()}")
    
    # Câu hỏi thứ hai (nên có history từ câu trước)
    print("\n=== Câu hỏi 2 (có history từ câu 1) ===")
    response = requests.post(
        f"{BASE_URL}/chat",
        json={"question": "Còn tại BIDV thì sao?", "userId": USER_ID}
    )
    print(f"Response: {response.json()}")
    
    # Câu hỏi thứ ba (tiếp tục với history)
    print("\n=== Câu hỏi 3 (có history từ câu 1 & 2) ===")
    response = requests.post(
        f"{BASE_URL}/chat",
        json={"question": "Đâu là ngân hàng có lãi suất cao hơn?", "userId": USER_ID}
    )
    print(f"Response: {response.json()}")

def test_streaming_with_history():
    """Test tương tác qua /chat-stream endpoint với history"""
    
    print("\n=== Test Streaming với History ===")
    # Tạo câu hỏi đầu tiên
    response = requests.post(
        f"{BASE_URL}/chat-stream",
        json={"question": "Thời gian đáo hạn tiết kiệm tại Techcombank?", "userId": USER_ID},
        stream=True
    )
    
    print("Streaming response:")
    full_response = ""
    for line in response.iter_lines():
        if line:
            line = line.decode('utf-8')
            if line.startswith('data: '):
                data = json.loads(line[6:])
                if "chunk" in data:
                    print(data["chunk"], end="", flush=True)
                    full_response += data["chunk"]
                elif "done" in data:
                    break
                elif "error" in data:
                    print(f"\nError: {data['error']}")
    print("\n\nFull response:", full_response)
    
    # Câu hỏi tiếp theo sử dụng history
    print("\n=== Streaming câu hỏi tiếp theo ===")
    response = requests.post(
        f"{BASE_URL}/chat-stream",
        json={"question": "So với ACB thì đâu tốt hơn?", "userId": USER_ID},
        stream=True
    )
    
    print("Streaming response:")
    for line in response.iter_lines():
        if line:
            line = line.decode('utf-8')
            if line.startswith('data: '):
                data = json.loads(line[6:])
                if "chunk" in data:
                    print(data["chunk"], end="", flush=True)
                elif "done" in data:
                    break
                elif "error" in data:
                    print(f"\nError: {data['error']}")
    print("\n")

def clear_history():
    """Xóa lịch sử hội thoại"""
    
    print("\n=== Xóa history ===")
    response = requests.post(
        f"{BASE_URL}/clear-history",
        json={"userId": USER_ID}
    )
    print(f"Response: {response.json()}")

if __name__ == "__main__":
    # Kiểm tra server còn hoạt động không
    try:
        ping = requests.get(f"{BASE_URL}/ping")
        if ping.status_code != 200:
            print("Server không phản hồi. Hãy chạy 'python serve.py' trước.")
            exit(1)
    except requests.exceptions.ConnectionError:
        print("Không thể kết nối đến server. Hãy chạy 'python serve.py' trước.")
        exit(1)
        
    print(f"Testing với USER_ID: {USER_ID}")
    
    # Chạy test
    test_chat_with_history()
    time.sleep(2)  # đợi một chút giữa các test
    
    test_streaming_with_history()
    time.sleep(2)
    
    # Xóa history sau khi test xong
    clear_history()