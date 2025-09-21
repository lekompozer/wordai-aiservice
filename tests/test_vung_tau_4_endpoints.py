import requests
import json
import base64
from PIL import Image, ImageDraw, ImageFont
import io
import time
from datetime import datetime

BASE_URL = "http://localhost:8000"

def get_expected_model(provider_name: str) -> str:
    """Trả về model mong đợi cho từng provider"""
    model_mapping = {
        "DeepSeek Standard": "deepseek-chat",
        "GPT-4o Standard": "gpt-4o", 
        "DeepSeek Reasoning": "deepseek-chat (enhanced prompt)",
        "GPT-4o Reasoning": "gpt-4o (has images) / o1-preview (text-only)"
    }
    return model_mapping.get(provider_name, "unknown")

def create_vung_tau_house_image():
    """Tạo hình ảnh sổ hồng nhà 1 trệt 2 lầu Vũng Tàu"""
    img = Image.new('RGB', (700, 900), color='white')
    draw = ImageDraw.Draw(img)
    
    try:
        font_title = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 18)
        font_large = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 14)
        font_normal = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 12)
        font_small = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 10)
    except:
        font_title = font_large = font_normal = font_small = ImageFont.load_default()
    
    # Header chính thức
    draw.text((50, 30), "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", fill='black', font=font_large)
    draw.text((50, 55), "Độc lập - Tự do - Hạnh phúc", fill='black', font=font_normal)
    draw.text((450, 55), "Số: VT-2024-005678", fill='black', font=font_normal)
    
    # Title
    draw.text((50, 100), "GIẤY CHỨNG NHẬN QUYỀN SỬ DỤNG ĐẤT", fill='red', font=font_title)
    draw.text((50, 125), "QUYỀN SỞ HỮU NHÀ Ở VÀ TÀI SẢN KHÁC GẮN LIỀN VỚI ĐẤT", fill='red', font=font_title)
    draw.text((50, 150), "(SỔ HỒNG)", fill='red', font=font_large)
    
    # Content với thông tin ĐẤT CHÂU PHA - CẬP NHẬT MỚI
    content = [
        "",
        "I. THÔNG TIN CHUNG:",
        "- Số vào sổ cấp: VT-2024-005678",
        "- Ngày cấp: 15/03/2024",
        "- Cơ quan cấp: UBND TP. Vũng Tàu",
        "",
        "II. NGƯỜI SỬ DỤNG ĐẤT:",
        "- Họ và tên: NGUYỄN VĂN MINH",
        "- CCCD: 271234567890, ngày cấp: 10/01/2020",
        "- Địa chỉ thường trú: Ấp Tân Trung, Xã Châu Pha",
        "",
        "III. THÔNG TIN VỀ ĐẤT:",
        "- Địa chỉ thửa đất: Ấp Tân Trung, Xã Châu Pha, thị xã Phú Mỹ, tỉnh Bà Rịa - Vũng Tàu",
        "- Số tờ bản đồ: 33; Số thửa: 2007",
        "- Diện tích: 1,855.3 m²",
        "- Mục đích sử dụng: Đất trồng cây lâu năm",
        "- Thời hạn sử dụng: 2049",
        "- Nguồn gốc: Được tặng cho đất được Công nhận QSDĐ như giao đất không thu tiền sử dụng đất",
        "- Hình thức sử dụng: Sử dụng riêng",
        "",
        "IV. THÔNG TIN VỀ NHÀ Ở VÀ TÀI SẢN KHÁC TRÊN ĐẤT:",
        "- Loại nhà ở: Không",
        "- Cây trồng: Không",
        "",
        "V. THÔNG TIN KHÁC:",
        "- Tình trạng pháp lý: Sổ hồng chính chủ, không tranh chấp",
        "- Mặt tiền: 17.6m (đường nhựa 8m)",
        "- Địa hình: Mặt tiền nở hậu", 
        "- Khu vực: Gần trung tâm Phú Mỹ, tiềm năng phát triển cao",
        "",
        "Ghi chú: Đất nông nghiệp có tiềm năng chuyển đổi mục đích sử dụng"
    ]
    
    y_position = 180
    for line in content:
        if line.startswith("I.") or line.startswith("II.") or line.startswith("III.") or line.startswith("IV.") or line.startswith("V."):
            draw.text((50, y_position), line, fill='blue', font=font_large)
        elif line.startswith("-"):
            draw.text((70, y_position), line, fill='black', font=font_normal)
        elif line.startswith("  +"):
            draw.text((90, y_position), line, fill='black', font=font_small)
        elif line:
            draw.text((50, y_position), line, fill='black', font=font_normal)
        y_position += 20
    
    # Border và chữ ký
    draw.rectangle([30, 20, 670, 880], outline='black', width=3)
    draw.rectangle([40, 30, 660, 870], outline='black', width=1)
    
    # Chữ ký
    draw.text((450, 820), "TP. Vũng Tàu, ngày 15 tháng 03 năm 2024", fill='black', font=font_normal)
    draw.text((450, 840), "CHỦ TỊCH UBND TP. VŨNG TÀU", fill='black', font=font_normal)
    draw.text((450, 860), "(Đã ký)", fill='black', font=font_normal)
    
    # Convert to base64
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    return base64.b64encode(img_buffer.getvalue()).decode()

