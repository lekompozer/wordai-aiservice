import requests
import json
import base64
import asyncio
from src.clients.chatgpt_client import ChatGPTClient
from src.providers.ai_provider_manager import AIProviderManager
from config.config import CHATGPT_API_KEY, DEEPSEEK_API_KEY

BASE_URL = "http://localhost:8000"

def test_chatgpt_direct():
    """Test ChatGPT client trực tiếp"""
    print("=== Testing ChatGPT Client Directly ===")
    
    if not CHATGPT_API_KEY:
        print("❌ CHATGPT_API_KEY not found")
        return
    
    try:
        client = ChatGPTClient(CHATGPT_API_KEY, model="gpt-4o")
        
        # Test simple text message
        messages = [
            {"role": "system", "content": "Bạn là trợ lý AI hữu ích."},
            {"role": "user", "content": "Lãi suất tiết kiệm 12 tháng là bao nhiêu? Trả lời ngắn gọn."}
        ]
        
        print("Testing simple text completion...")
        result = asyncio.run(client.chat_completion(messages))
        print(f"✅ Simple completion result: {result}")
        
        print("\nTesting streaming...")
        async def test_streaming():
            chunks = []
            async for chunk in client.chat_completion_stream(messages):
                chunks.append(chunk)
                print(chunk, end="", flush=True)
            print(f"\n✅ Streaming completed. Total chunks: {len(chunks)}")
        
        asyncio.run(test_streaming())
        
    except Exception as e:
        print(f"❌ ChatGPT direct test failed: {e}")
        import traceback
        traceback.print_exc()

def test_chatgpt_with_multimodal():
    """Test ChatGPT với multimodal content"""
    print("\n=== Testing ChatGPT Multimodal ===")
    
    try:
        client = ChatGPTClient(CHATGPT_API_KEY, model="gpt-4o")
        
        # Tạo simple base64 image (text as image)
        text_content = "Sổ đỏ - Diện tích: 100m2, Quận 1, TP.HCM"
        image_base64 = base64.b64encode(text_content.encode()).decode()
        
        # Multimodal message
        messages = [
            {"role": "system", "content": "Bạn là chuyên gia phân tích bất động sản."},
            {
                "role": "user", 
                "content": [
                    {"type": "text", "text": "Phân tích thông tin trong hình ảnh này"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        }
                    }
                ]
            }
        ]
        
        print("Testing multimodal completion...")
        result = asyncio.run(client.chat_completion(messages))
        print(f"✅ Multimodal result: {result}")
        
    except Exception as e:
        print(f"❌ ChatGPT multimodal test failed: {e}")
        import traceback
        traceback.print_exc()

def test_ai_provider_manager():
    """Test AI Provider Manager với ChatGPT"""
    print("\n=== Testing AI Provider Manager ===")
    
    try:
        manager = AIProviderManager(DEEPSEEK_API_KEY, CHATGPT_API_KEY)
        
        messages = [
            {"role": "system", "content": "Bạn là trợ lý AI."},
            {"role": "user", "content": "Chào bạn, hôm nay thế nào?"}
        ]
        
        print("Testing ChatGPT via manager...")
        result = asyncio.run(manager.chat_completion(messages, "chatgpt"))
        print(f"✅ Manager result: {result}")
        
        print("\nTesting ChatGPT streaming via manager...")
        async def test_manager_streaming():
            chunks = []
            async for chunk in manager.chat_completion_stream(messages, "chatgpt"):
                chunks.append(chunk)
                print(chunk, end="", flush=True)
            print(f"\n✅ Manager streaming completed. Total chunks: {len(chunks)}")
        
        asyncio.run(test_manager_streaming())
        
    except Exception as e:
        print(f"❌ AI Provider Manager test failed: {e}")
        import traceback
        traceback.print_exc()

def test_chatgpt_via_api():
    """Test ChatGPT qua API endpoint"""
    print("\n=== Testing ChatGPT via API Endpoint ===")
    
    # Simple text request
    text_request = {
        "question": "Chào bạn, bạn là ai?",
        "userId": "test_chatgpt_api",
        "ai_provider": "chatgpt",
        "use_backend_ocr": False
    }
    
    print("Testing ChatGPT text-only via API...")
    try:
        response = requests.post(f"{BASE_URL}/chat-with-files-stream", json=text_request, stream=True)
        print(f"Response status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"Error response: {response.text}")
            return
        
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
                        elif "error" in data:
                            print(f"\n❌ API Error: {data['error']}")
                            break
                    except json.JSONDecodeError as e:
                        print(f"\n❌ JSON decode error: {e}")
                        print(f"Raw line: {line}")
                        continue
        
    except Exception as e:
        print(f"❌ API test failed: {e}")
        import traceback
        traceback.print_exc()

def test_chatgpt_multimodal_via_api():
    """Test ChatGPT multimodal qua API"""
    print("\n=== Testing ChatGPT Multimodal via API ===")
    
    # Tạo simple image data
    text_content = "Sổ đỏ: Diện tích 100m2, Quận 1 TP.HCM, Giá trị ước tính 10 tỷ"
    image_base64 = base64.b64encode(text_content.encode()).decode()
    
    multimodal_request = {
        "question": "Phân tích bất động sản trong hình ảnh này",
        "userId": "test_chatgpt_multimodal",
        "ai_provider": "chatgpt",
        "use_backend_ocr": False,
        "files": [
            {
                "filename": "so_do.jpg",
                "content_type": "image/jpeg",
                "content": image_base64
            }
        ]
    }
    
    print("Testing ChatGPT multimodal via API...")
    try:
        response = requests.post(f"{BASE_URL}/chat-with-files-stream", json=multimodal_request, stream=True, timeout=60)
        print(f"Response status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"Error response: {response.text}")
            return
        
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
                        elif "error" in data:
                            print(f"\n❌ API Error: {data['error']}")
                            break
                    except json.JSONDecodeError as e:
                        print(f"\n❌ JSON decode error: {e}")
                        continue
        
    except Exception as e:
        print(f"❌ Multimodal API test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 Starting ChatGPT isolated tests...")
    print(f"CHATGPT_API_KEY available: {bool(CHATGPT_API_KEY)}")
    
    # Test theo từng layer
    test_chatgpt_direct()              # Layer 1: Direct client
    test_chatgpt_with_multimodal()     # Layer 2: Multimodal support
    test_ai_provider_manager()         # Layer 3: Provider manager
    test_chatgpt_via_api()            # Layer 4: API endpoint (text)
    test_chatgpt_multimodal_via_api() # Layer 5: API endpoint (multimodal)
    
    print("\n🎉 All ChatGPT tests completed!")