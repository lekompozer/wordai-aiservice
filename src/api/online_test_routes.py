"""
Online Test API Routes - Phase 1, 2, 3
Endpoints for test generation, taking tests, submission, WebSocket auto-save, and test editing
"""

import logging
import os
import asyncio
import boto3
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from bson import ObjectId
from pymongo import MongoClient

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    BackgroundTasks,
    UploadFile,
    File,
    Form,
    Query,
)
from pydantic import BaseModel, Field

from src.middleware.auth import verify_firebase_token as require_auth
from src.services.test_generator_service import get_test_generator_service
from src.services.document_manager import document_manager
from src.services.test_sharing_service import get_test_sharing_service
from src.models.subscription import SubscriptionUsageUpdate
import config.config as config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tests", tags=["Online Tests - Phase 1-3"])

# MongoDB connection helper
_mongo_client = None


def get_mongodb_service():
    """Get MongoDB database instance (helper for compatibility)"""
    global _mongo_client
    if _mongo_client is None:
        mongo_uri = getattr(config, "MONGODB_URI_AUTH", None) or getattr(
            config, "MONGODB_URI", "mongodb://localhost:27017"
        )
        _mongo_client = MongoClient(mongo_uri)
    db_name = getattr(config, "MONGODB_NAME", "wordai_db")
    db = _mongo_client[db_name]

    # Return a simple object that mimics the service interface
    class MongoDBService:
        def __init__(self, database):
            self.db = database

    return MongoDBService(db)


def get_document_manager():
    """Get document manager instance"""
    return document_manager


# ========== R2 Configuration for Marketplace ==========

# R2 Configuration
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "wordai")
R2_ENDPOINT_URL = os.getenv("R2_ENDPOINT")
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "https://static.wordai.pro")

# Initialize R2 client
_s3_client = None


def get_s3_client():
    """Get or create S3 client for R2"""
    global _s3_client
    if _s3_client is None:
        if not all([R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT_URL]):
            logger.error("❌ Missing R2 credentials")
            raise HTTPException(
                status_code=500, detail="R2 storage not configured properly"
            )

        _s3_client = boto3.client(
            "s3",
            aws_access_key_id=R2_ACCESS_KEY_ID,
            aws_secret_access_key=R2_SECRET_ACCESS_KEY,
            endpoint_url=R2_ENDPOINT_URL,
            region_name="auto",
        )
        logger.info("✅ R2 client initialized for marketplace")

    return _s3_client


async def upload_cover_to_r2(
    file_content: bytes, test_id: str, version: str, content_type: str
) -> str:
    """
    Upload test cover image to R2 and return public URL

    Cover images are stored in public 'test-covers/' directory for direct access.
    The R2 bucket has a public access policy configured for this directory.
    """
    try:
        # Generate R2 key
        key = f"test-covers/test_{test_id}_{version}.jpg"

        logger.info(f"   [R2] Uploading cover image...")
        logger.info(f"   [R2] Key: {key}")
        logger.info(f"   [R2] Size: {len(file_content)} bytes")

        s3_client = get_s3_client()

        # Upload to R2 (public read via bucket policy)
        s3_client.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=key,
            Body=file_content,
            ContentType=content_type,
        )

        # Return public URL (accessible via bucket policy)
        public_url = f"{R2_PUBLIC_URL}/{key}"
        logger.info(f"   [R2] ✅ Cover uploaded: {public_url}")
        return public_url

    except Exception as e:
        logger.error(f"   [R2] ❌ Upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Cover upload failed: {str(e)}")


# ========== Phase 4: Access Control Helper ==========


