"""
R2 Storage Service - Cloudflare R2 (S3-compatible) integration
Handles presigned URL generation for direct file uploads
"""

import os
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)


class R2StorageService:
    """Service for managing file uploads to Cloudflare R2 storage"""

    def __init__(self):
        """Initialize R2 client with credentials from environment"""
        self.access_key_id = os.getenv("R2_ACCESS_KEY_ID")
        self.secret_access_key = os.getenv("R2_SECRET_ACCESS_KEY")
        self.bucket_name = os.getenv("R2_BUCKET_NAME", "wordai-documents")
        self.endpoint_url = os.getenv("R2_ENDPOINT_URL")
        self.public_url = os.getenv("R2_PUBLIC_URL", "https://cdn.wordai.vn")

        if not all([self.access_key_id, self.secret_access_key, self.endpoint_url]):
            raise ValueError(
                "Missing R2 credentials. Please set R2_ACCESS_KEY_ID, "
                "R2_SECRET_ACCESS_KEY, and R2_ENDPOINT_URL in environment"
            )

        # Initialize boto3 S3 client with R2 endpoint
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            config=Config(signature_version="s3v4"),
            region_name="auto",  # R2 uses 'auto' for region
        )

        logger.info(f"R2StorageService initialized with bucket: {self.bucket_name}")

    def generate_unique_filename(self, original_filename: str) -> str:
        """
        Generate unique filename to prevent conflicts

        Args:
            original_filename: Original filename from user

        Returns:
            Unique filename with timestamp and UUID prefix
        """
        # Extract extension
        name_parts = original_filename.rsplit(".", 1)
        extension = name_parts[1] if len(name_parts) > 1 else "pdf"
        base_name = name_parts[0]

        # Generate unique prefix
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]

        # Clean base name (remove special chars)
        clean_name = "".join(c for c in base_name if c.isalnum() or c in ("_", "-"))
        clean_name = clean_name[:50]  # Limit length

        return f"attachments/{timestamp}_{unique_id}_{clean_name}.{extension}"

    def generate_presigned_upload_url(
        self,
        filename: str,
        content_type: str = "application/pdf",
        expiration: int = 300,
    ) -> dict:
        """
        Generate presigned URL for direct file upload to R2

        Args:
            filename: Original filename from user
            content_type: MIME type of file (default: application/pdf)
            expiration: URL expiration time in seconds (default: 300 = 5 minutes)

        Returns:
            dict with:
                - presigned_url: URL to upload file (PUT request)
                - file_url: Public URL to access file after upload
                - key: S3 object key (path in bucket)
                - expires_in: Expiration time in seconds
        """
        try:
            # Generate unique key (path in bucket)
            key = self.generate_unique_filename(filename)

            # Generate presigned URL for PUT operation
            presigned_url = self.s3_client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": key,
                    "ContentType": content_type,
                },
                ExpiresIn=expiration,
                HttpMethod="PUT",
            )

            # Construct public URL
            file_url = self.get_public_url(key)

            logger.info(f"Generated presigned URL for {filename} -> {key}")

            return {
                "presigned_url": presigned_url,
                "file_url": file_url,
                "key": key,
                "expires_in": expiration,
            }

        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {str(e)}")
            raise Exception(f"Failed to generate upload URL: {str(e)}")

    def get_public_url(self, key: str) -> str:
        """
        Get public CDN URL for an uploaded file

        Args:
            key: S3 object key (path in bucket)

        Returns:
            Public URL to access file
        """
        # Remove leading slash if present
        key = key.lstrip("/")
        return f"{self.public_url}/{key}"

    def delete_file(self, key: str) -> bool:
        """
        Delete file from R2 storage

        Args:
            key: S3 object key (path in bucket)

        Returns:
            True if deleted successfully
        """
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            logger.info(f"Deleted file: {key}")
            return True

        except ClientError as e:
            logger.error(f"Failed to delete file {key}: {str(e)}")
            return False

    def check_bucket_exists(self) -> bool:
        """
        Check if R2 bucket exists and is accessible

        Returns:
            True if bucket exists and accessible
        """
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"Bucket {self.bucket_name} is accessible")
            return True

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == "404":
                logger.error(f"Bucket {self.bucket_name} does not exist")
            else:
                logger.error(f"Cannot access bucket {self.bucket_name}: {str(e)}")
            return False


# Singleton instance
_r2_service_instance = None


def get_r2_service() -> R2StorageService:
    """
    Get singleton instance of R2StorageService

    Returns:
        R2StorageService instance
    """
    global _r2_service_instance
    if _r2_service_instance is None:
        _r2_service_instance = R2StorageService()
    return _r2_service_instance
