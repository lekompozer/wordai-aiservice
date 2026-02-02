"""
Font Upload Service

Service for managing custom font uploads to R2 storage
"""

import os
import uuid
import logging
from typing import Optional, List, Dict, Any, BinaryIO
from datetime import datetime
from fastapi import UploadFile, HTTPException
import boto3
from botocore.exceptions import ClientError
from pymongo.database import Database

from src.database.db_manager import DBManager
from src.models.font_models import (
    FontFormat,
    FontFamily,
    FontMetadata,
    FontResponse,
    FontFaceRule,
)

logger = logging.getLogger("chatbot")


class FontUploadService:
    """Service for uploading and managing custom fonts"""

    # Maximum file size: 5MB
    MAX_FILE_SIZE = 5 * 1024 * 1024

    # Allowed MIME types
    ALLOWED_MIME_TYPES = {
        "font/ttf": FontFormat.TTF,
        "font/otf": FontFormat.OTF,
        "font/woff": FontFormat.WOFF,
        "font/woff2": FontFormat.WOFF2,
        "application/x-font-ttf": FontFormat.TTF,
        "application/x-font-otf": FontFormat.OTF,
        "application/x-font-woff": FontFormat.WOFF,
        "application/font-woff": FontFormat.WOFF,
        "application/font-woff2": FontFormat.WOFF2,
    }

    # Allowed file extensions
    ALLOWED_EXTENSIONS = {".ttf", ".otf", ".woff", ".woff2"}

    def __init__(self):
        """Initialize font upload service"""
        # Initialize database
        db_manager = DBManager()
        self.db: Database = db_manager.db
        self.fonts_collection = self.db["custom_fonts"]

        # R2 Storage configuration
        self.r2_account_id = os.getenv("R2_ACCOUNT_ID")
        self.r2_access_key = os.getenv("R2_ACCESS_KEY_ID")
        self.r2_secret_key = os.getenv("R2_SECRET_ACCESS_KEY")
        self.r2_bucket_name = os.getenv("R2_BUCKET_NAME", "wordai")
        self.r2_public_url = os.getenv("R2_PUBLIC_URL", "https://static.wordai.pro")

        # Initialize R2 client
        self.r2_client = boto3.client(
            "s3",
            endpoint_url=f"https://{self.r2_account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=self.r2_access_key,
            aws_secret_access_key=self.r2_secret_key,
            region_name="auto",
        )

        # Create indexes
        self._ensure_indexes()

    def _ensure_indexes(self):
        """Create necessary indexes"""
        try:
            self.fonts_collection.create_index([("user_id", 1), ("font_name", 1)])
            self.fonts_collection.create_index([("user_id", 1), ("is_active", 1)])
            self.fonts_collection.create_index("font_id", unique=True)
            logger.info("Font collection indexes created successfully")
        except Exception as e:
            logger.error(f"Error creating font indexes: {e}")

    def _validate_font_file(self, file: UploadFile) -> tuple[bytes, FontFormat]:
        """
        Validate font file format and size

        Args:
            file: Uploaded font file

        Returns:
            Tuple of (file_bytes, font_format)

        Raises:
            HTTPException: If validation fails
        """
        # Read file content
        file_content = file.file.read()
        file.file.seek(0)  # Reset file pointer

        # Check file size
        file_size = len(file_content)
        if file_size > self.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File size {file_size / 1024 / 1024:.2f}MB exceeds maximum of 5MB",
            )

        if file_size == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded")

        # Check file extension
        filename = file.filename.lower()
        file_ext = os.path.splitext(filename)[1]

        if file_ext not in self.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file extension '{file_ext}'. Allowed: {', '.join(self.ALLOWED_EXTENSIONS)}",
            )

        # Determine format from extension
        format_map = {
            ".ttf": FontFormat.TTF,
            ".otf": FontFormat.OTF,
            ".woff": FontFormat.WOFF,
            ".woff2": FontFormat.WOFF2,
        }
        font_format = format_map[file_ext]

        logger.info(
            f"Font file validated: {filename} ({file_size / 1024:.2f}KB, {font_format})"
        )
        return file_content, font_format

    def _upload_to_r2(
        self, file_content: bytes, user_id: str, font_name: str, font_format: FontFormat
    ) -> Dict[str, str]:
        """
        Upload font to R2 storage

        Args:
            file_content: Font file bytes
            user_id: User's Firebase UID
            font_name: Font display name
            font_format: Font format

        Returns:
            Dict with r2_key and r2_url
        """
        # Generate R2 key: fonts/{userId}/{fontName}.{format}
        safe_font_name = "".join(
            c if c.isalnum() or c in ("-", "_") else "_" for c in font_name
        )
        r2_key = f"fonts/{user_id}/{safe_font_name}.{font_format.value}"

        # Upload to R2
        try:
            content_type_map = {
                FontFormat.TTF: "font/ttf",
                FontFormat.WOFF: "font/woff",
                FontFormat.WOFF2: "font/woff2",
            }

            self.r2_client.put_object(
                Bucket=self.r2_bucket_name,
                Key=r2_key,
                Body=file_content,
                ContentType=content_type_map[font_format],
                CacheControl="public, max-age=31536000",  # 1 year cache
            )

            r2_url = f"{self.r2_public_url}/{r2_key}"
            logger.info(f"Font uploaded to R2: {r2_key}")

            return {"r2_key": r2_key, "r2_url": r2_url}

        except ClientError as e:
            logger.error(f"R2 upload failed: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to upload font to storage: {str(e)}"
            )

    async def upload_font(
        self,
        user_id: str,
        file: UploadFile,
        font_name: str,
        font_family: FontFamily,
        description: Optional[str] = None,
    ) -> FontResponse:
        """
        Upload a custom font

        Args:
            user_id: User's Firebase UID
            file: Uploaded font file
            font_name: Display name for the font
            font_family: Font family category
            description: Optional description

        Returns:
            FontResponse with font metadata
        """
        # Validate font file
        file_content, font_format = self._validate_font_file(file)

        # Check if font name already exists for this user
        existing = self.fonts_collection.find_one(
            {"user_id": user_id, "font_name": font_name, "is_active": True}
        )

        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Font '{font_name}' already exists. Please use a different name.",
            )

        # Upload to R2
        r2_data = self._upload_to_r2(file_content, user_id, font_name, font_format)

        # Create font metadata
        font_id = str(uuid.uuid4())
        now = datetime.utcnow()

        font_metadata = FontMetadata(
            font_id=font_id,
            user_id=user_id,
            font_name=font_name,
            font_family=font_family,
            description=description,
            original_filename=file.filename,
            format=font_format,
            file_size=len(file_content),
            r2_key=r2_data["r2_key"],
            r2_url=r2_data["r2_url"],
            is_active=True,
            created_at=now,
            updated_at=now,
        )

        # Save to database
        self.fonts_collection.insert_one(font_metadata.dict())

        logger.info(
            f"Font uploaded successfully: {font_id} ({font_name}) for user {user_id}"
        )

        return FontResponse(
            font_id=font_id,
            font_name=font_name,
            font_family=font_family,
            description=description,
            format=font_format,
            file_size=len(file_content),
            r2_url=r2_data["r2_url"],
            is_active=True,
            created_at=now,
        )

    async def list_user_fonts(self, user_id: str) -> List[FontResponse]:
        """
        List all active fonts for a user

        Args:
            user_id: User's Firebase UID

        Returns:
            List of FontResponse objects
        """
        fonts = list(
            self.fonts_collection.find({"user_id": user_id, "is_active": True}).sort(
                "created_at", -1
            )
        )

        return [
            FontResponse(
                font_id=font["font_id"],
                font_name=font["font_name"],
                font_family=font["font_family"],
                description=font.get("description"),
                format=font["format"],
                file_size=font["file_size"],
                r2_url=font["r2_url"],
                is_active=font["is_active"],
                created_at=font["created_at"],
            )
            for font in fonts
        ]

    async def delete_font(self, user_id: str, font_id: str) -> bool:
        """
        Delete a custom font

        Args:
            user_id: User's Firebase UID
            font_id: Font ID to delete

        Returns:
            True if deleted successfully

        Raises:
            HTTPException: If font not found or not owned by user
        """
        # Find font
        font = self.fonts_collection.find_one({"font_id": font_id, "user_id": user_id})

        if not font:
            raise HTTPException(
                status_code=404,
                detail="Font not found or you don't have permission to delete it",
            )

        # Delete from R2
        try:
            self.r2_client.delete_object(Bucket=self.r2_bucket_name, Key=font["r2_key"])
            logger.info(f"Font deleted from R2: {font['r2_key']}")
        except ClientError as e:
            logger.error(f"R2 deletion failed: {e}")
            # Continue with database deletion even if R2 fails

        # Soft delete from database
        self.fonts_collection.update_one(
            {"font_id": font_id},
            {"$set": {"is_active": False, "updated_at": datetime.utcnow()}},
        )

        logger.info(f"Font deleted: {font_id} ({font['font_name']}) for user {user_id}")
        return True

    async def get_font_face_rules(self, user_id: str) -> List[FontFaceRule]:
        """
        Generate CSS @font-face rules for all user fonts

        Args:
            user_id: User's Firebase UID

        Returns:
            List of FontFaceRule objects with CSS rules
        """
        fonts = await self.list_user_fonts(user_id)

        font_face_rules = []
        for font in fonts:
            # Generate CSS @font-face rule
            css_rule = f"""@font-face {{
  font-family: '{font.font_name}';
  src: url('{font.r2_url}') format('{font.format.value}');
  font-display: swap;
}}"""

            font_face_rules.append(
                FontFaceRule(
                    font_id=font.font_id,
                    font_name=font.font_name,
                    font_family=font.font_family,
                    css_rule=css_rule,
                )
            )

        return font_face_rules
