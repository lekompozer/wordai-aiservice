"""
R2 Client for downloading files from Cloudflare R2 storage.
Used by ingestion workers to download documents for processing.
"""

import os
import logging
import asyncio
from typing import Optional, Dict, Any, List
from pathlib import Path

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    import aiofiles

    BOTO3_AVAILABLE = True
except ImportError:
    logging.warning("boto3 not available for R2 integration")
    BOTO3_AVAILABLE = False

# Configure logging
logger = logging.getLogger(__name__)

# Import config
from src.core.config import APP_CONFIG


class R2Client:
    """
    Client for interacting with Cloudflare R2 storage.
    Handles file downloads for document ingestion.
    """

    def __init__(
        self,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        bucket_name: str,
        region: str = "auto",
    ):
        """
        Initialize R2 client.

        Args:
            account_id: Cloudflare account ID
            access_key_id: R2 access key ID
            secret_access_key: R2 secret access key
            bucket_name: R2 bucket name
            region: R2 region (usually "auto")
        """
        if not BOTO3_AVAILABLE:
            raise ImportError("boto3 not available. Please install: pip install boto3")

        self.account_id = account_id
        self.bucket_name = bucket_name

        # R2 endpoint URL
        self.endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"

        # Initialize S3 client (R2 is S3-compatible)
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region,
        )

        logger.info(f"Initialized R2 client for bucket {bucket_name}")

    async def upload_file(
        self,
        local_path: str,
        remote_path: str,
        content_type: str = None,
        content_disposition: str = None,
    ) -> bool:
        """
        Upload a file from local filesystem to R2.

        Args:
            local_path: Local path to the file
            remote_path: Path to store file in R2 bucket
            content_type: MIME type of the file (optional)
            content_disposition: Content-Disposition header (optional, e.g. 'attachment; filename="doc.pdf"')

        Returns:
            True if upload successful, False otherwise
        """
        try:
            local_file = Path(local_path)
            if not local_file.exists():
                logger.error(f"Local file not found: {local_path}")
                return False

            # Upload file using sync client in thread pool
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._upload_file_sync,
                local_path,
                remote_path,
                content_type,
                content_disposition,
            )

            logger.debug(f"Successfully uploaded {local_path} to {remote_path}")
            return True

        except Exception as e:
            logger.error(f"Error uploading {local_path}: {e}")
            return False

    def _upload_file_sync(
        self,
        local_path: str,
        remote_path: str,
        content_type: str = None,
        content_disposition: str = None,
    ):
        """Synchronous file upload (runs in thread pool)"""
        # Read file content
        with open(local_path, "rb") as f:
            file_content = f.read()

        # Build put_object parameters
        put_params = {
            "Bucket": self.bucket_name,
            "Key": remote_path,
            "Body": file_content,
        }

        # Add optional parameters
        if content_type:
            put_params["ContentType"] = content_type
        if content_disposition:
            put_params["ContentDisposition"] = content_disposition

        # Upload using put_object (allows setting ContentDisposition)
        self.s3_client.put_object(**put_params)

    async def download_file(self, remote_path: str, local_path: str) -> bool:
        """
        Download a file from R2 to local filesystem.

        Args:
            remote_path: Path to file in R2 bucket
            local_path: Local path to save the file

        Returns:
            True if download successful, False otherwise
        """
        try:
            # Ensure local directory exists
            local_file = Path(local_path)
            local_file.parent.mkdir(parents=True, exist_ok=True)

            # Download file using sync client in thread pool
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, self._download_file_sync, remote_path, local_path
            )

            # Verify file was downloaded
            if local_file.exists() and local_file.stat().st_size > 0:
                logger.debug(f"Successfully downloaded {remote_path} to {local_path}")
                return True
            else:
                logger.error(f"Download failed: file {local_path} is empty or missing")
                return False

        except Exception as e:
            logger.error(f"Error downloading {remote_path}: {e}")
            return False

    def _download_file_sync(self, remote_path: str, local_path: str):
        """Synchronous file download (runs in thread pool)"""
        self.s3_client.download_file(
            Bucket=self.bucket_name, Key=remote_path, Filename=local_path
        )

    async def file_exists(self, remote_path: str) -> bool:
        """
        Check if a file exists in R2.

        Args:
            remote_path: Path to file in R2 bucket

        Returns:
            True if file exists, False otherwise
        """
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._head_object_sync, remote_path)
            return True

        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            else:
                logger.error(f"Error checking file existence {remote_path}: {e}")
                return False
        except Exception as e:
            logger.error(f"Error checking file existence {remote_path}: {e}")
            return False

    def _head_object_sync(self, remote_path: str):
        """Synchronous head object (runs in thread pool)"""
        self.s3_client.head_object(Bucket=self.bucket_name, Key=remote_path)

    async def get_file_info(self, remote_path: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata about a file in R2.

        Args:
            remote_path: Path to file in R2 bucket

        Returns:
            Dictionary with file metadata or None if not found
        """
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, self._head_object_sync, remote_path
            )

            return {
                "size": response.get("ContentLength", 0),
                "last_modified": response.get("LastModified"),
                "etag": response.get("ETag", "").strip('"'),
                "content_type": response.get("ContentType", ""),
                "metadata": response.get("Metadata", {}),
            }

        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                logger.debug(f"File not found: {remote_path}")
                return None
            else:
                logger.error(f"Error getting file info {remote_path}: {e}")
                return None
        except Exception as e:
            logger.error(f"Error getting file info {remote_path}: {e}")
            return None

    async def list_files(
        self, prefix: str = "", max_keys: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        List files in R2 bucket with optional prefix filter.

        Args:
            prefix: Prefix filter for file paths
            max_keys: Maximum number of files to return

        Returns:
            List of file information dictionaries
        """
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, self._list_objects_sync, prefix, max_keys
            )

            files = []
            for obj in response.get("Contents", []):
                files.append(
                    {
                        "key": obj["Key"],
                        "size": obj["Size"],
                        "last_modified": obj["LastModified"],
                        "etag": obj["ETag"].strip('"'),
                    }
                )

            return files

        except Exception as e:
            logger.error(f"Error listing files with prefix {prefix}: {e}")
            return []

    def _list_objects_sync(self, prefix: str, max_keys: int):
        """Synchronous list objects (runs in thread pool)"""
        return self.s3_client.list_objects_v2(
            Bucket=self.bucket_name, Prefix=prefix, MaxKeys=max_keys
        )

    async def generate_presigned_url(
        self, remote_path: str, expiration: int = 3600, method: str = "GET"
    ) -> Optional[str]:
        """
        Generate a presigned URL for file access.

        Args:
            remote_path: Path to file in R2 bucket
            expiration: URL expiration time in seconds
            method: HTTP method (GET, PUT, etc.)

        Returns:
            Presigned URL or None if error
        """
        try:
            loop = asyncio.get_event_loop()

            if method.upper() == "GET":
                url = await loop.run_in_executor(
                    None,
                    self._generate_presigned_url_sync,
                    "get_object",
                    {"Bucket": self.bucket_name, "Key": remote_path},
                    expiration,
                )
            elif method.upper() == "PUT":
                url = await loop.run_in_executor(
                    None,
                    self._generate_presigned_url_sync,
                    "put_object",
                    {"Bucket": self.bucket_name, "Key": remote_path},
                    expiration,
                )
            else:
                logger.error(f"Unsupported method for presigned URL: {method}")
                return None

            return url

        except Exception as e:
            logger.error(f"Error generating presigned URL for {remote_path}: {e}")
            return None

    def _generate_presigned_url_sync(
        self, client_method: str, method_parameters: dict, expiration: int
    ):
        """Synchronous presigned URL generation (runs in thread pool)"""
        return self.s3_client.generate_presigned_url(
            ClientMethod=client_method, Params=method_parameters, ExpiresIn=expiration
        )

    async def delete_file(self, remote_path: str) -> bool:
        """
        Delete a file from R2.

        Args:
            remote_path: Path to file in R2 bucket

        Returns:
            True if deletion successful, False otherwise
        """
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._delete_object_sync, remote_path)

            logger.info(f"Successfully deleted {remote_path}")
            return True

        except Exception as e:
            logger.error(f"Error deleting {remote_path}: {e}")
            return False

    def _delete_object_sync(self, remote_path: str):
        """Synchronous delete object (runs in thread pool)"""
        self.s3_client.delete_object(Bucket=self.bucket_name, Key=remote_path)

    def health_check(self) -> bool:
        """
        Check if R2 connection is healthy.

        Returns:
            True if connection is healthy
        """
        try:
            # Try to list bucket (this requires minimal permissions)
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            return True
        except Exception as e:
            logger.error(f"R2 health check failed: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get R2 client statistics"""
        return {
            "bucket_name": self.bucket_name,
            "endpoint_url": self.endpoint_url,
            "account_id": self.account_id,
        }

    def get_public_url(self, remote_path: str) -> str:
        """
        Generate public URL for accessing files via custom domain.

        Args:
            remote_path: Path to file in R2 bucket

        Returns:
            Public URL for file access
        """
        # Get public URL from config, fallback to agent8x.io.vn if not set
        public_url = APP_CONFIG.get("r2_public_url") or "https://agent8x.io.vn"
        # Remove leading slash if present
        clean_path = remote_path.lstrip("/")
        return f"{public_url.rstrip('/')}/{clean_path}"


# Factory function
def create_r2_client() -> R2Client:
    """
    Create R2Client from environment variables.

    Environment variables:
        R2_ACCOUNT_ID: Cloudflare account ID
        R2_ACCESS_KEY_ID: R2 access key ID
        R2_SECRET_ACCESS_KEY: R2 secret access key
        R2_BUCKET_NAME: R2 bucket name
        R2_REGION: R2 region (default: auto)

    Returns:
        Configured R2Client instance
    """
    account_id = os.getenv("R2_ACCOUNT_ID")
    access_key_id = os.getenv("R2_ACCESS_KEY_ID")
    secret_access_key = os.getenv("R2_SECRET_ACCESS_KEY")
    bucket_name = os.getenv("R2_BUCKET_NAME")

    if not all([account_id, access_key_id, secret_access_key, bucket_name]):
        raise ValueError("Missing required R2 environment variables")

    return R2Client(
        account_id=account_id,
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
        bucket_name=bucket_name,
        region=os.getenv("R2_REGION", "auto"),
    )
