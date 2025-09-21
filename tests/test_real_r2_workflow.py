"""
Real R2 Upload Test for Admin Workflow
Tests actual R2 upload functionality with credentials from .env
"""

import asyncio
import os
import tempfile
import csv
from datetime import datetime
from pathlib import Path
import httpx
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config

# Load environment variables
from dotenv import load_dotenv

load_dotenv()

# R2 Configuration from .env
R2_CONFIG = {
    "access_key_id": os.getenv("R2_ACCESS_KEY_ID"),
    "secret_access_key": os.getenv("R2_SECRET_ACCESS_KEY"),
    "endpoint_url": os.getenv("R2_ENDPOINT"),
    "bucket_name": os.getenv("R2_BUCKET_NAME"),
    "public_url": os.getenv("R2_PUBLIC_URL"),
    "region": os.getenv("R2_REGION", "auto"),
}

# API Configuration
API_BASE_URL = "http://localhost:8000"
API_KEY = os.getenv("INTERNAL_API_KEY", "agent8x-backend-secret-key-2025")

HEADERS = {
    "X-API-Key": API_KEY,
    "X-API-Version": "1.0",
    "Content-Type": "application/json",
}

# Test Company
TEST_COMPANY = {
    "company_id": "real-test-company-2025",
    "company_name": "Real Test Company",
    "industry": "restaurant",
}


class R2FileUploader:
    """Real R2 file uploader using credentials from .env"""

    def __init__(self):
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=R2_CONFIG["endpoint_url"],
            aws_access_key_id=R2_CONFIG["access_key_id"],
            aws_secret_access_key=R2_CONFIG["secret_access_key"],
            region_name=R2_CONFIG["region"],
            config=Config(signature_version="s3v4"),
        )
        self.bucket_name = R2_CONFIG["bucket_name"]
        self.public_url = R2_CONFIG["public_url"]

    async def upload_file(self, file_path: str, company_id: str, file_type: str) -> str:
        """Upload file to R2 and return public URL"""
        try:
            file_name = Path(file_path).name
            timestamp = int(datetime.now().timestamp())

            # Create R2 key path - simplified structure
            r2_key = f"companies/{company_id}/{timestamp}_{file_name}"

            print(f"📤 Uploading to R2: {file_name}")
            print(f"   Key: {r2_key}")
            print(f"   Bucket: {self.bucket_name}")

            # Upload file
            with open(file_path, "rb") as file_data:
                self.s3_client.upload_fileobj(
                    file_data,
                    self.bucket_name,
                    r2_key,
                    ExtraArgs={
                        "ContentType": self._get_content_type(file_path),
                        "ACL": "public-read",  # Make file publicly accessible
                    },
                )

            # Generate public URL
            public_url = f"{self.public_url}/{r2_key}"
            print(f"✅ Upload successful: {public_url}")

            return public_url

        except ClientError as e:
            print(f"❌ R2 upload failed: {e}")
            raise
        except Exception as e:
            print(f"❌ Upload error: {e}")
            raise

    def _get_content_type(self, file_path: str) -> str:
        """Determine content type based on file extension"""
        ext = Path(file_path).suffix.lower()
        content_types = {
            ".txt": "text/plain",
            ".csv": "text/csv",
            ".json": "application/json",
            ".pdf": "application/pdf",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
        }
        return content_types.get(ext, "application/octet-stream")


