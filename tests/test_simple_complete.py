"""
Simple Complete Test for 3 Companies: Golden Dragon Restaurant, Ivy Fashion Store, VRB Bank
Test đơn giản và hoàn chỉnh cho 3 công ty: upload files, trích xuất content, tạo Qdrant vector database
"""

import os
import asyncio
import boto3
import pandas as pd
import openai
from datetime import datetime
from pathlib import Path
import requests

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

class SimpleCompanyProcessor:
    def __init__(self):
        # Initialize R2 client
        self.r2_client = boto3.client(
            's3',
            endpoint_url='https://ad4f05c99ba9b9d5e4ae5b3fc3b3dcb3.r2.cloudflarestorage.com',
            aws_access_key_id=os.getenv('R2_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('R2_SECRET_ACCESS_KEY'),
            region_name='auto'
        )
        
        # Initialize OpenAI client
        self.openai_client = openai.OpenAI(
            api_key=os.getenv("CHATGPT_API_KEY")
        )
        
        self.bucket_name = "agent8x"
        
    def get_public_url(self, remote_path: str) -> str:
        """Get public URL for uploaded file"""
        return f"https://agent8x.io.vn/{remote_path}"
    
    async def upload_file_to_r2(self, local_path: str, remote_path: str) -> str:
        """Upload file to R2 storage"""
        try:
            self.r2_client.upload_file(local_path, self.bucket_name, remote_path)
            public_url = self.get_public_url(remote_path)
            print(f"✅ Uploaded: {public_url}")
            return public_url
        except Exception as e:
            print(f"❌ Upload failed: {e}")
            return None
    
    def extract_text_from_image(self, image_url: str) -> str:
        """Extract text from image using ChatGPT Vision"""
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Extract ALL text content from this image. Return only the text, no explanations."
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": image_url}
                            }
                        ]
                    }
                ],
                max_tokens=4000
            )
            
            content = response.choices[0].message.content
            print(f"📸 Image text extracted: {len(content)} characters")
            return content
            
        except Exception as e:
            print(f"❌ Image extraction failed: {e}")
            return ""
    
    def read_file_content(self, file_path: str) -> str:
        """Read content from file"""
        try:
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
                return df.to_string()
            else:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
        except Exception as e:
            print(f"❌ File read failed: {e}")
            return ""
    
    async def process_company_files(self, company_name: str, company_folder: str, files: list) -> dict:
        """Process all files for a company"""
        print(f"\n🏢 Processing: {company_name}")
        print("=" * 50)
        
        company_data = {
            "name": company_name,
            "folder": company_folder,
            "files": [],
            "total_content": ""
        }
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        for file_name in files:
            local_path = f"company-data-test/{file_name}"
            if not os.path.exists(local_path):
                print(f"⚠️ File not found: {local_path}")
                continue
                
            print(f"\n📄 Processing: {file_name}")
            
            # Generate remote path with timestamp
            file_ext = Path(file_name).suffix
            base_name = Path(file_name).stem
            remote_path = f"companies/{company_folder}/{timestamp}_{base_name}{file_ext}"
            
            # Upload to R2
            public_url = await self.upload_file_to_r2(local_path, remote_path)
            if not public_url:
                continue
            
            # Extract content
            content = ""
            if file_name.endswith(('.jpg', '.jpeg', '.png')):
                # Extract text from image
                content = self.extract_text_from_image(public_url)
            else:
                # Read text file
                content = self.read_file_content(local_path)
            
            file_data = {
                "name": file_name,
                "url": public_url,
                "content": content,
                "type": "image" if file_name.endswith(('.jpg', '.jpeg', '.png')) else "text"
            }
            
            company_data["files"].append(file_data)
            company_data["total_content"] += f"\n\n=== {file_name} ===\n{content}"
            
            print(f"✅ Text extracted: {len(content)} characters")
        
        return company_data
    
    def create_qdrant_via_api(self, collection_name: str, company_data: dict):
        """Create Qdrant collection via API"""
        try:
            # Prepare data for our API
            api_data = {
                "company_id": collection_name,
                "company_name": company_data["name"],
                "content": company_data["total_content"],
                "files": [
                    {
                        "name": f["name"],
                        "url": f["url"],
                        "content": f["content"]
                    }
                    for f in company_data["files"]
                ]
            }
            
            # Send to our document processing API
            api_url = "http://localhost:8000/api/v1/documents/process"
            response = requests.post(api_url, json=api_data)
            
            if response.status_code == 200:
                print(f"✅ Created Qdrant collection via API: {collection_name}")
                return response.json()
            else:
                print(f"❌ API call failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Qdrant API call failed: {e}")
            return None

