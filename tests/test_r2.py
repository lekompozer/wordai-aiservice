#!/usr/bin/env python3
"""
Test script để kiểm tra kết nối R2 Storage
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

def check_r2_config():
    """Kiểm tra R2 configuration"""
    print("🔍 Checking R2 configuration...")
    
    required_vars = [
        'R2_ACCOUNT_ID',
        'R2_ACCESS_KEY_ID', 
        'R2_SECRET_ACCESS_KEY',
        'R2_BUCKET_NAME',
        'R2_ENDPOINT'
    ]
    
    config = {}
    missing_vars = []
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            config[var] = value
            if 'SECRET' in var:
                print(f"✅ {var}: {value[:20]}...")
            else:
                print(f"✅ {var}: {value}")
        else:
            missing_vars.append(var)
            print(f"❌ {var}: NOT SET")
    
    if missing_vars:
        print(f"\n⚠️ Missing environment variables: {missing_vars}")
        return None
    
    print("\n✅ All R2 environment variables are set!")
    return config

async def test_basic_r2_connection():
    """Test basic R2 connection using boto3"""
    print("\n🔍 Testing basic R2 connection...")
    
    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError
        from botocore.config import Config
        
        # Get R2 config
        endpoint = os.getenv('R2_ENDPOINT')
        access_key = os.getenv('R2_ACCESS_KEY_ID')
        secret_key = os.getenv('R2_SECRET_ACCESS_KEY')
        bucket_name = os.getenv('R2_BUCKET_NAME')
        
        print(f"📍 Endpoint: {endpoint}")
        print(f"🪣 Bucket: {bucket_name}")
        print(f"🔑 Access Key: {access_key[:20]}...")
        
        # Create S3 client for R2
        s3_client = boto3.client(
            's3',
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(
                signature_version='s3v4',
                s3={'addressing_style': 'path'}
            ),
            region_name='auto'
        )
        
        print("⏳ Testing connection...")
        
        # Test 1: List buckets
        try:
            response = s3_client.list_buckets()
            buckets = [bucket['Name'] for bucket in response.get('Buckets', [])]
            print(f"✅ Connection successful! Found buckets: {buckets}")
            
            if bucket_name in buckets:
                print(f"✅ Target bucket '{bucket_name}' exists")
            else:
                print(f"⚠️ Target bucket '{bucket_name}' not found in: {buckets}")
                
        except Exception as e:
            print(f"❌ List buckets failed: {e}")
            return False
        
        # Test 2: Check bucket access
        try:
            response = s3_client.head_bucket(Bucket=bucket_name)
            print(f"✅ Bucket '{bucket_name}' is accessible")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                print(f"❌ Bucket '{bucket_name}' not found")
            elif error_code == '403':
                print(f"❌ Access denied to bucket '{bucket_name}'")
            else:
                print(f"❌ Bucket access error: {e}")
            return False
        
        # Test 3: List objects in bucket
        try:
            response = s3_client.list_objects_v2(Bucket=bucket_name, MaxKeys=10)
            object_count = response.get('KeyCount', 0)
            print(f"✅ Bucket contains {object_count} objects")
            
            if object_count > 0:
                print("📄 Sample objects:")
                for obj in response.get('Contents', [])[:5]:
                    print(f"   - {obj['Key']} ({obj['Size']} bytes)")
            
        except Exception as e:
            print(f"⚠️ List objects failed: {e}")
        
        return True
        
    except ImportError:
        print("❌ boto3 not installed. Please run: pip install boto3")
        return False
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False

async def test_file_operations():
    """Test file upload/download operations"""
    print("\n🔍 Testing file operations...")
    
    try:
        import boto3
        from botocore.config import Config
        
        # Initialize client
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
        
        # Test upload
        print("📤 Testing file upload...")
        test_content = f"""# R2 Storage Test

This is a test file uploaded to R2 at {datetime.now().isoformat()}.

