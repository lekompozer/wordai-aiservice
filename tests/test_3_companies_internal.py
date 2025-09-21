# test_3_companies_internal.py
"""
Internal AI Service Test - No Backend Integration
Test upload files to R2, process to Qdrant, and chat testing
"""

import asyncio
import os
import sys
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any
import pandas as pd
import base64

# Debug environment info
print("===================================================")
print(f"🐍 Python Executable: {sys.executable}")
print(f"🐍 Python Version: {sys.version}")
print("===================================================")

# Add src to path to resolve imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

try:
    from services.unified_chat_service import UnifiedChatService
    from services.company_data_manager import CompanyDataManager
    from services.data_extraction_service import DataExtractionService
    from providers.ai_provider_manager import AIProviderManager
    from storage.r2_client import R2Client
    from models.unified_models import UnifiedChatRequest, Industry, Language
    from utils.logger import setup_logger
    from src.queue.queue_manager import QueueManager, IngestionTask
except ImportError as e:
    print(f"❌ Import Error: {e}")
    print("Please ensure you are in the correct virtual environment and all dependencies are installed.")
    print("Try installing dependencies:")
    print(f"{sys.executable} -m pip install boto3 pandas")
    sys.exit(1)

logger = setup_logger()

class InternalAIServiceTest:
    def __init__(self):
        print("🔧 Initializing test services...")
        
        # Debug environment variables
        print(f"🔍 Debug Environment Variables:")
        print(f"   R2_ACCOUNT_ID: {os.getenv('R2_ACCOUNT_ID', 'NOT_SET')}")
        print(f"   R2_ACCESS_KEY_ID: {os.getenv('R2_ACCESS_KEY_ID', 'NOT_SET')}")
        print(f"   R2_SECRET_ACCESS_KEY: {os.getenv('R2_SECRET_ACCESS_KEY', 'NOT_SET')[:10]}...")
        print(f"   CHATGPT_API_KEY: {os.getenv('CHATGPT_API_KEY', 'NOT_SET')[:20]}...")
        print(f"   QDRANT_URL: {os.getenv('QDRANT_URL', 'NOT_SET')}")
        
        try:
            # Check for required environment variables
            required_env_vars = ['R2_ACCOUNT_ID', 'R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY', 'CHATGPT_API_KEY']
            missing_vars = [var for var in required_env_vars if not os.getenv(var)]
            
            if missing_vars:
                print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
                print("Please set these variables in your .env file or environment")
                sys.exit(1)
            
            # Initialize AI provider with API keys from environment
            deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")
            chatgpt_key = os.getenv("CHATGPT_API_KEY", "")
            self.ai_provider = AIProviderManager(deepseek_key, chatgpt_key)
            
            # Initialize services that depend on others
            self.extraction_service = DataExtractionService(self.ai_provider)
            self.data_manager = CompanyDataManager()
            self.chat_service = UnifiedChatService()
            
            # Initialize Queue Manager for ingestion
            self.queue_manager = QueueManager(redis_url=os.getenv('REDIS_URL', 'redis://localhost:6379'))
            
            # Initialize R2 client with environment variables
            self.r2_client = R2Client(
                account_id=os.getenv('R2_ACCOUNT_ID'),
                access_key_id=os.getenv('R2_ACCESS_KEY_ID'),
                secret_access_key=os.getenv('R2_SECRET_ACCESS_KEY'),
                bucket_name=os.getenv('R2_BUCKET_NAME', 'agent8x')
            )
            
            print("✅ Services initialized successfully.")
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            print(f"❌ Initialization failed: {e}")
            print(f"Error details: {str(e)}")
            sys.exit(1)
        
        # Company definitions
        self.companies = {
            "golden-dragon": {
                "id": "golden-dragon-restaurant",
                "name": "Nhà hàng Golden Dragon",
                "industry": Industry.RESTAURANT,
                "files": [
                    {
                        "path": "company-data-test/golden-dragon-info.txt",
                        "type": "info",
                        "data_type": "text"
                    },
                    {
                        "path": "company-data-test/golden-dragon-menu.jpg",
                        "type": "menu", 
                        "data_type": "image"
                    }
                ]
            },
            "ivy-fashion": {
                "id": "ivy-fashion-store",
                "name": "Cửa hàng thời trang Ivy Fashion",
                "industry": Industry.RETAIL,
                "files": [
                    {
                        "path": "company-data-test/ivy-fashion-info.txt",
                        "type": "info",
                        "data_type": "text"
                    },
                    {
                        "path": "company-data-test/ivy-fashion-products.csv",
                        "type": "products",
                        "data_type": "csv"
                    }
                ]
            },
            "vrb-bank": {
                "id": "vrb-bank-financial",
                "name": "Ngân hàng VRB",
                "industry": Industry.BANKING,
                "files": [
                    {
                        "path": "company-data-test/vrb-bank-info.md",
                        "type": "info",
                        "data_type": "text"
                    },
                    {
                        "path": "company-data-test/vrb-bank-services.docx",
                        "type": "services",
                        "data_type": "docx"
                    }
                ]
            }
        }
        
        # Store uploaded file URLs and test mode
        self.uploaded_files = {}
        self.test_mode = os.getenv('TEST_MODE', 'false').lower() == 'true'
        
        if self.test_mode:
            print("🧪 Running in TEST MODE - R2 upload will be simulated")
    
    async def upload_file_to_r2(self, file_path: str, company_id: str) -> str:
        """Upload file to R2 and return public URL"""
        try:
            # If in test mode, simulate upload
            if self.test_mode:
                return self.simulate_upload_for_test(file_path, company_id)
            
            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.basename(file_path)
            remote_path = f"companies/{company_id}/{timestamp}_{filename}"
            
            # Upload to R2 using the correct method
            success = await self.r2_client.upload_file(file_path, remote_path)
            
            if success:
                public_url = self.r2_client.get_public_url(remote_path)
                print(f"✅ Uploaded: {filename} → {public_url}")
                return public_url
            else:
                print(f"❌ Failed to upload {filename}, falling back to simulation")
                return self.simulate_upload_for_test(file_path, company_id)
                
        except Exception as e:
            logger.error(f"Upload error for {file_path}: {e}")
            print(f"❌ Upload error: {e}, falling back to simulation")
            return self.simulate_upload_for_test(file_path, company_id)
    
    def simulate_upload_for_test(self, file_path: str, company_id: str) -> str:
        """Simulate file upload for testing without R2"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.basename(file_path)
        remote_path = f"companies/{company_id}/{timestamp}_{filename}"
        public_url = f"https://agent8x.io.vn/{remote_path}"
        print(f"🧪 Simulated upload: {filename} → {public_url}")
        return public_url
    
    def _get_content_type(self, file_path: str) -> str:
        """Get content type based on file extension"""
        ext = os.path.splitext(file_path)[1].lower()
        content_types = {
            '.txt': 'text/plain',
            '.md': 'text/markdown',
            '.csv': 'text/csv',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        }
        return content_types.get(ext, 'application/octet-stream')
    
    async def extract_content_from_file(self, file_info: Dict, public_url: str, industry: str) -> Dict[str, Any]:
        """Extract content from file based on type"""
        try:
            file_path = file_info["path"]
            data_type = file_info["data_type"]
            
            if data_type == "text":
                # Read text content directly
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                return {
                    "success": True,
                    "content": content,
                    "metadata": {
                        "type": file_info["type"],
                        "format": "text"
                    }
                }
            
            elif data_type == "csv":
                # Process CSV data
                df = pd.read_csv(file_path)
                content = self._format_csv_content(df, industry)
                return {
                    "success": True,
                    "content": content,
                    "metadata": {
                        "type": file_info["type"],
                        "format": "csv",
                        "rows": len(df),
                        "columns": list(df.columns)
                    }
                }
            
            elif data_type == "image":
                # Use ChatGPT Vision to extract text from image
                print(f"🔍 Extracting text from image using ChatGPT Vision...")
                
                # Read image file
                with open(file_path, 'rb') as f:
                    image_data = f.read()
                
                # Convert to base64
                import base64
                base64_image = base64.b64encode(image_data).decode('utf-8')
                
                # Prepare messages for ChatGPT Vision
                prompt = f"""Extract all text content from this {file_info['type']} image.
                This is for a {industry} business. Extract menu items, prices, descriptions, and any other relevant information.
                Format the output in a clear, structured way in Vietnamese."""
                
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ]
                
                # Use ChatGPTClient for vision
                response = await self.ai_provider.chatgpt_client.chat_completion(messages)
                extracted_text = response
                print(f"✅ Extracted {len(extracted_text)} characters from image")
                
                return {
                    "success": True,
                    "content": extracted_text,
                    "metadata": {
                        "type": file_info["type"],
                        "format": "image",
                        "extraction_method": "chatgpt_vision"
                    }
                }
            
            elif data_type == "docx":
                # For demo, use predefined content
                content = self._get_vrb_services_content()
                return {
                    "success": True,
                    "content": content,
                    "metadata": {
                        "type": file_info["type"],
                        "format": "docx"
                    }
                }
            
        except Exception as e:
            logger.error(f"Content extraction error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _format_csv_content(self, df: pd.DataFrame, industry: str) -> str:
        """Format CSV content for better search"""
        if industry == "retail":
            lines = ["Danh sách sản phẩm thời trang Ivy Fashion:\n"]
            for _, row in df.iterrows():
                product_info = f"""
