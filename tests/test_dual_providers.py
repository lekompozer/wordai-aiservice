import requests
import json
import base64

BASE_URL = "http://localhost:8000"

def test_providers_availability():
    """Test xem providers nào có sẵn"""
    response = requests.get(f"{BASE_URL}/ai-providers")
    print("Available providers:")
    print(json.dumps(response.json(), indent=2))

def test_deepseek_with_ocr():
    """Test DeepSeek với OCR từ backend"""
    content = "Lãi suất tiết kiệm 12 tháng: 4.8%"
    
    request_data = {
        "question": "Lãi suất 12 tháng là bao nhiêu?",
        "userId": "test_deepseek",
        "ai_provider": "deepseek",
        "use_backend_ocr": True,
        "files": [
            {
                "filename": "laisuat.txt",
                "content_type": "text/plain",
                "extracted_text": content  # Đã OCR từ backend
            }
        ]
    }
    
    print("\n=== Testing DeepSeek ===")
    response = requests.post(f"{BASE_URL}/chat-with-files-stream", json=request_data, stream=True)
    
    for line in response.iter_lines():
        if line:
            line = line.decode('utf-8')
            if line.startswith('data: '):
                try:
                    data = json.loads(line[6:])
                    if "chunk" in data:
                        print(data["chunk"], end="", flush=True)
                    elif "done" in data:
                        print(f"\nProvider used: {data.get('provider', 'unknown')}")
                        break
                except:
                    continue

def test_chatgpt_multimodal():
    """Test ChatGPT với multimodal"""
    # Tạo image đơn giản (text thành base64)
    text_content = "Sổ đỏ - Diện tích: 100m2, Địa chỉ: Quận 1 TP.HCM"
    image_base64 = base64.b64encode(text_content.encode()).decode()
    
    request_data = {
        "question": "Phân tích thông tin trong hình ảnh này",
        "userId": "test_chatgpt",
        "ai_provider": "chatgpt",
        "use_backend_ocr": False,
        "files": [
            {
                "filename": "so_do.jpg",
                "content_type": "image/jpeg",
                "content": image_base64  # Raw image data
            }
        ]
    }
    
    print("\n=== Testing ChatGPT ===")
    response = requests.post(f"{BASE_URL}/chat-with-files-stream", json=request_data, stream=True)
    
    for line in response.iter_lines():
        if line:
            line = line.decode('utf-8')
            if line.startswith('data: '):
                try:
                    data = json.loads(line[6:])
                    if "chunk" in data:
                        print(data["chunk"], end="", flush=True)
                    elif "done" in data:
                        print(f"\nProvider used: {data.get('provider', 'unknown')}")
                        break
                except:
                    continue

if __name__ == "__main__":
    test_providers_availability()
    test_deepseek_with_ocr()
    test_chatgpt_multimodal()