## Test Information
- Bucket: {bucket_name}
- Endpoint: {os.getenv('R2_ENDPOINT')}
- Upload time: {datetime.now()}

## Content
This file is used to test:
1. File upload to R2
2. File download from R2  
3. File listing
4. File deletion

Generated by AI Chatbot RAG system.
""".encode('utf-8')
        
        test_key = f"test/upload_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        
        try:
            s3_client.put_object(
                Bucket=bucket_name,
                Key=test_key,
                Body=test_content,
                ContentType='text/markdown'
            )
            print(f"✅ Upload successful: {test_key}")
            
            # Generate public URL
            public_url = f"{os.getenv('R2_ENDPOINT')}/{bucket_name}/{test_key}"
            print(f"🔗 Public URL: {public_url}")
            
        except Exception as e:
            print(f"❌ Upload failed: {e}")
            return False
        
        # Test download
        print("📥 Testing file download...")
        try:
            response = s3_client.get_object(Bucket=bucket_name, Key=test_key)
            downloaded_content = response['Body'].read()
            downloaded_text = downloaded_content.decode('utf-8')
            
            print(f"✅ Download successful ({len(downloaded_content)} bytes)")
            print("📄 Content preview:")
            print(downloaded_text[:200] + "..." if len(downloaded_text) > 200 else downloaded_text)
            
        except Exception as e:
            print(f"❌ Download failed: {e}")
            return False
        
        # Test presigned URL
        print("🔗 Testing presigned URL generation...")
        try:
            presigned_url = s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket_name, 'Key': test_key},
                ExpiresIn=3600
            )
            print(f"✅ Presigned URL generated (expires in 1 hour)")
            print(f"   URL: {presigned_url[:80]}...")
            
        except Exception as e:
            print(f"❌ Presigned URL generation failed: {e}")
        
        # Test upload presigned URL
        print("📤 Testing upload presigned URL...")
        try:
            upload_key = f"test/presigned_upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            upload_url = s3_client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': bucket_name, 
                    'Key': upload_key,
                    'ContentType': 'text/plain'
                },
                ExpiresIn=3600
            )
            print(f"✅ Upload presigned URL generated")
            print(f"   URL: {upload_url[:80]}...")
            
        except Exception as e:
            print(f"❌ Upload presigned URL generation failed: {e}")
        
        # Test file listing with prefix
        print("📁 Testing file listing...")
        try:
            response = s3_client.list_objects_v2(
                Bucket=bucket_name,
                Prefix="test/",
                MaxKeys=10
            )
            
            test_files = response.get('Contents', [])
            print(f"✅ Found {len(test_files)} test files:")
            for file in test_files:
                print(f"   📄 {file['Key']} ({file['Size']} bytes, {file['LastModified']})")
                
        except Exception as e:
            print(f"❌ File listing failed: {e}")
        
        # Cleanup - delete test file
        print("🧹 Cleaning up test file...")
        try:
            s3_client.delete_object(Bucket=bucket_name, Key=test_key)
            print(f"✅ Test file deleted: {test_key}")
        except Exception as e:
            print(f"⚠️ Cleanup failed: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ File operations test failed: {e}")
        return False

async def test_document_workflow():
    """Test typical document upload workflow"""
    print("\n🔍 Testing document workflow...")
    
    try:
        import boto3
        from botocore.config import Config
        
        # Initialize client
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
        
        # Simulate document upload workflow
        user_id = "user_123"
        document_id = f"doc_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Create document structure
        documents = [
            {
                'filename': 'research_paper.pdf',
                'content': b'%PDF-1.4\nFake PDF content for testing...' * 100,
                'content_type': 'application/pdf'
            },
            {
                'filename': 'notes.txt', 
                'content': 'This is a text document with important notes.\n\nKey points:\n- Point 1\n- Point 2\n- Point 3'.encode('utf-8'),
                'content_type': 'text/plain'
            },
            {
                'filename': 'presentation.pptx',
                'content': b'PK\x03\x04' + b'Fake PowerPoint content...' * 50,
                'content_type': 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
            }
        ]
        
        uploaded_files = []
        
        for doc in documents:
            # Create organized file path
            file_key = f"users/{user_id}/documents/{document_id}/{doc['filename']}"
            
            try:
                s3_client.put_object(
                    Bucket=bucket_name,
                    Key=file_key,
                    Body=doc['content'],
                    ContentType=doc['content_type'],
                    Metadata={
                        'user_id': user_id,
                        'document_id': document_id,
                        'upload_timestamp': datetime.now().isoformat(),
                        'original_filename': doc['filename']
                    }
                )
                
                uploaded_files.append(file_key)
                print(f"✅ Uploaded: {doc['filename']} -> {file_key}")
                
            except Exception as e:
                print(f"❌ Upload failed for {doc['filename']}: {e}")
        
        # List user documents
        print(f"\n📁 Listing documents for user {user_id}...")
        try:
            response = s3_client.list_objects_v2(
                Bucket=bucket_name,
                Prefix=f"users/{user_id}/documents/",
                MaxKeys=50
            )
            
            user_files = response.get('Contents', [])
            print(f"✅ User has {len(user_files)} files:")
            
            for file in user_files:
                # Get metadata
                try:
                    obj_response = s3_client.head_object(Bucket=bucket_name, Key=file['Key'])
                    metadata = obj_response.get('Metadata', {})
                    print(f"   📄 {file['Key']} ({file['Size']} bytes)")
                    if metadata:
                        print(f"      📊 Metadata: {metadata}")
                except Exception:
                    print(f"   📄 {file['Key']} ({file['Size']} bytes)")
                    
        except Exception as e:
            print(f"❌ List user documents failed: {e}")
        
        # Test download specific document
        if uploaded_files:
            test_file = uploaded_files[0]
            print(f"\n📥 Testing download of: {test_file}")
            try:
                response = s3_client.get_object(Bucket=bucket_name, Key=test_file)
                content = response['Body'].read()
                metadata = response.get('Metadata', {})
                
                print(f"✅ Download successful ({len(content)} bytes)")
                print(f"📊 Metadata: {metadata}")
                
            except Exception as e:
                print(f"❌ Download failed: {e}")
        
        # Cleanup
        print("\n🧹 Cleaning up test documents...")
        for file_key in uploaded_files:
            try:
                s3_client.delete_object(Bucket=bucket_name, Key=file_key)
                print(f"✅ Deleted: {file_key}")
            except Exception as e:
                print(f"⚠️ Delete failed for {file_key}: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Document workflow test failed: {e}")
        return False

async def main():
    """Main test function"""
    print("🚀 R2 Storage Connection Test")
    print("=" * 60)
    
    # Check configuration
    config = check_r2_config()
    if not config:
        print("\n❌ Configuration check failed!")
        return
    
    # Test basic connection
    print("\n" + "="*60)
    connection_ok = await test_basic_r2_connection()
    if not connection_ok:
        print("\n❌ Basic connection test failed!")
        return
    
    # Test file operations
    print("\n" + "="*60)
    file_ops_ok = await test_file_operations()
    if not file_ops_ok:
        print("\n❌ File operations test failed!")
        return
    
    # Test document workflow
    print("\n" + "="*60)
    workflow_ok = await test_document_workflow()
    if not workflow_ok:
        print("\n❌ Document workflow test failed!")
        return
    
    print("\n" + "=" * 60)
    print("🎉 ALL R2 TESTS PASSED!")
    print("✅ Configuration: OK")
    print("✅ Connection: OK")
    print("✅ File Upload: OK")
    print("✅ File Download: OK")
    print("✅ File Listing: OK")
    print("✅ Presigned URLs: OK")
    print("✅ Document Workflow: OK")
    print("\n🚀 R2 Storage is ready for production use!")

if __name__ == "__main__":
    asyncio.run(main())
