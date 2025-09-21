"""
Cloudflare R2 Storage Configuration for AIVungtau Quotes System
Cấu hình để upload và quản lý files trên R2 bucket riêng cho AIVungtau
"""

import os
import boto3
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import uuid
from src.utils.logger import setup_logger

logger = setup_logger()


class AIVungtauR2StorageConfig:
    """Configuration for AIVungtau R2 Storage (Quotes System)"""

    def __init__(self):
        # AIVungtau R2 configuration from environment variables
        self.access_key_id = os.getenv("AIVUNGTAU_R2_ACCESS_KEY_ID")
        self.secret_access_key = os.getenv("AIVUNGTAU_R2_SECRET_ACCESS_KEY")
        self.bucket_name = os.getenv("AIVUNGTAU_R2_BUCKET_NAME", "aivungtau")
        self.endpoint_url = os.getenv(
            "AIVUNGTAU_R2_ENDPOINT",
            "https://69a4a90c19aacc196b81605e6be246d3.r2.cloudflarestorage.com",
        )
        self.public_url = os.getenv(
            "AIVUNGTAU_R2_PUBLIC_URL",
            "https://pub-aabd4cf5ec1246b3919d154ea540e4c6.r2.dev",
        )
        self.static_domain = os.getenv(
            "AIVUNGTAU_R2_STATIC_DOMAIN", "https://static.aivungtau.com"
        )

        # Default settings
        self.presigned_url_expiry = 30 * 60  # 30 minutes in seconds

        # Initialize S3 client
        self.s3_client = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize boto3 S3 client for AIVungtau R2"""
        try:
            if not self.access_key_id or not self.secret_access_key:
                logger.warning(
                    "⚠️ AIVungtau R2 credentials not configured - file upload will fail"
                )
                return

            self.s3_client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                region_name="auto",  # R2 uses 'auto' region
            )

            logger.info("✅ AIVungtau R2 S3 client initialized successfully")

        except Exception as e:
            logger.error(f"❌ Failed to initialize AIVungtau R2 client: {e}")
            self.s3_client = None

    async def upload_file_from_buffer(
        self,
        file_buffer: bytes,
        file_key: str,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Upload file từ buffer (in-memory) lên AIVungtau R2

        Args:
            file_buffer: File content as bytes
            file_key: Key/path for the file in bucket (e.g., "quotes/user123/quote_abc.docx")
            content_type: MIME type of the file
            metadata: Additional metadata to store with file

        Returns:
            Dict with upload result including file_key and urls
        """
        try:
            if not self.s3_client:
                raise Exception("AIVungtau R2 client not initialized")

            # Prepare metadata
            upload_metadata = {
                "uploaded_at": datetime.now().isoformat(),
                "service": "aivungtau-quotes",
            }
            if metadata:
                upload_metadata.update(metadata)

            # Upload to R2
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=file_key,
                Body=file_buffer,
                ContentType=content_type,
                Metadata=upload_metadata,
            )

            logger.info(f"✅ File uploaded to AIVungtau R2: {file_key}")

            return {
                "success": True,
                "file_key": file_key,
                "bucket": self.bucket_name,
                "size_bytes": len(file_buffer),
                "content_type": content_type,
                "public_url": f"{self.public_url}/{file_key}",
                "static_url": f"{self.static_domain}/{file_key}",
                "r2_url": f"{self.endpoint_url}/{self.bucket_name}/{file_key}",
            }

        except Exception as e:
            logger.error(f"❌ Failed to upload file to AIVungtau R2: {e}")
            raise

    def generate_presigned_download_url(
        self, file_key: str, expiry_minutes: int = 30, filename: Optional[str] = None
    ) -> str:
        """
        Tạo pre-signed URL để download file từ AIVungtau R2

        Args:
            file_key: Key of file in bucket
            expiry_minutes: URL expiry time in minutes (default: 30)
            filename: Force download with specific filename

        Returns:
            Pre-signed URL string
        """
        try:
            if not self.s3_client:
                raise Exception("AIVungtau R2 client not initialized")

            # Prepare parameters
            params = {"Bucket": self.bucket_name, "Key": file_key}

            # Add Content-Disposition header to force download with filename
            if filename:
                params["ResponseContentDisposition"] = (
                    f'attachment; filename="{filename}"'
                )

            # Generate pre-signed URL
            presigned_url = self.s3_client.generate_presigned_url(
                "get_object",
                Params=params,
                ExpiresIn=expiry_minutes * 60,  # Convert to seconds
            )

            logger.info(
                f"✅ Pre-signed URL generated for {file_key} (expires in {expiry_minutes} minutes)"
            )
            return presigned_url

        except Exception as e:
            logger.error(f"❌ Failed to generate pre-signed URL: {e}")
            raise

    def generate_file_key(self, user_id: str, file_type: str = "quote") -> str:
        """
        Tạo unique file key cho user

        Args:
            user_id: User ID
            file_type: Type of file (quote, template, etc.)

        Returns:
            Unique file key string
        """
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        file_key = f"{file_type}s/{user_id}/{timestamp}_{unique_id}.docx"

        return file_key

    async def delete_file(self, file_key: str) -> bool:
        """
        Xóa file từ AIVungtau R2 bucket

        Args:
            file_key: Key of file to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.s3_client:
                raise Exception("AIVungtau R2 client not initialized")

            self.s3_client.delete_object(Bucket=self.bucket_name, Key=file_key)

            logger.info(f"✅ File deleted from AIVungtau R2: {file_key}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to delete file from AIVungtau R2: {e}")
            return False

    def check_connection(self) -> Dict[str, Any]:
        """
        Kiểm tra kết nối đến AIVungtau R2 bucket

        Returns:
            Connection status dict
        """
        try:
            if not self.s3_client:
                return {"connected": False, "error": "S3 client not initialized"}

            # Try to list bucket (just to test connection)
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name, MaxKeys=1
            )

            return {
                "connected": True,
                "bucket": self.bucket_name,
                "endpoint": self.endpoint_url,
                "test_time": datetime.now().isoformat(),
            }

        except Exception as e:
            return {"connected": False, "error": str(e)}

        except Exception as e:
            logger.error(f"❌ Failed to initialize R2 client: {e}")
            self.s3_client = None

    async def upload_file_from_buffer(
        self,
        file_buffer: bytes,
        file_key: str,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Upload file từ buffer (in-memory) lên R2

        Args:
            file_buffer: File content as bytes
            file_key: Key/path for the file in bucket (e.g., "quotes/user123/quote_abc.docx")
            content_type: MIME type of the file
            metadata: Additional metadata to store with file

        Returns:
            Dict with upload result including file_key and urls
        """
        try:
            if not self.s3_client:
                raise Exception("R2 client not initialized")

            # Prepare metadata
            upload_metadata = {
                "uploaded_at": datetime.now().isoformat(),
                "service": "aivungtau-quotes",
            }
            if metadata:
                upload_metadata.update(metadata)

            # Upload to R2
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=file_key,
                Body=file_buffer,
                ContentType=content_type,
                Metadata=upload_metadata,
            )

            logger.info(f"✅ File uploaded to R2: {file_key}")

            return {
                "success": True,
                "file_key": file_key,
                "bucket": self.bucket_name,
                "size_bytes": len(file_buffer),
                "content_type": content_type,
                "public_url": f"{self.public_url}/{file_key}",
                "static_url": f"{self.static_domain}/{file_key}",
                "r2_url": f"{self.endpoint_url}/{self.bucket_name}/{file_key}",
            }

        except Exception as e:
            logger.error(f"❌ Failed to upload file to R2: {e}")
            raise

    def generate_presigned_download_url(
        self, file_key: str, expiry_minutes: int = 30, filename: Optional[str] = None
    ) -> str:
        """
        Tạo pre-signed URL để download file từ R2

        Args:
            file_key: Key of file in bucket
            expiry_minutes: URL expiry time in minutes (default: 30)
            filename: Force download with specific filename

        Returns:
            Pre-signed URL string
        """
        try:
            if not self.s3_client:
                raise Exception("R2 client not initialized")

            # Prepare parameters
            params = {"Bucket": self.bucket_name, "Key": file_key}

            # Add Content-Disposition header to force download with filename
            if filename:
                params["ResponseContentDisposition"] = (
                    f'attachment; filename="{filename}"'
                )

            # Generate pre-signed URL
            presigned_url = self.s3_client.generate_presigned_url(
                "get_object",
                Params=params,
                ExpiresIn=expiry_minutes * 60,  # Convert to seconds
            )

            logger.info(
                f"✅ Pre-signed URL generated for {file_key} (expires in {expiry_minutes} minutes)"
            )
            return presigned_url

        except Exception as e:
            logger.error(f"❌ Failed to generate pre-signed URL: {e}")
            raise

    def generate_file_key(self, user_id: str, file_type: str = "quote") -> str:
        """
        Tạo unique file key cho user

        Args:
            user_id: User ID
            file_type: Type of file (quote, template, etc.)

        Returns:
            Unique file key string
        """
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        file_key = f"{file_type}s/{user_id}/{timestamp}_{unique_id}.docx"

        return file_key

    async def delete_file(self, file_key: str) -> bool:
        """
        Xóa file từ R2 bucket

        Args:
            file_key: Key of file to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.s3_client:
                raise Exception("R2 client not initialized")

            self.s3_client.delete_object(Bucket=self.bucket_name, Key=file_key)

            logger.info(f"✅ File deleted from R2: {file_key}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to delete file from R2: {e}")
            return False

    def check_connection(self) -> Dict[str, Any]:
        """
        Kiểm tra kết nối đến R2 bucket

        Returns:
            Connection status dict
        """
        try:
            if not self.s3_client:
                return {"connected": False, "error": "S3 client not initialized"}

            # Try to list bucket (just to test connection)
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name, MaxKeys=1
            )

            return {
                "connected": True,
                "bucket": self.bucket_name,
                "endpoint": self.endpoint_url,
                "test_time": datetime.now().isoformat(),
            }

        except Exception as e:
            return {"connected": False, "error": str(e)}


# Global AIVungtau R2 storage instance for quotes system
aivungtau_r2_storage = AIVungtauR2StorageConfig()

# Backward compatibility alias
r2_storage = aivungtau_r2_storage