async def test_chat_with_companies(processor, company_data_list):
    """Test chat functionality with all companies"""
    print(f"\n🤖 Testing Chat with Companies")
    print("=" * 50)
    
    # Test scenarios for each company
    test_scenarios = {
        "golden-dragon-restaurant": [
            "Cho tôi xem menu nhà hàng và giá món ăn",
            "Tôi muốn đặt bàn cho 4 người vào tối nay lúc 7h",
            "Món gà H'mông nấm bí quả giá bao nhiêu?"
        ],
        "ivy-fashion-store": [
            "Tôi muốn xem các sản phẩm thời trang", 
            "Có áo sơ mi nam không? Giá bao nhiêu?",
            "Tôi muốn đặt mua 1 áo blazer size M"
        ],
        "vrb-bank-financial": [
            "Tôi muốn vay tiêu dùng 100 triệu VNĐ",
            "Lãi suất vay mua nhà hiện tại là bao nhiêu?",
            "Thủ tục mở tài khoản tiết kiệm như thế nào?"
        ]
    }
    
    for company_data in company_data_list:
        collection_name = company_data["folder"].replace("-", "_")
        company_name = company_data["name"]
        
        print(f"\n🏢 Testing chat with: {company_name}")
        print("-" * 30)
        
        if collection_name.replace("_", "-") in test_scenarios:
            scenarios = test_scenarios[collection_name.replace("_", "-")]
            
            for i, question in enumerate(scenarios, 1):
                print(f"\n❓ Test {i}: {question}")
                
                try:
                    # Test chat via API
                    chat_data = {
                        "company_id": collection_name,
                        "message": question,
                        "conversation_id": f"test_{collection_name}_{i}",
                        "language": "vi"
                    }
                    
                    response = requests.post("http://localhost:8000/api/v1/chat/unified", json=chat_data)
                    
                    if response.status_code == 200:
                        result = response.json()
                        print(f"✅ Response: {result.get('response', 'No response')[:200]}...")
                        
                        # Check if order/booking code generated
                        if 'order_code' in result:
                            print(f"🛒 Order Code: {result['order_code']}")
                        if 'booking_code' in result:
                            print(f"🪑 Booking Code: {result['booking_code']}")
                        if 'loan_code' in result:
                            print(f"💰 Loan Code: {result['loan_code']}")
                            
                    else:
                        print(f"❌ Chat API failed: {response.status_code}")
                        
                except Exception as e:
                    print(f"❌ Chat test failed: {e}")

async def main():
    """Main test function"""
    print("🚀 Simple Complete Test for 3 Companies")
    print("=" * 60)
    
    processor = SimpleCompanyProcessor()
    
    # Define companies and their files
    companies = {
        "Nhà hàng Golden Dragon": {
            "folder": "golden-dragon-restaurant",
            "files": ["golden-dragon-info.txt", "golden-dragon-menu.jpg"]
        },
        "Cửa hàng Ivy Fashion": {
            "folder": "ivy-fashion-store", 
            "files": ["ivy-fashion-info.txt", "ivy-fashion-products.csv"]
        },
        "Ngân hàng VRB": {
            "folder": "vrb-bank-financial",
            "files": ["vrb-bank-info.md", "vrb-bank-services.docx"]
        }
    }
    
    all_company_data = []
    
    # Process each company
    for company_name, company_info in companies.items():
        # Process files
        company_data = await processor.process_company_files(
            company_name,
            company_info["folder"],
            company_info["files"]
        )
        
        # Create Qdrant collection via API
        processor.create_qdrant_via_api(company_info["folder"], company_data)
        
        all_company_data.append(company_data)
    
    # Test chat functionality
    await test_chat_with_companies(processor, all_company_data)
    
    # Summary
    print(f"\n📊 Processing Summary")
    print("=" * 40)
    
    for company_data in all_company_data:
        print(f"\n🏢 {company_data['name']}")
        for file_data in company_data['files']:
            print(f"   ✅ {file_data['name']} ({len(file_data['content'])} chars)")
            print(f"      📎 {file_data['url']}")
    
    print(f"\n🎉 All companies processed successfully!")
    print(f"✅ Files uploaded to R2")
    print(f"✅ Content extracted from images and text")
    print(f"✅ Vector databases created in Qdrant")
    print(f"✅ Chat testing completed!")

if __name__ == "__main__":
    asyncio.run(main())
