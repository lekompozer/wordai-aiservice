import requests
import base64
import json
import os

# Configuration
BASE_URL = "http://localhost:8000"  # Adjust if your server runs on a different port
TEST_IMAGE_URL = "https://i.ibb.co/fzyvwdTg/sodo3.jpg"
USER_ID = "test_ocr_valuation_user"

async def test_chatgpt_vision_url():
    """Test ChatGPT Vision với URL trực tiếp"""
    print("\n--- Testing ChatGPT Vision với URL trực tiếp ---")
    
    payload = {
        "url": TEST_IMAGE_URL,
        "filename": "sodo3.jpg"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/test-ocr-url", json=payload)
        response.raise_for_status()
        result = response.json()
        print("ChatGPT Vision URL Test Result:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        if result.get("success"):
            print(f"\n✅ OCR Success!")
            print(f"Extracted text length: {result.get('text_length', 0)}")
            print(f"Extracted text: {result.get('extracted_text', 'N/A')}")
            return result.get('extracted_text', '')
        else:
            print(f"\n❌ OCR Failed: {result.get('error', 'Unknown error')}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"Error calling /test-ocr-url: {e}")
        return None

async def download_image_to_base64(url):
    """Download image từ URL và convert sang Base64"""
    try:
        import httpx
        
        print(f"Downloading image from: {url}")
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            
            image_data = response.content
            file_base64 = base64.b64encode(image_data).decode()
            
            print(f"Downloaded image: {len(image_data)} bytes")
            print(f"Base64 length: {len(file_base64)} characters")
            
            return file_base64, response.headers.get("content-type", "image/jpeg")
            
    except Exception as e:
        print(f"Error downloading image: {e}")
        return None, None

async def test_deepseek_reasoning_with_url():
    """Test /real-estate/deepseek-reasoning với image từ URL"""
    print(f"\n--- Testing /real-estate/deepseek-reasoning với URL image ---")
    
    # Download image từ URL
    image_base64, content_type = await download_image_to_base64(TEST_IMAGE_URL)
    if not image_base64:
        print("❌ Không thể download image từ URL")
        return

    valuation_question = "Hãy phân tích và định giá bất động sản này với thông tin thêm Tổng 280.9m²: Thổ cư 80m² (lâu dài) + đất trồng cây hàng năm 200.9m² (hết hạn 2063), đất phủ hồng toàn bộ. Đã xây kè đá, đổ nền bằng mặt đường, không vướng cột điện, ko lỗi phong thủy.Mặt tiền đường Xuân Sơn- Đá bạc DT 997 đang mở rộng 30m (đường cấp 1, tải trọng 40 tấn, (đang mở cách đất 400m, 2025 xong)Phía sau là suối thủy lợi, view thung lũng lộng gió Đông Nam quanh năm.Ngay khu dân cư đông đúc, gần chợ , trường, Cách công An Xã Suối Rao 800m"

    payload = {
        "question": valuation_question,
        "userId": USER_ID,
        "files": [
            {
                "filename": "sodo3.jpg",
                "content_type": content_type,
                "content": image_base64
            }
        ]
    }

    full_response_text = ""
    try:
        print("Sending request to /real-estate/deepseek-reasoning...")
        with requests.post(f"{BASE_URL}/real-estate/deepseek-reasoning", json=payload, stream=True) as response:
            response.raise_for_status()
            print("Streaming response:")
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    if decoded_line.startswith('data: '):
                        try:
                            data_json = json.loads(decoded_line[len('data: '):])
                            if "chunk" in data_json:
                                print(data_json["chunk"], end="", flush=True)
                                full_response_text += data_json["chunk"]
                            elif "progress" in data_json:
                                print(f"\n[PROGRESS] {data_json['progress']}")
                            elif "done" in data_json and data_json["done"]:
                                print("\n--- Stream finished ---")
                                print(f"Final status: {data_json}")
                                break
                            elif "error" in data_json:
                                print(f"\n[ERROR] {data_json['error']}")
                                break
                        except json.JSONDecodeError:
                            print(f"\n[RAW STREAM DATA (JSON DECODE ERROR)] {decoded_line}")
            print("\n--- End of Stream ---")
            if not full_response_text:
                print("Warning: No content chunks received in the stream.")

    except requests.exceptions.RequestException as e:
        print(f"Error calling /real-estate/deepseek-reasoning: {e}")
    
    print("\nFull response from DeepSeek Reasoning (concatenated):")
    if full_response_text:
        print(full_response_text)
    else:
        print("No text content was streamed.")

async def main():
    print(f"🔍 Testing với image URL: {TEST_IMAGE_URL}")
    
    # ✅ Test 1: ChatGPT Vision OCR với URL trực tiếp
    ocr_result = await test_chatgpt_vision_url()
    
    # ✅ Test 2: Real Estate Valuation với image từ URL
    await test_deepseek_reasoning_with_url()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())