def check_test_access(
    test_id: str, user_id: str, test_doc: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Check if user has access to test (owner, shared, or public)

    Args:
        test_id: Test ID
        user_id: Firebase UID
        test_doc: Optional test document (to avoid extra query)

    Returns:
        Dict with access_type ("owner", "shared", or "public") and test document

    Raises:
        HTTPException: If no access
    """
    try:
        # Get test if not provided
        if not test_doc:
            mongo_service = get_mongodb_service()
            test_doc = mongo_service.db["online_tests"].find_one(
                {"_id": ObjectId(test_id)}
            )

            if not test_doc:
                raise HTTPException(status_code=404, detail="Test not found")

        # Check if user is owner
        if test_doc.get("creator_id") == user_id:
            return {
                "access_type": "owner",
                "test": test_doc,
                "is_owner": True,
            }

        # Check if test is public on marketplace
        marketplace_config = test_doc.get("marketplace_config", {})
        if marketplace_config.get("is_public", False):
            return {
                "access_type": "public",
                "test": test_doc,
                "is_owner": False,
                "is_public": True,
            }

        # Check if test is shared with user
        sharing_service = get_test_sharing_service()
        share = sharing_service.db.test_shares.find_one(
            {
                "test_id": str(test_doc["_id"]),
                "sharee_id": user_id,
                "status": "accepted",
            }
        )

        if not share:
            raise HTTPException(
                status_code=403,
                detail="Access denied: You don't own this test and it hasn't been shared with you",
            )

        # Check deadline (priority: test's global deadline, then share-specific override)
        deadline = test_doc.get("deadline") or share.get("deadline")
        if deadline:
            if deadline.tzinfo is None:
                from datetime import timezone

                deadline = deadline.replace(tzinfo=timezone.utc)

            if deadline < datetime.now(deadline.tzinfo):
                # Auto-expire
                sharing_service.db.test_shares.update_one(
                    {"share_id": share["share_id"]}, {"$set": {"status": "expired"}}
                )
                raise HTTPException(
                    status_code=403,
                    detail="Access denied: Deadline has passed for this shared test",
                )

        return {
            "access_type": "shared",
            "test": test_doc,
            "is_owner": False,
            "share": share,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error checking test access: {e}")
        raise HTTPException(status_code=500, detail="Failed to check test access")


# ========== Request/Response Models ==========


class GenerateTestRequest(BaseModel):
    """Request model for AI-generated test"""

    source_type: str = Field(..., description="Source type: 'document' or 'file'")
    source_id: str = Field(..., description="Document ID or R2 file key")
    title: str = Field(..., description="Test title", min_length=5, max_length=200)
    description: Optional[str] = Field(
        None,
        description="Test description for test takers (optional, user-facing)",
        max_length=1000,
    )
    user_query: Optional[str] = Field(
        None,
        description="Instructions to AI: what topics/concepts to test (optional for files, can be inferred from content)",
        min_length=10,
        max_length=500,
    )
    language: str = Field(
        default="vi",
        description="Language for test content: specify any language (e.g., 'vi', 'en', 'zh', 'fr', 'es', etc.)",
    )
    difficulty: Optional[str] = Field(
        None,
        description="Question difficulty level: 'easy', 'medium', 'hard' (optional, AI can infer if not provided)",
    )
    num_questions: int = Field(..., description="Number of questions", ge=1, le=100)
    time_limit_minutes: int = Field(
        30, description="Time limit in minutes", ge=1, le=300
    )
    max_retries: int = Field(3, description="Maximum number of attempts", ge=1, le=10)
    passing_score: int = Field(
        70, description="Minimum score percentage to pass (0-100)", ge=0, le=100
    )
    deadline: Optional[datetime] = Field(
        None, description="Global deadline for all users (ISO 8601 format)"
    )
    show_answers_timing: str = Field(
        "immediate",
        description="When to show answers: 'immediate' (show after submit) or 'after_deadline' (show only after deadline passes)",
    )
    num_options: int = Field(
        4,
        description="Number of answer options per question (e.g., 4 for A-D, 6 for A-F). Set to 0 or 'auto' to let AI decide.",
        ge=0,
        le=10,
    )
    num_correct_answers: int = Field(
        1,
        description="Number of correct answers per question. Set to 0 or 'auto' to let AI decide based on question complexity.",
        ge=0,
        le=10,
    )


class ManualTestQuestion(BaseModel):
    """Manual question model - flexible validation for user-created tests"""

    question_text: str = Field(..., min_length=1, max_length=1000)
    options: list = Field(
        ..., description="List of options with 'key' and 'text'", min_length=2
    )
    correct_answer_key: str = Field(
        ..., description="Correct answer key (A, B, C, D, etc.)"
    )
    explanation: Optional[str] = Field(
        None, description="Optional explanation", max_length=500
    )


class TestAttachment(BaseModel):
    """Test attachment model for reading comprehension materials"""

    title: str = Field(
        ...,
        description="Attachment title (e.g., 'Reading Passage', 'Reference Document')",
        min_length=1,
        max_length=200,
    )
    description: Optional[str] = Field(
        None, description="Optional description of the attachment", max_length=500
    )
    file_url: str = Field(
        ...,
        description="URL to the PDF file (R2 storage URL or external URL)",
        max_length=1000,
    )
    file_size_mb: float = Field(
        ...,
        description="File size in MB (from presigned URL response)",
        ge=0,
        le=100,
    )


class PresignedURLRequest(BaseModel):
    """Request model for generating presigned URL for file upload"""

    filename: str = Field(
        ...,
        description="Original filename (e.g., 'passage1.pdf')",
        min_length=1,
        max_length=255,
    )
    file_size_mb: float = Field(
        ...,
        description="File size in MB (frontend must calculate before upload)",
        ge=0,
        le=100,  # Max 100MB per file
    )
    content_type: Optional[str] = Field(
        "application/pdf",
        description="MIME type of file (default: application/pdf)",
        max_length=100,
    )


class CreateManualTestRequest(BaseModel):
    """Request model for manual test creation"""

    title: str = Field(..., description="Test title", min_length=5, max_length=200)
    description: Optional[str] = Field(
        None, description="Test description (optional)", max_length=1000
    )
    language: str = Field(
        default="vi",
        description="Language for test content: specify any language (e.g., 'vi', 'en', 'zh', 'fr', 'es', etc.)",
    )
    time_limit_minutes: int = Field(
        30, description="Time limit in minutes", ge=1, le=300
    )
    max_retries: int = Field(3, description="Maximum number of attempts", ge=1, le=10)
    passing_score: int = Field(
        70, description="Minimum score percentage to pass (0-100)", ge=0, le=100
    )
    deadline: Optional[datetime] = Field(
        None, description="Global deadline for all users (ISO 8601 format)"
    )
    show_answers_timing: str = Field(
        "immediate",
        description="When to show answers: 'immediate' (show after submit) or 'after_deadline' (show only after deadline passes)",
    )
    questions: Optional[list[ManualTestQuestion]] = Field(
        default=[],
        description="List of questions (optional, can be empty to create draft test)",
    )
    attachments: Optional[list[TestAttachment]] = Field(
        default=[],
        description="List of PDF attachments for reading comprehension (optional)",
    )


class DuplicateTestRequest(BaseModel):
    """Request model for duplicating a test"""

    new_title: Optional[str] = Field(
        None,
        description="New title for duplicated test (optional, will auto-generate if not provided)",
        max_length=200,
    )


class TestQuestionsResponse(BaseModel):
    """Response model for test questions (for taking)"""

    test_id: str
    status: str
    title: str
    description: Optional[str]
    time_limit_minutes: int
    num_questions: int
    questions: list


class TestStatusResponse(BaseModel):
    """Response model for test status polling"""

    test_id: str
    status: str  # pending, generating, ready, failed
    progress_percent: int
    message: str
    error_message: Optional[str] = None
    # Include these when ready
    title: Optional[str] = None
    description: Optional[str] = None
    num_questions: Optional[int] = None
    created_at: Optional[str] = None
    generated_at: Optional[str] = None


class SubmitTestRequest(BaseModel):
    """Request model for test submission"""

    user_answers: list = Field(
        ..., description="List of {question_id, selected_answer_key}"
    )


class TestResultResponse(BaseModel):
    """Response model for test results"""

    submission_id: str
    score: float
    total_questions: int
    correct_answers: int
    time_taken_seconds: int
    results: list


class TestSummary(BaseModel):
    """Summary of a test"""

    test_id: str
    title: str
    num_questions: int
    time_limit_minutes: int
    created_at: str
    attempts_count: int


# ========== Endpoints ==========


# ========== Background Job for AI Generation ==========


async def generate_test_background(
    test_id: str,
    content: str,
    title: str,
    user_query: str,
    language: str,
    difficulty: Optional[str],
    num_questions: int,
    creator_id: str,
    source_type: str,
    source_id: str,
    time_limit_minutes: int,
    gemini_pdf_bytes: Optional[bytes],
    num_options: int = 4,
    num_correct_answers: int = 1,
):
    """
    Background job to generate test questions with AI
    Updates status: pending → generating → ready/failed
    """
    from pymongo import MongoClient
    import config.config as config

    mongo_uri = getattr(config, "MONGODB_URI_AUTH", None) or getattr(
        config, "MONGODB_URI", "mongodb://localhost:27017"
    )
    client = MongoClient(mongo_uri)
    db_name = getattr(config, "MONGODB_NAME", "wordai_db")
    db = client[db_name]
    collection = db["online_tests"]

    try:
        # Update status to generating
        collection.update_one(
            {"_id": ObjectId(test_id)},
            {
                "$set": {
                    "status": "generating",
                    "progress_percent": 10,
                    "updated_at": datetime.now(),
                }
            },
        )
        logger.info(f"🔄 Test {test_id}: Status updated to 'generating'")

        # Generate test with AI
        test_generator = get_test_generator_service()

        logger.info(f"🤖 Calling AI to generate {num_questions} questions...")
        questions = await test_generator._generate_questions_with_ai(
            content=content,
            user_query=user_query,
            language=language,
            difficulty=difficulty,
            num_questions=num_questions,
            gemini_pdf_bytes=gemini_pdf_bytes,
            num_options=num_options,
            num_correct_answers=num_correct_answers,
        )

        # Update progress
        collection.update_one(
            {"_id": ObjectId(test_id)},
            {"$set": {"progress_percent": 80, "updated_at": datetime.now()}},
        )

        # Save questions
        collection.update_one(
            {"_id": ObjectId(test_id)},
            {
                "$set": {
                    "questions": questions,
                    "status": "ready",
                    "progress_percent": 100,
                    "generated_at": datetime.now(),
                    "updated_at": datetime.now(),
                }
            },
        )

        logger.info(f"✅ Test {test_id}: Generation completed successfully")

    except Exception as e:
        logger.error(f"❌ Test {test_id}: Generation failed: {e}")
        collection.update_one(
            {"_id": ObjectId(test_id)},
            {
                "$set": {
                    "status": "failed",
                    "error_message": str(e),
                    "progress_percent": 0,
                    "updated_at": datetime.now(),
                }
            },
        )

    finally:
        client.close()


@router.post("/generate")
async def generate_test(
    request: GenerateTestRequest,
    background_tasks: BackgroundTasks,
    user_info: dict = Depends(require_auth),
):
    """
    Generate a new test from document or file (AI-powered)

    **NEW Async Pattern**: Returns immediately with test_id and status='pending'.
    Background job generates questions. Frontend polls /tests/{test_id}/status.

    **Flow:**
    1. Create test record with status='pending'
    2. Return test_id immediately (< 500ms)
    3. Start background AI generation
    4. Frontend polls status endpoint
    5. When ready, frontend renders questions

    **Benefits:**
    - Fast response time
    - User can close browser, come back later
    - No data loss on network errors
    """
    try:
        logger.info(f"📝 Test generation request from user {user_info['uid']}")
        logger.info(f"   Source: {request.source_type}/{request.source_id}")
        logger.info(f"   Title: {request.title}")
        logger.info(f"   Description: {request.description or '(none)'}")

        # Set default user_query if not provided
        if not request.user_query or request.user_query.strip() == "":
            request.user_query = f"Generate comprehensive test questions covering all key concepts and important information from this document. Questions should assess understanding of the main topics, details, and core knowledge presented in the material."
            logger.info(f"   Query: (auto-generated default)")
        else:
            logger.info(f"   Query: {request.user_query}")

        logger.info(f"   Language: {request.language}")
        logger.info(f"   Difficulty: {request.difficulty or '(auto)'}")
        logger.info(
            f"   Questions: {request.num_questions}, Time: {request.time_limit_minutes}min"
        )

        # Language validation removed - now supports ANY language for maximum flexibility
        # The AI model can generate questions in any language the user specifies

        # Initialize variables
        content = ""
        gemini_pdf_bytes = None  # For PDF files

        # Get content based on source type
        if request.source_type == "document":
            # Get document from MongoDB
            doc_manager = get_document_manager()
            try:
                doc = doc_manager.get_document(request.source_id, user_info["uid"])
                content_html = doc.get("content_html", "")

                if not content_html:
                    raise HTTPException(
                        status_code=400, detail="Document has no content"
                    )

                # Parse HTML to plain text (remove tags but preserve structure)
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(content_html, "html.parser")

                # Remove script and style tags completely
                for script in soup(["script", "style"]):
                    script.decompose()

                # Get text with some structure preserved
                content = soup.get_text(separator=" ", strip=True)

                # Clean up excessive whitespace
                import re

                content = re.sub(r"\s+", " ", content).strip()

                logger.info(f"📄 Parsed HTML document: {len(content)} characters")

            except Exception as e:
                logger.error(f"❌ Failed to get document: {e}")
                raise HTTPException(
                    status_code=404,
                    detail=f"Document not found or access denied: {str(e)}",
                )

        elif request.source_type == "file":
            # Get file metadata from MongoDB to check file type
            from src.services.user_manager import get_user_manager
            from src.services.file_download_service import FileDownloadService
            import google.generativeai as genai

            user_manager = get_user_manager()
            file_info = user_manager.get_file_by_id(request.source_id, user_info["uid"])

            if not file_info:
                raise HTTPException(
                    status_code=404, detail=f"File not found: {request.source_id}"
                )

            # Check file type and process accordingly
            file_type = file_info.get("file_type", "").lower()
            r2_key = file_info.get("r2_key")

            if not r2_key:
                raise HTTPException(
                    status_code=500, detail="File R2 key not found in database"
                )

            logger.info(f"📄 Processing file type: {file_type}")

            # ========== PDF FILES: Send directly to Gemini (no parsing) ==========
            if file_type == ".pdf":
                logger.info(f"📥 Downloading PDF from R2 for Gemini File API: {r2_key}")

                # Download PDF to temp file (ONLY download, no need to parse)
                # Gemini File API will handle PDF directly (including image-based PDFs)
                temp_pdf_path = (
                    await FileDownloadService._download_file_from_r2_with_boto3(
                        r2_key=r2_key, file_type="pdf"
                    )
                )

                if not temp_pdf_path:
                    raise HTTPException(
                        status_code=500, detail="Failed to download PDF from R2"
                    )

                logger.info(f"✅ PDF downloaded to: {temp_pdf_path}")

                # Read PDF content as bytes (NEW API approach)
                logger.info(f"📖 Reading PDF content for Gemini...")

                try:
                    with open(temp_pdf_path, "rb") as f:
                        pdf_content = f.read()

                    logger.info(f"✅ PDF content read: {len(pdf_content)} bytes")

                    # Store PDF bytes for Gemini (will be passed directly to model)
                    gemini_pdf_bytes = pdf_content

                    # Use placeholder content
                    content = f"[PDF file ready for Gemini: {len(pdf_content)} bytes]"

                except Exception as e:
                    logger.error(f"❌ Failed to read PDF: {e}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to process PDF: {str(e)}",
                    )

                finally:
                    # Cleanup temp file
                    if temp_pdf_path and os.path.exists(temp_pdf_path):
                        try:
                            os.unlink(temp_pdf_path)
                            logger.info(f"🗑️ Cleaned up temp file: {temp_pdf_path}")
                        except Exception as e:
                            logger.warning(f"⚠️ Failed to cleanup temp file: {e}")

            # ========== TEXT FILES: .md, .docx, .txt - Parse to text ==========
            elif file_type in [".md", ".docx", ".txt", ".doc"]:
                logger.info(f"📥 Downloading text file from R2: {r2_key}")

                # Download file to temp location
                temp_file_path = (
                    await FileDownloadService._download_file_from_r2_with_boto3(
                        r2_key=r2_key, file_type=file_type.replace(".", "")
                    )
                )

                if not temp_file_path:
                    raise HTTPException(
                        status_code=500, detail="Failed to download file from R2"
                    )

                try:
                    # Parse file to text based on type
                    if file_type == ".txt":
                        with open(temp_file_path, "r", encoding="utf-8") as f:
                            content = f.read()

                    elif file_type == ".md":
                        with open(temp_file_path, "r", encoding="utf-8") as f:
                            content = f.read()

                    elif file_type in [".docx", ".doc"]:
                        # Use python-docx to extract text
                        try:
                            from docx import Document

                            doc = Document(temp_file_path)
                            content = "\n".join([para.text for para in doc.paragraphs])
                        except Exception as e:
                            logger.error(f"❌ Failed to parse DOCX: {e}")
                            raise HTTPException(
                                status_code=500,
                                detail=f"Failed to parse DOCX file: {str(e)}",
                            )

                    logger.info(
                        f"✅ Parsed {file_type} file: {len(content)} characters"
                    )

                    if not content or len(content.strip()) < 50:
                        raise HTTPException(
                            status_code=400,
                            detail="File content is too short or empty",
                        )

                except Exception as e:
                    logger.error(f"❌ Failed to process file: {e}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to process {file_type} file: {str(e)}",
                    )

                finally:
                    # Cleanup temp file
                    if temp_file_path and os.path.exists(temp_file_path):
                        try:
                            os.unlink(temp_file_path)
                            logger.info(f"🗑️ Cleaned up temp file: {temp_file_path}")
                        except Exception as e:
                            logger.warning(f"⚠️ Failed to cleanup temp file: {e}")

            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type: {file_type}. Supported types: PDF (sent directly to Gemini), .md, .docx, .txt (parsed to text)",
                )

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid source_type: {request.source_type}. Must be 'document' or 'file'",
            )

        # ========== NEW: Create test record immediately with status='pending' ==========
        mongo_service = get_mongodb_service()
        collection = mongo_service.db["online_tests"]

        test_doc = {
            "title": request.title,
            "description": request.description,
            "user_query": request.user_query,
            "test_language": request.language,  # Renamed from 'language' to avoid MongoDB text index conflict
            "source_type": request.source_type,
            "source_document_id": (
                request.source_id if request.source_type == "document" else None
            ),
            "source_file_r2_key": (
                request.source_id if request.source_type == "file" else None
            ),
            "creator_id": user_info["uid"],
            "time_limit_minutes": request.time_limit_minutes,
            "num_questions": request.num_questions,
            "max_retries": request.max_retries,
            "passing_score": request.passing_score,
            "deadline": request.deadline,  # Global deadline for all shared users
            "show_answers_timing": request.show_answers_timing,  # New: Control when to show answers
            "creation_type": "ai_generated",
            "status": "pending",
            "progress_percent": 0,
            "questions": [],  # Will be populated by background job
            "is_active": True,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

        result = collection.insert_one(test_doc)
        test_id = str(result.inserted_id)

        logger.info(f"✅ Test record created: {test_id} with status='pending'")

        # ========== Start background job for AI generation ==========
        background_tasks.add_task(
            generate_test_background,
            test_id=test_id,
            content=content,
            title=request.title,
            user_query=request.user_query,
            language=request.language,
            difficulty=request.difficulty,
            num_questions=request.num_questions,
            creator_id=user_info["uid"],
            source_type=request.source_type,
            source_id=request.source_id,
            time_limit_minutes=request.time_limit_minutes,
            gemini_pdf_bytes=(
                gemini_pdf_bytes if request.source_type == "file" else None
            ),
            num_options=request.num_options if request.num_options > 0 else 4,
            num_correct_answers=(
                request.num_correct_answers if request.num_correct_answers > 0 else 1
            ),
        )

        logger.info(f"🚀 Background job queued for test {test_id}")

        # ========== Return immediately ==========
        return {
            "success": True,
            "test_id": test_id,
            "status": "pending",
            "title": request.title,
            "description": request.description,
            "num_questions": request.num_questions,
            "time_limit_minutes": request.time_limit_minutes,
            "created_at": test_doc["created_at"].isoformat(),
            "message": "Test created successfully. AI is generating questions...",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Test generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== NEW: Presigned URL for File Upload ==========


@router.post("/attachments/presigned-url", tags=["Attachments"])
async def get_presigned_upload_url(
    request: PresignedURLRequest,
    user_info: dict = Depends(require_auth),
):
    """
    Generate presigned URL for direct file upload to R2 storage

    **IMPORTANT**: Attachments tính vào storage quota của test owner, không phải người upload.
    Khi upload attachments cho test của người khác, vẫn tính vào quota của test owner.

    **Flow:**
    1. Frontend calls this endpoint with filename + file_size_mb
    2. Backend checks storage quota của user
    3. Backend generates presigned URL (valid 5 minutes)
    4. Frontend uploads file directly to presigned URL (PUT request)
    5. Frontend then creates attachment with file_url

    **Storage Rules:**
    - Attachments tính vào storage của test owner
    - Max file size: 100MB per file
    - Frontend phải tính file size trước khi gọi endpoint

    **Returns:**
    - presigned_url: URL for uploading file (PUT request)
    - file_url: Public URL to access file after upload
    - expires_in: Expiration time in seconds
    """
    try:
        from src.services.r2_storage_service import get_r2_service
        from src.services.subscription_service import get_subscription_service

        user_id = user_info["uid"]
        logger.info(
            f"🔗 Generating presigned URL for user {user_id}: {request.filename} ({request.file_size_mb}MB)"
        )

        # Check storage limit
        subscription_service = get_subscription_service()
        if not await subscription_service.check_storage_limit(
            user_id, request.file_size_mb
        ):
            subscription = await subscription_service.get_subscription(user_id)
            remaining_mb = subscription.storage_limit_mb - subscription.storage_used_mb

            raise HTTPException(
                status_code=403,
                detail={
                    "error": "Không đủ dung lượng lưu trữ",
                    "message": f"Cần: {request.file_size_mb:.2f}MB, Còn lại: {remaining_mb:.2f}MB",
                    "file_size_mb": request.file_size_mb,
                    "storage_used_mb": round(subscription.storage_used_mb, 2),
                    "storage_limit_mb": subscription.storage_limit_mb,
                    "upgrade_url": "https://ai.wordai.pro/pricing",
                },
            )

        # Get R2 service
        r2_service = get_r2_service()

        # Generate presigned URL
        result = r2_service.generate_presigned_upload_url(
            filename=request.filename, content_type=request.content_type
        )

        # Return presigned URL with file_size for tracking
        return {
            "success": True,
            "presigned_url": result["presigned_url"],
            "file_url": result["file_url"],
            "file_size_mb": request.file_size_mb,  # Return for frontend tracking
            "expires_in": result["expires_in"],
        }

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"❌ R2 configuration error: {e}")
        raise HTTPException(
            status_code=500, detail="File upload service not configured properly"
        )
    except Exception as e:
        logger.error(f"❌ Failed to generate presigned URL: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to generate upload URL: {str(e)}"
        )


# ========== NEW: Manual Test Creation Endpoint ==========


@router.post("/manual")
async def create_manual_test(
    request: CreateManualTestRequest,
    user_info: dict = Depends(require_auth),
):
    """
    Create a test with manually entered questions

    **UPDATED**: Questions are now optional - can create empty draft test

    User can:
    1. Create empty test with just title → Add questions later
    2. Create test with initial questions → Continue editing
    3. Duplicate existing test → Modify copy

    Test is immediately set to status='ready' (no AI generation needed).

    **Use Cases:**
    - Teacher creates draft quiz, adds questions gradually
    - Import questions from existing material
    - Quick test without AI
    """
    try:
        logger.info(f"📝 Manual test creation from user {user_info['uid']}")
        logger.info(f"   Title: {request.title}")
        logger.info(f"   Questions: {len(request.questions or [])}")

        # Validate questions if provided
        if request.questions:
            for idx, q in enumerate(request.questions):
                if len(q.options) < 2:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Question {idx+1}: Must have at least 2 options",
                    )

                # Validate correct_answer_key exists in options
                option_keys = [opt["key"] for opt in q.options]
                if q.correct_answer_key not in option_keys:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Question {idx+1}: correct_answer_key '{q.correct_answer_key}' not found in options",
                    )

        # Create test record
        mongo_service = get_mongodb_service()
        collection = mongo_service.db["online_tests"]

        # Format questions with question_id
        import uuid

        formatted_questions = []
        if request.questions:
            for q in request.questions:
                formatted_questions.append(
                    {
                        "question_id": str(uuid.uuid4())[:8],
                        "question_text": q.question_text,
                        "options": q.options,
                        "correct_answer_key": q.correct_answer_key,
                        "explanation": q.explanation,
                    }
                )

        # Determine status based on whether test has questions
        status = "ready" if len(formatted_questions) > 0 else "draft"

        # Format attachments with attachment_id
        formatted_attachments = []
        if request.attachments:
            for att in request.attachments:
                formatted_attachments.append(
                    {
                        "attachment_id": str(uuid.uuid4())[:12],
                        "title": att.title,
                        "description": att.description,
                        "file_url": att.file_url,
                        "uploaded_at": datetime.now(),
                    }
                )

        test_doc = {
            "title": request.title,
            "description": request.description,
            "user_query": None,  # N/A for manual tests
            "test_language": request.language,  # Renamed from 'language' to avoid MongoDB text index conflict
            "source_type": "manual",
            "source_document_id": None,
            "source_file_r2_key": None,
            "creator_id": user_info["uid"],
            "time_limit_minutes": request.time_limit_minutes,
            "num_questions": len(formatted_questions),
            "max_retries": request.max_retries,
            "passing_score": request.passing_score,
            "deadline": request.deadline,  # Global deadline for all shared users
            "show_answers_timing": request.show_answers_timing,  # New: Control when to show answers
            "creation_type": "manual",
            "status": status,  # "draft" if no questions, "ready" if has questions
            "progress_percent": 100 if len(formatted_questions) > 0 else 0,
            "questions": formatted_questions,
            "attachments": formatted_attachments,  # NEW: PDF attachments for reading comprehension
            "is_active": True,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

        result = collection.insert_one(test_doc)
        test_id = str(result.inserted_id)

        logger.info(f"✅ Manual test created: {test_id} (status: {status})")

        message = (
            "Manual test created successfully!"
            if status == "ready"
            else "Draft test created. Add questions to make it ready."
        )

        return {
            "success": True,
            "test_id": test_id,
            "status": status,
            "title": request.title,
            "description": request.description,
            "num_questions": len(formatted_questions),
            "num_attachments": len(formatted_attachments),
            "time_limit_minutes": request.time_limit_minutes,
            "created_at": test_doc["created_at"].isoformat(),
            "message": message,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Manual test creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Duplicate Test Endpoint ==========


@router.post("/{test_id}/duplicate")
async def duplicate_test(
    test_id: str,
    request: DuplicateTestRequest,
    user_info: dict = Depends(require_auth),
):
    """
    Duplicate an existing test

    **NEW Endpoint**

    Creates a copy of existing test with auto-generated title suffix:
    - "Test ABC" → "Test ABC copy1"
    - "Test ABC copy1" → "Test ABC copy2"
    - etc.

    **Use Cases:**
    - Create variations of same test
    - Modify copy without affecting original
    - Template-based test creation

    **Response:**
    - Returns new test_id with duplicated content
    - Questions are deep-copied with new question_ids
    - Status = "ready" (or "draft" if original was draft)
    """
    try:
        logger.info(
            f"📋 Duplicate test request: {test_id} from user {user_info['uid']}"
        )

        # Get original test
        mongo_service = get_mongodb_service()
        collection = mongo_service.db["online_tests"]

        original_test = collection.find_one({"_id": ObjectId(test_id)})

        if not original_test:
            raise HTTPException(status_code=404, detail="Test not found")

        # Only creator can duplicate
        if original_test.get("creator_id") != user_info["uid"]:
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to duplicate this test",
            )

        # Generate new title with copy suffix
        import re

        original_title = original_test.get("title", "Untitled Test")

        if request.new_title:
            new_title = request.new_title
        else:
            # Check for existing copies
            match = re.search(r" copy(\d+)$", original_title)
            if match:
                # Increment copy number
                copy_num = int(match.group(1)) + 1
                base_title = original_title[: match.start()]
                new_title = f"{base_title} copy{copy_num}"
            else:
                # First copy
                new_title = f"{original_title} copy1"

        # Deep copy questions with new question_ids
        import uuid

        new_questions = []
        for q in original_test.get("questions", []):
            new_q = q.copy()
            new_q["question_id"] = str(uuid.uuid4())[:8]
            new_questions.append(new_q)

        # Create duplicated test document
        duplicated_doc = {
            "title": new_title,
            "description": original_test.get("description"),
            "user_query": original_test.get("user_query"),
            "test_language": original_test.get("test_language")
            or original_test.get(
                "language", "vi"
            ),  # Support both old and new field names
            "source_type": original_test.get("source_type", "manual"),
            "source_document_id": original_test.get("source_document_id"),
            "source_file_r2_key": original_test.get("source_file_r2_key"),
            "creator_id": user_info["uid"],
            "time_limit_minutes": original_test.get("time_limit_minutes", 30),
            "num_questions": len(new_questions),
            "max_retries": original_test.get("max_retries", 3),
            "creation_type": original_test.get("creation_type", "manual"),
            "status": original_test.get("status", "ready"),
            "progress_percent": original_test.get("progress_percent", 100),
            "questions": new_questions,
            "is_active": True,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            # Add metadata to track duplication
            "duplicated_from": test_id,
            "is_duplicate": True,
        }

        result = collection.insert_one(duplicated_doc)
        new_test_id = str(result.inserted_id)

        logger.info(f"✅ Test duplicated: {test_id} → {new_test_id}")

        return {
            "success": True,
            "test_id": new_test_id,
            "original_test_id": test_id,
            "title": new_title,
            "description": duplicated_doc["description"],
            "num_questions": len(new_questions),
            "status": duplicated_doc["status"],
            "created_at": duplicated_doc["created_at"].isoformat(),
            "message": f"Test duplicated successfully as '{new_title}'",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Test duplication failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{test_id}/status")
async def get_test_status(
    test_id: str,
    user_info: dict = Depends(require_auth),
):
    """
    Get test generation status (for polling)

    **NEW Endpoint for async pattern**

    Frontend polls this endpoint every 3 seconds to check if AI generation is complete.

    **Status Values:**
    - `pending`: Test queued, AI generation not started
    - `generating`: AI is generating questions
    - `ready`: Questions generated, test ready to take
    - `failed`: AI generation failed

    **Usage:**
    ```javascript
    const interval = setInterval(async () => {
      const status = await fetch(`/api/v1/tests/${testId}/status`);
      if (status.status === 'ready') {
        clearInterval(interval);
        loadQuestions();
      }
    }, 3000);
    ```
    """
    try:
        mongo_service = get_mongodb_service()
        collection = mongo_service.db["online_tests"]

        test = collection.find_one({"_id": ObjectId(test_id)})

        if not test:
            raise HTTPException(status_code=404, detail="Test not found")

        # Check access (owner, public, or shared)
        access_info = check_test_access(test_id, user_info["uid"], test)
        logger.info(
            f"   ✅ Status check access granted: type={access_info['access_type']}"
        )

        status = test.get("status", "pending")
        progress = test.get("progress_percent", 0)

        response = {
            "test_id": test_id,
            "status": status,
            "progress_percent": progress,
        }

        if status == "pending":
            response["message"] = "Test is queued for generation..."
        elif status == "generating":
            response["message"] = f"AI is generating questions... ({progress}%)"
        elif status == "ready":
            response.update(
                {
                    "message": "Test is ready to take!",
                    "title": test.get("title"),
                    "description": test.get("description"),
                    "num_questions": test.get("num_questions"),
                    "time_limit_minutes": test.get("time_limit_minutes"),
                    "created_at": test.get("created_at").isoformat(),
                    "generated_at": (
                        test.get("generated_at").isoformat()
                        if test.get("generated_at")
                        else None
                    ),
                }
            )
        elif status == "failed":
            response.update(
                {
                    "message": "Test generation failed. Please try again.",
                    "error_message": test.get("error_message"),
                }
            )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get test status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{test_id}")
async def get_test(
    test_id: str,
    user_info: dict = Depends(require_auth),
):
    """
    Get test details - response varies by access type

    **UPDATED**: Now returns different data based on user's relationship to test

    **Owner View:**
    - Full test configuration (all settings)
    - All questions with correct answers
    - Marketplace config (if published)
    - Statistics (participants, earnings, ratings)
    - Complete edit dashboard data

    **Public View (Marketplace):**
    - Marketplace info only (cover, price, description, difficulty)
    - No questions revealed
    - Community stats (participants, average score)
    - User's participation history

    **Shared View:**
    - Questions for taking (without correct answers)
    - Basic test info

    **Access Control:**
    - Owner: Full access to all data
    - Public: Marketplace data only
    - Shared: Questions for taking
    """
    try:
        logger.info(f"📖 Get test request: {test_id} from user {user_info['uid']}")

        # Get test
        mongo_service = get_mongodb_service()
        test = mongo_service.db["online_tests"].find_one({"_id": ObjectId(test_id)})

        if not test:
            raise HTTPException(status_code=404, detail="Test not found")

        # ========== Check access (owner, shared, or public) ==========
        access_info = check_test_access(test_id, user_info["uid"], test)
        logger.info(f"   ✅ Access granted: type={access_info['access_type']}")

        # ========== OWNER VIEW: Return full edit dashboard data ==========
        if access_info["is_owner"]:
            logger.info(f"   🔑 Owner view: returning full data")

            # Get statistics
            submissions_collection = mongo_service.db["test_submissions"]
            total_submissions = submissions_collection.count_documents(
                {"test_id": test_id}
            )

            marketplace_config = test.get("marketplace_config", {})
            is_published = marketplace_config.get("is_public", False)

            return {
                "success": True,
                "test_id": test_id,
                "view_type": "owner",
                "is_owner": True,
                "access_type": "owner",
                # Basic info
                "title": test.get("title"),
                "description": test.get("description"),
                "is_active": test.get("is_active", True),
                "status": test.get("status", "ready"),
                # Test settings
                "max_retries": test.get("max_retries"),
                "time_limit_minutes": test.get("time_limit_minutes"),
                "passing_score": test.get("passing_score"),
                "deadline": (
                    test.get("deadline").isoformat() if test.get("deadline") else None
                ),
                "show_answers_timing": test.get("show_answers_timing"),
                # Questions (with correct answers for owner)
                "num_questions": len(test.get("questions", [])),
                "questions": test.get("questions", []),
                # Creation info
                "creation_type": test.get("creation_type"),
                "test_language": test.get("test_language", test.get("language", "vi")),
                # Statistics
                "total_submissions": total_submissions,
                # Marketplace (if published)
                "is_published": is_published,
                "marketplace_config": marketplace_config if is_published else None,
                # Timestamps
                "created_at": test.get("created_at").isoformat(),
                "updated_at": (
                    test.get("updated_at").isoformat()
                    if test.get("updated_at")
                    else None
                ),
            }

        # ========== PUBLIC VIEW: Return marketplace data only ==========
        elif access_info["access_type"] == "public":
            logger.info(f"   🌍 Public view: returning marketplace data only")

            marketplace_config = test.get("marketplace_config", {})

            # Get user's participation history
            submissions_collection = mongo_service.db["test_submissions"]
            user_submissions = list(
                submissions_collection.find(
                    {"test_id": test_id, "user_id": user_info["uid"]}
                ).sort("submitted_at", -1)
            )

            already_participated = len(user_submissions) > 0
            attempts_used = len(user_submissions)
            user_best_score = (
                max([s.get("score_percentage", 0) for s in user_submissions])
                if user_submissions
                else None
            )

            return {
                "success": True,
                "test_id": test_id,
                "view_type": "public",
                "is_owner": False,
                "access_type": "public",
                # Marketplace info
                "title": marketplace_config.get("title", test.get("title")),
                "description": marketplace_config.get(
                    "description", test.get("description")
                ),
                "short_description": marketplace_config.get("short_description"),
                "cover_image_url": marketplace_config.get("cover_image_url"),
                # Test configuration (basic)
                "num_questions": len(test.get("questions", [])),
                "time_limit_minutes": test.get("time_limit_minutes"),
                "passing_score": test.get("passing_score"),
                "max_retries": test.get("max_retries"),
                # Marketplace metadata
                "price_points": marketplace_config.get("price_points", 0),
                "category": marketplace_config.get("category"),
                "tags": marketplace_config.get("tags", []),
                "difficulty_level": marketplace_config.get("difficulty_level"),
                "version": marketplace_config.get("version"),
                # Community statistics
                "total_participants": marketplace_config.get("total_participants", 0),
                "average_participant_score": marketplace_config.get(
                    "average_participant_score", 0.0
                ),
                "average_rating": marketplace_config.get("average_rating", 0.0),
                "rating_count": marketplace_config.get("rating_count", 0),
                # Publication info
                "published_at": (
                    marketplace_config.get("published_at").isoformat()
                    if marketplace_config.get("published_at")
                    else None
                ),
                "creator_id": test.get("creator_id"),
                # User-specific info
                "already_participated": already_participated,
                "attempts_used": attempts_used,
                "user_best_score": user_best_score,
                # Additional metadata
                "creation_type": test.get("creation_type"),
                "test_language": test.get("test_language", test.get("language", "vi")),
            }

        # ========== SHARED VIEW: Return questions for taking (no answers) ==========
        else:
            logger.info(f"   👥 Shared view: returning questions for taking")

            # Check is_active for shared access
            if not test.get("is_active", False):
                raise HTTPException(status_code=403, detail="Test is not active")

            # Check if test is ready
            status = test.get("status", "ready")
            if status != "ready":
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "TEST_NOT_READY",
                        "message": f"Test is not ready yet. Current status: {status}",
                        "current_status": status,
                        "progress_percent": test.get("progress_percent", 0),
                        "tip": f"Poll GET /api/v1/tests/{test_id}/status to check when ready",
                    },
                )

            # Get questions without correct answers
            test_generator = get_test_generator_service()
            test_data = await test_generator.get_test_for_taking(
                test_id, user_info["uid"]
            )

            # Add metadata
            test_data["status"] = "ready"
            test_data["description"] = test.get("description")
            test_data["access_type"] = access_info["access_type"]
            test_data["is_owner"] = False
            test_data["view_type"] = "shared"

            return test_data

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get test: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{test_id}/start")
async def start_test(
    test_id: str,
    user_info: dict = Depends(require_auth),
):
    """
    Start a new test session

    **UPDATED Phase 4**: Now supports shared access (owner OR shared users)

    Creates a session record and returns test questions.
    Phase 2 WebSocket support for real-time progress.

    **Access Control:**
    - Owner: Unlimited attempts
    - Shared: Subject to max_retries limit
    """
    try:
        logger.info(f"🚀 Start test: {test_id} for user {user_info['uid']}")

        # Check if user has already exceeded max attempts
        mongo_service = get_mongodb_service()
        test_collection = mongo_service.db["online_tests"]
        submissions_collection = mongo_service.db["test_submissions"]

        test_doc = test_collection.find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        # ========== Phase 4: Check access (owner or shared) ==========
        access_info = check_test_access(test_id, user_info["uid"], test_doc)
        is_creator = access_info["is_owner"]
        is_public = access_info.get("access_type") == "public"

        logger.info(f"   ✅ Access granted: type={access_info['access_type']}")

        if is_creator:
            logger.info(f"   👤 User is test creator - unlimited attempts allowed")

        # ========== Phase 5: Deduct points for public marketplace tests ==========
        marketplace_config = test_doc.get("marketplace_config", {})
        price_points = marketplace_config.get("price_points", 0)

        # Deduct points on EVERY attempt if:
        # 1. Test is public (marketplace)
        # 2. User is NOT the creator
        # 3. Test has a price
        should_deduct_points = is_public and not is_creator and price_points > 0

        if should_deduct_points:
            # Get user's current points
            users_collection = mongo_service.db["users"]
            # Query by firebase_uid (unified schema)
            user_doc = users_collection.find_one({"firebase_uid": user_info["uid"]})

            logger.info(f"   🔍 Debug user document:")
            logger.info(f"      User ID: {user_info['uid']}")
            logger.info(f"      Email: {user_info.get('email', 'N/A')}")
            logger.info(f"      User doc found: {user_doc is not None}")
            if user_doc:
                logger.info(f"      Points in doc: {user_doc.get('points', 'MISSING')}")
                logger.info(
                    f"      Earnings in doc: {user_doc.get('earnings_points', 'MISSING')}"
                )
                logger.info(
                    f"      Firebase UID: {user_doc.get('firebase_uid', 'MISSING')}"
                )

            # Auto-create or sync user profile if not exists
            if not user_doc:
                logger.info(
                    f"   📝 Creating unified user profile for {user_info['uid']}"
                )
                user_doc = {
                    "firebase_uid": user_info["uid"],  # Primary key (unified)
                    "uid": user_info["uid"],  # Alias for backward compatibility
                    "email": user_info.get("email", ""),
                    "display_name": user_info.get("name", ""),
                    "photo_url": user_info.get("picture", ""),
                    "email_verified": user_info.get("email_verified", False),
                    "provider": user_info.get("firebase", {}).get(
                        "sign_in_provider", "unknown"
                    ),
                    # Online test fields
                    "points": 0,
                    "earnings_points": 0,
                    "point_transactions": [],
                    "earnings_transactions": [],
                    # Auth system fields
                    "subscription_plan": "free",
                    "total_conversations": 0,
                    "total_files": 0,
                    "preferences": {
                        "default_ai_provider": "openai",
                        "theme": "light",
                        "language": "vi",
                    },
                    # Timestamps
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                    "last_login": datetime.utcnow(),
                }
                users_collection.insert_one(user_doc)
                logger.info(f"   ✅ Unified user profile created with 0 points")

            current_points = user_doc.get("points", 0)

            # Check if user has enough points
            if current_points < price_points:
                raise HTTPException(
                    status_code=402,  # Payment Required
                    detail=f"Insufficient points. You need {price_points} points but only have {current_points} points.",
                )

            # Count how many times user has started this test (for logging)
            progress_collection = mongo_service.db["test_progress"]
            previous_attempts = progress_collection.count_documents(
                {"test_id": test_id, "user_id": user_info["uid"]}
            )
            current_attempt_number = previous_attempts + 1

            # Deduct points from user (on EVERY attempt)
            new_points = current_points - price_points
            users_collection.update_one(
                {"firebase_uid": user_info["uid"]},  # Use firebase_uid
                {
                    "$set": {"points": new_points, "updated_at": datetime.utcnow()},
                    "$push": {
                        "point_transactions": {
                            "type": "deduct",
                            "amount": price_points,
                            "reason": f"Started test: {test_doc.get('title')} (Attempt #{current_attempt_number})",
                            "test_id": test_id,
                            "attempt_number": current_attempt_number,
                            "timestamp": datetime.utcnow(),
                            "balance_after": new_points,
                        }
                    },
                },
            )

            # ✅ BIDIRECTIONAL SYNC: Also update subscription.points_remaining
            subscriptions_collection = mongo_service.db["user_subscriptions"]
            subscription_doc = subscriptions_collection.find_one(
                {"user_id": user_info["uid"]}
            )
            if subscription_doc:
                points_used = subscription_doc.get("points_used", 0) + price_points
                subscriptions_collection.update_one(
                    {"user_id": user_info["uid"]},
                    {
                        "$set": {
                            "points_remaining": new_points,
                            "points_used": points_used,
                            "updated_at": datetime.utcnow(),
                        }
                    },
                )
                logger.info(
                    f"   ✅ Subscription synced: points_remaining updated to {new_points}"
                )

            # Update test's total earnings (increment on EVERY attempt)
            # This will be distributed to creator's earnings_points (80% of total)
            test_collection.update_one(
                {"_id": ObjectId(test_id)},
                {"$inc": {"marketplace_config.total_earnings": price_points}},
            )

            # Calculate creator's earnings (80% of price, rounded up)
            import math

            creator_earnings = math.ceil(price_points * 0.8)

            # Add to creator's earnings_points (separate from regular points)
            creator_id = test_doc.get("creator_id")
            users_collection.update_one(
                {"firebase_uid": creator_id},  # Use firebase_uid
                {
                    "$inc": {"earnings_points": creator_earnings},
                    "$push": {
                        "earnings_transactions": {
                            "type": "earn",
                            "amount": creator_earnings,
                            "original_amount": price_points,
                            "percentage": 80,
                            "reason": f"User started your test: {test_doc.get('title')} (Attempt #{current_attempt_number})",
                            "test_id": test_id,
                            "participant_id": user_info["uid"],
                            "attempt_number": current_attempt_number,
                            "timestamp": datetime.utcnow(),
                        }
                    },
                },
            )

            # Only increment participants count on FIRST attempt
            if current_attempt_number == 1:
                test_collection.update_one(
                    {"_id": ObjectId(test_id)},
                    {"$inc": {"marketplace_config.total_participants": 1}},
                )

            logger.info(
                f"   💰 Points deducted: {price_points} from user {user_info['uid']} (Attempt #{current_attempt_number})"
            )
            logger.info(f"   💰 Test earnings: +{price_points} (total accumulated)")
            logger.info(
                f"   💵 Creator earnings: +{creator_earnings} points ({price_points} × 80% = {creator_earnings})"
            )
            logger.info(f"   📊 User balance: {current_points} → {new_points}")

        # Get test data
        test_generator = get_test_generator_service()
        test_data = await test_generator.get_test_for_taking(test_id, user_info["uid"])

        max_retries = test_doc.get("max_retries", 1)

        # Count user's attempts from BOTH submissions AND active sessions
        # This prevents users from starting multiple sessions to bypass retry limit
        progress_collection = mongo_service.db["test_progress"]

        # Count completed submissions
        completed_submissions = submissions_collection.count_documents(
            {
                "test_id": test_id,
                "user_id": user_info["uid"],
            }
        )

        # Count existing sessions (completed or not)
        existing_sessions = progress_collection.count_documents(
            {
                "test_id": test_id,
                "user_id": user_info["uid"],
            }
        )

        # Total attempts = max of submissions or sessions
        # (in case of orphaned sessions without submissions)
        attempts_used = max(completed_submissions, existing_sessions)

        # Current attempt number (this new session)
        current_attempt = attempts_used + 1

        # Check if exceeds limit BEFORE creating new session
        # BUT skip check if user is the creator (owner has unlimited attempts)
        if (
            not is_creator
            and max_retries != "unlimited"
            and current_attempt > max_retries
        ):
            raise HTTPException(
                status_code=429,
                detail=f"Maximum attempts ({max_retries}) exceeded. You have used {attempts_used} attempts.",
            )

        # Create session in test_progress (Phase 2 feature, but prepare now)
        import uuid

        session_id = str(uuid.uuid4())

        progress_collection.insert_one(
            {
                "session_id": session_id,
                "test_id": test_id,
                "user_id": user_info["uid"],
                "current_answers": {},  # ✅ Dict/object, not array
                "started_at": datetime.now(),
                "last_saved_at": datetime.now(),
                "time_remaining_seconds": test_data["time_limit_minutes"] * 60,
                "is_completed": False,
                "attempt_number": current_attempt,  # Track which attempt this is
            }
        )

        logger.info(
            f"   ✅ Session created: {session_id} (Attempt {current_attempt}/{max_retries if not is_creator else 'unlimited'})"
        )

        # Calculate time values for frontend
        time_limit_seconds = test_data["time_limit_minutes"] * 60
        time_remaining_seconds = time_limit_seconds  # Full time at start

        return {
            "success": True,
            "session_id": session_id,
            "test": test_data,
            # Attempt tracking
            "current_attempt": current_attempt,  # Lần thử hiện tại (1, 2, 3...)
            "max_attempts": (
                "unlimited" if is_creator else max_retries
            ),  # Creator = unlimited
            "attempts_remaining": (
                "unlimited"
                if is_creator
                else (
                    max_retries - current_attempt
                    if max_retries != "unlimited"
                    else "unlimited"
                )
            ),
            "is_creator": is_creator,  # NEW: Frontend biết user có phải creator
            # Time tracking
            "time_limit_seconds": time_limit_seconds,
            "time_remaining_seconds": time_remaining_seconds,
            "is_completed": False,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to start test: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{test_id}/submit")
async def submit_test(
    test_id: str,
    request: SubmitTestRequest,
    background_tasks: BackgroundTasks,
    user_info: dict = Depends(require_auth),
):
    """
    Submit test answers and get results

    **UPDATED Phase 4**: Now supports shared access and sends completion notifications

    Scores the test and returns detailed results with explanations.

    **Access Control:**
    - Owner: Can submit (for testing purposes)
    - Shared: Can submit according to max_retries limit

    **Phase 4 Features:**
    - Marks shared test as "completed" status
    - Sends email notification to test owner when shared user completes
    """
    try:
        logger.info(f"📤 Submit test: {test_id} from user {user_info['uid']}")
        logger.info(f"   Answers: {len(request.user_answers)} questions")

        # Get test with correct answers
        mongo_service = get_mongodb_service()
        test_collection = mongo_service.db["online_tests"]

        test_doc = test_collection.find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        # ========== Phase 5: Check access first (owner, shared, or public) ==========
        access_info = check_test_access(test_id, user_info["uid"], test_doc)
        is_owner = access_info["is_owner"]

        logger.info(f"   ✅ Access granted: type={access_info['access_type']}")

        # Check is_active ONLY for non-public tests
        # Public marketplace tests are always available regardless of is_active status
        if access_info["access_type"] != "public" and not test_doc.get(
            "is_active", False
        ):
            raise HTTPException(status_code=410, detail="Test is no longer active")

        # Score the test
        questions = test_doc["questions"]
        total_questions = len(questions)
        correct_count = 0
        results = []

        # Create answer map for quick lookup
        user_answers_map = {
            ans["question_id"]: ans["selected_answer_key"]
            for ans in request.user_answers
        }

        for q in questions:
            question_id = q["question_id"]
            correct_answer = q["correct_answer_key"]
            user_answer = user_answers_map.get(question_id, None)

            is_correct = user_answer == correct_answer
            if is_correct:
                correct_count += 1

            results.append(
                {
                    "question_id": question_id,
                    "question_text": q["question_text"],
                    "your_answer": user_answer,
                    "correct_answer": correct_answer,
                    "is_correct": is_correct,
                    "explanation": q["explanation"],
                }
            )

        # Calculate score (thang điểm 10)
        score_percentage = (
            (correct_count / total_questions * 100) if total_questions > 0 else 0
        )
        score_out_of_10 = (
            round(correct_count / total_questions * 10, 2) if total_questions > 0 else 0
        )

        # Check if passed based on test's passing_score setting
        passing_score = test_doc.get("passing_score", 70)  # Default 70%
        is_passed = score_percentage >= passing_score

        # ========== Validate time limit ==========
        # Get session to check started_at time
        progress_collection = mongo_service.db["test_progress"]
        session = progress_collection.find_one(
            {"test_id": test_id, "user_id": user_info["uid"], "is_completed": False},
            sort=[("started_at", -1)],  # Get most recent session
        )

        time_taken_seconds = 0
        if session and session.get("started_at"):
            started_at = session.get("started_at")
            submitted_at = datetime.now()
            time_taken_seconds = int((submitted_at - started_at).total_seconds())

            # Check if exceeded time limit
            time_limit_seconds = test_doc.get("time_limit_minutes", 30) * 60

            if time_taken_seconds > time_limit_seconds:
                # Time exceeded - reject submission and return latest result
                logger.warning(
                    f"⏰ Time limit exceeded: {time_taken_seconds}s > {time_limit_seconds}s"
                )

                # Get latest submission if exists
                submissions_collection = mongo_service.db["test_submissions"]
                latest_submission = submissions_collection.find_one(
                    {
                        "test_id": test_id,
                        "user_id": user_info["uid"],
                    },
                    sort=[("submitted_at", -1)],
                )

                if latest_submission:
                    # Return latest submission result
                    return {
                        "success": False,
                        "error": "time_limit_exceeded",
                        "message": f"Thời gian làm bài đã hết ({time_limit_seconds // 60} phút). Kết quả được lấy từ lần nộp gần nhất.",
                        "time_taken_seconds": time_taken_seconds,
                        "time_limit_seconds": time_limit_seconds,
                        "latest_submission": {
                            "submission_id": str(latest_submission["_id"]),
                            "score": latest_submission.get("score", 0),
                            "score_percentage": latest_submission.get(
                                "score_percentage", 0
                            ),
                            "is_passed": latest_submission.get("is_passed", False),
                            "submitted_at": latest_submission.get(
                                "submitted_at"
                            ).isoformat(),
                        },
                    }
                else:
                    # No previous submission - fail with 0 score
                    raise HTTPException(
                        status_code=422,
                        detail={
                            "error": "time_limit_exceeded",
                            "message": f"Thời gian làm bài đã hết ({time_limit_seconds // 60} phút) và không có lần nộp bài nào trước đó.",
                            "time_taken_seconds": time_taken_seconds,
                            "time_limit_seconds": time_limit_seconds,
                        },
                    )

        logger.info(f"   ⏱️ Time taken: {time_taken_seconds}s")

        # Count attempt number
        submissions_collection = mongo_service.db["test_submissions"]
        attempt_number = (
            submissions_collection.count_documents(
                {
                    "test_id": test_id,
                    "user_id": user_info["uid"],
                }
            )
            + 1
        )

        # Save submission
        submission_doc = {
            "test_id": test_id,
            "user_id": user_info["uid"],
            "user_answers": request.user_answers,
            "score": score_out_of_10,  # Thang điểm 10
            "score_percentage": score_percentage,  # Phần trăm (for reference)
            "total_questions": total_questions,
            "correct_answers": correct_count,
            "time_taken_seconds": time_taken_seconds,  # Calculated from started_at
            "attempt_number": attempt_number,
            "is_passed": is_passed,  # ✅ Fixed: Use test's passing_score
            "submitted_at": datetime.now(),
        }

        result = submissions_collection.insert_one(submission_doc)
        submission_id = str(result.inserted_id)

        # Mark session as completed (if exists)
        progress_collection = mongo_service.db["test_progress"]
        progress_collection.update_many(
            {"test_id": test_id, "user_id": user_info["uid"], "is_completed": False},
            {"$set": {"is_completed": True, "last_saved_at": datetime.now()}},
        )

        # ========== Phase 4: Mark shared test as completed ==========
        if not is_owner:
            sharing_service = get_test_sharing_service()
            sharing_service.mark_test_completed(test_id, user_info["uid"])
            logger.info(f"   ✅ Marked shared test as completed")

            # Send completion notification to owner (background task)
            async def send_completion_notification():
                try:
                    from src.services.brevo_email_service import get_brevo_service

                    # Get owner info
                    owner_id = test_doc.get("creator_id")
                    owner = mongo_service.db.users.find_one({"firebase_uid": owner_id})

                    # Get user info
                    user = mongo_service.db.users.find_one(
                        {"firebase_uid": user_info["uid"]}
                    )

                    if owner and user:
                        owner_email = owner.get("email")
                        owner_name = (
                            owner.get("name") or owner.get("display_name") or "Owner"
                        )
                        user_name = (
                            user.get("name")
                            or user.get("display_name")
                            or user.get("email", "Someone")
                        )

                        # Calculate time taken (placeholder for now)
                        time_taken_minutes = (
                            submission_doc.get("time_taken_seconds", 0) // 60
                        )

                        brevo = get_brevo_service()
                        await asyncio.to_thread(
                            brevo.send_test_completion_notification,
                            to_email=owner_email,
                            owner_name=owner_name,
                            user_name=user_name,
                            test_title=test_doc["title"],
                            score=score_out_of_10,
                            is_passed=submission_doc["is_passed"],
                            time_taken_minutes=max(1, time_taken_minutes),
                        )
                        logger.info(
                            f"   📧 Sent completion email to owner {owner_email}"
                        )
                except Exception as e:
                    logger.error(f"   ⚠️ Failed to send completion notification: {e}")

            background_tasks.add_task(send_completion_notification)

        logger.info(
            f"✅ Test submitted: score={score_out_of_10:.2f}/10 "
            f"({score_percentage:.1f}%), attempt={attempt_number}"
        )

        # ========== NEW: Check show_answers_timing setting ==========
        show_answers_timing = test_doc.get("show_answers_timing", "immediate")
        deadline = test_doc.get("deadline")
        should_hide_answers = False

        if show_answers_timing == "after_deadline" and deadline:
            # Make deadline timezone-aware if needed
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)

            current_time = datetime.now(timezone.utc)

            # Hide answers if deadline not passed yet
            if current_time < deadline:
                should_hide_answers = True
                logger.info(
                    f"   🔒 Hiding answers until deadline: {deadline.isoformat()}"
                )

        # Build response based on show_answers_timing
        if not should_hide_answers:
            # Full response - show everything
            response = {
                "success": True,
                "submission_id": submission_id,
                "score": score_out_of_10,  # Thang điểm 10
                "score_percentage": score_percentage,  # Phần trăm
                "total_questions": total_questions,
                "correct_answers": correct_count,
                "attempt_number": attempt_number,
                "is_passed": is_passed,
                "results": results,
            }
        else:
            # Limited response - hide detailed results and attempt number
            response = {
                "success": True,
                "submission_id": submission_id,
                "score": score_out_of_10,  # Thang điểm 10
                "score_percentage": score_percentage,  # Phần trăm
                "total_questions": total_questions,
                "correct_answers": correct_count,  # Still show total correct count
                "is_passed": is_passed,
                "results_hidden_until_deadline": deadline.isoformat(),
                "message": "Detailed answers will be revealed after the deadline",
            }

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Test submission failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{test_id}/sync-answers")
async def sync_answers(
    test_id: str,
    request: dict,
    user_info: dict = Depends(require_auth),
):
    """
    Sync answers to session (HTTP endpoint for reconnection)

    **Use case**: Frontend reconnect sau khi mất kết nối WebSocket

    Frontend gửi FULL answers để sync với backend. Backend sẽ overwrite
    toàn bộ current_answers của session.

    **Request Body:**
    ```json
    {
        "session_id": "uuid-string",
        "answers": {
            "question_id_1": "A",
            "question_id_2": "B",
            ...
        }
    }
    ```

    **Response:**
    ```json
    {
        "success": true,
        "session_id": "uuid-string",
        "answers_count": 5,
        "saved_at": "2025-11-15T10:30:00Z"
    }
    ```
    """
    try:
        session_id = request.get("session_id")
        answers = request.get("answers", {})

        if not session_id:
            raise HTTPException(
                status_code=400, detail="Missing required field: session_id"
            )

        logger.info(
            f"🔄 Sync answers for session {session_id[:8]}... "
            f"from user {user_info['uid']}: {len(answers)} answers"
        )

        # Get session and verify ownership
        mongo_service = get_mongodb_service()
        progress_collection = mongo_service.db["test_progress"]

        session = progress_collection.find_one({"session_id": session_id})

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Verify session belongs to user
        if session.get("user_id") != user_info["uid"]:
            raise HTTPException(
                status_code=403, detail="Session does not belong to user"
            )

        # Check if session is already completed
        if session.get("is_completed"):
            raise HTTPException(status_code=410, detail="Session already completed")

        # Check if time has expired
        test_collection = mongo_service.db["online_tests"]
        test = test_collection.find_one({"_id": ObjectId(test_id)})

        if not test:
            raise HTTPException(status_code=404, detail="Test not found")

        time_limit_seconds = test.get("time_limit_minutes", 30) * 60
        started_at = session.get("started_at")

        if started_at:
            elapsed_seconds = (datetime.now() - started_at).total_seconds()
            if elapsed_seconds > time_limit_seconds:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "time_expired",
                        "message": "Thời gian làm bài đã hết. Không thể sync answers.",
                        "elapsed_seconds": int(elapsed_seconds),
                        "time_limit_seconds": time_limit_seconds,
                    },
                )

        # Update answers in database (overwrite)
        result = progress_collection.update_one(
            {"session_id": session_id, "is_completed": False},
            {
                "$set": {
                    "current_answers": answers,  # Overwrite với full data
                    "last_saved_at": datetime.now(),
                }
            },
        )

        if result.modified_count == 0:
            raise HTTPException(
                status_code=500,
                detail="Failed to sync answers. Session may be inactive.",
            )

        saved_at = datetime.now()
        logger.info(f"✅ Synced {len(answers)} answers for session {session_id[:8]}...")

        return {
            "success": True,
            "session_id": session_id,
            "answers_count": len(answers),
            "saved_at": saved_at.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to sync answers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/me/tests")
async def get_my_tests(
    limit: int = 10,
    offset: int = 0,
    user_info: dict = Depends(require_auth),
):
    """
    Get paginated list of tests created by the current user

    **IMPORTANT:** With router prefix, this becomes /api/v1/tests/me/tests
    But documentation says it should be /api/v1/me/tests
    Use the user_router version below for correct path.

    **Phase 1 Feature**

    Args:
        limit: Number of tests to return (default 10, max 100)
        offset: Number of tests to skip (default 0)
    """
    try:
        logger.info(
            f"📋 Get my tests for user {user_info['uid']} (limit={limit}, offset={offset})"
        )

        # Validate pagination params
        if limit > 100:
            limit = 100
        if offset < 0:
            offset = 0

        mongo_service = get_mongodb_service()
        test_collection = mongo_service.db["online_tests"]
        submissions_collection = mongo_service.db["test_submissions"]

        # Get total count
        total_count = test_collection.count_documents({"creator_id": user_info["uid"]})

        # Get user's created tests with pagination, sorted by updated_at (latest first)
        tests = list(
            test_collection.find({"creator_id": user_info["uid"]})
            .sort(
                [("updated_at", -1), ("created_at", -1)]
            )  # Latest edited/created first
            .skip(offset)
            .limit(limit)
        )

        # Build result with minimal info for list view
        result = []
        for test in tests:
            test_id = str(test["_id"])
            attempts_count = submissions_collection.count_documents(
                {"test_id": test_id}
            )

            result.append(
                {
                    "test_id": test_id,
                    "title": test["title"],
                    "description": test.get("description"),  # Optional field
                    "num_questions": len(test.get("questions", [])),
                    "time_limit_minutes": test["time_limit_minutes"],
                    "status": test.get(
                        "status", "ready"
                    ),  # pending, generating, ready, failed, draft
                    "is_active": test.get("is_active", True),
                    "created_at": test["created_at"].isoformat(),
                    "updated_at": test.get(
                        "updated_at", test["created_at"]
                    ).isoformat(),
                    "total_submissions": attempts_count,
                }
            )

        return {
            "tests": result,
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total_count,
        }

    except Exception as e:
        logger.error(f"❌ Failed to get tests: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/me/submissions")
async def get_my_submissions(
    user_info: dict = Depends(require_auth),
):
    """
    Get list of test submissions by the current user

    **Phase 1 Feature**
    """
    try:
        logger.info(f"📊 Get my submissions for user {user_info['uid']}")

        mongo_service = get_mongodb_service()
        submissions_collection = mongo_service.db["test_submissions"]
        test_collection = mongo_service.db["online_tests"]

        # Get user's submissions
        submissions = list(
            submissions_collection.find(
                {"user_id": user_info["uid"]}, sort=[("submitted_at", -1)]
            )
        )

        # Enrich with test details
        result = []
        for sub in submissions:
            test_id = sub["test_id"]
            test_doc = test_collection.find_one({"_id": ObjectId(test_id)})

            if test_doc:
                result.append(
                    {
                        "submission_id": str(sub["_id"]),
                        "test_id": test_id,
                        "test_title": test_doc["title"],
                        "score": sub["score"],
                        "correct_answers": sub["correct_answers"],
                        "total_questions": sub["total_questions"],
                        "is_passed": sub.get("is_passed", False),
                        "attempt_number": sub["attempt_number"],
                        "submitted_at": sub["submitted_at"].isoformat(),
                    }
                )

        return {"submissions": result}

    except Exception as e:
        logger.error(f"❌ Failed to get submissions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/me/submissions/{submission_id}")
async def get_submission_detail(
    submission_id: str,
    user_info: dict = Depends(require_auth),
):
    """
    Get detailed results of a specific submission

    **Phase 1 Feature**
    """
    try:
        logger.info(f"🔍 Get submission detail: {submission_id}")

        mongo_service = get_mongodb_service()
        submissions_collection = mongo_service.db[
            "test_submissions"
        ]  # ✅ Correct collection

        submission = submissions_collection.find_one({"_id": ObjectId(submission_id)})

        if not submission:
            raise HTTPException(status_code=404, detail="Submission not found")

        if submission["user_id"] != user_info["uid"]:
            raise HTTPException(status_code=403, detail="Access denied")

        # Get test for question details
        test_collection = mongo_service.db["online_tests"]
        test_doc = test_collection.find_one({"_id": ObjectId(submission["test_id"])})

        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        # Build results with explanations
        results = []
        user_answers_map = {
            ans["question_id"]: ans["selected_answer_key"]
            for ans in submission["user_answers"]
        }

        for q in test_doc["questions"]:
            question_id = q["question_id"]
            user_answer = user_answers_map.get(question_id)
            is_correct = user_answer == q["correct_answer_key"]

            results.append(
                {
                    "question_id": question_id,
                    "question_text": q["question_text"],
                    "options": q["options"],
                    "your_answer": user_answer,
                    "correct_answer": q["correct_answer_key"],
                    "is_correct": is_correct,
                    "explanation": q["explanation"],
                }
            )

        # ========== NEW: Check show_answers_timing setting ==========
        show_answers_timing = test_doc.get("show_answers_timing", "immediate")
        deadline = test_doc.get("deadline")
        should_hide_answers = False

        if show_answers_timing == "after_deadline" and deadline:
            # Make deadline timezone-aware if needed
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)

            current_time = datetime.now(timezone.utc)

            # Hide answers if deadline not passed yet
            if current_time < deadline:
                should_hide_answers = True
                logger.info(
                    f"   🔒 Hiding detailed answers until deadline: {deadline.isoformat()}"
                )

        # Build response based on show_answers_timing
        if not should_hide_answers:
            # Full response - show everything
            response = {
                "submission_id": submission_id,
                "test_title": test_doc["title"],
                "score": submission["score"],  # Thang điểm 10
                "score_percentage": submission.get(
                    "score_percentage", submission["score"] * 10
                ),  # Fallback for old data
                "total_questions": submission["total_questions"],
                "correct_answers": submission["correct_answers"],
                "time_taken_seconds": submission.get("time_taken_seconds", 0),
                "attempt_number": submission["attempt_number"],
                "is_passed": submission.get("is_passed", False),
                "submitted_at": submission["submitted_at"].isoformat(),
                "results": results,
            }
        else:
            # Limited response - only basic info, NO detailed results
            response = {
                "submission_id": submission_id,
                "test_title": test_doc["title"],
                "score": submission["score"],  # Thang điểm 10
                "score_percentage": submission.get(
                    "score_percentage", submission["score"] * 10
                ),
                "total_questions": submission["total_questions"],
                "correct_answers": submission["correct_answers"],  # Still show count
                "is_passed": submission.get("is_passed", False),
                "submitted_at": submission["submitted_at"].isoformat(),
                "results_hidden_until_deadline": deadline.isoformat(),
                "message": "Detailed answers and explanations will be revealed after the deadline",
            }

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get submission detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Phase 2: HTTP Fallback Endpoints for Real-time Progress ==========


class SaveProgressRequest(BaseModel):
    """Request model for saving progress (HTTP fallback)"""

    session_id: str = Field(..., description="Session ID from /start endpoint")
    answers: dict = Field(
        ..., description="Current answers dict (question_id -> answer_key)"
    )
    time_remaining_seconds: Optional[int] = Field(
        None, description="Time remaining in seconds"
    )


class ProgressResponse(BaseModel):
    """Response model for progress retrieval"""

    session_id: str
    current_answers: dict
    time_remaining_seconds: Optional[int]
    started_at: str
    last_saved_at: str
    is_completed: bool


@router.post(
    "/{test_id}/progress/save", response_model=dict, tags=["Phase 2 - Auto-save"]
)
async def save_test_progress(
    test_id: str,
    request: SaveProgressRequest,
    user_info: dict = Depends(require_auth),
):
    """
    HTTP fallback for saving test progress (for clients without WebSocket)
    Saves current answers and time remaining to database
    """
    try:
        user_id = user_info["uid"]
        mongo_service = get_mongodb_service()

        # Verify test exists
        test_doc = mongo_service.db["online_tests"].find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        # Verify session exists and belongs to user
        session = mongo_service.db["test_progress"].find_one(
            {"session_id": request.session_id}
        )

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        if session["user_id"] != user_id:
            raise HTTPException(
                status_code=403, detail="Session does not belong to user"
            )

        if str(session["test_id"]) != test_id:
            raise HTTPException(
                status_code=400, detail="Session does not belong to this test"
            )

        if session.get("is_completed"):
            raise HTTPException(status_code=409, detail="Session already completed")

        # Update progress in database
        update_data = {
            "current_answers": request.answers,
            "last_saved_at": datetime.utcnow(),
        }

        if request.time_remaining_seconds is not None:
            update_data["time_remaining_seconds"] = request.time_remaining_seconds

        result = mongo_service.db["test_progress"].update_one(
            {"session_id": request.session_id}, {"$set": update_data}
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=500, detail="Failed to save progress")

        logger.info(
            f"💾 Saved progress for session {request.session_id}: "
            f"{len(request.answers)} answers"
        )

        return {
            "success": True,
            "session_id": request.session_id,
            "saved_at": datetime.utcnow().isoformat(),
            "answers_count": len(request.answers),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to save progress: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{test_id}/progress", response_model=ProgressResponse, tags=["Phase 2 - Auto-save"]
)
async def get_test_progress(
    test_id: str,
    session_id: str,
    user_info: dict = Depends(require_auth),
):
    """
    Get current test progress (HTTP fallback)
    Useful for resuming tests after reconnection or page refresh
    """
    try:
        user_id = user_info["uid"]
        mongo_service = get_mongodb_service()

        # Verify test exists
        test_doc = mongo_service.db["online_tests"].find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        # Get session progress
        session = mongo_service.db["test_progress"].find_one({"session_id": session_id})

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        if session["user_id"] != user_id:
            raise HTTPException(
                status_code=403, detail="Session does not belong to user"
            )

        if str(session["test_id"]) != test_id:
            raise HTTPException(
                status_code=400, detail="Session does not belong to this test"
            )

        return ProgressResponse(
            session_id=session["session_id"],
            current_answers=session.get("current_answers", {}),
            time_remaining_seconds=session.get("time_remaining_seconds"),
            started_at=session["started_at"].isoformat(),
            last_saved_at=session.get(
                "last_saved_at", session["started_at"]
            ).isoformat(),
            is_completed=session.get("is_completed", False),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get progress: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{test_id}/resume", response_model=dict, tags=["Phase 2 - Auto-save"])
async def resume_test_session(
    test_id: str,
    user_info: dict = Depends(require_auth),
):
    """
    Resume an incomplete test session
    Returns the most recent session if one exists
    """
    try:
        user_id = user_info["uid"]
        mongo_service = get_mongodb_service()

        # Verify test exists
        test_doc = mongo_service.db["online_tests"].find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        # Find most recent incomplete session for this user and test
        session = mongo_service.db["test_progress"].find_one(
            {"user_id": user_id, "test_id": ObjectId(test_id), "is_completed": False},
            sort=[("started_at", -1)],
        )

        if not session:
            raise HTTPException(
                status_code=404,
                detail="No incomplete session found. Please start a new test.",
            )

        # Calculate elapsed time
        elapsed_seconds = int(
            (datetime.utcnow() - session["started_at"]).total_seconds()
        )
        time_limit_seconds = test_doc["time_limit_minutes"] * 60
        time_remaining = max(0, time_limit_seconds - elapsed_seconds)

        # If time ran out, mark session as completed and return error
        if time_remaining == 0:
            mongo_service.db["test_progress"].update_one(
                {"_id": session["_id"]}, {"$set": {"is_completed": True}}
            )
            raise HTTPException(
                status_code=410,
                detail="Session expired due to time limit. Please start a new test.",
            )

        # Update time remaining in database
        mongo_service.db["test_progress"].update_one(
            {"_id": session["_id"]},
            {"$set": {"time_remaining_seconds": time_remaining}},
        )

        return {
            "session_id": session["session_id"],
            "current_answers": session.get("current_answers", {}),
            "time_limit_seconds": time_limit_seconds,
            "time_remaining_seconds": time_remaining,
            "is_completed": False,
            "started_at": session["started_at"].isoformat(),
            "last_saved_at": session.get(
                "last_saved_at", session["started_at"]
            ).isoformat(),
            "message": "Session resumed successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to resume session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Phase 3: Test Configuration & Editing ==========


class UpdateTestConfigRequest(BaseModel):
    """Request model for updating test configuration"""

    max_retries: Optional[int] = Field(
        None, description="Max retry attempts", ge=1, le=20
    )
    time_limit_minutes: Optional[int] = Field(
        None, description="Time limit in minutes", ge=1, le=300
    )
    passing_score: Optional[int] = Field(
        None, description="Minimum score percentage to pass (0-100)", ge=0, le=100
    )
    deadline: Optional[datetime] = Field(
        None, description="Global deadline for all users (ISO 8601 format)"
    )
    show_answers_timing: Optional[str] = Field(
        None,
        description="When to show answers: 'immediate' or 'after_deadline'",
    )
    is_active: Optional[bool] = Field(None, description="Active status")
    title: Optional[str] = Field(None, description="Test title", max_length=200)
    description: Optional[str] = Field(
        None, description="Test description", max_length=1000
    )


class UpdateTestQuestionsRequest(BaseModel):
    """Request model for updating test questions"""

    questions: list = Field(..., description="Updated questions array")


class UpdateMarketplaceConfigRequest(BaseModel):
    """Request model for updating marketplace configuration"""

    title: Optional[str] = Field(
        None, description="Marketplace title", min_length=10, max_length=200
    )
    description: Optional[str] = Field(
        None, description="Full description", min_length=50, max_length=2000
    )
    short_description: Optional[str] = Field(
        None, description="Short description for cards", max_length=150
    )
    price_points: Optional[int] = Field(None, description="Price in points", ge=0)
    category: Optional[str] = Field(None, description="Test category")
    tags: Optional[str] = Field(None, description="Comma-separated tags")
    difficulty_level: Optional[str] = Field(None, description="Difficulty level")
    is_public: Optional[bool] = Field(
        None, description="Public status (unpublish if False)"
    )


class FullTestEditRequest(BaseModel):
    """Request model for comprehensive test editing (owner only)"""

    # Basic config
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    is_active: Optional[bool] = None

    # Test settings
    max_retries: Optional[int] = Field(None, ge=1, le=20)
    time_limit_minutes: Optional[int] = Field(None, ge=1, le=300)
    passing_score: Optional[int] = Field(None, ge=0, le=100)
    deadline: Optional[datetime] = None
    show_answers_timing: Optional[str] = None

    # Questions
    questions: Optional[list] = None

    # Attachments (NEW)
    attachments: Optional[list[TestAttachment]] = Field(
        None,
        description="List of PDF attachments for reading comprehension",
    )

    # Marketplace config (if published)
    marketplace_title: Optional[str] = Field(None, min_length=10, max_length=200)
    marketplace_description: Optional[str] = Field(None, min_length=50, max_length=2000)
    short_description: Optional[str] = Field(None, max_length=150)
    price_points: Optional[int] = Field(None, ge=0)
    category: Optional[str] = None
    tags: Optional[str] = None
    difficulty_level: Optional[str] = None


class TestPreviewResponse(BaseModel):
    """Response model for test preview (including correct answers)"""

    test_id: str
    title: str
    time_limit_minutes: int
    max_retries: int
    is_active: bool
    total_questions: int
    questions: list
    created_at: str
    updated_at: str


@router.patch("/{test_id}/config", response_model=dict, tags=["Phase 3 - Editing"])
async def update_test_config(
    test_id: str,
    request: UpdateTestConfigRequest,
    user_info: dict = Depends(require_auth),
):
    """
    Update test configuration (max_retries, time_limit, status, title, description)
    Only the test creator can update configuration
    """
    try:
        user_id = user_info["uid"]
        mongo_service = get_mongodb_service()

        # Verify test exists and user is creator
        test_doc = mongo_service.db["online_tests"].find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        if test_doc["creator_id"] != user_id:
            raise HTTPException(
                status_code=403,
                detail="Only the test creator can update configuration",
            )

        # Build update data
        update_data = {"updated_at": datetime.utcnow()}

        if request.max_retries is not None:
            update_data["max_retries"] = request.max_retries

        if request.time_limit_minutes is not None:
            update_data["time_limit_minutes"] = request.time_limit_minutes

        if request.passing_score is not None:
            update_data["passing_score"] = request.passing_score

        if request.deadline is not None:
            update_data["deadline"] = request.deadline

        if request.show_answers_timing is not None:
            # Validate value
            if request.show_answers_timing not in ["immediate", "after_deadline"]:
                raise HTTPException(
                    status_code=400,
                    detail="show_answers_timing must be 'immediate' or 'after_deadline'",
                )
            update_data["show_answers_timing"] = request.show_answers_timing

        if request.is_active is not None:
            update_data["is_active"] = request.is_active

        if request.title is not None:
            update_data["title"] = request.title

        if request.description is not None:
            update_data["description"] = request.description

        # Update in database
        result = mongo_service.db["online_tests"].update_one(
            {"_id": ObjectId(test_id)}, {"$set": update_data}
        )

        if result.modified_count == 0:
            raise HTTPException(
                status_code=500, detail="Failed to update configuration"
            )

        logger.info(f"✅ Updated configuration for test {test_id}")

        return {
            "success": True,
            "test_id": test_id,
            "updated_fields": list(update_data.keys()),
            "updated_at": update_data["updated_at"].isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update test config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{test_id}/questions", response_model=dict, tags=["Phase 3 - Editing"])
async def update_test_questions(
    test_id: str,
    request: UpdateTestQuestionsRequest,
    user_info: dict = Depends(require_auth),
):
    """
    Update test questions and answers
    Only the test creator can edit questions
    Validates question structure before saving
    """
    try:
        user_id = user_info["uid"]
        mongo_service = get_mongodb_service()

        # Verify test exists and user is creator
        test_doc = mongo_service.db["online_tests"].find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        if test_doc["creator_id"] != user_id:
            raise HTTPException(
                status_code=403, detail="Only the test creator can edit questions"
            )

        # Validate questions structure
        if not request.questions or len(request.questions) == 0:
            raise HTTPException(
                status_code=400, detail="At least one question is required"
            )

        if len(request.questions) > 100:
            raise HTTPException(status_code=400, detail="Maximum 100 questions allowed")

        for idx, q in enumerate(request.questions):
            # Validate required fields
            if not q.get("question_text"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Question {idx + 1}: question_text is required",
                )

            if not q.get("options") or len(q["options"]) < 2:
                raise HTTPException(
                    status_code=400,
                    detail=f"Question {idx + 1}: At least 2 options are required",
                )

            # Support both correct_answer_key (string) and correct_answer_keys (array)
            has_correct_answer_key = q.get("correct_answer_key")
            has_correct_answer_keys = q.get("correct_answer_keys")

            if not has_correct_answer_key and not has_correct_answer_keys:
                raise HTTPException(
                    status_code=400,
                    detail=f"Question {idx + 1}: correct_answer_key or correct_answer_keys is required",
                )

            # Get option keys for validation
            option_keys = [opt.get("key") for opt in q["options"]]

            # Normalize to correct_answer_keys array format
            if has_correct_answer_keys:
                # Ensure it's an array
                if isinstance(q["correct_answer_keys"], str):
                    q["correct_answer_keys"] = [q["correct_answer_keys"]]

                # Validate all correct answers exist in options
                for ans in q["correct_answer_keys"]:
                    if ans not in option_keys:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Question {idx + 1}: correct answer '{ans}' not found in options {option_keys}",
                        )

                # Also set correct_answer_key for backwards compatibility (first correct answer)
                q["correct_answer_key"] = q["correct_answer_keys"][0]

            elif has_correct_answer_key:
                # Old format: single correct answer
                if q["correct_answer_key"] not in option_keys:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Question {idx + 1}: correct_answer_key '{q['correct_answer_key']}' "
                        f"not found in options {option_keys}",
                    )

                # Convert to new format
                q["correct_answer_keys"] = [q["correct_answer_key"]]

            # Ensure question_id exists (generate if missing)
            if not q.get("question_id"):
                q["question_id"] = str(ObjectId())

        # Update questions in database
        result = mongo_service.db["online_tests"].update_one(
            {"_id": ObjectId(test_id)},
            {"$set": {"questions": request.questions, "updated_at": datetime.utcnow()}},
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=500, detail="Failed to update questions")

        logger.info(f"✅ Updated {len(request.questions)} questions for test {test_id}")

        return {
            "success": True,
            "test_id": test_id,
            "questions_updated": len(request.questions),
            "updated_at": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update questions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Attachment Management (NEW) ==========


@router.get("/{test_id}/attachments", response_model=dict, tags=["Phase 3 - Editing"])
async def get_test_attachments(
    test_id: str,
    user_info: dict = Depends(require_auth),
):
    """
    Get list of all attachments for a test

    **Use case:** Display attachments when editing test - user can view, add, or delete

    **Access:**
    - Owner: Can view and manage attachments
    - Others: Read-only access if they have test access

    **Returns:**
    - List of attachments with id, title, description, file_url, file_size_mb, uploaded_at
    - Total storage used by attachments
    - Test metadata (creator_id, title)
    """
    try:
        logger.info(
            f"📋 Get attachments for test {test_id} from user {user_info['uid']}"
        )

        # Get test
        mongo_service = get_mongodb_service()
        test_collection = mongo_service.db["online_tests"]

        test_doc = test_collection.find_one({"_id": ObjectId(test_id)})

        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        # Check access (owner or shared)
        access_info = check_test_access(test_id, user_info["uid"], test_doc)
        is_owner = access_info["is_owner"]

        logger.info(
            f"   ✅ Access granted: type={access_info['access_type']}, owner={is_owner}"
        )

        # Get attachments
        attachments = test_doc.get("attachments", [])

        # Calculate total storage used by attachments
        total_storage_mb = sum(att.get("file_size_mb", 0) for att in attachments)

        # Format response
        formatted_attachments = []
        for att in attachments:
            formatted_attachments.append(
                {
                    "attachment_id": att.get("attachment_id"),
                    "title": att.get("title"),
                    "description": att.get("description"),
                    "file_url": att.get("file_url"),
                    "file_size_mb": att.get("file_size_mb", 0),
                    "uploaded_at": (
                        att.get("uploaded_at").isoformat()
                        if att.get("uploaded_at")
                        else None
                    ),
                }
            )

        logger.info(
            f"   📄 Found {len(formatted_attachments)} attachments ({total_storage_mb:.2f}MB total)"
        )

        return {
            "success": True,
            "test_id": test_id,
            "test_title": test_doc.get("title"),
            "creator_id": test_doc.get("creator_id"),
            "is_owner": is_owner,
            "attachments": formatted_attachments,
            "total_attachments": len(formatted_attachments),
            "total_storage_mb": round(total_storage_mb, 2),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get attachments: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{test_id}/attachments", response_model=dict, tags=["Phase 3 - Editing"])
async def add_test_attachment(
    test_id: str,
    attachment: TestAttachment,
    user_info: dict = Depends(require_auth),
):
    """
    Add a PDF attachment to test (Owner only)

    **IMPORTANT**: File size tính vào storage quota của test owner.

    Use case: Add reading comprehension materials, reference documents, etc.

    **Request Body:**
    ```json
    {
        "title": "Reading Passage 1",
        "description": "Short story for comprehension questions",
        "file_url": "https://r2.storage.com/files/passage1.pdf",
        "file_size_mb": 2.5
    }
    ```
    """
    try:
        from src.services.subscription_service import get_subscription_service

        user_id = user_info["uid"]
        mongo_service = get_mongodb_service()

        # Verify test exists and user is creator
        test_doc = mongo_service.db["online_tests"].find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        if test_doc["creator_id"] != user_id:
            raise HTTPException(
                status_code=403, detail="Only test creator can add attachments"
            )

        # Create attachment with unique ID
        import uuid

        new_attachment = {
            "attachment_id": str(uuid.uuid4())[:12],
            "title": attachment.title,
            "description": attachment.description,
            "file_url": attachment.file_url,
            "file_size_mb": attachment.file_size_mb,
            "uploaded_at": datetime.now(),
        }

        # Add to test's attachments array
        result = mongo_service.db["online_tests"].update_one(
            {"_id": ObjectId(test_id)},
            {
                "$push": {"attachments": new_attachment},
                "$set": {"updated_at": datetime.now()},
            },
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=500, detail="Failed to add attachment")

        # Update storage usage for test owner
        subscription_service = get_subscription_service()
        await subscription_service.update_usage(
            user_id, SubscriptionUsageUpdate(storage_mb=attachment.file_size_mb)
        )

        logger.info(
            f"✅ Added attachment {new_attachment['attachment_id']} ({attachment.file_size_mb}MB) to test {test_id}, updated storage for user {user_id}"
        )

        return {
            "success": True,
            "test_id": test_id,
            "attachment": new_attachment,
            "message": "Attachment added successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to add attachment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put(
    "/{test_id}/attachments/{attachment_id}",
    response_model=dict,
    tags=["Phase 3 - Editing"],
)
async def update_test_attachment(
    test_id: str,
    attachment_id: str,
    attachment: TestAttachment,
    user_info: dict = Depends(require_auth),
):
    """
    Update a test attachment (Owner only)

    **Request Body:**
    ```json
    {
        "title": "Updated Reading Passage 1",
        "description": "Updated description",
        "file_url": "https://r2.storage.com/files/updated_passage1.pdf"
    }
    ```
    """
    try:
        user_id = user_info["uid"]
        mongo_service = get_mongodb_service()

        # Verify test exists and user is creator
        test_doc = mongo_service.db["online_tests"].find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        if test_doc["creator_id"] != user_id:
            raise HTTPException(
                status_code=403, detail="Only test creator can update attachments"
            )

        # Find attachment in array
        attachments = test_doc.get("attachments", [])
        attachment_found = False

        for att in attachments:
            if att["attachment_id"] == attachment_id:
                att["title"] = attachment.title
                att["description"] = attachment.description
                att["file_url"] = attachment.file_url
                att["updated_at"] = datetime.now()
                attachment_found = True
                break

        if not attachment_found:
            raise HTTPException(status_code=404, detail="Attachment not found")

        # Update entire attachments array
        result = mongo_service.db["online_tests"].update_one(
            {"_id": ObjectId(test_id)},
            {"$set": {"attachments": attachments, "updated_at": datetime.now()}},
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=500, detail="Failed to update attachment")

        logger.info(f"✅ Updated attachment {attachment_id} in test {test_id}")

        return {
            "success": True,
            "test_id": test_id,
            "attachment_id": attachment_id,
            "message": "Attachment updated successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update attachment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/{test_id}/attachments/{attachment_id}",
    response_model=dict,
    tags=["Phase 3 - Editing"],
)
async def delete_test_attachment(
    test_id: str,
    attachment_id: str,
    user_info: dict = Depends(require_auth),
):
    """
    Delete a test attachment (Owner only)

    **IMPORTANT**: Giảm storage usage khi xóa attachment.
    """
    try:
        from src.services.subscription_service import get_subscription_service

        user_id = user_info["uid"]
        mongo_service = get_mongodb_service()

        # Verify test exists and user is creator
        test_doc = mongo_service.db["online_tests"].find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        if test_doc["creator_id"] != user_id:
            raise HTTPException(
                status_code=403, detail="Only test creator can delete attachments"
            )

        # Find attachment to get file_size_mb before deleting
        attachment_to_delete = None
        for att in test_doc.get("attachments", []):
            if att.get("attachment_id") == attachment_id:
                attachment_to_delete = att
                break

        if not attachment_to_delete:
            raise HTTPException(status_code=404, detail="Attachment not found")

        # Get file size (default to 0 if not found for old attachments)
        file_size_mb = attachment_to_delete.get("file_size_mb", 0)

        # Remove attachment from array
        result = mongo_service.db["online_tests"].update_one(
            {"_id": ObjectId(test_id)},
            {
                "$pull": {"attachments": {"attachment_id": attachment_id}},
                "$set": {"updated_at": datetime.now()},
            },
        )

        if result.modified_count == 0:
            raise HTTPException(
                status_code=404, detail="Attachment not found or already deleted"
            )

        # Decrease storage usage for test owner
        if file_size_mb > 0:
            subscription_service = get_subscription_service()
            await subscription_service.update_usage(
                user_id,
                SubscriptionUsageUpdate(
                    storage_mb=-file_size_mb
                ),  # Negative to decrease
            )

            logger.info(
                f"✅ Deleted attachment {attachment_id} ({file_size_mb}MB) from test {test_id}, decreased storage for user {user_id}"
            )
        else:
            logger.info(
                f"✅ Deleted attachment {attachment_id} from test {test_id} (no storage tracking)"
            )

        return {
            "success": True,
            "test_id": test_id,
            "attachment_id": attachment_id,
            "message": "Attachment deleted successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete attachment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{test_id}/preview", response_model=TestPreviewResponse, tags=["Phase 3 - Editing"]
)
async def preview_test(
    test_id: str,
    user_info: dict = Depends(require_auth),
):
    """
    Preview test with all details including correct answers
    Only the test creator can preview with answers
    """
    try:
        user_id = user_info["uid"]
        mongo_service = get_mongodb_service()

        # Get test document
        test_doc = mongo_service.db["online_tests"].find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        if test_doc["creator_id"] != user_id:
            raise HTTPException(
                status_code=403, detail="Only the test creator can preview with answers"
            )

        return TestPreviewResponse(
            test_id=str(test_doc["_id"]),
            title=test_doc["title"],
            time_limit_minutes=test_doc["time_limit_minutes"],
            max_retries=test_doc["max_retries"],
            is_active=test_doc.get("is_active", True),
            total_questions=len(test_doc["questions"]),
            questions=test_doc["questions"],  # Includes correct_answer_key
            created_at=test_doc["created_at"].isoformat(),
            updated_at=test_doc.get("updated_at", test_doc["created_at"]).isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to preview test: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{test_id}/edit", response_model=dict, tags=["Phase 3 - Editing"])
async def full_edit_test(
    test_id: str,
    request: FullTestEditRequest,
    user_info: dict = Depends(require_auth),
):
    """
    Comprehensive test editing endpoint for owner

    **Can update ALL test aspects in one call:**
    - Basic config: title, description, is_active
    - Test settings: max_retries, time_limit_minutes, passing_score, deadline, show_answers_timing
    - Questions: Full questions array
    - Marketplace config: marketplace_title, marketplace_description, price_points, category, tags, difficulty

    **Access:**
    - Only test creator can edit

    **Usage:**
    - Update any combination of fields
    - All fields optional (only update what you provide)
    - For marketplace fields, test must already be published

    **Returns:**
    - Updated test document with all current values
    - Useful for owner's edit dashboard
    """
    try:
        user_id = user_info["uid"]
        mongo_service = get_mongodb_service()

        logger.info(f"✏️ Full edit test {test_id}")
        logger.info(f"   User: {user_id}")

        # ========== Step 1: Verify test exists and user is creator ==========
        test_doc = mongo_service.db["online_tests"].find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        if test_doc["creator_id"] != user_id:
            raise HTTPException(
                status_code=403, detail="Only the test creator can edit this test"
            )

        # ========== Step 2: Build update data ==========
        update_data = {}
        marketplace_updates = {}

        # Basic config updates
        if request.title is not None:
            update_data["title"] = request.title
            logger.info(f"   Update title: {request.title}")

        if request.description is not None:
            update_data["description"] = request.description
            logger.info(f"   Update description")

        if request.is_active is not None:
            update_data["is_active"] = request.is_active
            logger.info(f"   Update is_active: {request.is_active}")

        # Test settings updates
        if request.max_retries is not None:
            update_data["max_retries"] = request.max_retries
            logger.info(f"   Update max_retries: {request.max_retries}")

        if request.time_limit_minutes is not None:
            update_data["time_limit_minutes"] = request.time_limit_minutes
            logger.info(f"   Update time_limit: {request.time_limit_minutes}min")

        if request.passing_score is not None:
            update_data["passing_score"] = request.passing_score
            logger.info(f"   Update passing_score: {request.passing_score}%")

        if request.deadline is not None:
            update_data["deadline"] = request.deadline
            logger.info(f"   Update deadline: {request.deadline}")

        if request.show_answers_timing is not None:
            if request.show_answers_timing not in ["immediate", "after_deadline"]:
                raise HTTPException(
                    status_code=400,
                    detail="show_answers_timing must be 'immediate' or 'after_deadline'",
                )
            update_data["show_answers_timing"] = request.show_answers_timing
            logger.info(f"   Update show_answers_timing: {request.show_answers_timing}")

        # Questions update
        if request.questions is not None:
            if len(request.questions) == 0:
                raise HTTPException(
                    status_code=400, detail="At least one question is required"
                )

            if len(request.questions) > 100:
                raise HTTPException(
                    status_code=400, detail="Maximum 100 questions allowed"
                )

            # Validate questions structure
            for idx, q in enumerate(request.questions):
                if not q.get("question_text"):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Question {idx + 1}: question_text is required",
                    )

                if not q.get("options") or len(q["options"]) < 2:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Question {idx + 1}: At least 2 options are required",
                    )

                # Ensure question_id exists
                if not q.get("question_id"):
                    q["question_id"] = str(ObjectId())

            update_data["questions"] = request.questions
            logger.info(f"   Update questions: {len(request.questions)} questions")

        # Attachments update (NEW)
        if request.attachments is not None:
            # Format attachments with attachment_id if not present
            import uuid

            formatted_attachments = []
            for att in request.attachments:
                # If dict without attachment_id, convert from TestAttachment model
                if isinstance(att, dict):
                    if not att.get("attachment_id"):
                        att["attachment_id"] = str(uuid.uuid4())[:12]
                    if not att.get("uploaded_at"):
                        att["uploaded_at"] = datetime.now()
                    formatted_attachments.append(att)
                else:
                    # TestAttachment model instance
                    formatted_attachments.append(
                        {
                            "attachment_id": str(uuid.uuid4())[:12],
                            "title": att.title,
                            "description": att.description,
                            "file_url": att.file_url,
                            "uploaded_at": datetime.now(),
                        }
                    )

            update_data["attachments"] = formatted_attachments
            logger.info(
                f"   Update attachments: {len(formatted_attachments)} attachments"
            )

        # ========== Step 3: Handle marketplace config updates (if published) ==========
        marketplace_config = test_doc.get("marketplace_config", {})
        is_published = marketplace_config.get("is_public", False)

        if is_published:
            # Update marketplace fields
            if request.marketplace_title is not None:
                if len(request.marketplace_title) < 10:
                    raise HTTPException(
                        status_code=400,
                        detail="Marketplace title must be at least 10 characters",
                    )
                marketplace_updates["marketplace_config.title"] = (
                    request.marketplace_title
                )
                logger.info(f"   Update marketplace title: {request.marketplace_title}")

            if request.marketplace_description is not None:
                if len(request.marketplace_description) < 50:
                    raise HTTPException(
                        status_code=400,
                        detail="Marketplace description must be at least 50 characters",
                    )
                marketplace_updates["marketplace_config.description"] = (
                    request.marketplace_description
                )
                logger.info(f"   Update marketplace description")

            if request.short_description is not None:
                marketplace_updates["marketplace_config.short_description"] = (
                    request.short_description
                )
                logger.info(f"   Update short_description")

            if request.price_points is not None:
                if request.price_points < 0:
                    raise HTTPException(status_code=400, detail="Price must be >= 0")
                marketplace_updates["marketplace_config.price_points"] = (
                    request.price_points
                )
                logger.info(f"   Update price: {request.price_points} points")

            if request.category is not None:
                valid_categories = [
                    "programming",
                    "language",
                    "math",
                    "science",
                    "business",
                    "technology",
                    "design",
                    "exam_prep",
                    "certification",
                    "other",
                ]
                if request.category not in valid_categories:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid category. Valid: {', '.join(valid_categories)}",
                    )
                marketplace_updates["marketplace_config.category"] = request.category
                logger.info(f"   Update category: {request.category}")

            if request.tags is not None:
                tags_list = [
                    tag.strip().lower()
                    for tag in request.tags.split(",")
                    if tag.strip()
                ]
                if len(tags_list) < 1:
                    raise HTTPException(
                        status_code=400, detail="At least 1 tag is required"
                    )
                if len(tags_list) > 10:
                    raise HTTPException(
                        status_code=400, detail="Maximum 10 tags allowed"
                    )
                marketplace_updates["marketplace_config.tags"] = tags_list
                logger.info(f"   Update tags: {tags_list}")

            if request.difficulty_level is not None:
                valid_difficulty = ["beginner", "intermediate", "advanced", "expert"]
                if request.difficulty_level not in valid_difficulty:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid difficulty. Valid: {', '.join(valid_difficulty)}",
                    )
                marketplace_updates["marketplace_config.difficulty_level"] = (
                    request.difficulty_level
                )
                logger.info(f"   Update difficulty: {request.difficulty_level}")

        elif any(
            [
                request.marketplace_title,
                request.marketplace_description,
                request.short_description,
                request.price_points is not None,
                request.category,
                request.tags,
                request.difficulty_level,
            ]
        ):
            raise HTTPException(
                status_code=400,
                detail="Cannot update marketplace config. Test is not published. Use POST /marketplace/publish first.",
            )

        # ========== Step 4: Combine all updates ==========
        all_updates = {**update_data, **marketplace_updates}

        if not all_updates:
            raise HTTPException(
                status_code=400,
                detail="No fields to update. Provide at least one field to update.",
            )

        # Add timestamp
        all_updates["updated_at"] = datetime.utcnow()

        # ========== Step 5: Update in database ==========
        result = mongo_service.db["online_tests"].update_one(
            {"_id": ObjectId(test_id)}, {"$set": all_updates}
        )

        if result.modified_count == 0:
            logger.warning(f"⚠️ No changes made to test {test_id}")

        # ========== Step 6: Get updated test document ==========
        updated_test = mongo_service.db["online_tests"].find_one(
            {"_id": ObjectId(test_id)}
        )

        logger.info(f"✅ Test {test_id} fully updated")

        # ========== Step 7: Return comprehensive response ==========
        return {
            "success": True,
            "test_id": test_id,
            "updated_fields": list(all_updates.keys()),
            "test": {
                # Basic info
                "title": updated_test.get("title"),
                "description": updated_test.get("description"),
                "is_active": updated_test.get("is_active", True),
                # Test settings
                "max_retries": updated_test.get("max_retries"),
                "time_limit_minutes": updated_test.get("time_limit_minutes"),
                "passing_score": updated_test.get("passing_score"),
                "deadline": (
                    updated_test.get("deadline").isoformat()
                    if updated_test.get("deadline")
                    else None
                ),
                "show_answers_timing": updated_test.get("show_answers_timing"),
                # Questions
                "num_questions": len(updated_test.get("questions", [])),
                "questions": updated_test.get("questions", []),
                # Marketplace (if published)
                "is_published": is_published,
                "marketplace_config": updated_test.get("marketplace_config", {}),
                # Timestamps
                "created_at": updated_test.get("created_at").isoformat(),
                "updated_at": updated_test.get("updated_at").isoformat(),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to edit test: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{test_id}", response_model=dict, tags=["Phase 3 - Editing"])
async def delete_test(
    test_id: str,
    user_info: dict = Depends(require_auth),
):
    """
    Delete a test (soft delete by setting is_active=false)
    Only the test creator can delete
    """
    try:
        user_id = user_info["uid"]
        mongo_service = get_mongodb_service()

        # Verify test exists and user is creator
        test_doc = mongo_service.db["online_tests"].find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        if test_doc["creator_id"] != user_id:
            raise HTTPException(
                status_code=403, detail="Only the test creator can delete"
            )

        # Soft delete by setting is_active=false
        result = mongo_service.db["online_tests"].update_one(
            {"_id": ObjectId(test_id)},
            {"$set": {"is_active": False, "updated_at": datetime.utcnow()}},
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=500, detail="Failed to delete test")

        logger.info(f"🗑️ Soft deleted test {test_id}")

        return {
            "success": True,
            "test_id": test_id,
            "message": "Test deactivated successfully",
            "deleted_at": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete test: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{test_id}/attempts", response_model=dict, tags=["Phase 3 - Editing"])
async def get_test_attempts(
    test_id: str,
    user_info: dict = Depends(require_auth),
):
    """
    Get user's attempt history for a specific test

    Returns:
    - Summary: total attempts, remaining attempts, best score
    - List of all submissions with basic info
    - Click on submission_id to get full details via GET /me/submissions/{submission_id}

    **Example:**
    User A làm test XX 3 lần:
    - Attempt 1: score 5.0/10 (50%) - PASS
    - Attempt 2: score 7.0/10 (70%) - PASS
    - Attempt 3: score 8.0/10 (80%) - PASS
    """
    try:
        user_id = user_info["uid"]
        mongo_service = get_mongodb_service()

        # Verify test exists
        test_doc = mongo_service.db["online_tests"].find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        # Check if user is creator (unlimited attempts)
        is_creator = test_doc.get("creator_id") == user_id

        # Get all submissions for this user and test (sorted newest first)
        submissions = list(
            mongo_service.db["test_submissions"]
            .find({"test_id": test_id, "user_id": user_id})
            .sort("submitted_at", -1)
        )

        attempts_used = len(submissions)
        max_retries = test_doc.get("max_retries", 3)

        # Creator has unlimited attempts
        if is_creator:
            attempts_remaining = float("inf")  # Unlimited
            can_retake = True
        else:
            attempts_remaining = max(0, max_retries - attempts_used)
            can_retake = attempts_remaining > 0

        # Get best score
        best_score = 0
        if submissions:
            best_score = max(sub.get("score", 0) for sub in submissions)

        # Build submission list with more details
        submission_list = []
        for sub in submissions:
            submission_list.append(
                {
                    "submission_id": str(sub["_id"]),
                    "score": sub.get("score", 0),  # Thang điểm 10
                    "score_percentage": sub.get(
                        "score_percentage", sub.get("score", 0) * 10
                    ),
                    "correct_answers": sub.get("correct_answers", 0),
                    "total_questions": sub.get("total_questions", 0),
                    "is_passed": sub.get("is_passed", False),
                    "attempt_number": sub.get("attempt_number", 0),
                    "time_taken_seconds": sub.get("time_taken_seconds", 0),
                    "submitted_at": sub["submitted_at"].isoformat(),
                }
            )

        logger.info(
            f"📊 Get attempts for test {test_id}: user={user_id}, "
            f"attempts={attempts_used}/{max_retries}, best_score={best_score}/10"
        )

        return {
            "test_id": test_id,
            "test_title": test_doc["title"],
            "is_creator": is_creator,
            "max_retries": max_retries if not is_creator else None,  # None = unlimited
            "attempts_used": attempts_used,
            "attempts_remaining": "unlimited" if is_creator else attempts_remaining,
            "best_score": best_score,
            "can_retake": can_retake,
            "submissions": submission_list,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get attempts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{test_id}/participants", response_model=dict, tags=["Phase 3 - Editing"])
async def get_test_participants(
    test_id: str,
    user_info: dict = Depends(require_auth),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query(
        "latest", regex="^(latest|highest_score|lowest_score|most_attempts)$"
    ),
):
    """
    Get list of all participants for a test (OWNER ONLY)

    Returns detailed information about each participant:
    - User ID, email, display name
    - Number of attempts
    - Best score
    - Latest submission date
    - Total correct answers
    - Average time taken

    **Access:** Only test owner can view participants

    **Sort options:**
    - latest: Most recent participants first
    - highest_score: Best scores first
    - lowest_score: Lowest scores first
    - most_attempts: Most attempts first
    """
    try:
        user_id = user_info["uid"]
        mongo_service = get_mongodb_service()

        # Verify test exists
        test_doc = mongo_service.db["online_tests"].find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        # Check ownership
        if test_doc.get("creator_id") != user_id:
            raise HTTPException(
                status_code=403, detail="Only test owner can view participants"
            )

        # Get all unique participants who have started the test at least once
        progress_collection = mongo_service.db["test_progress"]
        submissions_collection = mongo_service.db["test_submissions"]
        users_collection = mongo_service.db["users"]

        # Get unique user IDs from test_progress (anyone who started)
        participant_ids = progress_collection.distinct("user_id", {"test_id": test_id})

        if not participant_ids:
            return {
                "test_id": test_id,
                "test_title": test_doc.get("title", "Untitled"),
                "total_participants": 0,
                "participants": [],
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_items": 0,
                    "total_pages": 0,
                    "has_next": False,
                    "has_prev": False,
                },
            }

        # Build participant data
        participants_data = []

        for participant_id in participant_ids:
            # Get user info
            user_doc = users_collection.find_one({"firebase_uid": participant_id})
            if not user_doc:
                continue  # Skip if user not found

            # Get all submissions for this participant
            submissions = list(
                submissions_collection.find(
                    {"test_id": test_id, "user_id": participant_id}
                ).sort("submitted_at", -1)
            )

            # Calculate statistics
            num_attempts = len(submissions)
            best_score = 0
            total_correct = 0
            total_time = 0
            latest_submission = None

            if submissions:
                best_score = max(sub.get("score", 0) for sub in submissions)
                total_correct = sum(
                    sub.get("correct_answers", 0) for sub in submissions
                )
                total_time = sum(
                    sub.get("time_taken_seconds", 0) for sub in submissions
                )
                latest_submission = submissions[0].get("submitted_at")

            avg_time = total_time / num_attempts if num_attempts > 0 else 0

            participants_data.append(
                {
                    "user_id": participant_id,
                    "email": user_doc.get("email", "N/A"),
                    "display_name": user_doc.get("display_name", "Anonymous"),
                    "photo_url": user_doc.get("photo_url"),
                    "num_attempts": num_attempts,
                    "best_score": best_score,
                    "total_correct_answers": total_correct,
                    "avg_time_seconds": int(avg_time),
                    "latest_submission_at": (
                        latest_submission.isoformat() if latest_submission else None
                    ),
                    "has_submitted": num_attempts > 0,
                }
            )

        # Sort based on sort_by parameter
        if sort_by == "latest":
            participants_data.sort(
                key=lambda x: x["latest_submission_at"] or "", reverse=True
            )
        elif sort_by == "highest_score":
            participants_data.sort(key=lambda x: x["best_score"], reverse=True)
        elif sort_by == "lowest_score":
            participants_data.sort(key=lambda x: x["best_score"])
        elif sort_by == "most_attempts":
            participants_data.sort(key=lambda x: x["num_attempts"], reverse=True)

        # Pagination
        total_items = len(participants_data)
        total_pages = (total_items + page_size - 1) // page_size
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size

        paginated_participants = participants_data[start_idx:end_idx]

        logger.info(
            f"📊 Get participants for test {test_id}: "
            f"owner={user_id}, total={total_items}, page={page}/{total_pages}"
        )

        return {
            "test_id": test_id,
            "test_title": test_doc.get("title", "Untitled"),
            "total_participants": total_items,
            "participants": paginated_participants,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_items": total_items,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get participants: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Phase 4: Question Media Upload ==========


@router.post(
    "/{test_id}/questions/{question_id}/media",
    response_model=dict,
    tags=["Phase 4 - Question Media"],
)
async def upload_question_media(
    test_id: str,
    question_id: str,
    media_file: UploadFile = File(...),
    media_type: str = Form(...),  # "image" or "audio"
    description: str = Form(None),
    user_info: dict = Depends(require_auth),
):
    """
    Upload image or audio for a specific question

    Supported formats:
    - Images: JPG, PNG, GIF (max 5MB)
    - Audio: MP3, WAV, OGG (max 10MB)

    Media will be stored in R2: question-media/{test_id}/{question_id}_{type}.ext
    """
    try:
        user_id = user_info["uid"]
        mongo_service = get_mongodb_service()

        logger.info(
            f"📤 Uploading {media_type} for question {question_id} in test {test_id}"
        )

        # ========== Step 1: Verify test and permissions ==========
        test_doc = mongo_service.db["online_tests"].find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        if test_doc["creator_id"] != user_id:
            raise HTTPException(
                status_code=403,
                detail="Only test creator can upload question media",
            )

        # ========== Step 2: Find question ==========
        questions = test_doc.get("questions", [])
        question_index = None
        for idx, q in enumerate(questions):
            if q.get("question_id") == question_id:
                question_index = idx
                break

        if question_index is None:
            raise HTTPException(status_code=404, detail="Question not found in test")

        # ========== Step 3: Validate media type and file ==========
        if media_type not in ["image", "audio"]:
            raise HTTPException(
                status_code=400, detail="media_type must be 'image' or 'audio'"
            )

        # Validate file type
        if media_type == "image":
            allowed_types = ["image/jpeg", "image/png", "image/gif", "image/jpg"]
            max_size_mb = 5
            extensions = {".jpg": "jpg", ".jpeg": "jpg", ".png": "png", ".gif": "gif"}
        else:  # audio
            allowed_types = ["audio/mpeg", "audio/mp3", "audio/wav", "audio/ogg"]
            max_size_mb = 10
            extensions = {".mp3": "mp3", ".wav": "wav", ".ogg": "ogg"}

        if media_file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed: {', '.join(allowed_types)}",
            )

        # Read and validate file size
        media_content = await media_file.read()
        size_mb = len(media_content) / (1024 * 1024)

        if size_mb > max_size_mb:
            raise HTTPException(
                status_code=400,
                detail=f"File too large: {size_mb:.2f}MB (max {max_size_mb}MB)",
            )

        logger.info(f"   File size: {size_mb:.2f}MB")

        # ========== Step 4: Determine file extension ==========
        import mimetypes

        ext = mimetypes.guess_extension(media_file.content_type) or ".bin"
        if ext in extensions:
            ext = f".{extensions[ext]}"

        # ========== Step 5: Upload to R2 ==========
        s3_client = get_s3_client()
        key = f"question-media/{test_id}/{question_id}_{media_type}{ext}"

        logger.info(f"   [R2] Uploading to: {key}")

        s3_client.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=key,
            Body=media_content,
            ContentType=media_file.content_type,
        )

        media_url = f"{R2_PUBLIC_URL}/{key}"
        logger.info(f"   [R2] ✅ Uploaded: {media_url}")

        # ========== Step 6: Update question in database ==========
        update_path = f"questions.{question_index}"
        result = mongo_service.db["online_tests"].update_one(
            {"_id": ObjectId(test_id)},
            {
                "$set": {
                    f"{update_path}.media_type": media_type,
                    f"{update_path}.media_url": media_url,
                    f"{update_path}.media_description": description or "",
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        if result.modified_count == 0:
            logger.warning(f"⚠️  No changes made to question {question_id}")

        logger.info(f"✅ Media uploaded for question {question_id}")

        return {
            "success": True,
            "test_id": test_id,
            "question_id": question_id,
            "media_type": media_type,
            "media_url": media_url,
            "media_description": description or "",
            "file_size_mb": round(size_mb, 2),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to upload question media: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/{test_id}/questions/{question_id}/media",
    response_model=dict,
    tags=["Phase 4 - Question Media"],
)
async def delete_question_media(
    test_id: str,
    question_id: str,
    user_info: dict = Depends(require_auth),
):
    """
    Delete media (image/audio) from a question
    """
    try:
        user_id = user_info["uid"]
        mongo_service = get_mongodb_service()

        logger.info(f"🗑️  Deleting media for question {question_id} in test {test_id}")

        # Verify test and permissions
        test_doc = mongo_service.db["online_tests"].find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        if test_doc["creator_id"] != user_id:
            raise HTTPException(
                status_code=403, detail="Only test creator can delete question media"
            )

        # Find question
        questions = test_doc.get("questions", [])
        question_index = None
        old_media_url = None

        for idx, q in enumerate(questions):
            if q.get("question_id") == question_id:
                question_index = idx
                old_media_url = q.get("media_url")
                break

        if question_index is None:
            raise HTTPException(status_code=404, detail="Question not found")

        if not old_media_url:
            raise HTTPException(
                status_code=404, detail="No media found for this question"
            )

        # Delete from R2 (optional - files are small, can keep for rollback)
        try:
            s3_client = get_s3_client()
            # Extract key from URL
            key = old_media_url.replace(f"{R2_PUBLIC_URL}/", "")
            s3_client.delete_object(Bucket=R2_BUCKET_NAME, Key=key)
            logger.info(f"   [R2] ✅ Deleted: {key}")
        except Exception as e:
            logger.warning(f"   [R2] ⚠️  Failed to delete from R2: {e}")

        # Remove media fields from question
        update_path = f"questions.{question_index}"
        result = mongo_service.db["online_tests"].update_one(
            {"_id": ObjectId(test_id)},
            {
                "$unset": {
                    f"{update_path}.media_type": "",
                    f"{update_path}.media_url": "",
                    f"{update_path}.media_description": "",
                },
                "$set": {"updated_at": datetime.utcnow()},
            },
        )

        logger.info(f"✅ Media deleted for question {question_id}")

        return {
            "success": True,
            "test_id": test_id,
            "question_id": question_id,
            "deleted_media_url": old_media_url,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete question media: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Phase 5: Marketplace Endpoints ==========


@router.post(
    "/{test_id}/marketplace/publish",
    response_model=dict,
    tags=["Phase 5 - Marketplace"],
)
async def publish_test_to_marketplace(
    test_id: str,
    cover_image: Optional[UploadFile] = File(None),
    title: str = Form(...),
    description: str = Form(...),
    short_description: Optional[str] = Form(None),
    price_points: int = Form(...),
    category: str = Form(...),
    tags: str = Form(...),
    difficulty_level: str = Form(...),
    user_info: dict = Depends(require_auth),
):
    """
    Publish test to marketplace with cover image and full metadata

    Requirements:
    - Test must have at least 5 questions
    - Description must be at least 50 characters
    - Title must be at least 10 characters
    - Cover image: (Optional) JPG/PNG, max 5MB, min 800x600
    - Short description: (Optional) Brief summary for listing cards
    - Price: 0 (FREE) or any positive integer

    Returns:
    - marketplace_url: Public marketplace URL
    - marketplace_config: Full marketplace configuration
    """
    try:
        user_id = user_info["uid"]
        mongo_service = get_mongodb_service()

        logger.info(f"📢 Publishing test {test_id} to marketplace")
        logger.info(f"   User: {user_id}")
        logger.info(f"   Title: {title}")
        logger.info(f"   Price: {price_points} points")
        logger.info(f"   Category: {category}")

        # ========== Step 1: Validate test exists and user is creator ==========
        test_doc = mongo_service.db["online_tests"].find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        if test_doc.get("creator_id") != user_id:
            raise HTTPException(
                status_code=403, detail="Only test creator can publish to marketplace"
            )

        # ========== Step 2: Check if already published ==========
        if test_doc.get("marketplace_config", {}).get("is_public"):
            raise HTTPException(
                status_code=409,
                detail="Test already published. Use PATCH /marketplace/config to update.",
            )

        # ========== Step 3: Validate test requirements ==========
        if not test_doc.get("is_active", False):
            raise HTTPException(
                status_code=400, detail="Test must be active before publishing"
            )

        questions = test_doc.get("questions", [])
        if len(questions) < 5:
            raise HTTPException(
                status_code=400,
                detail=f"Test must have at least 5 questions (current: {len(questions)})",
            )

        # ========== Step 4: Validate form inputs ==========
        if len(title) < 10:
            raise HTTPException(
                status_code=400, detail="Title must be at least 10 characters"
            )

        if len(description) < 50:
            raise HTTPException(
                status_code=400, detail="Description must be at least 50 characters"
            )

        if price_points < 0:
            raise HTTPException(status_code=400, detail="Price must be >= 0")

        # Validate category
        valid_categories = [
            "programming",
            "language",
            "math",
            "science",
            "business",
            "technology",
            "design",
            "exam_prep",
            "certification",
            "other",
        ]
        if category not in valid_categories:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid category. Valid: {', '.join(valid_categories)}",
            )

        # Validate difficulty
        valid_difficulty = ["beginner", "intermediate", "advanced", "expert"]
        if difficulty_level not in valid_difficulty:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid difficulty. Valid: {', '.join(valid_difficulty)}",
            )

        # Parse tags
        tags_list = [tag.strip().lower() for tag in tags.split(",") if tag.strip()]
        if len(tags_list) < 1:
            raise HTTPException(status_code=400, detail="At least 1 tag is required")
        if len(tags_list) > 10:
            raise HTTPException(status_code=400, detail="Maximum 10 tags allowed")

        # ========== Step 5: Validate cover image (optional) ==========
        cover_url = None
        if cover_image:
            if not cover_image.content_type in ["image/jpeg", "image/png", "image/jpg"]:
                raise HTTPException(
                    status_code=400,
                    detail="Cover image must be JPG or PNG",
                )

            # Read file content
            cover_content = await cover_image.read()
            cover_size_mb = len(cover_content) / (1024 * 1024)

            if cover_size_mb > 5:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cover image too large: {cover_size_mb:.2f}MB (max 5MB)",
                )

            logger.info(f"   Cover image size: {cover_size_mb:.2f}MB")
        else:
            logger.info(f"   No cover image provided (optional)")

        # ========== Step 6: Determine version ==========
        current_version = test_doc.get("marketplace_config", {}).get("version", 0)
        new_version = f"v{current_version + 1}"

        logger.info(f"   Creating marketplace version: {new_version}")

        # ========== Step 7: Upload cover image to R2 (if provided) ==========
        if cover_image:
            cover_url = await upload_cover_to_r2(
                cover_content, test_id, new_version, cover_image.content_type
            )
        else:
            cover_url = None

        # ========== Step 8: Create marketplace_config ==========
        marketplace_config = {
            "is_public": True,
            "version": new_version,
            "title": title,
            "description": description,
            "short_description": (
                short_description or description[:100] + "..."
                if len(description) > 100
                else description
            ),  # Auto-generate from description if not provided
            "cover_image_url": cover_url,  # None if not provided
            "price_points": price_points,
            "category": category,
            "tags": tags_list,
            "difficulty_level": difficulty_level,
            "published_at": datetime.utcnow(),
            "total_participants": 0,
            "total_earnings": 0,
            "average_rating": 0.0,
            "rating_count": 0,
            "average_participant_score": 0.0,
        }

        # ========== Step 9: Update test document ==========
        result = mongo_service.db["online_tests"].update_one(
            {"_id": ObjectId(test_id)},
            {
                "$set": {
                    "marketplace_config": marketplace_config,
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        if result.modified_count == 0:
            logger.error(f"❌ Failed to update test {test_id}")
            raise HTTPException(status_code=500, detail="Failed to update test")

        # ========== Step 10: Return success response ==========
        marketplace_url = f"https://wordai.vn/marketplace/tests/{test_id}"

        logger.info(f"✅ Test {test_id} published successfully!")
        logger.info(f"   Version: {new_version}")
        logger.info(f"   Cover: {cover_url}")
        logger.info(f"   URL: {marketplace_url}")

        return {
            "success": True,
            "test_id": test_id,
            "version": new_version,
            "marketplace_url": marketplace_url,
            "published_at": marketplace_config["published_at"].isoformat(),
            "marketplace_config": marketplace_config,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to publish test: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch(
    "/{test_id}/marketplace/config",
    response_model=dict,
    tags=["Phase 5 - Marketplace"],
)
async def update_marketplace_config(
    test_id: str,
    cover_image: Optional[UploadFile] = File(None),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    short_description: Optional[str] = Form(None),
    price_points: Optional[int] = Form(None),
    category: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    difficulty_level: Optional[str] = Form(None),
    is_public: Optional[bool] = Form(None),
    user_info: dict = Depends(require_auth),
):
    """
    Update marketplace configuration for an already published test

    **Can update:**
    - cover_image: Upload new cover image (JPG/PNG, max 5MB)
    - title: Marketplace title (min 10 chars)
    - description: Full description (min 50 chars)
    - short_description: Brief summary for listing cards
    - price_points: Price in points (>= 0)
    - category: Test category
    - tags: Comma-separated tags
    - difficulty_level: Difficulty (beginner/intermediate/advanced/expert)
    - is_public: Set to False to unpublish test

    **Access:**
    - Only test creator can update
    - Test must already be published (marketplace_config.is_public = true)

    **Note:**
    - All fields are optional, only update what you provide
    - Cover image: If provided, uploads new version and replaces old URL
    - Version number increments automatically on update
    """
    try:
        user_id = user_info["uid"]
        mongo_service = get_mongodb_service()

        logger.info(f"🔄 Updating marketplace config for test {test_id}")
        logger.info(f"   User: {user_id}")

        # ========== Step 1: Validate test exists and user is creator ==========
        test_doc = mongo_service.db["online_tests"].find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        if test_doc.get("creator_id") != user_id:
            raise HTTPException(
                status_code=403,
                detail="Only test creator can update marketplace config",
            )

        # ========== Step 2: Check if test is published ==========
        marketplace_config = test_doc.get("marketplace_config", {})
        if not marketplace_config.get("is_public", False):
            raise HTTPException(
                status_code=400,
                detail="Test is not published. Use POST /marketplace/publish first.",
            )

        # ========== Step 3: Build update data ==========
        update_data = {}

        # Validate and update title
        if title is not None:
            if len(title) < 10:
                raise HTTPException(
                    status_code=400, detail="Title must be at least 10 characters"
                )
            update_data["marketplace_config.title"] = title
            logger.info(f"   Update title: {title}")

        # Validate and update description
        if description is not None:
            if len(description) < 50:
                raise HTTPException(
                    status_code=400, detail="Description must be at least 50 characters"
                )
            update_data["marketplace_config.description"] = description
            logger.info(f"   Update description (length: {len(description)})")

        # Update short description
        if short_description is not None:
            update_data["marketplace_config.short_description"] = short_description
            logger.info(f"   Update short_description")

        # Validate and update price
        if price_points is not None:
            if price_points < 0:
                raise HTTPException(status_code=400, detail="Price must be >= 0")
            update_data["marketplace_config.price_points"] = price_points
            logger.info(f"   Update price: {price_points} points")

        # Validate and update category
        if category is not None:
            valid_categories = [
                "programming",
                "language",
                "math",
                "science",
                "business",
                "technology",
                "design",
                "exam_prep",
                "certification",
                "other",
            ]
            if category not in valid_categories:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid category. Valid: {', '.join(valid_categories)}",
                )
            update_data["marketplace_config.category"] = category
            logger.info(f"   Update category: {category}")

        # Validate and update tags
        if tags is not None:
            tags_list = [tag.strip().lower() for tag in tags.split(",") if tag.strip()]
            if len(tags_list) < 1:
                raise HTTPException(
                    status_code=400, detail="At least 1 tag is required"
                )
            if len(tags_list) > 10:
                raise HTTPException(status_code=400, detail="Maximum 10 tags allowed")
            update_data["marketplace_config.tags"] = tags_list
            logger.info(f"   Update tags: {tags_list}")

        # Validate and update difficulty
        if difficulty_level is not None:
            valid_difficulty = ["beginner", "intermediate", "advanced", "expert"]
            if difficulty_level not in valid_difficulty:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid difficulty. Valid: {', '.join(valid_difficulty)}",
                )
            update_data["marketplace_config.difficulty_level"] = difficulty_level
            logger.info(f"   Update difficulty: {difficulty_level}")

        # Update public status (unpublish if False)
        if is_public is not None:
            update_data["marketplace_config.is_public"] = is_public
            logger.info(f"   Update is_public: {is_public}")

        # ========== Step 4: Handle cover image upload (if provided) ==========
        if cover_image:
            logger.info(f"   New cover image provided: {cover_image.filename}")

            # Validate image
            if not cover_image.content_type in ["image/jpeg", "image/png", "image/jpg"]:
                raise HTTPException(
                    status_code=400,
                    detail="Cover image must be JPG or PNG",
                )

            # Read file content
            cover_content = await cover_image.read()
            cover_size_mb = len(cover_content) / (1024 * 1024)

            if cover_size_mb > 5:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cover image too large: {cover_size_mb:.2f}MB (max 5MB)",
                )

            logger.info(f"   Cover image size: {cover_size_mb:.2f}MB")

            # Increment version for new upload
            current_version_str = marketplace_config.get("version", "v1")
            current_version_num = int(current_version_str.replace("v", ""))
            new_version = f"v{current_version_num + 1}"

            # Upload to R2
            cover_url = await upload_cover_to_r2(
                cover_content, test_id, new_version, cover_image.content_type
            )

            update_data["marketplace_config.cover_image_url"] = cover_url
            update_data["marketplace_config.version"] = new_version
            logger.info(f"   Uploaded new cover: {cover_url}")
            logger.info(f"   New version: {new_version}")

        # ========== Step 5: Ensure at least one field to update ==========
        if not update_data:
            raise HTTPException(
                status_code=400,
                detail="No fields to update. Provide at least one field to update.",
            )

        # Add updated_at timestamp
        update_data["updated_at"] = datetime.utcnow()

        # ========== Step 6: Update in database ==========
        result = mongo_service.db["online_tests"].update_one(
            {"_id": ObjectId(test_id)}, {"$set": update_data}
        )

        if result.modified_count == 0:
            logger.warning(f"⚠️ No changes made to test {test_id} (data might be same)")

        # ========== Step 7: Get updated config ==========
        updated_test = mongo_service.db["online_tests"].find_one(
            {"_id": ObjectId(test_id)}
        )
        updated_marketplace_config = updated_test.get("marketplace_config", {})

        logger.info(f"✅ Marketplace config updated for test {test_id}")

        return {
            "success": True,
            "test_id": test_id,
            "updated_fields": list(update_data.keys()),
            "marketplace_config": updated_marketplace_config,
            "updated_at": update_data["updated_at"].isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update marketplace config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{test_id}/marketplace/details",
    response_model=dict,
    tags=["Phase 5 - Marketplace"],
)
async def get_public_test_details(
    test_id: str,
    user_info: dict = Depends(require_auth),
):
    """
    Get full public test details for marketplace view (before starting test)

    Returns comprehensive information including:
    - Marketplace config (title, description, cover_image, price, difficulty)
    - Test statistics (num_questions, time_limit, passing_score)
    - Community stats (total_participants, average_participant_score, average_rating)
    - User status (already_participated, attempts_used, user_best_score)

    **Access:**
    - Must be a public test (marketplace_config.is_public = true)
    - Any authenticated user can view

    **Note:**
    - This is for VIEWING details only (before starting)
    - To start the test, use POST /{test_id}/start (which will deduct points)
    """
    try:
        user_id = user_info["uid"]
        mongo_service = get_mongodb_service()

        logger.info(f"📋 Get public test details: {test_id} for user {user_id}")

        # ========== Step 1: Get test document ==========
        test_doc = mongo_service.db["online_tests"].find_one({"_id": ObjectId(test_id)})

        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        # ========== Step 2: Check if test is public ==========
        marketplace_config = test_doc.get("marketplace_config", {})
        if not marketplace_config.get("is_public", False):
            raise HTTPException(
                status_code=403,
                detail="This test is not public. Only published marketplace tests can be viewed.",
            )

        # ========== Step 3: Get user's participation history ==========
        submissions_collection = mongo_service.db["test_submissions"]

        user_submissions = list(
            submissions_collection.find({"test_id": test_id, "user_id": user_id}).sort(
                "submitted_at", -1
            )
        )

        already_participated = len(user_submissions) > 0
        attempts_used = len(user_submissions)
        user_best_score = (
            max([s.get("score_percentage", 0) for s in user_submissions])
            if user_submissions
            else None
        )

        # ========== Step 4: Check if user is creator ==========
        is_creator = test_doc.get("creator_id") == user_id

        # ========== Step 5: Build response ==========
        response = {
            "success": True,
            "test_id": test_id,
            # Basic test info
            "title": marketplace_config.get("title", test_doc.get("title")),
            "description": marketplace_config.get(
                "description", test_doc.get("description")
            ),
            "short_description": marketplace_config.get("short_description"),
            "cover_image_url": marketplace_config.get("cover_image_url"),
            # Test configuration
            "num_questions": test_doc.get(
                "num_questions", len(test_doc.get("questions", []))
            ),
            "time_limit_minutes": test_doc.get("time_limit_minutes", 30),
            "passing_score": test_doc.get("passing_score", 70),
            "max_retries": test_doc.get("max_retries", 3),
            # Marketplace metadata
            "price_points": marketplace_config.get("price_points", 0),
            "category": marketplace_config.get("category"),
            "tags": marketplace_config.get("tags", []),
            "difficulty_level": marketplace_config.get("difficulty_level"),
            "version": marketplace_config.get("version"),
            # Community statistics
            "total_participants": marketplace_config.get("total_participants", 0),
            "average_participant_score": marketplace_config.get(
                "average_participant_score", 0.0
            ),
            "average_rating": marketplace_config.get("average_rating", 0.0),
            "rating_count": marketplace_config.get("rating_count", 0),
            # Publication info
            "published_at": (
                marketplace_config.get("published_at").isoformat()
                if marketplace_config.get("published_at")
                else None
            ),
            "creator_id": test_doc.get("creator_id"),
            # User-specific info
            "is_creator": is_creator,
            "already_participated": already_participated,
            "attempts_used": attempts_used,
            "user_best_score": user_best_score,
            # Additional metadata
            "creation_type": test_doc.get("creation_type"),
            "test_language": test_doc.get(
                "test_language", test_doc.get("language", "vi")
            ),
        }

        logger.info(f"✅ Public test details retrieved: {test_id}")
        logger.info(f"   Price: {response['price_points']} points")
        logger.info(
            f"   User participated: {already_participated} ({attempts_used} attempts)"
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get public test details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/me/earnings",
    response_model=dict,
    tags=["Phase 5 - Marketplace"],
)
async def get_my_earnings(
    user_info: dict = Depends(require_auth),
):
    """
    Get user's earnings from public tests

    Returns:
    - earnings_points: Total earnings available (can be withdrawn to cash)
    - total_earned: Lifetime earnings
    - earnings_transactions: Recent earnings history
    - pending_withdrawal: Any pending withdrawal requests

    **Note:**
    - earnings_points is separate from regular points
    - earnings_points can be withdrawn to real money
    - Regular points are for app usage only
    """
    try:
        user_id = user_info["uid"]
        mongo_service = get_mongodb_service()

        logger.info(f"💰 Get earnings for user: {user_id}")

        # Get user document (use firebase_uid)
        users_collection = mongo_service.db["users"]
        user_doc = users_collection.find_one({"firebase_uid": user_id})

        if not user_doc:
            raise HTTPException(status_code=404, detail="User not found")

        earnings_points = user_doc.get("earnings_points", 0)
        earnings_transactions = user_doc.get("earnings_transactions", [])

        # Calculate total lifetime earnings
        total_earned = sum(
            t.get("amount", 0) for t in earnings_transactions if t.get("type") == "earn"
        )

        # Get recent transactions (last 50)
        recent_transactions = sorted(
            earnings_transactions,
            key=lambda x: x.get("timestamp", datetime.min),
            reverse=True,
        )[:50]

        # Format transactions for response
        formatted_transactions = []
        for t in recent_transactions:
            formatted_transactions.append(
                {
                    "type": t.get("type"),
                    "amount": t.get("amount"),
                    "original_amount": t.get("original_amount"),
                    "percentage": t.get("percentage"),
                    "reason": t.get("reason"),
                    "test_id": t.get("test_id"),
                    "timestamp": (
                        t.get("timestamp").isoformat() if t.get("timestamp") else None
                    ),
                }
            )

        response = {
            "success": True,
            "earnings_points": earnings_points,
            "total_earned": total_earned,
            "total_withdrawn": total_earned - earnings_points,
            "recent_transactions": formatted_transactions,
        }

        logger.info(f"✅ Earnings retrieved: {earnings_points} points available")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get earnings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/me/earnings/withdraw",
    response_model=dict,
    tags=["Phase 5 - Marketplace"],
)
async def withdraw_earnings(
    amount: int,
    user_info: dict = Depends(require_auth),
):
    """
    Request to withdraw earnings to real money

    **Requirements:**
    - Minimum withdrawal: 100,000 points (100,000 VND)
    - earnings_points must be sufficient
    - Withdrawal will be processed manually by admin

    **Process:**
    1. User requests withdrawal
    2. Points are held (deducted from earnings_points)
    3. Admin reviews and transfers money
    4. Transaction is recorded

    **Note:**
    - This only works with earnings_points (not regular points)
    - Withdrawals are processed within 24-48 hours
    - User will receive money via bank transfer
    """
    try:
        user_id = user_info["uid"]
        mongo_service = get_mongodb_service()

        logger.info(f"💸 Withdrawal request: {amount} points from user {user_id}")

        # Minimum withdrawal check
        MIN_WITHDRAWAL = 100000
        if amount < MIN_WITHDRAWAL:
            raise HTTPException(
                status_code=400,
                detail=f"Minimum withdrawal is {MIN_WITHDRAWAL} points ({MIN_WITHDRAWAL:,} VND)",
            )

        # Get user document (use firebase_uid)
        users_collection = mongo_service.db["users"]
        user_doc = users_collection.find_one({"firebase_uid": user_id})

        if not user_doc:
            raise HTTPException(status_code=404, detail="User not found")

        earnings_points = user_doc.get("earnings_points", 0)

        # Check sufficient balance
        if earnings_points < amount:
            raise HTTPException(
                status_code=402,
                detail=f"Insufficient earnings. You have {earnings_points:,} points but requested {amount:,} points.",
            )

        # Deduct from earnings_points
        new_earnings = earnings_points - amount
        users_collection.update_one(
            {"firebase_uid": user_id},  # Use firebase_uid
            {
                "$set": {"earnings_points": new_earnings},
                "$push": {
                    "earnings_transactions": {
                        "type": "withdraw",
                        "amount": amount,
                        "reason": "Withdrawal to bank account",
                        "status": "pending",
                        "timestamp": datetime.utcnow(),
                        "balance_after": new_earnings,
                    }
                },
            },
        )

        # Create withdrawal request for admin review
        withdrawals_collection = mongo_service.db["withdrawal_requests"]
        withdrawal_doc = {
            "user_id": user_id,
            "amount": amount,
            "amount_vnd": amount,  # 1 point = 1 VND
            "status": "pending",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "user_email": user_info.get("email"),
            "user_name": user_info.get("name"),
        }

        result = withdrawals_collection.insert_one(withdrawal_doc)
        withdrawal_id = str(result.inserted_id)

        logger.info(f"✅ Withdrawal request created: {withdrawal_id}")
        logger.info(f"   Amount: {amount:,} points ({amount:,} VND)")
        logger.info(f"   User balance: {earnings_points:,} → {new_earnings:,}")

        return {
            "success": True,
            "withdrawal_id": withdrawal_id,
            "amount": amount,
            "amount_vnd": amount,
            "status": "pending",
            "message": "Withdrawal request submitted. You will receive money within 24-48 hours.",
            "new_balance": new_earnings,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to process withdrawal: {e}")
        raise HTTPException(status_code=500, detail=str(e))