Sản phẩm: {row.get('TÊN SẢN PHẨM', '')}
- Mã SP: {row.get('MÃ SP', '')}
- Loại: {row.get('LOẠI', '')}
- Size: {row.get('SIZE', '')}
- Màu sắc: {row.get('MÀU SẮC', '')}
- Giá: {row.get('GIÁ', '')}
- Tồn kho: {row.get('TỒN KHO', '')}
- Mô tả: {row.get('MÔ TẢ', '')}
"""
                lines.append(product_info)
            return "\n".join(lines)
        else:
            return df.to_string()
    
    def _get_vrb_services_content(self) -> str:
        """Get VRB bank services content"""
        return """
# Dịch vụ Ngân hàng VRB

## Dịch vụ tài chính cá nhân

### 1. Tài khoản tiết kiệm
- **Lãi suất**: 6.5%/năm cho kỳ hạn 12 tháng
- **Số tiền gửi tối thiểu**: 100,000 VNĐ
- **Tính năng**: Rút tiền tự do, tính lãi theo ngày
- **Ưu đãi**: Miễn phí thẻ ATM năm đầu

### 2. Vay mua nhà
- **Lãi suất**: Từ 8.5%/năm
- **Thời hạn vay**: Tối đa 25 năm
- **Tỷ lệ cho vay**: Lên đến 80% giá trị tài sản
- **Hồ sơ**: CMND, sổ hộ khẩu, giấy tờ thu nhập

