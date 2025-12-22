"""
Main FastAPI application factory and startup configuration
"""

import asyncio
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import time
from datetime import datetime
import asyncio
import os
import logging

from src.core.config import APP_CONFIG
from src.api.health_routes import router as health_router
from src.exceptions import InsufficientPointsError

# ✅ COMMENTED: Chat routes - Firebase auth dependency
# from src.api.chat_routes import router as chat_router
from src.api.real_estate_routes import router as real_estate_router
from src.api.ocr_routes import router as ocr_router
from src.api.loan_routes import router as loan_router

# ✅ ADDED: Document Processing API for Phase 1
from src.api.document_processing_routes import router as document_processing_router

# ✅ ADDED: Document Generation API for AI-powered document creation - KEEP (uses WordAI credentials)
from src.api.document_generation import router as document_generation_router

# ❌ REMOVED: Quote Generation API - Not used
# from src.api.quote_generation import router as quote_generation_router

# ❌ REMOVED: Quote Settings API - Not used
# from src.routes.quote_settings import router as quote_settings_router

# ❌ REMOVED: Enhanced Template Upload API - Not used
# from src.routes.enhanced_template_routes import router as enhanced_template_router

# ✅ ADDED: AI Sales Agent for loan consultation
from src.ai_sales_agent.api.routes import router as ai_sales_agent_router

# ✅ ADDED: Unified Chat System for multi-industry support
from src.api.unified_chat_routes import router as unified_chat_router

# ✅ ADDED: Conversation Analysis API for remarketing insights with Google Gemini
from src.api.conversation_analysis_routes import router as conversation_analysis_router

# ✅ ADDED: Admin API for Company Data Management - Modular Structure
from src.api.admin.company_routes import router as company_router
from src.api.admin.file_routes import router as file_router
from src.api.admin.products_services_routes import router as products_services_router
from src.api.admin.image_routes import router as image_router
from src.api.admin.task_status_routes import router as task_status_router

# ❌ REMOVED: Admin Template Management - Not used
# from src.routes.admin_template_routes import router as admin_template_router

# ✅ ADDED: Company Context and User History APIs for Optimized Chat
from src.api.admin.company_context_routes import router as company_context_router
from src.api.user_history_routes import router as user_history_router

# ✅ ADDED: AI Extraction API for structured data extraction
from src.api.extraction_routes import router as extraction_router

# ✅ ADDED: Hybrid Search Strategy for enhanced callbacks, search & CRUD
from src.api.hybrid_strategy_router import main_router as hybrid_strategy_router

# ✅ ADDED: Internal CORS management for chat-plugin dynamic domains
from src.api.internal_cors_routes import router as internal_cors_router

# ✅ ADDED: Dynamic CORS middleware for chat-plugin support
from src.middleware.dynamic_cors import DynamicCORSMiddleware

# ✅ ADDED: Hybrid Search API for direct search testing
from src.api.hybrid_search.hybrid_search_routes import router as hybrid_search_router

# ✅ ADDED: Firebase Authentication API for user management
from src.api.auth_routes import router as auth_router

# ✅ ADDED: Subscription & Points API for user subscription and points management
from src.api.subscription_routes import router as subscription_router

# ✅ ADDED: Billing History API for payment history
from src.api.billing_routes import router as billing_router

# ✅ ADDED: Support Ticket System API for customer support
from src.api.support_routes import router as support_router

# ✅ ADDED: Payment Activation API for subscription activation from payment service
from src.api.payment_activation_routes import router as payment_activation_router
from src.api.payment_activation_routes import points_router

# ✅ ADDED: USDT BEP20 Payment System - Cryptocurrency payments
from src.api.usdt_subscription_routes import router as usdt_subscription_router
from src.api.usdt_points_routes import router as usdt_points_router
from src.api.usdt_webhook_routes import router as usdt_webhook_router

# ✅ ADDED: E2EE Secret Documents - Key Management API
from src.api.secret_key_routes import router as secret_key_router

# ✅ ADDED: E2EE Secret Documents - CRUD API
from src.api.secret_document_routes import router as secret_document_router

# Authentication API
# from src.api.auth_routes import router as auth_router

# ✅ COMMENTED: HTML to DOCX Conversion API - Firebase auth dependency
# from src.api.conversion_routes import router as conversion_router

# ✅ UNCOMMENTED: Document Settings and History APIs - needed by frontend
from src.api.document_settings_routes import router as document_settings_router
from src.api.documents_history_routes import router as documents_history_router

# ✅ ADDED: Simple File Management API for basic file upload & folder CRUD
from src.api.simple_file_routes import router as simple_file_router

# ✅ ADDED: AI Content Edit API for Tiptap editor with multiple AI providers
from src.api.ai_content_edit import router as ai_content_edit_router

# ✅ ADDED: AI Chat API for streaming chat with file context
from src.api.ai_chat import router as ai_chat_router

# ✅ ADDED: Document Chat API for AI chat with document context and file support
from src.api.document_chat_routes import router as document_chat_router

# ✅ ADDED: Document Editor API for document management with auto-save
from src.api.document_editor_routes import router as document_editor_router

# ✅ ADDED: AI Editor Suite for document editing features (Edit, Translate, Format, Bilingual)
from src.api.ai_editor_routes import router as ai_editor_router

# ✅ ADDED: Document Export API for PDF, DOCX, TXT export with pagination
from src.api.document_export_routes import router as document_export_router

# ✅ ADDED: Book Export API for exporting books and chapters to PDF, DOCX, TXT, HTML
from src.api.book_export_routes import router as book_export_router

# ✅ ADDED: Library Files API for Type 3 files (templates, guides, references, resources)
from src.api.library_routes import router as library_router

# ✅ ADDED: Encrypted Library Images API for E2EE images (Zero-Knowledge)
from src.api.encrypted_library_routes import router as encrypted_library_router

