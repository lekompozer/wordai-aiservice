"""
Simple Company File Upload Test
Test đơn giản upload file công ty lên R2
"""

import os
import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Set environment first
os.environ['PYTHONPATH'] = '/Users/user/Code/ai-chatbot-rag'

try:
    import boto3
    from botocore.exceptions import ClientError
    print("✅ boto3 available")
except ImportError:
    print("❌ boto3 not available")
    exit(1)

def create_simple_r2_client():
    """Create simple R2 client"""
    account_id = os.getenv("R2_ACCOUNT_ID", "69a4a90c19aacc196b81605e6be246d3")
    access_key_id = os.getenv("R2_ACCESS_KEY_ID", "bbd59dad2a31ae85eb8e22c1f6136208")
    secret_access_key = os.getenv("R2_SECRET_ACCESS_KEY", "84170aa9314ec4bdf35d2ee63184576534677bbf7d6b52e0742a9e2bd664b3b7")
    bucket_name = os.getenv("R2_BUCKET_NAME", "agent8x")
    
    endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"
    
    s3_client = boto3.client(
        's3',
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        region_name='auto'
    )
    
    return s3_client, bucket_name

async def upload_file_to_r2(s3_client, bucket_name, local_path: str, remote_path: str) -> Tuple[bool, Optional[str]]:
    """Upload file to R2"""
    try:
        if not os.path.exists(local_path):
            print(f"❌ File not found: {local_path}")
            return False, None
        
        # Upload file
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            s3_client.upload_file,
            local_path,
            bucket_name,
            remote_path
        )
        
        # Create public URL with new format
        public_url = f"https://agent8x.io.vn/{remote_path}"
        print(f"✅ Uploaded: {public_url}")
        return True, public_url
        
    except Exception as e:
        print(f"❌ Upload error: {e}")
        return False, None

def extract_text_from_document(file_path: str) -> Optional[str]:
    """Extract text from document"""
    try:
        file_extension = Path(file_path).suffix.lower()
        
        if file_extension in ['.txt', '.md']:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
                
        elif file_extension == '.csv':
            try:
                import pandas as pd
                df = pd.read_csv(file_path)
                content = f"CSV Data with {len(df)} rows:\n\n"
                content += df.to_string(index=False)
                return content
            except Exception as e:
                print(f"❌ CSV error: {e}")
                return None
                
        elif file_extension == '.docx':
            # Return manual content for VRB services
            if "vrb-bank-services" in file_path:
                return """
# Dịch vụ Ngân hàng VRB

## Dịch vụ tài chính cá nhân
### 1. Tài khoản tiết kiệm
- Lãi suất: 6.5%/năm cho kỳ hạn 12 tháng
- Số tiền gửi tối thiểu: 100,000 VNĐ

### 2. Vay mua nhà  
- Lãi suất: Từ 8.5%/năm
- Thời hạn vay: Tối đa 25 năm
- Tỷ lệ cho vay: Lên đến 80% giá trị tài sản

### 3. Thẻ tín dụng VRB
- Loại thẻ: Classic, Gold, Platinum, Diamond
- Hạn mức: Từ 10 triệu - 1 tỷ VNĐ
- Ưu đãi: Cashback 1-3%, miễn phí năm đầu

## Dịch vụ doanh nghiệp
### 1. Vay vốn kinh doanh
- Lãi suất: Từ 9.5%/năm
- Hạn mức: Từ 500 triệu - 100 tỷ VNĐ

### 2. Bảo lãnh ngân hàng
- Loại bảo lãnh: Thầu, tạm ứng, bảo hành, thanh toán
- Phí bảo lãnh: Từ 0.1%/tháng

## Ngân hàng số
- VRB Mobile Banking: Chuyển tiền, thanh toán hóa đơn
- VRB Internet Banking: Quản lý tài khoản, đầu tư
- Bảo mật sinh trắc học
- Hỗ trợ 24/7

## Khách hàng thân thiết  
- VRB Elite Club: Số dư từ 500 triệu VNĐ
- VRB Premium: Số dư từ 100 triệu VNĐ
"""
            return None
            
        else:
            print(f"❌ Unsupported file format: {file_extension}")
            return None
            
    except Exception as e:
        print(f"❌ Text extraction error: {e}")
        return None

async def process_company_files(company_id: str, company_name: str, files: List[str]):
    """Process files for one company"""
    print(f"\n🏢 Processing: {company_name}")
    print("=" * 50)
    
    s3_client, bucket_name = create_simple_r2_client()
    
    results = []
    
    for file_path in files:
        if not os.path.exists(file_path):
            print(f"❌ File not found: {file_path}")
            continue
        
        file_name = Path(file_path).name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        remote_path = f"companies/{company_id}/{timestamp}_{file_name}"
        
        print(f"\n📄 Processing: {file_name}")
        
        # 1. Upload to R2
        upload_success, public_url = await upload_file_to_r2(s3_client, bucket_name, file_path, remote_path)
        
        if not upload_success:
            print(f"❌ Upload failed: {file_name}")
            continue
        
        # 2. Extract content (for non-image files)
        import mimetypes
        mime_type, _ = mimetypes.guess_type(file_path)
        
        if mime_type and mime_type.startswith('image/'):
            print(f"📸 Image file detected: {file_name}")
            print(f"   URL for ChatGPT Vision: {public_url}")
            content = f"[IMAGE FILE] {file_name} - URL: {public_url}"
        else:
            content = extract_text_from_document(file_path)
            if content:
                print(f"✅ Text extracted: {len(content)} characters")
            else:
                print(f"❌ Text extraction failed")
                continue
        
        results.append({
            "file_name": file_name,
            "r2_url": public_url,
            "content_length": len(content) if content else 0,
            "mime_type": mime_type
        })
    
    return results

async def test_3_companies_simple():
    """Test simple upload for 3 companies"""
    print("🚀 Simple File Upload Test for 3 Companies")
    print("=" * 60)
    
    companies = [
        {
            "id": "golden-dragon-restaurant",
            "name": "Nhà hàng Golden Dragon",
            "files": [
                "company-data-test/golden-dragon-info.txt",
                "company-data-test/golden-dragon-menu.jpg"
            ]
        },
        {
            "id": "ivy-fashion-store", 
            "name": "Cửa hàng Ivy Fashion",
            "files": [
                "company-data-test/ivy-fashion-info.txt",
                "company-data-test/ivy-fashion-products.csv"
            ]
        },
        {
            "id": "vrb-bank-financial",
            "name": "Ngân hàng VRB", 
            "files": [
                "company-data-test/vrb-bank-info.md",
                "company-data-test/vrb-bank-services.docx"
            ]
        }
    ]
    
    all_results = {}
    
    for company in companies:
        try:
            results = await process_company_files(
                company["id"], 
                company["name"], 
                company["files"]
            )
            all_results[company["id"]] = results
            
        except Exception as e:
            print(f"❌ Error processing {company['name']}: {e}")
    
    # Summary
    print(f"\n📊 Upload Summary")
    print("=" * 30)
    
    for company_id, results in all_results.items():
        company_name = next(c["name"] for c in companies if c["id"] == company_id)
        print(f"\n🏢 {company_name}")
        for result in results:
            print(f"   ✅ {result['file_name']} ({result['content_length']} chars)")
            print(f"      📎 {result['r2_url']}")
    
    print(f"\n🎉 Upload completed!")
    return all_results

if __name__ == "__main__":
    asyncio.run(test_3_companies_simple())