### 3. Thẻ tín dụng VRB
- **Loại thẻ**: Classic, Gold, Platinum, Diamond
- **Hạn mức**: Từ 10 triệu - 1 tỷ VNĐ
- **Ưu đãi**: Cashback 1-3%, miễn phí năm đầu
- **Đặc quyền**: Ưu đãi tại hơn 10,000 merchant

### 4. Chuyển tiền quốc tế
- **Phí chuyển**: Từ 50,000 VNĐ/giao dịch
- **Thời gian**: 1-3 ngày làm việc
- **Mạng lưới**: Hơn 200 quốc gia và vùng lãnh thổ

## Dịch vụ doanh nghiệp

### 1. Tài khoản doanh nghiệp
- **Phí duy trì**: 50,000 VNĐ/tháng
- **Giao dịch**: Miễn phí 100 giao dịch đầu tiên/tháng
- **Internet Banking**: Đầy đủ tính năng quản lý tài chính

### 2. Vay vốn kinh doanh
- **Lãi suất**: Từ 9.5%/năm (ưu đãi cho khách hàng VIP)
- **Hạn mức**: Từ 500 triệu - 100 tỷ VNĐ
- **Thời hạn**: Linh hoạt từ 6 tháng - 10 năm
- **Tài sản đảm bảo**: Linh hoạt theo nhu cầu