# ✅ ADDED: Encrypted Folder API for folder management
from src.api.encrypted_folder_routes import router as encrypted_folder_router

# ✅ ADDED: Secret Images API - Dedicated endpoints for secret images with folder support
from src.api.secret_images_routes import router as secret_images_router

# ✅ ADDED: Online Test API for test generation and taking (Phase 1-3) - Split into 4 modules
from src.api.test_creation_routes import router as test_creation_router
from src.api.test_taking_routes import router as test_taking_router
from src.api.test_grading_routes import router as test_grading_router
from src.api.test_marketplace_routes import router as test_marketplace_router

# ✅ ADDED: Test Translation API for translating tests to different languages
from src.api.test_translation_routes import router as test_translation_router

# ✅ ADDED: Test Statistics API for analytics and reporting
from src.api.test_statistics_routes import router as test_statistics_router

# ✅ ADDED: Test Sharing API for Online Test Phase 4 (Sharing & Collaboration)
from src.api.test_sharing_routes import router as test_sharing_router

# ✅ ADDED: Listening Audio Management API for editing transcript and regenerating audio
from src.api.listening_audio_routes import router as listening_audio_router

# ✅ ADDED: Test Marketplace API for Online Test Phase 5 (Marketplace)
from src.api.marketplace_routes import router as marketplace_router
from src.api.marketplace_transactions_routes import (
    router as marketplace_transactions_router,
)

# ✅ ADDED: WebSocket service for Online Test Phase 2 (Real-time auto-save)
from src.services.test_websocket_service import get_websocket_service

# ✅ ADDED: Share API for File Sharing System (Phase 2)
from src.api.share_routes import router as share_router

# ✅ ADDED: Notification API for InApp notification system
from src.api.notification_routes import router as notification_router

# ✅ ADDED: Document Editor API for document management with auto-save
from src.api.document_editor_routes import router as document_editor_router

# ✅ ADDED: Gemini Slide Parser API for presentation slides with native PDF support
from src.api.gemini_slide_parser_routes import router as gemini_slide_parser_router

# ✅ ADDED: Slide Share API for public presentation sharing with analytics
from src.api.slide_share_routes import router as slide_share_router

# ✅ ADDED: PDF Document API - Upload, Split, Merge, and AI Conversion
from src.api.pdf_document_routes import router as pdf_document_router

# ✅ ADDED: Public API routes (no auth) for wordai.pro homepage
from src.api.public_routes import router as public_router

# Configure logging
logger = logging.getLogger(__name__)

# ✅ NEW: Online Books API - GitBook-style documentation system (renamed from User Guides)
from src.api.book_routes import router as book_router

# ✅ NEW: Book Chapter Management API - Chapter CRUD, reordering, bulk updates
from src.api.book_chapter_routes import router as book_chapter_router

# ✅ NEW: Book Public & Community API - Public view, Community marketplace, Discovery
from src.api.book_public_routes import router as book_public_router

# ✅ NEW: Book Marketplace API - Earnings, Purchases, My Published Books
from src.api.book_marketplace_routes import router as book_marketplace_router

# ✅ ADDED: Book Advanced API - Translation & Duplication features
from src.api.book_advanced_routes import router as book_advanced_router

# ✅ ADDED: Book Translation API - Multi-language support (17 languages)
from src.api.book_translation_routes import router as book_translation_router

# ✅ ADDED: Translation Job API - Background translation jobs with status tracking
from src.api.translation_job_routes import router as translation_job_router

# ✅ ADDED: Book Chapter Audio API - Audio narration for chapters (upload, TTS, multi-language)
from src.api.book_chapter_audio_routes import router as book_chapter_audio_router

# ✅ ADDED: Standalone Audio API - Voices and preview endpoints (not tied to book/chapter)
from src.api.audio_routes import router as audio_router

# ✅ ADDED: Book Cover AI - Generate covers using OpenAI gpt-image-1
from src.api.book_cover_ai_routes import router as book_cover_ai_router

# ✅ ADDED: Test Cover AI - Generate covers for online tests using Gemini 3 Pro Image
from src.api.test_cover_ai_routes import router as test_cover_ai_router

# ✅ ADDED: Test Evaluation AI - AI-powered evaluation of test results
from src.api.test_evaluation_routes import router as test_evaluation_router

# ✅ ADDED: Book Background API - AI-powered A4 backgrounds for books and chapters
from src.api.book_background_routes import router as book_background_router
from src.api.book_background_routes import (
    upload_router as book_background_upload_router,
    slide_router as slide_background_router,
)

# ✅ ADDED: Slide AI API - AI-powered slide formatting and editing
from src.api.slide_ai_routes import router as slide_ai_router

# ✅ ADDED: Slide Narration API - AI-powered subtitle and audio generation
from src.api.slide_narration_routes import router as slide_narration_router

# ✅ ADDED: Slide AI Generation API - AI-powered slide creation from scratch
from src.api.slide_ai_generation_routes import router as slide_ai_generation_router

# ✅ ADDED: Author API - Community books author management
from src.api.author_routes import router as author_router

# ✅ ADDED: Saved Books API - User's bookmarked books
from src.api.book_saved_routes import router as saved_books_router

# ✅ ADDED: Book Reviews API - User reviews and ratings for books
from src.api.book_review_routes import router as book_review_router

# ✅ ADDED: Community Books API - Public browsing and discovery
from src.api.community_routes import router as community_router

# ✅ ADDED: Image Generation API - AI-powered image generation using Gemini 2.5 Flash Image
from src.api.image_generation_routes import router as image_generation_router
from src.api.image_generation_phase2_routes import (
    router as image_generation_phase2_router,
)

# ✅ ADDED: Image Editing API - AI-powered image editing using Gemini 3 Pro Image
from src.api.image_editing_routes import router as image_editing_router

