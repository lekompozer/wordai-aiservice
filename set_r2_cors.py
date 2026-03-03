"""
Set CORS policy on R2 bucket to allow wordai.pro to fetch PDFs/images directly.
Run: docker exec ai-chatbot-rag python3 /app/set_r2_cors.py
"""

import os
import sys
import boto3
from botocore.client import Config

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

s3_client = boto3.client(
    "s3",
    endpoint_url=os.getenv("R2_ENDPOINT"),
    aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
    config=Config(signature_version="s3v4"),
    region_name="auto",
)

bucket = os.getenv("R2_BUCKET_NAME", "wordai-documents")

cors_config = {
    "CORSRules": [
        {
            "AllowedHeaders": ["*"],
            "AllowedMethods": ["GET", "HEAD"],
            "AllowedOrigins": [
                "https://wordai.pro",
                "https://www.wordai.pro",
                "https://ai.wordai.pro",
                "http://localhost:3000",
                "http://localhost:3001",
                "http://localhost:5173",
            ],
            "ExposeHeaders": ["ETag", "Content-Length", "Content-Type"],
            "MaxAgeSeconds": 86400,
        }
    ]
}

print(f"Setting CORS on bucket: {bucket}")
print(f"Endpoint: {os.getenv('R2_ENDPOINT')}")

try:
    s3_client.put_bucket_cors(Bucket=bucket, CORSConfiguration=cors_config)
    print("✅ CORS policy set successfully!")

    # Verify
    result = s3_client.get_bucket_cors(Bucket=bucket)
    print("\n📋 Current CORS config:")
    for rule in result["CORSRules"]:
        print(f"  Origins: {rule['AllowedOrigins']}")
        print(f"  Methods: {rule['AllowedMethods']}")
except Exception as e:
    print(f"❌ Failed: {e}")