def test_endpoint(endpoint: str, provider_name: str):
    """Test một endpoint cụ thể"""
    print(f"\n{'='*80}")
    print(f"TESTING: {provider_name.upper()}")
    print(f"Endpoint: {endpoint}")
    print(f"Expected Model: {get_expected_model(provider_name)}")
    print(f"Time: {datetime.now()}")
    print(f"{'='*80}")
    
    # Tạo image data
    image_base64 = create_vung_tau_house_image()
    
    # Request data
    request_data = {
        "question": "Hãy định giá miếng đất nông nghiệp này và phân tích chi tiết khả năng thế chấp ngân hàng để vay thế chấp tối đa. Tôi muốn biết có thể vay được bao nhiêu tiền từ bất động sản này.",
        "userId": f"test_{provider_name.replace('-', '_')}",
        "files": [
            {
                "filename": "so_hong_dat_chau_pha.png",
                "content_type": "image/png",
                "content": image_base64
            }
        ]
    }
    
    start_time = time.time()
    full_response = ""
    
    try:
        response = requests.post(
            f"{BASE_URL}{endpoint}",
            json=request_data,
            stream=True,
            timeout=180  # 3 minutes timeout
        )
        
        print(f"Response Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ Error: {response.text}")
            return None
        
        # Stream response
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
                            end_time = time.time()
                            duration = end_time - start_time
                            print(f"\n\n✅ COMPLETED")
                            print(f"Provider: {data.get('provider', 'unknown')}")
                            print(f"Mode: {data.get('mode', 'unknown')}")
                            print(f"Duration: {duration:.2f} seconds")
                            print(f"Response length: {len(full_response)} characters")
                            break
                        elif "error" in data:
                            print(f"\n❌ ERROR: {data['error']}")
                            return None
                    except json.JSONDecodeError:
                        continue
        
        return {
            "provider": provider_name,
            "response": full_response,
            "duration": duration,
            "length": len(full_response)
        }
        
    except Exception as e:
        print(f"\n❌ Exception: {e}")
        return None