class RealAdminWorkflowTester:
    """Test admin workflow with real R2 uploads"""

    def __init__(self):
        # Increase timeout for AI processing
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(300.0, read=300.0))
        self.r2_uploader = R2FileUploader()
        self.company_id = TEST_COMPANY["company_id"]
        self.uploaded_files = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    def create_test_content(self):
        """Create test files with real content"""
        temp_dir = Path(tempfile.gettempdir()) / "real_admin_test"
        temp_dir.mkdir(exist_ok=True)

        # 1. Company information TXT
        company_content = """
PHỞ VIỆT RESTAURANT - THÔNG TIN CÔNG TY

Giới Thiệu:
Phở Việt Restaurant là chuỗi nhà hàng chuyên phục vụ món phở truyền thống Việt Nam,
được thành lập từ năm 2020 với sứ mệnh mang hương vị phở chính gốc đến với thực khách.

Thông Tin Liên Hệ:
- Địa chỉ: 456 Lê Lợi, Quận 3, TP.HCM
- Hotline: 028-3933-5678
- Email: info@pho-viet.com.vn
- Website: www.pho-viet.com.vn

Giờ Hoạt Động:
- Thứ 2 - Chủ nhật: 06:00 - 23:00
- Phục vụ breakfast, lunch, dinner

Chính Sách:
- Cam kết sử dụng nguyên liệu tươi sạch
- Nước dùng được nấu trong 12 giờ
- Thịt bò nhập khẩu từ Úc
- Bánh phở làm thủ công hàng ngày

Dịch Vụ:
- Dine-in (tại chỗ)
- Takeaway (mang về)  
- Delivery (giao hàng)
- Catering (tiệc ngoài)
"""

        txt_file = temp_dir / "company_info.txt"
        with open(txt_file, "w", encoding="utf-8") as f:
            f.write(company_content)

        # 2. Products CSV
        csv_file = temp_dir / "pho_menu.csv"
        with open(csv_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Tên Món", "Giá (VND)", "Mô Tả", "Danh Mục", "Có Sẵn"])

            menu_items = [
                ["Phở Tái", "65000", "Phở với thịt bò tái", "Phở Bò", "Có"],
                ["Phở Chín", "65000", "Phở với thịt bò chín", "Phở Bò", "Có"],
                [
                    "Phở Đặc Biệt",
                    "85000",
                    "Phở với tái, chín, gầu, gân",
                    "Phở Bò",
                    "Có",
                ],
                ["Phở Gà", "60000", "Phở gà truyền thống", "Phở Gà", "Có"],
                ["Phở Gà Nấm", "70000", "Phở gà với nấm hương", "Phở Gà", "Có"],
                ["Bánh Mì Pate", "25000", "Bánh mì với pate gan", "Bánh Mì", "Có"],
                [
                    "Bánh Mì Thịt Nướng",
                    "30000",
                    "Bánh mì với thịt nướng",
                    "Bánh Mì",
                    "Có",
                ],
                ["Cà Phê Đen", "20000", "Cà phê đen truyền thống", "Đồ Uống", "Có"],
                ["Cà Phê Sữa", "25000", "Cà phê sữa đá", "Đồ Uống", "Có"],
                ["Trà Đá", "10000", "Trà đá miễn phí", "Đồ Uống", "Có"],
            ]

            for item in menu_items:
                writer.writerow(item)

        return {"company_txt": str(txt_file), "products_csv": str(csv_file)}

    async def test_company_registration(self):
        """Test company registration"""
        print("\n🏢 Testing Company Registration...")

        try:
            response = await self.client.post(
                f"{API_BASE_URL}/api/admin/companies/register",
                headers=HEADERS,
                json=TEST_COMPANY,
            )

            if response.status_code == 200:
                result = response.json()
                print(f"✅ Company registered: {result.get('company_id')}")
                return True
            else:
                print(f"❌ Registration failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False

        except Exception as e:
            print(f"❌ Registration error: {e}")
            return False

    async def test_real_file_upload(
        self, file_path: str, data_type: str, description: str
    ):
        """Test file upload with real R2 upload"""
        print(f"\n📄 Testing Real File Upload ({data_type})...")

        try:
            # Step 1: Upload to R2
            print("1. Uploading file to R2...")
            r2_url = await self.r2_uploader.upload_file(
                file_path, self.company_id, data_type
            )

            # Step 2: Call AI Service
            print("2. Processing with AI Service...")
            file_metadata = {
                "original_name": Path(file_path).name,
                "file_id": f"real_{data_type}_{int(datetime.now().timestamp())}",
                "file_name": Path(file_path).name,
                "file_size": Path(file_path).stat().st_size,
                "file_type": self.r2_uploader._get_content_type(file_path),
                "uploaded_by": "real_test_user",
                "description": description,
                "tags": ["real_test", data_type, "r2_upload"],
            }

            upload_request = {
                "r2_url": r2_url,
                "data_type": data_type,
                "industry": "restaurant",
                "metadata": file_metadata,
                "upload_to_qdrant": True,
            }

            response = await self.client.post(
                f"{API_BASE_URL}/api/admin/companies/{self.company_id}/files/upload",
                headers=HEADERS,
                json=upload_request,
            )

            if response.status_code == 200:
                result = response.json()
                print(f"✅ File processed successfully:")
                print(f"   File ID: {result.get('file_id')}")
                print(f"   AI Provider: {result.get('ai_provider')}")
                print(f"   Status: {result.get('processing_status')}")
                print(f"   R2 URL: {r2_url}")

                self.uploaded_files.append(
                    {
                        "file_id": result.get("file_id"),
                        "r2_url": r2_url,
                        "type": data_type,
                    }
                )

                return True
            else:
                print(f"❌ AI processing failed: {response.status_code}")
                try:
                    error_details = response.json()
                    print(f"   Response: {error_details}")
                except:
                    print(f"   Response: {response.text}")
                return False

        except Exception as e:
            print(f"❌ File upload error: {str(e)}")
            print(f"   Error type: {type(e).__name__}")
            import traceback

            print(f"   Traceback: {traceback.format_exc()}")
            return False

    async def test_products_extraction(self, csv_file_path: str):
        """Test products extraction with real CSV file"""
        print(f"\n🍽️ Testing Real Products Extraction...")

        try:
            # Upload CSV to R2
            print("1. Uploading CSV to R2...")
            r2_url = await self.r2_uploader.upload_file(
                csv_file_path, self.company_id, "products"
            )

            # Call extraction endpoint
            print("2. Extracting products with AI...")
            extraction_request = {
                "r2_url": r2_url,
                "company_id": self.company_id,
                "industry": "restaurant",
                "target_categories": ["products"],
                "file_metadata": {
                    "original_name": Path(csv_file_path).name,
                    "file_size": Path(csv_file_path).stat().st_size,
                    "file_type": "text/csv",
                    "uploaded_at": datetime.now().isoformat(),
                    "file_id": f"real_products_{int(datetime.now().timestamp())}",
                },
                "company_info": {
                    "id": self.company_id,
                    "name": TEST_COMPANY["company_name"],
                    "industry": "restaurant",
                },
                "language": "vi",
                "upload_to_qdrant": True,
            }

            response = await self.client.post(
                f"{API_BASE_URL}/api/admin/companies/{self.company_id}/extract",
                headers=HEADERS,
                json=extraction_request,
            )

            if response.status_code == 200:
                result = response.json()
                print(f"✅ Products extraction completed:")
                print(f"   Success: {result.get('success')}")
                print(f"   AI Provider: {result.get('ai_provider')}")
                print(f"   Items Extracted: {result.get('total_items_extracted', 0)}")

                structured_data = result.get("structured_data", {})
                products = structured_data.get("products", [])

                print(f"   📦 Products found: {len(products)}")

                if products:
                    print(
                        f"   Sample: {products[0].get('name', 'N/A')} - {products[0].get('price', 'N/A')}"
                    )

                return True
            else:
                print(f"❌ Extraction failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False

        except Exception as e:
            print(f"❌ Extraction error: {e}")
            return False

    async def test_search_functionality(self):
        """Test search and retrieval"""
        print(f"\n🔍 Testing Search Functionality...")

        # Wait for background processing - increased for R2→AI→Qdrant pipeline
        print("⏳ Waiting for Qdrant processing...")
        print("   📤 R2 Upload → 🤖 AI Extraction → 📊 Qdrant Ingestion")
        print("   ⏱️ This process takes 2-3 minutes total...")

        for i in range(18):  # 18 x 10 seconds = 3 minutes
            await asyncio.sleep(10)
            print(f"   ⏱️ Waiting... {(i+1)*10}s / 180s")

        print("✅ Background processing wait completed")

        try:
            # Get company info (includes search stats)
            response = await self.client.get(
                f"{API_BASE_URL}/api/admin/companies/{self.company_id}", headers=HEADERS
            )

            if response.status_code == 200:
                result = response.json()
                print(f"📋 Full response: {result}")  # Debug: print full response

                company_data = result.get("data", {})
                print(
                    f"📋 Company data keys: {list(company_data.keys())}"
                )  # Debug: print available keys

                print(f"✅ Company data accessible:")
                print(f"   Company ID: {company_data.get('company_id', 'N/A')}")
                print(f"   Company Name: {company_data.get('company_name', 'N/A')}")
                print(f"   Industry: {company_data.get('industry', 'N/A')}")
                print(f"   Collection: {company_data.get('collection_name', 'N/A')}")
                print(f"   Vector Count: {company_data.get('vector_count', 0)}")

                # Try to get products
                products_response = await self.client.get(
                    f"{API_BASE_URL}/api/admin/companies/{self.company_id}/products",
                    headers=HEADERS,
                )

                if products_response.status_code == 200:
                    products_result = products_response.json()
                    products = products_result.get("data", [])
                    print(f"   📦 Products in database: {len(products)}")

                    if products:
                        print(f"   Sample products:")
                        for i, product in enumerate(products[:3]):  # Show first 3
                            name = product.get("name", "N/A")
                            price = product.get("price", "N/A")
                            category = product.get("category", "N/A")
                            description = product.get("description", "N/A")
                            print(f"      {i+1}. {name} - {price} VND")
                            print(f"         Category: {category}")
                            print(f"         Description: {description[:50]}...")
                    else:
                        print(f"   ⚠️ No products found in database")

                        # DEBUG: Try to get ALL data from collection to see what's actually stored
                        print(f"   🔍 DEBUG: Checking all data in collection...")
                        try:
                            from qdrant_client import QdrantClient
                            import os

                            qdrant_client = QdrantClient(
                                url=os.getenv("QDRANT_URL"),
                                api_key=os.getenv("QDRANT_API_KEY"),
                            )

                            collection_name = (
                                f"restaurant_{self.company_id.replace('-', '_')}"
                            )
                            print(f"   🔍 Checking collection: {collection_name}")

                            # Get all points in collection
                            scroll_result = qdrant_client.scroll(
                                collection_name=collection_name,
                                limit=20,
                                with_payload=True,
                            )

                            if scroll_result and len(scroll_result) > 0:
                                points = scroll_result[0]
                                print(
                                    f"   📊 Total points in collection: {len(points)}"
                                )

                                for i, point in enumerate(points[:5]):  # Show first 5
                                    payload = (
                                        point.payload
                                        if hasattr(point, "payload")
                                        else {}
                                    )
                                    content_type = payload.get("content_type", "N/A")
                                    company_id = payload.get("company_id", "N/A")
                                    print(
                                        f"      Point {i+1}: content_type='{content_type}', company_id='{company_id}'"
                                    )
                                    print(
                                        f"                Payload keys: {list(payload.keys())}"
                                    )
                            else:
                                print(f"   ❌ No points found in collection at all!")

                        except Exception as debug_error:
                            print(f"   ❌ Debug error: {debug_error}")

                return True
            else:
                print(f"❌ Search failed: {response.status_code}")
                return False

        except Exception as e:
            print(f"❌ Search error: {e}")
            return False

    async def cleanup(self):
        """Clean up test data"""
        print(f"\n🧹 Cleaning up test data...")

        try:
            # Delete company (this should clean up all associated data)
            response = await self.client.delete(
                f"{API_BASE_URL}/api/admin/companies/{self.company_id}", headers=HEADERS
            )

            if response.status_code == 200:
                print("✅ Test company deleted successfully")

                # Note: In production, you might want to also clean up R2 files
                # For test purposes, we'll leave them as they'll be in a test folder
                print(f"📁 R2 files left in: companies/{self.company_id}/")

                return True
            else:
                print(f"❌ Cleanup failed: {response.status_code}")
                return False

        except Exception as e:
            print(f"❌ Cleanup error: {e}")
            return False

    async def run_real_workflow_test(self):
        """Run complete workflow test with real R2 uploads"""
        print("🚀 Real Admin Workflow Test with R2 Upload")
        print("=" * 60)
        print(f"API: {API_BASE_URL}")
        print(f"R2 Bucket: {R2_CONFIG['bucket_name']}")
        print(f"R2 Endpoint: {R2_CONFIG['endpoint_url']}")
        print(f"Company: {self.company_id}")
        print("=" * 60)

        # Create test files
        test_files = self.create_test_content()
        print(f"\n📁 Test files created:")
        for name, path in test_files.items():
            print(f"   {name}: {Path(path).name}")

        # Run workflow
        steps = [
            ("Company Registration", self.test_company_registration),
            (
                "Company Info Upload",
                lambda: self.test_real_file_upload(
                    test_files["company_txt"], "document", "Company information"
                ),
            ),
            (
                "Products CSV Upload",
                lambda: self.test_products_extraction(test_files["products_csv"]),
            ),
            ("Search & Retrieval", self.test_search_functionality),
            ("Cleanup", self.cleanup),
        ]

        results = {}
        for step_name, step_func in steps:
            print(f"\n{'='*20} {step_name} {'='*20}")

            try:
                success = await step_func()
                results[step_name] = success

                if not success:
                    print(f"❌ {step_name} failed!")
                    break

            except Exception as e:
                print(f"❌ {step_name} error: {e}")
                results[step_name] = False
                break

        # Print results
        print("\n" + "=" * 60)
        print("🎯 REAL WORKFLOW TEST RESULTS")
        print("=" * 60)

        for step, success in results.items():
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"{step:<25} {status}")

        passed = sum(results.values())
        total = len(results)

        print(f"\nResult: {passed}/{total} steps completed successfully")

        if passed == total:
            print("🎉 ALL TESTS PASSED! Real R2 workflow working correctly!")
        else:
            print("⚠️ Some tests failed. Check logs above.")

        # Cleanup temp files
        import shutil

        temp_dir = Path(tempfile.gettempdir()) / "real_admin_test"
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
            print(f"🗑️ Local test files cleaned: {temp_dir}")


async def main():
    """Main test runner"""
    # Verify R2 configuration
    missing_config = [k for k, v in R2_CONFIG.items() if not v]
    if missing_config:
        print(f"❌ Missing R2 configuration: {missing_config}")
        print("Please check your .env file")
        return

    print("✅ R2 configuration verified")

    async with RealAdminWorkflowTester() as tester:
        await tester.run_real_workflow_test()


if __name__ == "__main__":
    asyncio.run(main())
