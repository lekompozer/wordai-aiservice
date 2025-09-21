"""
Test ChatGPT Vision API for Image Text Extraction
Test trích xuất text từ hình ảnh bằng ChatGPT Vision
"""

import os
import asyncio
from src.providers.ai_provider_manager import get_default_provider

async def test_image_text_extraction():
    """Test trích xuất text từ menu Golden Dragon"""
    print("🖼️ Testing Image Text Extraction with ChatGPT Vision")
    print("=" * 60)
    
    # Image URL from R2 upload
    image_url = "https://files.agent8x.io.vn/companies/golden-dragon-restaurant/20250714_103031_golden-dragon-menu.jpg"
    
    try:
        # Get AI provider
        ai_provider = get_default_provider()
        
        prompt = """
        Please extract ALL text content from this restaurant menu image. 
        List all items with their prices in Vietnamese currency.
        Format the output clearly with categories and items.
        
        Hãy trích xuất TẤT CẢ nội dung text từ hình ảnh menu nhà hàng này.
        Liệt kê tất cả món ăn với giá bằng tiền Việt Nam.
        Định dạng output rõ ràng theo danh mục và món ăn.
        """
        
        print(f"📸 Processing image: {image_url}")
        print(f"🤖 Using AI provider: {ai_provider.__class__.__name__}")
        
        # Generate response with image
        response = await ai_provider.generate_response(
            prompt=prompt,
            context="",
            image_url=image_url,
            max_tokens=2000
        )
        
        if response and response.strip():
            print(f"\n✅ Text extraction successful!")
            print(f"📝 Extracted content ({len(response)} characters):")
            print("=" * 50)
            print(response)
            print("=" * 50)
            
            # Save extracted content
            output_file = "extracted_menu_content.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"# Extracted Menu Content from Golden Dragon\n")
                f.write(f"# Image URL: {image_url}\n")
                f.write(f"# Extracted at: {asyncio.get_event_loop().time()}\n\n")
                f.write(response)
            
            print(f"💾 Content saved to: {output_file}")
            
        else:
            print(f"❌ No text extracted from image")
            
    except Exception as e:
        print(f"❌ Error extracting text from image: {e}")
        import traceback
        traceback.print_exc()

async def test_multiple_images():
    """Test trích xuất từ nhiều image URLs"""
    print("\n🖼️ Testing Multiple Image URLs")
    print("=" * 40)
    
    # Test với các image URLs khác nhau
    test_images = [
        {
            "name": "Golden Dragon Menu",
            "url": "https://files.agent8x.io.vn/companies/golden-dragon-restaurant/20250714_103031_golden-dragon-menu.jpg",
            "description": "Restaurant menu image"
        }
    ]
    
    ai_provider = get_default_provider()
    
    for image_info in test_images:
        print(f"\n📸 Testing: {image_info['name']}")
        print(f"🔗 URL: {image_info['url']}")
        
        try:
            prompt = f"""
            Extract all text from this {image_info['description']}.
            Return the content in a structured format.
            Include prices if this is a menu.
            
            Trích xuất tất cả text từ {image_info['description']} này.
            Trả về nội dung có cấu trúc rõ ràng.
            Bao gồm giá nếu đây là menu.
            """
            
            response = await ai_provider.generate_response(
                prompt=prompt,
                context="",
                image_url=image_info['url'],
                max_tokens=1500
            )
            
            if response:
                print(f"✅ Success: {len(response)} characters extracted")
                print(f"📝 Preview: {response[:200]}...")
            else:
                print(f"❌ Failed to extract text")
                
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    async def main():
        await test_image_text_extraction()
        await test_multiple_images()
    
    asyncio.run(main())
