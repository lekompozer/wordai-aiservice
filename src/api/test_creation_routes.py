"""
Online Test Creation Routes
Endpoints for AI generation, manual creation, test configuration, and owner statistics
"""

import logging
import os
import uuid
from typing import Optional, Dict, Any
from datetime import datetime
from bson import ObjectId

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

from src.middleware.auth import verify_firebase_token as require_auth
from src.models.online_test_models import *
from src.services.online_test_utils import *

logger = logging.getLogger("chatbot")

router = APIRouter(prefix="/api/v1/tests", tags=["Test Creation"])


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

        # Validate creator_name if provided
        if request.creator_name:
            from src.services.creator_name_validator import validate_creator_name

            user_email = user_info.get("email", "")
            validate_creator_name(request.creator_name, user_email, user_info["uid"])

        test_doc = {
            "title": request.title,
            "description": request.description,
            "creator_name": request.creator_name,
            "test_category": request.test_category,
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
            test_category=request.test_category,
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


# ========== NEW: Generate Test from General Knowledge ==========


class GenerateGeneralTestRequest(BaseModel):
    """Request model for AI-generated test from general knowledge"""

    title: str = Field(..., description="Test title", min_length=5, max_length=200)
    description: Optional[str] = Field(
        None,
        description="Test description for test takers (optional, user-facing)",
        max_length=1000,
    )
    creator_name: Optional[str] = Field(
        None, min_length=2, max_length=100, description="Custom creator display name"
    )
    topic: str = Field(
        ...,
        description="Topic/Category (e.g., 'Leadership Styles', 'Python Programming', 'MBTI Personality')",
        min_length=3,
        max_length=200,
    )
    user_query: str = Field(
        ...,
        description="Detailed instructions for AI (e.g., 'Focus on modern theories', 'Include practical examples')",
        min_length=10,
        max_length=2000,
    )
    test_category: str = Field(
        default="academic",
        description="Test category: 'academic' or 'diagnostic'",
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


@router.post("/generate/general")
async def generate_test_from_general_knowledge(
    request: GenerateGeneralTestRequest,
    background_tasks: BackgroundTasks,
    user_info: dict = Depends(require_auth),
):
    """
    Generate a new test from general AI knowledge (no file/document required)

    **NEW Endpoint**: Creates tests based on topic and user query without needing source material.

    **Use Cases:**
    - Personality/diagnostic tests (e.g., MBTI, leadership style assessment)
    - General knowledge quizzes (e.g., history, science trivia)
    - Skill assessments based on common knowledge

    **Flow:**
    1. Create test record with status='pending' and source_type='general_knowledge'
    2. Return test_id immediately
    3. Start background AI generation
    4. Frontend polls status endpoint
    """
    try:
        logger.info(f"📝 General test generation request from user {user_info['uid']}")
        logger.info(f"   Topic: {request.topic}")
        logger.info(f"   Category: {request.test_category}")
        logger.info(f"   Title: {request.title}")

        # Create test record
        mongo_service = get_mongodb_service()
        collection = mongo_service.db["online_tests"]

        # Validate creator_name if provided
        if request.creator_name:
            from src.services.creator_name_validator import validate_creator_name

            user_email = user_info.get("email", "")
            validate_creator_name(request.creator_name, user_email, user_info["uid"])

        test_doc = {
            "title": request.title,
            "description": request.description,
            "creator_name": request.creator_name,
            "test_category": request.test_category,
            "user_query": request.user_query,
            "test_language": request.language,
            "source_type": "general_knowledge",
            "source_document_id": None,
            "source_file_r2_key": None,
            "topic": request.topic,  # NEW: Store topic
            "creator_id": user_info["uid"],
            "time_limit_minutes": request.time_limit_minutes,
            "num_questions": request.num_questions,
            "max_retries": request.max_retries,
            "passing_score": request.passing_score,
            "deadline": request.deadline,
            "show_answers_timing": request.show_answers_timing,
            "creation_type": "ai_generated",
            "status": "pending",
            "progress_percent": 0,
            "questions": [],
            "is_active": True,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

        result = collection.insert_one(test_doc)
        test_id = str(result.inserted_id)

        logger.info(f"✅ Test record created: {test_id} with status='pending'")

        # Build comprehensive content from topic and query
        content = f"""Topic: {request.topic}

Instructions: {request.user_query}

Generate a comprehensive {request.test_category} test based on general knowledge of this topic."""

        # Start background job
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
            source_type="general_knowledge",
            source_id=request.topic,
            time_limit_minutes=request.time_limit_minutes,
            gemini_pdf_bytes=None,
            num_options=request.num_options if request.num_options > 0 else 4,
            num_correct_answers=(
                request.num_correct_answers if request.num_correct_answers > 0 else 1
            ),
            test_category=request.test_category,
        )

        logger.info(f"🚀 Background job queued for general test {test_id}")

        return {
            "success": True,
            "test_id": test_id,
            "status": "pending",
            "title": request.title,
            "description": request.description,
            "topic": request.topic,
            "test_category": request.test_category,
            "num_questions": request.num_questions,
            "time_limit_minutes": request.time_limit_minutes,
            "created_at": test_doc["created_at"].isoformat(),
            "message": "Test created successfully. AI is generating questions from general knowledge...",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ General test generation failed: {e}")
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


# ========== NEW: Presigned URL for Essay Answer Media Upload ==========


@router.post("/manual")
async def create_manual_test(
    request: CreateManualTestRequest,
    user_info: dict = Depends(require_auth),
):
    """
    Create a test with manually entered questions

    **UPDATED**:
    - Questions are now optional - can create empty draft test
    - Supports Essay and Mixed-format questions (Phase 2)

    User can:
    1. Create empty test with just title → Add questions later
    2. Create test with MCQ, Essay, or Mixed questions → Continue editing
    3. Duplicate existing test → Modify copy

    Test is immediately set to status='ready' (no AI generation needed).

    **Question Types:**
    - MCQ: Traditional multiple-choice (auto-graded)
    - Essay: Free-text response (manual grading required)
    - Mixed: Combination of MCQ and Essay

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
                q_type = getattr(q, "question_type", "mcq")

                if q_type == "mcq":
                    # MCQ validation
                    if not q.options or len(q.options) < 2:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Question {idx+1}: MCQ must have at least 2 options",
                        )

                    # Validate correct_answer_key exists in options
                    # For diagnostic tests, correct_answer_key is optional
                    if request.test_category != "diagnostic":
                        if not q.correct_answer_key:
                            raise HTTPException(
                                status_code=400,
                                detail=f"Question {idx+1}: correct_answer_key is required for academic tests",
                            )

                        option_keys = [opt["key"] for opt in q.options]
                        if q.correct_answer_key not in option_keys:
                            raise HTTPException(
                                status_code=400,
                                detail=f"Question {idx+1}: correct_answer_key '{q.correct_answer_key}' not found in options",
                            )

                elif q_type == "essay":
                    # Essay validation
                    if q.options or q.correct_answer_key:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Question {idx+1}: Essay questions cannot have options or correct_answer_key",
                        )

                    if not q.max_points or q.max_points < 1 or q.max_points > 100:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Question {idx+1}: Essay max_points must be between 1 and 100",
                        )

                else:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Question {idx+1}: Invalid question_type '{q_type}'. Must be 'mcq' or 'essay'",
                    )

        # Create test record
        mongo_service = get_mongodb_service()
        collection = mongo_service.db["online_tests"]

        # Validate creator_name if provided
        if request.creator_name:
            from src.services.creator_name_validator import validate_creator_name

            user_email = user_info.get("email", "")
            validate_creator_name(request.creator_name, user_email, user_info["uid"])

        # Format questions with question_id
        import uuid

        formatted_questions = []
        if request.questions:
            for q in request.questions:
                q_type = getattr(q, "question_type", "mcq")

                question_dict = {
                    "question_id": str(uuid.uuid4())[:8],
                    "question_text": q.question_text,
                    "question_type": q_type,
                    "max_points": getattr(q, "max_points", 1),
                }

                # Add MCQ-specific fields
                if q_type == "mcq":
                    question_dict.update(
                        {
                            "options": q.options,
                            "correct_answer_key": q.correct_answer_key,
                            "explanation": q.explanation,
                        }
                    )

                # Add Essay-specific fields
                elif q_type == "essay":
                    if hasattr(q, "grading_rubric") and q.grading_rubric:
                        question_dict["grading_rubric"] = q.grading_rubric

                # Add media fields if present
                if hasattr(q, "media_type") and q.media_type:
                    question_dict["media_type"] = q.media_type
                    question_dict["media_url"] = q.media_url
                    question_dict["media_description"] = getattr(
                        q, "media_description", ""
                    )

                formatted_questions.append(question_dict)

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
            "creator_name": request.creator_name,
            "test_category": request.test_category,
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
            "grading_config": request.grading_config,  # NEW: Weighted scoring configuration
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
            "test_category": original_test.get("test_category", "academic"),
            "evaluation_criteria": original_test.get("evaluation_criteria"),
            "user_query": original_test.get("user_query"),
            "test_language": original_test.get("test_language")
            or original_test.get(
                "language", "vi"
            ),  # Support both old and new field names
            "source_type": original_test.get("source_type", "manual"),
            "source_document_id": original_test.get("source_document_id"),
            "source_file_r2_key": original_test.get("source_file_r2_key"),
            "topic": original_test.get("topic"),  # For general_knowledge tests
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

        # Log warning if diagnostic test missing evaluation_criteria
        if duplicated_doc["test_category"] == "diagnostic" and not duplicated_doc.get(
            "evaluation_criteria"
        ):
            logger.warning(
                f"⚠️ Duplicating diagnostic test {test_id} without evaluation_criteria"
            )

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

        # Query filter: only active tests (not soft-deleted)
        query_filter = {
            "creator_id": user_info["uid"],
            "is_active": {"$ne": False},  # Include True and null (legacy tests)
        }

        # Get total count of active tests
        total_count = test_collection.count_documents(query_filter)

        # Get user's created tests with pagination, sorted by updated_at (latest first)
        tests = list(
            test_collection.find(query_filter)
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

            # Get marketplace config if exists
            marketplace_config = test.get("marketplace_config", {})
            is_public = marketplace_config.get("is_public", False)

            test_info = {
                "test_id": test_id,
                "title": test["title"],
                "description": test.get("description"),  # Optional field
                "num_questions": len(test.get("questions", [])),
                "time_limit_minutes": test["time_limit_minutes"],
                "test_category": test.get(
                    "test_category", "academic"
                ),  # Add diagnostic/academic indicator
                "status": test.get(
                    "status", "ready"
                ),  # pending, generating, ready, failed, draft
                "is_active": test.get("is_active", True),
                "created_at": test["created_at"].isoformat(),
                "updated_at": test.get("updated_at", test["created_at"]).isoformat(),
                "total_submissions": attempts_count,
            }

            # Add marketplace info if published
            if is_public:
                test_info["is_public"] = True
                test_info["marketplace"] = {
                    "price_points": marketplace_config.get("price_points", 0),
                    "category": marketplace_config.get("category"),
                    "difficulty_level": marketplace_config.get("difficulty_level"),
                    "total_participants": marketplace_config.get(
                        "total_participants", 0
                    ),
                    "average_rating": marketplace_config.get("average_rating", 0.0),
                    "evaluation_criteria": marketplace_config.get(
                        "evaluation_criteria"
                    ),
                }
            else:
                test_info["is_public"] = False

            result.append(test_info)

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

        if request.evaluation_criteria is not None:
            # Update in marketplace_config if test is published
            marketplace_config = test_doc.get("marketplace_config", {})
            if marketplace_config.get("is_public", False):
                update_data["marketplace_config.evaluation_criteria"] = (
                    request.evaluation_criteria
                )
                logger.info(
                    f"📝 Updating evaluation_criteria for published test {test_id}"
                )

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

            q_type = q.get("question_type", "mcq")

            if q_type not in ["mcq", "essay"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Question {idx + 1}: question_type must be 'mcq' or 'essay'",
                )

            if q_type == "mcq":
                # MCQ validation
                if not q.get("options") or len(q["options"]) < 2:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Question {idx + 1}: MCQ requires at least 2 options",
                    )

                # Check if test is diagnostic
                test_category = test_doc.get("test_category", "academic")
                is_diagnostic = test_category == "diagnostic"

                # Support both correct_answer_key (string) and correct_answer_keys (array)
                has_correct_answer_key = q.get("correct_answer_key")
                has_correct_answer_keys = q.get("correct_answer_keys")

                # Skip correct_answer validation for diagnostic tests
                if not is_diagnostic:
                    if not has_correct_answer_key and not has_correct_answer_keys:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Question {idx + 1}: MCQ requires correct_answer_key or correct_answer_keys",
                        )

                # Get option keys for validation
                option_keys = [opt.get("key") for opt in q["options"]]

                # Normalize to correct_answer_keys array format (only for academic tests)
                if not is_diagnostic:
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

            elif q_type == "essay":
                # Essay validation
                if (
                    q.get("options")
                    or q.get("correct_answer_key")
                    or q.get("correct_answer_keys")
                ):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Question {idx + 1}: Essay questions cannot have options or correct answers",
                    )

            # Validate and set max_points for all question types
            max_points = q.get("max_points", 1)
            if (
                not isinstance(max_points, (int, float))
                or max_points < 1
                or max_points > 100
            ):
                raise HTTPException(
                    status_code=400,
                    detail=f"Question {idx + 1}: max_points must be between 1 and 100",
                )

            # Set default max_points if not provided
            if "max_points" not in q:
                q["max_points"] = 1

            # Validate media fields if present
            if q.get("media_type"):
                if q["media_type"] not in ["image", "audio"]:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Question {idx + 1}: media_type must be 'image' or 'audio'",
                    )
                if not q.get("media_url"):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Question {idx + 1}: media_url is required when media_type is set",
                    )

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

        # Creator name update with validation
        if request.creator_name is not None:
            from src.services.creator_name_validator import validate_creator_name

            user_email = user_info.get("email", "")
            # Validate uniqueness and reserved names, allow same test to keep its name
            validate_creator_name(request.creator_name, user_email, user_id, test_id)
            update_data["creator_name"] = request.creator_name
            logger.info(f"   Update creator_name: {request.creator_name}")

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

            # Validate questions structure (support MCQ and Essay)
            for idx, q in enumerate(request.questions):
                if not q.get("question_text"):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Question {idx + 1}: question_text is required",
                    )

                q_type = q.get("question_type", "mcq")

                if q_type not in ["mcq", "essay"]:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Question {idx + 1}: question_type must be 'mcq' or 'essay'",
                    )

                if q_type == "mcq":
                    # MCQ validation
                    if not q.get("options") or len(q["options"]) < 2:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Question {idx + 1}: MCQ requires at least 2 options",
                        )

                    if not q.get("correct_answer_key"):
                        raise HTTPException(
                            status_code=400,
                            detail=f"Question {idx + 1}: MCQ requires correct_answer_key",
                        )

                elif q_type == "essay":
                    # Essay validation
                    if q.get("options") or q.get("correct_answer_key"):
                        raise HTTPException(
                            status_code=400,
                            detail=f"Question {idx + 1}: Essay questions cannot have options or correct_answer_key",
                        )

                    max_points = q.get("max_points", 1)
                    if (
                        not isinstance(max_points, (int, float))
                        or max_points < 1
                        or max_points > 100
                    ):
                        raise HTTPException(
                            status_code=400,
                            detail=f"Question {idx + 1}: max_points must be between 1 and 100",
                        )

                    # Set default max_points if not provided
                    if "max_points" not in q:
                        q["max_points"] = 1

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

            if request.evaluation_criteria is not None:
                marketplace_updates["marketplace_config.evaluation_criteria"] = (
                    request.evaluation_criteria
                )
                logger.info(f"   Update evaluation_criteria")

        elif any(
            [
                request.marketplace_title,
                request.marketplace_description,
                request.short_description,
                request.price_points is not None,
                request.category,
                request.tags,
                request.difficulty_level,
                request.evaluation_criteria,
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
