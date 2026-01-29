"""
Software Lab Storage Service
Handle R2 storage for binary files (images, videos, audio, etc.)
Code files are stored in MongoDB as text.
"""

import io
import os
import boto3
from typing import Optional, BinaryIO
from pathlib import Path
import mimetypes


class SoftwareLabStorage:
    """
    R2 Storage service for Software Lab binary files.

    Storage Strategy:
    - Code files (.py, .js, .html, .css, .sql) → MongoDB (text content)
    - Binary files (.png, .jpg, .mp3, .mp4, .pdf) → R2 Storage
    """

    # File types that should be stored in R2 (binary/assets)
    R2_FILE_EXTENSIONS = {
        # Images
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".webp",
        ".ico",
        # Videos
        ".mp4",
        ".webm",
        ".mov",
        ".avi",
        # Audio
        ".mp3",
        ".wav",
        ".ogg",
        ".m4a",
        # Documents
        ".pdf",
        ".doc",
        ".docx",
        # Archives
        ".zip",
        ".tar",
        ".gz",
        # Fonts
        ".ttf",
        ".woff",
        ".woff2",
        ".otf",
        # Other binary
        ".bin",
        ".exe",
        ".dll",
    }

    # Code file extensions (stored in MongoDB as text)
    CODE_FILE_EXTENSIONS = {
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".html",
        ".css",
        ".scss",
        ".sass",
        ".sql",
        ".json",
        ".md",
        ".txt",
        ".yaml",
        ".yml",
        ".xml",
        ".csv",
    }

    def __init__(self):
        """Initialize R2 client"""
        # Get R2 config from environment variables
        endpoint_url = os.getenv("R2_ENDPOINT")
        access_key_id = os.getenv("R2_ACCESS_KEY_ID")
        secret_access_key = os.getenv("R2_SECRET_ACCESS_KEY")
        bucket_name = os.getenv("R2_BUCKET_NAME", "wordai-documents")

        # Validate required env vars
        if not all([endpoint_url, access_key_id, secret_access_key]):
            raise ValueError(
                "Missing R2 credentials. Check R2_ENDPOINT, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY"
            )

        self.s3_client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name="auto",
        )

        self.bucket_name = bucket_name
        self.public_url = os.getenv("R2_PUBLIC_URL", "https://static.wordai.pro")

    def should_store_in_r2(self, file_path: str) -> bool:
        """
        Check if file should be stored in R2 (binary) or MongoDB (text).

        Args:
            file_path: File path (e.g., "assets/logo.png")

        Returns:
            True if should store in R2, False if store in MongoDB
        """
        ext = Path(file_path).suffix.lower()

        # Explicitly check code files first
        if ext in self.CODE_FILE_EXTENSIONS:
            return False

        # Then check binary files
        if ext in self.R2_FILE_EXTENSIONS:
            return True

        # Default: unknown extension → store in MongoDB as text
        return False

    def upload_file(
        self,
        file_content: bytes,
        project_id: str,
        file_path: str,
        content_type: Optional[str] = None,
    ) -> str:
        """
        Upload binary file to R2 storage.

        Args:
            file_content: Binary file content
            project_id: Project ID (for organizing files)
            file_path: Original file path (e.g., "assets/logo.png")
            content_type: MIME type (auto-detect if None)

        Returns:
            Public URL of uploaded file
        """
        # Generate R2 key: software-lab/{project_id}/{file_path}
        r2_key = f"software-lab/{project_id}/{file_path}"

        # Auto-detect content type if not provided
        if not content_type:
            content_type, _ = mimetypes.guess_type(file_path)
            if not content_type:
                content_type = "application/octet-stream"

        # Upload to R2
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=r2_key,
            Body=file_content,
            ContentType=content_type,
            # Make publicly readable
            ACL="public-read",
        )

        # Return public URL
        public_url = f"{self.public_url}/{r2_key}"
        return public_url

    def upload_file_stream(
        self,
        file_stream: BinaryIO,
        project_id: str,
        file_path: str,
        content_type: Optional[str] = None,
    ) -> str:
        """
        Upload file from stream (for FastAPI UploadFile).

        Args:
            file_stream: File stream
            project_id: Project ID
            file_path: Original file path
            content_type: MIME type

        Returns:
            Public URL
        """
        file_content = file_stream.read()
        return self.upload_file(file_content, project_id, file_path, content_type)

    def delete_file(self, project_id: str, file_path: str) -> bool:
        """
        Delete file from R2 storage.

        Args:
            project_id: Project ID
            file_path: File path

        Returns:
            True if deleted successfully
        """
        r2_key = f"software-lab/{project_id}/{file_path}"

        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=r2_key)
            return True
        except Exception as e:
            print(f"Error deleting R2 file {r2_key}: {e}")
            return False

    def delete_project_files(self, project_id: str) -> int:
        """
        Delete all files of a project from R2.

        Args:
            project_id: Project ID

        Returns:
            Number of files deleted
        """
        prefix = f"software-lab/{project_id}/"

        try:
            # List all objects with prefix
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name, Prefix=prefix
            )

            if "Contents" not in response:
                return 0

            # Delete all objects
            objects = [{"Key": obj["Key"]} for obj in response["Contents"]]

            self.s3_client.delete_objects(
                Bucket=self.bucket_name, Delete={"Objects": objects}
            )

            return len(objects)

        except Exception as e:
            print(f"Error deleting project files for {project_id}: {e}")
            return 0

    def get_file_url(self, project_id: str, file_path: str) -> str:
        """
        Get public URL of file in R2.

        Args:
            project_id: Project ID
            file_path: File path

        Returns:
            Public URL
        """
        r2_key = f"software-lab/{project_id}/{file_path}"
        return f"{self.public_url}/{r2_key}"

    def upload_thumbnail(
        self, image_content: bytes, project_id: str, image_format: str = "png"
    ) -> str:
        """
        Upload project thumbnail/screenshot.

        Args:
            image_content: Image bytes
            project_id: Project ID
            image_format: Image format (png, jpg)

        Returns:
            Public URL
        """
        r2_key = f"software-lab/{project_id}/thumbnail.{image_format}"

        content_type = f"image/{image_format}"

        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=r2_key,
            Body=image_content,
            ContentType=content_type,
            ACL="public-read",
        )

        return f"{self.public_url}/{r2_key}"


# Singleton instance
_storage_instance: Optional[SoftwareLabStorage] = None


def get_software_lab_storage() -> SoftwareLabStorage:
    """Get singleton storage instance"""
    global _storage_instance

    if _storage_instance is None:
        _storage_instance = SoftwareLabStorage()

    return _storage_instance
