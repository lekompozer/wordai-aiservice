#!/usr/bin/env python3
"""
Upload test file to R2 for document processing testing
"""

import os
import asyncio
import logging
from datetime import datetime
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv('development.env')
    logger.info("✅ Loaded development.env")
except ImportError:
    logger.warning("⚠️ python-dotenv not installed")

async def upload_english_file():
    """Upload English grammar file to R2"""
    try:
        import boto3
        from botocore.config import Config
        
        # Read the English file
        english_file_path = Path("test-english-present-simple.txt")
        if not english_file_path.exists():
            print(f"❌ File not found: {english_file_path}")
            return None
        
        with open(english_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"📄 File content length: {len(content)} characters")
        print(f"📄 First 200 chars: {content[:200]}...")
        
        # Initialize S3 client for R2
        s3_client = boto3.client(
            's3',
            endpoint_url=os.getenv('R2_ENDPOINT'),
            aws_access_key_id=os.getenv('R2_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('R2_SECRET_ACCESS_KEY'),
            config=Config(
                signature_version='s3v4',
                s3={'addressing_style': 'path'}
            ),
            region_name='auto'
        )
        
        bucket_name = os.getenv('R2_BUCKET_NAME')
        
        # Create organized file path for testing
        user_id = "test_user_001"
        document_id = f"english_grammar_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        file_key = f"documents/{document_id}/english-present-simple.txt"
        
        print(f"📤 Uploading to R2...")
        print(f"   Bucket: {bucket_name}")
        print(f"   Key: {file_key}")
        
        # Upload to R2
        s3_client.put_object(
            Bucket=bucket_name,
            Key=file_key,
            Body=content.encode('utf-8'),
            ContentType='text/plain',
            Metadata={
                'user_id': user_id,
                'document_id': document_id,
                'upload_timestamp': datetime.now().isoformat(),
                'original_filename': 'english-present-simple.txt',
                'file_type': 'txt',
                'purpose': 'api_testing'
            }
        )
        
        print(f"✅ Upload successful!")
        print(f"📁 R2 Key: {file_key}")
        
        # Verify upload
        response = s3_client.head_object(Bucket=bucket_name, Key=file_key)
        file_size = response['ContentLength']
        print(f"✅ File verified: {file_size} bytes")
        
        return {
            'r2_key': file_key,
            'document_id': document_id,
            'user_id': user_id,
            'file_name': 'english-present-simple.txt',
            'content_type': 'text/plain',
            'file_size': file_size
        }
        
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return None

async def main():
    """Main function"""
    print("🚀 Uploading English Grammar File to R2")
    print("=" * 60)
    
    # Upload file
    result = await upload_english_file()
    if result:
        print("\n✅ File uploaded successfully!")
        print("📋 Upload details:")
        for key, value in result.items():
            print(f"   {key}: {value}")
        
        print("\n🧪 Ready for API testing with:")
        print(f"   Document ID: {result['document_id']}")
        print(f"   User ID: {result['user_id']}")
        print(f"   R2 Key: {result['r2_key']}")
        print(f"   File Name: {result['file_name']}")
        print(f"   Content Type: {result['content_type']}")
        
        # Return test command
        print("\n🚀 Test command:")
        print(f"""curl -X POST http://localhost:8000/api/documents/process \\
  -H "Content-Type: application/json" \\
  -d '{{
    "document_id": "{result['document_id']}",
    "user_id": "{result['user_id']}",
    "r2_key": "{result['r2_key']}",
    "file_name": "{result['file_name']}",
    "content_type": "{result['content_type']}",
    "callback_url": "http://localhost:3000/api/documents/callback"
  }}'""")
        
        return result
    else:
        print("\n❌ Upload failed!")
        return None

if __name__ == "__main__":
    result = asyncio.run(main())