### 3. Bảo lãnh ngân hàng
- **Loại bảo lãnh**: Thầu, tạm ứng, bảo hành, thanh toán
- **Phí bảo lãnh**: Từ 0.1%/tháng
- **Thời gian xử lý**: 2-3 ngày làm việc
"""
    
    async def setup_company(self, company_key: str):
        """Setup single company - upload files and index to Qdrant"""
        company = self.companies[company_key]
        company_id = company["id"]
        
        print(f"\n🏢 Setting up {company['name']}...")
        print("=" * 60)
        
        try:
            # Step 1: Register company in Qdrant
            print(f"📋 Registering company: {company_id}")
            company_data = {
                'company_id': company_id,
                'company_name': company["name"],
                'industry': company["industry"].value,
                'description': f"{company['name']} - {company['industry'].value}",
                'languages': [Language.VIETNAMESE],
                'data_sources': {},
                'ai_config': {},
                'industry_config': {}
            }
            
            result = await self.data_manager.register_company(company_data)
            
            if result:
                print(f"✅ Company registered successfully")
            else:
                print(f"❌ Failed to register company")
                return False
            
            # Step 2: Upload files to R2 and process
            self.uploaded_files[company_id] = []
            
            for file_info in company["files"]:
                file_path = file_info["path"]
                
                if not os.path.exists(file_path):
                    print(f"❌ File not found: {file_path}")
                    continue
                
                print(f"\n📄 Processing: {file_path}")
                
                # Upload to R2
                public_url = await self.upload_file_to_r2(file_path, company_id)
                if not public_url:
                    continue
                
                self.uploaded_files[company_id].append({
                    "file": file_path,
                    "url": public_url,
                    "type": file_info["type"]
                })
                
                # Extract content
                print(f"🔍 Extracting content...")
                extraction_result = await self.extract_content_from_file(
                    file_info, 
                    public_url,
                    company["industry"].value
                )
                
                if extraction_result["success"]:
                    # Use the existing ingestion pipeline via Redis queue
                    print(f"📤 Enqueueing document for ingestion...")
                    
                    # Create ingestion task
                    task = IngestionTask(
                        task_id=str(uuid.uuid4()),
                        user_id=company_id,  # Use company_id as user_id for this test
                        document_id=str(uuid.uuid4()),
                        file_path=public_url.replace("https://agent8x.io.vn/", ""),  # Extract R2 key from URL
                        filename=os.path.basename(file_path),
                        file_type=self._get_content_type(file_path),
                        file_size=os.path.getsize(file_path),
                        upload_timestamp=datetime.now().isoformat(),
                        callback_url=None,  # No callback needed for test
                        additional_metadata={
                            "company_id": company_id,
                            "company_name": company["name"],
                            "industry": company["industry"].value,
                            "file_type": file_info["type"],
                            "data_type": file_info["data_type"],
                            **extraction_result["metadata"]
                        }
                    )
                    
                    # Connect to queue and enqueue task
                    await self.queue_manager.connect()
                    success = await self.queue_manager.enqueue_task(task)
                    
                    if success:
                        print(f"✅ Document queued for ingestion (Task ID: {task.task_id})")
                        print(f"   📋 Queue system will process: R2 → Text extraction → Chunking → Qdrant")
                        print(f"   ⚡ Processing will be handled by ingestion worker")
                    else:
                        print(f"❌ Failed to enqueue document for ingestion")
                        
                else:
                    print(f"❌ Failed to extract content: {extraction_result.get('error')}")
            
            print(f"\n✅ Setup completed for {company['name']}")
            return True
            
        except Exception as e:
            logger.error(f"Setup error for {company['name']}: {e}")
            print(f"❌ Setup failed: {e}")
            return False
    
    async def test_company_chat(self, company_key: str):
        """Test chat functionality for a company"""
        company = self.companies[company_key]
        company_id = company["id"]
        
        print(f"\n💬 Testing chat for {company['name']}")
        print("=" * 50)
        
        # Define test queries based on industry
        test_queries = {
            "golden-dragon": [
                "Xin chào, tôi muốn đặt bàn cho 4 người vào tối mai lúc 7 giờ",
                "Cho tôi xem menu món chay của nhà hàng",
                "Món nào là đặc sản của nhà hàng?",
                "Giá combo gia đình là bao nhiêu?"
            ],
            "ivy-fashion": [
                "Tôi cần tìm váy dự tiệc màu đỏ size M",
                "Có áo sơ mi nam đang sale không?",
                "Cho tôi xem các sản phẩm quần jeans",
                "Tôi muốn đặt 2 áo thun trắng size L"
            ],
            "vrb-bank": [
                "Tôi muốn vay mua nhà 2 tỷ, thu nhập 30 triệu/tháng có được không?",
                "Lãi suất tiết kiệm 12 tháng là bao nhiêu?",
                "Điều kiện mở thẻ tín dụng Platinum?",
                "Phí chuyển tiền quốc tế như thế nào?"
            ]
        }
        
        queries = test_queries.get(company_key, [])
        session_id = f"test-{company_key}-{int(datetime.now().timestamp())}"
        
        for i, query in enumerate(queries, 1):
            print(f"\n🙋 Query {i}: {query}")
            
            try:
                request = UnifiedChatRequest(
                    message=query,
                    company_id=company_id,
                    session_id=session_id,
                    industry=company["industry"],
                    language=Language.VIETNAMESE,
                    context={
                        "test_mode": True,
                        "disable_webhooks": True  # Disable webhooks for internal testing
                    }
                )
                
                response = await self.chat_service.process_message(request)
                
                print(f"🤖 AI: {response.response}")
                print(f"📋 Intent: {response.intent.value} (confidence: {response.confidence:.2f})")
                
                # Generate relevant codes based on intent
                if company_key == "golden-dragon" and "RESERVATION" in response.intent.value:
                    booking_code = f"GD{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:6].upper()}"
                    print(f"🎫 Mã đặt bàn: {booking_code}")
                    
                elif company_key == "ivy-fashion" and "ORDER" in response.intent.value:
                    order_code = f"IV{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:6].upper()}"
                    print(f"🛒 Mã đơn hàng: {order_code}")
                    
                elif company_key == "vrb-bank" and "vay" in query.lower():
                    assessment_code = f"VRB{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:8].upper()}"
                    print(f"📋 Mã thẩm định: {assessment_code}")
                    
            except Exception as e:
                logger.error(f"Chat test error: {e}")
                print(f"❌ Error: {e}")
    
    async def interactive_console(self):
        """Interactive console for testing"""
        print("\n🖥️ Interactive Test Console")
        print("=" * 60)
        print("Available companies:")
        for key, info in self.companies.items():
            print(f"  {key}: {info['name']}")
        
        print("\nCommands:")
        print("  setup <company_key>     - Setup company data")
        print("  test <company_key>      - Run automated tests")
        print("  chat <company_key>      - Start chat session")
        print("  list                    - List uploaded files")
        print("  quit                    - Exit")
        
        while True:
            try:
                command = input("\n> ").strip().lower()
                
                if command == "quit":
                    print("👋 Goodbye!")
                    break
                    
                elif command == "list":
                    print("\n📁 Uploaded Files:")
                    for company_id, files in self.uploaded_files.items():
                        print(f"\n{company_id}:")
                        for file_info in files:
                            print(f"  - {file_info['file']} → {file_info['url']}")
                            
                elif command.startswith("setup "):
                    company_key = command.split()[1]
                    if company_key in self.companies:
                        await self.setup_company(company_key)
                    else:
                        print(f"❌ Unknown company: {company_key}")
                        
                elif command.startswith("test "):
                    company_key = command.split()[1]
                    if company_key in self.companies:
                        await self.test_company_chat(company_key)
                    else:
                        print(f"❌ Unknown company: {company_key}")
                        
                elif command.startswith("chat "):
                    company_key = command.split()[1]
                    if company_key in self.companies:
                        await self.start_chat_session(company_key)
                    else:
                        print(f"❌ Unknown company: {company_key}")
                        
                else:
                    print("❌ Unknown command. Type 'quit' to exit.")
                    
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                logger.error(f"Console error: {e}")
                print(f"❌ Error: {e}")
    
    async def start_chat_session(self, company_key: str):
        """Start interactive chat session with a company"""
        company = self.companies[company_key]
        company_id = company["id"]
        session_id = f"chat-{company_key}-{int(datetime.now().timestamp())}"
        
        print(f"\n💬 Chat Session: {company['name']}")
        print("Type 'exit' to end chat")
        print("-" * 50)
        
        while True:
            try:
                user_input = input("\n👤 You: ").strip()
                
                if user_input.lower() == "exit":
                    print("Chat session ended.")
                    break
                
                request = UnifiedChatRequest(
                    message=user_input,
                    company_id=company_id,
                    session_id=session_id,
                    industry=company["industry"],
                    language=Language.VIETNAMESE,
                    context={
                        "test_mode": True,
                        "disable_webhooks": True
                    }
                )
                
                response = await self.chat_service.process_message(request)
                
                print(f"\n🤖 AI: {response.response}")
                print(f"[Intent: {response.intent.value}, Confidence: {response.confidence:.2f}]")
                
            except Exception as e:
                logger.error(f"Chat error: {e}")
                print(f"❌ Error: {e}")

async def main():
    """Main function"""
    print("🚀 AI Service Internal Test - No Backend Integration")
    print("=" * 60)
    
    tester = InternalAIServiceTest()
    
    # Option 1: Automated setup and test
    print("\n📋 Running automated setup and tests...")
    
    for company_key in tester.companies:
        success = await tester.setup_company(company_key)
        if success:
            await tester.test_company_chat(company_key)
    
    # Option 2: Interactive console
    print("\n" + "="*60)
    print("✅ Automated tests completed!")
    print("Starting interactive console...")
    
    await tester.interactive_console()

if __name__ == "__main__":
    asyncio.run(main())