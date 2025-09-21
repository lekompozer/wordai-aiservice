import requests
import json
import base64
import asyncio
from PIL import Image, ImageDraw, ImageFont
import io
from src.clients.chatgpt_client import ChatGPTClient
from config.config import CHATGPT_API_KEY

def create_real_image_base64():
    """Tạo image thật thay vì encode text"""
    
    # Tạo image 400x300 với nền trắng
    img = Image.new('RGB', (400, 300), color='white')
    draw = ImageDraw.Draw(img)
    
    # Vẽ text giả lập sổ đỏ
    try:
        # Dùng font mặc định
        font = ImageFont.load_default()
    except:
        font = None
    
    # Vẽ nội dung sổ đỏ
    text_lines = [
        "GIẤY CHỨNG NHẬN QUYỀN SỬ DỤNG ĐẤT",
        "",
        "Người sử dụng: NGUYỄN VĂN A", 
        "Địa chỉ: 123 Đường ABC, Quận 1, TP.HCM",
        "",
        "THÔNG TIN ĐẤT:",
        "- Diện tích: 100 m²",
        "- Mục đích: Đất ở tại đô thị", 
        "- Thời hạn: Lâu dài",
        "",
        "Giá trị ước tính: 10.000.000.000 VNĐ"
    ]
    
    y_position = 20
    for line in text_lines:
        if line:  # Không vẽ dòng trống
            draw.text((20, y_position), line, fill='black', font=font)
        y_position += 25
    
    # Vẽ border
    draw.rectangle([10, 10, 390, 290], outline='black', width=2)
    
    # Convert sang base64
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_base64 = base64.b64encode(img_buffer.getvalue()).decode()
    
    return img_base64

def test_chatgpt_with_real_image():
    """Test ChatGPT với real image"""
    print("=== Testing ChatGPT với Real Image ===")
    
    try:
        client = ChatGPTClient(CHATGPT_API_KEY, model="gpt-4o")
        
        # Tạo real image
        image_base64 = create_real_image_base64()
        print(f"Created image base64, length: {len(image_base64)}")
        
        # Multimodal message với real image
        messages = [
            {"role": "system", "content": "Bạn là chuyên gia định giá bất động sản tại Việt Nam."},
            {
                "role": "user", 
                "content": [
                    {"type": "text", "text": "Hãy phân tích thông tin bất động sản trong hình ảnh này và ước tính giá trị thị trường hiện tại."},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_base64}"
                        }
                    }
                ]
            }
        ]
        
        print("Testing multimodal completion với real image...")
        result = asyncio.run(client.chat_completion(messages))
        print(f"✅ Multimodal result: {result}")
        
        return True
        
    except Exception as e:
        print(f"❌ ChatGPT multimodal test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_chatgpt_multimodal_via_api_fixed():
    """Test ChatGPT multimodal qua API với real image"""
    print("\n=== Testing ChatGPT Multimodal via API (Fixed) ===")
    
    try:
        # Tạo real image
        image_base64 = create_real_image_base64()
        
        multimodal_request = {
            "question": "Phân tích bất động sản trong hình ảnh này và ước tính giá trị",
            "userId": "test_chatgpt_multimodal_fixed",
            "ai_provider": "chatgpt",
            "use_backend_ocr": False,
            "files": [
                {
                    "filename": "so_do.png",
                    "content_type": "image/png",
                    "content": image_base64
                }
            ]
        }
        
        print("Testing ChatGPT multimodal via API với real image...")
        response = requests.post(
            "http://localhost:8000/chat-with-files-stream", 
            json=multimodal_request, 
            stream=True, 
            timeout=60
        )
        
        print(f"Response status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"Error response: {response.text}")
            return False
        
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
                            print(f"\nProvider used: {data.get('provider', 'unknown')}")
                            break
                        elif "error" in data:
                            print(f"\n❌ API Error: {data['error']}")
                            return False
                    except json.JSONDecodeError:
                        continue
        
        print(f"\n✅ Full response length: {len(full_response)}")
        return True
        
    except Exception as e:
        print(f"❌ Multimodal API test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_simple_chatgpt_text_only():
    """Test ChatGPT text-only qua API để đảm bảo hoạt động"""
    print("\n=== Testing ChatGPT Text-Only (Control Test) ===")
    
    text_request = {
        "question": "Lãi suất tiết kiệm 12 tháng hiện tại của Vietcombank là bao nhiêu?",
        "userId": "test_chatgpt_control",
        "ai_provider": "chatgpt",
        "use_backend_ocr": False
    }
    
    try:
        response = requests.post(
            "http://localhost:8000/chat-with-files-stream",
            json=text_request,
            stream=True,
            timeout=30
        )
        
        print(f"Response status: {response.status_code}")
        
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
                            return True
                        elif "error" in data:
                            print(f"\n❌ Error: {data['error']}")
                            return False
                    except:
                        continue
        
    except Exception as e:
        print(f"❌ Text-only test failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Testing ChatGPT Multimodal (Fixed Version)...")
    print(f"CHATGPT_API_KEY available: {bool(CHATGPT_API_KEY)}")
    
    # Test 1: Control test với text-only
    control_success = test_simple_chatgpt_text_only()
    
    # Test 2: Direct client với real image
    if control_success:
        direct_success = test_chatgpt_with_real_image()
        
        # Test 3: API endpoint với real image
        if direct_success:
            api_success = test_chatgpt_multimodal_via_api_fixed()
            
            if api_success:
                print("\n🎉 All ChatGPT multimodal tests passed!")
            else:
                print("\n❌ API multimodal test failed")
        else:
            print("\n❌ Direct multimodal test failed") 
    else:
        print("\n❌ Control test failed")