# ✅ ADDED: Font Upload API - Custom font upload and management with R2 storage
from src.api.font_routes import router as font_router

# ✅ ADDED: Media Upload API - Pre-signed URL for direct R2 image uploads (documents/chapters)
from src.api.media_routes import router as media_router

# Global startup time for uptime tracking
startup_time = time.time()

# Global worker management
background_workers = {}

# ✅ Initialize Firebase Admin SDK IMMEDIATELY (before any route definitions)
print("🔥 Initializing Firebase Admin SDK globally...")
try:
    from src.config.firebase_config import FirebaseConfig

    firebase_config = FirebaseConfig()
    print("✅ Firebase Admin SDK initialized globally")
except Exception as e:
    print(f"❌ Firebase initialization failed: {e}")
    # Don't raise error - let app continue without Firebase


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    ✅ STARTUP/SHUTDOWN: Application lifecycle management
    """
    # ===== STARTUP =====
    print("🚀 Starting AI Chatbot RAG Service...")
    print(
        f"   Environment: {APP_CONFIG.get('debug', False) and 'Development' or 'Production'}"
    )
    print(f"   Host: {APP_CONFIG['host']}")
    print(f"   Port: {APP_CONFIG['port']}")
    print(f"   Base URL: {APP_CONFIG['base_url']}")

    # Initialize global components here if needed
    try:
        # Load documents or initialize services
        await load_documents()

        # ✅ Start background workers
        await start_background_workers()

        print("✅ Application startup completed")
    except Exception as e:
        print(f"❌ Startup error: {e}")
        raise

    yield

    # ===== SHUTDOWN =====
    print("🛑 Shutting down AI Chatbot RAG Service...")

    # ✅ Shutdown background workers
    await shutdown_background_workers()

    print("✅ Shutdown completed")


async def load_documents():
    """
    ✅ Load documents and initialize services on startup
    """
    global documents
    documents = {}

    try:
        print("📚 Loading documents and initializing services...")

        # Firebase is now initialized in serve.py before app import
        # No need to initialize it here anymore

        # Add any other initialization logic here
        # For example: load vector store, initialize AI providers, etc.

        print("✅ Documents and services loaded successfully")

    except Exception as e:
        print(f"❌ Failed to load documents: {e}")
        raise


async def start_background_workers():
    """
    ✅ Start background workers for queue processing
    """
    try:
        print("🔧 Starting background workers...")

        # ===== START DOCUMENT PROCESSING WORKER (for /upload endpoint) =====
        print("📄 Starting DocumentProcessingWorker for /upload endpoint...")
        from src.workers.document_processing_worker import DocumentProcessingWorker

        doc_worker = DocumentProcessingWorker(
            worker_id="app_doc_worker", poll_interval=2.0  # Poll every 2 seconds
        )

        await doc_worker.initialize()

        # Start worker in background task
        doc_worker_task = asyncio.create_task(doc_worker.run())
        background_workers["document_worker"] = {
            "worker": doc_worker,
            "task": doc_worker_task,
        }

        print("✅ DocumentProcessingWorker started")

        # ===== START EXTRACTION PROCESSING WORKER (Worker 1) =====
        print(
            "🎯 Starting ExtractionProcessingWorker (Worker 1: AI extraction only)..."
        )
        from src.workers.extraction_processing_worker import ExtractionProcessingWorker

        extraction_worker = ExtractionProcessingWorker(
            worker_id="app_extraction_worker", poll_interval=1.0
        )

        await extraction_worker.initialize()

        # Start worker in background task
        extraction_worker_task = asyncio.create_task(extraction_worker.run())
        background_workers["extraction_worker"] = {
            "worker": extraction_worker,
            "task": extraction_worker_task,
        }

        print("✅ ExtractionProcessingWorker started")

        # ===== START STORAGE PROCESSING WORKER (Worker 2) =====
        print(
            "💾 Starting StorageProcessingWorker (Worker 2: Qdrant + callback only)..."
        )
        from src.workers.storage_processing_worker import StorageProcessingWorker

        storage_worker = StorageProcessingWorker(
            worker_id="app_storage_worker", poll_interval=1.0
        )

        await storage_worker.initialize()

        # Start worker in background task
        storage_worker_task = asyncio.create_task(storage_worker.run())
        background_workers["storage_worker"] = {
            "worker": storage_worker,
            "task": storage_worker_task,
        }

        print("✅ StorageProcessingWorker started")

        # ===== START AI EDITOR WORKER =====
        print("🎨 Starting AI Editor Worker (Edit/Format)...")
        from src.workers.ai_editor_worker import AIEditorWorker

        ai_editor_worker = AIEditorWorker(worker_id="app_ai_editor_worker")

        await ai_editor_worker.initialize()

        ai_editor_worker_task = asyncio.create_task(ai_editor_worker.run())
        background_workers["ai_editor_worker"] = {
            "worker": ai_editor_worker,
            "task": ai_editor_worker_task,
        }

        print("✅ AI Editor Worker started")

        # ===== START SLIDE GENERATION WORKER =====
        print("📊 Starting Slide Generation Worker...")
        from src.workers.slide_generation_worker import SlideGenerationWorker

        slide_gen_worker = SlideGenerationWorker(worker_id="app_slide_gen_worker")

        await slide_gen_worker.initialize()

        slide_gen_worker_task = asyncio.create_task(slide_gen_worker.run())
        background_workers["slide_generation_worker"] = {
            "worker": slide_gen_worker,
            "task": slide_gen_worker_task,
        }

        print("✅ Slide Generation Worker started")

        # ===== START TRANSLATION WORKER =====
        print("🌐 Starting Translation Worker...")
        from src.workers.translation_worker import TranslationWorker

        translation_worker = TranslationWorker(worker_id="app_translation_worker")

        await translation_worker.initialize()

        translation_worker_task = asyncio.create_task(translation_worker.run())
        background_workers["translation_worker"] = {
            "worker": translation_worker,
            "task": translation_worker_task,
        }

        print("✅ Translation Worker started")

        # ===== START SLIDE FORMAT WORKER =====
        print("🎨 Starting Slide Format Worker...")
        from src.workers.slide_format_worker import SlideFormatWorker

        slide_format_worker = SlideFormatWorker(worker_id="app_slide_format_worker")

        await slide_format_worker.initialize()

        slide_format_worker_task = asyncio.create_task(slide_format_worker.run())
        background_workers["slide_format_worker"] = {
            "worker": slide_format_worker,
            "task": slide_format_worker_task,
        }

        print("✅ Slide Format Worker started")

        # ===== START CHAPTER TRANSLATION WORKER =====
        print("📖 Starting Chapter Translation Worker...")
        from src.workers.chapter_translation_worker import ChapterTranslationWorker

        chapter_translation_worker = ChapterTranslationWorker(
            worker_id="app_chapter_translation_worker"
        )

        await chapter_translation_worker.initialize()

        chapter_translation_worker_task = asyncio.create_task(
            chapter_translation_worker.run()
        )
        background_workers["chapter_translation_worker"] = {
            "worker": chapter_translation_worker,
            "task": chapter_translation_worker_task,
        }

        print("✅ Chapter Translation Worker started")

        # ===== START USDT PAYMENT VERIFICATION WORKER =====
        print("💰 Starting USDT Payment Verification Worker...")
        from src.services.usdt_verification_job import start_verification_job

        # Create verification task
        verification_task = asyncio.create_task(start_verification_job())
        background_workers["usdt_verification"] = {
            "worker": None,  # Job manages itself
            "task": verification_task,
        }

        print("✅ USDT Payment Verification Worker started (checking every 30s)")

        print("")
        print("🎉 All workers started successfully!")
        print("📋 Worker Architecture:")
        print(
            "   📄 DocumentProcessingWorker → /upload endpoint (DocumentProcessingTask only)"
        )
        print(
            "   🎯 ExtractionProcessingWorker → Worker 1: AI extraction for /process-async"
        )
        print(
            "   💾 StorageProcessingWorker → Worker 2: Qdrant storage + backend callbacks"
        )
        print("   🎨 AI Editor Worker → AI Edit/Format operations (ai_editor queue)")
        print(
            "   📊 Slide Generation Worker → AI slide HTML generation (slide_generation queue)"
        )
        print(
            "   🌐 Translation Worker → Book translation jobs (translation_jobs queue)"
        )
        print(
            "   🎨 Slide Format Worker → Single slide AI formatting (slide_format queue)"
        )
        print(
            "   📖 Chapter Translation Worker → Chapter translation + optional new chapter creation (chapter_translation queue)"
        )
        print(
            "   💰 USDT Verification Worker → Scan blockchain for pending USDT payments"
        )
        print("   🔄 Flow: API → Worker 1 (AI) → Worker 2 (Storage) → Backend")

    except Exception as e:
        print(f"❌ Failed to start background workers: {e}")
        raise


async def shutdown_background_workers():
    """
    ✅ Shutdown background workers gracefully
    """
    try:
        print("🛑 Shutting down background workers...")

        for worker_name, worker_info in background_workers.items():
            try:
                print(f"   🛑 Stopping {worker_name}...")

                # Shutdown worker (if it has a worker instance)
                if worker_info.get("worker"):
                    await worker_info["worker"].shutdown()

                # Special handling for USDT verification job
                if worker_name == "usdt_verification":
                    from src.services.usdt_verification_job import stop_verification_job

                    stop_verification_job()

                # Cancel task
                worker_info["task"].cancel()
                try:
                    await worker_info["task"]
                except asyncio.CancelledError:
                    pass

                print(f"   ✅ {worker_name} stopped")

            except Exception as worker_error:
                print(f"   ❌ Error stopping {worker_name}: {worker_error}")

        background_workers.clear()
        print("✅ All background workers stopped")

    except Exception as e:
        print(f"❌ Error shutting down workers: {e}")


def create_app() -> FastAPI:
    """
    ✅ FastAPI application factory
    """
    app = FastAPI(
        title="AI Chatbot RAG Service",
        description="Advanced AI-powered chatbot with RAG capabilities, document processing, OCR, and financial services",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if APP_CONFIG["debug"] else None,
        redoc_url="/redoc" if APP_CONFIG["debug"] else None,
        redirect_slashes=False,  # Tắt auto-redirect để tránh HTTPS downgrade
    )

    # ===== VALIDATION ERROR HANDLER =====
    logger = logging.getLogger("chatbot")

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        """Log validation errors with full details"""
        logger.error("=" * 80)
        logger.error(f"❌ FASTAPI VALIDATION ERROR (422)")
        logger.error(f"   Path: {request.url.path}")
        logger.error(f"   Method: {request.method}")
        logger.error(
            f"   Content-Type: {request.headers.get('content-type', 'NOT SET')}"
        )

        # Try to get the body - FastAPI may have cached it
        body_str = "Could not read body"
        try:
            # Try to get from exc.body first (available in newer FastAPI versions)
            if hasattr(exc, "body"):
                body_str = (
                    exc.body.decode("utf-8")
                    if isinstance(exc.body, bytes)
                    else str(exc.body)
                )
            else:
                # Fallback: try to read from request (may fail if already consumed)
                body = await request.body()
                body_str = body.decode("utf-8")
        except Exception as e:
            body_str = f"Error reading body: {e}"

        logger.error(f"   Request Body: {body_str}")
        logger.error(f"   Validation Errors ({len(exc.errors())} total):")
        for i, error in enumerate(exc.errors(), 1):
            logger.error(f"      {i}. Location: {error.get('loc', 'unknown')}")
            logger.error(f"         Message: {error.get('msg', 'unknown')}")
            logger.error(f"         Type: {error.get('type', 'unknown')}")
            if "input" in error:
                logger.error(f"         Input: {error['input']}")
        logger.error("=" * 80)

        return JSONResponse(status_code=422, content={"detail": exc.errors()})

    @app.exception_handler(InsufficientPointsError)
    async def insufficient_points_handler(
        request: Request, exc: InsufficientPointsError
    ):
        """
        Global handler for insufficient points errors

        Returns HTTP 402 Payment Required with standardized format:
        {
            "error": "INSUFFICIENT_POINTS",
            "message": "Vietnamese error message",
            "points_needed": 2,
            "points_available": 0,
            "service": "ai_chat_chatgpt",
            "action_required": "purchase_points",
            "purchase_url": "/pricing"
        }

        Frontend should detect error="INSUFFICIENT_POINTS" and show popup
        prompting user to purchase more points.
        """
        logger.warning(f"💰 Insufficient points: {exc.message}")
        logger.warning(f"   Service: {exc.service}")
        logger.warning(
            f"   Required: {exc.points_needed}, Available: {exc.points_available}"
        )

        return JSONResponse(status_code=402, content=exc.to_dict())

    # ===== CORS MIDDLEWARE REMOVED =====
    # CORS is now handled at the bottom of the file based on ENVIRONMENT variable
    # This prevents duplicate CORS middleware that was causing "true, true" headers

    # Dynamic CORS middleware for chat-plugin support (streaming routes only)
    backend_url = APP_CONFIG.get("backend_webhook_url", "http://localhost:8001")
    app.add_middleware(DynamicCORSMiddleware, backend_url=backend_url)

    # ===== PROXY HEADERS MIDDLEWARE =====
    @app.middleware("http")
    async def handle_proxy_headers(request: Request, call_next):
        """
        Handle X-Forwarded-Proto header from Nginx to preserve HTTPS in redirects
        This prevents FastAPI from downgrading HTTPS → HTTP when redirecting
        """
        # Get the X-Forwarded-Proto header (set by Nginx)
        forwarded_proto = request.headers.get("X-Forwarded-Proto")

        if forwarded_proto:
            # Update request scope to use the forwarded protocol
            request.scope["scheme"] = forwarded_proto

        response = await call_next(request)
        return response

    # ===== SECURITY MIDDLEWARE =====
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        """Add security headers to all responses"""
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"

        return response

    # ===== IMAGE API REQUEST LOGGING MIDDLEWARE =====
    @app.middleware("http")
    async def log_image_api_requests(request: Request, call_next):
        """
        Log ALL requests to /api/v1/images/* endpoints to debug missing logs
        This runs BEFORE authentication middleware
        """
        path = request.url.path

        if "/api/v1/images/" in path:
            logger = logging.getLogger("chatbot")
            logger.info(f"🖼️ IMAGE API REQUEST RECEIVED:")
            logger.info(f"   Path: {path}")
            logger.info(f"   Method: {request.method}")
            logger.info(f"   Origin: {request.headers.get('origin', 'none')}")
            logger.info(
                f"   Content-Type: {request.headers.get('content-type', 'none')}"
            )
            logger.info(
                f"   Authorization: {'present' if request.headers.get('authorization') else 'MISSING'}"
            )
            logger.info(
                f"   Client: {request.client.host if request.client else 'unknown'}"
            )

        response = await call_next(request)

        if "/api/v1/images/" in path:
            logger = logging.getLogger("chatbot")
            logger.info(f"🖼️ IMAGE API RESPONSE: {response.status_code}")

        return response

    # ===== REQUEST LOGGING MIDDLEWARE (for debugging suspicious requests) =====
    @app.middleware("http")
    async def log_suspicious_requests(request: Request, call_next):
        """
        Log detailed info for suspicious requests (404s, non-API paths)
        Helps track browser extensions, malware, or unwanted injected scripts
        """
        response = await call_next(request)

        # Log suspicious patterns
        suspicious_paths = [
            "/js/",
            "/css/",
            "/fonts/",
            "/images/",
            "/twint",
            "/lkk",
            "/support_parent",
        ]

        path = request.url.path
        is_suspicious = response.status_code == 404 and (
            path == "/" or any(pattern in path for pattern in suspicious_paths)
        )

        if is_suspicious:
            logger = logging.getLogger("chatbot")
            client_host = request.client.host if request.client else "unknown"
            user_agent = request.headers.get("user-agent", "unknown")
            referer = request.headers.get("referer", "none")
            origin = request.headers.get("origin", "none")

            logger.warning(
                f"🚨 SUSPICIOUS REQUEST [404]:\n"
                f"   Path: {path}\n"
                f"   Client: {client_host}\n"
                f"   User-Agent: {user_agent[:100]}...\n"
                f"   Referer: {referer}\n"
                f"   Origin: {origin}\n"
                f"   ⚠️ Possible browser extension/malware injecting scripts"
            )

        return response

    # ===== REGISTER ROUTERS =====

    # ✅ Authentication endpoints - Firebase auth for user management
    app.include_router(auth_router, tags=["Firebase Authentication"])

    # ✅ Subscription & Points endpoints - User subscription and points management
    app.include_router(subscription_router, tags=["Subscription & Points"])

    # ✅ Payment Activation endpoint - IPN subscription activation from payment service
    app.include_router(payment_activation_router, tags=["Payment Activation"])

    # ✅ Points Management endpoint - Points purchase from payment service
    app.include_router(points_router, tags=["Points Management"])

    # ✅ Billing History endpoints - Payment history
    app.include_router(billing_router, tags=["Billing & Payments"])

    # ✅ USDT BEP20 Payment System - Cryptocurrency payments
    app.include_router(usdt_subscription_router, tags=["USDT - Subscription Payments"])
    app.include_router(usdt_points_router, tags=["USDT - Points Purchase"])
    app.include_router(usdt_webhook_router, tags=["USDT - Webhooks"])

    # ✅ Support System endpoints - Customer support tickets
    app.include_router(support_router, tags=["Customer Support"])

    # ✅ E2EE Secret Documents - Key Management endpoints
    app.include_router(secret_key_router, tags=["E2EE - Key Management"])

    # ✅ E2EE Secret Documents - CRUD endpoints
    app.include_router(secret_document_router, tags=["E2EE - Secret Documents"])

    # Health and status endpoints
    app.include_router(health_router, tags=["Health"])

    # ✅ Public API endpoints (no auth) - For wordai.pro homepage
    app.include_router(public_router, tags=["Public"])

    # ✅ COMMENTED: Chat endpoints - Firebase auth dependency
    # app.include_router(chat_router, prefix="/api/chat", tags=["Chat"])

    # ✅ COMMENTED: Support legacy frontend paths - Firebase auth dependency
    # app.include_router(chat_router, tags=["Chat - Legacy Paths"])

    # Unified Chat System - Multi-industry with intelligent routing
    app.include_router(unified_chat_router, tags=["Unified Chat - Multi-Industry"])

    # Conversation Analysis API - Remarketing insights with Google Gemini
    app.include_router(
        conversation_analysis_router,
        tags=["Conversation Analysis", "Remarketing", "Gemini AI"],
    )

    # Real estate analysis endpoints
    app.include_router(real_estate_router, tags=["Real Estate"])

    # OCR endpoints
    app.include_router(ocr_router, tags=["OCR"])

    # Loan assessment endpoints
    app.include_router(loan_router, tags=["Loan Assessment"])

    # Document processing endpoints
    app.include_router(document_processing_router, tags=["Document Processing"])

    # ❌ REMOVED: Quote generation endpoints - Not used
    # app.include_router(quote_generation_router, tags=["Quote Generation", "Gemini AI"])

    # ❌ REMOVED: Quote settings endpoints - Not used
    # app.include_router(
    #     quote_settings_router, tags=["Quote Settings", "User Preferences"]
    # )

    # ❌ REMOVED: Template upload endpoints - Not used
    # app.include_router(
    #     enhanced_template_router,
    #     tags=["Template Management", "AI Analysis", "PDF Processing"],
    # )

    # AI Sales Agent endpoints for loan consultation
    app.include_router(
        ai_sales_agent_router,
        prefix="/api/sales-agent",
        tags=["AI Sales Agent - Loan Consultation"],
    )

    # Conversation Analysis API for remarketing insights
    app.include_router(
        conversation_analysis_router,
        prefix="/api/conversation-analysis",
        tags=["Conversation Analysis - Google Gemini"],
    )

    # Admin routers for company data management - Modular Structure
    app.include_router(
        company_router, prefix="/api/admin", tags=["Admin - Company Management"]
    )
    app.include_router(
        file_router, prefix="/api/admin", tags=["Admin - File Management"]
    )
    app.include_router(
        products_services_router,
        prefix="/api/admin",
        tags=["Admin - Products & Services"],
    )
    app.include_router(
        image_router, prefix="/api/admin", tags=["Admin - Image Processing"]
    )
    app.include_router(task_status_router)

    # ❌ REMOVED: Admin Template Management - Not used
    # app.include_router(admin_template_router, tags=["Admin - System Templates"])

    # ✅ COMMENTED: HTML to DOCX Conversion API - Firebase auth dependency
    # app.include_router(conversion_router, tags=["Document Conversion"])

    # ✅ RESTORED: Document Settings and History APIs - needed by frontend
    app.include_router(document_settings_router, tags=["Document Settings"])
    app.include_router(documents_history_router, tags=["Documents History"])

    # ✅ ADDED: AI Content Edit API - HTML editing with AI
    app.include_router(ai_content_edit_router, tags=["AI Content Edit"])

    # ✅ ADDED: AI Chat API - Streaming chat with file context
    app.include_router(ai_chat_router, tags=["AI Chat"])

    # ✅ ADDED: Document Chat API - AI chat with document context
    app.include_router(document_chat_router, tags=["Document Chat"])

    # ✅ ADDED: Document Editor API - Document management with auto-save
    app.include_router(document_editor_router, tags=["Document Editor"])

    # ✅ ADDED: AI Editor Suite - Edit, Translate, Format, Bilingual Conversion
    app.include_router(ai_editor_router, tags=["AI Editor Suite"])

    # ✅ ADDED: Document Export API - Export to PDF, DOCX, TXT with pagination
    app.include_router(document_export_router, tags=["Document Export"])

    # ✅ ADDED: Book Export API - Export books and chapters to PDF, DOCX, TXT, HTML
    app.include_router(book_export_router, tags=["Book Export"])

    # ✅ ADDED: Test Sharing API - Online Test Phase 4 (Sharing & Collaboration)
    # IMPORTANT: Mount BEFORE online_test_router to prioritize specific routes like /shared-with-me
    app.include_router(test_sharing_router, tags=["Online Tests - Phase 4: Sharing"])

    # ✅ ADDED: Test Marketplace API - Online Test Phase 5 (Marketplace)
    # Mount marketplace routes before online_test_router for priority
    app.include_router(marketplace_router, tags=["Online Tests - Phase 5: Marketplace"])
    app.include_router(
        marketplace_transactions_router, tags=["Online Tests - Phase 5: Transactions"]
    )

    # ✅ REFACTORED: Online Test API - Split into 4 specialized routers
    app.include_router(test_creation_router, tags=["Online Tests - Creation"])
    app.include_router(test_taking_router, tags=["Online Tests - Taking"])
    app.include_router(test_grading_router, tags=["Online Tests - Grading"])
    app.include_router(test_marketplace_router, tags=["Online Tests - Marketplace"])

    # ✅ ADDED: Test Translation API - Translate tests to different languages
    app.include_router(test_translation_router, tags=["Online Tests - Translation"])

    # ✅ ADDED: Test Statistics API - Analytics and reporting for tests and users
    app.include_router(test_statistics_router, tags=["Online Tests - Statistics"])

    # ✅ ADDED: Listening Audio Management API - Edit transcript and regenerate audio
    app.include_router(listening_audio_router, tags=["Online Tests - Listening Audio"])

    # ✅ ADDED: WebSocket support for Online Test Phase 2 (Real-time auto-save)
    websocket_service = get_websocket_service()
    app.mount("/socket.io", websocket_service.get_asgi_app())
    print("🔌 WebSocket mounted at /socket.io for Online Test real-time features")

    # ✅ ADDED: Company Context and User History APIs
    app.include_router(company_context_router)
    app.include_router(user_history_router)

    # ✅ ADDED: AI Extraction API
    app.include_router(extraction_router, tags=["AI Extraction - Products & Services"])

    # ✅ ADDED: Hybrid Search API for direct testing
    app.include_router(hybrid_search_router, tags=["Hybrid Search API"])

    # ✅ ADDED: Document Generation API for AI-powered document creation - KEEP
    app.include_router(document_generation_router, tags=["Document Generation"])

    # ✅ NEW: Simple File Management API with R2 integration
    app.include_router(simple_file_router, tags=["Simple File Management"])

    # ✅ NEW: Library Files API - Type 3 files (Phase 1 complete)
    app.include_router(library_router, tags=["Library Files"])

    # ✅ NEW: Encrypted Library Images API - E2EE images with Zero-Knowledge
    app.include_router(
        encrypted_library_router, tags=["Encrypted Library Images - E2EE"]
    )

    # ✅ NEW: Encrypted Library Folders API - Folder management for E2EE images
    app.include_router(
        encrypted_folder_router, tags=["Encrypted Library Folders - E2EE"]
    )

    # ✅ NEW: Secret Images API - Dedicated endpoints for secret images with folder support
    app.include_router(secret_images_router, tags=["Secret Images"])

    # ✅ NEW: Share API - File Sharing System (Phase 2 complete)
    app.include_router(share_router, tags=["File Sharing"])

    # ✅ NEW: Notification API - InApp notification system
    app.include_router(notification_router, tags=["Notifications"])

    # ✅ REMOVED DUPLICATE: AI Content Edit API already included above (line 734)
    # app.include_router(ai_content_edit_router, tags=["AI Content Editing"])

    # ✅ NEW: Gemini Slide Parser API - Native PDF support for presentations
    app.include_router(
        gemini_slide_parser_router,
        tags=["Gemini Slide Parser", "AI Document Processing"],
    )

    # ✅ NEW: Slide Share API - Public presentation sharing with password & analytics
    app.include_router(
        slide_share_router,
        tags=["Slide Sharing", "Public Presentations"],
    )

    # ✅ NEW: PDF Document API - Upload, Split, Merge, and AI Conversion
    app.include_router(
        pdf_document_router,
        tags=["PDF Documents", "AI Conversion", "Document Management"],
    )

    # ✅ NEW: Book Marketplace API - Earnings, Purchases, My Published Books
    # IMPORTANT: Register BEFORE book_router to prioritize specific routes like /my-published, /earnings
    # over dynamic route /{book_id}
    app.include_router(
        book_marketplace_router,
        tags=["Book Marketplace", "Earnings", "Purchases"],
    )

    # ✅ NEW: Book Chapter Management API - Chapter CRUD, reordering, bulk updates
    app.include_router(
        book_chapter_router,
        tags=["Online Books Chapters", "Chapter Management"],
    )

    # ✅ NEW: Book Public & Community API - Public view, Community marketplace, Discovery
    app.include_router(
        book_public_router,
        tags=["Online Books Public & Community", "Book Discovery"],
    )

    # ✅ NEW: Online Books API - GitBook-style documentation system (renamed from User Guides)
    # Contains dynamic route /{book_id} - must be registered AFTER specific routes
    app.include_router(
        book_router,
        tags=["Online Books", "Documentation System"],
    )

    # ✅ NEW: Book Advanced API - Translation & Duplication features
    app.include_router(
        book_advanced_router,
        tags=["Book Advanced", "Translation", "Duplication"],
    )

    # ✅ NEW: Book Translation API - Multi-language support (17 languages)
    app.include_router(
        book_translation_router,
        tags=["Book Translation", "Multi-Language", "AI Translation"],
    )

    # ✅ NEW: Translation Job API - Background translation jobs with status tracking
    app.include_router(
        translation_job_router,
        tags=["Translation Jobs", "Background Processing", "Job Status"],
    )

    # ✅ NEW: Book Chapter Audio API - Audio narration for chapters (upload, TTS, multi-language)
    app.include_router(
        book_chapter_audio_router,
        tags=["Book Audio", "Chapter Audio", "TTS", "Audio Narration"],
    )

    # ✅ NEW: Standalone Audio API - Voices and preview endpoints
    app.include_router(
        audio_router,
        tags=["Audio", "TTS", "Voice Preview"],
    )

    # ✅ NEW: Book Cover AI - Generate covers using OpenAI gpt-image-1
    app.include_router(
        book_cover_ai_router,
        tags=["AI Book Cover", "Image Generation"],
    )

    # ✅ NEW: Test Cover AI - Generate covers for online tests (16:9)
    app.include_router(
        test_cover_ai_router,
        tags=["AI Test Cover", "Online Tests"],
    )

    # ✅ NEW: Test Evaluation AI - AI-powered evaluation of test results
    app.include_router(
        test_evaluation_router,
        tags=["AI Test Evaluation", "Feedback"],
    )

    # ✅ NEW: Book Background API - AI-powered A4 backgrounds for books and chapters
    app.include_router(
        book_background_router,
        tags=["Book Backgrounds", "Chapter Backgrounds", "AI Background Generation"],
    )

    # ✅ Background image upload endpoint
    app.include_router(
        book_background_upload_router,
        tags=["Book Background Upload"],
    )

    # ✅ Slide background generation endpoint
    app.include_router(
        slide_background_router,
        tags=["Slide Backgrounds", "AI Background Generation"],
    )

    # ✅ NEW: Slide AI API - AI-powered slide formatting and editing
    app.include_router(
        slide_ai_router,
        tags=["Slide AI", "AI Formatting"],
    )

    # ✅ NEW: Slide Narration API - AI-powered subtitle and audio generation
    app.include_router(
        slide_narration_router,
        tags=["Slide Narration", "AI"],
    )

    # ✅ NEW: Slide AI Generation API - AI-powered slide creation from scratch
    app.include_router(
        slide_ai_generation_router,
        tags=["Slide AI Generation", "AI"],
    )

    # ✅ NEW: Author API - Community books author management
    app.include_router(
        author_router,
        tags=["Authors", "Community Books"],
    )

    # ✅ NEW: Saved Books API - User's bookmarked books
    app.include_router(
        saved_books_router,
        prefix="/api/v1",
        tags=["Saved Books", "Bookmarks"],
    )

    # ✅ NEW: Book Reviews API - User reviews and ratings for books
    app.include_router(
        book_review_router,
        prefix="/api/v1",
        tags=["Book Reviews", "Ratings"],
    )

    # ✅ NEW: Community Books API - Public browsing and discovery
    app.include_router(
        community_router,
        prefix="/api/v1",
        tags=["Community Books", "Public Discovery"],
    )

    # ✅ ADDED: Internal CORS management for chat-plugin
    app.include_router(internal_cors_router, tags=["Internal CORS"])

    # ✅ ADDED: Image Generation API - AI-powered image generation (Phase 1: Photorealistic, Stylized, Logo)
    app.include_router(image_generation_router, tags=["AI Image Generation"])

    # ✅ ADDED: Image Generation Phase 2 API - Background, Mockup, Sequential Art
    app.include_router(
        image_generation_phase2_router, tags=["AI Image Generation - Phase 2"]
    )

    # ✅ ADDED: Image Editing API - Style Transfer, Object Edit, Inpainting, Composition
    app.include_router(image_editing_router, tags=["AI Image Editing"])

    # ✅ ADDED: Font Upload API - Custom font upload and management with R2 storage
    app.include_router(font_router, tags=["Custom Fonts", "Font Management"])

    # ✅ ADDED: Media Upload API - Pre-signed URL for direct R2 image uploads
    app.include_router(media_router, tags=["Media Upload", "Image Upload"])

    # ✅ Hybrid Search Strategy - Enhanced callbacks, search & CRUD operations
    app.include_router(
        hybrid_strategy_router,
        prefix="/api",
        tags=[
            "Hybrid Search Strategy",
            "Enhanced Callbacks",
            "Metadata + Vector Search",
        ],
    )

    # ✅ Admin Task Status API
    app.include_router(
        task_status_router, prefix="/api/admin", tags=["Admin - Task Status"]
    )

    print("✅ FastAPI application created with all routes")
    print("📌 AI Content Edit endpoints:")
    print("   POST /api/ai/content/edit - AI-powered content editing")
    print("   GET  /api/ai/content/health - Health check")
    print("   GET  /api/ai/content/providers - Available AI providers")
    print("   GET  /api/ai/content/operations - Supported operations")
    print("📌 Unified Chat System endpoints:")
    print("   POST /api/unified/chat-stream - Streaming version of unified chat")
    print("   POST /api/unified/detect-intent - Intent detection only")
    print("   GET  /api/unified/industries - Supported industries")
    print("   GET  /api/unified/languages - Supported languages")
    print("   GET  /api/unified/session/{id} - Session management")
    print("   DELETE /api/unified/session/{id} - Clear session")
    print("📌 AI Sales Agent endpoints:")
    print("   POST /api/sales-agent/chat - Natural conversation for loan consultation")
    print("   POST /api/sales-agent/assess - Loan assessment based on collected data")
    print(
        "   POST /api/sales-agent/check-readiness - Check if data is ready for assessment"
    )
    print(
        "   GET  /api/sales-agent/suggest-questions/{session_id} - Get smart question suggestions"
    )
    print("   DELETE /api/sales-agent/session/{session_id} - Clear session data")
    print("📌 Admin API endpoints:")
    print("   POST /api/admin/companies/register - Register new company")
    print("   GET  /api/admin/companies/{id} - Get company details")
    print("   GET  /api/admin/companies/{id}/stats - Get company data statistics")
    print(
        "   POST /api/admin/companies/{id}/context/basic-info/from-backend - Update basic info (Backend format)"
    )
    print(
        "   POST /api/admin/companies/{id}/files/upload - Upload company files (R2 URL only)"
    )
    print("   POST /api/admin/companies/{id}/extract - Extract data from files")
    print("   POST /api/admin/companies/{id}/search - Search company data")
    print(
        "   GET  /api/admin/industries/{industry}/data-types - Get supported data types"
    )
    print("   GET  /api/admin/file-types - Get supported file types")

    return app


# Create the FastAPI application instance
app = create_app()

# CORS Middleware
# IMPORTANT: Only add CORSMiddleware if NOT in production.
# In production, Nginx handles all CORS headers. Adding them here will cause duplication.
if os.getenv("ENVIRONMENT") != "production":
    print("✅ DEVELOPMENT MODE: Enabling FastAPI CORSMiddleware.")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:3001",
            "http://localhost:3002",
            "https://aivungtau.com",
            "https://www.aivungtau.com",
        ],  # Origins for dev
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    print("✅ PRODUCTION MODE: Skipping FastAPI CORSMiddleware (handled by Nginx).")

# Global variable for document storage (will be moved to proper service later)
documents = {}