def run_comprehensive_test():
    """Chạy test tất cả 4 endpoints và so sánh"""
    
    print("🏠 COMPREHENSIVE REAL ESTATE VALUATION TEST")
    print("Property: Chính chủ, bán đất Châu Pha Bà Ria, DT 1855m2, mặt tiền đường 8m")
    print(f"Test started at: {datetime.now()}")
    
    # Định nghĩa 4 endpoints
    endpoints = [
        ("/real-estate/deepseek", "DeepSeek Standard"),
        ("/real-estate/gpt4o", "GPT-4o Standard"),
        ("/real-estate/deepseek-reasoning", "DeepSeek Reasoning"),
        ("/real-estate/gpt4o-reasoning", "GPT-4o Reasoning")
    ]
    
    results = []
    
    # Test từng endpoint
    for endpoint, provider_name in endpoints:
        result = test_endpoint(endpoint, provider_name)
        if result:
            results.append(result)
        
        # Nghỉ 2 giây giữa các test
        time.sleep(2)
    
    # Summary và comparison
    print(f"\n{'='*100}")
    print("SUMMARY & COMPARISON")
    print(f"{'='*100}")
    
    if results:
        print(f"{'Provider':<20} {'Duration':<12} {'Length':<10} {'Quality Indicators'}")
        print("-" * 80)
        
        for result in results:
            # Đánh giá chất lượng dựa trên keywords
            quality_keywords = [
                'triệu', 'tỷ', 'giá trị', 'thế chấp', 'vay', 'lãi suất', 
                'thẩm định', 'rủi ro', 'khuyến nghị', 'phân tích'
            ]
            quality_score = sum(1 for kw in quality_keywords if kw.lower() in result['response'].lower())
            
            print(f"{result['provider']:<20} {result['duration']:<12.2f} {result['length']:<10} {quality_score}/{len(quality_keywords)}")
        
        # Tìm provider tốt nhất
        best_reasoning = max([r for r in results if 'reasoning' in r['provider'].lower()], 
                           key=lambda x: len(x['response']), default=None)
        fastest = min(results, key=lambda x: x['duration'])
        longest = max(results, key=lambda x: x['length'])
        
        print(f"\n🏆 WINNERS:")
        if best_reasoning:
            print(f"🧠 Best Reasoning: {best_reasoning['provider']}")
        print(f"⚡ Fastest: {fastest['provider']} ({fastest['duration']:.2f}s)")
        print(f"📝 Most Detailed: {longest['provider']} ({longest['length']} chars)")
        
        # Recommendations
        print(f"\n💡 RECOMMENDATIONS:")
        print("- For quick valuation: DeepSeek Standard")
        print("- For balanced analysis: GPT-4o Standard") 
        print("- For deep analysis: GPT-4o Reasoning")
        print("- For budget option: DeepSeek Reasoning")
        
    else:
        print("❌ No successful tests completed")
    
    print(f"\nTest completed at: {datetime.now()}")

def test_single_endpoint():
    """Test một endpoint đơn lẻ để debug"""
    print("🔍 SINGLE ENDPOINT TEST")
    
    while True:
        print("\nAvailable endpoints:")
        print("1. /real-estate/deepseek")
        print("2. /real-estate/gpt4o")  
        print("3. /real-estate/deepseek-reasoning")
        print("4. /real-estate/gpt4o-reasoning")
        print("5. Exit")
        
        choice = input("\nSelect endpoint (1-5): ").strip()
        
        if choice == "5":
            break
        elif choice in ["1", "2", "3", "4"]:
            endpoints = [
                "/real-estate/deepseek",
                "/real-estate/gpt4o", 
                "/real-estate/deepseek-reasoning",
                "/real-estate/gpt4o-reasoning"
            ]
            names = [
                "DeepSeek Standard",
                "GPT-4o Standard",
                "DeepSeek Reasoning", 
                "GPT-4o Reasoning"
            ]
            
            endpoint = endpoints[int(choice) - 1]
            name = names[int(choice) - 1]
            
            test_endpoint(endpoint, name)
        else:
            print("❌ Invalid choice")

if __name__ == "__main__":
    print("🏠 VŨNG TÀU REAL ESTATE VALUATION TEST SUITE")
    print(f"Server: {BASE_URL}")
    
    while True:
        print("\n" + "="*50)
        print("TEST OPTIONS:")
        print("1. Run comprehensive test (all 4 endpoints)")
        print("2. Test single endpoint")
        print("3. Exit")
        
        choice = input("\nSelect option (1-3): ").strip()
        
        if choice == "1":
            run_comprehensive_test()
        elif choice == "2":
            test_single_endpoint()
        elif choice == "3":
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice")

